"""Pydantic models for llm_preview catalog + intent actions."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LlmActionType(str, Enum):
    find = "find"
    delete = "delete"
    bulk_find = "bulk_find"
    bulk_delete = "bulk_delete"
    download = "download"
    bulk_download = "bulk_download"
    find_review_needed = "find_review_needed"
    find_ai_review_needed = "find_ai_review_needed"


class PreviewCatalogEntry(BaseModel):
    table_id: str = Field(..., description="Stable extraction table_id")
    name: str = Field(..., description="Short display name / title")
    summary: str = Field(default="", description="One-line table summary")


class LlmPreviewCatalog(BaseModel):
    tables: List[PreviewCatalogEntry] = Field(default_factory=list)


class LlmActionPlan(BaseModel):
    type: LlmActionType
    table_names: List[str] = Field(
        default_factory=list,
        description="table_id values from the catalog (single or many)",
    )
    rationale: str = Field(default="")

    @field_validator("table_names", mode="before")
    @classmethod
    def _coerce_table_names(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            return [s] if s else []
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()]
        return []


class CatalogSummarizeResult(BaseModel):
    """Structured LLM output for catalog summarization."""

    tables: List[PreviewCatalogEntry] = Field(default_factory=list)
