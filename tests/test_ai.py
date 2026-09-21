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


def test_provider_uses_openai_compatible_json_object_output(monkeypatch):
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
    assert engine._provider([{"role": "user", "content": "JSON"}]) == {"value": "ok"}
    assert seen["url"] == "https://provider.example/v1/chat/completions"
    assert seen["body"]["model"] == "vision-model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "provider" not in seen["body"]


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


def test_remote_paddle_region_bboxes(monkeypatch, tmp_path):
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"synthetic-pdf")
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "http://ocr.local:8080")
    monkeypatch.setenv("PARSE_PROVIDER", "paddle")
    pruned = {"width": 1000, "height": 1400, "parsing_res_list": [
        {"block_label": "text", "block_content": " 환자명: 홍길동 ", "block_bbox": [10, 20, 300, 60]},
        {"block_label": "table", "block_content": "<table></table>", "block_bbox": [10, 80, 900, 400]},
        {"block_label": "image", "block_content": "", "block_bbox": [0, 0, 1, 1]},
    ]}
    response = {"result": {"layoutParsingResults": [{"prunedResult": pruned, "markdown": {"text": "ignored"}}]}}
    monkeypatch.setattr(parsers.httpx, "post", lambda url, **_: httpx.Response(200, json=response, request=httpx.Request("POST", url)))
    blocks = parsers._remote_paddle(source, 0)
    assert [(b["type"], b["text"], b["bbox"], b["page_size"]) for b in blocks] == [
        ("text", "환자명: 홍길동", [10, 20, 300, 60], [1000, 1400]),
        ("table", "<table></table>", [10, 80, 900, 400], [1000, 1400]),
    ]
