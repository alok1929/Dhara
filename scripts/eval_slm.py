#!/usr/bin/env python3
"""Run the same prompts on each small on-prem model and store JSON metrics.

The loop is:

    load_model()
    run_model()
    store_metrics()
    next model

Ready catalogue rows with ``device: cpu`` are the default set. Add the next
SLM to ``deploy/model-server/models.yaml`` (status ready, device cpu) and to
the gateway, then run this script again. Add a shared task in
``scripts/fixtures/slm_eval_prompts.json``.

The model must already be loaded. This script calls the gateway; it does not
start or stop containers.

Usage (from the Dhara repo root):

    python scripts/eval_slm.py
    python scripts/eval_slm.py --only gemma-2-2b-it --only bitnet-b1.58-2b
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "deploy" / "model-server" / "models.yaml"
PROMPTS = ROOT / "scripts" / "fixtures" / "slm_eval_prompts.json"
MODEL_ENV = ROOT / "deploy" / "model-server" / ".env"
OUT_DIR = ROOT / "scripts" / "output" / "slm_eval"


def _load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def gateway_root() -> str:
    explicit = (os.environ.get("DHARA_LLM_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        if explicit.endswith("/v1"):
            explicit = explicit[:-3]
        return explicit
    port = "8100"
    if MODEL_ENV.is_file():
        for line in MODEL_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("GATEWAY_PORT="):
                value = line.split("=", 1)[1].strip()
                if value:
                    port = value
                break
    return f"http://127.0.0.1:{port}"


def catalogue_models(path: Path, *, device: str | None, only: set[str]) -> list[dict]:
    raw = _load_yaml(path)
    found: list[dict] = []
    for entry in raw.get("llm") or []:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("id") or "").strip()
        if not model_id or str(entry.get("status") or "") != "ready":
            continue
        if device and str(entry.get("device") or "") != device:
            continue
        if only and model_id not in only:
            continue
        found.append(entry)
    return found


def parameter_billions(entry: dict) -> float | None:
    raw = str(entry.get("parameters") or "").strip().lower()
    if raw.endswith("b"):
        raw = raw[:-1]
    try:
        return float(raw)
    except ValueError:
        return None


def models_under(path: Path, billions: float, *, only: set[str]) -> list[dict]:
    """Ready catalogue rows whose parameter count is below ``billions``."""
    found = []
    for entry in catalogue_models(path, device=None, only=only):
        size = parameter_billions(entry)
        if size is not None and size < billions:
            found.append(entry)
    return found


def parse_json_text(raw: str) -> Any | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return False
        return all(_values_match(left, right) for left, right in zip(expected, actual))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return all(_values_match(value, actual.get(key)) for key, value in expected.items())
    return expected == actual


def score_response(raw: str, expect: dict | None) -> dict:
    """Score one reply. ``passed`` is true when every declared check holds."""
    expect = expect or {}
    parsed = parse_json_text(raw)
    checks: list[dict] = []
    if expect.get("json"):
        checks.append({"name": "json", "passed": isinstance(parsed, dict)})
    equals = expect.get("equals") or {}
    if equals:
        body = parsed if isinstance(parsed, dict) else {}
        ok = _values_match(equals, {key: body.get(key) for key in equals})
        checks.append({"name": "equals", "passed": ok, "expected": equals, "actual": {key: body.get(key) for key in equals}})
    needles = [str(item) for item in (expect.get("reply_contains") or [])]
    if needles:
        reply = ""
        if isinstance(parsed, dict) and parsed.get("reply") is not None:
            reply = str(parsed.get("reply"))
        haystack = f"{reply}\n{raw or ''}"
        missing = [item for item in needles if item.lower() not in haystack.lower()]
        checks.append({"name": "reply_contains", "passed": not missing, "missing": missing})
    return {
        "passed": bool(checks) and all(item["passed"] for item in checks),
        "checks": checks,
        "parsed": parsed if isinstance(parsed, (dict, list)) else None,
    }


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": "Bearer local"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def served_model_ids(gateway: str, timeout: float) -> list[str]:
    payload = _get_json(f"{gateway}/v1/models", timeout=timeout)
    ids: list[str] = []
    for item in payload.get("data") or []:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids


def chat(gateway: str, model: str, messages: list[dict], max_tokens: int, timeout: float) -> dict:
    started = time.perf_counter()
    payload = _post_json(
        f"{gateway}/v1/chat/completions",
        {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = message.get("content") or message.get("reasoning_content") or ""
    usage = payload.get("usage") or {}
    return {
        "latency_ms": elapsed_ms,
        "response": text,
        "finish_reason": choice.get("finish_reason"),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        },
    }


def load_model(gateway: str, entry: dict, *, timeout: float) -> dict:
    """Confirm the gateway can call this id, then time one short reply."""
    model_id = str(entry["id"])
    started = time.perf_counter()
    try:
        ids = served_model_ids(gateway, timeout=min(timeout, 15))
    except Exception as exc:  # noqa: BLE001
        return {
            "id": model_id,
            "name": entry.get("name") or model_id,
            "loaded": False,
            "load_ms": round((time.perf_counter() - started) * 1000),
            "error": f"gateway unreachable: {exc}",
        }
    if model_id not in ids:
        return {
            "id": model_id,
            "name": entry.get("name") or model_id,
            "loaded": False,
            "load_ms": round((time.perf_counter() - started) * 1000),
            "error": f"{model_id} is not served. Gateway has: {', '.join(ids) or '(none)'}",
        }
    try:
        probe = chat(
            gateway,
            model_id,
            [{"role": "user", "content": "Reply with the single word ready."}],
            max_tokens=16,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "id": model_id,
            "name": entry.get("name") or model_id,
            "loaded": False,
            "load_ms": round((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }
    return {
        "id": model_id,
        "name": entry.get("name") or model_id,
        "context": entry.get("context"),
        "parameters": entry.get("parameters"),
        "loaded": True,
        "load_ms": probe["latency_ms"],
        "probe_response": (probe["response"] or "").strip(),
        "error": None,
    }


def run_model(gateway: str, model_id: str, cases: list[dict], *, timeout: float) -> list[dict]:
    results: list[dict] = []
    for case in cases:
        case_id = str(case.get("id") or "case")
        try:
            reply = chat(
                gateway,
                model_id,
                case.get("messages") or [],
                int(case.get("max_tokens") or 256),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "id": case_id,
                    "passed": False,
                    "error": str(exc),
                    "response": "",
                    "latency_ms": None,
                    "checks": [],
                }
            )
            continue
        scored = score_response(reply["response"], case.get("expect"))
        results.append(
            {
                "id": case_id,
                "passed": scored["passed"],
                "error": None,
                "response": reply["response"],
                "parsed": scored["parsed"],
                "checks": scored["checks"],
                "latency_ms": reply["latency_ms"],
                "finish_reason": reply["finish_reason"],
                "usage": reply["usage"],
            }
        )
    return results


def summarize(cases: list[dict]) -> dict:
    latencies = [item["latency_ms"] for item in cases if isinstance(item.get("latency_ms"), int)]
    return {
        "cases": len(cases),
        "passed": sum(1 for item in cases if item.get("passed")),
        "errors": sum(1 for item in cases if item.get("error")),
        "mean_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
    }


def store_metrics(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    latest = out_dir / "latest.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def evaluate(models: list[dict], cases: list[dict], gateway: str, timeout: float) -> dict:
    rows: list[dict] = []
    for entry in models:
        loaded = load_model(gateway, entry, timeout=timeout)
        print(f"\n== {loaded['id']} loaded={loaded['loaded']} load_ms={loaded['load_ms']}")
        if loaded.get("error"):
            print(f"   {loaded['error']}", file=sys.stderr)
        case_rows: list[dict] = []
        if loaded["loaded"]:
            case_rows = run_model(gateway, loaded["id"], cases, timeout=timeout)
            for row in case_rows:
                mark = "pass" if row["passed"] else "fail"
                print(f"   {row['id']}: {mark} {row.get('latency_ms')} ms")
        loaded["cases"] = case_rows
        loaded["summary"] = summarize(case_rows)
        rows.append(loaded)
    return {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "gateway": gateway,
        "prompt_file": str(PROMPTS.relative_to(ROOT)),
        "models": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", default=[], help="catalogue id to include")
    parser.add_argument("--device", default="", help="If set, only this catalogue device")
    parser.add_argument(
        "--max-parameters",
        type=float,
        default=5,
        help="Include ready models below this size in billions. Used when --device is omitted.",
    )
    parser.add_argument("--all-ready", action="store_true", help="include every ready catalogue id")
    parser.add_argument("--gateway", default="", help="gateway origin, without /v1")
    parser.add_argument("--prompts", type=Path, default=PROMPTS)
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--timeout", type=float, default=180, help="seconds per request")
    args = parser.parse_args()

    only = set(args.only)
    if args.all_ready or args.device:
        models = catalogue_models(
            args.catalogue,
            device=None if args.all_ready else args.device,
            only=only,
        )
    else:
        models = models_under(args.catalogue, args.max_parameters, only=only)
    if not models:
        print("no catalogue models matched", file=sys.stderr)
        return 1
    suite = json.loads(args.prompts.read_text(encoding="utf-8"))
    cases = suite.get("cases") or []
    if not cases:
        print("no prompt cases", file=sys.stderr)
        return 1
    gateway = (args.gateway or gateway_root()).rstrip("/")
    report = evaluate(models, cases, gateway, args.timeout)
    path = store_metrics(report, args.out)
    print(f"\nwrote {path}")
    print(f"wrote {args.out / 'latest.json'}")
    failed = [row["id"] for row in report["models"] if not row["loaded"] or row["summary"]["passed"] < row["summary"]["cases"]]
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
