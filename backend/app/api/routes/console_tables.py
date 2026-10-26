"""Stateless console table AI search (batch preview / grouping tables)."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    chat_ready_for_user,
    get_db,
    llm_routing_for_user,
    require_user_email,
    resolve_llm_credentials,
)
from app.services.llm.routing import llm_routing_scope

router = APIRouter()


def _table_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    tid = str(raw.get("table_id") or raw.get("_uid") or "").strip()
    title = str(raw.get("title") or raw.get("id") or "").strip()
    entry: Dict[str, Any] = {
        "table_id": tid,
        "title": title or "Table",
    }
    if raw.get("page") is not None:
        entry["page"] = raw.get("page")
    summary = raw.get("short_description") or raw.get("description")
    if summary:
        entry["short_description"] = str(summary)[:240]
    if raw.get("filename"):
        entry["filename"] = str(raw.get("filename"))
    return entry


@router.post("/api/console/tables/ai-search")
async def console_ai_search_tables(
    request: Request,
    user_email: str = Depends(require_user_email),
    db: Session = Depends(get_db),
):
    """Natural-language table find/remove for Console batch tables.

    Body: ``{ prompt, tables: [{ table_id|_uid, title, ... }] }``
    Returns ``{ intent, table_ids, rationale }`` — never mutates server state.
    """
    from app.services.extraction.pdf.suggest_search import suggest_tables_from_prompt

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    prompt = str(body.get("prompt") or body.get("query") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")

    api_key, _provider = resolve_llm_credentials(request, user_email, db=db)
    if not chat_ready_for_user(db, user_email, api_key, _provider):
        raise HTTPException(
            400,
            "Configure LLM in Settings (cloud API key or on-prem model) before using AI search",
        )
    routing = llm_routing_for_user(db, user_email)

    tables_raw = body.get("tables")
    if not isinstance(tables_raw, list):
        raise HTTPException(400, "tables array is required")

    catalog: List[Dict[str, Any]] = []
    for item in tables_raw:
        if not isinstance(item, dict):
            continue
        row = _table_payload(item)
        if row["table_id"]:
            catalog.append(row)

    if not catalog:
        return {
            "intent": "find",
            "table_ids": [],
            "rationale": "No tables are available.",
        }

    with llm_routing_scope(routing):
        result = suggest_tables_from_prompt(
            prompt=prompt,
            tables=[{"table_id": c["table_id"], **c} for c in catalog],
            api_key=api_key,
        )
    return result


@router.post("/api/console/tables/ai-chat")
async def console_ai_chat_tables(
    request: Request,
    user_email: str = Depends(require_user_email),
    db: Session = Depends(get_db),
):
    """Natural-language Q&A over batch preview tables (chat console)."""
    from app.services.extraction.pdf.preview_chat import preview_chat_from_prompt

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    prompt = str(body.get("prompt") or body.get("query") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")

    api_key, _provider = resolve_llm_credentials(request, user_email, db=db)
    if not chat_ready_for_user(db, user_email, api_key, _provider):
        raise HTTPException(
            400,
            "Configure LLM in Settings (cloud API key or on-prem model) before using chat",
        )
    routing = llm_routing_for_user(db, user_email)

    tables_raw = body.get("tables")
    if not isinstance(tables_raw, list):
        raise HTTPException(400, "tables array is required")

    catalog: List[Dict[str, Any]] = []
    for item in tables_raw:
        if not isinstance(item, dict):
            continue
        row = _table_payload(item)
        if row["table_id"]:
            catalog.append(row)

    conversation = body.get("conversation")
    if not isinstance(conversation, list):
        conversation = None

    try:
        with llm_routing_scope(routing):
            return preview_chat_from_prompt(
                prompt=prompt,
                tables=[{"table_id": c["table_id"], **c} for c in catalog],
                api_key=api_key,
                conversation=conversation,
            )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Could not run chat: {e}") from e
