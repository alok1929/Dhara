"""Catalogue id, folder name, and vLLM SERVED_NAME must be the same string."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2] / "deploy" / "model-server"


def dockerfile_env(path: Path) -> dict[str, str]:
    text = re.sub(r"\\\r?\n", " ", path.read_text(encoding="utf-8"))
    env: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip().startswith("ENV "):
            continue
        for key, value in re.findall(r"(\w+)=(\"[^\"]*\"|\S+)", line[4:]):
            env[key] = value.strip('"')
    return env


def deployable_llms() -> list[str]:
    raw = yaml.safe_load((ROOT / "models.yaml").read_text(encoding="utf-8"))
    return [entry["id"] for entry in raw.get("llm") or [] if entry.get("status") == "ready"]


def test_catalogue_file_exists():
    assert (ROOT / "models.yaml").is_file()
    assert (ROOT / "compose.llm-only.yml").is_file()
    assert (ROOT / "gateway" / "Dockerfile").is_file()


@pytest.mark.parametrize("model_id", deployable_llms())
def test_served_model_name_matches_folder_and_catalogue_id(model_id):
    folder = ROOT / "llm" / model_id
    assert folder.is_dir(), f"ready id {model_id} has no llm/{model_id}/ folder"
    env = dockerfile_env(folder / "Dockerfile")
    assert "vllm" in (folder / "Dockerfile").read_text(encoding="utf-8")
    assert env.get("SERVED_NAME") == model_id
    assert env.get("PORT") == "8003"
    assert int(env.get("MAX_MODEL_LEN") or "0") >= 16384


def test_env_example_model_is_a_ready_id():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    match = re.search(r"^LLM_MODEL=(\S+)\s*$", text, re.M)
    assert match, "LLM_MODEL missing from deploy/model-server/.env.example"
    assert match.group(1) in deployable_llms()
