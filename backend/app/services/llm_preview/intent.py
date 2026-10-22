"""LangChain intent classification for llm_input."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_prompts import (
    LLM_GROUPING_INTENT_EXTRA,
    LLM_PREVIEW_INTENT_HUMAN_PROMPT,
    LLM_PREVIEW_INTENT_SYSTEM_PROMPT,
)
from app.services.llm_preview.schemas import LlmActionPlan, LlmActionType
from app.services.preview.tables import sanitize_table_ids

logger = logging.getLogger(__name__)

_BULK_FIND_MIN = 3


def normalize_action_plan(plan: LlmActionPlan) -> LlmActionPlan:
    """Align LLM output with notebook heuristics (e.g. promote find → bulk_find)."""
    if plan.type == LlmActionType.find and len(plan.table_names) >= _BULK_FIND_MIN:
        plan.type = LlmActionType.bulk_find
    if plan.type == LlmActionType.download and len(plan.table_names) >= _BULK_FIND_MIN:
        plan.type = LlmActionType.bulk_download
    if plan.type == LlmActionType.delete and len(plan.table_names) >= _BULK_FIND_MIN:
        plan.type = LlmActionType.bulk_delete
    if plan.type == LlmActionType.propose_group and len(plan.table_names) >= _BULK_FIND_MIN:
        plan.type = LlmActionType.bulk_propose_group
    return plan


def plan_from_user_request(
    *,
    user_request: str,
    catalog: List[Dict[str, Any]],
    api_key: str,
    prompt: Optional[str] = None,
    stage: str = "preview",
    groups: Optional[List[Dict[str, Any]]] = None,
) -> LlmActionPlan:
    """Ask the LLM for an action plan; sanitize table_names against catalog ids."""
    text = (user_request or "").strip()
    if not text:
        raise ValueError("user_request is required")
    from app.services.llm.factory import live_openai_chat

    llm_client = live_openai_chat(api_key)
    if llm_client is None:
        raise ValueError("An LLM API key is required in Settings")

    valid_ids = {
        str(c.get("table_id") or "").strip()
        for c in catalog
        if isinstance(c, dict) and c.get("table_id")
    }
    if not valid_ids and (stage or "").strip().lower() != "grouping":
        return LlmActionPlan(
            type=LlmActionType.find,
            table_names=[],
            rationale="No tables are available.",
        )

    llm = llm_client.langchain_chat(temperature=0)
    compact_catalog = [
        {
            "table_id": str(c.get("table_id") or "").strip(),
            "name": str(c.get("name") or ""),
            "summary": str(c.get("summary") or "")[:240],
        }
        for c in catalog
        if isinstance(c, dict) and c.get("table_id")
    ]
    groups_payload = groups if isinstance(groups, list) else []

    system = LLM_PREVIEW_INTENT_SYSTEM_PROMPT
    if (stage or "").strip().lower() == "grouping":
        system = system + LLM_GROUPING_INTENT_EXTRA

    structured = llm.with_structured_output(LlmActionPlan)
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", LLM_PREVIEW_INTENT_HUMAN_PROMPT),
        ]
    )
    chain = chat_prompt | structured

    try:
        plan: LlmActionPlan = chain.invoke(
            {
                "prompt": (prompt or "").strip() or "(none)",
                "user_request": text,
                "catalog_json": json.dumps(compact_catalog, ensure_ascii=False),
                "groups_json": json.dumps(groups_payload, ensure_ascii=False) or "[]",
            }
        )
    except Exception as e:
        logger.warning("llm_preview intent failed: %s", e)
        raise ValueError(f"Could not interpret request: {e}") from e

    if not isinstance(plan, LlmActionPlan):
        plan = LlmActionPlan.model_validate(plan)

    # For merge_groups, fill table_names from the Groups list when the model omitted them.
    if plan.type == LlmActionType.merge_groups and groups_payload:
        by_num = {
            int(g.get("group_number")): g
            for g in groups_payload
            if isinstance(g, dict) and g.get("group_number") is not None
        }
        indices = [int(i) for i in (plan.group_indices or []) if int(i) >= 1]
        if len(indices) >= 2:
            collected: List[str] = []
            for num in indices:
                entry = by_num.get(num) or {}
                for tid in entry.get("table_ids") or []:
                    sid = str(tid or "").strip()
                    if sid and sid not in collected:
                        collected.append(sid)
            if collected:
                plan.table_names = collected
            if not (plan.group_name or "").strip():
                names = [
                    str((by_num.get(n) or {}).get("name") or f"Group {n}")
                    for n in indices
                    if n in by_num
                ]
                plan.group_name = " + ".join(names)[:120] if names else ""

    plan.table_names = sanitize_table_ids(plan.table_names, valid_ids) if valid_ids else list(plan.table_names or [])
    plan = normalize_action_plan(plan)
    if not (plan.group_name or "").strip() and plan.type in (
        LlmActionType.propose_group,
        LlmActionType.bulk_propose_group,
    ):
        if plan.table_names:
            first = compact_catalog[0] if compact_catalog else {}
            for entry in compact_catalog:
                if entry.get("table_id") in plan.table_names:
                    first = entry
                    break
            plan.group_name = str(first.get("name") or "Proposed group")[:120]
    if not (plan.rationale or "").strip():
        if plan.type == LlmActionType.merge_groups and plan.group_indices:
            plan.rationale = (
                f"Merge groups {', '.join(str(i) for i in plan.group_indices)}."
            )
        elif plan.table_names:
            plan.rationale = f"Matched {len(plan.table_names)} table(s)."
        else:
            plan.rationale = "No matching tables."
    return plan
