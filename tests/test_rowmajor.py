"""rowmajor 표 추출(TABLE_EXTRACT): 열 배치 판별(table_layout), 위치 배열 호출과 합집합 열 되돌리기(engine),
열 밀림 시 asis 재추출(verify.read). 모든 LLM 호출은 가짜로 바꾼다."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import fitz
import httpx
import pytest

from backend import doctypes, engine, rules, table_layout, verify

DETAIL = list(doctypes.DOC_TYPES["세부내역서"]["tables"]["항목내역"])
RECEIPT = list(doctypes.DOC_TYPES["진료비영수증"]["tables"]["항목내역"])


def cells(*rows):
    """셀 행으로 만든 표 블록 하나."""
    return [{"type": "table", "rows": [list(row) for row in rows], "text": ""}]


def printed(blocks, union):
    """``printed_columns``의 열 순서(머리글 글자는 뺀다). 못 정하면 None."""
    columns = table_layout.printed_columns(blocks, union)
    return None if columns is None else list(columns)


def header(*lines):
    """(글자, x0, y0) 줄로 만든 표 블록 하나. 줄 폭은 글자 수에 비례한다."""
    return [{"type": "table", "text": "", "lines": [{"text": text, "bbox": [x, y, x + 20 * len(text.replace(" ", "")), y + 20]}
                                                    for text, x, y in lines]}]


# --- 진료비영수증 양식 판별 -------------------------------------------------------


@pytest.mark.parametrize("rows,form", [
    ((["항목", "요양급여(①+②)", "비급여③"], ["진찰료", "100", ""]), 1),
    ((["항목", "급여", "", "", "비급여"], ["", "본인부담금", "공단부담금", "전액본인부담", ""]), 2),
    ((["항목", "본인부담", "선택진료 신청", "비급여"],), 2),  # 신청란의 '선택진료'는 선택진료료 열이 아니다
    ((["항목", "본인부담금", "선택진료료", "선택진료료 이외"],), 4),
    ((["항목", "본인부담금", "선택진료료", "선택진료료 이의"],), 4),  # OCR 오독
    ((["항목", "선택진료료", "본인부담금", "이외"],), 4),  # 칸이 갈린 '이외'
    ((["항목", "본인부담금", "선택진료료", "이외"],), 5),  # 붙은 '선택진료료 이외'는 선택진료료외 한 열이다
    ((["항목", "본인부담금", "선택진료료외"],), 5),
    ((["항목", "본인부담금", "선택진료료"],), None),  # 양식 3인지 '외'를 놓친 양식 4인지 모른다
    ((["항목", "금액"],), None),
])
def test_receipt_form_reads_the_layout_from_header_words(rows, form):
    assert table_layout.receipt_form(cells(*rows)) == form


def test_receipt_form_ignores_non_table_blocks():
    assert table_layout.receipt_form([{"type": "text", "rows": [["요양급여(①+②)"]]}]) is None


def test_receipt_plan_gives_the_printed_columns_with_their_descriptions_and_zero_fill():
    union = dict.fromkeys(RECEIPT, "합집합 설명")
    description, columns, fill = table_layout.plan("진료비영수증", "항목내역", cells(["요양급여(①+②)", "비급여"]), "표", union)

    assert list(columns) == ["항목", "급여", "비급여"]
    assert description == table_layout.FORMS[1]["description"] and columns["급여"] == table_layout.FORMS[1]["columns"]["급여"]
    assert fill == "0"


def test_plan_is_none_when_the_layout_or_table_is_unknown():
    union = dict.fromkeys(RECEIPT, "")
    assert table_layout.plan("진료비영수증", "항목내역", cells(["항목", "금액"]), "표", union) is None
    assert table_layout.plan("진단서", "병명내역", cells(["요양급여(①+②)"]), "표", {"병명": ""}) is None


# --- 세부내역서 머리글 열 순서 ------------------------------------------------------


def test_header_order_follows_the_printed_x_order_and_reads_ocr_typos():
    # 인쇄 순서: 항목 일자 코드 명칭 단가 횟수 일수 투여량 충액(총액 오독) 비급여
    blocks = header(("항목", 0, 0), ("일자", 100, 0), ("코드", 200, 0), ("명칭", 300, 0), ("단가", 500, 0),
                    ("횟수", 600, 0), ("일수", 700, 0), ("투여량", 800, 0), ("충액", 900, 0), ("비급여", 1000, 0))

    assert printed(blocks, DETAIL) == [
        "항목", "시작일자", "EDI코드", "EDI명칭", "단가", "횟수", "일수", "투여량", "총액", "비급여"]


def test_header_splits_merged_words_and_joins_split_words():
    # '수량횟수일수'는 한 줄에 붙었고 '급여 구분'은 띄어 썼다
    blocks = header(("항목", 0, 0), ("일자", 100, 0), ("명칭", 200, 0), ("단가", 300, 0), ("수량횟수일수", 400, 0),
                    ("총액", 700, 0), ("급여 구분", 800, 0))

    columns = printed(blocks, DETAIL)

    assert columns[columns.index("단가"):] == ["단가", "투여량", "횟수", "일수", "총액", "급여구분", "비급여"]


def test_group_title_is_dropped_when_sub_columns_sit_below_it():
    blocks = header(("항목", 0, 0), ("명칭", 100, 0), ("단가", 200, 0), ("일수", 300, 0), ("총액", 400, 0), ("급여", 550, 0),
                    ("본인부담금", 500, 25), ("공단부담금", 650, 25))

    columns = printed(blocks, DETAIL)

    assert "급여" not in columns and columns[-3:] == ["본인부담", "공단부담", "비급여"]


def test_header_without_four_columns_on_one_line_falls_back():
    rotated = header(*[(word, 0, index * 100) for index, word in enumerate(["항목", "명칭", "단가", "일수", "총액"])])
    assert printed(rotated, DETAIL) is None
    assert printed(header(("환자성명", 0, 0)), DETAIL) is None
    assert table_layout.plan("세부내역서", "항목내역", rotated, "표", dict.fromkeys(DETAIL, "")) is None


def test_unread_required_columns_stay_in_union_place_and_unread_optional_columns_are_dropped():
    blocks = header(("항목", 0, 0), ("명칭", 200, 0), ("단가", 300, 0), ("횟수", 400, 0), ("총액", 600, 0))

    columns = printed(blocks, DETAIL)

    # 못 읽은 일자·코드(필수)는 제자리에, 그 개념 낱말을 하나도 못 읽었으니 짝 열(종료일자·원내코드)도 함께 둔다
    assert columns[:5] == ["항목", "시작일자", "종료일자", "원내코드", "EDI코드"]
    assert "일수" in columns and "투여량" not in columns and "선택진료료" not in columns


@pytest.mark.parametrize("words,expected", [
    (["코드"], ["EDI코드"]),  # 코드 낱말 하나 = 코드 열 하나(EDI코드)
    (["처방코드", "EDI코트"], ["원내코드", "EDI코드"]),  # '…코드' 끝말·오독도 코드 열이라 둘을 센다
    (["서발코드", "EDI 코드"], ["원내코드", "EDI코드"]),  # 앞말 오독, 떨어진 'EDI 코드'
    ([], ["원내코드", "EDI코드"]),  # 코드 낱말을 못 읽으면 코드 열 수를 몰라 둘 다 둔다
])
def test_code_columns_are_dropped_only_when_the_header_counted_them(words, expected):
    names = ["항목", "일자", *words, "명칭", "단가", "횟수", "일수", "총액"]
    blocks = header(*[(word, index * 100, 0) for index, word in enumerate(names)])

    columns = printed(blocks, DETAIL)

    assert [column for column in columns if column in ("원내코드", "EDI코드")] == expected
    assert columns.index("EDI명칭") == columns.index("EDI코드") + 1


HEAD = (("항목", 0, 0), ("일자", 200, 0), ("코드", 700, 0), ("명칭", 900, 0), ("단가", 1200, 0), ("일수", 1300, 0), ("총액", 1400, 0))


@pytest.mark.parametrize("body", [
    [("2023.02.22 ~ 2023.03.01", 0, 40), ("2023.02.22 ~ 2023.02.22", 0, 70)],  # 한 줄에 범위
    [("20211101", 60, 40), ("-", 145, 40), ("20211103", 160, 40), ("20211104", 60, 70), ("20211109", 160, 70)],  # 두 줄이 나란히
    [("2021-08-19", 60, 40), ("~2021-08-21", 60, 60), ("2021-08-19", 60, 90), ("~2021-08-19", 60, 110)],  # 한 칸에 쌓인 범위
    [("2018.05.23-", 60, 40), ("2018.05.26", 60, 60), ("2018.05.26-", 60, 90), ("2018.05.26", 60, 110)],  # 범위 표시로 끝나는 윗줄
    [("2020.06.24~06.30", 60, 40), ("2020.07.06~07.06", 60, 70)],  # 연도를 줄인 끝 값
    [("2020-01-01", 60, 40), ("2019-12-21~2020-01-02", 60, 70), ("2019-12-22~2020-01-01", 60, 100), ("2020-01-03", 60, 130)],  # 일부 행만 기간
])
def test_a_single_date_column_printing_a_period_keeps_both_dates(body):
    columns = printed(header(*HEAD, *body), DETAIL)

    assert columns[:3] == ["항목", "시작일자", "종료일자"]


@pytest.mark.parametrize("body", [
    [("20220826", 80, 40), ("20220827", 80, 70), ("20220826", 80, 100)],  # 날짜 하나씩
    [("2023.02.22 ~ 2023.03.01", 800, 40), ("20220826", 80, 70)],  # 범위가 이웃 열(명칭) 칸에 있다
    [("2023.02.22 ~ 2023.03.01", 60, -40)],  # 머리글 위(문서 머리의 진료기간)
])
def test_a_single_date_column_without_periods_stays_one_column(body):
    assert "종료일자" not in printed(header(*HEAD, *body), DETAIL)


@pytest.mark.parametrize("merged", ["본인부담금공단부담금", "본인부당금공단부담금", "본인부담금:공단부담금"])
def test_ocr_merged_amount_headers_are_split_into_both_columns(merged):
    blocks = header(*HEAD, ("급여", 1500, 0), ("일부본인부담", 1500, 25), (merged, 1500, 50), ("비급여", 2000, 0))

    columns = printed(blocks, DETAIL)

    assert columns[-3:] == ["본인부담", "공단부담", "비급여"]


def test_a_header_word_split_over_two_lines_is_joined():
    blocks = header(*HEAD, ("본인부담금", 1500, 0), ("공단부담금", 1650, 0), ("전액", 1800, 0), ("본인부담", 1780, 22), ("비급여", 2000, 0))

    assert printed(blocks, DETAIL)[-4:] == ["본인부담", "공단부담", "전액본인부담", "비급여"]


@pytest.mark.parametrize("misread,kept", [
    (("단민부금", 1620, 0), True),  # 본인부담금 오독: 짝(공단부담) 칸 왼쪽에 본인부담 낱말과 겹치는 글자
    (("(본인일부", 1620, 0), True),
    (("열차", 1620, 0), False),  # 본인부담 낱말과 겹치지 않는 글자는 근거가 아니다
    (("단민부금", 1800, 0), False),  # 짝 칸의 다른 쪽(공단부담 오른쪽)에 있다
    (("단민부금", 1620, 60), False),  # 머리글 줄이 아니다(본문)
])
def test_an_unread_pair_column_is_kept_only_when_its_header_cell_shows_unread_text(misread, kept):
    blocks = header(*HEAD, misread, ("공단부담금", 1700, 0), ("비급여", 2000, 0))

    columns = printed(blocks, DETAIL)

    assert ("본인부담" in columns) == kept
    if kept:
        assert columns.index("본인부담") + 1 == columns.index("공단부담")


def test_a_date_header_ending_in_ilja_is_a_date_column():
    blocks = header(("항목", 0, 0), ("저방일자(시행일자)", 100, 0), ("코드", 500, 0), ("명칭", 600, 0), ("단가", 800, 0), ("총액", 900, 0))

    assert printed(blocks, DETAIL)[:3] == ["항목", "시작일자", "EDI코드"]


@pytest.mark.parametrize("codes,named", [
    (("수가코드", "청구코드"), {"원내코드": "수가코드", "EDI코드": "청구코드"}),
    (("코드", "코드"), {}),  # 같은 글자는 가르는 데 쓸 수 없다
    (("서발코드", "EDI코드"), {}),  # 오독한 머리글은 모델에 보이지 않는다
])
def test_header_plan_names_the_printed_header_of_columns_sharing_a_concept(codes, named):
    blocks = header(("항목", 0, 0), (codes[0], 100, 0), (codes[1], 300, 0), ("명칭", 500, 0), ("단가", 700, 0), ("총액", 800, 0))

    _, columns, _ = table_layout.plan("세부내역서", "항목내역", blocks, "표.", {key: key + " 설명" for key in DETAIL})

    assert {key: text.split("이 문서에서는 '")[1].split("'")[0] for key, text in columns.items() if "이 문서에서는" in text} == named
    assert columns["EDI명칭"] == "EDI명칭 설명"


def test_header_plan_appends_the_order_note():
    blocks = header(("항목", 0, 0), ("명칭", 100, 0), ("단가", 200, 0), ("일수", 300, 0), ("총액", 400, 0))
    description, columns, fill = table_layout.plan("세부내역서", "항목내역", blocks, "표.", {key: key + " 설명" for key in DETAIL})

    assert description == "표." + table_layout.NOTE and columns["단가"] == "단가 설명" and fill is None


# --- engine: 위치 배열 호출 --------------------------------------------------------


@pytest.fixture
def provider(monkeypatch, tmp_path):
    """provider 모드와 페이지 이미지 하나. 호출을 기록하고 json_schema 호출엔 rows, 아니면 objects 를 돌려준다."""
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_MODEL", "test/model")
    monkeypatch.setenv("AI_VISION", "true")
    image = tmp_path / "page.png"
    document = fitz.open()
    document.new_page(width=200, height=200)
    document[0].get_pixmap().save(image)
    state = SimpleNamespace(rows=[], objects=[], calls=[], image=str(image))

    def fake(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        state.calls.append({"messages": messages, "json_schema": json_schema, "max_tokens": max_tokens})
        if json_schema is not None:
            return {"rows": state.rows}
        return state.objects.pop(0) if state.objects else {}
    monkeypatch.setattr(engine, "_provider", fake)
    return state


def detail_schema():
    return verify._restrict(doctypes.schema("세부내역서"), {"환자성명", "항목내역"})


BLOCKS = [{"page": 1, "type": "table", "text": "항목 명칭 단가 일수 총액", "rows": [], "lines": [
    {"text": text, "bbox": [x, 0, x + 40, 20]} for text, x in (("항목", 0), ("명칭", 100), ("단가", 200), ("일수", 300), ("총액", 400))]}]


def test_rowmajor_reads_tables_as_positional_rows_beside_one_call_for_the_other_fields(provider):
    provider.objects = [{"환자성명": "홍길동"}]
    columns = printed(BLOCKS, DETAIL)
    provider.rows = [[{"단가": "100", "일수": "2", "총액": "200", "항목": "진찰료"}.get(column) for column in columns]]

    result, groundings = engine.extract(detail_schema(), BLOCKS, provider.image, table_extract="rowmajor")

    rows_call = next(call for call in provider.calls if call["json_schema"])
    item = rows_call["json_schema"]["properties"]["rows"]["items"]
    assert item["minItems"] == item["maxItems"] == len(columns)
    assert "Position order: 1=항목, 2=시작일자" in rows_call["messages"][1]["content"][-1]["text"]
    other = next(call for call in provider.calls if not call["json_schema"])
    assert len(provider.calls) == 2 and '"항목내역"' not in other["messages"][1]["content"][-1]["text"]
    assert result["환자성명"] == "홍길동" and list(result) == ["환자성명", "항목내역"]
    row = result["항목내역"][0]
    assert list(row) == DETAIL and row["단가"] == "100" and row["총액"] == "200" and row["투여량"] is None
    assert "항목내역" in groundings


def test_rowmajor_receipt_layout_fills_unprinted_columns_with_zero(provider):
    blocks = [{"page": 1, "type": "table", "text": "", "rows": [["항목", "요양급여(①+②)", "비급여"]]}]
    provider.rows = [["진찰료", "1000", None]]
    schema = verify._restrict(doctypes.schema("진료비영수증"), {"항목내역"})

    result, _ = engine.extract(schema, blocks, provider.image, table_extract="rowmajor")

    assert len(provider.calls) == 1
    assert result["항목내역"] == [{**dict.fromkeys(RECEIPT, "0"), "항목": "진찰료", "급여": "1000", "비급여": None}]


@pytest.mark.parametrize("rows", [[], [["진찰료"]]])
def test_a_reply_breaking_the_row_contract_rereads_that_table_asis(provider, rows):
    provider.rows = rows
    provider.objects = [{"항목내역": [{"항목": "진찰료", "총액": "100"}]}]
    schema = verify._restrict(doctypes.schema("세부내역서"), {"항목내역"})

    result, _ = engine.extract(schema, BLOCKS, provider.image, table_extract="rowmajor")

    assert [call["json_schema"] is not None for call in provider.calls] == [True, False]
    assert result["항목내역"][0]["총액"] == "100"


def test_rowmajor_without_page_images_reads_asis(provider):
    provider.objects = [{"항목내역": []}]
    schema = verify._restrict(doctypes.schema("세부내역서"), {"항목내역"})

    engine.extract(schema, BLOCKS, None, table_extract="rowmajor")

    assert [call["json_schema"] for call in provider.calls] == [None]


def test_asis_sends_the_whole_schema_in_one_call_as_before(provider):
    schema = detail_schema()

    engine.extract(schema, BLOCKS, provider.image)

    assert len(provider.calls) == 1 and provider.calls[0]["json_schema"] is None
    assert f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n" in provider.calls[0]["messages"][1]["content"][-1]["text"]
    with pytest.raises(ValueError):
        engine.extract(schema, BLOCKS, provider.image, table_extract="columns")


def test_rowmajor_reply_is_capped_by_the_amounts_in_the_ocr_evidence(provider):
    provider.rows = [["진찰료", "15000", "1", "15000"]]
    blocks = [{**BLOCKS[0], "text": "항목 명칭 단가 일수 총액 진찰료 15,000 1 15,000 검사료 3200 1 3200 1.5"}]

    engine.extract(detail_schema(), blocks, source=provider.image, table_extract="rowmajor")

    call = next(call for call in provider.calls if call["json_schema"])
    columns = call["json_schema"]["properties"]["rows"]["items"]["maxItems"]
    assert call["max_tokens"] == (4 + 20) * (10 * columns + 20)  # 금액 꼴 4개('1.5'·'1'은 아니다) + 20행


def test_a_rowmajor_reply_cut_at_the_cap_reads_the_table_asis(provider, monkeypatch):
    def capped(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        provider.calls.append({"json_schema": json_schema})
        if json_schema is not None:
            raise RuntimeError("AI provider 응답이 토큰 제한으로 잘렸습니다.")
        return {"항목내역": [{"항목": "진찰료"}]}
    monkeypatch.setattr(engine, "_provider", capped)

    result, _ = engine.extract(detail_schema(), BLOCKS, source=provider.image, table_extract="rowmajor")

    assert result["항목내역"] == [{"항목": "진찰료"}] and [bool(call["json_schema"]) for call in provider.calls].count(False) == 2


def test_max_tokens_is_sent_only_when_given(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_MODEL", "test/model")
    bodies = []

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @contextmanager
        def stream(self, method, url, json=None, **kwargs):
            bodies.append(json)
            yield httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]},
                                 request=httpx.Request("POST", url))
    monkeypatch.setattr(engine.httpx, "Client", Client)

    engine._provider([], json_schema={"type": "object"}, max_tokens=500)
    engine._provider([])

    assert bodies[0]["max_tokens"] == 500 and "max_tokens" not in bodies[1]


def test_json_schema_calls_require_the_parameter_and_leave_out_reasoning(monkeypatch):
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("AI_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_MODEL", "test/model")
    monkeypatch.delenv("AI_REASONING", raising=False)
    bodies = []

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @contextmanager
        def stream(self, method, url, json=None, **kwargs):
            bodies.append(json)
            yield httpx.Response(200, json={"choices": [{"message": {"content": '{"rows": []}'}, "finish_reason": "stop"}]},
                                 request=httpx.Request("POST", url))
    monkeypatch.setattr(engine.httpx, "Client", Client)

    engine._provider([], json_schema={"type": "object"})
    engine._provider([])

    assert bodies[0]["response_format"] == {"type": "json_schema", "json_schema": {"name": "response", "schema": {"type": "object"}}}
    assert bodies[0]["provider"] == {"require_parameters": True} and "reasoning" not in bodies[0]
    assert bodies[1]["response_format"] == {"type": "json_object"} and "provider" not in bodies[1] and bodies[1]["reasoning"] == {"enabled": False}


# --- verify.read: 열 밀림 감지 후 asis 재추출 -----------------------------------------


def shifted_rows(bad, good):
    """산술이 어긋난 행 bad개, 맞는 행 good개."""
    return ([{"항목": "검사료", "단가": "100", "횟수": "1", "일수": "1", "총액": str(900 + 100 * index)} for index in range(bad)]
            + [{"항목": "검사료", "단가": "100", "횟수": "1", "일수": "1", "총액": "100"}] * good)


@pytest.fixture
def read_calls(monkeypatch):
    state = SimpleNamespace(first=[], calls=[])

    def extract(schema, blocks, source=None, *, table_extract="asis", **kwargs):
        state.calls.append((table_extract, list(schema["properties"])))
        return {"항목내역": state.first if len(state.calls) == 1 else shifted_rows(0, 3)}, {}
    monkeypatch.setattr(verify, "parse", lambda *args, **kwargs: ("", [{"type": "text", "text": "x", "page": 1}]))
    monkeypatch.setattr(engine, "extract", extract)
    return state


@pytest.mark.parametrize("bad,good,rechecked", [(3, 7, True), (1, 4, False), (0, 0, False)])
def test_rowmajor_table_is_reread_asis_when_row_arithmetic_breaks(monkeypatch, read_calls, bad, good, rechecked):
    monkeypatch.setenv("TABLE_EXTRACT", "rowmajor")
    monkeypatch.setenv("TABLE_RECHECK_RATIO", "0.3")
    read_calls.first = shifted_rows(bad, good)

    _, fields, _ = verify.read("scan.png", "세부내역서", only={"항목내역"}, auto_reprocess=False)

    assert read_calls.calls == [("rowmajor", ["항목내역"])] + ([("asis", ["항목내역"])] if rechecked else [])
    assert all(row["총액"] == "100" for row in fields["항목내역"]) == (rechecked or not bad)


def test_asis_setting_never_rereads(monkeypatch, read_calls):
    monkeypatch.setenv("TABLE_EXTRACT", "asis")
    read_calls.first = shifted_rows(5, 0)

    verify.read("scan.png", "세부내역서", only={"항목내역"}, auto_reprocess=False)

    assert read_calls.calls == [("asis", ["항목내역"])]


def test_table_misses_counts_arithmetic_rows_once_and_only_for_detail_bills():
    paid = lambda row: {**row, "급여구분": "급여", "본인부담": str(int(row["총액"]) - 50) if row["총액"] == "100" else "1", "공단부담": "50"}  # noqa: E731
    rows = [paid(row) for row in shifted_rows(1, 3)]
    fields = {"항목내역": rows}

    assert rules.table_misses("세부내역서", rows, fields) == 0.25  # 어긋난 행 하나가 두 검사에 걸려도 한 번만 센다
    assert rules.table_misses("진료비영수증", rows, fields) == 0.0
    assert rules.table_misses("세부내역서", [], {"항목내역": []}) == 0.0


@pytest.mark.parametrize("blank,kept", [(4, 0), (3, 1), (1, 3)])
def test_table_misses_counts_rows_whose_amounts_are_all_blank(blank, kept):
    # 금액 열을 통째로 비운 응답: 총액이 없어 행 산술로는 실패율 0이다
    rows = [{"항목": "검사료", "EDI코드": "B1010", "EDI명칭": "검사"}] * blank + shifted_rows(0, kept)

    assert rules.table_misses("세부내역서", rows, {"항목내역": rows}) == blank / (blank + kept)


def test_table_misses_counts_collapsed_rows_by_values_that_do_not_fit_their_column():
    # 무너진 표: 코드가 날짜·금액 칸에, 명칭이 금액 칸에 흘렀다(값 둘 이상이 열 종류에 맞지 않는 행)
    broken = {"항목": "20221202", "시작일자": "D0002014", "단가": "1,056", "전액본인부담": "D2252004", "비급여": "요 일반검사"}
    one_off = {"항목": "검사료", "시작일자": "D0002014", "단가": "1,056", "총액": "1,056", "횟수": "1", "일수": "1"}  # 한 칸만 틀림
    rows = [broken] * 3 + [one_off]

    assert rules.table_misses("세부내역서", rows, rules.apply("세부내역서", {"항목내역": rows}, [])) == 0.75


@pytest.mark.parametrize("rows,rechecked", [
    (shifted_rows(4, 6), False),  # 가산처럼 일부 행만 어긋나면(기본 0.6 미만) 다시 읽지 않는다
    (shifted_rows(7, 3), True),  # 열이 밀리면 행 대부분이 어긋난다
    ([{"항목": "검사료", "EDI코드": "B1010"}] * 5, True),  # 금액을 통째로 비웠다
])
def test_default_gate_rereads_only_broken_tables(monkeypatch, read_calls, rows, rechecked):
    monkeypatch.setenv("TABLE_EXTRACT", "rowmajor")
    monkeypatch.delenv("TABLE_RECHECK_RATIO", raising=False)
    read_calls.first = rows

    verify.read("scan.png", "세부내역서", only={"항목내역"}, auto_reprocess=False)

    assert len(read_calls.calls) == 1 + rechecked


# --- 돌아간 페이지(orientation) ----------------------------------------------------


@pytest.mark.parametrize("turn", [90, 180, 270])
def test_header_order_is_read_on_the_upright_page_of_a_turned_block(turn):
    from backend.parsers import unturn
    upright = [{**header(("항목", 0, 0), ("코드", 200, 0), ("명칭", 300, 0), ("단가", 500, 0), ("일수", 700, 0), ("총액", 900, 0))[0],
                "page_size": [1200, 400]}]
    turned = unturn(upright, turn)  # 원본(돌아간) 페이지 좌표로 보고된 블록

    assert turned[0]["orientation"] == turn
    assert printed(turned, DETAIL) == printed(upright, DETAIL)


def test_rowmajor_page_image_is_turned_upright(provider, monkeypatch):
    turns = []
    monkeypatch.setattr(engine, "_page_images", lambda source, pages, turns_=None: turns.append(turns_) or ["data:x"])
    provider.objects = [{"환자성명": "홍길동"}]
    blocks = [{**BLOCKS[0], "orientation": 90}]

    engine.extract(detail_schema(), blocks, provider.image, table_extract="rowmajor")

    assert turns and all(t == {1: 90} for t in turns)
