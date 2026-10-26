"""Resolve which chat server to call.

Precedence (per signed-in user when routing is bound or loaded from DB):

1. ``DHARA_LLM_PROVIDER=mock`` — no HTTP
2. User chose **on-prem** and ``DHARA_LLM_*`` is set — gateway → vLLM
3. User chose **cloud** (default) — Settings key → OpenAI / Anthropic
4. none — callers skip LLM / use heuristics

Without user routing (benchmark scripts, ``get_llm_for_request`` only): on-prem
env still wins when configured, same as before.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.credentials import service as credentials_service
from app.services.llm.base_llm import LlmClient
from app.services.llm.profiles import LlmProfile, normalize_openai_base_url
from app.services.llm.routing import (
    CHAT_SOURCE_CLOUD,
    CHAT_SOURCE_ON_PREM,
    LlmChatRouting,
    current_llm_routing,
)
from app.services.llm_prompts import ANTHROPIC_MODEL, OPENAI_MODEL


def get_llm_for_user(session: Session, user_email: str) -> Optional[LlmClient]:
    """Resolve chat for a signed-in user (DB routing + stored key)."""
    from app.db.repositories import llm_keys as llm_repo

    routing = llm_repo.get_routing(session, user_email)
    decided = _from_env(routing=routing)
    if decided is not None:
        return decided
    key, provider = credentials_service.resolve_for_user(session, user_email)
    return _from_user_key(key, provider)


def get_llm_for_request(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    *,
    routing: LlmChatRouting | None = None,
) -> Optional[LlmClient]:
    """Same as :func:`get_llm_for_user`, using an already-loaded key + optional routing."""
    decided = _from_env(routing=routing or current_llm_routing())
    if decided is not None:
        return decided
    key = (api_key or "").strip() or None
    prov = (provider or "").strip().lower() or None
    return _from_user_key(key, prov)


def chat_ready(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    *,
    routing: LlmChatRouting | None = None,
) -> bool:
    """True when a non-mock chat profile is configured."""
    client = get_llm_for_request(api_key, provider, routing=routing)
    return client is not None and not client.is_mock


def chat_ready_for_user(session: Session, user_email: str) -> bool:
    client = get_llm_for_user(session, user_email)
    return client is not None and not client.is_mock


def live_openai_chat(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    *,
    routing: LlmChatRouting | None = None,
) -> Optional[LlmClient]:
    """OpenAI-compatible client, or None for mock / Anthropic-only / unconfigured."""
    client = get_llm_for_request(api_key, provider, routing=routing)
    if client is None or client.is_mock or client.provider != "openai":
        return None
    return client


def _use_on_prem_env(routing: LlmChatRouting | None) -> bool:
    if routing is None:
        return True
    return routing.chat_source == CHAT_SOURCE_ON_PREM


def _from_env(*, routing: LlmChatRouting | None) -> Optional[LlmClient]:
    settings = get_settings()
    if settings.dhara_llm_provider == "mock":
        return _mock_client()
    if routing is not None and routing.chat_source == CHAT_SOURCE_CLOUD:
        return None
    if not _use_on_prem_env(routing):
        return None
    if settings.dhara_llm_base_url and settings.dhara_llm_model:
        model = (routing.on_prem_model if routing else None) or settings.dhara_llm_model
        return LlmClient(
            LlmProfile(
                kind="on-prem",
                provider="openai",
                model=model.strip(),
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
