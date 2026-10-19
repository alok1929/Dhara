"""HTTP + follow-up helpers for notebooks and scripts (no FastAPI dependency)."""
from __future__ import annotations

import base64
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

from app.services.llm_preview.schemas import LlmInputResponse


def post_llm_input(
    *,
    base_url: str,
    job_id: str,
    user_request: str,
    headers: Optional[Dict[str, str]] = None,
    prompt: Optional[str] = None,
    tables: Optional[List[dict]] = None,
    persist_reviews: bool = False,
    refresh: bool = False,
    force_summarize: bool = False,
    confirm_delete: bool = False,
    timeout: float = 300,
) -> Dict[str, Any]:
    """
    Single chat entrypoint: LangChain intent + action execution on the backend.

    Catalog is auto-built from Preview tables when missing or when ``refresh`` is true.
    """
    body: Dict[str, Any] = {"user_request": user_request}
    if prompt:
        body["prompt"] = prompt
    if tables is not None:
        body["tables"] = tables
    if persist_reviews:
        body["persist_reviews"] = True
    if refresh:
        body["refresh"] = True
    if force_summarize:
        body["force_summarize"] = True
    if confirm_delete:
        body["confirm_delete"] = True

    hdrs = dict(headers or {})
    hdrs.setdefault("Content-Type", "application/json")
    r = requests.post(
        f"{base_url.rstrip('/')}/api/llm_preview/jobs/{job_id}/llm_input",
        headers=hdrs,
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return LlmInputResponse.model_validate(data).model_dump()


def post_llm_preview_data(
    *,
    base_url: str,
    job_id: str,
    headers: Optional[Dict[str, str]] = None,
    tables: Optional[List[dict]] = None,
    force_summarize: bool = False,
    timeout: float = 120,
) -> Dict[str, Any]:
    """Explicitly store catalog on the job (optional — llm_input can auto-build)."""
    body: Dict[str, Any] = {}
    if tables is not None:
        body["tables"] = tables
    if force_summarize:
        body["force_summarize"] = True
    hdrs = dict(headers or {})
    hdrs.setdefault("Content-Type", "application/json")
    r = requests.post(
        f"{base_url.rstrip('/')}/api/llm_preview/jobs/{job_id}/llm_preview_data",
        headers=hdrs,
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def get_llm_preview_data(
    *,
    base_url: str,
    job_id: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60,
) -> Dict[str, Any]:
    hdrs = dict(headers or {})
    r = requests.get(
        f"{base_url.rstrip('/')}/api/llm_preview/jobs/{job_id}/llm_preview_data",
        headers=hdrs,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _table_ids_from_result(action_result: Dict[str, Any]) -> List[str]:
    ids = action_result.get("table_ids")
    if isinstance(ids, list) and ids:
        return [str(x) for x in ids]
    names = action_result.get("table_names")
    if isinstance(names, dict):
        return list(names.keys())
    if isinstance(names, list):
        return [str(x) for x in names]
    return []


def execute_preview_action(
    action_result: Dict[str, Any],
    *,
    base_url: Optional[str] = None,
    base: Optional[str] = None,
    job_id: str,
    headers: Optional[Dict[str, str]] = None,
    confirm_delete: bool = False,
    download_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Optional follow-up on ``post_llm_input`` output.

    - find / bulk_find / review filters: returns the same payload (already executed).
    - delete / bulk_delete: soft-delete only when ``confirm_delete=True``.
    - download / bulk_download: write xlsx files or a zip to ``download_dir``.
    """
    resolved_base = (base_url or base or "").strip()
    if not resolved_base:
        raise ValueError("base_url (or base) is required")

    action = str(action_result.get("type") or "find").strip().lower()
    table_ids = _table_ids_from_result(action_result)
    hdrs = dict(headers or {})

    if action in ("find", "bulk_find", "find_review_needed", "find_ai_review_needed"):
        return {
            **action_result,
            "executed": action_result.get("executed", True),
            "table_ids": table_ids,
            "count": len(table_ids),
        }

    if action in ("delete", "bulk_delete"):
        if not confirm_delete:
            return {
                **action_result,
                "executed": False,
                "table_ids": table_ids,
                "count": len(table_ids),
                "message": action_result.get("message")
                or "Pass confirm_delete=True to soft-delete these tables",
            }
        if not table_ids:
            return {"type": action, "executed": False, "deleted": [], "count": 0}
        r = requests.post(
            f"{resolved_base.rstrip('/')}/api/pdf/jobs/{job_id}/tables/delete",
            headers={**hdrs, "Content-Type": "application/json"},
            json={"table_ids": table_ids},
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        return {
            "type": action,
            "executed": True,
            "deleted": body.get("deleted") or table_ids,
            "deleted_count": body.get("deleted_count"),
            "response": body,
        }

    if action in ("download", "bulk_download"):
        files = action_result.get("files") or []
        if files:
            out_dir = Path(download_dir) if download_dir else Path.cwd()
            out_dir.mkdir(parents=True, exist_ok=True)
            if len(files) == 1:
                f0 = files[0]
                out_path = out_dir / str(f0.get("filename") or f"{table_ids[0]}.xlsx")
                out_path.write_bytes(base64.b64decode(f0["content_base64"]))
                return {
                    "type": action,
                    "executed": True,
                    "path": str(out_path),
                    "table_ids": table_ids,
                    "count": len(table_ids),
                    "bytes": out_path.stat().st_size,
                }
            zip_path = out_dir / f"{job_id}_selected_tables.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    name = str(f.get("filename") or "table.xlsx")
                    zf.writestr(name, base64.b64decode(f["content_base64"]))
            return {
                "type": action,
                "executed": True,
                "path": str(zip_path),
                "table_ids": table_ids,
                "count": len(table_ids),
                "bytes": zip_path.stat().st_size,
            }

        if not table_ids:
            return {"type": action, "executed": False, "path": None, "count": 0}
        r = requests.post(
            f"{resolved_base.rstrip('/')}/api/pdf/jobs/{job_id}/tables/download-zip",
            headers={**hdrs, "Content-Type": "application/json"},
            json={"table_ids": table_ids},
            timeout=180,
        )
        r.raise_for_status()
        out_dir = Path(download_dir) if download_dir else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{job_id}_selected_tables.zip"
        out_path.write_bytes(r.content)
        return {
            "type": action,
            "executed": True,
            "path": str(out_path),
            "table_ids": table_ids,
            "count": len(table_ids),
            "bytes": len(r.content),
        }

    raise ValueError(f"Unknown action type: {action!r}")
