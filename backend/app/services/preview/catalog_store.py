"""Persist llm_preview catalog + chat turns on the extraction job reviews."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

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


def get_llm_preview_catalog(job: dict) -> Optional[List[dict]]:
    bucket = _bucket(job)
    catalog = bucket.get("catalog")
    if not isinstance(catalog, list):
        return None
    return catalog


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
    catalog = bucket.get("catalog") if isinstance(bucket.get("catalog"), list) else None
    return {
        "catalog": catalog,
        "updated_at": bucket.get("updated_at"),
        "source_table_count": bucket.get("source_table_count"),
        "last_turns": get_llm_turns(job),
        # llm_preview is the Preview stage (not Grouping=3).
        "pipeline_step": preview_pipeline_step(job),
    }
