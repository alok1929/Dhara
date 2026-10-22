#!/usr/bin/env python3
"""Compare chat backends outside Settings.

Production on-prem wiring stays ``DHARA_LLM_*`` plus ``LLM_MODEL`` in
``deploy/model-server``. This script sends one frozen prompt to each backend
listed in ``scripts/fixtures/llm_backends.yaml`` so OpenAI, Gemma 4B, and a
larger checkpoint can be compared between runs.

It does not load weights. Start vLLM yourself, and change ``LLM_MODEL`` plus
rebuild the ``llm`` container before calling a different catalogue id.

Usage (from the Dhara repo root, with backend deps installed):

    python scripts/compare_llm_backends.py
    python scripts/compare_llm_backends.py --only gemma-3-4b
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "scripts" / "fixtures" / "llm_compare_prompt.json"
BACKENDS = ROOT / "scripts" / "fixtures" / "llm_backends.yaml"


def _load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", default=[], help="backend name to run")
    parser.add_argument("--backends", type=Path, default=BACKENDS)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    args = parser.parse_args()

    prompt = json.loads(args.fixture.read_text(encoding="utf-8"))
    spec = _load_yaml(args.backends)
    wanted = set(args.only)
    from openai import OpenAI

    ran = 0
    for backend in spec.get("backends") or []:
        name = str(backend.get("name") or "")
        if wanted and name not in wanted:
            continue
        key_env = str(backend.get("api_key_env") or "DHARA_LLM_API_KEY")
        api_key = (os.environ.get(key_env) or "").strip() or "local"
        if key_env == "OPENAI_API_KEY" and not (os.environ.get(key_env) or "").strip():
            print(f"skip {name}: set {key_env}", file=sys.stderr)
            continue
        model = str(backend.get("model") or "")
        base_url = str(backend.get("base_url") or "").rstrip("/")
        notes = backend.get("notes") or ""
        print(f"\n== {name} model={model} base_url={base_url}")
        if notes:
            print(f"   {notes}")
        client = OpenAI(api_key=api_key, base_url=base_url)
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=prompt["messages"],
            )
        except Exception as exc:
            print(f"   error: {exc}", file=sys.stderr)
            continue
        message = resp.choices[0].message
        text = (getattr(message, "content", None) or "") or (
            getattr(message, "reasoning_content", None) or ""
        )
        print(text.strip() or "(empty content)")
        ran += 1
    if ran == 0:
        print("no backends ran", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
