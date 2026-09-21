import json

import httpx
import pytest

from backend import engine, parsers
from backend.main import app
from fastapi.testclient import TestClient


def test_ai_status_is_sanitized(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("AI_API_KEY", "must-not-leak")
    monkeypatch.setenv("AI_VLM_MODEL", "vision-model")
    response = TestClient(app).get("/api/ai/status")
    assert response.status_code == 200
    assert {key: response.json()[key] for key in ("configured", "mode", "provider", "model")} == {
        "configured": True,
        "mode": "provider",
        "provider": "provider.example",
        "model": "vision-model",
    }
    assert response.json()["ocr"] == {
        "mode": "library",
        "configured": False,
        "provider": "local/native",
        "model": None,
        "ready": False,
    }
    assert "must-not-leak" not in response.text
    assert "https://" not in response.text


def test_provider_uses_openai_compatible_structured_output(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setenv("AI_VLM_MODEL", "vision-model")
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"value":"ok"}'}}]})

    real_client = httpx.Client
    monkeypatch.setattr(engine.httpx, "Client", lambda **_kwargs: real_client(transport=httpx.MockTransport(handler)))
    schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False}
    assert engine._provider([{"role": "user", "content": "JSON"}], schema) == {"value": "ok"}
    assert seen["url"] == "https://provider.example/v1/chat/completions"
    assert seen["body"]["model"] == "vision-model"
    assert seen["body"]["response_format"]["json_schema"]["strict"] is True


def test_provider_configuration_and_http_errors_are_explicit(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(engine.ProviderConfigurationError):
        engine._provider([])

    monkeypatch.setenv("AI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("AI_API_KEY", "secret")
    monkeypatch.setenv("AI_VLM_MODEL", "vision-model")
    real_client = httpx.Client
    transport = httpx.MockTransport(lambda _request: httpx.Response(401, json={"error": {"message": "secret provider detail"}}))
    monkeypatch.setattr(engine.httpx, "Client", lambda **_kwargs: real_client(transport=transport))
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        engine._provider([])
    assert "secret provider detail" not in str(error.value)


def test_remote_paddle_layout_contract(monkeypatch, tmp_path):
    source = tmp_path / "scan.png"
    source.write_bytes(b"synthetic-image")
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "https://ocr.example")
    monkeypatch.setenv("PARSE_PROVIDER", "paddle")
    monkeypatch.setenv("PADDLEOCR_ACCESS_TOKEN", "ocr-secret")
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={"result": {"layoutParsingResults": [{"markdown": {"text": "환자명: 홍길동"}}]}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(parsers.httpx, "post", post)
    blocks = parsers.parse_image(source)
    assert seen["url"] == "https://ocr.example/layout-parsing"
    assert seen["json"]["fileType"] == 1
    assert seen["headers"] == {"Authorization": "Bearer ocr-secret"}
    assert blocks == [{"type": "text", "page": 1, "bbox": None, "text": "환자명: 홍길동", "source": "paddleocr_remote"}]
