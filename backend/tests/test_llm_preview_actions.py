"""Unit tests for llm_preview action dispatch (no live LLM)."""
from __future__ import annotations

from app.services.llm_preview.actions import execute_action_plan
from app.services.llm_preview.schemas import LlmActionPlan, LlmActionType
from app.services.llm_preview.summarize import build_llm_preview_catalog, catalog_from_tables


def _tables():
    return [
        {
            "table_id": "t1",
            "title": "Births",
            "human_review_needed": True,
            "human_review_reason": "uncertain_title",
            "columns": [{"name": "Age"}],
            "rows": [["0-1"]],
        },
        {
            "table_id": "t2",
            "title": "Deaths",
            "human_review_needed": False,
            "title_repaired_by_llm": True,
            "columns": [{"name": "Sex"}],
            "rows": [["M"]],
        },
        {
            "table_id": "t3",
            "title": "Clean",
            "human_review_needed": False,
            "columns": [{"name": "Year"}],
            "rows": [[2020]],
        },
    ]


def test_find_returns_subset_table_data():
    plan = LlmActionPlan(
        type=LlmActionType.find,
        table_names=["t1", "missing", "t3"],
        rationale="matched",
    )
    out = execute_action_plan(plan, _tables())
    assert out["type"] == "find"
    assert out["table_names"] == ["t1", "t3"]
    assert set(out["table_data"].keys()) == {"t1", "t3"}
    assert out["executed"] is False
    assert "files" not in out


def test_delete_does_not_execute():
    plan = LlmActionPlan(
        type=LlmActionType.bulk_delete,
        table_names=["t2"],
        rationale="remove deaths",
    )
    out = execute_action_plan(plan, _tables())
    assert out["type"] == "bulk_delete"
    assert out["executed"] is False
    assert "t2" in out["table_data"]


def test_find_review_needed_filters_scope():
    plan = LlmActionPlan(
        type=LlmActionType.find_review_needed,
        table_names=[],
        rationale="review",
    )
    out = execute_action_plan(plan, _tables())
    assert out["table_names"] == ["t1"]
    assert set(out["table_data"].keys()) == {"t1"}


def test_find_ai_review_needed_includes_repaired_and_uncertain():
    plan = LlmActionPlan(
        type=LlmActionType.find_ai_review_needed,
        table_names=[],
        rationale="ai",
    )
    out = execute_action_plan(plan, _tables())
    assert set(out["table_names"]) == {"t1", "t2"}


def test_download_includes_base64_files():
    plan = LlmActionPlan(
        type=LlmActionType.download,
        table_names=["t3"],
        rationale="dl",
    )
    out = execute_action_plan(plan, _tables())
    assert "files" in out
    assert len(out["files"]) == 1
    f0 = out["files"][0]
    assert f0["table_id"] == "t3"
    assert f0["filename"].endswith(".xlsx")
    assert f0["content_base64"]
    assert "spreadsheetml" in f0["media_type"]


def test_action_plan_coerces_single_table_name_string():
    plan = LlmActionPlan(type=LlmActionType.find, table_names="t1")  # type: ignore[arg-type]
    assert plan.table_names == ["t1"]


def test_catalog_from_tables_uses_stubs_without_llm():
    tables = [
        {
            "table_id": "t1",
            "title": "Births by Age",
            "short_description": "Age x sex counts",
            "page": 3,
            "rows": [["should", "not", "appear"]],
            "columns": [{"name": "Age"}],
        },
        {"table_id": "t2", "title": "Deaths", "page": 4},
    ]
    catalog = catalog_from_tables(tables)
    assert catalog == [
        {"table_id": "t1", "name": "Births by Age", "summary": "Age x sex counts"},
        {"table_id": "t2", "name": "Deaths", "summary": "Deaths"},
    ]
    # Default builder must not call LangChain
    assert build_llm_preview_catalog(tables, force_summarize=False) == catalog
