"""Static chat profiles. Settings does not pick Gemma vs OpenAI in v1."""

from __future__ import annotations

from dataclasses import dataclass


def normalize_openai_base_url(raw: str) -> str:
    """Accept ``http://host:8100`` or ``http://host:8100/v1``; always return ``.../v1``."""
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise ValueError("DHARA_LLM_BASE_URL is empty")
    if url.endswith("/v1"):
        return url
    return f"{url}/v1"


@dataclass(frozen=True)
class LlmProfile:
    """One resolved chat target.

    ``kind`` is ``mock``, ``on-prem`` (gateway → vLLM), or ``cloud`` (Settings key).
    ``provider`` is ``mock``, ``openai`` (including vLLM and MEITY OpenAI-compat),
    or ``anthropic`` (cloud only; never used when on-prem env is set).
    """

    kind: str
    provider: str
    model: str
    api_key: str
    base_url: str | None = None
