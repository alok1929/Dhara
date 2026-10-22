"""Facade over ``app.services.llm_prompts`` (prompt text stays there)."""

from __future__ import annotations

import app.services.llm_prompts as _prompts


def __getattr__(name: str):
    return getattr(_prompts, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_prompts)))
