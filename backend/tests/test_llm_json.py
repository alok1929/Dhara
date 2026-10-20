"""Tests for Preview chat / AI-search LLM JSON recovery."""
from app.services.extraction.pdf.llm_json import loads_llm_json


def test_loads_valid_json():
    data = loads_llm_json(
        '{"reply": "ok", "action": "remove", "table_ids": ["a", "b"]}'
    )
    assert data == {
        "reply": "ok",
        "action": "remove",
        "table_ids": ["a", "b"],
    }


def test_loads_truncated_table_ids_array():
    raw = """{
  "reply": "I will remove all tables related to area as requested.",
  "action": "remove",
  "table_ids": [
    "DDI_DES_DEL_VS_MEDIATOUPL_P9",
    "DDI_DES_DEL_VS_MEDIATOUPL_P10",
    "DDI_DES_DEL_VS_MEDIATOUPL_P11"
"""
    data = loads_llm_json(raw)
    assert data is not None
    assert data["action"] == "remove"
    assert "area" in data["reply"]
    assert data["table_ids"] == [
        "DDI_DES_DEL_VS_MEDIATOUPL_P9",
        "DDI_DES_DEL_VS_MEDIATOUPL_P10",
        "DDI_DES_DEL_VS_MEDIATOUPL_P11",
    ]


def test_loads_markdown_fenced_json():
    raw = """```json
{"reply": "Found 1 table.", "action": "find", "table_ids": ["t1"]}
```"""
    data = loads_llm_json(raw)
    assert data["action"] == "find"
    assert data["table_ids"] == ["t1"]


def test_loads_empty_returns_none():
    assert loads_llm_json("") is None
    assert loads_llm_json("not json at all") is None
