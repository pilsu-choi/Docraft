"""AO 교차검증(`backend.verify`)과 `POST /api/verify`. doctypes/rules는 monkeypatch로 대체한다."""

import glob
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import doctypes, engine, rules, verify
from backend.main import app
from test_ai_provider import FakeClient, configure, install_response


client = TestClient(app)
SAMPLES = "/home/pilsu/projects/mirae-assets/harness-v2/docs/agentic-ocr-2.0.1-results"

AO = {
    "transaction_id": "tx-1",
    "documents": [{
        "doc_type": "진단서",
        "extracted_fields": [
            {"key": "진단일", "value": "20230228", "confidence": 0.99, "predicted_value": "20230228"},
            {"key": "진단명", "value": "골절", "confidence": 0.71, "predicted_value": "골절"},
        ],
        "extracted_groups": [{"key": "의료기관", "fields": [
            {"key": "병원명", "value": "고려대병원", "confidence": 0.80, "predicted_value": "고려대병원"},
            {"key": "면허번호", "value": "", "confidence": 0.0, "predicted_value": "44577"},
            {"key": "환자명", "value": "홍길동", "confidence": 0.70, "predicted_value": "홍길동"},
        ]}],
        "extracted_tables": [{"key": "병명내역", "headers": ["병명코드", "병명"], "rows": [[
            {"key": "병명코드", "value": "R634", "confidence": 0.97, "predicted_value": "R634"},
            {"key": "병명", "value": "이상체중감소", "confidence": 0.73, "predicted_value": "이상체중감소"},
        ]]}],
    }],
}
DOCRAFT = {
    "진단일": "20230228",  # agree
    "진단명": "골정",  # dispute -> ao
    "병원명": "고려대학교 구로병원",  # dispute -> docraft
    "면허번호": "44577",  # agree: AO의 빈 value는 predicted_value로 채워진다
    "환자명": "홍길순",  # dispute -> corrected
    "병명내역": [{"병명코드": "R634", "병명": "이상체중감소"}, {"병명코드": "M8199", "병명": "골다공증"}],  # dispute
}
VERDICTS = {
    "진단명": {"value": "골절", "source": "ao", "reason": "AO 값이 이미지와 같다"},
    "병원명": {"value": "고려대학교 구로병원", "source": "docraft", "reason": "이미지에 전체 이름이 있다"},
    "환자명": {"value": "홍길동님", "source": "corrected", "reason": "이미지 표기를 그대로 읽었다"},
    "병명내역": {"source": "corrected", "reason": "부상병 행이 빠졌다",
                 "rows": [{"병명코드": "R634", "병명": "이상체중감소"}, {"병명코드": "M8199", "병명": "골다공증(속발)"}]},
}


def _image(tmp_path, name="scan.png", frames=1):
    path = tmp_path / name
    pages = [Image.new("RGB", (8, 8), "white") for _ in range(frames)]
    pages[0].save(path, save_all=frames > 1, append_images=pages[1:])
    return path


def stub(monkeypatch, judged=VERDICTS, docraft=DOCRAFT):
    """doctypes·rules·parse·extract·judge를 대체하고 judge 호출 인자를 모아 돌려준다."""
    calls = []
    monkeypatch.setitem(doctypes.DOC_TYPES, "진단서", {})
    monkeypatch.setattr(doctypes, "schema", lambda doc_type: {"type": "object"})
    monkeypatch.setattr(doctypes, "kind", lambda doc_type, key, table=None: "text")
    monkeypatch.setattr(rules, "same", lambda kind, a, b: (a or None) == (b or None))
    # blocks가 있으면(추출 단계) 고정된 docraft를, 없으면(_decide의 판정값 정규화) 입력을 그대로 돌려준다.
    monkeypatch.setattr(rules, "apply", lambda doc_type, result, blocks: deepcopy(docraft) if blocks else deepcopy(result))
    monkeypatch.setattr(verify, "parse", lambda *args, **kwargs: ("md", [{"text": "x"}]))
    monkeypatch.setattr(engine, "extract", lambda schema, blocks, source=None: ({}, {}))
    monkeypatch.setattr(verify, "judge", lambda image, doc_type, disputes: calls.append((image, doc_type, disputes)) or deepcopy(judged))
    return calls


def field(document, key):
    return next(value for name, value in verify._scalars(document) if name == key)


# --- flatten -------------------------------------------------------------


def sample(doc_type):
    paths = glob.glob(f"{SAMPLES}/{doc_type}/*.json")
    if not paths:
        pytest.skip(f"AO 예시 JSON이 없습니다: {doc_type}")
    return json.load(open(paths[0], encoding="utf-8"))["documents"][0]


def test_flatten_reads_fields_groups_and_tables_of_a_real_diagnosis_result():
    flat = verify.flatten(sample("진단서"))

    assert flat["진단일"] == "20230228"
    assert flat["병원명"] == "고려대학교 구로병원"  # 그룹 필드도 같은 평면에 온다
    assert flat["병명내역"][0]["병명코드"] == "R634"
    assert all(isinstance(row, dict) for row in flat["병명내역"])


def test_flatten_reads_a_real_statement_result_with_a_wide_table():
    flat = verify.flatten(sample("세부내역서"))

    assert flat["사고발생일자"] == "20230311"
    assert flat["환자성명"] == "이현창"
    assert flat["항목내역"][0]["EDI코드"] == "AA254"


@pytest.mark.parametrize("doc_type, name", [("수술확인서", "수술확인서"), ("입퇴원확인서", "입원확인서"),
                                            ("약제비영수증", "약제영수증")])
def test_flatten_and_add_missing_on_the_new_types_real_results(doc_type, name):
    document = sample(doc_type)
    assert doctypes.ALIASES.get(document["doc_type"], document["doc_type"]) == doc_type == doctypes.ALIASES.get(name, name)
    flat = verify.flatten(document)
    assert set(flat) <= set(doctypes.schema(doc_type)["properties"])
    assert verify._add_missing(document, doc_type) == 0  # AO 예시에 이미 모든 키가 있다


def test_flatten_falls_back_to_predicted_value_and_maps_empty_values_to_none():
    flat = verify.flatten({"extracted_fields": [
        {"key": "면허번호", "value": "", "predicted_value": "44577"},
        {"key": "통원일수", "value": "", "predicted_value": ""},
    ]})

    assert flat == {"면허번호": "44577", "통원일수": None}


# --- run -----------------------------------------------------------------


def test_run_only_sends_mismatched_fields_to_the_judge(monkeypatch):
    calls = stub(monkeypatch)

    verify.run("scan.png", AO)

    _, doc_type, disputes = calls[0]
    assert doc_type == "진단서"
    assert set(disputes) == {"진단명", "병원명", "환자명", "병명내역"}  # 일치하는 진단일·면허번호는 빠진다
    assert disputes["병원명"] == {"ao": "고려대병원", "docraft": "고려대학교 구로병원"}
    assert disputes["병명내역"]["docraft"] == DOCRAFT["병명내역"]


def test_run_skips_the_judge_when_every_field_agrees(monkeypatch):
    agreeing = {**verify.flatten(AO["documents"][0])}
    calls = stub(monkeypatch, docraft=agreeing)

    output = verify.run("scan.png", AO)

    assert calls == []
    assert output["documents"][0]["verify"]["counts"] == {
        "agree": 6, "ao": 0, "docraft": 0, "corrected": 0, "unknown": 0, "added": 0}


def test_run_applies_every_verdict_source_and_keeps_the_original_values(monkeypatch):
    stub(monkeypatch)

    output = verify.run("scan.png", AO)
    document = output["documents"][0]

    assert (field(document, "진단일")["value"], field(document, "진단일")["source"]) == ("20230228", "agree")
    assert field(document, "진단일")["reason"] is None
    assert field(document, "면허번호")["value"] == "44577" and field(document, "면허번호")["ao_value"] == ""
    assert field(document, "진단명")["value"] == "골절" and field(document, "진단명")["source"] == "ao"
    assert field(document, "병원명")["value"] == "고려대학교 구로병원"
    assert field(document, "병원명")["ao_value"] == "고려대병원"
    assert field(document, "병원명")["docraft_value"] == "고려대학교 구로병원"
    assert field(document, "병원명")["source"] == "docraft"
    assert field(document, "환자명")["value"] == "홍길동님" and field(document, "환자명")["source"] == "corrected"
    assert field(document, "환자명")["reason"] == "이미지 표기를 그대로 읽었다"
    assert field(document, "진단일")["confidence"] == 0.99  # 기존 필드는 보존된다


def test_run_reports_counts_the_docraft_result_and_leaves_the_input_untouched(monkeypatch):
    stub(monkeypatch)
    original = deepcopy(AO)

    output = verify.run("scan.png", AO)

    assert output["transaction_id"] == "tx-1"
    assert output["documents"][0]["verify"]["doc_type"] == "진단서"
    assert output["documents"][0]["verify"]["docraft"] == DOCRAFT
    assert output["documents"][0]["verify"]["counts"] == {
        "agree": 2, "ao": 1, "docraft": 1, "corrected": 2, "unknown": 0, "added": 0}
    assert AO == original


def test_run_rebuilds_table_rows_from_the_verdict_keeping_the_cell_format(monkeypatch):
    stub(monkeypatch)

    table = verify.run("scan.png", AO)["documents"][0]["extracted_tables"][0]

    assert table["source"] == "corrected" and len(table["rows"]) == 2
    assert [cell["key"] for cell in table["rows"][0]] == ["병명코드", "병명"]
    assert table["rows"][0][0]["confidence"] == 0.97  # 원래 셀이 있으면 형식을 보존한다
    assert table["rows"][0][0]["ao_value"] == "R634"
    assert [cell["value"] for cell in table["rows"][1]] == ["M8199", "골다공증(속발)"]
    assert table["rows"][1][0]["ao_value"] is None
    # 판정이 늘린 행은 열 셀의 형식만 빌리고 원래 값은 남기지 않는다(예측값은 최종값으로 맞춘다).
    assert table["rows"][1][0]["confidence"] is None and table["rows"][1][0]["predicted_value"] == "M8199"
    assert table["rows"][1][1]["docraft_value"] == "골다공증"
    assert table["rows"][1][1]["reason"] == "부상병 행이 빠졌다"


def test_run_keeps_the_ao_value_when_the_judge_leaves_a_field_out(monkeypatch):
    stub(monkeypatch, judged={})

    document = verify.run("scan.png", AO)["documents"][0]

    assert field(document, "병원명")["value"] == "고려대병원"
    assert field(document, "병원명")["source"] == "unknown"  # 판정이 없으면 이미지로 확인된 것이 아니다
    assert field(document, "병원명")["reason"] == verify.NO_VERDICT


def test_run_rejects_a_document_type_it_has_no_fields_for(monkeypatch):
    stub(monkeypatch)

    with pytest.raises(ValueError, match="지원하지 않는 문서 유형"):
        verify.run("scan.png", AO, doc_type="처방전")
    with pytest.raises(ValueError, match="documents"):
        verify.run("scan.png", {"documents": []})


def test_run_maps_an_ao_document_type_alias_to_its_type(monkeypatch):
    calls = stub(monkeypatch)
    monkeypatch.setitem(doctypes.DOC_TYPES, "약제비영수증", {})
    ao = deepcopy(AO)
    ao["documents"][0]["doc_type"] = "약제영수증"

    result = verify.run("scan.png", ao)

    assert calls[0][1] == verify.document(result)["verify"]["doc_type"] == "약제비영수증"


def test_run_prefers_the_requested_document_type_over_the_ao_one(monkeypatch):
    calls = stub(monkeypatch)
    monkeypatch.setitem(doctypes.DOC_TYPES, "소견서", {})

    verify.run("scan.png", AO, doc_type="소견서")

    assert calls[0][1] == "소견서"


# --- hint_paths ------------------------------------------------------------


def hinted_stub(monkeypatch, judged=VERDICTS, docraft=DOCRAFT):
    """stub()에 hint_paths의 key 검증·스키마 축소에 쓰는 실제 형태의 spec/schema를 얹는다."""
    calls = stub(monkeypatch, judged, docraft)
    fields, tables = ["진단일", "진단명", "병원명", "면허번호", "환자명"], ["병명내역"]
    monkeypatch.setattr(doctypes, "spec", lambda doc_type: {
        "fields": {key: {"kind": "text"} for key in fields},
        "tables": {"병명내역": {"병명코드": {"kind": "text"}, "병명": {"kind": "text"}}}})
    monkeypatch.setattr(doctypes, "schema", lambda doc_type: {
        "type": "object", "properties": dict.fromkeys([*fields, *tables], {}), "required": [*fields, *tables]})
    schemas = []
    monkeypatch.setattr(engine, "extract", lambda schema, blocks, source=None: (schemas.append(schema) or {}, {}))
    return calls, schemas


def test_run_with_hint_paths_only_judges_the_given_keys(monkeypatch):
    calls, _ = hinted_stub(monkeypatch)

    document = verify.run("scan.png", AO, hint_paths=["병원명"])["documents"][0]

    assert set(calls[0][2]) == {"병원명"}  # 병원명만 disputes로 Judge에 갔다
    assert field(document, "병원명")["value"] == "고려대학교 구로병원" and field(document, "병원명")["source"] == "docraft"
    assert "source" not in field(document, "진단명")  # 힌트 밖 필드는 판정 정보 없이 AO 값 그대로
    assert "source" not in field(document, "진단일")
    assert document["verify"]["counts"] == {"agree": 0, "ao": 0, "docraft": 1, "corrected": 0, "unknown": 0, "added": 0}


def test_run_with_hint_paths_restricts_the_extraction_schema(monkeypatch):
    _, schemas = hinted_stub(monkeypatch)

    verify.run("scan.png", AO, hint_paths=["병원명", "병명내역"])

    assert set(schemas[0]["properties"]) == {"병원명", "병명내역"}
    assert set(schemas[0]["required"]) == {"병원명", "병명내역"}


def test_run_without_hint_paths_behaves_as_before(monkeypatch):
    calls, schemas = hinted_stub(monkeypatch)

    document = verify.run("scan.png", AO)["documents"][0]

    assert set(calls[0][2]) == {"진단명", "병원명", "환자명", "병명내역"}
    assert set(schemas[0]["properties"]) == {"진단일", "진단명", "병원명", "면허번호", "환자명", "병명내역"}
    assert document["verify"]["counts"]["docraft"] == 1


def test_run_ignores_unknown_hint_paths_alongside_known_ones_and_logs_once(monkeypatch, caplog):
    calls, _ = hinted_stub(monkeypatch)

    with caplog.at_level("WARNING"):
        document = verify.run("scan.png", AO, hint_paths=["병원명", "없는키"])["documents"][0]

    assert set(calls[0][2]) == {"병원명"}  # 알 수 없는 key는 disputes에 들어가지 않는다
    assert caplog.text.count("없는키") == 1  # 경고는 한 번만
    assert "source" not in field(document, "진단명")  # 나머지 힌트 밖 필드는 그대로


def test_run_rejects_hint_paths_with_no_key_defined_for_the_doc_type(monkeypatch):
    calls, _ = hinted_stub(monkeypatch)

    with pytest.raises(ValueError, match="hint_paths"):
        verify.run("scan.png", AO, hint_paths=["없는키"])

    assert calls == []  # 파싱·추출·Judge 전에 끊긴다


def test_run_with_empty_hint_paths_behaves_as_before(monkeypatch):
    calls, _ = hinted_stub(monkeypatch)

    document = verify.run("scan.png", AO, hint_paths=[])["documents"][0]

    assert set(calls[0][2]) == {"진단명", "병원명", "환자명", "병명내역"}
    assert document["verify"]["counts"]["docraft"] == 1


def test_verify_route_forwards_parsed_hint_paths(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(verify, "run", lambda image, ao, doc_type=None, hint_paths=None: seen.append(hint_paths) or {
        "documents": [{"verify": {"counts": {}}}]})

    response = post(_image(tmp_path), hint_paths=json.dumps(["병원명"]))

    assert response.status_code == 200 and seen[0] == ["병원명"]


def test_verify_route_rejects_invalid_hint_paths_json(tmp_path):
    response = post(_image(tmp_path), hint_paths="not json")

    assert response.status_code == 422 and "hint_paths" in response.json()["detail"]


def test_verify_route_rejects_a_non_list_hint_paths(tmp_path):
    response = post(_image(tmp_path), hint_paths=json.dumps({"key": "병원명"}))

    assert response.status_code == 422 and "hint_paths" in response.json()["detail"]


def test_verify_route_rejects_hint_paths_with_no_key_defined_for_the_doc_type(tmp_path):
    """모든 key가 진단서 정의 밖이면(=extraction 낭비 방지) 이미지 파싱 전에 422로 끊는다(실제 verify.run)."""
    response = post(_image(tmp_path), doc_type="진단서", hint_paths=json.dumps(["없는키"]))

    assert response.status_code == 422 and "hint_paths" in response.json()["detail"]


# --- reclassifying a format-only "corrected" verdict (real doctypes/rules) -----


def real_stub(monkeypatch, docraft, verdicts, blocks=None):
    """parse·extract·judge만 대체한다. doctypes·rules는 실제 것을 쓴다.

    ``rules.apply``는 docraft 추출 호출(blocks 있음)만 고정된 docraft로 바꿔치기하고,
    ``_decide``의 판정값 정규화 호출(blocks 없음)은 실제 ``rules.apply``를 그대로 쓴다.
    """
    real_apply = rules.apply
    monkeypatch.setattr(verify, "parse", lambda *args, **kwargs: ("md", blocks or [{"text": "x"}]))
    monkeypatch.setattr(engine, "extract", lambda schema, blocks, source=None: ({}, {}))
    monkeypatch.setattr(rules, "apply",
                         lambda doc_type, result, blocks: deepcopy(docraft) if blocks else real_apply(doc_type, result, blocks))
    monkeypatch.setattr(verify, "judge", lambda image, doc_type, disputes: deepcopy(verdicts))


def test_run_reclassifies_a_format_only_corrected_verdict_to_ao(monkeypatch):
    """Judge가 형식만 다른(점 있는 코드·구분자 다른 날짜) 값을 corrected로 줘도 AO와 같으면 ao로 재분류한다."""
    ao = {"documents": [{"doc_type": "진단서", "extracted_fields": [
        {"key": "발급일", "value": "20220517", "confidence": 0.9},
    ], "extracted_tables": [{"key": "병명내역", "headers": ["병명코드", "병명"], "rows": [[
        {"key": "병명코드", "value": "R634", "confidence": 0.9},
        {"key": "병명", "value": "이상체중감소", "confidence": 0.9},
    ]]}]}]}
    docraft = {"발급일": "20220510", "병명내역": [{"병명코드": "R635", "병명": "다른병명"}]}
    verdicts = {
        "발급일": {"value": "2022/05/17", "source": "corrected", "reason": "이미지 표기 그대로"},
        "병명내역": {"source": "corrected", "reason": "이미지 표기 그대로",
                   "rows": [{"병명코드": "R63.4", "병명": "이상체중감소"}]},
    }
    real_stub(monkeypatch, docraft, verdicts)

    document = verify.run("scan.png", ao)["documents"][0]

    assert (field(document, "발급일")["value"], field(document, "발급일")["source"]) == ("20220517", "ao")
    assert field(document, "발급일")["reason"] == "이미지 표기 그대로"
    table = document["extracted_tables"][0]
    assert table["source"] == "ao"
    assert [cell["value"] for cell in table["rows"][0]] == ["R634", "이상체중감소"]


def test_run_normalizes_a_genuinely_corrected_table_value_without_reclassifying(monkeypatch):
    """AO·Docraft 둘 다와 다른 값은 corrected로 남되, 최종 값은 정규화(점 제거)한다."""
    ao = {"documents": [{"doc_type": "진단서", "extracted_tables": [
        {"key": "병명내역", "headers": ["병명코드", "병명"], "rows": [[
            {"key": "병명코드", "value": "R634", "confidence": 0.9},
            {"key": "병명", "value": "AAA", "confidence": 0.9},
        ]]}]}]}
    docraft = {"병명내역": [{"병명코드": "R635", "병명": "BBB"}]}
    verdicts = {"병명내역": {"source": "corrected", "reason": "행이 하나 더 있다",
                          "rows": [{"병명코드": "R63.4", "병명": "AAA"}, {"병명코드": "S99", "병명": "CCC"}]}}
    real_stub(monkeypatch, docraft, verdicts)

    table = verify.run("scan.png", ao)["documents"][0]["extracted_tables"][0]

    assert table["source"] == "corrected"
    assert [cell["value"] for cell in table["rows"][0]] == ["R634", "AAA"]  # 점이 지워졌다
    assert [cell["value"] for cell in table["rows"][1]] == ["S99", "CCC"]


def test_run_keeps_a_genuinely_corrected_text_field_unchanged(monkeypatch):
    """AO·Docraft 둘 다와 진짜로 다른 값이면 Judge가 준 값 그대로 corrected에 남는다."""
    ao = {"documents": [{"doc_type": "진단서", "extracted_fields": [
        {"key": "진료과", "value": "내과", "confidence": 0.9},
    ]}]}
    docraft = {"진료과": "소아과"}  # '외과'였다면 '정형외과'가 품고 있어 rules.same이 같다고 본다
    verdicts = {"진료과": {"value": "정형외과", "source": "corrected", "reason": "이미지에 정형외과로 적혀있다"}}
    real_stub(monkeypatch, docraft, verdicts)

    field_out = field(verify.run("scan.png", ao)["documents"][0], "진료과")

    assert (field_out["value"], field_out["source"], field_out["reason"]) == ("정형외과", "corrected", "이미지에 정형외과로 적혀있다")


def test_decide_drops_total_rows_ao_excludes_via_apply_reuse():
    """Judge가 AO에 없던 '계'·'끝수처리 조정금액' 같은 합계행을 끼워 넣어도 rules.apply 재사용으로 걸러진다."""
    verdict = {"source": "corrected", "reason": "합계행을 함께 읽었다", "rows": [
        {"항목": "진찰료", "본인부담": "1,000"},
        {"항목": "계", "본인부담": "9,000"},
        {"항목": "끝수처리 조정금액", "본인부담": "-10"},
    ]}

    rows, source, reason = verify._decide("세부내역서", "항목내역", verdict, [], [], "rows")

    assert [row["항목"] for row in rows] == ["진찰료"]  # 합계행 두 개 모두 빠졌다
    assert rows[0]["본인부담"] == "1000"  # kind별 정규화(콤마 제거)도 함께 적용된다
    assert source == "corrected" and reason == "합계행을 함께 읽었다"


# --- judge ---------------------------------------------------------------


def test_judge_attaches_the_page_image_and_parses_the_verdicts(monkeypatch, tmp_path):
    configure(monkeypatch)
    install_response(monkeypatch, json.dumps({
        "병원명": {"value": "고려대학교 구로병원", "source": "docraft", "reason": "이미지"},
        "없는키": {"value": "x", "source": "ao", "reason": "무시"},
    }, ensure_ascii=False))
    pages = []
    monkeypatch.setattr(engine, "_page_images", lambda source, numbers: pages.append((source, numbers)) or ["data:image/jpeg;base64,AA"])
    path = str(_image(tmp_path))

    verdicts = verify.judge(path, "진단서", {"병원명": {"ao": "고려대병원", "docraft": "고려대학교 구로병원"}})

    assert list(verdicts) == ["병원명"]  # 요청하지 않은 키는 버린다
    assert verdicts["병원명"]["source"] == "docraft"
    assert pages == [(path, [1])]
    content = FakeClient.requests[0][1]["json"]["messages"][0]["content"]
    assert content[0]["image_url"]["url"] == "data:image/jpeg;base64,AA"
    assert "진단서" in content[1]["text"] and "고려대학교 구로병원" in content[1]["text"]
    assert doctypes.DOC_TYPES["진단서"]["fields"]["병원명"]["description"] in content[1]["text"]  # desc가 실려 간다
    assert FakeClient.requests[0][1]["json"]["response_format"] == {"type": "json_object"}


def test_describe_adds_a_field_desc_and_a_table_desc_per_column_once():
    entry = verify._describe("진단서", "병원명", {"ao": "고려대병원", "docraft": "고려대학교 구로병원"})
    assert entry["desc"] == doctypes.DOC_TYPES["진단서"]["fields"]["병원명"]["description"]

    table_entry = verify._describe("진단서", "병명내역", {"ao": [], "docraft": []})
    assert table_entry["desc"] == {column: meta["description"]
                                    for column, meta in doctypes.DOC_TYPES["진단서"]["tables"]["병명내역"].items()}


def test_judge_rejects_a_non_object_response(monkeypatch):
    configure(monkeypatch)
    install_response(monkeypatch, "[1, 2]")
    monkeypatch.setattr(engine, "_page_images", lambda source, numbers: [])

    with pytest.raises(RuntimeError, match="JSON object"):
        verify.judge("scan.png", "진단서", {"병원명": {"ao": "a", "docraft": "b"}})


# --- route ---------------------------------------------------------------


def post(path, ao_result=None, **data):
    with open(path, "rb") as handle:
        return client.post("/api/verify", files={"image": (path.name, handle, "image/png")},
                           data={"ao_result": json.dumps(AO) if ao_result is None else ao_result, **data})


def test_verify_route_returns_the_corrected_result(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(verify, "run", lambda image, ao, doc_type=None, hint_paths=None: seen.append((image, doc_type)) or {
        "documents": [{"verify": {"counts": {"agree": 1, "ao": 0, "docraft": 0, "corrected": 0}}}]})

    response = post(_image(tmp_path), doc_type="진단서")

    assert response.status_code == 200
    assert response.json()["documents"][0]["verify"]["counts"]["agree"] == 1
    assert seen[0][1] == "진단서" and seen[0][0].endswith(".png")


def test_verify_route_rejects_a_non_image_upload(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.4")

    response = post(path)

    assert response.status_code == 415
    assert "이미지 파일만" in response.json()["detail"]


@pytest.mark.parametrize("ao_result,message", [("not json", "JSON으로"), ('{"documents": []}', "documents")])
def test_verify_route_rejects_an_unusable_ao_result(tmp_path, ao_result, message):
    response = post(_image(tmp_path), ao_result=ao_result)

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_verify_route_reports_an_unsupported_document_type(monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "run", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("지원하지 않는 문서 유형입니다: x")))

    response = post(_image(tmp_path))

    assert response.status_code == 422 and "지원하지 않는 문서 유형" in response.json()["detail"]


def test_verify_route_turns_a_provider_failure_into_a_gateway_error(monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("AI provider 요청 실패")))

    response = post(_image(tmp_path))

    assert response.status_code == 502 and "교차검증에 실패" in response.json()["detail"]


def test_verify_route_rejects_a_multi_page_tif(monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "run", lambda *args, **kwargs: pytest.fail("다중 페이지 문서는 처리하면 안 된다"))

    response = post(_image(tmp_path, "scan.tif", frames=2))

    assert response.status_code == 422
    assert response.json()["detail"] == "다중 페이지 문서는 아직 지원하지 않습니다."


# --- UI 형식과 key·value 누락 ---------------------------------------------

CASES = Path("/home/pilsu/projects/mirae-assets/harness-v2/docs/requirements")
UI = {"run_id": "r1", "stage": "extract", "status": "done", "result": {
    "doc_type": "진료비영수증",
    "fields": [{"key": "발행일", "value": "20241210", "display_label": "발행일"}],
    "groups": [{"key": "금액산정", "fields": [
        {"key": "금액산정.진료비총액", "value": "11387230", "display_label": "진료비총액"}]}],
    "tables": [{"key": "항목내역", "headers": ["항목", "본인부담금"],
                "rows": [[{"key": "항목내역[0].항목", "value": "진찰료"}, {"value": "1815"}]]}]}}


def ui_case(folder, name):
    path = CASES / folder / "latest" / name
    if not path.exists():
        pytest.skip(f"케이스 파일이 없습니다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_flatten_reads_the_ui_result_format(monkeypatch):
    flat = verify.flatten(verify.document(UI))

    assert flat["발행일"] == "20241210"
    assert flat["진료비총액"] == "11387230"  # 그룹 접두사를 뗀다
    assert flat["항목내역"] == [{"항목": "진찰료", "본인부담금": "1815"}]  # 셀 key가 없으면 headers로 보충한다


def test_flatten_reads_a_real_ui_result_of_an_error_case():
    flat = verify.flatten(verify.document(ui_case("[진료비영수증]비급여_급여_오추출됨", "07-extract-bbox.json")))

    assert flat["의료기관정보-명칭"] == "허그요양병원"
    assert flat["환자정보-성명"] is None  # 빈 value는 None
    assert flat["항목내역"][27] == {"항목": "정액수가(요양병원)", "본인부담금": "375610", "공단부담금": "2001620",
                                 "전액본인부담": "0", "비급여": "0", "선택진료료": "0", "선택진료료외": "0",
                                 "급여": "9010000"}


@pytest.mark.parametrize("element, expected", [
    ({"key": "발행일", "value": "20241210"}, ("발행일", "20241210")),
    ({"key": "발행일", "value": ""}, ("발행일", None)),                            # value 누락
    ({"key": "", "display_label": "발행일", "value": "20241210"}, ("발행일", "20241210")),  # key 누락
    ({"value": "20241210"}, (None, "20241210")),                                  # key·display_label 둘 다 없음
    ({"key": "발행일"}, ("발행일", None)),                                         # key만 있고 value 없음
    ({}, (None, None)),                                                           # 둘 다 없음
    ({"key": "발행일", "value": "20241210", "not_extracted": True}, ("발행일", None)),
])
def test_name_and_value_of_an_element_with_missing_parts(element, expected):
    assert (verify._name(element), verify._value(element)) == expected


def test_run_marks_an_element_without_a_name_as_unknown(monkeypatch):
    stub(monkeypatch, judged={})
    ao = deepcopy(AO)
    ao["documents"][0]["extracted_fields"].append({"value": "이름 없는 값"})

    document = verify.run("scan.png", ao)["documents"][0]

    nameless = document["extracted_fields"][-1]
    assert (nameless["source"], nameless["reason"]) == ("unknown", verify.UNKNOWN)
    assert nameless["value"] == "이름 없는 값"  # 값은 그대로 둔다
    elements = [*verify._scalars(document), *verify._tables(document)]
    unjudged = sum(element.get("reason") == verify.NO_VERDICT for _, element in elements)
    assert document["verify"]["counts"]["unknown"] == 1 + unjudged  # 이름 없는 원소 + 판정 없는 필드


def test_run_adds_defined_fields_and_tables_the_ao_result_left_out(monkeypatch):
    ao = {"result": {"doc_type": "진료비영수증", "fields": [{"key": "발행일", "value": "20241210"}],
                     "groups": [], "tables": []}}
    docraft = {"진료비총액": "216470", "항목내역": [{"항목": "진찰료", "본인부담금": "1000"}]}
    verdicts = {"진료비총액": {"value": "216470", "source": "docraft", "reason": "이미지 우측 합계"},
                "항목내역": {"source": "docraft", "reason": "이미지의 표", "rows": docraft["항목내역"]}}
    real_stub(monkeypatch, docraft, verdicts)

    result = verify.run("scan.png", ao)["result"]
    spec = doctypes.DOC_TYPES["진료비영수증"]

    added = {element["key"]: element for element in result["fields"] if element.get("added")}
    assert len(added) == len(spec["fields"]) - 1  # 발행일만 이미 있었다
    assert added["진료비총액"]["ao_value"] is None
    assert (added["진료비총액"]["value"], added["진료비총액"]["source"]) == ("216470", "docraft")
    assert added["환자부담총액"]["value"] is None  # Docraft도 못 읽은 필드는 값 없이 agree
    assert added["환자부담총액"]["source"] == "agree"
    table = result["tables"][0]
    assert table["added"] and table["key"] == "항목내역" and table["headers"] == list(spec["tables"]["항목내역"])
    assert [cell["value"] for cell in table["rows"][0][:2]] == ["진찰료", "1000"]
    assert table["rows"][0][0]["key"] == "항목" and table["rows"][0][0]["ao_value"] is None
    assert result["verify"]["counts"]["added"] == len(spec["fields"]) - 1 + 1


def test_run_on_a_ui_result_needs_a_document_type_when_the_result_has_none(monkeypatch):
    stub(monkeypatch)
    ao = {"result": {"doc_type": None, "fields": [], "groups": [], "tables": []}}

    with pytest.raises(ValueError, match="지원하지 않는 문서 유형"):
        verify.run("scan.png", ao)


# --- 진료비영수증 이상 검출이 run에 실리는지 --------------------------------


def test_run_reports_the_checks_and_hands_the_judge_a_hint(monkeypatch):
    ao = ui_case("[진료비영수증]비급여_급여_오추출됨", "07-extract-bbox.json")
    rows = verify.flatten(verify.document(ao))["항목내역"]
    docraft = {"항목내역": [{**row, "급여": "0", "비급여": "9010000"} for row in (rows[27], rows[30])]}
    calls = []
    # 머리글에 급여가 묶음 제목으로만 있는 실제 서식을 흉내 낸 파싱 블록.
    real_stub(monkeypatch, docraft, {}, blocks=[{"type": "table", "rows": [
        ["항 목", "급 여", "", "비급여④"], ["일부", "본인부담", "전액본인"], ["본인부담금①", "공단부담금②", "부담③"]]}])
    monkeypatch.setattr(verify, "judge", lambda image, doc_type, disputes: calls.append(disputes) or {})

    result = verify.run("scan.png", ao, doc_type="진료비영수증")["result"]

    codes = {flag["code"] for flag in result["verify"]["checks"]}
    assert {"no_column", "sum_mismatch"} <= codes
    assert "0이어야" not in calls[0]["항목내역"].get("hint", "")  # 룰이 고친 no_column은 Judge 힌트에서 빠진다
    table = result["tables"][0]
    assert (table["rows"][27][7]["value"], table["rows"][27][4]["value"]) == ("0", "9010000")  # 급여 → 비급여
    assert table["source"] == "corrected" and "column_shift" in table["reason"]
    assert not [flag for flag in result["verify"]["checks_after"] if flag["code"] == "no_column"]


def test_run_computes_checks_after_over_every_field_even_with_hint_paths(monkeypatch):
    """checks_after는 final(힌트로 좁힌 부분집합)이 아니라 ao_flat에 final을 얹은 전체 필드로 돌려야
    한다 — 안 그러면 힌트 밖 구성 필드가 빠져 sum_mismatch 같은 필드 간 검사가 묻힌다."""
    ao = {"documents": [{"doc_type": "진료비영수증", "extracted_fields": [
        {"key": "진료비총액", "value": "999999", "confidence": 0.9},
        {"key": "환자부담총액", "value": "300000", "confidence": 0.9},
        {"key": "공단부담총액", "value": "200000", "confidence": 0.9},
    ]}]}
    real_stub(monkeypatch, {"진료비총액": "999999"}, {})  # docraft가 AO와 같아 dispute 없이 agree

    result = verify.run("scan.png", ao, hint_paths=["진료비총액"])["documents"][0]

    assert set(field(result, key)["value"] for key in ("환자부담총액", "공단부담총액")) == {"300000", "200000"}
    assert "source" not in field(result, "환자부담총액")  # 힌트 밖이라 판정은 안 붙지만
    codes = {flag["code"] for flag in result["verify"]["checks_after"]}
    assert "sum_mismatch" in codes  # 999999 ≠ 300000+200000, 힌트 밖 구성 필드까지 봐야 잡힌다


# --- 라우트가 UI 형식을 받는지 ---------------------------------------------


def test_verify_route_accepts_the_ui_result_format(monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "run", lambda image, ao, doc_type=None, hint_paths=None: {"result": {"verify": {"counts": {}}}})

    response = post(_image(tmp_path), ao_result=json.dumps(UI), doc_type="진료비영수증")

    assert response.status_code == 200 and response.json()["result"]["verify"] == {"counts": {}}


def test_verify_route_rejects_a_payload_with_neither_documents_nor_result(tmp_path):
    response = post(_image(tmp_path), ao_result='{"result": 3}')

    assert response.status_code == 422 and "documents" in response.json()["detail"]


# ── 표 행 대응 ──────────────────────────────────────────────────────────────

def _detail(code, start, quantity):
    return {"항목": "식대", "EDI코드": code, "시작일자": start, "횟수": quantity}


def test_row_diff_ignores_row_order():
    """행 순서만 다른 표는 어긋난 곳이 없다 — 표 전체를 Judge에 다시 쓰게 하지 않는다."""
    rows = [_detail("A100", "20210101", "1"), _detail("A200", "20210102", "2")]

    assert verify._row_diff("세부내역서", "항목내역", rows, rows[::-1]) == []


def test_row_diff_reports_only_the_differing_cell_of_a_matched_row():
    ao = [_detail("A100", "20210101", "1"), _detail("A200", "20210102", "2")]
    mine = [_detail("A100", "20210101", "1"), _detail("A200", "20210102", "9")]

    assert verify._row_diff("세부내역서", "항목내역", ao, mine) == [
        {"row": 1, "column": "횟수", "ao": "2", "docraft": "9"}]


def test_row_diff_reports_a_row_only_one_side_read_as_a_whole_row():
    ao = [_detail("A100", "20210101", "1"), _detail("A200", "20210102", "2")]
    mine = [_detail("A100", "20210101", "1")]

    diff = verify._row_diff("세부내역서", "항목내역", ao, mine)

    assert diff == [{"row": 1, "ao": ao[1], "docraft": None}]


HANBANG_AO = [{"항목": "진찰료", "본인부담금": "2726", "공단부담금": "10904"},
              {"항목": "시술및처치료", "본인부담금": "71608", "공단부담금": "286032"},
              {"항목": "합계", "본인부담금": "74334", "공단부담금": "296936"}]
HANBANG_DOCRAFT = [{"항목": "진찰료", "본인부담금": "2720", "공단부담금": "10904"},  # 흐린 팩스 오독
                   {"항목": "시술및처치료", "본인부담금": "71808", "공단부담금": "288032"},
                   {"항목": "합계", "본인부담금": "74334", "공단부담금": "298936"}]


def test_balance_reverts_a_judged_table_that_breaks_the_totals():
    """이슈 정리 260923 현상 3 문서: Judge가 합계식에 안 맞는 Docraft 표를 골랐으면 합계식에 맞는 AO 표로 되돌린다."""
    ao = {"항목내역": HANBANG_AO, "진료비총액": "371270", "환자부담총액": "74334"}
    chosen = {"항목내역": (HANBANG_DOCRAFT, "docraft", "Judge"), "진료비총액": ("371270", "agree", None),
              "환자부담총액": ("74334", "agree", None)}

    value, source, reason = verify._balance("진료비영수증", chosen, ao, {"항목내역": HANBANG_DOCRAFT})["항목내역"]

    assert (value, source) == (HANBANG_AO, "ao") and "합계식" in reason


def test_balance_keeps_a_judgement_when_the_other_reading_is_empty_or_no_better():
    ao = {"항목내역": [], "진료비총액": "371270"}
    chosen = {"항목내역": (HANBANG_DOCRAFT, "docraft", "Judge"), "진료비총액": ("371270", "agree", None)}

    assert verify._balance("진료비영수증", dict(chosen), ao, {"항목내역": HANBANG_DOCRAFT}) == chosen  # 빈 표로 바꾸지 않는다
    assert rules.sum_errors("진료비영수증", {"항목내역": HANBANG_AO, "진료비총액": "371270"}) == 0
    assert rules.sum_errors("진료비영수증", {"항목내역": HANBANG_DOCRAFT, "진료비총액": "371270"}) > 0


def test_run_keeps_the_printed_subtotal_rows_of_a_detail_table(monkeypatch):
    """0922 재테스트: Docraft는 세부내역서 집계 행을 뽑지 않으므로 Judge가 Docraft 표를 골라도 AO의 인쇄된
    소계·합계 행은 원래 자리에 남아야 한다(지우면 인쇄된 행이 사라진다)."""
    columns = ["항목", "EDI코드", "EDI명칭", "총액"]
    rows = [["진찰료", "AA157", "초진진찰료", "18000"], ["소계", None, None, "18000"],
            ["검사료", "B1010", "일반혈액검사", "900"], ["소계", None, None, "900"], ["합계", None, None, "18900"]]
    ao = {"documents": [{"doc_type": "세부내역서", "extracted_fields": [], "extracted_tables": [{
        "key": "항목내역", "headers": columns, "rows": [[{"key": column, "value": value} for column, value in zip(columns, row)]
                                                    for row in rows]}]}]}
    docraft = {"항목내역": [{"항목": "진찰료", "EDI코드": "AA157", "EDI명칭": "초진진찰료", "총액": "18000"},
                        {"항목": "검사료", "EDI코드": "B1010", "EDI명칭": "일반혈액검사", "총액": "990"}]}
    seen = []
    real_stub(monkeypatch, docraft, {"항목내역": {"source": "docraft", "reason": "이미지"}})
    monkeypatch.setattr(verify, "judge", lambda image, doc_type, disputes: seen.append(disputes) or
                        {"항목내역": {"source": "docraft", "reason": "이미지"}})

    table = verify.run("scan.png", ao, doc_type="세부내역서")["documents"][0]["extracted_tables"][0]

    names = [row[0]["value"] for row in table["rows"]]
    assert names == ["진찰료", "소계", "검사료", "소계", "합계"]
    assert [row[3]["value"] for row in table["rows"]] == ["18000", "18000", "990", "900", "18900"]
    assert not any(rules.is_total(row) for row in seen[0]["항목내역"]["ao"])  # 집계 행은 판정에 보내지 않는다


def test_run_keeps_each_row_on_its_own_original_cells_when_a_row_is_inserted(monkeypatch):
    """0922 재테스트: 판정 표가 중간에 행을 끼우면 뒤쪽 행이 자리 번호가 같은 원래 행(합계)의 셀·예측값을
    물려받아 빈 행이 합계 값을 가진 것처럼 읽혔다. 행 짝짓기로 원래 셀을 찾는다."""
    columns = ["항목", "본인부담금"]
    rows = [["진찰료", "848"], ["예약진찰료", ""], ["합계", "2000"]]
    ao = {"documents": [{"doc_type": "진료비영수증", "extracted_fields": [], "extracted_tables": [{
        "key": "항목내역", "headers": columns, "rows": [[{"key": column, "value": value, "predicted_value": value, "confidence": 0.9}
                                                    for column, value in zip(columns, row)] for row in rows]}]}]}
    docraft = {"항목내역": [{"항목": "진찰료", "본인부담금": "848"}, {"항목": "선별급여", "본인부담금": None},
                        {"항목": "예약진찰료", "본인부담금": None}, {"항목": "합계", "본인부담금": "2000"}]}
    real_stub(monkeypatch, docraft, {"항목내역": {"source": "docraft", "reason": "이미지"}})

    document = verify.run("scan.png", ao, doc_type="진료비영수증")["documents"][0]
    table = document["extracted_tables"][0]

    assert [[cell["value"] for cell in row] for row in table["rows"]] == [
        ["진찰료", "848"], ["선별급여", None], ["예약진찰료", None], ["합계", "2000"]]
    assert table["rows"][2][1]["ao_value"] == "" and table["rows"][3][1]["ao_value"] == "2000"
    assert [row["본인부담금"] for row in verify.flatten(document)["항목내역"]] == ["848", None, None, "2000"]
