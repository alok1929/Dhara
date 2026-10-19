"""Chat (llm_preview) and guided Preview share one job + Postgres deleted_table_ids."""
from __future__ import annotations

from app.services.ingestion.review_tables import flatten_job_result_to_review_tables
from app.services.preview.catalog_store import (
    get_llm_preview_catalog,
    get_llm_preview_meta,
    set_llm_preview_catalog,
)
from app.services.preview.mutations import soft_delete_tables


def _job():
    return {
        "job_id": "sync_job",
        "user_email": "u@example.com",
        "status": "done",
        "deleted_table_ids": [],
        "reviews": {},
        "result": {
            "1": {
                "tables": [
                    {"table_id": "t1", "title": "Spice A", "page": 1},
                    {"table_id": "t2", "title": "Spice B", "page": 1},
                    {"table_id": "t3", "title": "Rice", "page": 2},
                ]
            }
        },
    }


def test_guided_delete_hides_tables_from_review_list_and_chat_catalog():
    job = _job()
    set_llm_preview_catalog(
        job,
        [
            {"table_id": "t1", "name": "Spice A", "summary": "a"},
            {"table_id": "t2", "name": "Spice B", "summary": "b"},
            {"table_id": "t3", "name": "Rice", "summary": "r"},
        ],
    )

    soft_delete_tables(job, ["t1", "t2"])

    guided_ids = {t["table_id"] for t in flatten_job_result_to_review_tables(job)}
    assert guided_ids == {"t3"}
    assert set(job.get("deleted_table_ids") or []) >= {"t1", "t2"}

    catalog = get_llm_preview_catalog(job)
    assert catalog is not None
    assert {c["table_id"] for c in catalog} == {"t3"}

    meta = get_llm_preview_meta(job)
    assert {c["table_id"] for c in (meta.get("catalog") or [])} == {"t3"}


def test_flatten_excludes_soft_deleted_tables():
    job = _job()
    job["deleted_table_ids"] = ["t2"]
    flat = flatten_job_result_to_review_tables(job)
    assert {t["table_id"] for t in flat} == {"t1", "t3"}
