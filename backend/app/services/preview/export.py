"""Table download helpers shared by PDF routes and llm_preview."""
from __future__ import annotations

import base64
import io
import pathlib
import zipfile
from typing import Any, Dict, List, Sequence, Tuple

from app.services.ingestion.wizard.table_export import safe_download_stem, table_to_excel_bytes

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def table_xlsx_bytes_and_filename(table: dict, *, table_id: str | None = None) -> Tuple[bytes, str]:
    tid = str(table_id or table.get("table_id") or "table")
    xlsx = table_to_excel_bytes(table)
    stem = safe_download_stem(table, fallback=f"table_{tid}")
    return xlsx, f"{stem}.xlsx"


def tables_to_zip_bytes(
    tables: Sequence[dict],
    job_name: str,
    job_id: str,
) -> Tuple[bytes, str]:
    """Build a ZIP of .xlsx files; returns (zip_bytes, download_filename)."""
    buf = io.BytesIO()
    used_names: set = set()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for t in tables:
            tid = str(t.get("table_id") or "table")
            stem = safe_download_stem(t, fallback=f"table_{tid}")
            name = f"{stem}.xlsx"
            if name in used_names:
                name = f"{stem}_{tid}.xlsx"
            used_names.add(name)
            zf.writestr(name, table_to_excel_bytes(t))
    zip_stem = safe_download_stem({"title": pathlib.Path(str(job_name)).stem}, fallback=job_id)
    return buf.getvalue(), f"{zip_stem}_tables.zip"


def tables_to_download_files_base64(tables: Sequence[dict]) -> List[Dict[str, Any]]:
    """JSON-safe download artifacts for llm_preview download / bulk_download."""
    files: List[Dict[str, Any]] = []
    used_names: set = set()
    for t in tables:
        tid = str(t.get("table_id") or "table")
        xlsx, filename = table_xlsx_bytes_and_filename(t, table_id=tid)
        if filename in used_names:
            stem = filename.rsplit(".", 1)[0]
            filename = f"{stem}_{tid}.xlsx"
        used_names.add(filename)
        files.append(
            {
                "table_id": tid,
                "filename": filename,
                "media_type": XLSX_MEDIA,
                "content_base64": base64.b64encode(xlsx).decode("ascii"),
            }
        )
    return files
