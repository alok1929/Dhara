"""Persist llm_preview catalog + chat turns on the extraction job reviews."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Set

LLM_PREVIEW_KEY = "__llm_preview"
MAX_LAST_TURNS = 20


def _bucket(job: dict) -> dict:
    reviews = job.setdefault("reviews", {})
    if not isinstance(reviews, dict):
        reviews = {}
        job["reviews"] = reviews
    bucket = reviews.get(LLM_PREVIEW_KEY)
    if not isinstance(bucket, dict):
        bucket = {}
        reviews[LLM_PREVIEW_KEY] = bucket
    return bucket


def deleted_table_ids_set(job: dict) -> Set[str]:
    raw = job.get("deleted_table_ids") or []
    if not isinstance(raw, list):
        return set()
    return {str(x).strip() for x in raw if x is not None and str(x).strip()}


def filter_catalog_entries(
    catalog: List[dict],
    deleted: Set[str],
) -> List[dict]:
    """Drop soft-deleted tables so chat and guided Preview stay aligned."""
    if not deleted:
        return catalog
    out: List[dict] = []
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("table_id") or "").strip()
        if tid and tid in deleted:
            continue
        out.append(entry)
    return out


def get_llm_preview_catalog(job: dict) -> Optional[List[dict]]:
    bucket = _bucket(job)
    catalog = bucket.get("catalog")
    if not isinstance(catalog, list):
        return None
    return filter_catalog_entries(catalog, deleted_table_ids_set(job))


def prune_llm_preview_catalog(job: dict, table_ids: Sequence[str]) -> None:
    """Remove deleted ids from the stored chat catalog (same job as guided Preview)."""
    remove = {str(tid).strip() for tid in table_ids if tid is not None and str(tid).strip()}
    if not remove:
        return
    bucket = _bucket(job)
    catalog = bucket.get("catalog")
    if not isinstance(catalog, list) or not catalog:
        return
    bucket["catalog"] = filter_catalog_entries(catalog, remove)
    bucket["updated_at"] = time.time()
    bucket["source_table_count"] = len(bucket["catalog"])


def set_llm_preview_catalog(
    job: dict,
    catalog: List[dict],
    *,
    source_table_count: Optional[int] = None,
) -> dict:
    bucket = _bucket(job)
    bucket["catalog"] = catalog
    bucket["updated_at"] = time.time()
    if source_table_count is not None:
        bucket["source_table_count"] = int(source_table_count)
    else:
        bucket["source_table_count"] = len(catalog)
    return bucket


def get_llm_turns(job: dict) -> List[dict]:
    bucket = _bucket(job)
    turns = bucket.get("last_turns")
    if not isinstance(turns, list):
        return []
    return [t for t in turns if isinstance(t, dict)]


def append_llm_turn(job: dict, turn: Dict[str, Any]) -> List[dict]:
    bucket = _bucket(job)
    turns = bucket.get("last_turns")
    if not isinstance(turns, list):
        turns = []
    entry = dict(turn)
    entry.setdefault("at", time.time())
    turns.append(entry)
    if len(turns) > MAX_LAST_TURNS:
        turns = turns[-MAX_LAST_TURNS:]
    bucket["last_turns"] = turns
    return turns


def get_llm_preview_meta(job: dict) -> dict:
    """Public slice of __llm_preview for GET responses."""
    from app.services.preview.access import preview_pipeline_step

    bucket = _bucket(job)
    raw = bucket.get("catalog") if isinstance(bucket.get("catalog"), list) else None
    catalog = (
        filter_catalog_entries(raw, deleted_table_ids_set(job)) if raw is not None else None
    )
    return {
        "catalog": catalog,
        "updated_at": bucket.get("updated_at"),
        "source_table_count": bucket.get("source_table_count"),
        "last_turns": get_llm_turns(job),
        # llm_preview is the Preview stage (not Grouping=3).
        "pipeline_step": preview_pipeline_step(job),
    }
