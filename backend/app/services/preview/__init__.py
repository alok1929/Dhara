"""Unified Preview / guided-mode job helpers shared by PDF and llm_preview routes."""

from app.services.preview.access import (
    PREVIEW_PIPELINE_STEP,
    PreviewJobError,
    effective_pipeline_step,
    ensure_preview_pipeline_step,
    job_owned_by_email,
    job_visible_to,
    preview_pipeline_step,
    require_finished_job,
)
from app.services.preview.catalog_store import (
    append_llm_turn,
    get_llm_preview_catalog,
    get_llm_preview_meta,
    get_llm_turns,
    set_llm_preview_catalog,
)
from app.services.preview.export import (
    table_xlsx_bytes_and_filename,
    tables_to_download_files_base64,
    tables_to_zip_bytes,
)
from app.services.preview.mutations import soft_delete_tables
from app.services.preview.tables import (
    CATALOG_OVERLAY_KEYS,
    PERSIST_OVERLAY_KEYS,
    apply_overlay_to_job_reviews,
    overlay_client_tables,
    review_tables_for_job,
    sanitize_table_ids,
    subset_tables_by_ids,
    tables_by_id,
)

__all__ = [
    "PREVIEW_PIPELINE_STEP",
    "PreviewJobError",
    "effective_pipeline_step",
    "ensure_preview_pipeline_step",
    "job_owned_by_email",
    "job_visible_to",
    "preview_pipeline_step",
    "require_finished_job",
    "append_llm_turn",
    "get_llm_preview_catalog",
    "get_llm_preview_meta",
    "get_llm_turns",
    "set_llm_preview_catalog",
    "table_xlsx_bytes_and_filename",
    "tables_to_download_files_base64",
    "tables_to_zip_bytes",
    "soft_delete_tables",
    "CATALOG_OVERLAY_KEYS",
    "PERSIST_OVERLAY_KEYS",
    "apply_overlay_to_job_reviews",
    "overlay_client_tables",
    "review_tables_for_job",
    "sanitize_table_ids",
    "subset_tables_by_ids",
    "tables_by_id",
]
