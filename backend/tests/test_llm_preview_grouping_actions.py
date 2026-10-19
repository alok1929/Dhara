"""Grouping-stage chat actions (no live LLM / DB)."""
from __future__ import annotations

from app.services.llm_preview.actions import execute_action_plan
from app.services.llm_preview.intent import normalize_action_plan
from app.services.llm_preview.schemas import LlmActionPlan, LlmActionType


def test_propose_group_preview_not_executed():
    plan = LlmActionPlan(
        type=LlmActionType.bulk_propose_group,
        table_names=["a", "b", "c"],
        group_name="Spice crops",
        rationale="topic",
    )
    tables = [
        {"table_id": "a", "title": "Spice A"},
        {"table_id": "b", "title": "Spice B"},
        {"table_id": "c", "title": "Spice C"},
    ]
    out = execute_action_plan(plan, tables)
    assert out["type"] == "bulk_propose_group"
    assert out["executed"] is False
    assert out["group_name"] == "Spice crops"
    assert out["message"]
    assert set(out["table_ids"]) == {"a", "b", "c"}


def test_normalize_promotes_propose_group_to_bulk():
    plan = LlmActionPlan(
        type=LlmActionType.propose_group,
        table_names=["a", "b", "c"],
        rationale="g",
    )
    out = normalize_action_plan(plan)
    assert out.type == LlmActionType.bulk_propose_group
