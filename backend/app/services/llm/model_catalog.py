"""On-prem LLM catalogue (models.yaml) and optional gateway probe."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
import yaml

from app.core.config import get_settings
from app.services.llm.profiles import normalize_openai_base_url

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _catalogue_path() -> Path:
    import os

    explicit = (os.environ.get("DHARA_MODEL_CATALOG_PATH") or "").strip()
    if explicit:
        return Path(explicit)
    for candidate in (
        _REPO_ROOT / "deploy" / "model-server" / "models.yaml",
        Path("/deploy/model-server/models.yaml"),
    ):
        if candidate.is_file():
            return candidate
    return _REPO_ROOT / "deploy" / "model-server" / "models.yaml"


def load_catalogue_entries() -> list[dict[str, Any]]:
    path = _catalogue_path()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        log.warning("model catalogue missing (%s): %s", path, exc)
        return []
    except yaml.YAMLError as exc:
        log.warning("model catalogue invalid (%s): %s", path, exc)
        return []
    if not isinstance(raw, dict):
        return []
    out: list[dict[str, Any]] = []
    for entry in raw.get("llm") or []:
        if isinstance(entry, dict) and entry.get("id"):
            out.append(dict(entry))
    return out


def _gateway_models_sync(base_url: str, timeout: float = 2.5) -> tuple[list[str], bool]:
    if not base_url.strip():
        return [], False
    root = normalize_openai_base_url(base_url.rstrip("/"))
    if root.endswith("/v1"):
        root = root[:-3]
    url = urljoin(root + "/", "v1/models")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001
        log.debug("gateway models probe failed (%s): %s", url, exc)
        return [], False
    ids: list[str] = []
    for item in payload.get("data") or []:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids, True


def build_llm_catalog_payload(
    *,
    user_chat_source: str | None = None,
    user_on_prem_model: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    base = settings.dhara_llm_base_url.strip()
    env_model = settings.dhara_llm_model.strip()
    on_prem = bool(base and env_model and settings.dhara_llm_provider != "mock")
    source = (user_chat_source or "cloud").strip().lower()
    active = (
        (user_on_prem_model or env_model).strip()
        if source == "on_prem"
        else None
    )

    gateway_ids, reachable = _gateway_models_sync(base) if base else ([], False)
    gateway_set = set(gateway_ids)

    models: list[dict[str, Any]] = []
    for entry in load_catalogue_entries():
        model_id = str(entry.get("id") or "")
        status = str(entry.get("status") or "")
        models.append(
            {
                "id": model_id,
                "name": entry.get("name") or model_id,
                "status": status,
                "parameters": entry.get("parameters"),
                "huggingface": entry.get("huggingface"),
                "deployable": status == "ready",
                "on_gateway": model_id in gateway_set,
                "active_for_chat": on_prem
                and source == "on_prem"
                and model_id == active,
                "local_vllm": status == "ready",
            }
        )

    # Gateway may expose ids not listed in yaml (e.g. OpenAI proxy route).
    known = {m["id"] for m in models}
    for gid in gateway_ids:
        if gid not in known:
            models.append(
                {
                    "id": gid,
                    "name": gid,
                    "status": "gateway",
                    "deployable": True,
                    "on_gateway": True,
                    "active_for_chat": on_prem
                    and source == "on_prem"
                    and gid == active,
                    "local_vllm": False,
                }
            )

    return {
        "on_prem": {
            "configured": on_prem,
            "base_url": base or None,
            "active_model": active if source == "on_prem" else None,
            "env_default_model": env_model or None,
        },
        "chat_source": source,
        "on_prem_model": user_on_prem_model or env_model or None,
        "gateway": {
            "reachable": reachable,
            "model_ids": gateway_ids,
        },
        "models": models,
        "catalogue_path": str(_catalogue_path()),
    }
