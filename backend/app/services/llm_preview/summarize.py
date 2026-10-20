"""Catalog stubs for llm_preview_data (heuristic by default; optional LangChain)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.services.llm_prompts import LLM_PREVIEW_SUMMARIZE_PROMPT, OPENAI_MODEL
from app.services.llm_preview.schemas import CatalogSummarizeResult, PreviewCatalogEntry

logger = logging.getLogger(__name__)


def _stub_entry(table: Dict[str, Any]) -> PreviewCatalogEntry:
    tid = str(table.get("table_id") or "")
    title = str(table.get("title") or "").strip()
    banner = str(table.get("banner_table_id") or "").strip()
    # Prefer an existing summary/description; otherwise a light sliver from title.
    summary = str(
        table.get("short_description")
        or table.get("description")
        or table.get("summary")
        or ""
    ).strip()
    name = title or banner or f"Page {table.get('page')} table"
    if not summary and name:
        summary = name[:240]
    return PreviewCatalogEntry(
        table_id=tid,
        name=name[:200] or tid,
        summary=(summary[:240] if summary else ""),
    )


def _table_stub_for_llm(table: Dict[str, Any]) -> Dict[str, Any]:
    entry = _stub_entry(table)
    out: Dict[str, Any] = {
        "table_id": entry.table_id,
        "title": entry.name,
        "page": table.get("page"),
    }
    if entry.summary:
        out["summary"] = entry.summary
    hr = table.get("human_review_needed")
    if hr is not None:
        out["human_review_needed"] = bool(hr)
    return out


def catalog_from_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build ``[{table_id, name, summary}, ...]`` from Preview stubs — no LLM.

    Uses title / banner / short_description already on the table (or client overlay).
    """
    return [
        _stub_entry(t).model_dump()
        for t in tables
        if t.get("table_id") is not None
    ]


def summarize_tables_catalog(
    *,
    tables: List[Dict[str, Any]],
    api_key: str,
) -> List[Dict[str, Any]]:
    """
    Optional LLM enrichment: rewrite stubs into name + summary via LangChain.

    Prefer ``catalog_from_tables`` for the normal POST path; call this only when
    ``force_summarize`` is set.
    """
    if not (api_key or "").strip():
        raise ValueError("An LLM API key is required in Settings")

    stubs = [_stub_entry(t) for t in tables if t.get("table_id") is not None]
    if not stubs:
        return []

    by_id = {e.table_id: e for e in stubs}
    llm_input = [_table_stub_for_llm(t) for t in tables if t.get("table_id") is not None]

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        temperature=0,
        api_key=api_key.strip(),
    )
    structured = llm.with_structured_output(CatalogSummarizeResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You produce structured table catalogs for data stewards."),
            ("human", LLM_PREVIEW_SUMMARIZE_PROMPT),
        ]
    )
    chain = prompt | structured

    try:
        result: CatalogSummarizeResult = chain.invoke(
            {"tables_json": json.dumps(llm_input, ensure_ascii=False)}
        )
    except Exception as e:
        logger.warning("llm_preview summarize failed, using stubs: %s", e)
        return [e.model_dump() for e in stubs]

    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in result.tables or []:
        tid = str(entry.table_id or "").strip()
        if not tid or tid not in by_id or tid in seen:
            continue
        seen.add(tid)
        name = (entry.name or "").strip() or by_id[tid].name
        summary = (entry.summary or "").strip() or by_id[tid].summary
        out.append(
            {
                "table_id": tid,
                "name": name[:200],
                "summary": summary[:240],
            }
        )

    for tid, stub in by_id.items():
        if tid not in seen:
            out.append(stub.model_dump())
            seen.add(tid)

    return out


def build_llm_preview_catalog(
    tables: List[Dict[str, Any]],
    *,
    force_summarize: bool = False,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Default: heuristic stubs. LLM only when ``force_summarize`` is true."""
    if force_summarize:
        return summarize_tables_catalog(tables=tables, api_key=api_key or "")
    return catalog_from_tables(tables)
