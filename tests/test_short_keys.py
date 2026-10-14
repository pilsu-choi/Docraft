"""SHORT_KEYS: 표 없는 필드 읽기(_read_chunk)·금액산정 읽기(_read_summary)의 짧은 키 대응. 가짜 provider만 쓴다."""

import json

import pytest

from backend import engine

SCHEMA = {"type": "object", "required": ["병원명", "금액"], "properties": {
    "병원명": {"type": "string", "description": "기관 이름"}, "금액": {"type": "string"}, "비고": {"type": "string", "description": "메모"}}}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("SHORT_KEYS", "true")


def _fake(seen, reply):
    return lambda messages, **kw: seen.append((messages[-1]["content"], kw)) or reply


def test_short_schema_orders_keys_and_moves_descriptions_to_legend(on):
    slim, legend, keys = engine._short_schema(SCHEMA)
    assert keys == {"a": "병원명", "b": "금액", "c": "비고"}
    assert list(slim["properties"]) == ["a", "b", "c"] and "required" not in slim
    assert "description" not in json.dumps(slim) and "기관 이름" not in json.dumps(slim, ensure_ascii=False)
    assert legend.splitlines() == ["a = 병원명: 기관 이름", "b = 금액", "c = 비고: 메모"]


def test_short_schema_skips_tables_over_26_fields_and_off_flag(on, monkeypatch):
    table = {"properties": {"x": {"type": "string"}, "표": {"type": "array"}}}
    wide = {"properties": {f"k{i}": {"type": "string"} for i in range(27)}}
    assert engine._short_schema(table) is None and engine._short_schema(wide) is None
    monkeypatch.setenv("SHORT_KEYS", "false")
    assert engine._short_schema(SCHEMA) is None


def test_long_keys_drops_unknown_short_keys_and_fills_missing_with_none():
    assert engine._long_keys({"a": "X", "z": "?", "c": ""}, {"a": "병원명", "b": "금액", "c": "비고"}) == {"병원명": "X", "금액": None, "비고": ""}


def test_long_keys_keeps_values_the_model_wrote_under_original_keys():
    assert engine._long_keys({"병원명": "X", "b": "1"}, {"a": "병원명", "b": "금액", "c": "비고"}) == {"병원명": "X", "금액": "1", "비고": None}


def test_short_keys_on_by_default(monkeypatch):
    monkeypatch.delenv("SHORT_KEYS", raising=False)
    assert engine._short_schema(SCHEMA) is not None


def test_read_summary_asks_short_keys_and_maps_back(on, monkeypatch):
    seen = []
    monkeypatch.setattr(engine, "_provider", _fake(seen, {"a": "서울", "b": "", "q": 1}))
    assert engine._read_summary(SCHEMA, []) == {"병원명": "서울", "금액": None, "비고": None}
    assert "a = 병원명: 기관 이름" in seen[0][0]


def test_read_summary_unchanged_when_off(monkeypatch):
    monkeypatch.setenv("SHORT_KEYS", "false")
    monkeypatch.setattr(engine, "_provider", _fake([], {"병원명": "서울", "금액": ""}))
    assert engine._read_summary(SCHEMA, []) == {"병원명": "서울", "금액": None, "비고": None}


def test_read_chunk_maps_back_and_json_schema_uses_short_keys(on, monkeypatch):
    monkeypatch.setenv("COMPACT_REPLY", "true")
    seen = []
    monkeypatch.setattr(engine, "_provider", _fake(seen, {"a": "서울", "b": "100"}))
    chunk = [{"page": 1, "text": "서울 100"}]
    assert engine._read_chunk(SCHEMA, chunk, 0, 1, None, 10000) == {"병원명": "서울", "금액": "100", "비고": None}
    assert list(seen[0][1]["json_schema"]["properties"]) == ["a", "b", "c"]
