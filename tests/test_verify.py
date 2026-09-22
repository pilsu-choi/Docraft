"""AO 교차검증(`backend.verify`)과 `POST /api/verify`. doctypes/rules는 monkeypatch로 대체한다."""

import glob
import json
from copy import deepcopy

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
                 "rows": [{"병명코드": "R634", "병명": "이상체중감소"}, {"병명코드": "M8199", "병명": "골다공증"}]},
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
    monkeypatch.setattr(rules, "apply", lambda doc_type, result, blocks: deepcopy(docraft))
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
    assert output["documents"][0]["verify"]["counts"] == {"agree": 6, "ao": 0, "docraft": 0, "corrected": 0}


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
    assert output["documents"][0]["verify"]["counts"] == {"agree": 2, "ao": 1, "docraft": 1, "corrected": 2}
    assert AO == original


def test_run_rebuilds_table_rows_from_the_verdict_keeping_the_cell_format(monkeypatch):
    stub(monkeypatch)

    table = verify.run("scan.png", AO)["documents"][0]["extracted_tables"][0]

    assert table["source"] == "corrected" and len(table["rows"]) == 2
    assert [cell["key"] for cell in table["rows"][0]] == ["병명코드", "병명"]
    assert table["rows"][0][0]["confidence"] == 0.97  # 원래 셀이 있으면 형식을 보존한다
    assert table["rows"][0][0]["ao_value"] == "R634"
    assert [cell["value"] for cell in table["rows"][1]] == ["M8199", "골다공증"]
    assert table["rows"][1][0]["ao_value"] is None
    # 판정이 늘린 행은 열 셀의 형식만 빌리고 원래 값은 남기지 않는다.
    assert all(table["rows"][1][0][name] is None for name in ("confidence", "predicted_value"))
    assert table["rows"][1][1]["docraft_value"] == "골다공증"
    assert table["rows"][1][1]["reason"] == "부상병 행이 빠졌다"


def test_run_keeps_the_ao_value_when_the_judge_leaves_a_field_out(monkeypatch):
    stub(monkeypatch, judged={})

    document = verify.run("scan.png", AO)["documents"][0]

    assert field(document, "병원명")["value"] == "고려대병원"
    assert field(document, "병원명")["source"] == "ao"
    assert field(document, "병원명")["reason"] == verify.NO_VERDICT


def test_run_rejects_a_document_type_it_has_no_fields_for(monkeypatch):
    stub(monkeypatch)

    with pytest.raises(ValueError, match="지원하지 않는 문서 유형"):
        verify.run("scan.png", AO, doc_type="약제비영수증")
    with pytest.raises(ValueError, match="documents"):
        verify.run("scan.png", {"documents": []})


def test_run_prefers_the_requested_document_type_over_the_ao_one(monkeypatch):
    calls = stub(monkeypatch)
    monkeypatch.setitem(doctypes.DOC_TYPES, "소견서", {})

    verify.run("scan.png", AO, doc_type="소견서")

    assert calls[0][1] == "소견서"


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
    assert FakeClient.requests[0][1]["json"]["response_format"] == {"type": "json_object"}


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
    monkeypatch.setattr(verify, "run", lambda image, ao, doc_type=None: seen.append((image, doc_type)) or {
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
