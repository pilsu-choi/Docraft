"""Docraft 순수 읽기(`backend.verify.read`)와 `POST /api/read`. `test_verify.py`의 스텁을 재사용한다."""

import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend import engine, rules, verify
from backend.main import app
from test_verify import DOCRAFT, _image, hinted_stub, stub

client = TestClient(app)


def post_read(path, doc_type="진단서", **data):
    with open(path, "rb") as handle:
        return client.post("/api/read", files={"image": (path.name, handle, "image/png")},
                           data={"doc_type": doc_type, **data})


# --- verify.resolve_doc_type / resolve_keys -------------------------------


def test_resolve_doc_type_maps_an_alias_to_its_canonical_name():
    assert verify.resolve_doc_type("약제영수증") == "약제비영수증"
    assert verify.resolve_doc_type("진단서") == "진단서"


def test_resolve_doc_type_rejects_an_unsupported_type():
    with pytest.raises(ValueError, match="지원하지 않는 문서 유형"):
        verify.resolve_doc_type("처방전")


def test_resolve_keys_returns_none_when_omitted_or_empty():
    assert verify.resolve_keys("진단서", None) is None
    assert verify.resolve_keys("진단서", []) is None


def test_resolve_keys_drops_unknown_keys_and_warns_once(caplog):
    with caplog.at_level("WARNING"):
        only = verify.resolve_keys("진단서", ["진단일", "없는키"], label="keys")

    assert only == {"진단일"}
    assert caplog.text.count("없는키") == 1
    assert "keys" in caplog.text


def test_resolve_keys_raises_when_no_key_is_valid():
    with pytest.raises(ValueError, match="keys"):
        verify.resolve_keys("진단서", ["없는키"], label="keys")


# --- verify.read -----------------------------------------------------------


def test_read_restricts_the_extraction_schema_and_returns_docraft_and_blocks(monkeypatch):
    _, schemas = hinted_stub(monkeypatch)

    doc_type, fields, blocks = verify.read("scan.png", "진단서", {"병원명", "병명내역"})

    assert doc_type == "진단서"
    assert set(schemas[0]["properties"]) == {"병원명", "병명내역"}
    assert fields == DOCRAFT  # 스텁의 고정 docraft(전체 필드), only는 추출 스키마만 좁힌다
    assert blocks == [{"text": "x"}]


def test_read_without_only_uses_the_full_schema(monkeypatch):
    _, schemas = hinted_stub(monkeypatch)

    verify.read("scan.png", "진단서", None)

    assert set(schemas[0]["properties"]) == {"진단일", "진단명", "병원명", "면허번호", "환자명", "병명내역"}


def test_read_groundings_keep_normalized_scalar_and_drop_changed_value():
    source = {"page": 1, "bbox": [10, 20, 90, 40], "source_text": "2026.09.27", "confidence": 1.0}
    raw = {"진단일": "2026.09.27", "병원명": "원래 병원"}
    final = {"진단일": "20260927", "병원명": "바뀐 병원"}
    grounds = {key: source for key in raw}

    result = verify._read_groundings("진단서", raw, final, grounds)

    assert result == {"진단일": {**source, "basis": "image_pixel"}}


def test_read_groundings_match_reordered_rows_and_leave_derived_or_duplicate_rows_empty():
    def source(index):
        return {"page": 1, "bbox": [index * 10, 1, index * 10 + 9, 8],
                "source_text": f"질병 {index}", "confidence": 1.0}

    raw = {"병명내역": [
        {"병명코드": "A01.0", "병명": "첫째"},
        {"병명코드": "B02.1", "병명": "둘째"},
        {"병명코드": "D04.2", "병명": "중복"},
        {"병명코드": "D04.2", "병명": "중복"},
    ]}
    grounds = {"병명내역": {str(i): {"병명코드": source(i), "병명": source(i)} for i in range(4)}}
    final = {"병명내역": [{"병명코드": "B021", "병명": "둘째"}, {"병명코드": "C030", "병명": "추가"},
                           {"병명코드": "A010", "병명": "첫째"}, {"병명코드": "D042", "병명": "중복"}]}

    rows = verify._read_groundings("진단서", raw, final, grounds)["병명내역"]

    assert [row.get("병명코드", {}).get("bbox") for row in rows] == [[10, 1, 19, 8], None, [0, 1, 9, 8], None]


def test_read_groundings_drop_modified_and_low_confidence_cells():
    source = {"page": 1, "bbox": [1, 2, 3, 4], "source_text": "원문", "confidence": 1.0}
    raw = {"병명내역": [{"병명코드": "A1", "병명": "원래"}]}
    grounds = {"병명내역": {"0": {"병명코드": source, "병명": source}}}
    changed = {"병명내역": [{"병명코드": "A1", "병명": "교정됨"}]}

    assert verify._read_groundings("진단서", raw, changed, grounds) == {"병명내역": [{}]}
    assert verify._read_groundings("진단서", {"병원명": "원문"}, {"병원명": "원문"},
                                   {"병원명": {**source, "confidence": 0.5}}) == {}


def test_read_stops_before_extract_once_cancelled(monkeypatch):
    import threading

    stub(monkeypatch)
    cancel = threading.Event()
    cancel.set()
    calls = []
    monkeypatch.setattr(engine, "extract", lambda *a, **k: calls.append(1))

    with pytest.raises(verify.Cancelled):
        verify.read("scan.png", "진단서", None, cancel=cancel)

    assert calls == []  # 파싱 뒤 추출 전에 멈췄다


def test_verify_run_uses_read_for_its_own_parse_extract_apply(monkeypatch):
    """run()이 read()를 통해 같은 parse→extract→rules.apply 경로를 타는지(중복 구현 없음)."""
    calls = []
    real_read = verify.read
    monkeypatch.setattr(verify, "read", lambda *a, **k: calls.append((a, k)) or real_read(*a, **k))
    stub(monkeypatch)
    ao = {"documents": [{"doc_type": "진단서", "extracted_fields": [{"key": "진단일", "value": "20230228"}]}]}

    verify.run("scan.png", ao)

    assert len(calls) == 1 and calls[0][0][:2] == ("scan.png", "진단서")


# --- route -------------------------------------------------------------


def test_read_route_returns_the_contract_shape_with_all_fields_when_keys_is_omitted(monkeypatch, tmp_path):
    hinted_stub(monkeypatch)

    response = post_read(_image(tmp_path))
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {"doc_type", "fields", "groundings", "field_quality", "elapsed_ms"}
    assert body["doc_type"] == "진단서"
    assert isinstance(body["elapsed_ms"], int)
    assert body["fields"] == DOCRAFT  # 스텁의 고정 docraft(전체 필드), AO 비교·판정 정보 없음
    assert body["groundings"] == {"병명내역": [{}, {}]}


def test_read_route_returns_verified_grounding_for_requested_key(monkeypatch, tmp_path):
    hinted_stub(monkeypatch)
    source = {"page": 1, "bbox": [10, 20, 90, 40], "source_text": "원본 병원", "confidence": 0.9}
    monkeypatch.setattr(engine, "extract", lambda *a, **k: ({"병원명": "원본 병원"}, {"병원명": source}))
    monkeypatch.setattr(rules, "apply", lambda *a, **k: {"병원명": "원본 병원", "진단일": "추론값"})

    response = post_read(_image(tmp_path), keys=json.dumps(["병원명"]))

    assert response.status_code == 200
    assert response.json()["fields"] == {"병원명": "원본 병원"}
    assert response.json()["groundings"] == {"병원명": {**source, "basis": "image_pixel"}}


def test_read_route_restricts_fields_to_the_requested_keys(monkeypatch, tmp_path):
    hinted_stub(monkeypatch)

    response = post_read(_image(tmp_path), keys=json.dumps(["병원명"]))

    assert response.status_code == 200
    assert set(response.json()["fields"]) == {"병원명"}
    assert response.json()["fields"]["병원명"] == DOCRAFT["병원명"]


def test_read_route_rejects_an_unsupported_doc_type(tmp_path):
    response = post_read(_image(tmp_path), doc_type="처방전")

    assert response.status_code == 422 and "지원하지 않는 문서 유형" in response.json()["detail"]


def test_read_route_rejects_invalid_keys_json(tmp_path):
    response = post_read(_image(tmp_path), keys="not json")

    assert response.status_code == 422 and "keys" in response.json()["detail"]


def test_read_route_rejects_a_non_list_keys(tmp_path):
    response = post_read(_image(tmp_path), keys=json.dumps({"key": "병원명"}))

    assert response.status_code == 422 and "keys" in response.json()["detail"]


def test_read_route_returns_no_fields_when_no_key_is_defined_for_the_doc_type(tmp_path):
    response = post_read(_image(tmp_path), doc_type="진단서", keys=json.dumps(["사고발생일자"]))

    assert response.status_code == 200 and response.json() == {"doc_type": "진단서", "fields": {}, "groundings": {}, "field_quality": {}, "elapsed_ms": 0}


def test_read_route_rejects_a_non_image_upload(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.4")

    response = post_read(path)

    assert response.status_code == 415
    assert "이미지 파일만" in response.json()["detail"]


def test_read_route_rejects_a_multi_page_tif(monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "read", lambda *args, **kwargs: pytest.fail("다중 페이지 문서는 처리하면 안 된다"))

    response = post_read(_image(tmp_path, "scan.tif", frames=2))

    assert response.status_code == 422
    assert response.json()["detail"] == "다중 페이지 문서는 아직 지원하지 않습니다."


def test_read_route_cancels_the_run_when_the_client_disconnects(monkeypatch, tmp_path):
    def fake_read(path, doc_type, only, cancel=None, with_groundings=False):
        assert cancel.wait(5)
        raise verify.Cancelled

    async def gone(self): return True
    monkeypatch.setattr(verify, "read", fake_read)
    monkeypatch.setattr(Request, "is_disconnected", gone)

    assert post_read(_image(tmp_path)).status_code == 499
    assert client.get("/api/health").json()["verify_inflight"] == 0


def test_read_route_turns_a_provider_failure_into_a_gateway_error(monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "read", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("AI provider 요청 실패")))

    response = post_read(_image(tmp_path))

    assert response.status_code == 502 and "읽기에 실패" in response.json()["detail"]


def test_read_route_shares_the_inflight_counter_with_verify(monkeypatch, tmp_path):
    """/api/health의 verify_inflight는 이름은 그대로지만 /api/verify·/api/read 처리 중 요청을 함께 센다."""
    import backend.main as main
    assert main.INFLIGHT == 0
    monkeypatch.setattr(verify, "read", lambda *a, **k: ("진단서", {}, [], {}))

    response = post_read(_image(tmp_path))

    assert response.status_code == 200
    assert main.INFLIGHT == 0
