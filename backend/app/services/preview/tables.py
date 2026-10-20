"""Review-table helpers: load, overlay client Preview state, id sanitization."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

# Keys used by AI search / llm_preview catalog overlays (titles & summaries).
CATALOG_OVERLAY_KEYS = (
    "title",
    "banner_table_id",
    "short_description",
    "description",
    "summary",
    "page",
    "human_review_needed",
    "human_review_reason",
)

# Keys used when Continuing from Preview (persist-approved).
PERSIST_OVERLAY_KEYS = (
    "title",
    "rows",
    "columns",
    "classification",
    "human_review_needed",
    "human_review_reason",
    "semantic_status",
)


def review_tables_for_job(job: dict) -> list:
    """Flatten job result into the same review-table list as GET /result."""
    from app.workers.extraction_jobs import _pdf_tables_from_job

    return _pdf_tables_from_job(job)


def tables_by_id(tables: Sequence[dict]) -> Dict[str, dict]:
    return {
        str(t.get("table_id")): t
        for t in tables
        if isinstance(t, dict) and t.get("table_id") is not None
    }


def sanitize_table_ids(
    ids_raw: Any,
    valid_ids: Set[str],
) -> List[str]:
    """Dedupe and keep only ids present in ``valid_ids`` (order preserved)."""
    selected: List[str] = []
    if not isinstance(ids_raw, list):
        if isinstance(ids_raw, str) and ids_raw.strip():
            ids_raw = [ids_raw]
        else:
            return selected
    seen: Set[str] = set()
    for tid in ids_raw:
        sid = str(tid or "").strip()
        if not sid or sid not in valid_ids or sid in seen:
            continue
        seen.add(sid)
        selected.append(sid)
    return selected


def _client_by_id(client_tables: Any) -> Dict[str, dict]:
    if not isinstance(client_tables, list) or not client_tables:
        return {}
    return {
        str(t.get("table_id")): t
        for t in client_tables
        if isinstance(t, dict) and t.get("table_id")
    }


def overlay_client_tables(
    tables: List[dict],
    client_tables: Any,
    *,
    keys: Sequence[str] = CATALOG_OVERLAY_KEYS,
) -> List[dict]:
    """Mutate ``tables`` in place with matching client fields; return same list."""
    by_id = _client_by_id(client_tables)
    if not by_id:
        return tables
    for t in tables:
        override = by_id.get(str(t.get("table_id") or ""))
        if not override:
            continue
        for key in keys:
            if key in override:
                t[key] = override.get(key)
    return tables


def apply_overlay_to_job_reviews(
    job: dict,
    client_tables: Any,
    *,
    keys: Sequence[str] = PERSIST_OVERLAY_KEYS,
    tables: Optional[List[dict]] = None,
) -> List[dict]:
    """
    Merge client Preview overlays onto in-memory tables and ``job["reviews"]``.

    Does not persist — caller must ``_save_pdf_job(job)`` when desired.
    Returns the (possibly newly loaded) tables list after overlay.
    """
    if tables is None:
        tables = review_tables_for_job(job)
    by_id = _client_by_id(client_tables)
    if not by_id:
        return tables

    reviews = dict(job.get("reviews") or {})
    for t in tables:
        tid = str(t.get("table_id") or "")
        override = by_id.get(tid)
        if not override:
            continue
        patch = {k: override[k] for k in keys if k in override}
        if not patch:
            continue
        t.update(patch)
        reviews[tid] = {**reviews.get(tid, {}), **patch}
    job["reviews"] = reviews
    return tables


def subset_tables_by_ids(
    tables: Sequence[dict],
    table_ids: Iterable[str],
) -> Dict[str, dict]:
    """Return ``{table_id: table}`` for requested ids that exist in ``tables``."""
    by_id = tables_by_id(tables)
    out: Dict[str, dict] = {}
    for tid in table_ids:
        sid = str(tid)
        if sid in by_id:
            out[sid] = by_id[sid]
    return out
