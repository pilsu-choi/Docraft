"""doctypes 스키마와 rules 정규화·보충 룰(twin reader 이식분) 테스트."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend import doctypes, rules

AO_SAMPLES = Path("/home/pilsu/projects/mirae-assets/harness-v2/docs/agentic-ocr-2.0.1-results")


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


def test_total_row_moves_to_total_fields():
    rows = [{"항목": "진찰료", "본인부담": "1,000", "공단부담": "2,000"},
            {"항목": "합 계", "본인부담": "5,000", "공단부담": "7,000"}]
    out = rules.apply("세부내역서", {"항목내역": rows}, [])
    assert [row["항목"] for row in out["항목내역"]] == ["진찰료"]
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
            if document["doc_type"] != doc_type:
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
    properties = doctypes.schema(doc_type)["properties"]
    # 표가 있는 문서에서는 표로 나오는 내역 필드는 표로만 정의한다.
    assert scalars <= set(properties), scalars - set(properties)
    for table, headers in tables.items():
        assert table in properties, table
        assert headers <= set(properties[table]["items"]["properties"]), headers
