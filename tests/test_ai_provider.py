"""Provider contract tests; all HTTP is mocked and no live AI calls are made."""

import json
import logging

import httpx
import pytest

from backend import engine


class FakeClient:
    response = None
    responses = None
    requests = []

    def __init__(self, *args, **kwargs):
        del args, kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if self.responses is not None:
            return self.responses[len(self.requests) - 1]
        return self.response


def _response(content, status_code, finish_reason):
    return httpx.Response(
        status_code,
        json={"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]},
        request=httpx.Request("POST", "https://provider.invalid/v1/chat/completions"),
    )


def install_response(monkeypatch, content, *, status_code=200, finish_reason="stop"):
    FakeClient.response = _response(content, status_code, finish_reason)
    FakeClient.responses = None
    FakeClient.requests = []
    monkeypatch.setattr(engine.httpx, "Client", FakeClient)


def install_responses(monkeypatch, contents, *, status_code=200, finish_reason="stop"):
    """One JSON response body per expected provider call, returned in call order."""
    FakeClient.responses = [_response(content, status_code, finish_reason) for content in contents]
    FakeClient.response = None
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


def test_extract_grounds_leaves_by_normalized_text_match(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"hospital": "전액 본인부담", "amount": 12380, "count": 1.0}, ensure_ascii=False))
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}, "amount": {"type": "number"}, "count": {"type": "number"}}, "required": ["hospital", "amount", "count"]}
    blocks = [
        {"text": "환자명: 홍길동", "page": 1, "bbox": [0, 0, 10, 10]},
        {"text": "<td>전액\n본인부담</td><td>12,380</td><td>1</td>", "page": 2, "bbox": [1, 2, 3, 4]},
    ]

    result, groundings = engine.extract(schema, blocks)

    assert result == {"hospital": "전액 본인부담", "amount": 12380, "count": 1.0}
    assert groundings["hospital"] == {"confidence": 1.0, "page": 2, "bbox": [1, 2, 3, 4], "source_text": "전액 본인부담"}
    assert groundings["amount"] == {"confidence": 1.0, "page": 2, "bbox": [1, 2, 3, 4], "source_text": "12380"}
    assert groundings["count"] == {"confidence": 1.0, "page": 2, "bbox": [1, 2, 3, 4], "source_text": "1.0"}
    body = FakeClient.requests[0][1]["json"]
    assert body["response_format"] == {"type": "json_object"}
    assert "provider" not in body
    assert "groundings" not in json.dumps(body["messages"], ensure_ascii=False)


def test_extract_marks_values_absent_from_blocks_as_low_confidence(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"hospital": "서울병원", "code": "없는값"}, ensure_ascii=False))
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}, "code": {"type": "string"}}, "required": ["hospital", "code"]}
    blocks = [{"text": "병원: 서울병원", "page": 1, "bbox": [0, 0, 1, 1]}]

    result, groundings = engine.extract(schema, blocks)

    assert result == {"hospital": "서울병원", "code": "없는값"}
    assert groundings["code"] == {"confidence": 0.0, "page": None, "bbox": None, "source_text": "없는값"}
    assert engine.validate(result, schema, groundings) == [
        {"path": "/code", "code": "low_confidence", "message": "원문 근거 또는 추출 신뢰도가 낮습니다."},
    ]


def test_extract_grounding_tree_mirrors_arrays_and_nesting(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({
        "환자": {"이름": "홍길동"},
        "항목정보": [{"코드": "AA254", "금액": 12380}, {"코드": "BB100", "금액": None}],
    }, ensure_ascii=False))
    schema = {"type": "object", "properties": {
        "환자": {"type": "object", "properties": {"이름": {"type": "string"}}, "required": ["이름"]},
        "항목정보": {"type": "array", "items": {"type": "object", "properties": {"코드": {"type": "string"}, "금액": {"type": ["number", "null"]}}, "required": ["코드", "금액"]}},
    }, "required": ["환자", "항목정보"]}
    blocks = [{"text": "홍길동 AA254 12,380 BB100", "page": 3, "bbox": [5, 6, 7, 8]}]

    _, groundings = engine.extract(schema, blocks)

    assert groundings["환자"]["이름"]["page"] == 3
    assert list(groundings["항목정보"]) == ["0", "1"]
    assert groundings["항목정보"]["0"]["금액"] == {"confidence": 1.0, "page": 3, "bbox": [5, 6, 7, 8], "source_text": "12380"}
    assert groundings["항목정보"]["1"]["금액"] == {"confidence": 0, "page": None, "bbox": None, "source_text": None}


TABLE_BLOCK = {
    "text": (
        "<table>"
        "<tr><td>항목</td><td>금액</td><td>횟수</td></tr>"
        "<tr><td>진찰료</td><td>12,380</td><td>1</td></tr>"
        "<tr><td>약품비</td><td>0</td><td>3</td></tr>"
        "<tr><td>주사료</td><td>15</td><td>2</td></tr>"
        "</table>"
    ),
    "type": "table",
    "page": 1,
    "bbox": [0, 0, 100, 400],
}
ROW_SCHEMA = {"type": "object", "properties": {"항목정보": {"type": "array", "items": {"type": "object", "properties": {
    "항목": {"type": "string"}, "금액": {"type": "number"}, "횟수": {"type": "number"}}}}}}


def test_extract_grounds_each_array_item_on_its_own_table_row(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"항목정보": [
        {"항목": "진찰료", "금액": 12380, "횟수": 1},
        {"항목": "약품비", "금액": 0, "횟수": 3},
    ]}, ensure_ascii=False))

    _, groundings = engine.extract(ROW_SCHEMA, [TABLE_BLOCK])

    # The row box is the block box split by <tr> index: 4 rows over y 0..400.
    assert groundings["항목정보"]["0"]["항목"] == {"confidence": 1.0, "page": 1, "bbox": [0, 100.0, 100, 200.0], "source_text": "진찰료"}
    assert groundings["항목정보"]["0"]["횟수"]["bbox"] == [0, 100.0, 100, 200.0]
    # `0` must not be found inside the `12,380` cell of the row above.
    assert groundings["항목정보"]["1"]["금액"] == {"confidence": 1.0, "page": 1, "bbox": [0, 200.0, 100, 300.0], "source_text": "0"}


def test_extract_marks_array_item_value_taken_from_another_row(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"항목정보": [{"항목": "주사료", "금액": 12380, "횟수": 2}]}, ensure_ascii=False))

    result, groundings = engine.extract(ROW_SCHEMA, [TABLE_BLOCK])

    item = groundings["항목정보"]["0"]
    assert item["항목"]["bbox"] == [0, 300.0, 100, 400.0]
    assert item["금액"] == {"confidence": 0.5, "page": 1, "bbox": [0, 100.0, 100, 200.0], "source_text": "12380"}
    assert engine.validate(result, ROW_SCHEMA, groundings) == [
        {"path": "/항목정보/0/금액", "code": "low_confidence", "message": "원문 근거 또는 추출 신뢰도가 낮습니다."},
    ]


def test_extract_grounds_values_inside_sentences_and_date_separator_variants(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"신청인": "이현창", "일자": "2023-03-11"}, ensure_ascii=False))
    schema = {"type": "object", "properties": {"신청인": {"type": "string"}, "일자": {"type": "string"}}}
    blocks = [{"text": "신청인 이현창(환자와의 관계: 본인)의 요청에 따라 2023.03.11 발급합니다.", "page": 2, "bbox": [1, 2, 3, 4]}]

    _, groundings = engine.extract(schema, blocks)

    assert groundings["신청인"] == {"confidence": 1.0, "page": 2, "bbox": [1, 2, 3, 4], "source_text": "이현창"}
    assert groundings["일자"]["confidence"] == 1.0


def test_extract_top_level_leaves_may_come_from_different_blocks(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"제목": "진료비 세부산정내역", "항목": "진찰료"}, ensure_ascii=False))
    schema = {"type": "object", "properties": {"제목": {"type": "string"}, "항목": {"type": "string"}}}

    _, groundings = engine.extract(schema, [{"text": "진료비 세부산정내역", "page": 1, "bbox": [0, 0, 10, 10]}, TABLE_BLOCK])

    assert groundings["제목"] == {"confidence": 1.0, "page": 1, "bbox": [0, 0, 10, 10], "source_text": "진료비 세부산정내역"}
    assert groundings["항목"] == {"confidence": 1.0, "page": 1, "bbox": [0, 100.0, 100, 200.0], "source_text": "진찰료"}


def test_extract_response_that_is_not_an_object_raises(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps(["서울병원"], ensure_ascii=False))
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}}}

    with pytest.raises(RuntimeError, match="JSON object"):
        engine.extract(schema, [{"text": "병원: 서울병원", "page": 1, "bbox": None}])


def test_extract_drops_null_optional_field_and_passes_validation(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({"hospital": "서울병원", "code": None}, ensure_ascii=False))
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}, "code": {"type": "string"}}, "required": ["hospital"]}
    blocks = [{"text": "병원: 서울병원", "page": 1, "bbox": [0, 0, 1, 1]}]

    result, groundings = engine.extract(schema, blocks)

    assert result == {"hospital": "서울병원"}
    assert "code" not in groundings
    assert engine.validate(result, schema, groundings) == []


def test_extract_small_document_is_a_single_provider_call(monkeypatch):
    """The common case (document fits the budget) makes exactly one call, with no "part N of M" note."""
    configure(monkeypatch)
    install_response(monkeypatch, '{"hospital": "서울병원"}')
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}}}
    blocks = [{"text": "병원: 서울병원", "page": 1, "bbox": None}, {"text": "추가 정보", "page": 2, "bbox": None}]

    result, _ = engine.extract(schema, blocks)

    assert result == {"hospital": "서울병원"}
    assert len(FakeClient.requests) == 1
    system_content = FakeClient.requests[0][1]["json"]["messages"][0]["content"]
    assert "part" not in system_content


def test_extract_splits_multi_page_document_into_chunks_on_page_boundaries(monkeypatch, caplog):
    configure(monkeypatch)
    monkeypatch.setenv("EXTRACT_CHUNK_CHARS", "50")
    install_responses(monkeypatch, ['{"hospital": null}', '{"hospital": "서울병원"}'])
    schema = {"type": "object", "properties": {"hospital": {"type": "string"}}}
    blocks = [
        {"text": "A" * 20, "page": 1, "bbox": None},
        {"text": "B" * 20, "page": 1, "bbox": None},
        {"text": "C" * 20, "page": 2, "bbox": None},
    ]

    with caplog.at_level(logging.INFO, logger="backend.engine"):
        result, _ = engine.extract(schema, blocks)

    assert len(FakeClient.requests) == 2
    assert result == {"hospital": "서울병원"}
    first_system = FakeClient.requests[0][1]["json"]["messages"][0]["content"]
    second_system = FakeClient.requests[1][1]["json"]["messages"][0]["content"]
    assert "part 1 of 2" in first_system and "page(s) 1" in first_system
    assert "part 2 of 2" in second_system and "page(s) 2" in second_system
    first_evidence = FakeClient.requests[0][1]["json"]["messages"][1]["content"]
    assert "A" * 20 in first_evidence and "B" * 20 in first_evidence and "C" * 20 not in first_evidence
    second_evidence = FakeClient.requests[1][1]["json"]["messages"][1]["content"]
    assert "C" * 20 in second_evidence and "A" * 20 not in second_evidence
    assert "chunks=2" in caplog.text


def test_extract_merges_chunk_results_array_concat_and_scalar_first_non_null(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("EXTRACT_CHUNK_CHARS", "35")
    install_responses(monkeypatch, [
        json.dumps({"title": None, "items": [{"code": "A"}, {"code": "B"}]}, ensure_ascii=False),
        json.dumps({"title": "문서 제목", "items": [{"code": "B"}, {"code": "C"}]}, ensure_ascii=False),
    ])
    schema = {"type": "object", "properties": {
        "title": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object", "properties": {"code": {"type": "string"}}}},
    }}
    blocks = [{"text": "X" * 30, "page": 1, "bbox": None}, {"text": "Y" * 30, "page": 2, "bbox": None}]

    result, _ = engine.extract(schema, blocks)

    assert len(FakeClient.requests) == 2
    # "title" keeps the first non-null value in document order; the "B" item duplicated at the chunk
    # boundary is dropped once, but a real repeat within a chunk's own list is never touched.
    assert result == {"title": "문서 제목", "items": [{"code": "A"}, {"code": "B"}, {"code": "C"}]}


def test_extract_splits_an_oversize_page_at_block_boundaries(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("EXTRACT_CHUNK_CHARS", "50")
    install_responses(monkeypatch, ["{}", "{}", "{}"])
    blocks = [{"text": "Z" * 30, "page": 1, "bbox": None} for _ in range(3)]

    engine.extract({"type": "object", "properties": {}}, blocks)

    # One page (93 chars) over the 50-char budget must split into several same-page chunks, never drop blocks.
    assert len(FakeClient.requests) == 3
    for _, request in FakeClient.requests:
        system_content = request["json"]["messages"][0]["content"]
        assert "page(s) 1" in system_content


def test_extract_truncates_a_single_block_that_alone_exceeds_the_budget(monkeypatch, caplog):
    configure(monkeypatch)
    monkeypatch.setenv("EXTRACT_CHUNK_CHARS", "50")
    install_response(monkeypatch, "{}")
    blocks = [{"text": "가" * 100, "page": 1, "bbox": None}]

    with caplog.at_level(logging.WARNING, logger="backend.engine"):
        engine.extract({"type": "object", "properties": {}}, blocks)

    assert len(FakeClient.requests) == 1
    evidence = FakeClient.requests[0][1]["json"]["messages"][1]["content"].split("Source blocks:\n", 1)[1]
    assert len(evidence) == 50
    assert "truncat" in caplog.text
