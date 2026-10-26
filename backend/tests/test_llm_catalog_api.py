"""On-prem catalogue payload for Settings."""

from __future__ import annotations

from app.services.llm.model_catalog import build_llm_catalog_payload, load_catalogue_entries


def test_load_catalogue_has_ready_models():
    entries = load_catalogue_entries()
    ids = {e["id"] for e in entries if e.get("status") == "ready"}
    assert "phi-4-mini-instruct" in ids
    assert "gemma-3-4b" in ids


def test_build_payload_marks_active_model(monkeypatch):
    from app.core.config import clear_settings_cache

    monkeypatch.setenv("DHARA_LLM_BASE_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("DHARA_LLM_MODEL", "phi-4-mini-instruct")
    clear_settings_cache()

    payload = build_llm_catalog_payload(
        user_chat_source="on_prem",
        user_on_prem_model="phi-4-mini-instruct",
    )
    assert payload["on_prem"]["configured"] is True
    assert payload["on_prem"]["active_model"] == "phi-4-mini-instruct"
    active = [m for m in payload["models"] if m.get("active_for_chat")]
    assert len(active) == 1
    assert active[0]["id"] == "phi-4-mini-instruct"
