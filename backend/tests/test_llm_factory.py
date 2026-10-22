"""Chat factory precedence: mock → on-prem env → Settings key → none."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def fresh_settings(monkeypatch):
    monkeypatch.delenv("DHARA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DHARA_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DHARA_LLM_MODEL", raising=False)
    monkeypatch.delenv("DHARA_LLM_API_KEY", raising=False)
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()


def test_mock_beats_onprem_and_user_key(fresh_settings, monkeypatch):
    monkeypatch.setenv("DHARA_LLM_PROVIDER", "mock")
    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://model-gateway:8100")
    monkeypatch.setenv("DHARA_LLM_MODEL", "gemma-3-4b")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    from app.services.llm.factory import get_llm_for_request

    client = get_llm_for_request("sk-ant-real", provider="anthropic")
    assert client is not None
    assert client.is_mock
    assert client.provider == "mock"


def test_onprem_ignores_user_key_and_normalizes_v1(fresh_settings, monkeypatch):
    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://model-gateway:8100/")
    monkeypatch.setenv("DHARA_LLM_MODEL", "gemma-3-4b")
    monkeypatch.setenv("DHARA_LLM_API_KEY", "gateway-token")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    from app.services.llm.factory import get_llm_for_request, live_openai_chat

    client = live_openai_chat("sk-ant-should-not-win", provider="anthropic")
    assert client is not None
    assert client.is_on_prem
    assert client.provider == "openai"
    assert client.model == "gemma-3-4b"
    assert client.base_url == "http://model-gateway:8100/v1"
    assert client.api_key == "gateway-token"
    assert get_llm_for_request("sk-live").kind == "on-prem"


def test_base_url_already_v1_is_not_doubled(fresh_settings, monkeypatch):
    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://model-gateway:8100/v1")
    monkeypatch.setenv("DHARA_LLM_MODEL", "gemma-3-4b")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    from app.services.llm.factory import live_openai_chat

    client = live_openai_chat(None)
    assert client is not None
    assert client.base_url == "http://model-gateway:8100/v1"
    assert client.api_key == "local"


def test_partial_onprem_env_does_not_win(fresh_settings, monkeypatch):
    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://model-gateway:8100")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    from app.services.llm.factory import get_llm_for_request

    assert get_llm_for_request(None) is None
    client = get_llm_for_request("sk-user")
    assert client is not None
    assert client.kind == "cloud"
    assert client.base_url is None
    assert client.model == "gpt-4o-mini"


def test_cloud_anthropic_when_no_onprem(fresh_settings):
    from app.services.llm.factory import get_llm_for_request, live_openai_chat

    client = get_llm_for_request("sk-ant-abc")
    assert client is not None
    assert client.provider == "anthropic"
    assert client.kind == "cloud"
    assert live_openai_chat("sk-ant-abc") is None


def test_get_llm_for_user_onprem_skips_db(fresh_settings, monkeypatch):
    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://gw:8100")
    monkeypatch.setenv("DHARA_LLM_MODEL", "gemma-3-4b")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    from app.services.llm import factory

    def _boom(*_a, **_k):
        raise AssertionError("user key must not be read when on-prem env is set")

    monkeypatch.setattr(factory.credentials_service, "resolve_for_user", _boom)
    client = factory.get_llm_for_user(MagicMock(), "u@example.com")
    assert client is not None and client.is_on_prem


def test_json_salvage_logs_onprem_profile(fresh_settings, monkeypatch, caplog):
    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://gw:8100")
    monkeypatch.setenv("DHARA_LLM_MODEL", "gemma-3-4b")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    import logging

    from app.services.llm.factory import live_openai_chat

    client = live_openai_chat(None)
    assert client is not None
    with caplog.at_level(logging.WARNING):
        parsed = client.loads_json("```json\n{\"ok\": true}\n```", context="pdf_validate_page")
    assert parsed == {"ok": True}
    assert any("profile=on-prem" in rec.message and "pdf_validate_page" in rec.message for rec in caplog.records)


def test_completion_text_uses_reasoning_when_content_empty():
    from app.services.llm.base_llm import LlmClient
    from app.services.llm.profiles import LlmProfile

    client = LlmClient(
        LlmProfile(kind="on-prem", provider="openai", model="qwen", api_key="local", base_url="http://x/v1")
    )
    message = MagicMock()
    message.content = ""
    message.reasoning_content = "{\"tables\": []}"
    message.reasoning = None
    assert client.completion_text(message) == "{\"tables\": []}"
