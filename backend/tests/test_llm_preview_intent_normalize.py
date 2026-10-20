"""Intent normalization heuristics (no live LLM)."""
from __future__ import annotations

from app.services.llm_preview.intent import normalize_action_plan
from app.services.llm_preview.schemas import LlmActionPlan, LlmActionType


def test_find_promoted_to_bulk_find_at_three_ids():
    plan = LlmActionPlan(
        type=LlmActionType.find,
        table_names=["a", "b", "c"],
        rationale="topic",
    )
    out = normalize_action_plan(plan)
    assert out.type == LlmActionType.bulk_find


def test_download_promoted_to_bulk_download():
    plan = LlmActionPlan(
        type=LlmActionType.download,
        table_names=["a", "b", "c"],
        rationale="dl",
    )
    out = normalize_action_plan(plan)
    assert out.type == LlmActionType.bulk_download
