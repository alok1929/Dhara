"""Gateway configuration for the Dhara LLM slot.

The slot is deployed when LLM_MODEL is set. The upstream URL defaults to the
Compose service name ``llm`` on port 8003.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _clean(name: str) -> str:
    return (os.getenv(name) or "").strip().rstrip("/")


def _default_llm_upstream(model: str) -> str:
    """Compose uses ``http://llm:8003``; host-run gateway uses localhost."""
    if not model:
        return ""
    explicit = _clean("LLM_UPSTREAM")
    if explicit:
        return explicit
    if Path("/.dockerenv").exists():
        return "http://llm:8003"
    return "http://127.0.0.1:8003"


@dataclass(frozen=True)
class Upstream:
    url: str
    model: str

    @property
    def enabled(self) -> bool:
        return bool(self.model and self.url)


@dataclass(frozen=True)
class CloudRoute:
    """OpenAI chat proxied by this gateway. The key stays here, not in callers."""

    url: str
    model: str
    api_key: str

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.model and self.api_key)


def _extra_upstreams() -> list[Upstream]:
    """Comma-separated ``id=url`` pairs, for a second vLLM beside the main slot."""
    found: list[Upstream] = []
    for part in (os.getenv("LLM_EXTRA_UPSTREAMS") or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        model, url = part.split("=", 1)
        model = model.strip()
        url = url.strip().rstrip("/")
        if model and url:
            found.append(Upstream(url, model))
    return found


@dataclass(frozen=True)
class Settings:
    llm: Upstream
    locals: tuple[Upstream, ...]
    openai: CloudRoute

    @classmethod
    def from_env(cls) -> Settings:
        model = _clean("LLM_MODEL")
        url = _default_llm_upstream(model)
        primary = Upstream(url, model)
        locals_list = [primary] if primary.enabled else []
        seen = {primary.model} if primary.enabled else set()
        for extra in _extra_upstreams():
            if extra.model in seen:
                continue
            locals_list.append(extra)
            seen.add(extra.model)
        key = _clean("OPENAI_API_KEY")
        cloud_model = _clean("OPENAI_MODEL") or ("gpt-4o-mini" if key else "")
        cloud_url = _clean("OPENAI_BASE_URL") or ("https://api.openai.com" if key else "")
        return cls(primary, tuple(locals_list), CloudRoute(cloud_url, cloud_model, key))


settings = Settings.from_env()
