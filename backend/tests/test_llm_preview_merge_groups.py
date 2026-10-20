"""Unit tests for grouping merge helpers (no live DB / LLM)."""
from app.services.llm_preview.grouping import groups_for_intent
from app.services.llm_preview.schemas import LlmActionPlan, LlmActionType


def test_groups_for_intent_numbers_are_one_based():
    grouping = {
        "groups": [
            {
                "name": "Alpha",
                "tables": [{"id": "pk1", "table_id": "T1"}, {"id": "pk2", "table_id": "T2"}],
            },
            {"name": "Beta", "tables": [{"id": "pk3", "table_id": "T3"}]},
        ]
    }
    rows = groups_for_intent(grouping)
    assert [r["group_number"] for r in rows] == [1, 2]
    assert rows[0]["table_ids"] == ["T1", "T2"]
    assert rows[1]["name"] == "Beta"


def test_merge_groups_action_plan_accepts_group_indices():
    plan = LlmActionPlan(
        type=LlmActionType.merge_groups,
        table_names=["T1", "T2"],
        group_indices=[6, 7],
        group_name="Merged",
        rationale="Merge group 6 and 7",
    )
    assert plan.type == LlmActionType.merge_groups
    assert plan.group_indices == [6, 7]
