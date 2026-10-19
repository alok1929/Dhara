#!/usr/bin/env python3
"""
Preview chat CLI — same flow as chat.ipynb against the running Dhara backend.

Usage:
  python scripts/chat_preview_cli.py /path/to/file.pdf
  python scripts/chat_preview_cli.py /path/to/file.pdf --prompt "find spice tables"
  python scripts/chat_preview_cli.py --job-id <id> --prompt "download condiment tables"
  python scripts/chat_preview_cli.py /path/to/file.pdf --run-tests

Requires: backend on DHARA_BASE (default http://localhost:8000), LLM key in Settings.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
DEFAULT_PDF = REPO_ROOT / "media_to_upload1762321618.pdf"
DEFAULT_BASE = os.environ.get("DHARA_BASE", "http://localhost:8000").rstrip("/")
DEFAULT_EMAIL = os.environ.get("DHARA_EMAIL", "alokhegde2221@gmail.com")
DEFAULT_PASSWORD = os.environ.get("DHARA_PASSWORD", "12345678")


def _ensure_backend_path() -> None:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def login(base: str, email: str, password: str) -> Dict[str, str]:
    r = requests.post(f"{base}/api/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code == 401:
        r = requests.post(
            f"{base}/api/signup",
            json={"email": email, "password": password, "name": "ChatCLI"},
            timeout=30,
        )
    r.raise_for_status()
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def upload_pdf(base: str, headers: dict, pdf_path: Path) -> str:
    with pdf_path.open("rb") as f:
        r = requests.post(
            f"{base}/api/upload",
            headers=headers,
            data={"type": "pdf"},
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=300,
        )
    r.raise_for_status()
    return str(r.json()["job_id"])


def poll_job(base: str, headers: dict, job_id: str, *, verbose: bool = True) -> None:
    status = None
    for i in range(600):
        r = requests.get(f"{base}/api/pdf/jobs/{job_id}", headers=headers, timeout=60)
        r.raise_for_status()
        job = r.json()
        status = job.get("status")
        if verbose and (i % 5 == 0 or status not in ("queued", "running", "processing")):
            pct = job.get("percent") or (job.get("progress") or {}).get("percent")
            msg = job.get("message") or (job.get("progress") or {}).get("message") or ""
            print(f"  [{i:03d}] status={status} percent={pct} {msg}")
        if status in ("done", "completed_with_errors", "error", "failed"):
            break
        time.sleep(2)
    else:
        raise TimeoutError(f"Job {job_id} still {status} after polling")
    if status not in ("done", "completed_with_errors"):
        raise RuntimeError(f"Job failed: {status}")


def fetch_preview_tables(base: str, headers: dict, job_id: str) -> List[dict]:
    r = requests.get(f"{base}/api/pdf/jobs/{job_id}/result", headers=headers, timeout=120)
    r.raise_for_status()
    tables = r.json().get("tables") or []
    if not tables:
        raise RuntimeError("Preview result has no tables")
    return tables


def compact_tables_for_llm(tables: List[dict]) -> List[dict]:
    out = []
    for t in tables:
        tid = t.get("table_id")
        if not tid:
            continue
        entry = {
            "table_id": tid,
            "page": t.get("page"),
            "title": t.get("title"),
            "banner_table_id": t.get("banner_table_id"),
            "short_description": t.get("short_description")
            or t.get("description")
            or t.get("summary"),
            "human_review_needed": t.get("human_review_needed"),
            "human_review_reason": t.get("human_review_reason"),
        }
        out.append({k: v for k, v in entry.items() if v is not None and v != ""})
    return out


def table_ids_from_result(result: Dict[str, Any]) -> List[str]:
    ids = result.get("table_ids")
    if isinstance(ids, list) and ids:
        return [str(x) for x in ids]
    names = result.get("table_names")
    if isinstance(names, dict):
        return list(names.keys())
    if isinstance(names, list):
        return [str(x) for x in names]
    return []


@dataclass
class ValidationIssue:
    message: str


def validate_llm_result(
    result: Dict[str, Any],
    *,
    valid_ids: Set[str],
    tables_by_id: Dict[str, dict],
) -> List[ValidationIssue]:
    """Ensure the API never returns phantom tables or inconsistent payloads."""
    issues: List[ValidationIssue] = []
    ids = table_ids_from_result(result)
    unknown = [tid for tid in ids if tid not in valid_ids]
    if unknown:
        issues.append(ValidationIssue(f"unknown table_ids (not in job): {unknown[:5]}"))

    td = result.get("table_data") or {}
    if not isinstance(td, dict):
        issues.append(ValidationIssue("table_data is not an object"))
        td = {}

    extra_data_keys = set(td.keys()) - set(ids)
    if extra_data_keys:
        issues.append(
            ValidationIssue(f"table_data keys not listed in table_ids: {list(extra_data_keys)[:5]}")
        )
    missing_data = [tid for tid in ids if tid not in td and result.get("type", "").startswith("find")]
    if missing_data and result.get("type") in (
        "find",
        "bulk_find",
        "find_review_needed",
        "find_ai_review_needed",
    ):
        issues.append(ValidationIssue(f"missing table_data for ids: {missing_data[:5]}"))

    for tid in ids:
        if tid in td:
            live = tables_by_id.get(tid)
            if live and str(td[tid].get("table_id") or tid) != tid:
                issues.append(ValidationIssue(f"table_data[{tid}] has mismatched table_id field"))

    names = result.get("table_names")
    if isinstance(names, dict):
        for tid in ids:
            if tid not in names:
                issues.append(ValidationIssue(f"table_names map missing label for {tid}"))

    action = str(result.get("type") or "")
    if action in ("delete", "bulk_delete") and result.get("executed") is True:
        issues.append(ValidationIssue("delete action must not auto-execute (executed should be false)"))

    if action in ("download", "bulk_download") and ids and not (result.get("files") or []):
        # files may be filled after execute_preview_action; warn only at llm_input layer
        pass

    return issues


def print_result_summary(result: Dict[str, Any]) -> None:
    ids = table_ids_from_result(result)
    print(f"  type: {result.get('type')}")
    print(f"  rationale: {result.get('rationale', '')[:200]}")
    print(f"  matches: {len(ids)}  executed: {result.get('executed')}")
    if ids:
        names = result.get("table_names") or {}
        for tid in ids[:8]:
            label = names.get(tid, tid) if isinstance(names, dict) else tid
            print(f"    - {tid}: {str(label)[:90]}")
        if len(ids) > 8:
            print(f"    … and {len(ids) - 8} more")


def send_prompt(
    *,
    base: str,
    headers: dict,
    job_id: str,
    user_request: str,
    chat_tables: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    _ensure_backend_path()
    from app.services.llm_preview.client import post_llm_input

    return post_llm_input(
        base_url=base,
        job_id=job_id,
        user_request=user_request,
        headers=headers,
        tables=chat_tables,
    )


@dataclass
class TestCase:
    name: str
    prompt: str
    check: Callable[[Dict[str, Any], Dict[str, dict], Set[str]], List[str]]
    follow_up_download: bool = False


def _text_blob(t: dict) -> str:
    parts = [
        str(t.get("title") or ""),
        str(t.get("name") or ""),
        str(t.get("summary") or ""),
    ]
    return " ".join(parts).upper()


def _build_test_cases() -> List[TestCase]:
    def check_spices(result, by_id, valid):
        errs = []
        ids = table_ids_from_result(result)
        if not ids:
            return ["expected at least one spice/condiment table"]
        if result.get("type") not in ("find", "bulk_find", "download", "bulk_download"):
            errs.append(f"unexpected type {result.get('type')}")
        for tid in ids:
            blob = _text_blob(by_id.get(tid, {}))
            if not re.search(r"SPICE|CONDIMENT", blob):
                errs.append(f"{tid} title does not mention spice/condiment: {blob[:80]}")
        return errs

    def check_nonsense(result, by_id, valid):
        ids = table_ids_from_result(result)
        if ids:
            return [f"expected zero matches for nonsense query, got {ids}"]
        return []

    def check_delete_safe(result, by_id, valid):
        errs = []
        if result.get("type") not in ("delete", "bulk_delete"):
            errs.append(f"expected delete type, got {result.get('type')}")
        if result.get("executed") is True:
            errs.append("delete must not execute without confirm")
        return errs

    def check_rice(result, by_id, valid):
        ids = table_ids_from_result(result)
        if not ids:
            return ["expected at least one rice-related table"]
        rice_ok = False
        for tid in ids:
            if re.search(r"\bRICE\b", _text_blob(by_id.get(tid, {}))):
                rice_ok = True
        if not rice_ok:
            return ["no returned table mentions rice in title/summary"]
        return []

    def check_review(result, by_id, valid):
        errs = []
        if result.get("type") != "find_review_needed":
            errs.append(f"expected find_review_needed, got {result.get('type')}")
        ids = table_ids_from_result(result)
        for tid in ids:
            t = by_id.get(tid) or (result.get("table_data") or {}).get(tid) or {}
            if not t.get("human_review_needed"):
                errs.append(f"{tid} is not flagged human_review_needed")
        return errs

    def check_publication_team(result, by_id, valid):
        ids = table_ids_from_result(result)
        if len(ids) != 1:
            return [f"expected exactly one team/publication table, got {len(ids)}"]
        blob = _text_blob(by_id.get(ids[0], {}))
        if "PUBLICATION" not in blob and "TEAM" not in blob:
            return [f"unexpected table for publication query: {blob[:100]}"]
        return []

    return [
        TestCase("search_condiment_spices", "show tables related to condiment and spices", check_spices),
        TestCase("nonsense_no_hallucination", "tables about lunar diamond mining exports 2099", check_nonsense),
        TestCase(
            "delete_selection_only",
            "delete tables related to condiment and spices",
            check_delete_safe,
        ),
        TestCase(
            "download_spices",
            "download tables related to condiment and spices",
            lambda r, b, v: (
                ["expected download/bulk_download"]
                if r.get("type") not in ("download", "bulk_download")
                else check_spices(r, b, v)
            ),
            follow_up_download=True,
        ),
        TestCase(
            "search_rice",
            "find tables that mention rice in the title or description",
            check_rice,
        ),
        TestCase(
            "publication_team",
            "show the table about the team associated in preparation of publication",
            check_publication_team,
        ),
        TestCase(
            "human_review_filter",
            "which tables need human review",
            check_review,
        ),
    ]


def run_test_suite(
    *,
    base: str,
    headers: dict,
    job_id: str,
    chat_tables: List[dict],
    tables_by_id: Dict[str, dict],
    valid_ids: Set[str],
    download_dir: Path,
) -> int:
    _ensure_backend_path()
    from app.services.llm_preview.client import execute_preview_action

    failures = 0
    for tc in _build_test_cases():
        print(f"\n=== TEST: {tc.name} ===")
        print(f"prompt: {tc.prompt!r}")
        try:
            result = send_prompt(
                base=base,
                headers=headers,
                job_id=job_id,
                user_request=tc.prompt,
                chat_tables=chat_tables,
            )
        except Exception as e:
            print(f"  FAIL request: {e}")
            failures += 1
            continue

        print_result_summary(result)
        val_issues = validate_llm_result(result, valid_ids=valid_ids, tables_by_id=tables_by_id)
        logic_errs = tc.check(result, tables_by_id, valid_ids)

        if tc.follow_up_download and not logic_errs and not val_issues:
            try:
                ex = execute_preview_action(
                    result,
                    base_url=base,
                    job_id=job_id,
                    headers=headers,
                    download_dir=download_dir,
                )
                if not ex.get("executed") or not ex.get("path"):
                    logic_errs.append("download follow-up did not write a file")
                else:
                    p = Path(str(ex["path"]))
                    if not p.is_file() or p.stat().st_size < 100:
                        logic_errs.append(f"download output too small or missing: {p}")
                    else:
                        print(f"  download path: {p} ({p.stat().st_size:,} bytes)")
            except Exception as e:
                logic_errs.append(f"download follow-up failed: {e}")

        if val_issues:
            print("  VALIDATION:")
            for v in val_issues:
                print(f"    - {v.message}")
            failures += 1
        if logic_errs:
            print("  ASSERTIONS:")
            for msg in logic_errs:
                print(f"    - {msg}")
            failures += 1
        if not val_issues and not logic_errs:
            print("  PASS")

    print(f"\n{'=' * 40}\nTests failed: {failures}")
    return failures


def interactive_loop(
    *,
    base: str,
    headers: dict,
    job_id: str,
    chat_tables: List[dict],
    tables_by_id: Dict[str, dict],
    valid_ids: Set[str],
    download_dir: Path,
) -> None:
    _ensure_backend_path()
    from app.services.llm_preview.client import execute_preview_action

    print("\nInteractive chat (empty line or 'quit' to exit). Commands: /download /delete")
    while True:
        try:
            line = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line or line.lower() in ("quit", "exit", "q"):
            break

        confirm_delete = False
        do_download = False
        if line.startswith("/download "):
            do_download = True
            line = line[len("/download ") :].strip()
        elif line.startswith("/delete "):
            confirm_delete = True
            line = line[len("/delete ") :].strip()

        result = send_prompt(
            base=base,
            headers=headers,
            job_id=job_id,
            user_request=line,
            chat_tables=chat_tables,
        )
        print_result_summary(result)
        for v in validate_llm_result(result, valid_ids=valid_ids, tables_by_id=tables_by_id):
            print(f"  WARNING: {v.message}")

        action = str(result.get("type") or "")
        if do_download or action in ("download", "bulk_download"):
            ex = execute_preview_action(
                result,
                base_url=base,
                job_id=job_id,
                headers=headers,
                download_dir=download_dir,
            )
            print(f"  download: executed={ex.get('executed')} path={ex.get('path')}")
        elif confirm_delete or action in ("delete", "bulk_delete"):
            ex = execute_preview_action(
                result,
                base_url=base,
                job_id=job_id,
                headers=headers,
                confirm_delete=confirm_delete,
            )
            print(f"  delete: executed={ex.get('executed')} message={ex.get('message')}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preview chat CLI (llm_input over PDF jobs)")
    p.add_argument(
        "pdf",
        nargs="?",
        type=Path,
        default=None,
        help=f"PDF to upload (default: {DEFAULT_PDF.name})",
    )
    p.add_argument("--job-id", help="Skip upload; use an existing finished job_id")
    p.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--prompt", "-p", action="append", dest="prompts", help="One-shot prompt(s)")
    p.add_argument("--run-tests", action="store_true", help="Run built-in scenario suite")
    p.add_argument(
        "--download-dir",
        type=Path,
        default=REPO_ROOT / "chat_cli_downloads",
        help="Where to write download outputs",
    )
    p.add_argument("--json", action="store_true", help="Print raw JSON for each llm_input response")
    p.add_argument("-q", "--quiet", action="store_true", help="Less upload/poll logging")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base.rstrip("/")

    pdf_path = args.pdf
    if args.job_id:
        job_id = args.job_id.strip()
    else:
        if pdf_path is None:
            pdf_path = DEFAULT_PDF
        pdf_path = pdf_path.expanduser().resolve()
        if not pdf_path.is_file():
            print(f"PDF not found: {pdf_path}", file=sys.stderr)
            return 2

    if not args.quiet:
        print(f"API: {base}")

    headers = login(base, args.email, args.password)
    if not args.quiet:
        print("Logged in.")

    if not args.job_id:
        if not args.quiet:
            print(f"Uploading {pdf_path.name} …")
        job_id = upload_pdf(base, headers, pdf_path)
        if not args.quiet:
            print(f"job_id={job_id}")
            print("Polling extraction …")
        poll_job(base, headers, job_id, verbose=not args.quiet)
    elif not args.quiet:
        print(f"Using existing job_id={job_id}")

    tables = fetch_preview_tables(base, headers, job_id)
    valid_ids = {str(t["table_id"]) for t in tables if t.get("table_id")}
    tables_by_id = {str(t["table_id"]): t for t in tables if t.get("table_id")}
    chat_tables = compact_tables_for_llm(tables)
    if not args.quiet:
        print(f"Preview tables: {len(tables)}  valid_ids: {len(valid_ids)}")

    args.download_dir.mkdir(parents=True, exist_ok=True)

    if args.run_tests:
        return 1 if run_test_suite(
            base=base,
            headers=headers,
            job_id=job_id,
            chat_tables=chat_tables,
            tables_by_id=tables_by_id,
            valid_ids=valid_ids,
            download_dir=args.download_dir,
        ) else 0

    if args.prompts:
        for prompt in args.prompts:
            print(f"\n--- prompt: {prompt!r} ---")
            result = send_prompt(
                base=base,
                headers=headers,
                job_id=job_id,
                user_request=prompt,
                chat_tables=chat_tables,
            )
            if args.json:
                print(json.dumps(result, indent=2, default=str)[:8000])
            else:
                print_result_summary(result)
            for v in validate_llm_result(result, valid_ids=valid_ids, tables_by_id=tables_by_id):
                print(f"  VALIDATION ERROR: {v.message}")
                return 1
        return 0

    interactive_loop(
        base=base,
        headers=headers,
        job_id=job_id,
        chat_tables=chat_tables,
        tables_by_id=tables_by_id,
        valid_ids=valid_ids,
        download_dir=args.download_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
