"""doctypes 스키마와 rules 정규화·보충 룰(twin reader 이식분) 테스트."""

import types
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend import doctypes, rules, verify

AO_SAMPLES = Path("/home/pilsu/projects/mirae-assets/harness-v2/docs/agentic-ocr-2.0.1-results")
# AO 2.0.1 예시(2026-09-09) 뒤 고객사 추출 스키마에 생긴 키. 예시 응답에는 없다(2026-10-05 약제영수증 스키마의 비급여 열, 진단서4종 스키마의 진료소견).
AO_LATER_KEYS = {"약제비영수증": {"진료비내역-비급여"}, **dict.fromkeys(("진단서", "소견서", "수술확인서", "입퇴원확인서"), {"진료소견"})}


@pytest.fixture(autouse=True)
def no_required(monkeypatch):
    """다른 룰 테스트의 작은 문서가 필수 필드·항목 누락으로 걸리지 않게 한다. 누락 룰 테스트는 ``REQUIRED``·``REQUIRED_ITEMS``를 직접 둔다."""
    monkeypatch.setattr(rules, "REQUIRED", {})
    monkeypatch.setattr(rules, "REQUIRED_ITEMS", {})


def block(text="", rows=None, kind="text", lines=None):
    return {"type": kind, "page": 1, "bbox": None, "text": text, "rows": rows, "lines": lines}


# ── 정규화 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("2023.02.28", "20230228"),
    ("2023-2-8", "20230208"),
    ("2023/02/28", "20230228"),
    ("2023년 2월 28일", "20230228"),
    ("20230228", "20230228"),
    ("230228", "20230228"),
    ("23.1.2", "20230102"),
    ("99.12.31", "19991231"),
    ("50.1.1", "19500101"),
    ("49.1.1", "20490101"),
    ("진단연월일: 2021/7/9", "20210709"),
    ("2023.02.30", None),           # 달력에 없는 날
    ("2023.02.29", None),           # 윤일 아님
    ("2024.02.29", "20240229"),     # 윤일
    ("1234567890123", None),        # 주민번호 13자리는 날짜가 아니다
    ("2O25.O1.l2", "20250112"),     # 숫자에 붙은 O·l은 0·1 오독
    ("2025년 O1월 I2일", "20250112"),
    ("Oct 2025.01.12", "20250112"),  # 숫자에 붙지 않은 글자는 둔다
    ("", None),
])
def test_date_normalize(raw, expected):
    assert rules.normalize("date", raw) == expected


def test_dates_normalize_keeps_order_and_dedups():
    raw = "['20210819', '20210826', '2021.08.19']"
    assert rules.normalize("dates", raw) == "20210819, 20210826"
    assert rules.normalize("dates", "2023.1.2 ~ 2023.1.5") == "20230102, 20230105"


@pytest.mark.parametrize("raw, expected", [
    ("12,380원", "12380"),
    ("I2,3OO", "12300"),          # I→1, O→0
    ("B00", "800"),               # B→8
    ("b00", "600"),               # b→6
    ("1ㅇㅇ", "100"),              # ㅇ→0
    ("1이이", "100"),              # 이→0
    ("000", "0"),
    ("0012380", "12380"),
    ("  ", None),
    ("-", None),
    ("954.5", "954.5"),           # 세부내역서 소수 단가(0922 재테스트: 9545로 10배가 됐다)
    ("676,782.5", "676782.5"),
    ("19160.0", "19160"),         # .0은 정수
    ("1.234", "1234"),            # 소수 세 자리는 천 단위 구분
    ("-42,360", "-42360"),        # 음수 부호를 살린다(0922 재테스트: 모델이 읽은 부호가 정규화에서 사라졌다)
    ("−6", "-6"), ("△1,200", "-1200"), ("-0", "0"),
])
def test_amount_normalize(raw, expected):
    assert rules.normalize("amount", raw) == expected


@pytest.mark.parametrize("raw, expected", [("1,5", "1.5"), ("2 x 3", "6"), ("1.5x2", "3"), ("3회", "3"), ("없음", None)])
def test_number_normalize(raw, expected):
    assert rules.normalize("number", raw) == expected


def test_idnum_phone_code_bool_normalize():
    assert rules.normalize("idnum", "880101 - 1234567") == "880101-1234567"
    assert rules.normalize("idnum", "880101-1******") == "880101-1******"
    assert rules.normalize("idnum", "이름없음") is None
    assert rules.normalize("phone", "(02) 123-4567") == "02-123-4567"
    assert rules.normalize("phone", "02-123-4567 / FAX 02-000-1111") == "02-123-4567"
    assert rules.normalize("code", "j20.9") == "J209"        # 점은 지운다
    assert rules.normalize("code", "020.9") == "D209"        # 앞자리 0 → D
    assert rules.normalize("code", "163") == "I63"           # 앞자리 1 → I
    assert rules.normalize("code", "S8260 M5136") == "S8260, M5136"
    assert rules.same("code", "R63.4", "R634")                # AO 표기(점 없음)와 같아진다
    assert rules.normalize("bool", "[V]") == "Y"
    assert rules.normalize("bool", "") == "N"
    assert rules.normalize("bool", None) is None


@pytest.mark.parametrize("kind, a, b", [
    ("amount", None, "0"),                       # 빈 금액 칸과 0은 같다
    ("amount", "", "0원"),
    ("number", None, "0"),
    ("text", "(주상병)이상체중감소", "이상체중감소"),   # 접두가 붙은 쪽을 같게 본다
    ("text", "급성기관지염", "급성 기관지염(의증)"),
])
def test_same_is_lenient_about_empty_amounts_and_wrapped_text(kind, a, b):
    assert rules.same(kind, a, b) and rules.same(kind, b, a)


@pytest.mark.parametrize("kind, a, b", [
    ("amount", None, "1000"),
    ("text", None, "이상체중감소"),
    ("text", "가", "가나다"),                      # 한 글자는 품고 있어도 같다고 보지 않는다
    ("text", "외과", "정형외과"),                   # 세 글자 이하는 품고 있어도 다른 값이다
    ("text", "이상체중감소", "체중증가"),
])
def test_same_still_separates_different_values(kind, a, b):
    assert not rules.same(kind, a, b) and not rules.same(kind, b, a)


def test_row_diff_follows_the_lenient_comparison():
    """표 비교도 같은 규칙을 따른다: 빈 금액 칸 = 0, 접두가 붙은 항목명 = 같은 항목."""
    ao = [{"항목": "초음파진단료", "본인부담금": "1000", "비급여": None}]
    mine = [{"항목": "(기본항목)초음파진단료", "본인부담금": "1,000", "비급여": "0"}]

    assert verify._row_diff("진료비영수증", "항목내역", ao, mine) == []
    assert verify._row_diff("진료비영수증", "항목내역", ao, [{**mine[0], "본인부담금": "2000"}]) == [
        {"row": 0, "column": "본인부담금", "ao": "1000", "docraft": "2000"}]


def test_same_compares_after_normalizing():
    assert rules.same("date", "2023.2.28", "20230228")
    assert rules.same("dates", "20210819, 20210826", "20210826, 20210819")   # 집합 비교
    assert rules.same("text", "급성 기관지염", "급성기관지염!")
    assert rules.same("amount", "12,380원", "12380")
    assert rules.same("text", None, None)
    assert not rules.same("text", None, "가")
    assert not rules.same("date", "20230228", "20230227")


# ── 필드별 정제·파생 ────────────────────────────────────────────────────────

def test_name_hospital_address_cleanup():
    out = rules.apply("진단서", {"이름": "김철수김철수", "의사명": "의사 홍길동 제12345호",
                                "병원명": "명칭: 서울정형외과의원(직인)", "주소": "주소: 서울시 강남구 1로 2 (02-123-4567)"}, [])
    assert out["이름"] == "김철수"
    assert out["의사명"] == "홍길동"
    assert out["병원명"] == "서울정형외과의원"
    assert out["주소"] == "서울시 강남구 1로 2"
    assert rules.apply("진단서", {"병원명": "서울대학병"}, [])["병원명"] == "서울대학병원"
    assert rules.apply("진단서", {"병원명": "한사랑의과의원"}, [])["병원명"] == "한사랑외과의원"


@pytest.mark.parametrize("raw, expected", [
    ("홍길동 (인)", "홍길동"),
    ("홍길동 인", "홍길동"),
    ("홍길동(印)", "홍길동"),
    ("김인수", "김인수"),   # 이름 안의 "인"은 날인 표시가 아니다
    ("이인", "이인"),       # 이름 안의 "인"은 날인 표시가 아니다
])
def test_name_seal_mark_removed(raw, expected):
    assert rules.apply("진단서", {"이름": raw}, [])["이름"] == expected


def test_gender_and_birthday_derived_from_idnum():
    out = rules.apply("진단서", {"환자 주민번호": "880101-1234567"}, [])
    assert (out["성별"], out["생년월일"]) == ("남", "19880101")
    assert rules.apply("진단서", {"환자 주민번호": "050101-4******"}, [])["성별"] == "여"
    assert rules.apply("진단서", {"환자 주민번호": "050101-4******"}, [])["생년월일"] == "20050101"
    assert rules.apply("진단서", {"환자 주민번호": "880101-1234567", "성별": "male"}, [])["성별"] == "남"


def test_disease_code_split_from_name():
    out = rules.apply("진단서", {"병명내역": [{"병명코드": None, "병명": "(J20.9) 급성 기관지염"}]}, [])
    assert out["병명내역"] == [{"병명코드": "J209", "병명": "급성 기관지염"}]


def test_accident_date_is_earliest_or_treatment_start():
    receipt = rules.apply("진료비영수증", {"환자정보-진료시작일": "2019.11.22"}, [])
    assert receipt["사고발생일자"] == "20191122"
    detail = rules.apply("세부내역서", {"환자정보(진료시작일)": "20230311"}, [])
    assert detail["사고발생일자"] == "20230311"


def test_detail_stay_kind_from_room():
    assert rules.apply("세부내역서", {"환자정보(병실)": "1203호"}, [])["환자정보(입통원구분)"] == "입원"
    assert rules.apply("세부내역서", {"환자정보(병실)": "8W/865"}, [])["환자정보(입통원구분)"] == "입원"
    assert rules.apply("세부내역서", {"환자정보(병실)": "외래"}, [])["환자정보(입통원구분)"] == "통원"


def test_receipt_visit_code_and_enum_synonyms():
    out = rules.apply("진료비영수증", {"환자정보-환자구분": "보험외래"}, [])
    assert out["외래/입원"] == "02"                                   # 외래 → 02
    assert rules.apply("진료비영수증", {"외래/입원": "입원"}, [])["외래/입원"] == "01"


# ── 블록에서 빠진 값 보충 ───────────────────────────────────────────────────

def test_fill_from_table_row():
    blocks = [block(kind="table", rows=[["진단연월일", "", "2023. 2. 28."], ["의료기관명칭", "서울정형외과의원"]])]
    out = rules.apply("진단서", {"진단일": None, "병원명": None}, blocks)
    assert out["진단일"] == "20230228"
    assert out["병원명"] == "서울정형외과의원"


def test_fill_from_text_block():
    blocks = [block(text="환자성명: 홍길동\n주민등록번호 : 880101-1234567\n발급일 2023.03.02")]
    out = rules.apply("진단서", {"이름": None, "환자 주민번호": None, "발급일": None}, blocks)
    assert (out["이름"], out["환자 주민번호"], out["발급일"]) == ("홍길동", "880101-1234567", "20230302")
    assert out["성별"] == "남"      # 보충된 주민번호에서 파생된다


def test_fill_uses_lines_when_text_is_empty():
    blocks = [block(text="", lines=[{"text": "면허번호 제 12345 호", "bbox": None}])]
    assert rules.apply("진단서", {"면허번호": None}, blocks)["면허번호"] == "12345"


def test_fill_keeps_hospital_values_out_of_the_patient_columns():
    """의료기관 칸에서 읽은 주소·연락처는 환자 칸을 채우지 않는다(영역 제약)."""
    blocks = [block(kind="table", rows=[["환자의 성명", "홍길동"]]),
              block(text="의료기관 명칭 : 서울정형외과의원\n주소 : 서울특별시 도봉구 창동 650\n전화번호 : 02-123-4567")]
    out = rules.apply("진단서", {"주소": None, "병원주소": None, "연락처": None, "병원연락처": None}, blocks)
    assert out["병원주소"] == "서울특별시 도봉구 창동 650"
    assert out["병원연락처"] == "02-123-4567"
    assert (out["주소"], out["연락처"]) == (None, None)


def test_fill_does_not_reuse_a_value_another_field_already_holds():
    """이름류는 한 무리 안에서 상호배제한다 — 환자 이름이 의사명으로 되풀이되지 않는다."""
    blocks = [block(text="위와 같이 진단합니다.\n의사 성명 : 홍길동")]
    assert rules.apply("진단서", {"이름": "홍길동", "의사명": None}, blocks)["의사명"] is None
    assert rules.apply("진단서", {"이름": None, "의사명": None}, blocks)["의사명"] == "홍길동"


def test_fill_skips_when_candidates_of_the_same_rank_disagree():
    blocks = [block(kind="table", rows=[["진단연월일", "2023.02.28"], ["진단연월일", "2023.03.05"]])]
    assert rules.apply("진단서", {"진단일": None}, blocks)["진단일"] is None


def test_fill_leaves_an_empty_form_cell_empty():
    """서식에 그 필드의 라벨 칸이 있는데 비어 있으면 더 약한 근거로 채우지 않는다."""
    blocks = [block(kind="table", rows=[["환자의 성명", "홍길동"], ["환자의 주소", ""]]),
              block(text="환자 정보\n주소 : 서울특별시 도봉구 창동 650")]
    assert rules.apply("진단서", {"주소": None}, blocks)["주소"] is None


def test_fill_rejects_form_options_and_label_fragments():
    options = [block(text="의료기관 명칭 : 서울정형외과의원\n[ ▣ ] 의사 [ ] 치과의사 [ ] 한의사 면허번호 제")]
    assert rules.apply("진단서", {"의사명": None}, options)["의사명"] is None
    fragment = [block(kind="table", rows=[["질병군(DRG)번호", "4 환자구분"], ["성명", "홍길동"]])]
    assert rules.apply("진료비영수증", {"환자정보-질병군(DRG)번호": None}, fragment)["환자정보-질병군(DRG)번호"] is None


def test_care_period_takes_the_first_and_the_last_date():
    blocks = [block(kind="table", rows=[["진료기간", "2019.09.15 ~ 2019.10.15"]])]
    out = rules.apply("진료비영수증", {"환자정보-진료시작일": None, "환자정보-진료종료일": None}, blocks)
    assert (out["환자정보-진료시작일"], out["환자정보-진료종료일"]) == ("20190915", "20191015")


def test_report_diagnosis_date_needs_its_own_label():
    """소견서에 원래 드문 진단일은 제 이름 라벨이 있을 때만 채운다."""
    blocks = [block(text="소견일 : 2020.10.05")]
    assert rules.apply("소견서", {"진단일": None}, blocks)["진단일"] is None
    assert rules.apply("진단서", {"진단일": None}, blocks)["진단일"] == "20201005"


def test_total_row_moves_to_total_fields():
    rows = [{"항목": "진찰료", "본인부담": "1,000", "공단부담": "2,000"},
            {"항목": "합 계", "본인부담": "5,000", "공단부담": "7,000"}]
    out = rules.apply("세부내역서", {"항목내역": rows}, [])
    assert [row["항목"] for row in out["항목내역"]] == ["진찰료", "합계"]  # 세부내역서 집계 행은 표준 라벨로 남는다
    assert (out["급여_본인부담총액"], out["급여_공단부담총액"]) == ("5000", "7000")


def test_apply_does_not_mutate_input():
    result = {"진단일": "2023.02.28", "병명내역": [{"병명코드": None, "병명": "(J20.9) 급성 기관지염"}]}
    snapshot = json.dumps(result, ensure_ascii=False)
    rules.apply("진단서", result, [block(text="발급일 2023.03.02")])
    assert json.dumps(result, ensure_ascii=False) == snapshot


def test_apply_returns_every_field_of_the_doc_type():
    for doc_type, spec in doctypes.DOC_TYPES.items():
        out = rules.apply(doc_type, {}, [])
        assert set(out) == set(spec["fields"]) | set(spec["tables"])
        assert all(out[table] == [] for table in spec["tables"])


# ── 스키마 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("doc_type", list(doctypes.DOC_TYPES))
def test_schema_is_valid_json_schema(doc_type):
    schema = doctypes.schema(doc_type)
    Draft202012Validator.check_schema(schema)
    assert schema["title"] == doc_type
    assert json.dumps(schema, ensure_ascii=False)
    for key, prop in schema["properties"].items():
        assert prop.get("description"), key
        if prop["type"] == "array":
            assert prop["items"]["properties"]
    sample = {key: None for key in schema["properties"]}
    sample.update({table: [] for table, prop in schema["properties"].items() if prop["type"] == "array"})
    Draft202012Validator(schema).validate(sample)


@pytest.mark.parametrize("doc_type", list(doctypes.DOC_TYPES))
def test_every_field_has_a_known_kind(doc_type):
    spec = doctypes.DOC_TYPES[doc_type]
    for key, meta in spec["fields"].items():
        assert meta["kind"] in doctypes.KINDS
        assert doctypes.kind(doc_type, key) == meta["kind"]
    for table, columns in spec["tables"].items():
        for column, meta in columns.items():
            assert meta["kind"] in doctypes.KINDS
            assert doctypes.kind(doc_type, column, table) == meta["kind"]


def _ao_keys(doc_type):
    """AO 예시 응답의 유형별 키: (스칼라·그룹 키 집합, {표 key: 열 키 집합})."""
    scalars, tables = set(), {}
    for path in sorted((AO_SAMPLES / doc_type).glob("*.json")):
        for document in json.loads(path.read_text())["documents"]:
            if doctypes.ALIASES.get(document["doc_type"], document["doc_type"]) != doc_type:
                continue
            scalars |= {field["key"] for field in document.get("extracted_fields") or []}
            for group in document.get("extracted_groups") or []:
                scalars |= {field["key"] for field in group.get("fields") or []}
            for table in document.get("extracted_tables") or []:
                tables.setdefault(table["key"], set()).update(table.get("headers") or [])
    return scalars, tables


@pytest.mark.skipif(not AO_SAMPLES.exists(), reason="AO 예시 응답이 없는 환경")
@pytest.mark.parametrize("doc_type", list(doctypes.DOC_TYPES))
def test_schema_covers_every_ao_key(doc_type):
    scalars, tables = _ao_keys(doc_type)
    assert scalars, f"{doc_type} 예시 키를 읽지 못했다"
    scalars = {"상한액초과금" if key == "상환액초과금" else key for key in scalars}  # AO 2.0.1 예시의 옛 오기 키
    properties = doctypes.schema(doc_type)["properties"]
    # 표가 있는 문서에서는 표로 나오는 내역 필드는 표로만 정의한다.
    assert scalars <= set(properties), scalars - set(properties)
    for table, headers in tables.items():
        assert table in properties, table
        assert headers <= set(properties[table]["items"]["properties"]), headers


@pytest.mark.skipif(not AO_SAMPLES.exists(), reason="AO 예시 응답이 없는 환경")
@pytest.mark.parametrize("doc_type", ["수술확인서", "입퇴원확인서", "약제비영수증"])
def test_schema_matches_ao_keys_and_order_exactly(doc_type):
    document = json.loads(next((AO_SAMPLES / doc_type).glob("*.json")).read_text())["documents"][0]
    order = [field["key"] for field in document["extracted_fields"]]
    order += [field["key"] for group in document["extracted_groups"] for field in group["fields"]]
    spec = doctypes.spec(doc_type)
    # 값이 없는 표를 AO는 "[]" 스칼라로 내므로 스칼라·표 키를 합쳐 비교한다.
    later = AO_LATER_KEYS.get(doc_type, set())
    assert set(order) | {table["key"] for table in document["extracted_tables"]} | later == set(doctypes.schema(doc_type)["properties"])
    assert [key for key in order if key in spec["fields"]] == [key for key in spec["fields"] if key not in later]


@pytest.mark.parametrize("doc_type", ["진단서", "소견서", "수술확인서", "입퇴원확인서"])
def test_clinical_opinion_is_text_field(doc_type):
    assert doctypes.spec(doc_type)["fields"]["진료소견"]["kind"] == "text"


# --- 진료비영수증 이상 검출·교정 (rules.check / rules.correct) ----------------

CASES = "/home/pilsu/projects/mirae-assets/harness-v2/docs/requirements"
# 머리글에 급여가 본인부담금·공단부담금을 묶는 제목으로만 있고 비급여는 독립 열인 실제 서식.
RECEIPT_BLOCKS = [{"type": "table", "rows": [["환자등록번호", "환자성명"], ["항 목", "급 여", "", "비급여④"],
                                             ["일부", "본인부담", "전액본인"], ["본인부담금①", "공단부담금②", "부담③"]]}]


def receipt(*rows):
    """항목·금액만 적은 간이 항목내역. 빠뜨린 열은 0으로 채운다."""
    return [{"항목": name, **{column: "0" for column in rules.ITEM_COLUMNS}, **amounts} for name, amounts in rows]


def case(folder, name):
    """오류 케이스 폴더의 AO UI 결과를 정규 dict으로. 파일이 없으면 건너뛴다."""
    path = Path(CASES) / folder / "latest" / name
    if not path.exists():
        pytest.skip(f"케이스 파일이 없습니다: {path}")
    return verify.flatten(verify.document(json.loads(path.read_text(encoding="utf-8"))))


@pytest.mark.parametrize("name, expected", [
    ("입원료 1인실", "입원료_1인실"), ("입원료 2·3인실", "입원료_2-3인실"), ("입원료 4인실 이상", "입원료_4인실이상"),
    ("투약 행위료", "투약및조제료_행위료"), ("주사료 약품비", "주사료_약품비"), ("식 대", "식대"),
    ("계", "합계"), ("보철·교정료", "보철교정료"), ("", None),
    ("필투약및조제료_행위료", "투약및조제료_행위료"), ("필주사료_약품비", "주사료_약품비"),  # 서식 분류 칸 글자
    ("선택항목_CT진단료", "CT진단료"), ("선택항목_기타", "기타"),
    ("선별급여", "선별급여"), ("선택진료료", "선택진료료"), ("필름대", "필름대"),  # 뗀 나머지가 표준 항목이 아니면 둔다
    ("「국민건강보험법 제41조의4에 따른 요양급여」", "선별급여"), ("시행령 별표2 제4호의 요양급여", "선별급여"),
    ("시행및처치료", "시술및처치료"), ("치료제료대", "치료재료대"),  # 한 글자 OCR 오독(이슈 정리 260923)
    ("영상진단및방사선", "영상진단및방사선"),  # 표준 이름이 아니어도 가까운 이름이 없으면 둔다
    ("진칠료", "진찰료"), ("진찰로", "진찰료"), ("입윈료", "입원료"), ("검사로", "검사료"), ("미취료", "마취료"),
    ("식데", "식대"), ("합게", "합계"), ("기티", "기타"),  # 세 글자 이하는 자모 하나 오독만 고친다
    ("주사료", "주사료"), ("검사", "검사"),  # 짧은 이름은 글자 하나가 통째로 다르면 둔다('주사료'↔'검사료')
    ("한약접약", "한약(첩약)"), ("한약(청약)", "한약(첩약)"), ("한약첩약", "한약(첩약)"), ("한약(첩약)", "한약(첩약)"),
    ("선별급여 및 기타", "선별급여및기타"), ("선별급여항목", "선별급여항목"),  # 인쇄된 표기를 유지한다(사용자 결정 2026-10-07)
    ("치료재대", "치료재료대"), ("보수처리조정금액", "끝수처리조정금액"),  # 네 글자·중간 글자 빠짐
    ("재활및물리치료", "재활및물리치료료"), ("조제료 약품비", "투약및조제료_약품비"),  # 이름 규칙(끝 글자 변형·두 칸 갈림)
    ("65세이상등경감", "65세이상등경감"),  # 두 글자 이상 차이는 둔다
])
def test_item_name_follows_the_ao_prompt_rules(name, expected):
    assert rules.item(name) == expected


def test_check_is_empty_for_other_document_types():
    assert rules.check("진단서", {"항목내역": receipt(("진찰료", {}))}, {}, RECEIPT_BLOCKS) == []


def test_check_finds_a_cell_holding_more_than_one_amount():
    rows = receipt(("주사료_약품비", {"본인부담금": "1,104 9,000 123,785"}))

    found = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": rows}, RECEIPT_BLOCKS)

    assert [flag["code"] for flag in found] == ["multi_amount", "multi_amount"]  # AO·Docraft 양쪽
    assert found[0]["row"] == 0 and "1,104 9,000 123,785" in found[0]["message"]


def test_check_finds_a_column_the_form_does_not_have():
    """비급여_급여_오추출됨 케이스: 급여가 묶음 제목뿐인데 급여 값이 들어간 행을 집어낸다."""
    rows = case("[진료비영수증]비급여_급여_오추출됨", "07-extract-bbox.json")["항목내역"]

    found = rules.check("진료비영수증", {"항목내역": rows}, {}, RECEIPT_BLOCKS)
    flags = [flag for flag in found if flag["code"] == "no_column"]

    assert [flag["row"] for flag in flags] == [27, 30]  # 정액수가(요양병원)·합계
    assert all(flag["column"] == "급여" for flag in flags)  # 비급여④는 독립 열이라 걸리지 않는다


def test_check_finds_a_total_row_copied_from_an_item_row():
    rows = receipt(("진찰료", {"본인부담금": "1000"}), ("검사료", {"본인부담금": "2000"}), ("합계", {"본인부담금": "2000"}))

    found = rules.check("진료비영수증", {"항목내역": rows}, {}, RECEIPT_BLOCKS)

    assert [flag["row"] for flag in found if flag["code"] == "row_copy"] == [2]


def test_check_allows_a_total_equal_to_a_lump_sum_row_and_finds_a_broken_sum():
    """비급여_급여_오추출됨 원본: 합계 행이 정액수가(요양병원) 행과 실제로 같다(포괄수가 행이 위쪽 행을 다시 담는다)."""
    rows = case("[진료비영수증]비급여_급여_오추출됨", "07-extract-bbox.json")["항목내역"]
    fields = {"항목내역": rows, "환자부담총액": "9385610", "진료비총액": "11387230", "공단부담총액": "2001620"}

    found = rules.check("진료비영수증", fields, {}, RECEIPT_BLOCKS)

    assert not [flag for flag in found if flag["code"] == "row_copy"]
    sums = [flag for flag in found if flag["code"] == "sum_mismatch"]
    assert [flag["key"] for flag in sums] == ["환자부담총액"]  # 진료비총액·공단부담총액은 맞는다


def test_check_finds_rows_only_one_side_has():
    rows = receipt(("진찰료", {"본인부담금": "1000"}), ("합계", {"본인부담금": "1000"}))
    mine = receipt(("진찰료", {"본인부담금": "1000"}), ("CT진단료", {}), ("합계", {"본인부담금": "1000"}))

    found = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, RECEIPT_BLOCKS)

    assert [(flag["code"], flag.get("item")) for flag in found] == [("row_missing", "CT진단료")]


def test_check_allows_a_sum_off_by_less_than_a_hundred():
    """십의 자리 절사(요건 1절)는 불일치로 보지 않는다."""
    rows = receipt(("진찰료", {"본인부담금": "142137"}), ("합계", {"본인부담금": "142130"}))

    assert rules.check("진료비영수증", {"항목내역": rows, "환자부담총액": "142130"}, {}, RECEIPT_BLOCKS) == []


def test_correct_moves_a_nonexistent_column_to_the_column_docraft_read():
    rows = receipt(("정액수가(요양병원)", {"급여": "9010000"}))
    mine = receipt(("정액수가(요양병원)", {"비급여": "9010000"}))

    fixed, reason = rules.run("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, RECEIPT_BLOCKS, rounds=1)[0]["항목내역"]

    assert (fixed[0]["급여"], fixed[0]["비급여"]) == ("0", "9010000")
    assert "[RECEIPT.COLUMN_SHIFT]" in reason and rows[0]["급여"] == "9010000"  # 입력은 건드리지 않는다


def test_correct_leaves_a_move_docraft_does_not_confirm_to_the_judge():
    rows = receipt(("정액수가(요양병원)", {"급여": "9010000"}))

    assert rules.run("진료비영수증", {"항목내역": rows}, {}, RECEIPT_BLOCKS, rounds=1)[0] == {}


def test_correct_adds_a_missing_row_only_when_it_has_no_amounts():
    rows = receipt(("진찰료", {"본인부담금": "1000"}), ("합계", {"본인부담금": "1000"}))
    mine = receipt(("진찰료", {"본인부담금": "1000"}), ("CT진단료", {}), ("MRI진단료", {"비급여": "500000"}))

    fixed, reason = rules.run("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, RECEIPT_BLOCKS, rounds=1)[0]["항목내역"]

    assert [row["항목"] for row in fixed] == ["진찰료", "CT진단료", "합계"]  # 금액 있는 MRI는 Judge에게 맡긴다
    assert "CT진단료" in reason


def test_apply_keeps_both_the_subtotal_and_the_total_row_of_a_receipt():
    """서식에 인쇄된 소계 행을 지우면 아래 행이 밀린다. 남기되 합계 필드는 합계 행만 채운다."""
    rows = [{"항목": "진찰료", "공단부담금": "1,000"}, {"항목": "소계", "공단부담금": "1,000"},
            {"항목": "계", "공단부담금": "1,000"}]

    out = rules.apply("진료비영수증", {"항목내역": rows}, [])

    assert [row["항목"] for row in out["항목내역"]] == ["진찰료", "소계", "합계"]
    assert out["공단부담총액"] == "1000"  # 합계 행만 합계 필드를 채운다(소계는 채우지 않는다)
    # 남긴 소계를 합계 계산에서는 빼므로 항목 행 합(1,000)이 합계 행과 어긋나지 않는다
    assert [flag for flag in rules.check("진료비영수증", out, {}, []) if flag["code"] == "sum_mismatch"] == []


def test_check_does_not_guess_a_missing_column_without_header_evidence():
    """머리글을 못 읽었거나 다른 표만 읽었으면 없는 열이라고 단정하지 않는다."""
    rows = receipt(("처치및수술료", {"비급여": "800000"}))
    other = [{"type": "table", "rows": [["환자등록번호", "환자성명"], ["861025", "홍길동"]]}]

    assert rules.check("진료비영수증", {"항목내역": rows}, {}, []) == []
    assert rules.check("진료비영수증", {"항목내역": rows}, {}, other) == []


def test_receipt_column_recognizes_a_standalone_leaf_column():
    """하위 열이 없는 홑 칸이면 비급여·급여도 열 이름으로 본다."""
    assert rules._receipt_column(["비급여"]) == "비급여"
    assert rules._receipt_column(["요양급여"]) == "급여"


def test_receipt_column_does_not_treat_a_group_title_as_a_leaf():
    """하위 열(선택진료·본인부담 등)이 딸린 묶음 제목 칸은 leaf로 보지 않는다."""
    assert rules._receipt_column(["급여", "전액본인"]) is None    # 급여가 전액본인을 묶는 제목
    assert rules._receipt_column(["비급여", "선택진료"]) is None  # 비급여가 선택진료를 묶는 제목


def test_check_finds_a_column_shifted_to_its_neighbor():
    """AO가 비급여 값을 선택진료료 칸에 냈지만 Docraft(룰 적용 후)는 비급여 칸에 바로 읽었다."""
    rows = receipt(("초음파진단료", {"선택진료료": "50000"}))
    mine = receipt(("초음파진단료", {"비급여": "50000"}))

    found = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [])
    flags = [flag for flag in found if flag["code"] == "column_shift"]

    assert [(flag["row"], flag["column"], flag["target"]) for flag in flags] == [(0, "선택진료료", "비급여")]


def test_correct_swaps_a_shifted_column_when_ao_left_the_true_column_empty():
    rows = receipt(("초음파진단료", {"선택진료료": "50000"}))
    mine = receipt(("초음파진단료", {"비급여": "50000"}))

    fixed, reason = rules.run("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [], rounds=1)[0]["항목내역"]

    assert (fixed[0]["선택진료료"], fixed[0]["비급여"]) == ("0", "50000")
    assert "[RECEIPT.COLUMN_SHIFT]" in reason


def test_correct_leaves_a_shift_the_judge_should_decide():
    """AO의 대상 열에 이미 값(0이 아닌)이 있으면 함부로 바꾸지 않고 Judge에게 맡긴다."""
    rows = receipt(("초음파진단료", {"선택진료료": "50000", "비급여": "30000"}))
    mine = receipt(("초음파진단료", {"비급여": "50000"}))

    assert rules.run("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [], rounds=1)[0] == {}


def test_apply_realigns_a_value_shifted_to_the_neighboring_column():
    """모델이 본인부담금·공단부담금 값을 서로 바꿔 냈으면 파서 표 열 정체성으로 되돌린다."""
    header = ["구분", "항목", "본인부담금", "공단부담금"]
    rows = [header, ["기본", "진찰료", "3,423", "7,987"], ["기본", "초음파진단료", "1,030", "442"]]
    blocks = [block(rows=rows, kind="table")]
    read = {"항목내역": [{"항목": "진찰료", "본인부담금": "3423", "공단부담금": "7987"},
                     {"항목": "초음파진단료", "본인부담금": "442", "공단부담금": "1030"}]}  # 뒤 행이 뒤바뀜

    out = rules.apply("진료비영수증", read, blocks)

    assert (out["항목내역"][0]["본인부담금"], out["항목내역"][0]["공단부담금"]) == ("3423", "7987")
    assert (out["항목내역"][1]["본인부담금"], out["항목내역"][1]["공단부담금"]) == ("1030", "442")


def test_receipt_column_tolerates_a_misread_character_in_other_than():
    """항목명_누락 원본: 파서가 '선택진료료 이외'를 '선택진료료 미외'로 읽었다."""
    assert rules._receipt_column(["비급 여", "선택진료료 미외"]) == "선택진료료외"
    assert rules._receipt_column(["비급 여", "선택 진료료"]) == "선택진료료"


def test_apply_moves_a_whole_column_the_parser_table_confirms_on_two_rows():
    """두 행에서 선택진료료 → 선택진료료외로 되돌렸으면 파서 표에 없는 행(기타·합계)도 같이 되돌린다."""
    rows = [["항목", "선택진료료", "선택진료료 미외"], ["검사료", "", "40,000"], ["MRI진단료", "", "420,000"]]
    read = {"항목내역": [{"항목": "검사료", "선택진료료": "40000"}, {"항목": "MRI진단료", "선택진료료": "420000"},
                     {"항목": "기타", "선택진료료": "10000"}, {"항목": "합계", "선택진료료": "470000"}]}

    out = rules.apply("진료비영수증", read, [block(rows=rows, kind="table")])

    assert [(row["선택진료료"], row["선택진료료외"]) for row in out["항목내역"]] == [
        ("0", "40000"), ("0", "420000"), ("0", "10000"), ("0", "470000")]


SHIFT_BLOCKS = [{"type": "table", "rows": [["항목", "본인부담금", "공단부담금", "비급여"], ["마취료", "9,000", "36,000", ""],
                                           ["처치및수술료", "", "", "1,500,000"], ["검사료", "", "", "500,000"],
                                           ["영상진단료", "", "", ""]]}]


def test_check_and_correct_a_column_shifted_down_by_rows():
    """파싱_에러 원본: AO가 비급여 값을 한 행씩 아래로 밀어 적었다. 열 합은 같아 합계 검사로는 못 잡는다."""
    rows = receipt(("마취료", {"본인부담금": "9000", "공단부담금": "36000", "비급여": "0"}),
                   ("처치및수술료", {"비급여": "0"}), ("검사료", {"비급여": "1500000"}), ("영상진단료", {"비급여": "500000"}))
    mine = receipt(("마취료", {"본인부담금": "9000", "공단부담금": "36000"}),
                   ("처치및수술료", {"비급여": "1500000"}), ("검사료", {"비급여": "500000"}), ("영상진단료", {}))

    checks = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, SHIFT_BLOCKS)
    fixed, reason = rules.run("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, SHIFT_BLOCKS, rounds=1)[0]["항목내역"]

    assert [(flag["row"], flag["target_row"]) for flag in checks if flag["code"] == "row_shift"] == [(2, 1), (3, 2)]
    assert [row["비급여"] for row in fixed] == ["0", "1500000", "500000", "0"]
    assert "[RECEIPT.ROW_SHIFT]" in reason


def test_check_leaves_a_row_shift_the_parser_table_does_not_confirm():
    """Docraft만 다른 행에서 읽었고 파서 표 근거가 없으면 AO를 밀렸다고 보지 않는다."""
    rows = receipt(("처치및수술료", {}), ("검사료", {"비급여": "1500000"}))
    mine = receipt(("처치및수술료", {"비급여": "1500000"}), ("검사료", {}))

    assert not [flag for flag in rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [])
                if flag["code"] == "row_shift"]


FORM_BLOCKS = [{"type": "table", "rows": [["항목", "본인부담금", "공단부담금", "전액본인부담", "비급여"],
                                          ["진찰료", "2,268", "3,402", "", ""], ["검사료", "28,132", "42,198", "", "3,000"]]}]


def test_check_finds_a_whole_column_moved_to_a_column_the_form_does_not_have():
    """이슈 정리 260923 현상 1: 공단부담금 열 전체가 서식에 없는 선택진료료외로 갔다. 열 합은 맞아 합계 검사로는 못 잡는다."""
    rows = receipt(("진찰료", {"본인부담금": "2268", "선택진료료외": "3402"}),
                   ("검사료", {"본인부담금": "28132", "선택진료료외": "42198", "비급여": "3000"}))

    found = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": []}, FORM_BLOCKS)

    assert [(flag["row"], flag["column"]) for flag in found if flag["code"] == "no_column"] == [
        (0, "선택진료료외"), (1, "선택진료료외")]


def test_check_trusts_docraft_over_a_header_the_parser_misread():
    """파서 머리글에 없어도 Docraft 표가 그 열에 값을 읽었으면 서식에 없는 열로 몰지 않는다."""
    rows = receipt(("진찰료", {"선택진료료외": "3402"}))
    mine = receipt(("검사료", {"선택진료료외": "42198"}))

    assert not [flag for flag in rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, FORM_BLOCKS)
                if flag["code"] == "no_column"]


def test_correct_renames_an_item_to_the_standard_name():
    """이슈 정리 260923 현상 2·3: 선별급여 유의어와 '시행및처치료' 오독을 표준 이름으로 고친다."""
    rows = receipt(("국민건강보험법 제41조의4에 따른 요양급여", {}), ("시행및처치료", {"본인부담금": "71608"}),
                   ("보철·교정료", {}))  # 기호만 다른 이름은 그대로 둔다

    fixed, reason = rules.run("진료비영수증", {"항목내역": rows}, {"항목내역": rows}, [], rounds=1)[0]["항목내역"]

    assert [row["항목"] for row in fixed] == ["선별급여", "시술및처치료", "보철·교정료"]
    assert "[RECEIPT.ITEM_NAME]" in reason


def test_apply_clears_a_subtotal_column_read_as_full_self_pay():
    """한방 서식의 일부 본인부담 '소계' 열(본인+공단)을 전액본인부담으로 읽었으면 비운다(오독 행이 섞여도 과반이면)."""
    rows = [["항목", "본인부담금", "공단부담금", "소계", "선택 진료료"]]
    read = {"항목내역": [{"항목": "진찰료", "본인부담금": "2726", "공단부담금": "10904", "전액본인부담": "13630"},
                     {"항목": "식대", "본인부담금": "35910", "공단부담금": "35910", "전액본인부담": "71820"},
                     {"항목": "시술및처치료", "본인부담금": "71808", "공단부담금": "288032", "전액본인부담": "357640"}]}

    out = rules.apply("진료비영수증", read, [block(rows=rows, kind="table")])

    assert [row["전액본인부담"] for row in out["항목내역"]] == [None, None, None]


def test_headers_find_the_item_row_even_when_cells_are_merged():
    blocks = [{"type": "table", "rows": [["환자등록번호", "환자성명"], ["이비인후과 항목", "급여", "비급여"],
                                          ["본인부담금", "공단부담금", "전액본인부담"]]}]

    cells = rules._headers(blocks)

    assert {"급여", "비급여", "본인부담금"} <= cells
    assert rules._grouped(cells, *rules.GROUPED["급여"][:2]) is True     # 급여는 묶음 제목
    assert rules._grouped(cells, *rules.GROUPED["비급여"][:2]) is False  # 비급여는 독립 열


def test_headers_find_the_row_by_column_words_when_item_is_misread():
    """'항목'을 '함목'으로 읽어도 코드·명칭·횟수 같은 머리글 낱말이 셋 이상인 행을 머리글로 본다."""
    rows = [["함목 진찰료 입원료", "일자", "코드", "명칭", "금액", "횟수", "일수", "총액", "급여", "비급여"],
            ["함목 진찰료 입원료", "일자", "코드", "명칭", "금액", "횟수", "일수", "총액", "본인부담금", "비급여"],
            ["함목 진찰료 입원료", "2019.10.21", "AA156", "진찰료(초진)", "17,400", "1", "1", "17,400", "0", "0"]]

    cells = rules._headers([block(rows=[["환자등록번호", "환자성명"]], kind="table"), block(rows=rows, kind="table")])

    assert {"코드", "명칭", "금액", "일수", "본인부담금"} <= cells
    assert "환자등록번호" not in cells  # 머리글 낱말이 없는 표는 건너뛴다


def test_headers_split_merged_header_cells_into_words():
    """머리글 낱말 여럿이 병합된 셀은 낱말로 나눠, 코드 열을 하나로 세고 급여를 묶음 제목으로 본다."""
    rows = [["명칭 급여 항목 일자 코드 금액 횟수 일수 비급여 총액 일부본인부담 전액본인 공단부담금 부담 본인부담금"] * 3,
            ["진찰료 20211214", "AH011", "감염예방관리료(1등급)"]]

    cells = rules._headers([block(rows=rows, kind="table")])

    assert {"코드", "금액", "일수", "본인부담금"} <= cells
    assert sum("코드" in cell for cell in cells) == 1
    assert rules._grouped(cells, *rules.GROUPED["급여"]) is True


def test_headers_infer_columns_from_arithmetic_without_header_row():
    """머리글 없는 이어지는 쪽: 금액×횟수×일수=총액인 이웃 열로 머리글 낱말을 만들어 서식에 없는 투여량을 비운다."""
    rows = [["진찰료", "2022-12-08", "AA254", "재진진찰료-의원", "12,130", "1", "1", "12,130", "1,213", "10,917", "ㅇ", "0"],
            ["진찰료", "2023-01-18", "AH200000", "만성질환관리료", "2,230", "1", "1", "2,230", "223", "2,007", "o", "0"],
            ["검사료", "2023-01-18", "03021002", "당검사", "1,184", "1", "1", "1,184", "118", "1,066", "ㅇ", "0"],
            ["주사료", "2023-01-18", "vd3m", "비타민D", "50,000", "1", "1", "50,000", "0", "0", "0", "50,000"],
            ["투약 및 조제료", "2023-01-18", "650100021", "가소콜액", "25", "3", "5", "375", "∞", "17", "0", "0"]]
    read = {"항목내역": [{"항목": "진찰료", "EDI코드": "AA254", "단가": "12130", "투여량": "1", "횟수": "1", "일수": "1"}]}

    out = rules.apply("세부내역서", read, [block(rows=rows, kind="table")])

    assert rules._headers([block(rows=rows, kind="table")]) == {"금액", "횟수", "일수", "총액"}
    assert out["항목내역"][0]["투여량"] is None and out["항목내역"][0]["단가"] == "12130"


def test_headers_infer_nothing_from_an_unrelated_table():
    rows = [["가", "3", "7", "40"], ["나", "2", "9", "5"], ["다", "11", "4", "12"], ["라", "6", "6", "100"]]

    assert rules._headers([block(rows=rows, kind="table")]) == set()


# ── 룰 확장: 라벨 글자 제거·표 열 관례·소견 문장 보충 ───────────────────────

@pytest.mark.parametrize("key, value", [
    ("환자정보-질병군(DRG)번호", "질병군(DRG)번호"),   # 머리글이 값 자리에 들어온 것
    ("환자정보(병실)", "병실"),
    ("환자성명", "성별"),
    ("환자정보(환자등록번호)", ":"),
    ("환자성명", "제"),
    ("환자정보(환자등록번호)", "</td><td colspan=\"2\"></td></tr>"),   # 표 마크업
])
def test_label_text_is_not_a_value(key, value):
    doc_type = "진료비영수증" if key.startswith("환자정보-") else "세부내역서"
    assert rules.apply(doc_type, {key: value}, [])[key] is None


def test_a_real_value_survives_the_label_filter():
    out = rules.apply("세부내역서", {"환자성명": "홍길동", "환자정보(병실)": "1203호"}, [])
    assert (out["환자성명"], out["환자정보(병실)"]) == ("홍길동", "1203호")


def test_receipt_item_names_are_normalized_in_apply():
    rows = [{"항목": "입원료 2·3인실"}, {"항목": "투약 및 조제료-약품비"}, {"항목": "식 대"}]

    out = rules.apply("진료비영수증", {"항목내역": rows}, [])

    assert [row["항목"] for row in out["항목내역"]] == ["입원료_2-3인실", "투약및조제료_약품비", "식대"]


def _placed(names):
    return [row["항목"] for row in rules.apply("진료비영수증", {"항목내역": [{"항목": name, "본인부담금": "0"} for name in names]}, [])["항목내역"]]


@pytest.mark.parametrize("names, expected", [
    # 두 글자 이상 오독: 이웃 행이 서식 순서로 후보를 좁힌다(정답지 30건의 실제 꼴)
    (["치료재료대", "진폐및혈액성분제제료", "CT진단료"], ["치료재료대", "전혈및혈액성분제제료", "CT진단료"]),
    (["정신요법료", "전협및험액성문제제료", "CT진단료"], ["정신요법료", "전혈및혈액성분제제료", "CT진단료"]),
    (["치료재료대", "지혈및클리닉치료료", "정신요법료"], ["치료재료대", "재활및물리치료료", "정신요법료"]),
    # 이웃이 한쪽뿐인 첫·끝 행은 서식 순서 끝까지를 후보로 본다
    (["진살뇨", "식대"], ["진찰료", "식대"]),
    (["65세이상등정액", "정액수가환자외료"], ["65세이상등정액", "정액수가(완화의료)"]),
    # 후보가 둘: 1등이 확실히 앞서면 바꾸고(방사진단료 → 영상진단료), 비슷하면 두지 않는다
    (["검사료", "방사진단료", "치료재료대"], ["검사료", "영상진단료", "치료재료대"]),
    (["검사료", "영상치료료", "치료재료대"], ["검사료", "영상치료료", "치료재료대"]),
    # 이미 표에 있는 표준 항목으로는 바꾸지 않는다(중복 금지)
    (["전혈및혈액성분제제료", "치료재료대", "진폐및혈액성분제제료", "CT진단료"],
     ["전혈및혈액성분제제료", "치료재료대", "진폐및혈액성분제제료", "CT진단료"]),
    # 낱말을 더하거나 뺀 인쇄 이름(음절 수가 둘 이상 다르다)과 닮은 후보가 없는 병원별 항목은 그대로 둔다
    (["투약및조제료_행위료", "투약재료", "주사료_행위료"], ["투약및조제료_행위료", "투약재료", "주사료_행위료"]),
    (["주사료_행위료", "주사재료", "마취료"], ["주사료_행위료", "주사재료", "마취료"]),
    (["CT진단료", "제증명료및기타", "합계"], ["CT진단료", "제증명료및기타", "합계"]),
    (["검사료", "영상진단및방사선", "치료재료대"], ["검사료", "영상진단및방사선", "치료재료대"]),
    (["검사료", "무통주사", "치료재료대"], ["검사료", "무통주사", "치료재료대"]),
])
def test_receipt_item_name_is_matched_within_its_printed_position(names, expected):
    assert _placed(names) == expected


@pytest.mark.xfail(strict=True, reason="길이가 같은 정상 낱말의 다른 이름은 아직 오독과 가리지 못한다(일반 규칙 근거 부족, 2026-10-08)")
@pytest.mark.parametrize("names", [
    ["치료재료대", "초음파검사료", "정액수가(요양병원)"], ["MRI진단료", "DITI진단료", "초음파진단료"], ["진찰료", "입원료식대", "투약및조제료_행위료"],
])
def test_receipt_item_name_keeps_a_same_length_printed_name(names):
    assert _placed(names) == names


@pytest.mark.parametrize("raw, expected", [
    ("v22oo", "V2200"), ("AA254 030", "AA254030"), ("{AA000000}", "AA000000"),
    ("650902021", "650902021"), ("MCR3OI", "MCR301"),
])
def test_edi_code_normalize(raw, expected):
    assert rules.normalize("edi", raw) == expected


def test_item_names_flags_misprints_but_keeps_printed_standard_names():
    rows = [{"항목": "한약(첩약)"}, {"항목": "한약(청약)"}, {"항목": "선별급여 및 기타"}]

    flags = rules._item_names(types.SimpleNamespace(rows=rows))

    assert [(flag["row"], flag["name"]) for flag in flags] == [(1, "한약(첩약)")]


@pytest.mark.parametrize("raw, expected", [
    ("보철·교정료", "보철교정료"),
    ("검사/판독료", "검사판독료"),
    ("「식대」", "식대"),
    ("처치 및 수술료", "처치및수술료"),
    ("입원료_1인실", "입원료_1인실"),  # 하위 항목 밑줄은 ITEM_ALIASES가 되살리는 canonical 표기다
    ("입원료 상급병실", "입원료_상급병실"),  # 세로 병합된 '입원료' 상위 칸 + 하위 칸 '상급병실'
    ("선택항목_CT진단료", "CT진단료"),  # 서식 분류 칸 글자는 뗀다
    ("100/100미만 50%", "100/100미만50%"),  # 구 요양급여 서식의 본인부담률별 행(인쇄 이름이 표준이다)
    ("「국민건강보험법」제41\n/조의4", "선별급여"), ("끝수 조정금액", "끝수처리조정금액"),
])
def test_receipt_item_name_drops_every_non_alphanumeric_character(raw, expected):
    assert rules.item(raw) == expected


def test_detail_item_columns_follow_the_ao_convention():
    """세부내역서: 머리글 근거가 없는(Judge 교정) 표는 코드를 AO처럼 인쇄된 칸 그대로 둔다.

    다른 칸에서 옮겨 채우지 않는다(2026-10-03): 급여는 총액에서, 비급여는 '급/비' 표시+총액에서, 종료일자는 시작일자에서
    만들지 않는다. 급여구분 표시는 그대로 둔다. 머리글 근거가 없으면 급여 모델 값도 지운다.
    """
    rows = [{"원내코드": "V2200", "EDI코드": None, "시작일자": "20230311", "종료일자": None,
             "급여구분": "급여", "총액": "12380", "급여": "12,380"},
            {"원내코드": "AA254", "EDI코드": "AA254", "급여구분": "비급여", "총액": "60000"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]

    assert [(row["원내코드"], row["EDI코드"]) for row in out] == [("V2200", None), ("AA254", "AA254")]
    assert (out[0]["종료일자"], out[0]["급여"]) == (None, None)
    assert (out[1]["비급여"], out[1]["급여"], out[1]["급여구분"], out[1]["총액"]) == (None, None, "비급여", "60000")


def test_detail_paid_column_keeps_printed_values_even_when_equal_to_the_total():
    """독립 '급여' 값 열이 보이는 서식은 모델이 읽은 인쇄값을 둔다. 총액과 같아도 인쇄된 값이다(2026-10-03 정책: '급여액' 서식)."""
    blocks = [{"rows": [["항목", "코드", "총액", "급여", "비급여"],
                        ["진찰료", "AA100", "12380", "", ""]]}]
    rows = [{"급여구분": "급여", "총액": "12380", "급여": "8666"}, {"급여구분": "급여", "총액": "5000", "급여": "5000"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]

    assert (out[0]["급여"], out[1]["급여"]) == ("8666", "5000")


def test_detail_paid_column_stays_null_when_it_only_groups_the_share_columns():
    """급여가 본인부담·공단부담·전액본인부담을 묶는 머리글이면 값 칸이 아니므로 총액에서 만들지 않는다. 인쇄된 비급여 열도
    '비급여' 표시 행의 빈 칸을 총액으로 채우지 않는다(읽은 값만)."""
    blocks = [{"rows": [["항목", "총액", "급여", "급여", "급여", "비급여"],
                        ["", "", "본인부담", "공단부담", "전액본인부담", ""]]}]

    out = rules.apply("세부내역서", {"항목내역": [{"급여구분": "급여", "총액": "12380"},
                                              {"급여구분": "비급여", "총액": "60000"}]}, blocks)["항목내역"]

    assert (out[0]["급여"], out[1]["비급여"]) == (None, None)


def test_detail_paid_column_is_cleared_when_the_form_has_no_paid_amount_cell():
    """급여 값 칸이 없는 서식에서 모델이 총액-비급여로 채워 온 급여는 인쇄값이 아니므로 지운다."""
    blocks = [{"rows": [["항목", "총액", "급여", "급여", "급여", "비급여"],
                        ["", "", "본인부담", "공단부담", "전액본인부담", ""]]}]
    rows = [{"급여구분": "급여", "총액": "12380", "급여": "12380", "본인부담": "3714", "공단부담": "8666"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]

    assert out[0]["급여"] is None
    assert (out[0]["본인부담"], out[0]["공단부담"]) == ("3714", "8666")  # 인쇄된 하위 열은 그대로 둔다


@pytest.mark.parametrize("fields", [{}, {"환자정보(진료시작일)": None, "환자정보(진료종료일)": None}])
def test_treatment_period_is_not_computed_from_the_item_table(fields):
    """진료기간은 인쇄된 값만 둔다(2026-10-03). 사고발생일자는 스키마 정의(진료 기간의 시작일)대로 가장 이른 행 날짜다."""
    rows = [{"시작일자": "20191022", "종료일자": "20191022"}, {"시작일자": "20191021", "종료일자": "20191104"}]

    out = rules.apply("세부내역서", {**fields, "항목내역": rows}, [])

    assert (out.get("환자정보(진료시작일)"), out.get("환자정보(진료종료일)")) == (None, None)
    assert out["사고발생일자"] == "20191021"


def test_printed_period_wins_over_table_dates_and_a_missing_end_stays_blank():
    rows = [{"시작일자": "20191021", "종료일자": "20191104"}]
    out = rules.apply("세부내역서", {"환자정보(진료시작일)": "2019.10.25", "항목내역": rows}, [])
    assert (out["환자정보(진료시작일)"], out.get("환자정보(진료종료일)"), out["사고발생일자"]) == ("20191025", None, "20191025")


def test_single_printed_care_date_does_not_fill_the_end_date():
    blocks = [block(kind="table", rows=[["진료일자", "2019.01.21"]])]
    out = rules.apply("진료비영수증", {"외래/입원": "외래", "환자정보-진료시작일": None, "환자정보-진료종료일": None}, blocks)
    assert (out["환자정보-진료시작일"], out["환자정보-진료종료일"]) == ("20190121", None)


def test_grouped_amount_column_is_emptied_when_the_form_has_no_such_column():
    rows = receipt(("진찰료", {"급여": "15310", "본인부담금": "4593", "공단부담금": "10717"}))

    out = rules.apply("진료비영수증", {"항목내역": rows}, RECEIPT_BLOCKS)

    assert out["항목내역"][0]["급여"] is None          # 급여는 본인·공단부담금을 묶는 제목뿐이다
    assert out["항목내역"][0]["비급여"] == "0"         # 비급여는 독립 열이라 그대로 둔다


def test_treatment_row_is_built_from_the_opinion_sentence():
    blocks = [block(kind="table", rows=[["치료소견", "상기환자 상기진단 하 약물 치료하였습니다."]])]

    out = rules.apply("소견서", {}, blocks)

    assert out["치료내역"] == [{"치료일": None, "치료명": "상기환자 상기진단 하 약물 치료하였습니다."}]


def test_marked_dates_in_the_remarks_become_test_rows():
    blocks = [block(text="비고: 2021/08/19, 2022/05/17 (검사), 2022/09/22(검사)")]

    out = rules.apply("진단서", {}, blocks)

    assert out["검사내역"] == [{"검사일": "20220517", "검사명": "검사"}, {"검사일": "20220922", "검사명": "검사"}]


def test_gender_is_left_alone_without_an_idnum():
    assert rules.apply("진단서", {"환자 주민번호": None}, [])["성별"] is None


def test_a_printed_choice_is_not_a_value():
    assert rules.apply("진단서", {"성별": "남 여"}, [])["성별"] is None   # 서식에 인쇄된 보기


def test_a_field_does_not_take_the_value_of_its_pair():
    blocks = [block(text="의료기관 주소: 서울시 강남구 1로 2\n환자의 주소 :")]

    out = rules.apply("진단서", {}, blocks)

    assert out["병원주소"] == "서울시 강남구 1로 2"
    assert out["주소"] is None


# ── 표 행 대응 ──────────────────────────────────────────────────────────────

def test_pair_rows_matches_by_key_columns_not_by_order():
    """세부내역서는 EDI코드+시작일자로 짝짓는다. 코드 한 글자가 어긋나도 아래 행이 밀리지 않는다."""
    label = [{"항목": "식대", "EDI코드": "DN001", "시작일자": "20210808", "횟수": "3"},
             {"항목": "식대", "EDI코드": "DN001", "시작일자": "20210810", "횟수": "2"}]
    read = [{"항목": "식대", "EDI코드": "CN001", "시작일자": "20210808", "횟수": "3"},
            {"항목": "식대", "EDI코드": "DN001", "시작일자": "20210810", "횟수": "2"}]

    pairs = rules.pair_rows("세부내역서", "항목내역", label, read)

    assert [(left["시작일자"], right["시작일자"]) for left, right in pairs] == [
        ("20210808", "20210808"), ("20210810", "20210810")]


def test_pair_rows_attaches_a_collapsed_item_name_to_its_detailed_row():
    """짝이 없으면 접두가 같은 행에 붙인다('주사료' ⊂ '주사료_행위료')."""
    pairs = rules.pair_rows("진료비영수증", "항목내역",
                            [{"항목": "주사료_행위료"}, {"항목": "주사료_약품비"}],
                            [{"항목": "주사료", "본인부담금": "442"}, {"항목": "주사료", "본인부담금": "88"}])

    assert [right["본인부담금"] for _, right in pairs] == ["442", "88"]


def test_pair_rows_leaves_a_row_without_a_counterpart_unpaired_when_asked():
    """``fallback=False``면 키가 맞지 않는 행을 억지로 잇지 않는다."""
    pairs = rules.pair_rows("진료비영수증", "항목내역", [{"항목": "입원료"}], [{"항목": "수액"}], fallback=False)

    assert pairs == [({"항목": "입원료"}, None), (None, {"항목": "수액"})]


def test_receipt_table_restores_detailed_item_names_in_printed_order():
    """모델이 '주사료' 한 이름으로 뭉친 두 행을 파서 표의 세분 항목명·순서로 되돌린다."""
    header = ["구분", "항목", "본인부담금", "공단부담금"]
    rows = [header, ["기본", "진찰료", "3,423", "7,987"], ["기본", "주사료 행위료", "442", "1,030"],
            ["기본", "주사료 약품비", "88", "205"], ["기본", "검사료", "0", "0"]]
    blocks = [block(rows=[header[:1] + ["본인부담금"] + header[2:], *rows], kind="table")]
    read = {"항목내역": [{"항목": "진찰료", "본인부담금": "3,423", "공단부담금": "7,987"},
                     {"항목": "주사료", "본인부담금": "442", "공단부담금": "1,030"},
                     {"항목": "주사료", "본인부담금": "88", "공단부담금": "205"}]}

    out = rules.apply("진료비영수증", read, blocks)

    assert [row["항목"] for row in out["항목내역"]] == ["진찰료", "주사료_행위료", "주사료_약품비", "검사료"]
    assert [row["본인부담금"] for row in out["항목내역"]] == ["3423", "442", "88", "0"]


# --- 공통 형식 검사·표 구조 정리 --------------------------------------------

@pytest.mark.parametrize("key, value, expected", [
    ("환자정보-환자등록번호", "야간(공휴일)진료", None),  # 숫자 없는 값은 옆 라벨이 흘러든 것
    ("환자정보-환자등록번호", "A-12345", "A-12345"),
    ("차트번호", "진료카드", None),
])
def test_registration_number_needs_a_digit(key, value, expected):
    doc_type = "진료비영수증" if key.startswith("환자정보") else "진단서"
    assert rules.apply(doc_type, {key: value}, [])[key] == expected


@pytest.mark.parametrize("fields, expected", [
    ({"입원일자": "20230310", "퇴원일자": "20230305", "발급일": "20230320"}, [("입원일자", None)]),
    ({"진단일": "20230325", "발급일": "20230320"}, [("진단일", None), ("진단일", None)]),  # 발급일 뒤 + 앞뒤 역전
    ({"퇴원일자": "20230325", "발급일": "20230320"}, []),  # 퇴원 예정일은 발급일 뒤일 수 있다
    ({"진단일": "18991231"}, [("진단일", None)]),
    ({"항목내역": [{"시작일자": "20230305", "종료일자": "20230301"}]}, [("항목내역", 0)]),
])
def test_bad_dates_are_flagged(fields, expected):
    doc_type = "세부내역서" if "항목내역" in fields else "진단서"
    found = [flag for flag in rules.check(doc_type, fields, {}, []) if flag["code"] == "bad_date"]
    assert [(flag["key"], flag.get("row")) for flag in found] == expected


@pytest.mark.parametrize("fields, expected", [
    ({"환자 주민번호": "900101-2******", "성별": "남", "생년월일": "19900101"}, ["성별"]),
    ({"환자 주민번호": "900101-1******", "성별": "남", "생년월일": "19900102"}, ["생년월일"]),
    ({"환자 주민번호": "030101-3******", "성별": "남", "생년월일": "20030101"}, []),
])
def test_sex_and_birthday_must_match_the_idnum(fields, expected):
    assert [flag["key"] for flag in rules.check("소견서", fields, {}, []) if flag["code"] == "id_mismatch"] == expected


def test_empty_and_header_rows_are_dropped_except_on_receipts():
    rows = [{"항목": "항목", "EDI명칭": "명칭", "총액": "금액"}, {"총액": "0"}, {"항목": "검사료", "총액": "1000"}]
    assert [row["항목"] for row in rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]] == ["검사료"]
    kept = rules.apply("진료비영수증", {"항목내역": receipt(("기타", {}))}, [])["항목내역"]
    assert [row["항목"] for row in kept] == ["기타"]  # 금액이 모두 0인 인쇄 행은 지키고


# --- 산술 검사·열 통째 바뀜 ----------------------------------------------------

def detail(*rows):
    return [{"단가": price, "투여량": dose, "횟수": "1", "일수": days, "총액": total, "급여구분": "급여"}
            for price, dose, days, total in rows]


@pytest.mark.parametrize("rows, expected", [
    (detail(("1000", None, "3", "3000"), ("13", "0.5", "1", "7")), []),        # 원 단위 반올림은 맞다
    (detail(("1000", None, "3", "2000")), [0]),
    (detail(*[("850", None, "1", "1020")] * 3, ("500", None, "1", "500")), []),  # 여러 행이 같은 비율(종별 가산)
])
def test_detail_row_arithmetic(rows, expected):
    found = rules.check("세부내역서", {"항목내역": rows}, {}, [])
    assert [flag["row"] for flag in found if flag["code"] == "row_arith"] == expected


def test_detail_row_split_must_add_up_to_the_total():
    rows = [{"총액": "1000", "급여구분": "급여", "본인부담": "300", "공단부담": "700"},
            {"총액": "1000", "급여구분": "급여", "본인부담": "300", "공단부담": "900"}]
    assert [flag["row"] for flag in rules.check("세부내역서", {"항목내역": rows}, {}, [])] == [1]


@pytest.mark.parametrize("fields, expected", [
    ({"진료비총액": "70470", "환자부담총액": "56800", "공단부담총액": "13670"}, []),
    ({"진료비총액": "70470", "환자부담총액": "56800", "공단부담총액": "10717"}, ["진료비총액", "환자부담총액", "공단부담총액"]),
    ({"납부한금액_합계": "56800", "납부한금액_카드": "56800", "납부한금액_현금": "100"}, ["납부한금액_합계", "납부한금액_카드", "납부한금액_현금"]),
    ({"납부한금액_합계": "56800", "납부한금액_카드": "50000"}, []),  # 구성 필드가 하나뿐이면 따지지 않는다
])
def test_printed_totals_must_add_up(fields, expected):
    assert [flag["key"] for flag in rules.check("진료비영수증", fields, {}, [])] == expected


SHIFTED = receipt(("진찰료", {"선택진료료": "20000"}), ("검사료", {"선택진료료": "15000"}),
                  ("합계", {"선택진료료외": "35000"}))


def test_a_whole_column_read_into_its_neighbour_is_swapped_back():
    out = rules.apply("진료비영수증", {"항목내역": SHIFTED}, [])["항목내역"]
    assert [(row["선택진료료"], row["선택진료료외"]) for row in out] == [("0", "20000"), ("0", "15000"), ("0", "35000")]

    flags = rules.check("진료비영수증", {"항목내역": SHIFTED}, {"항목내역": out}, [])
    swap = [flag for flag in flags if flag["code"] == "column_shift" and "row" not in flag]
    assert [(flag["column"], flag["target"]) for flag in swap] == [("선택진료료", "선택진료료외")]
    fixed, reason = rules.run("진료비영수증", {"항목내역": SHIFTED}, {"항목내역": out}, [], rounds=1)[0]["항목내역"]
    assert [row["선택진료료외"] for row in fixed] == ["20000", "15000", "35000"] and "맞바꿨다" in reason


def test_an_ambiguous_column_swap_is_left_alone():
    rows = receipt(("진찰료", {"선택진료료": "35000"}), ("합계", {"선택진료료외": "35000", "비급여": "35000"}))
    assert rules._swaps(rows) == []


@pytest.mark.parametrize("field, expected", [("13846", "17983"), ("17990", "17990")])
def test_total_field_follows_a_confirmed_total_row(field, expected):
    """항목 행 합이 합계 행을 뒷받침하고 진료비총액=환자+공단이 맞을 때만 공단부담총액을 합계 행 값으로 바꾼다."""
    rows = receipt(("진찰료", {"공단부담금": "17983"}), ("합계", {"공단부담금": "17983"}))
    read = {"항목내역": rows, "공단부담총액": field, "진료비총액": "25690", "환자부담총액": "7700"}
    assert rules.apply("진료비영수증", read, [])["공단부담총액"] == expected


@pytest.mark.parametrize("value, rows, expected", [
    ("15722", [], None),          # 문서 어디에도 없고 어떤 계산으로도 설명되지 않는 급여총액
    ("8543", [], "8543"),         # 콤마를 빼면 인쇄돼 있다
    ("15722", [{"항목": "합계", "본인부담": "1", "급여": "15722"}], "15722"),  # 합계 행이 있으면 그 값을 쓴다
])
def test_unprinted_detail_totals_are_dropped(value, rows, expected):
    blocks = [block("급여 8,543 비급여 1,200")]
    out = rules.apply("세부내역서", {"급여_급여총액": value, "항목내역": rows}, blocks)
    assert out["급여_급여총액"] == expected
    flags = rules.check("세부내역서", {"급여_급여총액": value, "항목내역": []}, out, blocks)
    assert [flag["code"] for flag in flags] == ([] if value == "8543" else ["ungrounded"])
    assert rules.run("세부내역서", {"급여_급여총액": value}, out, blocks, rounds=1)[0] == (
        {} if value == "8543" else {"급여_급여총액": (None, "[GROUND.UNPRINTED] 베꼈거나 계산으로 설명되지 않는 급여 합계라 비웠다")})


def _lines(*pairs):
    return [{"항목": f"항목{i}", "본인부담": a, "공단부담": b, "급여": str(int(a) + int(b))} for i, (a, b) in enumerate(pairs)]


@pytest.mark.parametrize("fields, rows, expected", [
    # 구성 합(2026-10-05 정책: 인쇄되지 않아도 계산으로 설명되면 둔다)
    ({"급여_급여총액": "20820", "급여_본인부담총액": "6200", "급여_공단부담총액": "14620"}, [], "20820"),
    # 항목 열 합
    ({"급여_공단부담총액": "9000"}, _lines(("100", "4000"), ("200", "5000")), "9000"),
    ({"급여_급여총액": "9300"}, _lines(("100", "4000"), ("200", "5000")), "9300"),
    # 한 행의 값을 베낀 것
    ({"급여_공단부담총액": "5000"}, _lines(("100", "4000"), ("200", "5000")), None),
    # 항목 열 합보다 작은 소계를 옮긴 것
    ({"급여_공단부담총액": "4000"}, _lines(("100", "4000"), ("200", "5000")), None),
    # 열 합도 합계식도 아닌 값
    ({"급여_공단부담총액": "9500"}, _lines(("100", "4000"), ("200", "5000")), None),
    ({"급여_급여총액": "7777", "급여_본인부담총액": "6200", "급여_공단부담총액": "14620"}, [], None),
])
def test_unprinted_totals_are_kept_only_when_computation_explains_them(fields, rows, expected):
    out = rules.apply("세부내역서", {**fields, "항목내역": rows}, [block("본문 글자 111")])
    assert out[next(iter(fields))] == expected


def test_printed_total_stays_even_if_unexplained():
    out = rules.apply("세부내역서", {"급여_공단부담총액": "9500", "항목내역": _lines(("100", "4000"), ("200", "5000"))},
                      [block("공단부담 9,500")])
    assert out["급여_공단부담총액"] == "9500"


def test_shared_receipt_policy_requires_start_but_only_preserves_printed_end_date():
    required = rules._SHARED["required_keys"]["진료비영수증"]
    assert "환자정보-진료시작일" in required
    assert "환자정보-진료종료일" not in required


@pytest.mark.parametrize("visit", ["외래", "입원"])
def test_receipt_end_date_is_not_copied_from_its_start_date(visit):
    """진료종료일이 인쇄되지 않았으면 빈칸이다 — 외래라도 시작일을 베끼지 않는다(2026-10-03)."""
    out = rules.apply("진료비영수증", {"외래/입원": visit, "환자정보-진료시작일": "2019-01-21"}, [])
    assert (out["환자정보-진료시작일"], out.get("환자정보-진료종료일")) == ("20190121", None)


@pytest.mark.parametrize("total, expected", [("20820", "20820"), ("100820", None)])  # 비급여까지 더한 총액은 지운다
def test_detail_benefit_total_must_equal_its_parts(total, expected):
    read = {"급여_급여총액": total, "급여_본인부담총액": "6200", "급여_공단부담총액": "14620", "급여_전액본인부담총액": "0"}
    assert rules.apply("세부내역서", read, [])["급여_급여총액"] == expected


def test_a_table_with_many_broken_rows_is_flagged_as_low_quality():
    broken = [("1000", None, "2", "900"), ("1000", None, "2", "800"), ("1000", None, "2", "700")]
    rows = detail(*[("1000", None, "1", "1000")] * 3, *broken)
    found = [flag["code"] for flag in rules.check("세부내역서", {"항목내역": rows}, {}, [])]
    assert found.count("row_arith") == 3 and found.count("low_quality") == 0  # 절반이면 아직 아니다
    rows = detail(*[("1000", None, "1", "1000")] * 2, *broken)
    assert "low_quality" in [flag["code"] for flag in rules.check("세부내역서", {"항목내역": rows}, {}, [])]


# --- FP 감사 후속(서식에 없는 열·베낀 합계·중복 소견·번호 형식) --------------------

DETAIL_HEADER = [block(rows=[["항목", "일자", "코드", "명칭", "횟수", "일수", "총액", "본인부담금", "공단부담금"]], kind="table")]


def test_detail_columns_missing_from_the_header_are_cleared():
    """머리글에 단가·투여량·독립 급여 열이 없으면 모델이 옮겨 적은 값이다."""
    rows = [{"항목": "검사료", "단가": "6600", "투여량": "1", "횟수": "1", "일수": "1", "총액": "6600",
             "급여구분": "급여", "급여": "6000"}]
    out = rules.apply("세부내역서", {"항목내역": rows}, DETAIL_HEADER)["항목내역"][0]
    assert (out["단가"], out["투여량"], out["급여"], out["총액"]) == (None, None, None, "6600")
    header = [block(rows=[["항목", "단가", "투여량", "일수", "총액", "급여"]], kind="table")]
    out = rules.apply("세부내역서", {"항목내역": rows}, header)["항목내역"][0]
    assert (out["단가"], out["투여량"], out["급여"]) == ("6600", "1", "6000")


@pytest.mark.parametrize("total, expected", [("300", None), ("100", None), ("1000", "1000")])
def test_detail_totals_copied_from_a_row_or_a_subtotal_are_dropped(total, expected):
    """한 행의 값을 베꼈거나(300) 열 합보다 작은(100, 소계) 합계는 인쇄된 합계가 아니다."""
    rows = [{"항목": "검사료", "본인부담": "300"}, {"항목": "진찰료", "본인부담": "700"}]
    out = rules.apply("세부내역서", {"항목내역": rows, "급여_본인부담총액": total}, [block("300 700 100 1000")])
    assert out["급여_본인부담총액"] == expected


def test_treatment_notes_do_not_repeat_a_surgery_already_listed():
    sentence = "2020년7월15일 복강경하 난소낭종제거 수술함"
    blocks = [block(rows=[["치료내용", sentence]], kind="table")]
    surgery = {"수술내역": [{"수술일자": "20200715", "수술명": "복강경하 난소낭종제거 수술함"}]}
    assert rules.apply("진단서", surgery, blocks)["치료내역"] == []
    both = {**surgery, "치료내역": [{"치료일": None, "치료명": "복강경하 난소낭종제거 수술함"}]}
    assert rules.apply("진단서", both, [])["치료내역"] == []


def test_edi_code_holding_the_name_takes_the_code_from_the_hospital_column():
    rows = [{"원내코드": "S2084", "EDI코드": "ESWT 7 (체외충격파치료)", "EDI명칭": "ESWT 7 (체외충격파치료)"}]
    out = rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"][0]
    assert (out["원내코드"], out["EDI코드"]) == (None, "S2084")


@pytest.mark.parametrize("key, value, expected", [
    ("환자정보-질병군(DRG)번호", "N07200", "N07200"),
    ("환자정보-질병군(DRG)번호", "201902070516", None),       # 영수증번호
    ("환자정보-환자등록번호", "20191024-M188", None),           # 날짜로 시작하는 접수번호
    ("환자정보-환자등록번호", "602-82-00286 상호 학교법인", None),  # 사업자등록번호와 라벨
    ("차트번호", "20201015-00001", "20201015-00001"),          # 차트번호는 날짜로 시작하기도 한다
    ("의사명", "[] 치과의사", None), ("의사명", "또는인", None), ("의사명", "홍길동", "홍길동"),
])
def test_number_and_name_fields_reject_neighbouring_text(key, value, expected):
    doc_type = "진료비영수증" if key.startswith("환자정보") else "진단서"
    assert rules.apply(doc_type, {key: value}, [])[key] == expected


# ── 수술확인서·입퇴원확인서·약제비영수증 ────────────────────────────────────


def test_admission_period_cell_fills_both_admission_and_discharge_dates():
    blocks = [block(kind="table", rows=[["진료과", "정형외과", "입원기간", "2020-07-03 ~ 2020-07-11 (9일간)"]])]
    out = rules.apply("입퇴원확인서", {"입원일자": None, "퇴원일자": None}, blocks)
    assert (out["입원일자"], out["퇴원일자"]) == ("20200703", "20200711")


def test_empty_department_cell_does_not_take_the_next_label():
    blocks = [block(kind="table", rows=[["입원과", "", "호실", "", "입원 년월일", ""]])]
    assert rules.apply("수술확인서", {"진료과": "호실"}, blocks)["진료과"] is None


def test_surgery_date_written_in_the_name_cell_moves_to_its_column():
    out = rules.apply("수술확인서", {"수술내역": [{"수술일자": None, "수술명": "2019.05.02 Hydrocelectomy (right)"}]}, [])
    assert out["수술내역"] == [{"수술일자": "20190502", "수술명": "Hydrocelectomy (right)"}]


def test_pharmacy_receipt_accident_date_is_the_dispensing_date_and_sums_are_checked():
    fields = {"조제일자": "2021-06-03", "진료비내역-총액": "19,930", "진료비내역-급여본인부담": "4,100",
              "진료비내역-공단부담액": "9,730", "진료비내역-비급여및전액본인부담금": "6,100",
              "진료비내역-환자부담총액": "10,200", "약국정보(사업자등록번호)": "277-74-00289", "진료비내역-비급여": "1,200원"}
    out = rules.apply("약제비영수증", fields, [])
    assert out["사고발생일자"] == "20210603"
    assert doctypes.kind("약제비영수증", "진료비내역-비급여") == "amount" and out["진료비내역-비급여"] == "1200"
    assert out["약국정보(사업자등록번호)"] == "2777400289"
    assert not [flag for flag in rules.check("약제비영수증", out, out, []) if flag["code"] == "sum_mismatch"]
    out["진료비내역-환자부담총액"] = "12200"
    assert {flag["key"] for flag in rules.check("약제비영수증", out, out, []) if flag["code"] == "sum_mismatch"} >= {"진료비내역-환자부담총액"}


def test_correct_sets_the_benefit_class_from_the_amount_columns():
    """0922 재테스트: AO가 세부내역서 급여구분에 '열추출'을 잘못 낸다. 금액 열로 정해지면 고치고, 금액이 없는 행과
    집계 행은 비운다. e2e(코드2개_급여액): 금액이 '급여' 열에만 있는 서식도 급여다."""
    rows = [{"항목": "진찰료", "급여구분": "열추출", "본인부담": "5000", "공단부담": "13000"},
            {"항목": "주사료", "급여구분": "열추출", "비급여": "30000"},
            {"항목": "처치료", "급여구분": "열추출", "전액본인부담": "2000"},
            {"항목": "검사료", "급여구분": "열추출"},  # 금액이 없으면 정할 근거가 없다
            {"항목": "소계", "급여구분": "열추출", "본인부담": "5000"},  # 집계 행에는 급여구분이 없다
            {"항목": "재료대", "급여구분": "급여", "본인부담": "100"},
            {"항목": "투약료", "급여구분": "열추출", "급여": "50"},
            {"항목": "주사료", "급여구분": "열추출", "본인부담": "10", "비급여": "20"}]  # 둘 다면 Judge
    checks = rules.check("세부내역서", {"항목내역": rows}, {}, [])

    fixed, reason = rules.run("세부내역서", {"항목내역": rows}, {}, [], rounds=1)[0]["항목내역"]

    assert [flag["row"] for flag in checks if flag["code"] == "item_class"] == [0, 1, 2, 3, 4, 6, 7]
    assert [row["급여구분"] for row in fixed] == ["급여", "비급여", "급여", None, None, "급여", "급여", "열추출"]
    assert "[DETAIL.ITEM_CLASS]" in reason and rows[0]["급여구분"] == "열추출"  # 입력은 건드리지 않는다


def test_pair_rows_matches_rows_with_the_same_key_by_their_other_cells():
    """0922 재테스트: 같은 날 이름이 같은 이학요법료 행이 여럿이면 순서가 달라도 명칭·금액이 같은 행끼리 잇는다."""
    left = [{"항목": "이학요법료", "EDI명칭": "표층열치료", "총액": "954.5"},
            {"항목": "이학요법료", "EDI명칭": "간섭파전류치료", "총액": "4232"}]
    right = [{"항목": "이학요법료", "EDI명칭": "간섭파전류치료", "총액": "4232"},
             {"항목": "이학요법료", "EDI명칭": "표층열치료", "총액": "954.5"}]

    pairs = rules.pair_rows("세부내역서", "항목내역", left, right)

    assert [(a["EDI명칭"], b["EDI명칭"]) for a, b in pairs] == [("표층열치료", "표층열치료"), ("간섭파전류치료", "간섭파전류치료")]


def test_run_repeats_until_a_round_fixes_nothing_and_traces_each_rule():
    """0922 2020010684177: 1회차에 열 통째 바꾸기와 합계 행 칸 옮기기가 함께 걸려 검사료 비급여가 선택진료료외로 가고,
    2회차가 되돌려 합계식이 맞는다. 고칠 것이 없는 3회차에서 멈춘다."""
    ao = receipt(("진찰료", {"본인부담금": "4707"}), ("검사료", {"비급여": "50000"}),
                 ("합계", {"본인부담금": "4707", "선택진료료외": "50000"}))
    mine = receipt(("진찰료", {"본인부담금": "4707"}), ("검사료", {"비급여": "50000"}),
                   ("합계", {"본인부담금": "4707", "비급여": "50000"}))
    once = rules.run("진료비영수증", {"항목내역": ao}, {"항목내역": mine}, [], rounds=1)[0]["항목내역"][0]
    fixes, history, trace = rules.run("진료비영수증", {"항목내역": ao}, {"항목내역": mine}, [])
    assert once[1]["선택진료료외"] == "50000"
    assert [row["비급여"] for row in fixes["항목내역"][0]] == ["0", "50000", "50000"]
    assert len(history) == 3 and history[-1] == [] and ao[1]["비급여"] == "50000"  # 입력은 건드리지 않는다
    swap = [entry for entry in trace if entry["rule"] == "RECEIPT.COLUMN_SWAP"]
    assert [(entry["round"], entry["result"], entry["flags"], entry["fixed"]) for entry in swap] == [
        (1, "fail", 1, 0), (2, "fail", 1, 1), (3, "pass", 0, None)]
    assert {entry["action"] for entry in swap} == {"CORRECT"} and swap[0]["category"] == "STRUCT"


def test_a_rule_disabled_for_a_doc_type_is_not_checked(monkeypatch):
    rows = [{"항목": "진찰료", "급여구분": "열추출", "본인부담": "5000"}]
    assert [flag["code"] for flag in rules.check("세부내역서", {"항목내역": rows}, {}, [])] == ["item_class"]
    monkeypatch.setattr(rules, "DISABLE", rules._disabled({"세부내역서": ["DETAIL.ITEM_CLASS"]}))
    assert rules.check("세부내역서", {"항목내역": rows}, {}, []) == []
    assert rules.run("세부내역서", {"항목내역": rows}, {}, [])[0] == {}


def test_rulesets_reject_an_unknown_table_or_rule_id(tmp_path):
    path = tmp_path / "rules.yaml"
    path.write_text("disable: {}\nlabelz: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="labelz"):
        rules._load(path)
    with pytest.raises(ValueError, match="NO.SUCH"):
        rules._disabled({"세부내역서": ["NO.SUCH"]})


def test_a_required_field_or_table_left_empty_is_flagged(monkeypatch):
    monkeypatch.setattr(rules, "REQUIRED", rules._required({"진료비영수증": ["발행일", "진료비총액", "항목내역"]}))
    flags = rules.check("진료비영수증", {"발행일": " ", "진료비총액": "0", "항목내역": [{"항목": None}]}, {}, [])
    assert [(flag["code"], flag["key"], flag["rule"]) for flag in flags] == [
        ("missing", "발행일", "MISSING.REQUIRED"), ("missing", "항목내역", "MISSING.REQUIRED")]


def test_a_required_column_is_flagged_only_on_rows_that_have_its_condition(monkeypatch):
    monkeypatch.setattr(rules, "REQUIRED", rules._required({"수술확인서": [{"수술내역": {"수술일자": "수술명"}}]}))
    rows = [{"수술일자": None, "수술명": "충수절제술"}, {"수술일자": None, "수술명": None}, {"수술일자": "20240101", "수술명": "봉합"}]
    assert [(flag["key"], flag["row"], flag["column"]) for flag in rules.check("수술확인서", {"수술내역": rows}, {}, [])] == [
        ("수술내역", 0, "수술일자")]


def test_a_required_item_row_missing_from_the_table_is_flagged(monkeypatch):
    """진료비영수증은 항목내역 표에 진찰료·CT진단료 행이 반드시 있어야 한다(REQUIRED_ITEMS)."""
    monkeypatch.setattr(rules, "REQUIRED_ITEMS", {"진료비영수증": ("진찰료", "CT진단료")})
    rows = receipt(("진찰료", {"본인부담금": "5000"}))
    flags = rules.check("진료비영수증", {"항목내역": rows}, {}, [])
    assert [(flag["code"], flag["key"], flag["item"], flag["rule"]) for flag in flags] == [
        ("missing", "항목내역", "CT진단료", "MISSING.REQUIRED")]


def test_a_required_item_row_with_only_zero_amounts_still_counts_as_present(monkeypatch):
    """AO는 CT진단료를 금액 없이 0으로 찍기도 한다 — 행만 있으면 필수 항목은 채워진 것으로 본다."""
    monkeypatch.setattr(rules, "REQUIRED_ITEMS", {"진료비영수증": ("진찰료", "CT진단료")})
    rows = receipt(("진찰료", {"본인부담금": "5000"}), ("CT진단료", {}))
    assert rules.check("진료비영수증", {"항목내역": rows}, {}, []) == []


def test_a_required_item_exempt_by_another_row_is_not_flagged(monkeypatch):
    """한방 진료비영수증(항목내역에 '한방'으로 시작하는 행)은 CT진단료가 없어도 잡지 않는다(REQUIRED_ITEMS_EXEMPT).
    같은 문서에서 진찰료가 없으면 그건 그대로 잡는다."""
    monkeypatch.setattr(rules, "REQUIRED_ITEMS", {"진료비영수증": ("진찰료", "CT진단료")})
    rows = receipt(("한방물리요법료", {"본인부담금": "5000"}))
    flags = rules.check("진료비영수증", {"항목내역": rows}, {}, [])
    assert [(flag["code"], flag["key"], flag["item"], flag["rule"]) for flag in flags] == [
        ("missing", "항목내역", "진찰료", "MISSING.REQUIRED")]


def test_required_rejects_a_key_or_column_the_doc_type_does_not_define():
    for required in ({"진단서": ["진단명"]}, {"진단서": [{"병명내역": {"수술명": "병명코드"}}]}, {"없는유형": []}):
        with pytest.raises(ValueError, match="required"):
            rules._required(required)


@pytest.mark.parametrize("header, edi, expected", [
    (["항목", "코드", "명칭", "금액"], "AA254", (None, "AA254")),                    # 코드 열 하나: 모델이 두 칸에 적은 것
    (["항목", "코드", "명칭", "금액"], None, (None, "AA254")),                       # 코드 열 하나: 원내코드에만 적은 것
    (["항목", "EDI코드", "원내코드", "명칭", "금액"], "AA254", ("AA254", "AA254")),  # 코드 열 둘: 같은 코드가 둘 다 인쇄됨
    (["항목", "EDI코드", "원내코드", "명칭", "금액"], None, ("AA254", None)),        # 코드 열 둘: 원내코드만 인쇄됨(AO처럼 둔다)
])
def test_detail_code_columns_follow_the_printed_form(header, edi, expected):
    rows = [{"항목": "진찰료", "원내코드": "AA254", "EDI코드": edi, "EDI명칭": "재진진찰료", "총액": "12000"}]
    blocks = [block(rows=[header, ["진찰료", "AA254", "AA254", "재진진찰료", "12,000"]], kind="table")]

    out = rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]

    assert (out[0]["원내코드"], out[0]["EDI코드"]) == expected


# --- e2e 세부내역서 표적 룰(병실 진료과·섹션 항목·빈 투여량·EDI S/B) -------------------------------


@pytest.mark.parametrize("room, expected", [("외과", None), ("내과혈액종양", None), ("이비인후-두경부외과", None),
                                            ("내과,신경과", None), ("외래", "외래"), ("1203호", "1203호"),
                                            ("외과병동 501", "외과병동 501"), ("신관6병동-650", "신관6병동-650")])
def test_a_department_name_in_the_ward_is_dropped(room, expected):
    """병실 칸이 비면 모델·AO가 옆 진료과 칸을 읽는다. 외래·호실·병동은 병실 값이다."""
    assert rules.apply("세부내역서", {"환자정보(병실)": room}, [])["환자정보(병실)"] == expected


def test_run_clears_a_department_name_in_the_ao_ward():
    ao = {"환자정보(병실)": "내과혈액종양", "항목내역": [{"항목": "진찰료", "총액": "1000"}]}
    fixes = rules.run("세부내역서", ao, {}, [])[0]
    assert fixes["환자정보(병실)"][0] is None and fixes["환자정보(병실)"][1].startswith("[DETAIL.WARD]")
    assert rules.run("세부내역서", {**ao, "환자정보(병실)": "외래"}, {}, [])[0] == {}


def section_rows():
    return [{"항목": "01.진찰료"},
            {"항목": "소계", "총액": "3100"},
            {"항목": "재진 진찰료", "EDI코드": "AA256", "EDI명칭": "재진 진찰료", "총액": "3000"},
            {"항목": "01.진찰료", "EDI코드": "AU313", "EDI명칭": "의료질평가지원금", "총액": "60"},
            {"항목": "80.100분의100미만본인부담(80%)"},
            {"항목": "Medifoam 10*20", "EDI코드": "M3030702", "EDI명칭": "Medifoam 10*20", "총액": "40"}]


def test_items_copied_from_the_name_take_the_section_title():
    """창원경상대 서식: 섹션 제목('01.진찰료')이 제 행으로 읽히고 명세 행 항목에 EDI명칭이 들어간다. 라벨은 섹션명이다."""
    rows = rules.apply("세부내역서", {"항목내역": section_rows()}, [])["항목내역"]
    assert [row["항목"] for row in rows if row.get("EDI코드")] == ["01.진찰료", "01.진찰료", "80.100분의100미만본인부담(80%)"]
    fixed, reason = rules.run("세부내역서", {"항목내역": section_rows()}, {}, [])[0]["항목내역"]
    assert fixed[2]["항목"] == "01.진찰료" and fixed[5]["항목"].startswith("80.") and "[DETAIL.SECTION_ITEM]" in reason
    plain = [{"항목": "검사료", "EDI코드": "E7540", "EDI명칭": "검사료", "총액": "100"}]  # 섹션 행이 없으면 두지 않는다
    assert rules.apply("세부내역서", {"항목내역": plain}, [])["항목내역"][0]["항목"] == "검사료"


@pytest.mark.parametrize("header, kept", [
    (["항목", "코드", "명칭", "총투", "횟수", "일수", "금액"], "1"),  # 횟수가 따로 있으면 총투는 투여량이다
    (["항목", "코드", "명칭", "수량", "횟수", "일수", "단가"], "1"),
    (["항목", "코드", "명칭", "단가", "총투", "일수", "총액"], None),  # 횟수 열이 없는 서식의 총투는 횟수다
])
def test_dose_header_words_need_a_separate_count_column(header, kept):
    rows = [{"항목": "검사료", "EDI코드": "E7540", "투여량": "1", "횟수": "1", "일수": "1", "총액": "6600"}]
    out = rules.apply("세부내역서", {"항목내역": rows}, [block(rows=[header], kind="table")])["항목내역"][0]
    assert out["투여량"] == kept


def test_run_fills_ao_dose_cells_docraft_read_under_a_printed_header():
    """AO가 머리글에 인쇄된 투여량 칸을 비우면 Judge가 Docraft 값도 버리곤 한다. 짝지은 행의 Docraft 값으로 채운다."""
    ao = [{"항목": "진찰료", "EDI코드": "AA156", "시작일자": "20190710", "투여량": "", "총액": "17400"},
          {"항목": "투약료", "EDI코드": "D6809", "시작일자": "20190710", "투여량": "2", "총액": "300"}]
    mine = [{**row, "투여량": "1"} for row in ao]
    header = [block(rows=[["항목", "일자", "코드", "명칭", "금액", "횟수", "일수", "투여량", "총액"]], kind="table")]
    fixed, reason = rules.run("세부내역서", {"항목내역": ao}, {"항목내역": mine}, header)[0]["항목내역"]
    assert [row["투여량"] for row in fixed] == ["1", "2"] and "[DETAIL.EMPTY_CELL]" in reason
    assert rules.run("세부내역서", {"항목내역": ao}, {"항목내역": mine}, DETAIL_HEADER)[0] == {}  # 머리글에 없으면 두지 않는다


def test_edi_s_and_b_become_digits_only_when_the_master_knows_only_the_digits(monkeypatch):
    known = {"EB562": ["유도초음파"], "AA254": ["재진진찰료"]}
    monkeypatch.setattr(rules.master, "names", lambda system, value: known.get(value, []))
    assert rules.normalize("edi", "B1020B") == "B1020B"  # 원내코드는 B·S가 실제 글자다
    assert rules.normalize("edi", "MX122s1") == "MX122S1"
    assert rules.normalize("edi", "EB562") == "EB562"
    assert rules.normalize("edi", "AA2S4") == "AA254"


def test_check_does_not_add_a_docraft_row_that_misreads_an_existing_ao_row():
    """0922 재테스트: Docraft가 '치료재료대'를 '치료제료다'로 읽은 빈 행을 누락 행으로 끼워 중복 행이 생겼다.
    표준 이름 행(MRI진단료)은 비슷한 이름(CT진단료)이 있어도 그대로 끼운다."""
    rows = receipt(("치료재료대", {}), ("CT진단료", {}), ("합계", {}))
    mine = receipt(("치료제료다", {}), ("CT진단료", {}), ("MRI진단료", {}), ("예약진찰료", {}), ("합계", {}))

    found = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [])

    assert [flag["item"] for flag in found if flag["code"] == "row_missing"] == ["MRI진단료", "예약진찰료"]


def test_check_flags_a_printed_column_both_readings_left_empty():
    """e2e(3022033115105207-1.png): 머리글에 총투·횟수가 인쇄됐는데 AO·Docraft 모두 투여량 열을 통째로 비웠다."""
    blocks = [{"type": "table", "rows": [["항목", "코드", "명칭", "금액", "총투", "횟수", "일수"], ["이학요법료", "MX12251", "도수치료", "50000", "1", "1", "1"]]}]
    rows = [{"항목": "이학요법료", "EDI명칭": "도수치료", "단가": "50000", "투여량": None},
            {"항목": "소계", "단가": None, "투여량": "1"}]

    flags = [flag for flag in rules.check("세부내역서", {"항목내역": rows}, {"항목내역": rows}, blocks) if flag["code"] == "empty_column"]

    assert [(flag["key"], flag["column"]) for flag in flags] == [("항목내역", "투여량")]  # 소계 행은 보지 않는다
    assert not [flag for flag in rules.check("세부내역서", {"항목내역": rows}, {}, []) if flag["code"] == "empty_column"]  # 머리글 근거 없음


def test_has_header_needs_the_joined_words_in_separate_cells():
    """e2e(비급표현-KJM02605.tif): '횟수(총투)' 한 칸은 투여량 열이 아니다. 총투·횟수가 따로 인쇄돼야 투여량이다."""
    words = rules.HEADER_COLUMNS["투여량"]

    assert not rules._has_header({"단가", "횟수(총투)", "일수"}, words)
    assert rules._has_header({"단가", "총투", "횟수", "일수"}, words)


@pytest.mark.parametrize("name, expected", [
    ("정액수가(요양병원)", "정액수가(요양병원)"), ("정액수가 (완화의료)", "정액수가(완화의료)"),
    ("정액수가요양병원", "정액수가(요양병원)"), ("입원료 2·3인실", "입원료_2-3인실"), ("입원료_2,3인실", "입원료_2-3인실")])
def test_item_keeps_the_parentheses_of_standard_lump_sum_names(name, expected):
    """2026-09-24 사용자 결정: 영수증 정액수가 항목은 AO·서식처럼 괄호를 두고, 입원료 2·3인실은 '2-3'으로 통일한다."""
    assert rules.item(name) == expected


def test_detail_class_hint_forbids_guessing():
    """급여구분 스키마 설명은 인쇄된 값만·공란은 null·표 행 규칙을 담는다(공란 칸을 급여로 채우지 않게)."""
    description = doctypes.schema("세부내역서")["properties"]["항목내역"]["items"]["properties"]["급여구분"]["description"]
    assert "공란" not in description and "비었" in description and "null" in description and "추정하지 않는다" in description


def test_institution_type_checkbox_options_compare_exactly_but_plain_text_keeps_containment():
    kind = doctypes.kind("진료비영수증", "의료기관정보-요양기관종류")
    assert not rules.same(kind, "고상급종합병원", "종합병원") and not rules.same(kind, "상급종합병원", "종합병원")
    assert rules.same(kind, "종합 병원", "종합병원")
    assert rules.same("text", "고상급종합병원", "종합병원")


@pytest.mark.parametrize("printed, expected", [("80/100", "80/100"), ("80%", "80/100"), ("100분의90", "90/100"), ("비급", "비급여"),
                                               ("급", "급여"), ("100/100", "100/100")])
def test_benefit_class_keeps_the_printed_rate(printed, expected):
    """선별급여 80/100은 급여·비급여로 바꾸지 않고 원문을 남긴다(하네스가 급여로 해석해 금액 칸을 옮긴다)."""
    assert rules._enum("급여구분", printed) == expected
    assert "80/100" in doctypes.DOC_TYPES["세부내역서"]["tables"]["항목내역"]["급여구분"]["enum"]


def test_receipt_item_row_accepts_printed_rate_names():
    """구 요양급여 서식 행 이름(100/100미만50%)의 기호 때문에 파서 표 행 복원이 버리지 않는다."""
    assert rules._receipt_item(["100/100미만50%"]) == "100/100미만50%"


@pytest.mark.parametrize(("value", "expected"), [
    ("[✓]병원급", "병원급"), ("의원급", "의원급·보건기관"), ("의원급・보건기관", "의원급·보건기관"),
    ("고상급종합병원", "상급종합병원"), ("종합병원", "종합병원"), ("V", None),
])
def test_institution_type_maps_to_four_checkbox_values(value, expected):
    assert rules._enum("의료기관정보-요양기관종류", value) == expected


def test_institution_type_schema_lists_four_values():
    assert doctypes.spec("진료비영수증")["fields"]["의료기관정보-요양기관종류"]["enum"] == sorted(
        ["의원급·보건기관", "병원급", "종합병원", "상급종합병원"])


# ── 무리 값 채우기(섹션 제목·생략 칸·진료기간) ─────────────────────────────────

def fd_rows(*names, **extra):
    return [{"항목": None, "EDI코드": f"A{n:04d}", "EDI명칭": name, "총액": "100", **extra} for n, name in enumerate(names, 1)]


def fd_items(rows, blocks):
    return [row["항목"] for row in rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]]


def test_section_title_from_a_text_block_fills_the_empty_item():
    blocks = [block("05.검사료\nGlucose test\nBilirubin total\n06 .영상\nChest PA")]
    assert fd_items(fd_rows("Glucose test", "Bilirubin total", "Chest PA"), blocks) == ["05.검사료", "05.검사료", "06.영상"]


def test_section_title_from_a_table_cell_and_overlapping_rows_in_one_cell():
    html = "<table><tr><td>05.검사료</td></tr><tr><td>Glucose test<br>Bilirubin total</td><td>A0001</td></tr></table>"
    assert fd_items(fd_rows("Glucose test", "Bilirubin total"), [block(html, kind="table")]) == ["05.검사료"] * 2
    assert fd_items(fd_rows("Glucose test", "Bilirubin total"), [block("05.검사료\nGlucose test\nBilirubin total")]) == ["05.검사료"] * 2


def test_item_copying_the_code_takes_the_section_title():
    rows = fd_rows("Glucose test")
    rows[0]["항목"] = "A0001"
    assert fd_items(rows, [block("05.검사료\nGlucose test")]) == ["05.검사료"]


def test_title_shaped_item_is_kept():
    rows = fd_rows("Glucose test")
    rows[0]["항목"] = "15.SONO"
    assert fd_items(rows, [block("05.검사료\nGlucose test")]) == ["15.SONO"]


@pytest.mark.parametrize("line", ["1.진료비 계산서 영수증은 소득공제 신청 시 사용할 수 있습니다", "6.350"])
def test_notice_and_amount_lines_are_not_section_titles(line):
    assert fd_items(fd_rows("Glucose test"), [block(f"{line}\nGlucose test")]) == [None]


def test_section_titles_search_forward_only_and_skip_total_rows():
    rows = [{"항목": "소계", "EDI명칭": "Glucose test", "총액": "100"}, *fd_rows("Glucose test")]
    assert list(rules._section_items(rows, [block("05.검사료\nGlucose test")])) == [(1, "05.검사료")]


def test_section_checks_use_ocr_titles_too():
    ao = {"항목내역": fd_rows("Glucose test")}
    flags = rules.check("세부내역서", ao, {}, [block("05.검사료\nGlucose test")])
    assert any(flag["rule"] == "DETAIL.SECTION_ITEM" and flag["value"] == "05.검사료" for flag in flags)


def dated(*values):
    return [{"항목": "x", "EDI코드": f"A{n:04d}", "EDI명칭": f"n{n}", "총액": "1", "시작일자": value, "종료일자": value} for n, value in enumerate(values)]


def test_carry_fills_values_printed_only_on_the_first_row_of_a_group():
    rows = dated("20230101", None, None, "20230102", None)
    for row, item in zip(rows, ("가", None, None, "나", None)):
        row["항목"] = item
    out = rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]
    assert [row["항목"] for row in out] == ["가", "가", "가", "나", "나"]
    assert [row["시작일자"] for row in out] == ["20230101"] * 3 + ["20230102"] * 2


def test_carry_keeps_blanks_of_formats_that_print_every_row_and_blanks_above_the_first_value():
    rows = dated("20230101", "20230101", None, "20230102")
    assert [row["시작일자"] for row in rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]] == ["20230101", "20230101", None, "20230102"]
    rows = dated(None, "20230101", None, "20230102")
    assert [row["시작일자"] for row in rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]][:2] == [None, "20230101"]


def test_period_fills_rows_without_dates_and_leaves_the_end_blank_when_no_end_is_printed():
    rows = dated(None, None)
    out = rules.apply("세부내역서", {"항목내역": rows, "환자정보(진료시작일)": "2023-01-02"}, [])["항목내역"]
    assert [(row["시작일자"], row["종료일자"]) for row in out] == [("20230102", None)] * 2
    both = {"항목내역": dated(None, None), "환자정보(진료시작일)": "20230102", "환자정보(진료종료일)": "20230110"}
    assert rules.apply("세부내역서", both, [])["항목내역"][1]["종료일자"] == "20230110"


def test_period_is_not_applied_when_only_some_rows_have_dates():
    out = rules.apply("세부내역서", {"항목내역": dated("20230103", None), "환자정보(진료시작일)": "20230102"}, [])["항목내역"]
    assert out[0]["시작일자"] == "20230103"


def test_admission_period_label_fills_the_detail_period_and_rows():
    blocks = [block(kind="table", rows=[["입원기간", "2020-07-03 ~ 2020-07-11"]])]
    out = rules.apply("세부내역서", {"항목내역": dated(None)}, blocks)
    assert (out["환자정보(진료시작일)"], out["환자정보(진료종료일)"]) == ("20200703", "20200711")
    assert (out["항목내역"][0]["시작일자"], out["항목내역"][0]["종료일자"]) == ("20200703", "20200711")


def test_fill_down_is_idempotent():
    rows = dated(None, None, None)
    rows[0]["항목"] = "A0001"
    blocks = [block("05.검사료\nn0\nn1\n06.영상\nn2")]
    first = rules.apply("세부내역서", {"항목내역": rows, "환자정보(진료시작일)": "20230102"}, blocks)
    assert rules.apply("세부내역서", first, blocks) == first


# ── 세부내역서 통째로 맞바뀐 열(값 꼴·인쇄 자리) ─────────────────────────────────────

DETAIL_HEAD = [("항목", 0), ("코드", 150), ("명칭", 300), ("단가", 500), ("일수", 600), ("총액", 700), ("본인부담금", 850), ("공단부담금", 1000)]


def detail_blocks(*rows, head=DETAIL_HEAD):
    """머리글 줄과 본문 줄(값, x) 행으로 만든 세부내역서 표 블록 하나."""
    lines = [{"text": text, "bbox": [x - 30, 0, x + 30, 20]} for text, x in head]
    lines += [{"text": text, "bbox": [x - 30, 40 * (index + 1), x + 30, 40 * (index + 1) + 20]}
              for index, row in enumerate(rows) for text, x in row]
    return [block(kind="table", lines=lines)]


def paid_rows(pairs, total=None):
    rows = [{"항목": "검사료", "총액": str(a + b), "본인부담": str(a), "공단부담": str(b)} for a, b in pairs]
    return rows + ([{"항목": "합계", "총액": str(sum(total)), "본인부담": str(total[0]), "공단부담": str(total[1])}] if total else [])


PAID = [(2000, 8000), (1000, 4000), (400, 1600), (1400, 5600)]


@pytest.mark.parametrize("crossed,swapped,flagged", [
    (4, True, False),  # 네 행 모두 본인부담 값이 공단부담 머리글 아래 찍혔다 → 맞바꾼다(합계 행까지)
    (3, False, True),  # 넷 중 셋(바른 행의 네 배 미만, 근거가 약하다) → 알리기만 한다
    (2, False, False),  # 엇갈린 행이 바른 행보다 많지 않다
    (0, False, False),  # 머리글 자리와 맞다
])
def test_detail_payer_columns_are_swapped_only_on_consistent_print_positions(crossed, swapped, flagged):
    printed = [[(f"{a:,}", 850), (f"{b:,}", 1000)] for a, b in PAID]
    read = [(b, a) if index < crossed else (a, b) for index, (a, b) in enumerate(PAID)]  # 앞 crossed 행을 엇갈려 읽었다
    blocks = detail_blocks(*printed)

    out = rules.apply("세부내역서", {"항목내역": paid_rows(read, total=(0, 0))}, blocks)["항목내역"]
    flags = [flag for flag in rules.check("세부내역서", {"항목내역": out}, {"항목내역": out}, blocks) if flag["code"] == "column_swap"]

    expected = [(b, a) for a, b in read] if swapped else read
    assert [(int(row["본인부담"]), int(row["공단부담"])) for row in out[:4]] == expected
    assert bool(flags) == flagged


def test_detail_payer_share_alone_only_flags():
    # 머리글 자리 근거가 없는데 본인부담이 넷 중 셋을 넘는다(본인부담률은 20~60%): 값은 그대로 두고 알린다
    rows = paid_rows([(b, a) for a, b in PAID])
    out = rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]

    assert [row["본인부담"] for row in out] == [row["본인부담"] for row in rows]
    assert [flag["column"] for flag in rules.check("세부내역서", {"항목내역": out}, {"항목내역": out}, []) if flag["code"] == "column_swap"] == ["본인부담"]


CODES = [("HOS-01", "AA157"), ("XJ-77", "AL200"), ("DBENO", "650100422"), ("WICEVA", "N0021001")]  # (원내코드, EDI코드) 제자리


@pytest.mark.parametrize("codes,swapped,flagged", [
    ([(b, a) for a, b in CODES], True, False),  # 원내코드 칸이 모두 EDI 꼴, EDI코드 칸은 아니다 → 맞바꾼다
    ([(b, a) for a, b in CODES[:2]], False, True),  # 두 행뿐 → 알리기만
    ([(b, a) for a, b in CODES[:3]] + [("XY-1", "ZZ-2")], False, True),  # 원내코드 칸의 EDI 꼴이 8할 미만 → 알리기만
    ([(b, a) for a, b in CODES[:2]] + CODES[2:], False, False),  # 반만 엇갈렸다  # EDI코드 칸도 EDI 꼴이 섞였다(차이 0.5 미만) → 알리기만
    (CODES, False, False),  # 제자리
])
def test_hospital_and_edi_code_columns_are_told_apart_by_edi_code_shape(codes, swapped, flagged):
    head = [*DETAIL_HEAD[:1], ("원내코드", 100), ("EDI코드", 200), *DETAIL_HEAD[2:]]
    rows = [{"항목": "검사료", "원내코드": a, "EDI코드": b, "총액": "100"} for a, b in codes]
    blocks = detail_blocks(head=head)

    out = rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]
    flags = [flag for flag in rules.check("세부내역서", {"항목내역": out}, {"항목내역": out}, blocks) if flag["code"] == "column_swap"]

    got = [(row["원내코드"], row["EDI코드"]) for row in out]
    pairs = [(b, a) for a, b in codes] if swapped else codes
    assert got == [(rules.normalize("edi", a), rules.normalize("edi", b)) for a, b in pairs]
    assert bool(flags) == flagged


def test_two_codes_printed_in_one_header_cell_are_one_edi_value():
    # '코드' 아래 '{수가코드}'(한 칸 두 줄): 코드 열이 하나라 두 줄을 EDI코드 한 값으로 잇고 원내코드는 비운다(정답지 관례)
    head = [*DETAIL_HEAD[:2], ("{수가코드}", 150), *DETAIL_HEAD[2:]]
    head = [(text, x) for text, x in head]
    lines = [{"text": text, "bbox": [x - 30, 30 if text == "{수가코드}" else 0, x + 30, 50 if text == "{수가코드}" else 20]} for text, x in head]
    rows = [{"항목": "진찰료", "원내코드": "AIAU211", "EDI코드": "AU211", "총액": "100"}] * 3

    out = rules.apply("세부내역서", {"항목내역": rows}, [block(kind="table", lines=lines)])["항목내역"]

    assert [(row["원내코드"], row["EDI코드"]) for row in out] == [(None, "AU211AIAU211")] * 3


def test_a_single_code_column_without_a_stacked_header_does_not_join_values():
    # 코드 열 하나(쌓인 머리글 없음)에 모델이 명칭을 원내코드에 적었다: 다른 열 값을 이어 붙이지 않는다
    rows = [{"항목": "주사료", "원내코드": "수액주사", "EDI코드": "KK052", "총액": "100"}] * 3

    out = rules.apply("세부내역서", {"항목내역": rows}, detail_blocks())["항목내역"]

    assert [row["EDI코드"] for row in out] == ["KK052"] * 3


def test_codes_are_not_swapped_with_a_column_holding_names():
    # 원내코드 칸에 EDI 꼴 코드, EDI코드 칸에 명칭(모델이 열을 밀었다): 코드와 명칭을 맞바꾸지 않고 알리기만 한다
    head = [*DETAIL_HEAD[:1], ("원내코드", 100), ("EDI코드", 200), *DETAIL_HEAD[2:]]
    rows = [{"항목": "주사료", "원내코드": code, "EDI코드": name, "총액": "100"}
            for code, name in (("KK052", "수액주사 KO50"), ("KK053", "수액주사 KD100"), ("MO077", "글리세린 관장"))]
    blocks = detail_blocks(head=head)

    out = rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]

    assert [row["원내코드"] for row in out] == ["KK052", "KK053", "MO077"]
    assert [flag["column"] for flag in rules.check("세부내역서", {"항목내역": out}, {"항목내역": out}, blocks) if flag["code"] == "column_swap"] == ["원내코드"]


@pytest.mark.parametrize("label,standard", [
    ("소계", "소계"), ("소계:", "소계"), ("투약및조제료 소계", "소계"), ("계", "계"), ("계:", "계"), ("(Total)", "계"),
    ("합계", "합계"), ("합 계", "합계"), ("총합계", "합계"), ("총계", "합계"), ("합계:", "합계"),
    ("끝수처리조정금액", "끝수처리조정금액"), ("끝수처리 조정금액", "끝수처리조정금액"), ("끝처리 조정금액", "끝수처리조정금액"),
    ("끝수처리 조정금", "끝수처리조정금액"), ("끝수처리조정금액:", "끝수처리조정금액"), ("조정금액", "조정금액"),
])
def test_detail_summary_row_variants_are_kept_under_the_standard_label_and_not_summed(label, standard):
    """세부내역서 집계 행은 표준 라벨(AO·정답지 관례)로 표에 남고(2026-10-03 정책), 금액 합 검사에서는 빠진다."""
    rows = [{"항목": "진찰료", "EDI코드": "AA157", "총액": "100"}, {"항목": label, "총액": "100"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]

    assert [row["항목"] for row in out] == ["진찰료", standard] and rules.is_total(out[1]) and not rules.is_total(out[0])


@pytest.mark.parametrize("name", ["진찰료", "조정", "검사료", "계산서", "합계표"])
def test_item_names_are_not_summary_rows(name):
    assert not rules.is_total({"항목": name})


def test_a_coded_row_named_like_a_total_is_an_item_row():
    assert not rules.is_total({"항목": "검사료", "EDI코드": "B1010", "EDI명칭": "소계"})
    assert rules.is_total({"항목": "검사료", "EDI명칭": "소계"})


def test_detail_paid_column_stays_blank_on_summary_rows_when_not_printed():
    """급여 열이 인쇄되지 않은 서식(급여가 묶음 제목)은 항목 행·집계 행 모두 급여를 비운다 — 0도 총액 복사도 아니다."""
    blocks = [{"rows": [["항목", "총액", "급여", "급여", "비급여"], ["", "", "본인부담", "공단부담", ""]]}]
    rows = [{"항목": "진찰료", "급여구분": "급여", "총액": "100", "급여": "100"}, {"항목": "소계", "총액": "100", "급여": "0"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]

    assert [row["급여"] for row in out] == [None, None]
    assert [row["급여"] for row in rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]] == [None, None]  # 머리글 근거 없음


def test_detail_printed_paid_column_keeps_summary_row_values():
    """'급여액' 열이 인쇄된 서식은 집계 행의 급여도 인쇄값 그대로다."""
    blocks = [{"rows": [["항목", "코드", "명칭", "급여액", "비급여"], ["진찰료", "AA100", "초진", "100", ""]]}]
    rows = [{"항목": "진찰료", "EDI코드": "AA100", "총액": "100", "급여": "100"}, {"항목": "소계", "총액": "100", "급여": "100"}]

    assert [row["급여"] for row in rules.apply("세부내역서", {"항목내역": rows}, blocks)["항목내역"]] == ["100", "100"]


@pytest.mark.parametrize("row", [
    {"시작일자": "20230311", "종료일자": None, "급여구분": "급여", "총액": "100"},  # 날짜 열 하나: 종료일자 미인쇄
    {"시작일자": "20230311", "종료일자": None, "급여구분": "비급여", "총액": "60000", "비급여": None},  # '급/비' 표시
    {"시작일자": "20230311", "종료일자": None, "급여구분": "비급", "총액": "60000"},  # '비급' 표기 변형
    {"시작일자": "20230311", "종료일자": None, "급여구분": "비급여", "총액": "954.5", "단가": None},  # 소수 금액: 단가로도 옮기지 않는다
])
def test_detail_cells_are_never_copied_from_other_columns(row):
    """칸은 인쇄된 값만 둔다 — 총액을 비급여·단가로, 시작일자를 종료일자로 옮기지 않는다(머리글 있음·없음 두 경로)."""
    blocks = [{"rows": [["일자", "코드", "명칭", "금액", "횟수", "일수", "총액", "급/비"]]}]
    for given in ([], blocks):
        out = rules.apply("세부내역서", {"항목내역": [dict(row)]}, given)["항목내역"][0]
        assert (out["종료일자"], out["비급여"], out["단가"]) == (None, None, None)
        assert out["총액"] == row["총액"] and out["시작일자"] == "20230311" and out["급여구분"]


def test_detail_printed_end_dates_and_uncovered_amounts_are_kept():
    """인쇄된 종료일자·비급여 값은 그대로 둔다(빈 칸만 채우지 않는다)."""
    row = {"시작일자": "20230311", "종료일자": "20230315", "급여구분": "비급여", "총액": "60000", "비급여": "60000"}
    out = rules.apply("세부내역서", {"항목내역": [row]}, [])["항목내역"][0]
    assert (out["종료일자"], out["비급여"]) == ("20230315", "60000")


def test_detail_end_date_prompt_does_not_ask_to_copy_the_start_date():
    hint = doctypes.spec("세부내역서")["tables"]["항목내역"]["종료일자"]
    assert "시작일자와 같다" not in str(hint)


@pytest.mark.parametrize("mark, printed", [("급/비", False), ("비급", False), ("급 / 비", False), ("비급", True)])
def test_detail_uncovered_amounts_under_a_mark_column_are_not_printed(mark, printed):
    """'급/비'·'비급' 표시 열만 있는 서식은 비급여 금액 열이 없다 — 모델이 표시를 보고 옮긴 총액은 지우고 표시는 급여구분에 둔다.
    비급여 열이 함께 인쇄된 서식은 그 값을 둔다."""
    head = ["항목", "코드", "명칭", "단가", "횟수", "일수", "총액", mark, *(["비급여"] if printed else [])]
    row = {"EDI코드": "AA254", "급여구분": "비급여", "단가": "6500", "횟수": "1", "일수": "1", "총액": "6500", "비급여": "6500"}

    out = rules.apply("세부내역서", {"항목내역": [row]}, [{"rows": [head]}])["항목내역"][0]

    assert (out["비급여"], out["급여구분"], out["총액"]) == ("6500" if printed else None, "비급여", "6500")
