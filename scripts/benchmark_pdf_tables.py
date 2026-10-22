#!/usr/bin/env python3
"""Compare PDF tables from models served by the Dhara model gateway.

The script does not call OpenAI or vLLM itself. It reads ``GET /v1/models`` on
the FastAPI gateway and, for each id, runs the same post-extraction validation
the API uses (``app.services.llm_prompts`` via ``run_post_extraction_validation``)
with ``DHARA_LLM_BASE_URL`` pointed at that gateway.

The OpenAI key stays in ``deploy/model-server/.env`` (``OPENAI_API_KEY``).
This process sends ``api_key=local``, the same way an on-prem Dhara worker does.

Usage (from the Dhara repo, backend venv):

    python scripts/benchmark_pdf_tables.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PDF_PATH = ROOT / "births_death_report_2024_cond.pdf"
OUTPUT_PATH = ROOT / "scripts" / "output" / "births_death_report_2024_cond_benchmark.json"
GATEWAY_URL = "http://127.0.0.1:8100"

sys.path.insert(0, str(BACKEND))


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _models(gateway: str) -> list[dict[str, str]]:
    payload = _get_json(gateway.rstrip("/") + "/v1/models")
    found = []
    for item in payload.get("data") or []:
        model_id = str(item.get("id") or "").strip()
        if model_id:
            found.append({
                "id": model_id,
                "owned_by": str(item.get("owned_by") or ""),
            })
    return found


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _column_names(table: dict) -> list[str]:
    names = []
    for column in table.get("columns") or []:
        if isinstance(column, dict):
            names.append(str(column.get("name") or ""))
        else:
            names.append(str(column))
    return names


def _rows(table: dict) -> list[list[str]]:
    rows = []
    for row in table.get("rows") or []:
        if isinstance(row, list):
            rows.append([_norm(cell) for cell in row])
        else:
            rows.append([_norm(row)])
    return rows


def _table_view(table: dict) -> dict[str, Any]:
    return {
        "title": _norm(table.get("title")),
        "columns": _column_names(table),
        "rows": _rows(table),
        "human_review_reason": table.get("human_review_reason"),
    }


def _page_tables(page: dict | None) -> list[dict[str, Any]]:
    tables = (page or {}).get("tables") or []
    return [_table_view(table) for table in tables if isinstance(table, dict)]


def _diff_tables(left: list[dict], right: list[dict], left_id: str, right_id: str) -> list[dict]:
    diffs: list[dict] = []
    if len(left) != len(right):
        diffs.append({
            "kind": "table_count",
            left_id: len(left),
            right_id: len(right),
        })
    for index in range(max(len(left), len(right))):
        if index >= len(left) or index >= len(right):
            diffs.append({
                "kind": "missing_table",
                "table": index,
                "missing_from": left_id if index >= len(left) else right_id,
            })
            continue
        a, b = left[index], right[index]
        if a["title"] != b["title"]:
            diffs.append({
                "kind": "title",
                "table": index,
                left_id: a["title"],
                right_id: b["title"],
            })
        if a["columns"] != b["columns"]:
            diffs.append({
                "kind": "columns",
                "table": index,
                left_id: a["columns"],
                right_id: b["columns"],
            })
        cell_examples = []
        mismatch_count = 0
        row_limit = max(len(a["rows"]), len(b["rows"]))
        if len(a["rows"]) != len(b["rows"]):
            diffs.append({
                "kind": "row_count",
                "table": index,
                left_id: len(a["rows"]),
                right_id: len(b["rows"]),
            })
        for row_index in range(row_limit):
            a_row = a["rows"][row_index] if row_index < len(a["rows"]) else []
            b_row = b["rows"][row_index] if row_index < len(b["rows"]) else []
            width = max(len(a_row), len(b_row), len(a["columns"]), len(b["columns"]))
            for col_index in range(width):
                a_cell = a_row[col_index] if col_index < len(a_row) else ""
                b_cell = b_row[col_index] if col_index < len(b_row) else ""
                if a_cell == b_cell:
                    continue
                mismatch_count += 1
                if len(cell_examples) >= 40:
                    continue
                column = ""
                if col_index < len(a["columns"]):
                    column = a["columns"][col_index]
                elif col_index < len(b["columns"]):
                    column = b["columns"][col_index]
                cell_examples.append({
                    "row": row_index,
                    "column": column,
                    left_id: a_cell,
                    right_id: b_cell,
                })
        if mismatch_count:
            diffs.append({
                "kind": "cells",
                "table": index,
                "mismatch_count": mismatch_count,
                "examples": cell_examples,
            })
    return diffs


def _fallback_pages(by_page: dict[int, dict]) -> list[int]:
    pages = []
    for page_num, page in by_page.items():
        for table in (page or {}).get("tables") or []:
            if isinstance(table, dict) and table.get("human_review_reason") == "llm_validation_failed_heuristic":
                pages.append(int(page_num))
                break
    return pages


def _run_model(model_id: str, gateway: str, extracted: dict) -> dict[int, dict]:
    from app.core.config import get_settings
    from app.services.extraction.pdf.confidence_validation.orchestrate import (
        run_post_extraction_validation,
    )

    os.environ.pop("DHARA_LLM_PROVIDER", None)
    os.environ["DHARA_LLM_BASE_URL"] = gateway
    os.environ["DHARA_LLM_MODEL"] = model_id
    os.environ["DHARA_LLM_API_KEY"] = "local"
    get_settings.cache_clear()
    return run_post_extraction_validation(
        extracted["pages_grouped"],
        extracted["page_text"],
        pdf_path=extracted["pdf_path"],
        outline_index=extracted["outline_index"],
    )


def _extract(pdf_path: Path) -> dict:
    from app.services.extraction.pdf.confidence_validation.confidence_split import (
        split_by_confidence,
    )
    from app.services.extraction.pdf.utils.pymupdf import run_pdf_extraction

    pages_grouped, page_text, outline_index = run_pdf_extraction(pdf_path)
    _high, llm_pages, reason_counts = split_by_confidence(
        pages_grouped,
        page_text,
        pdf_path=pdf_path,
        outline_index=outline_index,
    )
    return {
        "pdf_path": pdf_path,
        "pages_grouped": pages_grouped,
        "page_text": page_text,
        "outline_index": outline_index,
        "llm_pages": sorted(int(p) for p in llm_pages),
        "llm_reason_counts": {str(k): int(v) for k, v in reason_counts.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=PDF_PATH)
    parser.add_argument("--gateway", default=GATEWAY_URL)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    try:
        models = _models(args.gateway)
    except Exception as exc:
        print(f"gateway {args.gateway} is not reachable: {exc}", file=sys.stderr)
        return 1
    if len(models) < 2:
        print(
            f"gateway {args.gateway} listed {len(models)} model(s); need the OpenAI model and phi-4-mini-instruct",
            file=sys.stderr,
        )
        return 1

    models.sort(key=lambda item: 0 if item["owned_by"] == "openai" else 1)
    baseline = models[0]["id"]
    print(f"gateway {args.gateway}")
    for item in models:
        print(f"  model {item['id']} ({item['owned_by']})")

    print(f"extracting {pdf_path.name}")
    t0 = time.time()
    extracted = _extract(pdf_path)
    print(
        f"  {len(extracted['pages_grouped'])} page(s) with tables, "
        f"{len(extracted['llm_pages'])} sent to the LLM, in {time.time() - t0:.1f}s"
    )

    runs: dict[str, dict[int, dict]] = {}
    timings: dict[str, float] = {}
    for item in models:
        model_id = item["id"]
        print(f"validating with {model_id}")
        started = time.time()
        runs[model_id] = _run_model(model_id, args.gateway.rstrip("/"), extracted)
        timings[model_id] = round(time.time() - started, 1)
        print(f"  {len(runs[model_id])} page(s) in {timings[model_id]}s")

    llm_page_set = set(extracted["llm_pages"])
    pages_out = []
    different_pages = 0
    cell_mismatches = 0
    per_model_cells = {item["id"]: 0 for item in models if item["id"] != baseline}
    per_model_pages = {item["id"]: 0 for item in models if item["id"] != baseline}
    pair_left, pair_right = "phi-4-mini-instruct", "gemma-3-4b"
    pair_key = f"{pair_right} vs {pair_left}"
    pair_cells = 0
    pair_pages = 0
    table_counts = {item["id"]: 0 for item in models}
    for page_num in sorted(set().union(*runs.values())):
        views = {model_id: _page_tables(runs[model_id].get(page_num)) for model_id in runs}
        for model_id, tables in views.items():
            table_counts[model_id] += len(tables)
        base_tables = views[baseline]
        page_diffs = {}
        identical = True
        for model_id, tables in views.items():
            if model_id == baseline:
                continue
            diffs = _diff_tables(base_tables, tables, baseline, model_id)
            page_diffs[model_id] = diffs
            if diffs:
                identical = False
                per_model_pages[model_id] += 1
                n_cells = sum(item.get("mismatch_count", 0) for item in diffs if item.get("kind") == "cells")
                per_model_cells[model_id] += n_cells
                cell_mismatches += n_cells
        if pair_left in views and pair_right in views:
            pair_diffs = _diff_tables(views[pair_left], views[pair_right], pair_left, pair_right)
            page_diffs[pair_key] = pair_diffs
            if pair_diffs:
                identical = False
                pair_pages += 1
                pair_cells += sum(
                    item.get("mismatch_count", 0) for item in pair_diffs if item.get("kind") == "cells"
                )
        if not identical:
            different_pages += 1
        entry = {
            "page": page_num,
            "route": "llm" if page_num in llm_page_set else "heuristic",
            "identical": identical,
            "table_counts": {model_id: len(tables) for model_id, tables in views.items()},
            "titles": {model_id: [table["title"] for table in tables] for model_id, tables in views.items()},
        }
        if not identical:
            entry["tables"] = views
            entry["differences"] = page_diffs
        pages_out.append(entry)

    document = {
        "pdf": str(pdf_path),
        "gateway": args.gateway.rstrip("/"),
        "prompt_module": "app.services.llm_prompts",
        "pipeline": "run_post_extraction_validation",
        "baseline": baseline,
        "models": [
            {
                "id": item["id"],
                "owned_by": item["owned_by"],
                "elapsed_s": timings[item["id"]],
                "table_count": table_counts[item["id"]],
                "llm_fallback_pages": _fallback_pages(runs[item["id"]]),
            }
            for item in models
        ],
        "llm_pages": extracted["llm_pages"],
        "llm_reason_counts": extracted["llm_reason_counts"],
        "summary": {
            "pages": len(pages_out),
            "pages_identical": len(pages_out) - different_pages,
            "pages_different": different_pages,
            "cell_mismatches": cell_mismatches,
            "table_counts": table_counts,
            "against_baseline": {
                model_id: {
                    "pages_different": per_model_pages[model_id],
                    "cell_mismatches": per_model_cells[model_id],
                }
                for model_id in per_model_cells
            },
            "gemma_vs_phi": {
                "pages_different": pair_pages,
                "cell_mismatches": pair_cells,
            },
        },
        "pages": pages_out,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2), encoding="utf-8")
    print(
        f"wrote {args.output} — {different_pages} page(s) differ, "
        f"{cell_mismatches} cell mismatch(es) vs {baseline}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
