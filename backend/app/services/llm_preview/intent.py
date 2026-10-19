"""LangChain intent classification for llm_input."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.services.llm_prompts import (
    LLM_GROUPING_INTENT_EXTRA,
    LLM_PREVIEW_INTENT_HUMAN_PROMPT,
    LLM_PREVIEW_INTENT_SYSTEM_PROMPT,
    OPENAI_MODEL,
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
) -> LlmActionPlan:
    """Ask the LLM for an action plan; sanitize table_names against catalog ids."""
    text = (user_request or "").strip()
    if not text:
        raise ValueError("user_request is required")
    if not (api_key or "").strip():
        raise ValueError("An LLM API key is required in Settings")

    valid_ids = {
        str(c.get("table_id") or "").strip()
        for c in catalog
        if isinstance(c, dict) and c.get("table_id")
    }
    if not valid_ids:
        return LlmActionPlan(
            type=LlmActionType.find,
            table_names=[],
            rationale="No tables are available.",
        )

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=0,
        api_key=api_key.strip(),
    )
    compact_catalog = [
        {
            "table_id": str(c.get("table_id") or "").strip(),
            "name": str(c.get("name") or ""),
            "summary": str(c.get("summary") or "")[:240],
        }
        for c in catalog
        if isinstance(c, dict) and c.get("table_id")
    ]

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
            }
        )
    except Exception as e:
        logger.warning("llm_preview intent failed: %s", e)
        raise ValueError(f"Could not interpret request: {e}") from e

    if not isinstance(plan, LlmActionPlan):
        plan = LlmActionPlan.model_validate(plan)

    plan.table_names = sanitize_table_ids(plan.table_names, valid_ids)
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
        if plan.table_names:
            plan.rationale = f"Matched {len(plan.table_names)} table(s)."
        else:
            plan.rationale = "No matching tables."
    return plan
