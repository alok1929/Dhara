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


def ready_llm_entries() -> list[dict]:
    raw = yaml.safe_load((ROOT / "models.yaml").read_text(encoding="utf-8"))
    return [entry for entry in raw.get("llm") or [] if entry.get("status") == "ready"]


def deployable_llms() -> list[str]:
    return [entry["id"] for entry in ready_llm_entries()]


def test_catalogue_file_exists():
    assert (ROOT / "models.yaml").is_file()
    assert (ROOT / "compose.llm-only.yml").is_file()
    assert (ROOT / "gateway" / "Dockerfile").is_file()


@pytest.mark.parametrize("entry", ready_llm_entries(), ids=lambda entry: entry["id"])
def test_served_model_name_matches_folder_and_catalogue_id(entry):
    model_id = entry["id"]
    folder = ROOT / "llm" / model_id
    assert folder.is_dir(), f"ready id {model_id} has no llm/{model_id}/ folder"
    text = (folder / "Dockerfile").read_text(encoding="utf-8")
    env = dockerfile_env(folder / "Dockerfile")
    assert "vllm" in text
    assert env.get("SERVED_NAME") == model_id
    assert env.get("PORT") == "8003"
    assert int(env.get("MAX_MODEL_LEN") or "0") == int(entry["context"])
    if entry.get("device") == "cpu":
        assert "vllm-openai-cpu" in text
        assert "gpu-memory-utilization" not in text
    else:
        assert "gpu-memory-utilization" in text


def test_cpu_profile_does_not_reserve_a_gpu():
    text = (ROOT / "compose.llm-only.yml").read_text(encoding="utf-8")
    assert "profiles: [\"llm-cpu\"]" in text
    cpu_service = text.split("llm-cpu:", 1)[1]
    assert "<<: *gpu-llm" not in cpu_service
    assert "\n          - llm\n" in cpu_service


def test_env_example_model_is_a_ready_id():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    match = re.search(r"^LLM_MODEL=(\S+)\s*$", text, re.M)
    assert match, "LLM_MODEL missing from deploy/model-server/.env.example"
    assert match.group(1) in deployable_llms()
