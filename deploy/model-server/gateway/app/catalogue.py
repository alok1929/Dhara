"""The LLM catalogue, read from models.yaml and served at /models."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("gateway")


def _find_catalogue() -> Path:
    """models.yaml sits beside this module in the image, or at the deploy root."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "models.yaml", here.parent.parent / "models.yaml"):
        if candidate.is_file():
            return candidate
    return here / "models.yaml"


CATALOGUE_PATH = _find_catalogue()

KINDS = ("llm",)


def load(path: Path | None = None) -> list[dict[str, Any]]:
    """Flatten the ``llm`` list. A missing catalogue does not stop routing."""
    src = path or CATALOGUE_PATH
    try:
        raw = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning("catalogue unavailable (%s): %s", src, exc)
        return []

    if not isinstance(raw, dict):
        log.warning(
            "catalogue at %s is %s, not a mapping",
            src,
            type(raw).__name__,
        )
        return []

    models: list[dict[str, Any]] = []
    for kind in KINDS:
        for entry in raw.get(kind) or []:
            models.append({"kind": kind, **entry})
    return models
