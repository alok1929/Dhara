"""Scoring for the small-model comparison script."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "eval_slm.py"
PROMPTS = ROOT / "scripts" / "fixtures" / "slm_eval_prompts.json"


def _load():
    spec = importlib.util.spec_from_file_location("eval_slm", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_score_passes_exact_json():
    mod = _load()
    raw = json.dumps({"reply": "There are 3 tables.", "action": "none", "table_ids": []})
    scored = mod.score_response(
        raw,
        {"json": True, "equals": {"action": "none", "table_ids": []}, "reply_contains": ["3"]},
    )
    assert scored["passed"] is True


def test_score_fails_when_the_id_is_wrong():
    mod = _load()
    raw = json.dumps({"reply": "Deaths needs review.", "action": "find", "table_ids": ["T1"]})
    scored = mod.score_response(raw, {"json": True, "equals": {"action": "find", "table_ids": ["T2"]}})
    assert scored["passed"] is False
    assert scored["checks"][1]["actual"]["table_ids"] == ["T1"]


def test_score_reads_json_wrapped_in_prose():
    mod = _load()
    raw = 'Here is the result:\n{"title": "Births by sex", "rows": [{"sex": "Female", "count": 12}]}'
    scored = mod.score_response(raw, {"json": True, "equals": {"title": "Births by sex"}})
    assert scored["passed"] is True


def test_prompt_file_cases_have_ids():
    suite = json.loads(PROMPTS.read_text(encoding="utf-8"))
    ids = [case["id"] for case in suite["cases"]]
    assert ids == ["count_tables", "tables_need_review", "births_json"]


def test_cpu_ready_models_include_the_running_pair():
    mod = _load()
    models = mod.catalogue_models(
        ROOT / "deploy" / "model-server" / "models.yaml",
        device="cpu",
        only=set(),
    )
    assert [item["id"] for item in models] == [
        "gemma-2-2b-it",
        "bitnet-b1.58-2b",
        "phi-2",
        "phi-3-mini-4k-instruct",
    ]


def test_ready_models_under_5b():
    mod = _load()
    models = mod.models_under(
        ROOT / "deploy" / "model-server" / "models.yaml",
        5,
        only=set(),
    )
    assert [item["id"] for item in models] == [
        "phi-4-mini-instruct",
        "gemma-3-4b",
        "gemma-2-2b-it",
        "bitnet-b1.58-2b",
        "phi-2",
        "phi-3-mini-4k-instruct",
    ]
