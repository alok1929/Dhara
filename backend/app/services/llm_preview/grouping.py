"""Grouping-stage chat: propose bundles and apply to Postgres (same job as guided UI)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.db.repositories import pdf_jobs as pdf_store


def ensure_persisted_tables(
    session: Session,
    *,
    job_id: str,
    user_email: str,
    filename: Optional[str],
    tables: List[dict],
) -> List[dict]:
    """Mirror Preview → Grouping handoff: persist working tables when not in DB yet."""
    active = pdf_store.list_active_tables(session, job_id)
    if active:
        return active
    if not tables:
        return []
    return pdf_store.persist_approved_tables(
        session,
        job_id=job_id,
        user_email=user_email,
        filename=filename,
        tables=tables,
    )


def sync_soft_deletes_to_postgres(
    session: Session,
    job_id: str,
    table_ids: Sequence[str],
) -> int:
    """Align ``pdf_tables.deleted_at`` with job ``deleted_table_ids`` (grouping step)."""
    from datetime import datetime, timezone

    from sqlalchemy import update

    from app.db.models.pdf import PdfTable

    ids = [str(t).strip() for t in table_ids if t is not None and str(t).strip()]
    if not ids:
        return 0
    now = datetime.now(timezone.utc)
    result = session.execute(
        update(PdfTable)
        .where(
            PdfTable.job_id == job_id,
            PdfTable.table_id.in_(ids),
            PdfTable.deleted_at.is_(None),
        )
        .values(deleted_at=now, updated_at=now)
    )
    session.flush()
    return int(result.rowcount or 0)


def merge_proposed_group(
    session: Session,
    job_id: str,
    *,
    group_name: str,
    table_ids: Sequence[str],
) -> Dict[str, Any]:
    """
    Add tables to a named group (or create one). Removes members from other groups first.
    Uses Postgres UUID ``table_pks`` — same as PUT /api/pdf/jobs/{id}/grouping.
    """
    name = (group_name or "").strip() or "Untitled group"
    tables = pdf_store.list_active_tables(session, job_id)
    by_table_id = {str(t.get("table_id") or ""): t for t in tables if t.get("table_id")}
    target_pks = {
        str(by_table_id[tid]["id"])
        for tid in table_ids
        if tid in by_table_id and by_table_id[tid].get("id")
    }
    if not target_pks:
        return pdf_store.load_grouping(session, job_id)

    current = pdf_store.load_grouping(session, job_id)
    normalized: List[dict] = []
    for g in current.get("groups") or []:
        pks = [
            str(m.get("id"))
            for m in (g.get("tables") or [])
            if m.get("id") and str(m.get("id")) not in target_pks
        ]
        if pks:
            normalized.append({"name": g.get("name") or "Untitled group", "table_pks": pks})

    merged = False
    key = name.casefold()
    for g in normalized:
        if (g.get("name") or "").strip().casefold() == key:
            g["table_pks"] = sorted(set(g.get("table_pks") or []) | target_pks)
            merged = True
            break
    if not merged:
        normalized.append({"name": name, "table_pks": sorted(target_pks)})

    pdf_store.save_grouping(session, job_id=job_id, groups=normalized)
    return pdf_store.load_grouping(session, job_id)


def grouping_catalog_from_tables(tables: List[dict]) -> List[dict]:
    """Catalog entries for grouping chat (same shape as Preview catalog)."""
    from app.services.llm_preview.summarize import catalog_from_tables

    return catalog_from_tables(tables)


def groups_for_intent(grouping: Optional[Dict[str, Any]]) -> List[dict]:
    """Compact group list for the LLM (1-based group_number as shown in UI)."""
    out: List[dict] = []
    for i, g in enumerate((grouping or {}).get("groups") or [], start=1):
        if not isinstance(g, dict):
            continue
        tables = g.get("tables") or []
        table_ids = [
            str(t.get("table_id") or "").strip()
            for t in tables
            if isinstance(t, dict) and t.get("table_id")
        ]
        out.append(
            {
                "group_number": i,
                "name": str(g.get("name") or f"Group {i}").strip() or f"Group {i}",
                "table_ids": table_ids,
                "table_count": len(table_ids),
            }
        )
    return out


def merge_groups_by_indices(
    session: Session,
    job_id: str,
    *,
    group_indices: Sequence[int],
    group_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge existing groups by 1-based UI numbers into the earliest group.
    Persists via ``save_grouping`` (same path as guided Grouping).
    """
    current = pdf_store.load_grouping(session, job_id)
    groups = list(current.get("groups") or [])
    if len(groups) < 2:
        return current

    unique = sorted(
        {
            int(i)
            for i in group_indices
            if i is not None and int(i) >= 1 and int(i) <= len(groups)
        }
    )
    if len(unique) < 2:
        return current

    zero_based = [n - 1 for n in unique]
    target = zero_based[0]
    sources = set(zero_based[1:])

    names = [
        str(groups[i].get("name") or f"Group {i + 1}").strip() or f"Group {i + 1}"
        for i in zero_based
    ]
    merged_name = (group_name or "").strip() or " + ".join(names)

    target_pks: List[str] = []
    for i, g in enumerate(groups):
        pks = [
            str(m.get("id"))
            for m in (g.get("tables") or [])
            if isinstance(m, dict) and m.get("id")
        ]
        if i == target or i in sources:
            for pk in pks:
                if pk not in target_pks:
                    target_pks.append(pk)

    normalized: List[dict] = []
    for i, g in enumerate(groups):
        if i in sources:
            continue
        if i == target:
            normalized.append({"name": merged_name, "table_pks": target_pks})
            continue
        pks = [
            str(m.get("id"))
            for m in (g.get("tables") or [])
            if isinstance(m, dict) and m.get("id")
        ]
        if pks:
            normalized.append(
                {"name": g.get("name") or "Untitled group", "table_pks": pks}
            )

    pdf_store.save_grouping(session, job_id=job_id, groups=normalized)
    return pdf_store.load_grouping(session, job_id)
