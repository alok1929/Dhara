"""Same job_id continuity: chat overlays / catalog / deletes share one working job."""
from __future__ import annotations

from app.services.preview.catalog_store import (
    append_llm_turn,
    get_llm_preview_catalog,
    get_llm_turns,
    set_llm_preview_catalog,
)
from app.services.preview.mutations import soft_delete_tables
from app.services.preview.tables import apply_overlay_to_job_reviews, overlay_client_tables


def _job_with_tables():
    """Minimal in-memory job shaped like extraction working state."""
    return {
        "job_id": "abc123",
        "user_email": "steward@example.com",
        "status": "done",
        "pipeline_step": 2,
        "reviews": {},
        "deleted_table_ids": [],
        "result": {
            "1": {
                "tables": [
                    {
                        "table_id": "t1",
                        "title": "Births by Age",
                        "page": 1,
                        "columns": [{"name": "Age"}],
                        "rows": [["0-1"]],
                    },
                    {
                        "table_id": "t2",
                        "title": "Deaths",
                        "page": 2,
                        "columns": [{"name": "Sex"}],
                        "rows": [["F"]],
                    },
                ]
            }
        },
    }


def test_chat_persist_reviews_visible_on_same_job():
    job = _job_with_tables()
    # Chat mode: steward renames a table via overlay + persist_reviews.
    tables = [
        dict(t)
        for page in job["result"].values()
        for t in (page.get("tables") or [])
    ]
    apply_overlay_to_job_reviews(
        job,
        [{"table_id": "t1", "title": "Births (edited in chat)"}],
        tables=tables,
    )
    assert job["reviews"]["t1"]["title"] == "Births (edited in chat)"

    # Guided mode would merge reviews on read — same job dict.
    guided = {**tables[0], **job["reviews"].get("t1", {})}
    assert guided["title"] == "Births (edited in chat)"


def test_catalog_and_turns_stay_on_job_after_delete():
    job = _job_with_tables()
    set_llm_preview_catalog(
        job,
        [
            {"table_id": "t1", "name": "Births", "summary": "age"},
            {"table_id": "t2", "name": "Deaths", "summary": "sex"},
        ],
    )
    append_llm_turn(
        job,
        {"user_request": "delete deaths", "type": "bulk_delete", "table_names": ["t2"]},
    )

    # Confirmed delete (guided or chat confirm) mutates same job.
    soft_delete_tables(job, ["t2"])
    assert "t2" in job["deleted_table_ids"]
    # Catalog + chat tail remain on the job for handoff / refresh.
    assert get_llm_preview_catalog(job) is not None
    assert len(get_llm_turns(job)) == 1
    assert "__llm_preview" in job["reviews"]


def test_overlay_without_persist_does_not_write_reviews():
    job = _job_with_tables()
    tables = [
        {"table_id": "t1", "title": "Births by Age"},
        {"table_id": "t2", "title": "Deaths"},
    ]
    overlay_client_tables(tables, [{"table_id": "t1", "title": "Ephemeral"}])
    assert tables[0]["title"] == "Ephemeral"
    assert job["reviews"] == {} or "t1" not in job.get("reviews", {})
