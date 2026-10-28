"""Natural-language Q&A over extracted table catalogs (Preview / chat console)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from app.services.extraction.pdf.llm_json import loads_llm_json
from app.services.llm.chat_commands import lines_from_tables, match_stage_command, run_stage_command
from app.services.llm.profiles import fit_gemma_2b_completion, gemma_2b_json_response_format
from app.services.extraction.pdf.suggest_search import _catalog_entry, _sanitize_ids
from app.services.llm_prompts import TABLE_PREVIEW_CHAT_PROMPT

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
    from app.services.llm.factory import live_openai_chat

    llm = live_openai_chat(api_key)
    if llm is None:
        raise ValueError("An LLM API key is required in Settings")

    if match_stage_command(text):
        return run_stage_command(
            command=text,
            lines=lines_from_tables(tables),
            api_key=api_key,
        )

    catalog = [_catalog_entry(t) for t in tables if t.get("table_id") is not None]
    valid_ids = {str(c["table_id"]) for c in catalog if c["table_id"]}
    if not valid_ids:
        return {
            "reply": "There are no extracted tables in this release yet.",
            "action": "none",
            "table_ids": [],
        }

    user_prompt = TABLE_PREVIEW_CHAT_PROMPT.format(
        conversation_block=_format_conversation_block(conversation),
        prompt=text,
        catalog_json=json.dumps(catalog, ensure_ascii=False),
    )
    # Large catalogs need a long reply on big models. Gemma 2 2B's context is 8192.
    user_prompt, max_tokens = fit_gemma_2b_completion(llm.model, user_prompt, 8000)
    client = llm.openai_sdk()
    create_kwargs = {
        "model": llm.model,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    response_format = gemma_2b_json_response_format(llm.model)
    if response_format is not None:
        create_kwargs["response_format"] = response_format
    resp = client.chat.completions.create(**create_kwargs)
    raw = llm.completion_text(resp.choices[0].message).strip()
    try:
        data = llm.loads_json(raw, context="preview_chat")
    except json.JSONDecodeError:
        data = loads_llm_json(raw) or {}
    if not isinstance(data, dict):
        data = {}
    if not data:
        logger.warning(
            "preview_chat: non-JSON LLM response profile=%s: %s",
            llm.profile_tag(),
            raw[:300],
        )

    reply = str(data.get("reply") or "").strip()
    action_raw = str(data.get("action") or "none").strip().lower()
    user_wants_remove = bool(_REMOVE_HINT.search(text))
    # Treat as remove when the model agrees, or when JSON failed but the prompt
    # clearly asked to delete (so we can fall through to suggest_search).
    wants_remove = user_wants_remove and (action_raw == "remove" or not data)

    if wants_remove:
        action = "remove"
    elif action_raw == "find":
        action = "find"
    else:
        action = "none"

    selected = _sanitize_ids(data.get("table_ids"), valid_ids) if action != "none" else []

    needs_search_fallback = (
        (action == "remove" and not selected)
        or (
            action != "remove"
            and (action != "find" or not selected)
            and (_SHOW_FIND_HINT.search(text) or _is_show_follow_up(text))
        )
    )
    if needs_search_fallback:
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
        search_intent = str(search_result.get("intent") or "find").strip().lower()
        if search_ids and user_wants_remove and (
            wants_remove or search_intent == "remove"
        ):
            remove_reply = reply
            if not remove_reply or not data:
                remove_reply = str(search_result.get("rationale") or "").strip()
            if not remove_reply:
                remove_reply = (
                    f"Found {len(search_ids)} table(s) to remove. Confirm in chat to delete them."
                )
            return {
                "reply": remove_reply,
                "action": "remove",
                "table_ids": search_ids,
            }
        if search_ids and search_intent != "remove" and not wants_remove:
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

    if not data and not selected:
        return {
            "reply": "I could not interpret that response. Try rephrasing your question.",
            "action": "none",
            "table_ids": [],
        }

    if not reply:
        if action == "remove" and selected:
            reply = (
                f"Found {len(selected)} table(s) to remove. Confirm in chat to delete them."
            )
        elif action == "find" and selected:
            reply = f"Found {len(selected)} matching table(s)."
        else:
            reply = "I do not have enough context to answer that from the table list alone."

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
