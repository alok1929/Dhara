"""Resolve which chat server to call.

Precedence (API and workers, same process env):

1. ``DHARA_LLM_PROVIDER=mock`` — no HTTP
2. ``DHARA_LLM_BASE_URL`` and ``DHARA_LLM_MODEL`` — gateway → vLLM; user key ignored for chat
3. Settings key — OpenAI-compat (no per-user base URL in v1) or Anthropic
4. none — callers skip LLM / use heuristics
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.credentials import service as credentials_service
from app.services.llm.base_llm import LlmClient
from app.services.llm.profiles import LlmProfile, normalize_openai_base_url
from app.services.llm_prompts import ANTHROPIC_MODEL, OPENAI_MODEL


def get_llm_for_user(session: Session, user_email: str) -> Optional[LlmClient]:
    """Resolve chat for a signed-in user. On-prem env ignores the stored key."""
    decided = _from_env()
    if decided is not None:
        return decided
    key, provider = credentials_service.resolve_for_user(session, user_email)
    return _from_user_key(key, provider)


def get_llm_for_request(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> Optional[LlmClient]:
    """Same precedence as :func:`get_llm_for_user`, using an already-loaded key."""
    decided = _from_env()
    if decided is not None:
        return decided
    key = (api_key or "").strip() or None
    prov = (provider or "").strip().lower() or None
    return _from_user_key(key, prov)


def chat_ready(api_key: Optional[str] = None, provider: Optional[str] = None) -> bool:
    """True when a non-mock chat profile is configured (on-prem or a user key)."""
    client = get_llm_for_request(api_key, provider)
    return client is not None and not client.is_mock


def live_openai_chat(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> Optional[LlmClient]:
    """OpenAI-compatible client, or None for mock / Anthropic-only / unconfigured.

    On-prem always returns this client (vLLM), even if the user key is ``sk-ant-``.
    """
    client = get_llm_for_request(api_key, provider)
    if client is None or client.is_mock or client.provider != "openai":
        return None
    return client


def _from_env() -> Optional[LlmClient]:
    settings = get_settings()
    if settings.dhara_llm_provider == "mock":
        return _mock_client()
    if settings.dhara_llm_base_url and settings.dhara_llm_model:
        return LlmClient(
            LlmProfile(
                kind="on-prem",
                provider="openai",
                model=settings.dhara_llm_model,
                api_key=settings.dhara_llm_api_key or "local",
                base_url=normalize_openai_base_url(settings.dhara_llm_base_url),
            )
        )
    return None


def _from_user_key(key: Optional[str], provider: Optional[str]) -> Optional[LlmClient]:
    if provider == "mock" or (key and key.startswith("mock")):
        return _mock_client()
    if not key:
        return None
    if provider == "anthropic" or (
        provider not in ("openai", "self-hosted") and key.startswith("sk-ant-")
    ):
        return LlmClient(
            LlmProfile(
                kind="cloud",
                provider="anthropic",
                model=ANTHROPIC_MODEL,
                api_key=key,
                base_url=None,
            )
        )
    # openai, self-hosted (MEITY), or unknown: OpenAI SDK, default host, no stored base_url.
    return LlmClient(
        LlmProfile(
            kind="cloud",
            provider="openai",
            model=OPENAI_MODEL,
            api_key=key,
            base_url=None,
        )
    )


def _mock_client() -> LlmClient:
    return LlmClient(
        LlmProfile(
            kind="mock",
            provider="mock",
            model="mock",
            api_key="mock-key",
            base_url=None,
        )
    )
