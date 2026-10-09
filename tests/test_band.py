"""TABLE_EXTRACT=band: 위치 응답 후처리·띠 자르기·짧은 키 읽기·띠 합치기(band), 금액산정 블록 병합(engine.extract).
합성 이미지와 가짜 provider만 쓴다."""

import threading
from types import SimpleNamespace

import fitz
import pytest

from backend import band, doctypes, engine, latency, verify

ITEM = doctypes.schema("진료비영수증")["properties"]["항목내역"]
KEYS = band.short_keys(ITEM)  # a..g = 본인부담금 … 비급여
GRID = {"item_grid": [100, 300, 700, 800], "header": [100, 300, 700, 340], "first_row": [100, 340, 700, 380],
        "total": [100, 760, 700, 800], "summary": [720, 300, 1000, 800]}


# --- 위치 응답 후처리 ---------------------------------------------------------------


def test_boxes_unwrap_nested_lists_and_clip_the_table_at_a_panel_beside_it():
    found = band.boxes({**GRID, "item_grid": [GRID["item_grid"]], "summary": [[600, 300, 1000, 800]]})
    assert found["grid"] == [100, 300, 600, 800] and found["summary"] == [600, 300, 1000, 800]


@pytest.mark.parametrize("summary", [[720, 300, 1000, 370], None, "x", [1, 2, 3]])
def test_boxes_ignore_a_summary_shorter_than_eight_percent_or_unusable(summary):
    assert "summary" not in band.boxes({**GRID, "summary": summary})


def test_a_summary_below_the_table_leaves_the_table_whole():
    found = band.boxes({**GRID, "summary": [100, 820, 700, 990]})
    assert found["grid"] == GRID["item_grid"] and found["summary"] == [100, 820, 700, 990]


@pytest.mark.parametrize("broken", [{"item_grid": None}, {"header": [1, 2]}, {"first_row": [100, 200, 700, 250]},  # 첫 행이 머리글 위
                                    {"total": [100, 300, 700, 330]}, {"item_grid": [700, 300, 100, 800]}])
def test_boxes_are_none_without_a_usable_table_box(broken):
    assert band.boxes({**GRID, **broken}) is None
    assert band.boxes("x") is None


def test_summary_clip_widens_toward_the_label_column_beside_the_table_and_a_little_all_around_below():
    beside = band.boxes({**GRID, "summary": [600, 400, 1000, 500]})
    assert band.summary_clip(beside) == [0.48, 0.3, 1.0, 0.8]  # 왼쪽 +120, 세로는 표 높이, 오른쪽 +40(1000에서 자름)
    below = band.boxes({**GRID, "summary": [100, 820, 700, 990]})
    assert band.summary_clip(below) == pytest.approx([0.06, 0.79, 0.74, 1.0])


# --- 띠 자르기 ----------------------------------------------------------------------


def test_clips_cut_three_overlapping_bands_with_a_header_strip_that_leaves_out_the_first_row():
    strips = band.clips(band.boxes(GRID))
    assert len(strips) == 3 and [len(s) for s in strips] == [1, 2, 2]
    body = [s[-1] for s in strips]
    assert all(box[0] == 0.08 and box[2] == 0.72 for strip in strips for box in strip)  # 표 가로 ±2%
    assert body[0][1] == 0.29 and body[0][3] == pytest.approx(0.34 + 0.475 / 3 + 0.0475)  # 첫 띠는 머리글 1% 위부터, 본문은 첫 데이터 행 위에서
    assert body[2][3] == pytest.approx(0.815)  # 마지막 합계 행 아래 1.5%
    assert body[1][1] == pytest.approx(0.34 + 0.475 / 3 - 0.0475) and body[1][1] < body[0][3]  # 앞 띠와 본문 높이의 10% 겹침
    assert [s[0] for s in strips[1:]] == [[0.08, 0.29, 0.72, 0.34]] * 2  # 머리글 띠는 첫 데이터 행 위에서 끝난다


def test_located_bands_are_cut_in_the_original_frame_of_a_turned_page():
    upright = engine._clip([0.1, 0.2, 0.5, 0.4], [1, 1], 0)
    turned = engine._clip([0.1, 0.2, 0.5, 0.4], [1, 1], 90)  # 반시계 90도로 세운 쪽: 위 x → 원본 아래
    assert upright == [0.1, 0.2, 0.5, 0.4] and turned == pytest.approx([0.6, 0.1, 0.8, 0.5])
    assert engine._clip([0, 0, 100, 50], [200, 100], 180) == [0.5, 0.5, 1.0, 1.0]


# --- 짧은 키 읽기 -------------------------------------------------------------------


def test_prompt_lists_short_keys_the_standard_names_and_the_all_keys_rule():
    text = band.prompt(ITEM, engine.BAND_NOTE[1])
    assert '"a" = 본인부담금' in text
    assert '"a" = 본인부담금: 급여 본인부담금. 숫자만.\n' in text and "마지막 최종" not in text.split("Short keys")[1].split("Every row")[0]
    assert "진찰료" in text and "never add a row because it is in the list" in text and "ALL keys" in text
    assert engine.BAND_NOTE[1].strip() in text


def test_expand_fills_blank_and_missing_amount_columns_with_zero_and_counts_odd_keys():
    rows, unknown, missing = band.expand([{"n": "진찰료", "a": "1,000", "b": "", "z": "9"}, "x", {"n": "합계", **dict.fromkeys(KEYS, "5")}], ITEM)
    assert unknown == 1 and missing == 1 and len(rows) == 2
    assert rows[0] == {"항목": "진찰료", "본인부담금": "1,000", **dict.fromkeys(list(KEYS.values())[1:], "0")}
    assert set(rows[1].values()) == {"합계", "5"}


def test_overlap_is_the_longest_run_of_similar_names_at_the_end_of_the_rows():
    rows = [{"항목": n} for n in ("진찰료", "입원료_1인실", "투약및조제료")]
    assert band.overlap(rows, [{"항목": "입원료 1인실"}, {"항목": "투약및조제료"}, {"항목": "주사료"}]) == 2
    assert band.overlap(rows, [{"항목": "주사료"}]) == 0
    assert band.overlap([{"항목": "주사료"}] * 3, [{"항목": "주사료"}] * 3) == 3
    assert band.overlap([], [{"항목": "a"}]) == 0


def test_last_total_keeps_only_the_final_total_row():
    rows = [{"항목": "진찰료"}, {"항목": "합계"}, {"항목": "검사료"}, {"항목": "합 계"}]
    assert [r["항목"] for r in band.last_total(rows)] == ["진찰료", "검사료", "합 계"]


# --- engine.extract: 위치 → 띠 + 금액산정 블록 --------------------------------------


@pytest.fixture
def state(monkeypatch, tmp_path):
    for name, value in {"AI_MODE": "provider", "AI_BASE_URL": "https://provider.invalid/v1", "AI_API_KEY": "key", "AI_MODEL": "m",
                        "AI_VISION": "true", "TABLE_PAGE_CONCURRENCY": "1"}.items():
        monkeypatch.setenv(name, value)
    image = tmp_path / "page.png"
    document = fitz.open()
    document.new_page(width=200, height=200)
    document[0].get_pixmap().save(image)
    row = lambda name, **cols: {"n": name, **dict.fromkeys(KEYS, ""), **cols}
    s = SimpleNamespace(image=str(image), calls=[], lock=threading.Lock(), locate=GRID, summary={"납부할금액": "1,000", "진료비총액": ""},
                        fields={"환자정보-성명": "홍길동", "진료비총액": "9,999"}, rows=[], fallback_rows=[["진찰료", "100", None]],
                        bands=[[row("진찰료", a="100", b="900"), row("입원료", a="200")],
                               [row("입원료", a="200"), row("투약료", b="50"), row("합계", a="300", b="950")],
                               [row("검사료", a="7"), row("합계", a="307", b="950")]],
                        blocks=[{"page": 1, "type": "table", "text": "", "rows": [["항목", "요양급여(①+②)", "비급여"]]}])

    def provider(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        content = messages[-1]["content"]
        text, images = (content[-1]["text"], len(content) - 1) if isinstance(content, list) else (content, 0)
        kind = ("locate" if text.startswith("Locate regions") else "summary" if "payment calculation) block" in text
                else "band" if "Short keys" in text else "rows" if json_schema else "fields")
        with s.lock:
            s.calls.append(SimpleNamespace(kind=kind, text=text, images=images, system=messages[0]["content"] if len(messages) > 1 else ""))
            if kind == "band":
                return {"rows": s.bands.pop(0)}
        if kind == "locate":
            return s.locate
        if kind == "summary":
            if isinstance(s.summary, Exception):
                raise s.summary
            return s.summary
        return {"rows": s.fallback_rows} if kind == "rows" else s.fields
    monkeypatch.setattr(engine, "_provider", provider)
    return s


def receipt_schema(*keys):
    return verify._restrict(doctypes.schema("진료비영수증"), {"항목내역", "환자정보-성명", "진료비총액", "납부할금액", *keys})


def kinds(s):
    return sorted(call.kind for call in s.calls)


def test_band_reads_the_located_table_in_three_strips_and_the_summary_block_apart(state):
    result, groundings = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert kinds(state) == ["band"] * 3 + ["fields", "locate", "summary"]
    assert [call.images for call in state.calls if call.kind == "band"] == [1, 2, 2]  # 첫 띠는 머리글째, 나머지는 머리글 띠 + 띠
    assert all(engine.TABLE_NOTE in call.system for call in state.calls if call.kind == "band")
    assert "항목내역" in groundings and result["환자정보-성명"] == "홍길동"


def test_overlapping_rows_are_read_once_blank_cells_are_zero_and_one_total_row_stays(state):
    result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    rows = result["항목내역"]
    assert [row["항목"] for row in rows] == ["진찰료", "입원료", "투약료", "검사료", "합계"]
    assert rows[0] == {"항목": "진찰료", "본인부담금": "100", "공단부담금": "900", **dict.fromkeys(list(KEYS.values())[2:], "0")}
    assert rows[-1]["본인부담금"] == "307"
    assert list(rows[0]) == list(ITEM["items"]["properties"])


def test_summary_block_is_final_for_its_keys_and_the_page_read_leaves_them_out(state):
    result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    fields_call = next(call for call in state.calls if call.kind == "fields")
    assert "환자정보-성명" in fields_call.text and "납부할금액" not in fields_call.text and "진료비총액" not in fields_call.text
    assert result["납부할금액"] == "1,000"
    assert result["진료비총액"] is None  # 블록의 빈칸은 쪽 전체 읽기 값(9,999)으로 메우지 않는다
    summary_call = next(call for call in state.calls if call.kind == "summary")
    assert summary_call.images == 1 and "납부할금액" in summary_call.text and "환자정보-성명" not in summary_call.text


@pytest.mark.parametrize("broken", [RuntimeError("HTTP 500"), ["not", "an", "object"]])
def test_a_summary_block_that_cannot_be_read_falls_back_to_the_page_read(state, broken):
    state.summary = broken
    with latency.track() as stats:
        result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    fields_calls = [call for call in state.calls if call.kind == "fields"]
    assert len(fields_calls) == 2 and "납부할금액" in fields_calls[1].text
    assert result["진료비총액"] == "9,999" and stats["band_fallback"] == "summary"


def test_without_a_summary_box_its_keys_come_from_the_page_read(state):
    state.locate = {**GRID, "summary": None}
    result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert kinds(state) == ["band"] * 3 + ["fields", "locate"]
    assert result["진료비총액"] == "9,999" and "진료비총액" in next(c for c in state.calls if c.kind == "fields").text


def test_band_keys_missing_or_unknown_are_counted_as_diagnostics(state):
    state.bands[0] = [{"n": "진찰료", "a": "1", "q": "2"}]
    with latency.track() as stats:
        engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert stats["band_unknown_keys"] == 1 and stats["band_missing_keys"] == 1


@pytest.mark.parametrize("locate", [{"item_grid": None}, "no json object", RuntimeError("HTTP 500")])
def test_an_unusable_locate_reads_the_table_as_rowmajor(state, monkeypatch, locate):
    state.locate = locate
    with latency.track() as stats:
        result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert kinds(state) == ["fields", "locate", "rows"] and stats["band_fallback"] == "locate"
    assert result["항목내역"][0]["항목"] == "진찰료" and result["진료비총액"] == "9,999"


def test_all_strips_failing_reads_the_table_as_rowmajor(state):
    state.bands = [None] * 3  # 행 목록이 없는 응답
    with latency.track() as stats:
        result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert stats["band_fallback"] == "read" and result["항목내역"][0]["항목"] == "진찰료"


@pytest.mark.parametrize("types, doc_type, mode, located", [
    (None, "진료비영수증", "band", True), ("세부내역서", "진료비영수증", "band", False),
    (None, "세부내역서", "band", False), (None, "진료비영수증", "rowmajor", False)])
def test_band_applies_only_to_the_listed_doc_types(state, monkeypatch, types, doc_type, mode, located):
    if types:
        monkeypatch.setenv("BAND_DOC_TYPES", types)
    schema = verify._restrict(doctypes.schema(doc_type), {"항목내역"})
    engine.extract(schema, state.blocks, state.image, table_extract=mode)

    assert ("locate" in kinds(state)) is located


def test_band_needs_one_page_with_an_image(state):
    engine.extract(receipt_schema(), state.blocks, None, table_extract="band")
    assert "locate" not in kinds(state)
