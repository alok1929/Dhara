"""Dispatch llm_preview action plans over live review tables."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from app.services.llm_preview.schemas import LlmActionPlan, LlmActionType
from app.services.preview.export import tables_to_download_files_base64
from app.services.preview.tables import sanitize_table_ids, tables_by_id

# Reasons / flags that Preview treats as AI-assisted review (aligned with UI).
_AI_REVIEW_REASONS = frozenset(
    {
        "title_filled_by_ai",
        "uncertain_title",
        "id_title_mismatch",
    }
)


def _needs_human_review(table: dict) -> bool:
    return bool(table.get("human_review_needed"))


def _needs_ai_review(table: dict) -> bool:
    if table.get("title_repaired_by_llm") or table.get("table_id_repaired_by_llm"):
        return True
    reason = str(table.get("human_review_reason") or "").strip()
    if reason in _AI_REVIEW_REASONS:
        return True
    return False


def _scope_ids(
    plan: LlmActionPlan,
    valid_ids: Set[str],
) -> List[str]:
    """
    Resolve table_names against valid ids.

    For review filters, empty table_names means "all tables".
    For find/delete/download, empty means empty result.
    """
    named = sanitize_table_ids(plan.table_names, valid_ids)
    if plan.type in (
        LlmActionType.find_review_needed,
        LlmActionType.find_ai_review_needed,
    ):
        return named if named else sorted(valid_ids)
    return named


def _table_data_for_ids(
    by_id: Dict[str, dict],
    ids: Sequence[str],
) -> Dict[str, dict]:
    return {tid: by_id[tid] for tid in ids if tid in by_id}


def _display_name(table: dict, table_id: str) -> str:
    title = str(table.get("title") or table.get("name") or "").strip()
    return title or table_id


def _table_name_map(by_id: Dict[str, dict], ids: Sequence[str]) -> Dict[str, str]:
    return {tid: _display_name(by_id[tid], tid) for tid in ids if tid in by_id}


def execute_action_plan(
    plan: LlmActionPlan,
    tables: List[dict],
) -> Dict[str, Any]:
    """
    Apply an action plan to live review tables.

    Delete types never mutate the job — ``executed`` is always False for them;
    the UI confirms via soft_delete_tables.
    """
    by_id = tables_by_id(tables)
    valid_ids = set(by_id.keys())
    scope = _scope_ids(plan, valid_ids)

    action = plan.type
    files: Optional[List[dict]] = None
    executed = False
    selected: List[str] = []

    if action in (LlmActionType.find, LlmActionType.bulk_find):
        selected = scope
    elif action in (LlmActionType.delete, LlmActionType.bulk_delete):
        selected = scope
        executed = False
    elif action in (LlmActionType.download, LlmActionType.bulk_download):
        selected = scope
        subset = [by_id[tid] for tid in selected if tid in by_id]
        files = tables_to_download_files_base64(subset)
    elif action == LlmActionType.find_review_needed:
        selected = [tid for tid in scope if tid in by_id and _needs_human_review(by_id[tid])]
    elif action == LlmActionType.find_ai_review_needed:
        selected = [tid for tid in scope if tid in by_id and _needs_ai_review(by_id[tid])]
    elif action in (LlmActionType.propose_group, LlmActionType.bulk_propose_group):
        selected = scope
        executed = False
    elif action == LlmActionType.merge_groups:
        selected = scope
        executed = False
    else:
        selected = scope

    table_data = _table_data_for_ids(by_id, selected)
    name_map = _table_name_map(by_id, selected)

    if action in (LlmActionType.find, LlmActionType.bulk_find):
        executed = bool(selected)
    elif action in (
        LlmActionType.find_review_needed,
        LlmActionType.find_ai_review_needed,
    ):
        executed = bool(selected)
    elif action in (LlmActionType.download, LlmActionType.bulk_download):
        executed = bool(files)
    elif action in (LlmActionType.delete, LlmActionType.bulk_delete):
        executed = False
    elif action in (LlmActionType.propose_group, LlmActionType.bulk_propose_group):
        executed = False
    elif action == LlmActionType.merge_groups:
        executed = False

    message: Optional[str] = None
    if action in (LlmActionType.delete, LlmActionType.bulk_delete) and selected:
        message = (
            "Confirm delete via POST /api/pdf/jobs/{job_id}/tables/delete "
            "or llm_input with confirm_delete=true"
        )
    if action in (LlmActionType.propose_group, LlmActionType.bulk_propose_group) and selected:
        message = (
            "Confirm grouping via llm_input with confirm_apply_group=true "
            "or save groups in guided Grouping UI"
        )
    if action == LlmActionType.merge_groups:
        message = "Merge will be applied when group_indices are valid"

    group_name = (plan.group_name or "").strip() or None

    out: Dict[str, Any] = {
        "type": action.value if isinstance(action, LlmActionType) else str(action),
        "table_ids": selected,
        "table_names": name_map,
        "rationale": plan.rationale or "",
        "executed": executed,
        "table_data": table_data,
        "count": len(selected),
    }
    if files is not None:
        out["files"] = files
    if message:
        out["message"] = message
    if group_name:
        out["group_name"] = group_name
    return out
