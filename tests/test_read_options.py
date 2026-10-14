"""`/api/read-options` contract tests; the provider is mocked and no live AI calls are made."""
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import doctypes, engine, verify
from backend.main import app
from test_ai_provider import FakeClient, configure, install_response

client = TestClient(app)
READING = {"section": True, "임상적추정": {"text": "임상적추정", "mark": "checked"}, "최종진단": {"text": "최종진단", "mark": "empty"}}


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "crop.png"
    Image.new("RGB", (8, 8), "white").save(path)
    return path.read_bytes()


def post(png, doc_type="진단서", name="crop.png"):
    return client.post("/api/read-options", files={"image": (name, png, "image/png")}, data={"doc_type": doc_type})


def stub_provider(monkeypatch, replies):
    calls = []

    def provider(messages, **kwargs):
        calls.append(kwargs)
        reply = replies[len(calls) - 1]
        if isinstance(reply, Exception): raise reply
        return reply

    monkeypatch.setattr(engine, "_provider", provider)
    return calls


@pytest.mark.parametrize("doc_type", sorted(doctypes.EXCLUSIVE_CHECKBOX_GROUPS))
def test_slots_come_from_the_doc_type_group(monkeypatch, png, doc_type):
    calls = stub_provider(monkeypatch, [READING])

    response = post(png, doc_type)

    assert response.status_code == 200
    body = response.json()
    assert body["doc_type"] == doc_type and body["options"] == READING and "elapsed_ms" in body and "diagnostics" in body
    schema = calls[0]["json_schema"]
    assert tuple(k for k in schema["properties"] if k != "section") == doctypes.EXCLUSIVE_CHECKBOX_GROUPS[doc_type]
    assert schema["properties"]["최종진단"]["properties"]["mark"]["enum"] == list(verify.OPTION_MARKS)
    assert calls[0]["max_tokens"] == 300


def test_alias_resolves_to_the_group(monkeypatch, png):
    stub_provider(monkeypatch, [READING])

    assert post(png, "입원확인서").json()["doc_type"] == "입퇴원확인서"


def test_provider_body_turns_reasoning_off_with_json_schema_and_option_model(monkeypatch, png):
    configure(monkeypatch)
    monkeypatch.setenv("AI_VLM_MODEL", "main/model")
    monkeypatch.setenv("OPTION_VLM_MODEL", "option/model")
    install_response(monkeypatch, json.dumps(READING))

    assert post(png).status_code == 200

    body = FakeClient.requests[0][1]["json"]
    assert body["model"] == "option/model" and body["max_tokens"] == 300
    assert body["response_format"]["type"] == "json_schema"
    assert body["reasoning"] == {"enabled": False} and body["chat_template_kwargs"] == {"enable_thinking": False}


def test_option_model_defaults_to_the_main_model(monkeypatch, png):
    configure(monkeypatch)
    monkeypatch.setenv("AI_VLM_MODEL", "main/model")
    monkeypatch.delenv("OPTION_VLM_MODEL", raising=False)
    install_response(monkeypatch, json.dumps(READING))

    post(png)

    assert FakeClient.requests[0][1]["json"]["model"] == "main/model"


def test_invalid_json_is_retried_once(monkeypatch, png):
    calls = stub_provider(monkeypatch, [json.JSONDecodeError("bad", "", 0), READING])

    assert post(png).status_code == 200 and len(calls) == 2


def test_invalid_json_twice_is_502(monkeypatch, png):
    calls = stub_provider(monkeypatch, [json.JSONDecodeError("bad", "", 0)] * 2)

    assert post(png).status_code == 502 and len(calls) == 2


def test_provider_failure_is_502_without_retry(monkeypatch, png):
    calls = stub_provider(monkeypatch, [RuntimeError("AI provider 요청 실패 (HTTP 500)")])

    response = post(png)

    assert response.status_code == 502 and len(calls) == 1


@pytest.mark.parametrize("doc_type", ["진료비영수증", "세부내역서", "약제비영수증", "없는유형"])
def test_doc_type_without_option_group_is_422(monkeypatch, png, doc_type):
    calls = stub_provider(monkeypatch, [])

    assert post(png, doc_type).status_code == 422 and not calls


def test_multipage_input_is_422(monkeypatch, tmp_path):
    calls = stub_provider(monkeypatch, [])
    path = tmp_path / "two.tiff"
    Image.new("RGB", (8, 8), "white").save(path, save_all=True, append_images=[Image.new("RGB", (8, 8), "black")])

    assert post(path.read_bytes(), name="two.tiff").status_code == 422 and not calls
