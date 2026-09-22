"""doctypes 스키마와 rules 정규화·보충 룰(twin reader 이식분) 테스트."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend import doctypes, rules, verify

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
    ("text", "이상체중감소", "체중증가"),
])
def test_same_still_separates_different_values(kind, a, b):
    assert not rules.same(kind, a, b) and not rules.same(kind, b, a)


def test_rows_same_follows_the_lenient_comparison():
    """표 비교도 같은 규칙을 따른다: 빈 금액 칸 = 0, 접두가 붙은 항목명 = 같은 항목."""
    ao = [{"항목": "진찰료", "본인부담금": "1000", "비급여": None}]
    mine = [{"항목": "(기본항목)진찰료", "본인부담금": "1,000", "비급여": "0"}]

    assert verify._rows_same("진료비영수증", "항목내역", ao, mine)
    assert not verify._rows_same("진료비영수증", "항목내역", ao, [{**mine[0], "본인부담금": "2000"}])


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


def test_check_finds_a_total_row_copied_from_an_item_row_and_a_broken_sum():
    rows = case("[진료비영수증]비급여_급여_오추출됨", "07-extract-bbox.json")["항목내역"]
    fields = {"항목내역": rows, "환자부담총액": "9385610", "진료비총액": "11387230", "공단부담총액": "2001620"}

    found = rules.check("진료비영수증", fields, {}, RECEIPT_BLOCKS)

    assert [flag["row"] for flag in found if flag["code"] == "row_copy"] == [30]
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
    checks = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, RECEIPT_BLOCKS)

    fixed, reason = rules.correct("진료비영수증", checks, {"항목내역": rows}, {"항목내역": mine})["항목내역"]

    assert (fixed[0]["급여"], fixed[0]["비급여"]) == ("0", "9010000")
    assert "no_column" in reason and rows[0]["급여"] == "9010000"  # 입력은 건드리지 않는다


def test_correct_leaves_a_move_docraft_does_not_confirm_to_the_judge():
    rows = receipt(("정액수가(요양병원)", {"급여": "9010000"}))
    checks = rules.check("진료비영수증", {"항목내역": rows}, {}, RECEIPT_BLOCKS)

    assert rules.correct("진료비영수증", checks, {"항목내역": rows}, {}) == {}


def test_correct_adds_a_missing_row_only_when_it_has_no_amounts():
    rows = receipt(("진찰료", {"본인부담금": "1000"}), ("합계", {"본인부담금": "1000"}))
    mine = receipt(("진찰료", {"본인부담금": "1000"}), ("CT진단료", {}), ("MRI진단료", {"비급여": "500000"}))
    checks = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, RECEIPT_BLOCKS)

    fixed, reason = rules.correct("진료비영수증", checks, {"항목내역": rows}, {"항목내역": mine})["항목내역"]

    assert [row["항목"] for row in fixed] == ["진찰료", "CT진단료", "합계"]  # 금액 있는 MRI는 Judge에게 맡긴다
    assert "CT진단료" in reason


def test_apply_keeps_the_final_total_row_of_a_receipt_but_drops_a_subtotal():
    rows = [{"항목": "진찰료", "공단부담금": "1,000"}, {"항목": "소계", "공단부담금": "1,000"},
            {"항목": "계", "공단부담금": "2,000"}]

    out = rules.apply("진료비영수증", {"항목내역": rows}, [])

    assert [row["항목"] for row in out["항목내역"]] == ["진찰료", "합계"]
    assert out["공단부담총액"] == "2000"  # 합계 행은 합계 필드도 채운다


def test_check_does_not_guess_a_missing_column_without_header_evidence():
    """머리글을 못 읽었거나 다른 표만 읽었으면 없는 열이라고 단정하지 않는다."""
    rows = receipt(("처치및수술료", {"비급여": "800000"}))
    other = [{"type": "table", "rows": [["환자등록번호", "환자성명"], ["861025", "홍길동"]]}]

    assert rules.check("진료비영수증", {"항목내역": rows}, {}, []) == []
    assert rules.check("진료비영수증", {"항목내역": rows}, {}, other) == []


def test_headers_find_the_item_row_even_when_cells_are_merged():
    blocks = [{"type": "table", "rows": [["환자등록번호", "환자성명"], ["이비인후과 항목", "급여", "비급여"],
                                          ["본인부담금", "공단부담금", "전액본인부담"]]}]

    cells = rules._headers(blocks)

    assert {"급여", "비급여", "본인부담금"} <= cells
    assert rules._grouped(cells, *rules.GROUPED["급여"][:2]) is True     # 급여는 묶음 제목
    assert rules._grouped(cells, *rules.GROUPED["비급여"][:2]) is False  # 비급여는 독립 열
