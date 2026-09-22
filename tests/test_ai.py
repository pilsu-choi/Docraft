import base64
import json

import fitz
import httpx
import pytest

from backend import doctypes, engine, parsers
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


def test_remote_paddle_label_mapping_and_html_table_rows(monkeypatch, tmp_path):
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"synthetic-pdf")
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "http://ocr.local:8080")
    pruned = {"parsing_res_list": [
        {"block_label": "doc_title", "block_content": "제목"},
        {"block_label": "paragraph_title", "block_content": "소제목"},
        {"block_label": "image", "block_content": "그림"},
        {"block_label": "chart", "block_content": "차트"},
        {"block_label": "header", "block_content": "머리말"},
        {"block_label": "footnote", "block_content": "각주"},
        {"block_label": "formula", "block_content": "E=mc^2"},
        {"block_label": "abstract", "block_content": "본문"},
        {"block_label": "table", "block_content": "<table><tr><td>A</td><td>B</td></tr></table>"},
    ]}
    response = {"result": {"layoutParsingResults": [{"prunedResult": pruned}]}}
    monkeypatch.setattr(parsers.httpx, "post", lambda url, **_: httpx.Response(200, json=response, request=httpx.Request("POST", url)))
    blocks = parsers._remote_paddle(source, 0)
    assert {b["label"]: b["type"] for b in blocks} == {
        "doc_title": "heading", "paragraph_title": "heading", "image": "figure", "chart": "figure",
        "header": "marginalia", "footnote": "marginalia", "formula": "formula", "abstract": "text", "table": "table",
    }
    table = next(b for b in blocks if b["label"] == "table")
    assert table["rows"] == [["A", "B"]]


def test_remote_paddle_page_range_sends_only_selected_pages_and_maps_back(monkeypatch, tmp_path):
    source = tmp_path / "scan.pdf"
    doc = fitz.open()
    for text in ["one", "two", "three", "four"]:
        doc.new_page().insert_text((72, 72), text)
    doc.save(source)
    doc.close()
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "https://ocr.example")
    seen = {}

    def post(url, **kwargs):
        sent = fitz.open(stream=base64.b64decode(kwargs["json"]["file"]), filetype="pdf")
        seen["page_count"] = len(sent)
        sent.close()
        results = [{"markdown": {"text": f"page-{i}"}} for i in range(seen["page_count"])]
        return httpx.Response(200, json={"result": {"layoutParsingResults": results}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(parsers.httpx, "post", post)
    blocks = parsers.parse_pdf(source, provider="paddle", pages="1,3")
    assert seen["page_count"] == 2
    assert [b["page"] for b in blocks] == [1, 3]


def _extract_messages(monkeypatch, schema, blocks):
    """extract()가 provider에 보낸 첫 호출의 (system, user text)."""
    sent = []
    monkeypatch.setattr(engine, "ai_settings", lambda: {"mode": "provider", "chunk_chars": 40000})
    monkeypatch.setattr(engine, "_provider", lambda messages, timeout=90: sent.append(messages) or {})
    engine.extract(schema, blocks)
    return sent[0][0]["content"], engine._message_text(sent[0][1]["content"])


def test_extract_grounds_table_rows_in_the_printed_document(monkeypatch):
    system, user = _extract_messages(monkeypatch, doctypes.schema("진료비영수증"),
                                     [{"page": 1, "text": "<table><tr><td>항목</td></tr></table>"}])
    assert "rows the document prints, in printed order" in system
    assert "never add a row the document does not print" in system
    table = json.loads(user.split("Schema:\n", 1)[1].split("\n\nSource blocks:", 1)[0])["properties"]["항목내역"]
    assert doctypes.GROUND_HINT in table["description"]
    assert "표준 목록에 없는 이름" in table["items"]["properties"]["항목"]["description"]


def test_extract_leaves_a_schema_without_tables_free_of_the_table_note(monkeypatch):
    system, _user = _extract_messages(monkeypatch, {"type": "object", "properties": {"제목": {"type": ["string", "null"]}},
                                                    "required": ["제목"]}, [{"page": 1, "text": "제목: 계약서"}])
    assert engine.TABLE_NOTE not in system


def test_extract_sends_table_blocks_as_rows_and_columns(monkeypatch):
    """표 블록은 행·열 구조가 남은 HTML 그대로 넘어간다(줄글로 뭉개지 않는다)."""
    html_table = "<table><tr><td>항목</td><td>코드</td></tr><tr><td>의학료</td><td>AA154</td></tr></table>"
    _system, user = _extract_messages(monkeypatch, {"type": "object", "properties": {}}, [{"page": 1, "text": html_table}])
    assert html_table in user.split("Source blocks:\n", 1)[1]


def test_detail_code_columns_route_a_single_printed_code_column_to_edi():
    columns = doctypes.schema("세부내역서")["properties"]["항목내역"]["items"]["properties"]
    assert "'청구코드'·'표준코드'·'수가코드'" in columns["EDI코드"]["description"]
    assert "코드 열이 하나뿐이면 그 값은 EDI코드에 적고 여기는 null" in columns["원내코드"]["description"]
    assert "표준 수가 명칭으로 바꾸지" in columns["EDI명칭"]["description"]
