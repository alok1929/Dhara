"""Unit tests for the unified preview service (no LLM / network)."""
from __future__ import annotations

from app.services.preview.catalog_store import (
    append_llm_turn,
    get_llm_preview_catalog,
    get_llm_preview_meta,
    get_llm_turns,
    set_llm_preview_catalog,
)
from app.services.preview.mutations import soft_delete_tables
from app.services.preview.tables import (
    apply_overlay_to_job_reviews,
    overlay_client_tables,
    sanitize_table_ids,
    subset_tables_by_ids,
)


def test_sanitize_table_ids_dedupes_and_filters():
    valid = {"a", "b", "c"}
    assert sanitize_table_ids(["a", "x", "a", "b", ""], valid) == ["a", "b"]
    assert sanitize_table_ids("c", valid) == ["c"]
    assert sanitize_table_ids(None, valid) == []


def test_overlay_client_tables_mutates_titles():
    tables = [
        {"table_id": "1", "title": "Old", "summary": "s"},
        {"table_id": "2", "title": "Keep"},
    ]
    overlay_client_tables(
        tables,
        [{"table_id": "1", "title": "New", "short_description": "desc"}],
    )
    assert tables[0]["title"] == "New"
    assert tables[0]["short_description"] == "desc"
    assert tables[1]["title"] == "Keep"


def test_apply_overlay_to_job_reviews_persists_in_memory():
    job = {
        "job_id": "j1",
        "reviews": {},
        "deleted_table_ids": [],
        "result": {},
    }
    tables = [
        {"table_id": "t1", "title": "A", "rows": [[1]]},
        {"table_id": "t2", "title": "B"},
    ]
    apply_overlay_to_job_reviews(
        job,
        [{"table_id": "t1", "title": "A-edited", "rows": [[9]]}],
        tables=tables,
    )
    assert tables[0]["title"] == "A-edited"
    assert tables[0]["rows"] == [[9]]
    assert job["reviews"]["t1"]["title"] == "A-edited"
    assert "t2" not in job["reviews"]


def test_soft_delete_tables_updates_deleted_and_clears_reviews():
    saved = []
    job = {
        "deleted_table_ids": ["old"],
        "reviews": {"a": {"title": "x"}, "b": {"title": "y"}, "__llm_preview": {}},
    }
    result = soft_delete_tables(job, ["a", "b"], save=saved.append)
    assert result["deleted_count"] == 2
    assert job["deleted_table_ids"] == ["a", "b", "old"]
    assert "a" not in job["reviews"]
    assert "b" not in job["reviews"]
    assert "__llm_preview" in job["reviews"]
    assert saved == [job]


def test_catalog_store_roundtrip_and_turns():
    job = {"reviews": {}, "pipeline_step": 2}
    set_llm_preview_catalog(
        job,
        [{"table_id": "1", "name": "N", "summary": "S"}],
        source_table_count=1,
    )
    assert get_llm_preview_catalog(job) == [
        {"table_id": "1", "name": "N", "summary": "S"}
    ]
    append_llm_turn(job, {"user_request": "find births", "type": "find", "table_names": ["1"]})
    turns = get_llm_turns(job)
    assert len(turns) == 1
    assert turns[0]["user_request"] == "find births"
    assert "at" in turns[0]
    meta = get_llm_preview_meta(job)
    assert meta["pipeline_step"] == 2
    assert meta["source_table_count"] == 1
    assert len(meta["last_turns"]) == 1


def test_pipeline_step_defaults_to_preview_when_unset():
    from app.services.preview.access import (
        PREVIEW_PIPELINE_STEP,
        effective_pipeline_step,
        ensure_preview_pipeline_step,
        preview_pipeline_step,
    )

    assert PREVIEW_PIPELINE_STEP == 2  # Preview (3 would be Grouping)

    job = {"status": "done", "reviews": {}, "grouping_status": "proposed"}
    assert preview_pipeline_step(job) == 2
    assert ensure_preview_pipeline_step(job) == 2
    assert job["pipeline_step"] == 2

    # Catalog meta always reports Preview, even if job later advanced.
    job["pipeline_step"] = 5
    meta = get_llm_preview_meta(job)
    assert meta["pipeline_step"] == 2

    assert effective_pipeline_step({"status": "running"}) == 1
    assert effective_pipeline_step({"status": "done", "pipeline_step": 5}) == 5


def test_subset_tables_by_ids():
    tables = [{"table_id": "1", "title": "A"}, {"table_id": "2", "title": "B"}]
    out = subset_tables_by_ids(tables, ["2", "9"])
    assert list(out.keys()) == ["2"]
    assert out["2"]["title"] == "B"
