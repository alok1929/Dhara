"""Preview job mutations (soft-delete tables)."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence


def soft_delete_tables(
    job: dict,
    table_ids: Sequence[str],
    *,
    save: Optional[Callable[[dict], None]] = None,
) -> Dict[str, Any]:
    """
    Soft-delete tables by recording ids in ``deleted_table_ids`` and clearing
    matching review patches. Does not reshuffle result payload.

    If ``save`` is provided, it is called with the mutated job (e.g. ``_save_pdf_job``).
    """
    ids = [str(tid) for tid in table_ids if tid is not None and str(tid).strip()]
    if not ids:
        return {"ok": True, "deleted": [], "deleted_count": 0}

    deleted = set(job.get("deleted_table_ids") or [])
    deleted.update(ids)
    job["deleted_table_ids"] = sorted(deleted)
    reviews = job.get("reviews") or {}
    for tid in ids:
        reviews.pop(tid, None)
    job["reviews"] = reviews

    from app.services.preview.catalog_store import prune_llm_preview_catalog

    prune_llm_preview_catalog(job, ids)

    if save is not None:
        save(job)

    return {"ok": True, "deleted": ids, "deleted_count": len(ids)}
