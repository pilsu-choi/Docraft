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
    ("필투약및조제료_행위료", "투약및조제료_행위료"), ("필주사료_약품비", "주사료_약품비"),  # 서식 분류 칸 글자
    ("선택항목_CT진단료", "CT진단료"), ("선택항목_기타", "기타"),
    ("선별급여", "선별급여"), ("선택진료료", "선택진료료"), ("필름대", "필름대"),  # 뗀 나머지가 표준 항목이 아니면 둔다
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
    checks = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [])

    fixed, reason = rules.correct("진료비영수증", checks, {"항목내역": rows}, {"항목내역": mine})["항목내역"]

    assert (fixed[0]["선택진료료"], fixed[0]["비급여"]) == ("0", "50000")
    assert "column_shift" in reason


def test_correct_leaves_a_shift_the_judge_should_decide():
    """AO의 대상 열에 이미 값(0이 아닌)이 있으면 함부로 바꾸지 않고 Judge에게 맡긴다."""
    rows = receipt(("초음파진단료", {"선택진료료": "50000", "비급여": "30000"}))
    mine = receipt(("초음파진단료", {"비급여": "50000"}))
    checks = rules.check("진료비영수증", {"항목내역": rows}, {"항목내역": mine}, [])

    assert rules.correct("진료비영수증", checks, {"항목내역": rows}, {"항목내역": mine}) == {}


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


def test_headers_find_the_item_row_even_when_cells_are_merged():
    blocks = [{"type": "table", "rows": [["환자등록번호", "환자성명"], ["이비인후과 항목", "급여", "비급여"],
                                          ["본인부담금", "공단부담금", "전액본인부담"]]}]

    cells = rules._headers(blocks)

    assert {"급여", "비급여", "본인부담금"} <= cells
    assert rules._grouped(cells, *rules.GROUPED["급여"][:2]) is True     # 급여는 묶음 제목
    assert rules._grouped(cells, *rules.GROUPED["비급여"][:2]) is False  # 비급여는 독립 열


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


@pytest.mark.parametrize("raw, expected", [
    ("v22oo", "V2200"), ("AA254 030", "AA254030"), ("{AA000000}", "AA000000"),
    ("650902021", "650902021"), ("MCR3OI", "MCR301"),
])
def test_edi_code_normalize(raw, expected):
    assert rules.normalize("edi", raw) == expected


def test_detail_item_columns_follow_the_ao_convention():
    """세부내역서: 코드는 EDI코드 한 열에 모으고, 비급여 칸과 종료일자를 채우며, 총액을 베낀 급여 칸은 지운다."""
    rows = [{"원내코드": "V2200", "EDI코드": None, "시작일자": "20230311", "종료일자": None,
             "급여구분": "급여", "총액": "12380", "급여": "12,380"},
            {"원내코드": "AA254", "EDI코드": "AA254", "급여구분": "비급여", "총액": "60000"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, [])["항목내역"]

    assert [(row["원내코드"], row["EDI코드"]) for row in out] == [(None, "V2200"), (None, "AA254")]
    assert (out[0]["종료일자"], out[0]["급여"]) == ("20230311", None)
    assert (out[1]["비급여"], out[1]["급여"]) == ("60000", None)


def test_treatment_period_comes_from_the_item_table():
    rows = [{"시작일자": "20191021", "종료일자": "20191104"}, {"시작일자": "20191022", "종료일자": "20191022"}]

    out = rules.apply("세부내역서", {"항목내역": rows}, [])

    assert (out["환자정보(진료시작일)"], out["환자정보(진료종료일)"]) == ("20191021", "20191104")


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
    fixed, reason = rules.correct("진료비영수증", flags, {"항목내역": SHIFTED}, {"항목내역": out})["항목내역"]
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
