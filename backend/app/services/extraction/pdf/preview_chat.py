"""Natural-language Q&A over extracted table catalogs (Preview / chat console)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from app.services.extraction.pdf.suggest_search import _catalog_entry, _sanitize_ids
from app.services.llm_prompts import OPENAI_MODEL, TABLE_PREVIEW_CHAT_PROMPT

logger = logging.getLogger(__name__)

_REMOVE_HINT = re.compile(
    r"\b(remove|delete|drop|discard|exclude|get rid of|take out)\b",
    re.IGNORECASE,
)

_SHOW_FIND_HINT = re.compile(
    r"(?i)\b(show|display|highlight|filter\s+(to|down)?|open)\b"
    r"|show\s+(me\s+)?(the\s+)?(them|those|these)\b"
    r"|^(show\s+them|show\s+those|show\s+these)\s*[.!?]*$"
)

_MAX_CONVERSATION_TURNS = 10


def _format_conversation_block(conversation: List[Dict[str, Any]] | None) -> str:
    if not conversation:
        return ""
    lines = ["Recent conversation (resolve follow-ups like \"show them\" from this):"]
    for turn in conversation[-_MAX_CONVERSATION_TURNS:]:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "user").strip().lower()
        if role not in ("user", "assistant"):
            continue
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        label = "Steward" if role == "user" else "Dhara"
        lines.append(f"{label}: {content}")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines) + "\n\n"


def _combined_search_prompt(prompt: str, conversation: List[Dict[str, Any]] | None) -> str:
    chunks = [prompt.strip()]
    for turn in (conversation or [])[-_MAX_CONVERSATION_TURNS:]:
        if not isinstance(turn, dict):
            continue
        content = str(turn.get("content") or "").strip()
        if content:
            chunks.append(content)
    return "\n\n".join(chunks)


def preview_chat_from_prompt(
    *,
    prompt: str,
    tables: List[Dict[str, Any]],
    api_key: str,
    conversation: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Answer about catalog tables; optional find/remove table_ids for UI actions."""
    text = (prompt or "").strip()
    if not text:
        raise ValueError("prompt is required")
    if not (api_key or "").strip():
        raise ValueError("An LLM API key is required in Settings")

    catalog = [_catalog_entry(t) for t in tables if t.get("table_id") is not None]
    valid_ids = {str(c["table_id"]) for c in catalog if c["table_id"]}
    if not valid_ids:
        return {
            "reply": "There are no extracted tables in this release yet.",
            "action": "none",
            "table_ids": [],
        }

    from openai import OpenAI

    user_prompt = TABLE_PREVIEW_CHAT_PROMPT.format(
        conversation_block=_format_conversation_block(conversation),
        prompt=text,
        catalog_json=json.dumps(catalog, ensure_ascii=False),
    )
    client = OpenAI(api_key=api_key.strip())
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=2000,
        temperature=0.2,
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        logger.warning("preview_chat: non-JSON LLM response: %s", raw[:300])
        return {
            "reply": "I could not interpret that response. Try rephrasing your question.",
            "action": "none",
            "table_ids": [],
        }

    if not isinstance(data, dict):
        data = {}

    reply = str(data.get("reply") or "").strip()
    if not reply:
        reply = "I do not have enough context to answer that from the table list alone."

    action_raw = str(data.get("action") or "none").strip().lower()
    wants_remove = bool(_REMOVE_HINT.search(text)) and action_raw == "remove"
    if wants_remove:
        action = "remove"
    elif action_raw == "find":
        action = "find"
    else:
        action = "none"

    selected = _sanitize_ids(data.get("table_ids"), valid_ids) if action != "none" else []

    needs_find_fallback = (
        action != "remove"
        and (action != "find" or not selected)
        and (_SHOW_FIND_HINT.search(text) or _is_show_follow_up(text))
    )
    if needs_find_fallback:
        from app.services.extraction.pdf.suggest_search import suggest_tables_from_prompt

        combined = _combined_search_prompt(text, conversation)
        try:
            search_result = suggest_tables_from_prompt(
                prompt=combined,
                tables=tables,
                api_key=api_key,
            )
        except ValueError:
            search_result = {}
        search_ids = _sanitize_ids(search_result.get("table_ids"), valid_ids)
        if search_ids and search_result.get("intent") != "remove":
            find_reply = reply
            if not find_reply or _generic_non_find_reply(find_reply):
                find_reply = str(search_result.get("rationale") or "").strip()
            if not find_reply:
                find_reply = f"Showing {len(search_ids)} matching table(s) in the preview."
            return {
                "reply": find_reply,
                "action": "find",
                "table_ids": search_ids,
            }

    return {
        "reply": reply,
        "action": action,
        "table_ids": selected,
    }


def _is_show_follow_up(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {
        "show them",
        "show those",
        "show these",
        "display them",
        "display those",
        "show me",
        "show",
        "them",
        "those",
    } or bool(re.match(r"^show\s+(them|those|these)\s*[.!?]*$", t, re.I))


def _generic_non_find_reply(reply: str) -> bool:
    lower = (reply or "").lower()
    return (
        "cell-level data" in lower
        or "let me know which table" in lower
        or "please let me know" in lower
    )
