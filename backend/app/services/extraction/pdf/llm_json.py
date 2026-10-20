"""Best-effort JSON parsing for Preview chat / AI-search LLM replies."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    return cleaned


def _close_truncated_json(text: str) -> str:
    """Append missing quotes / brackets when the model hits max_tokens mid-object."""
    s = (text or "").rstrip()
    if not s:
        return s

    in_str = False
    escape = False
    stack: List[str] = []
    for ch in s:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()

    if in_str:
        s += '"'
    # Drop a trailing comma before we close.
    s = re.sub(r",\s*$", "", s)
    while stack:
        s += stack.pop()
    return s


def _extract_table_ids_regex(raw: str) -> List[str]:
    """Pull string ids from a (possibly truncated) table_ids array."""
    match = re.search(r'"table_ids"\s*:\s*\[(.*)', raw or "", re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', match.group(1))


def _extract_field_string(raw: str, field: str) -> Optional[str]:
    match = re.search(
        rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)"',
        raw or "",
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


def loads_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON object from an LLM reply; recover truncated table_ids lists."""
    text = (raw or "").strip()
    if not text:
        return None

    candidates = [text, _strip_fences(text)]
    repaired = _strip_fences(text)
    repaired = (
        repaired.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    candidates.append(repaired)
    candidates.append(_close_truncated_json(repaired))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data

    # Truncation salvage: rebuild a minimal object from fragments.
    ids = _extract_table_ids_regex(text)
    action = _extract_field_string(text, "action")
    intent = _extract_field_string(text, "intent")
    reply = _extract_field_string(text, "reply")
    rationale = _extract_field_string(text, "rationale")
    if not ids and not action and not intent and not reply and not rationale:
        return None

    salvaged: Dict[str, Any] = {}
    if reply is not None:
        salvaged["reply"] = reply
    if rationale is not None:
        salvaged["rationale"] = rationale
    if action is not None:
        salvaged["action"] = action
    if intent is not None:
        salvaged["intent"] = intent
    if ids:
        salvaged["table_ids"] = ids
    logger.warning(
        "llm_json: salvaged truncated response (action=%s intent=%s ids=%s)",
        salvaged.get("action") or salvaged.get("intent"),
        salvaged.get("intent"),
        len(ids),
    )
    return salvaged
