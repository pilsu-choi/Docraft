"""Provider contract tests; all HTTP is mocked and no live AI calls are made."""

import json
import logging

import httpx
import pytest

from backend import engine


class FakeClient:
    response = None
    requests = []

    def __init__(self, *args, **kwargs):
        del args, kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response


def install_response(monkeypatch, content, *, status_code=200, finish_reason="stop"):
    response = httpx.Response(
        status_code,
        json={
            "choices": [{
                "message": {"content": content},
                "finish_reason": finish_reason,
            }],
        },
        request=httpx.Request("POST", "https://provider.invalid/v1/chat/completions"),
    )
    FakeClient.response = response
    FakeClient.requests = []
    monkeypatch.setattr(engine.httpx, "Client", FakeClient)


def configure(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "test-provider-key")
    monkeypatch.setenv("AI_MODEL", "test/model")
    monkeypatch.delenv("AI_VLM_MODEL", raising=False)


def test_provider_uses_configured_openai_compatible_contract(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, '{"type":"object","properties":{}}')

    result = engine.generate_schema("hospital name")

    assert result["type"] == "object"
    url, request = FakeClient.requests[0]
    assert url == "https://provider.invalid/v1/chat/completions"
    assert request["headers"] == {"Authorization": "Bearer test-provider-key"}
    assert request["json"]["model"] == "test/model"


def test_vlm_model_alias_is_supported(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "test-provider-key")
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.setenv("AI_VLM_MODEL", "vision/model")
    install_response(monkeypatch, '{"type":"object","properties":{}}')

    engine.generate_schema("hospital name")

    assert FakeClient.requests[0][1]["json"]["model"] == "vision/model"


def test_local_mode_is_explicit_and_missing_provider_does_not_fallback(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    for name in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "AI_VLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(engine.ProviderConfigurationError):
        engine.generate_schema("hospital name")

    monkeypatch.setenv("AI_MODE", "local")
    result = engine.generate_schema("hospital name")

    assert "properties" in result
    assert "hospital_name" in result["properties"]


@pytest.mark.parametrize(
    "status_code,content",
    [(401, '{"error":"unauthorized"}'), (200, '{"type":"object"')],
)
def test_provider_errors_are_not_hidden_by_local_fallback(monkeypatch, status_code, content):
    configure(monkeypatch)
    install_response(monkeypatch, content, status_code=status_code)

    with pytest.raises((RuntimeError, json.JSONDecodeError)):
        engine.generate_schema("hospital name")


def test_truncated_provider_response_is_rejected_without_fallback(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, '{"type":"object"}', finish_reason="length")

    # A provider response marked as truncated must not silently become a local schema.
    with pytest.raises(RuntimeError, match="잘렸습니다"):
        engine.generate_schema("hospital name")


def test_extract_provider_errors_are_not_hidden_by_local_fallback(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, "not-json")
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}}}

    with pytest.raises(json.JSONDecodeError):
        engine.extract(schema, [{"text": "hospital: Local", "page": None, "bbox": None}])


def test_extract_grounding_block_ids_fill_page_bbox_and_source_text(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({
        "result": {"hospital": "서울병원", "code": None},
        "groundings": [
            {"path": "/hospital", "confidence": 0.9, "block": 1},
            {"path": "/code", "confidence": 0.2, "block": 7},  # out of range
        ],
    }, ensure_ascii=False))
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}, "code": {"type": "string"}}, "required": ["hospital", "code"]}
    blocks = [
        {"text": "환자명: 홍길동", "page": 1, "bbox": [0, 0, 10, 10]},
        {"text": "병원: 서울병원", "page": 2, "bbox": [1, 2, 3, 4]},
    ]

    result, groundings = engine.extract(schema, blocks)

    assert result == {"hospital": "서울병원", "code": None}
    assert groundings["hospital"] == {"confidence": 0.9, "page": 2, "bbox": [1, 2, 3, 4], "source_text": "서울병원"}
    assert groundings["code"] == {"confidence": 0.2, "page": None, "bbox": None, "source_text": None}
    body = FakeClient.requests[0][1]["json"]
    item_schema = body["response_format"]["json_schema"]["schema"]["properties"]["groundings"]["items"]
    assert set(item_schema["properties"]) == {"path", "confidence", "block"}
    assert item_schema["required"] == ["path", "confidence", "block"] and item_schema["additionalProperties"] is False
    assert "[1] 병원: 서울병원" in body["messages"][1]["content"]


def test_extract_drops_null_optional_field_and_passes_validation(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({
        "result": {"hospital": "서울병원", "code": None},
        "groundings": [
            {"path": "/hospital", "confidence": 0.9, "block": 0},
            {"path": "/code", "confidence": 0.9, "block": 0},
        ],
    }, ensure_ascii=False))
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}, "code": {"type": "string"}}, "required": ["hospital"]}
    blocks = [{"text": "병원: 서울병원", "page": 1, "bbox": [0, 0, 1, 1]}]

    result, groundings = engine.extract(schema, blocks)

    assert result == {"hospital": "서울병원"}
    assert "code" not in groundings
    assert engine.validate(result, schema, groundings) == []


def test_extract_block_list_is_truncated_on_block_boundaries(monkeypatch, caplog):
    configure(monkeypatch)
    install_response(monkeypatch, '{"result": {}, "groundings": []}')
    blocks = [{"text": "가" * 5000, "page": 1, "bbox": None} for _ in range(12)]

    with caplog.at_level(logging.WARNING, logger="backend.engine"):
        engine.extract({"type": "object", "properties": {}}, blocks)

    lines = FakeClient.requests[0][1]["json"]["messages"][1]["content"].split("([id] text):\n", 1)[1].split("\n")
    assert 0 < len(lines) < len(blocks)
    assert all(line == f"[{index}] " + "가" * 5000 for index, line in enumerate(lines))
    assert sum(len(line) for line in lines) <= 40000
    assert "truncated" in caplog.text
