"""TABLE_EXTRACT=band: 위치 응답 후처리·띠 자르기·짧은 키 읽기·띠 합치기(band), 금액산정 블록 병합(engine.extract).
합성 이미지와 가짜 provider만 쓴다."""

import concurrent.futures
import copy
import hashlib
import threading
import time
from types import SimpleNamespace

import fitz
import pytest

from backend import band, doctypes, engine, latency, rules, verify

ITEM = doctypes.schema("진료비영수증")["properties"]["항목내역"]
DEV_PROMPT_SHA256 = "c96e890181e9aca410a145426f917b644d0e8da37e2422bb1b3df819a079f953"  # BAND_HEADER_NOTE 도입 전 dev(0751745) 띠 프롬프트
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


def labels(*places):
    """금액산정 패널 OCR 줄(쪽 1000 정규화): ``places``는 (글자, 왼쪽 x, 위 y)."""
    return [{"text": text, "bbox": [x, y, x + 60, y + 20]} for text, x, y in places]


PANEL = labels(("진료비 총액", 660, 400), ("환자부담 총액", 660, 450), ("납부할 금액", 662, 500), ("카드", 700, 550))


@pytest.mark.parametrize("grid, summary, lines, right", [
    ([100, 300, 700, 800], [600, 300, 1000, 800], PANEL, 660),  # 패널 상자가 표 맨 오른쪽 열(600~660)을 덮었다: 라벨 왼쪽 끝까지 둔다
    ([100, 300, 600, 800], [650, 300, 1000, 800], PANEL, 660),  # 표 상자가 맨 오른쪽 열 앞에서 끝났다: 라벨 왼쪽 끝까지 넓힌다
    ([100, 300, 700, 800], [600, 300, 1000, 800], PANEL + labels(("빠른 쾌유를 바랍니다", 610, 600), ("이성", 640, 650)), 660),  # 걸친 글·오독은 정렬선 밖
    ([100, 300, 700, 800], [600, 300, 1000, 800], labels(("진료비 총액", 660, 310)), 600),  # 라벨이 표 본문 높이 밖(머리글 줄): 근거 없음, 상자에서 자른다
    ([100, 300, 700, 800], [600, 300, 1000, 800], [], 600),  # OCR 없음: 상자에서 자른다
    ([100, 300, 700, 800], [100, 820, 700, 990], PANEL, 700),  # 패널이 표 아래: 표 그대로
])
def test_the_table_ends_where_the_panel_labels_begin(grid, summary, lines, right):
    assert band.boxes({**GRID, "item_grid": grid, "summary": summary}, lines)["grid"][2] == right


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


def test_clip_is_the_share_of_the_turned_page():
    assert engine._clip([0.1, 0.2, 0.5, 0.4], [1, 1]) == [0.1, 0.2, 0.5, 0.4]
    assert engine._clip([0, 0, 100, 50], [200, 100]) == [0, 0, 0.5, 0.5]


# --- 짧은 키 읽기 -------------------------------------------------------------------


def test_prompt_lists_short_keys_the_standard_names_and_the_all_keys_rule():
    text = band.prompt(ITEM, engine.BAND_NOTE[1])
    assert '"a" = 본인부담금' in text
    assert '"a" = 본인부담금: 급여 본인부담금. 숫자만.\n' in text and "마지막 최종" not in text.split("Short keys")[1].split("Every row")[0]
    assert "진찰료" in text and "never add a row because it is in the list" in text and "ALL keys" in text
    assert engine.BAND_NOTE[1].strip() in text


def test_header_note_is_only_added_when_switched_on_and_off_keeps_the_dev_prompt():
    on, off = band.prompt(ITEM, engine.BAND_NOTE[0], True), band.prompt(ITEM, engine.BAND_NOTE[0])
    assert band.HEADER_NOTE not in off and on.replace(band.HEADER_NOTE + "\n", "") == off  # 꺼짐 = dev 프롬프트 그대로
    assert hashlib.sha256(off.encode()).hexdigest() == DEV_PROMPT_SHA256  # dev 0751745 의 band.prompt(ITEM, BAND_NOTE[0]) 와 바이트 동일
    assert "'선택진료료 / 이외'" in on and "0 under 비급여" in on  # 스키마 비급여 설명(묶음 제목이면 0)과 같은 관례
    assert "묶는 제목이면 0" in ITEM["items"]["properties"]["비급여"]["description"]


def test_band_reads_strips_with_the_header_note_by_default_and_without_it_when_switched_off(monkeypatch):
    seen = []
    monkeypatch.setattr(engine, "_provider", lambda messages, **kw: seen.append(messages[-1]["content"][-1]["text"]) or {"rows": []})
    for value in ("false", "", "true"):
        monkeypatch.setenv("BAND_HEADER_NOTE", value) if value else monkeypatch.delenv("BAND_HEADER_NOTE", raising=False)
        engine._read_keyed(ITEM, ["data:image/jpeg;base64,"], engine.BAND_NOTE[0])
    assert band.HEADER_NOTE not in seen[0] and band.HEADER_NOTE in seen[1] and band.HEADER_NOTE in seen[2]


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
                        blocks=[{"page": 1, "type": "table", "text": "", "rows": [["항목", "요양급여(①+②)", "비급여"]]}],
                        locate_delay=0, spawned=[])

    def provider(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        content = messages[-1]["content"]
        text, images = (content[-1]["text"], len(content) - 1) if isinstance(content, list) else (content, 0)
        kind = ("locate" if text.startswith("Locate regions") else "summary" if "payment calculation) block" in text
                else "band" if "Short keys" in text else "rows" if "Extract this table now" in text else "fields")
        with s.lock:
            s.calls.append(SimpleNamespace(kind=kind, text=text, images=images, system=messages[0]["content"] if len(messages) > 1 else "",
                                           json_schema=json_schema, max_tokens=max_tokens, image=content[0]["image_url"]["url"] if images else None))
            if kind == "band":
                return {"rows": s.bands.pop(0)}
        if kind == "locate":
            time.sleep(s.locate_delay)
            if isinstance(s.locate, Exception):
                raise s.locate
            return s.locate
        if kind == "summary":
            if isinstance(s.summary, Exception):
                raise s.summary
            return s.summary
        return {"rows": s.fallback_rows} if kind == "rows" else s.fields
    monkeypatch.setattr(engine, "_provider", provider)
    spawn = latency.spawn  # 먼저 보낸 호출이 테스트 뒤(가짜 provider를 걷은 뒤)까지 남지 않게 끝을 기다린다
    monkeypatch.setattr(engine, "spawn", lambda *args: s.spawned.append(spawn(*args)) or s.spawned[-1])
    yield s
    concurrent.futures.wait(s.spawned)


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


@pytest.mark.parametrize("speculate", [False, True])
def test_without_a_summary_box_its_keys_come_from_the_page_read(state, monkeypatch, speculate):
    monkeypatch.setenv("BAND_SPECULATE", str(speculate))
    state.locate = {**GRID, "summary": None}
    with latency.track() as stats:
        result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert kinds(state) == ["band"] * 3 + ["fields"] * (1 + speculate) + ["locate"]  # 먼저 읽은 나머지 필드는 버리고 다시 읽는다
    assert stats.get("band_speculate") == ("reread" if speculate else None)
    assert result["진료비총액"] == "9,999" and any("진료비총액" in c.text for c in state.calls if c.kind == "fields")


def test_band_keys_missing_or_unknown_are_counted_as_diagnostics(state):
    state.bands[0] = [{"n": "진찰료", "a": "1", "q": "2"}]
    with latency.track() as stats:
        engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert stats["band_unknown_keys"] == 1 and stats["band_missing_keys"] == 1


@pytest.mark.parametrize("locate", [{"item_grid": None}, "no json object", RuntimeError("HTTP 500")])
def test_an_unusable_locate_reads_the_table_as_rowmajor(state, monkeypatch, locate):
    monkeypatch.setenv("BAND_SPECULATE", "true")
    state.locate = locate
    with latency.track() as stats:
        result, _ = engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")

    assert kinds(state) == ["fields", "fields", "locate", "rows"] and stats["band_fallback"] == "locate"  # 먼저 읽은 것 + 다시 읽은 것
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


def test_band_locates_the_table_end_from_the_upright_ocr_lines_of_the_page(state):
    located = {}
    state.blocks = [{**state.blocks[0], "page_size": [200, 200], "lines": [{"text": text, "bbox": [150, y, 190, y + 4]} for text, y in
                                                                          (("진료비 총액", 80), ("환자부담 총액", 90), ("납부할 금액", 100))]}]
    engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band", located=located)
    assert located["grid"][2] == 750  # 쪽 크기 200 → 1000 정규화한 패널 라벨 왼쪽 끝(표 상자 700보다 오른쪽)


def test_band_needs_one_page_with_an_image(state):
    engine.extract(receipt_schema(), state.blocks, None, table_extract="band")
    assert "locate" not in kinds(state)


# --- 지연 줄이기: 위치 먼저 찾기(BAND_PRELOCATE)·나머지 필드 먼저 읽기(BAND_SPECULATE)·띠 수·짧은 응답 ----------


def run(state, monkeypatch, blocks=None, schema=None, **env):
    """state를 처음 응답으로 되돌리고 환경변수를 바꿔 extract한 (결과, 근거, 호출 종류, 단계 값). 지연 줄이기 두 갈래는 켠 채로 본다(기본은 끔)."""
    for name, value in {"BAND_PRELOCATE": "true", "BAND_SPECULATE": "true", **env}.items():
        monkeypatch.setenv(name, value)
    state.calls.clear()
    state.bands = copy.deepcopy(state.first_bands)
    with latency.track() as stats:
        prelocated = engine.prelocate(schema or receipt_schema(), state.image, "band")
        result = engine.extract(schema or receipt_schema(), blocks or state.blocks, state.image, table_extract="band",
                                **({"prelocated": prelocated} if prelocated else {}))
    return result, kinds(state), stats


@pytest.fixture
def replay(state):
    state.first_bands = copy.deepcopy(state.bands)
    return state


@pytest.mark.parametrize("locate, summary", [(GRID, None), ({**GRID, "summary": None}, None), ({"item_grid": None}, None),
                                             (GRID, RuntimeError("HTTP 500")), (TimeoutError("deadline"), None)])
def test_reading_early_gives_the_same_result_in_every_branch(replay, monkeypatch, locate, summary):
    """위치 먼저 찾기·나머지 필드 먼저 읽기를 켜도 켜지 않은 읽기와 결과가 같다: 금액산정 상자를 찾음·못 찾음·위치 실패·
    블록 읽기 실패·위치 호출 예외 모두. 가짜 provider는 같은 요청에 같은 답을 낸다."""
    replay.locate, replay.summary, replay.locate_delay = locate, summary, 0.05
    outcomes = []
    for on in ("false", "true"):
        try:
            outcomes.append(run(replay, monkeypatch, BAND_PRELOCATE=on, BAND_SPECULATE=on)[:2])
        except TimeoutError as exc:
            outcomes.append((repr(exc), kinds(replay)))
    (before, before_calls), (after, after_calls) = outcomes
    assert after == before
    if locate is GRID and summary is None:
        assert after_calls == before_calls  # 금액산정 상자를 찾으면 호출이 늘지 않는다


def test_the_other_fields_are_read_while_the_locate_reply_is_pending(replay, monkeypatch):
    replay.locate_delay = 0.2
    run(replay, monkeypatch, BAND_PRELOCATE="false")
    order = [call.kind for call in replay.calls]
    assert order.index("fields") < order.index("band")  # 띠는 위치 응답 뒤에만 시작한다


def test_speculation_off_reads_the_other_fields_after_the_locate_reply(replay, monkeypatch):
    replay.locate_delay = 0.1
    run(replay, monkeypatch, BAND_PRELOCATE="false", BAND_SPECULATE="false")
    order = [call.kind for call in replay.calls]
    assert order[0] == "locate" and "fields" in order[1:]


def test_an_unturned_page_uses_the_locate_reply_sent_before_ocr(replay, monkeypatch):
    _, calls, stats = run(replay, monkeypatch)
    assert calls.count("locate") == 1 and stats["band_prelocate"] == "used"


@pytest.mark.parametrize("turn", [{"skew": 0.4}, {"orientation": 90}])
def test_a_page_ocr_turned_is_located_again_on_its_turned_image(replay, monkeypatch, turn):
    blocks = [{**replay.blocks[0], **turn}]
    expected = run(replay, monkeypatch, blocks, BAND_PRELOCATE="false")[0]
    result, calls, stats = run(replay, monkeypatch, blocks, BAND_PRELOCATE="true")
    assert (calls.count("locate"), stats.get("band_prelocate")) == (2, "turned")
    assert result == expected


@pytest.mark.parametrize("env, doc_type, mode, pages", [({"BAND_PRELOCATE": "false"}, "진료비영수증", "band", 1),
                                                       ({}, "세부내역서", "band", 1), ({}, "진료비영수증", "rowmajor", 1),
                                                       ({}, "진료비영수증", "band", 2), ({"AI_API_KEY": ""}, "진료비영수증", "band", 1),
                                                       ({"AI_VISION": "false"}, "진료비영수증", "band", 1)])
def test_prelocate_starts_only_where_extract_would_locate(state, monkeypatch, tmp_path, env, doc_type, mode, pages):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    source = tmp_path / "doc.pdf"
    document = fitz.open()
    for _ in range(pages):
        document.new_page(width=200, height=200)
    document.save(source)
    schema = verify._restrict(doctypes.schema(doc_type), {"항목내역"})
    assert engine.prelocate(schema, str(source), mode) is None and state.calls == []
    assert engine.prelocate(receipt_schema(), str(tmp_path / "missing.png"), "band") is None


def test_read_sends_the_locate_call_while_ocr_runs(replay, monkeypatch):
    monkeypatch.setenv("BAND_PRELOCATE", "true")
    located = threading.Event()
    replay.calls = type("Calls", (list,), {"append": lambda self, call: (list.append(self, call), call.kind == "locate" and located.set())})()

    def parse(*args):  # OCR이 끝나기 전에 위치 호출이 와야 돌아온다
        assert located.wait(5)
        return "", copy.deepcopy(replay.blocks)
    monkeypatch.setattr(verify, "parse", parse)
    replay.bands = copy.deepcopy(replay.first_bands)
    with latency.track() as stats:
        verify.read(replay.image, "진료비영수증", {"항목내역", "환자정보-성명", "진료비총액", "납부할금액"}, auto_reprocess=False)
    assert kinds(replay).count("locate") == 1 and stats["band_prelocate"] == "used"
    assert {"parse_ms", "extract_ms", "post_ms"} <= set(stats)


@pytest.mark.parametrize("count", [2, 4])
def test_band_strips_sets_the_number_of_strips(replay, monkeypatch, count):
    replay.first_bands = (replay.first_bands * 2)[:count]
    _, calls, _ = run(replay, monkeypatch, BAND_STRIPS=str(count))
    assert calls.count("band") == count
    strips = band.clips(band.boxes(GRID), count)
    assert len(strips) == count and strips[-1][-1][3] == pytest.approx(0.815)


@pytest.mark.parametrize("compact", [False, True])
def test_compact_reply_asks_for_one_line_json_with_capped_tokens(replay, monkeypatch, compact):
    run(replay, monkeypatch, COMPACT_REPLY=str(compact))
    calls = {call.kind: call for call in replay.calls}
    assert all(call.system.endswith(engine.COMPACT_NOTE) is compact for kind, call in calls.items() if kind != "locate")
    fields = calls["fields"]
    assert (fields.json_schema is not None) is compact and (fields.max_tokens == 60 * 1 + 100 if compact else fields.max_tokens is None)
    assert calls["summary"].max_tokens == (60 * 2 + 100 if compact else 1500)


def test_a_skewed_upright_page_uses_the_straightened_locate_image_sent_before_ocr(replay, monkeypatch, tmp_path):
    """OCR 전에 픽셀로 잰 기울기(parsers.page_tilt)로 바로 세운 이미지가 OCR 뒤 extract가 보낼 이미지와 바이트까지 같아 그 답을 쓴다."""
    from PIL import Image, ImageDraw
    page = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(page)
    for y in range(100, 1500, 40):  # 인쇄 줄 같은 가로 막대
        draw.rectangle([100, y, 1100, y + 12], fill="black")
    replay.image = str(tmp_path / "skewed.png")
    page.rotate(-2, Image.BICUBIC, expand=False, fillcolor="white").save(replay.image)
    from backend import parsers
    skew = parsers.page_tilt(replay.image)
    assert skew  # 2도 남짓 기울어 있다
    blocks = [{**replay.blocks[0], "skew": skew}]
    result, calls, stats = run(replay, monkeypatch, blocks)
    locate = next(call for call in replay.calls if call.kind == "locate")
    assert calls.count("locate") == 1 and stats["band_prelocate"] == "used"
    assert locate.image == engine._page_images(replay.image, [1], engine._turns(blocks))[0]
    assert result == run(replay, monkeypatch, blocks, BAND_PRELOCATE="false")[0]
    _, calls, stats = run(replay, monkeypatch, [{**replay.blocks[0], "skew": skew, "orientation": 90}], BAND_PRELOCATE="true")  # 90도 돌렸으면 다시 찾는다
    assert (calls.count("locate"), stats.get("band_prelocate")) == (2, "turned")


# --- 세부내역서: 위치 찾기 없이 OCR 행 경계로 자른 띠(BAND_DOC_TYPES=진료비영수증,세부내역서) ---------------------------

DETAIL = doctypes.schema("세부내역서")["properties"]["항목내역"]
DPROPS = DETAIL["items"]["properties"]
DKEYS = band.short_keys(DETAIL, "세부내역서")


def detail_row(**cols):
    """세부내역서 짧은 키 행(스키마 전체 열): 열 이름으로 준 값 외에는 빈칸."""
    names = {column: key for key, column in DKEYS.items()}
    return {key: "" for key in DKEYS} | {names[column]: value for column, value in cols.items()}


def detail_blocks(rows, wrapped=(), lines=True):
    """1쪽 세부내역서 표 블록(쪽 1000×1000): 머리글 줄 아래 금액이 찍힌 인쇄 행 ``rows``개(행 간격 STEP, 줄 높이 0.4 STEP), ``wrapped`` 번호
    행은 명칭이 다음 줄로 이어진다(금액 없는 줄)."""
    step = STEP(rows)
    text = [{"text": "항목 | 코드 | 명칭 | 금액 | 본인부담", "bbox": [60, 240 - step, 940, 240 - 0.6 * step]}]
    for i in range(rows):
        y = 240 + i * step
        text.append({"text": f"진찰료 | AA154 | 초진진찰료 | {10000 + i:,}", "bbox": [60, y, 940, y + 0.4 * step]})
        if i in wrapped:
            text.append({"text": "(이어 쓴 명칭)", "bbox": [300, y + 0.45 * step, 500, y + 0.8 * step]})
    return [{"page": 1, "type": "table", "text": "\n".join(line["text"] for line in text), "page_size": [1000, 1000],
             "bbox": [50, 200, 950, 245 + rows * step], **({"lines": text} if lines else {})}]


def STEP(rows):
    return min(20, 700 / rows)  # 표가 쪽 안에 든다


def body(strip):
    """띠 본문 크롭의 위·아래(쪽 1000 기준)."""
    return strip["clips"][-1][1] * 1000, strip["clips"][-1][3] * 1000


@pytest.mark.parametrize("rows, count", [(1, 1), (5, 1), (12, 1), (13, 2), (30, 3), (31, 3), (60, 5), (100, 8)])
def test_detail_bands_cut_between_printed_rows_about_twelve_rows_a_band(rows, count):
    blocks = detail_blocks(rows, wrapped={0, 11, 12, rows - 1})
    bands = engine._bands(blocks, len(DPROPS), band.PROFILES["세부내역서"]["rows"])
    assert len(bands) == count and not any(b.get("repeats") for b in bands)  # 행 사이에서 자르므로 되풀이 행이 없다
    lines = blocks[0]["lines"][1:]
    for line in lines:  # 어느 줄도 띠 경계에 걸치지 않고, 띠 하나에만 든다(이어 쓴 명칭 줄은 제 행과 같은 띠)
        middle = (line["bbox"][1] + line["bbox"][3]) / 2
        assert sum(top <= middle <= bottom for top, bottom in map(body, bands)) == 1
        assert not any(line["bbox"][1] < edge < line["bbox"][3] for b in bands for edge in body(b))
    sizes = [sum(top <= (line["bbox"][1] + line["bbox"][3]) / 2 <= bottom for line in lines if "," in line["text"]) for top, bottom in map(body, bands)]
    assert sum(sizes) == rows and max(sizes) <= -(-rows // count) and (max(sizes) <= 12 or count == engine.MAX_STRIPS)
    assert [len(b["clips"]) for b in bands] == [1] + [2] * (count - 1)  # 뒤 띠에는 머리글 띠가 첫 이미지로 붙는다
    top = pytest.approx((240 - 1.1 * STEP(rows)) / 1000)  # 머리글 줄 위 행 높이(0.4 STEP) 1/4 여백 — 표 블록 상자(0.2)가 아니다
    assert all(b["clips"][0] == [0.05, top, 0.95, pytest.approx((240 - 0.3 * STEP(rows)) / 1000)] for b in bands[1:])  # 머리글 줄과 첫 행 사이에서 끝나는 머리글 띠
    assert bands[0]["clips"][0][1] == top and "항목 | 코드" in bands[-1]["text"]  # 첫 띠는 머리글째, 띠 글자에는 머리글 줄


def test_rowmajor_fallback_bands_keep_their_amount_budget_and_repeats():
    assert engine._bands(detail_blocks(20), len(DPROPS)) == []  # 응답 상한 기준이면 20행은 한 덩어리: 다시 읽을 띠가 아니다
    bands = engine._bands(detail_blocks(200), len(DPROPS))
    assert len(bands) > 1 and all(b.get("repeats") for b in bands[1:])


def test_detail_prompt_keys_every_column_and_leaves_out_the_receipt_form_notes():
    text = band.prompt(DETAIL, engine.BAND_NOTE[1], True, "세부내역서")
    assert list(DKEYS.values()) == list(DPROPS) and DKEYS["a"] == "항목"  # 항목도 짧은 키 열(행 이름 n 없음)
    assert '"a" = 항목: 진료 항목 구분명.' in text and doctypes.DETAIL_HINT not in text.split("Short keys")[1].split("Every row")[0]
    assert '"n": "<' not in text and "every key (a, b," in text
    for receipt_only in ("Reading aid", rules.ITEM_ORDER[0] + ", ", band.LAYOUTS, band.HEADER_NOTE, "A blank cell is 0"):
        assert receipt_only not in text
    assert "끝수처리 조정금액" in text and "A blank cell is null" in text and engine.BAND_NOTE[1].strip() in text


def test_detail_expand_keeps_blank_cells_of_every_column_kind_null():
    rows, unknown, missing = band.expand([detail_row(항목="진찰료", EDI코드="AA154", 총액="17,610", 일수="1", 본인부담="")], DETAIL, "세부내역서")
    assert (unknown, missing) == (0, 0) and list(rows[0]) == list(DPROPS)
    assert rows[0]["항목"] == "진찰료" and rows[0]["총액"] == "17,610" and rows[0]["일수"] == "1"
    assert rows[0]["본인부담"] is None and rows[0]["시작일자"] is None and rows[0]["급여구분"] is None and rows[0]["EDI명칭"] is None  # 금액·날짜·enum·글자
    assert band.expand([{"a": "합계"}], DETAIL, "세부내역서")[0][0]["총액"] is None  # 빠진 금액 열도 0으로 채우지 않는다


PLAN = (DETAIL["description"] + " 열 배치 안내.", {"항목": DPROPS["항목"]["description"], "EDI코드": DPROPS["EDI코드"]["description"] + " 이 문서에서는 '코드' 열이다.",
                                              "EDI명칭": DPROPS["EDI명칭"]["description"], "단가": DPROPS["단가"]["description"], "횟수": DPROPS["횟수"]["description"],
                                              "일수": DPROPS["일수"]["description"], "총액": DPROPS["총액"]["description"],
                                              "본인부담": DPROPS["본인부담"]["description"], "기타": "알 수 없는 열."}, None)


def test_detail_prompt_asks_only_the_planned_columns_in_printed_order():
    keys = band.short_keys(DETAIL, "세부내역서", PLAN)
    assert list(keys.values()) == list(PLAN[1])  # 인쇄 순서, 스키마 밖 열도 물어 자리를 지킨다
    text = band.prompt(DETAIL, engine.BAND_NOTE[0], False, "세부내역서", PLAN)
    assert '"b" = EDI코드: EDI 코드.' in text and "이 문서에서는 '코드' 열이다." in text and doctypes.DETAIL_HINT not in text.split("Short keys")[1].split("Every row")[0]
    assert "급여구분" not in text.split("Short keys")[1].split("Every row")[0] and "every key (a, b, c, d, e, f, g, h, i) in this order" in text
    assert "Rules (same as the schema): " + PLAN[0] in text
    assert band.prompt(DETAIL, engine.BAND_NOTE[0], False, "세부내역서") != text  # 배치가 없으면 스키마 전체 열


def test_detail_expand_puts_planned_values_under_schema_columns_and_fills_the_rest():
    keys = {column: key for key, column in band.short_keys(DETAIL, "세부내역서", PLAN).items()}
    reply = [{keys["항목"]: "검사료", keys["단가"]: "15,180", keys["횟수"]: "1", keys["일수"]: "1", keys["총액"]: "15,180", keys["본인부담"]: "", keys["기타"]: "x"}]
    rows, unknown, missing = band.expand(reply, DETAIL, "세부내역서", PLAN)
    assert (unknown, missing) == (0, 1) and list(rows[0]) == list(DPROPS)  # 스키마 열·순서, 스키마 밖 '기타'는 버린다
    assert (rows[0]["단가"], rows[0]["횟수"], rows[0]["일수"], rows[0]["총액"]) == ("15,180", "1", "1", "15,180")
    assert rows[0]["본인부담"] is None and rows[0]["급여구분"] is None and rows[0]["시작일자"] is None
    assert band.expand(reply, DETAIL, "세부내역서", (PLAN[0], PLAN[1], "0"))[0][0]["급여구분"] == "0"  # 묻지 않은 열은 배치의 채움 값(rowmajor와 같다)


@pytest.fixture
def detail(state, monkeypatch):
    monkeypatch.setenv("BAND_DOC_TYPES", "진료비영수증,세부내역서")
    monkeypatch.setattr(engine, "_table_plan", lambda doc_type, *args: PLAN if doc_type == "세부내역서" else ("영수증 배치", {"본인부담금": "x"}, "0"))
    state.blocks = detail_blocks(30)
    keys = {column: key for key, column in band.short_keys(DETAIL, "세부내역서", PLAN).items()}
    state.row = lambda **cols: {keys[column]: value for column, value in cols.items()}
    return state


def detail_schema():
    return verify._restrict(doctypes.schema("세부내역서"), {"항목내역", "환자성명"})


def test_a_one_page_detail_statement_is_read_in_row_bands_without_a_locate_call(detail):
    detail.bands = [[detail.row(항목="진찰료", EDI코드="AA154", 총액="17,610")], [detail.row(항목="진찰료", EDI코드="AA154", 총액="17,610")],
                    [detail.row(항목="합계", 총액="30,140"), detail.row(항목="끝수처리 조정금액", 총액="-40"), detail.row(항목="합계", 총액="30,100")]]
    with latency.track() as stats:
        result, _ = engine.extract(detail_schema(), detail.blocks, detail.image, table_extract="band")

    assert kinds(detail) == ["band"] * 3 + ["fields"] and "band_fallback" not in stats  # 위치 찾기·금액산정 블록 읽기 없음
    calls = [call for call in detail.calls if call.kind == "band"]
    assert [call.images for call in calls] == [1, 2, 2]
    bands = engine._bands(detail.blocks, len(DPROPS), 12)
    assert [call.max_tokens for call in calls] == [min(engine.TABLE_REPLY_TOKENS, engine._reply_cap(b["text"], len(DPROPS))) + engine.THINK_TOKENS for b in bands]
    assert all(call.text == band.prompt(DETAIL, engine.BAND_NOTE[i > 0], True, "세부내역서", PLAN) for i, call in enumerate(calls))
    rows = result["항목내역"]  # 되풀이되는 같은 행도 겹침으로 지우지 않는다(띠가 겹치지 않는다), 인쇄된 집계 행은 그대로
    assert [(row["항목"], row["총액"]) for row in rows] == [("진찰료", "17,610"), ("진찰료", "17,610"), ("합계", "30,140"),
                                                         ("끝수처리 조정금액", "-40"), ("합계", "30,100")]
    assert rows[0]["EDI코드"] == "AA154" and rows[0]["본인부담"] is None and rows[0]["급여구분"] is None


def test_a_detail_statement_whose_ocr_lines_cannot_cut_it_is_read_as_rowmajor(detail):
    detail.blocks = detail_blocks(30, lines=False)
    with latency.track() as stats:
        engine.extract(detail_schema(), detail.blocks, detail.image, table_extract="band")
    assert "rows" in kinds(detail) and not {"locate", "band"} & set(kinds(detail)) and stats["band_fallback"] == "rows"


def test_a_detail_statement_is_never_prelocated(detail, monkeypatch):
    monkeypatch.setenv("BAND_PRELOCATE", "true")
    assert engine.prelocate(detail_schema(), detail.image, "band") is None and detail.calls == []


def test_receipt_band_strips_ignore_the_rowmajor_plan(detail):
    detail.blocks = [{"page": 1, "type": "table", "text": "", "rows": [["항목", "요양급여(①+②)", "비급여"]]}]
    detail.locate, detail.bands = GRID, [[], [], []]
    engine.extract(receipt_schema(), detail.blocks, detail.image, table_extract="band")
    texts = [call.text for call in detail.calls if call.kind == "band"]
    assert kinds(detail).count("locate") == 1 and len(texts) == 3
    assert all(text == band.prompt(ITEM, engine.BAND_NOTE[i > 0], True) for i, text in enumerate(texts))
    assert {call.max_tokens for call in detail.calls if call.kind == "band"} == {engine.KEYED_CAP}


def test_detail_row_band_prompt_says_every_row_is_whole_and_the_receipt_prompt_still_skips_cut_rows():
    text = band.prompt(DETAIL, engine.BAND_NOTE[1], True, "세부내역서", PLAN)
    assert "Skip rows" not in text and "cut off" not in text
    assert "Every row in the strip is whole" in text and "touching the top or bottom edge" in text
    assert "Skip rows whose name is cut off at the top or bottom edge." in band.prompt(ITEM, engine.BAND_NOTE[1])  # 영수증(겹친 띠)은 그대로


@pytest.mark.parametrize("rows", [5, 30, 61, 100])
def test_detail_row_bands_have_margin_around_every_row_without_taking_in_a_neighbour(rows):
    blocks = detail_blocks(rows, wrapped={3})
    last = max(line["bbox"][3] for line in blocks[0]["lines"])
    first = blocks[0]["lines"][0]["bbox"][1]
    blocks[0]["bbox"] = [50, first, 950, last]  # 표 블록 상자가 머리글 줄 위·마지막 줄 아래에 딱 붙었다
    bands = engine._bands(blocks, len(DPROPS), 12)
    pad = 0.4 * STEP(rows) / 4  # 행 높이의 1/4
    assert bands[0]["clips"][0][1] * 1000 == pytest.approx(first - pad) and bands[-1]["clips"][-1][3] * 1000 == pytest.approx(last + pad)
    for strip in bands:
        top, bottom = body(strip)
        inside = [line["bbox"] for line in blocks[0]["lines"] if top <= (line["bbox"][1] + line["bbox"][3]) / 2 <= bottom]
        assert all(box[1] - top >= pad - 1e-9 and bottom - box[3] >= pad - 1e-9 for box in inside)  # 경계 행도 여백째 담는다
        assert not any(box[3] > top and box[1] < bottom for box in (line["bbox"] for line in blocks[0]["lines"]) if box not in inside)  # 이웃 행은 안 든다
    fallback = engine._bands(blocks, len(DPROPS))  # rowmajor 폴백 띠(per 없음)는 그대로: 표 블록 상자에서 자른다
    assert (fallback == []) is (rows <= 20) and (not fallback or fallback[0]["clips"][0][1] * 1000 == pytest.approx(first))


# --- BAND_STRIP_EDGE: 세부내역서 OCR 행 띠 크롭을 원본 해상도까지 ---------------------------------------


def strip_size(path, edge=None, clip=(0.05, 0.2, 0.95, 0.4)):
    import base64
    import io
    from PIL import Image
    url = engine._page_images(str(path), [1], {}, [list(clip)], edge)[0]
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).size


@pytest.fixture
def scans(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setenv("AI_VISION", "true")
    files = {}
    for name, size, dpi in (("200dpi.tif", (2352, 1655), 200), ("96dpi.jpg", (1728, 2333), 96), ("72dpi.jpg", (3000, 2000), 72), ("nodpi.jpg", (2221, 3000), None)):
        files[name] = tmp_path / name
        Image.new("RGB", size, "white").save(files[name], **({"dpi": (dpi, dpi)} if dpi else {}))
    return files


@pytest.mark.parametrize("name, unset, wide", [("200dpi.tif", 2000, 2117), ("96dpi.jpg", 2000, 2000), ("72dpi.jpg", 2000, 2700), ("nodpi.jpg", 2000, 2000)])
def test_band_strip_edge_draws_row_strips_at_the_file_resolution_within_the_edge(scans, name, unset, wide):
    assert abs(strip_size(scans[name])[0] - unset) <= 1  # 끔: 기존 그대로(긴 변 VISION_MAX_EDGE)
    width = strip_size(scans[name], 3000)[0]
    assert abs(width - wide) <= 1  # 원본 픽셀까지, 기존보다 작게는 그리지 않는다(96dpi는 기존 배율이 이미 원본보다 크다)
    assert strip_size(scans[name], 2400)[0] <= max(2400, unset) + 1  # 상한


def test_band_strip_edge_is_passed_only_to_detail_row_bands(state, monkeypatch):
    seen = []
    images = engine._page_images
    monkeypatch.setattr(engine, "_page_images", lambda *args: seen.append(args[4] if len(args) > 4 else None) or images(*args))
    monkeypatch.setenv("BAND_STRIP_EDGE", "3000")
    monkeypatch.setenv("BAND_DOC_TYPES", "진료비영수증,세부내역서")
    engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")  # 영수증: 위치 찾기 띠는 그대로
    assert set(seen) == {None}
    seen.clear()
    state.bands = [[], [], []]
    engine.extract(verify._restrict(doctypes.schema("세부내역서"), {"항목내역"}), detail_blocks(30), state.image, table_extract="band")
    assert seen.count(3000) == 3 and None in seen  # 띠 셋만, 쪽 이미지는 그대로


# --- BAND_DUMP_DIR: 띠 읽기 진단 저장 ------------------------------------------------------------------


def test_band_dump_saves_each_strip_image_prompt_and_reply_under_the_request(state, monkeypatch, tmp_path):
    import hashlib
    import json
    from backend.config import bind_request
    dump = tmp_path / "dump"
    monkeypatch.setenv("BAND_DUMP_DIR", str(dump))
    engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")  # 요청 밖: 원본 파일 해시 폴더
    folder = dump / hashlib.sha1(open(state.image, "rb").read()).hexdigest()[:12]
    assert sorted(path.name for path in folder.iterdir()) == ["0.prompt.txt", "0.reply.json", "0_0.jpg", "1.prompt.txt", "1.reply.json",
                                                             "1_0.jpg", "1_1.jpg", "2.prompt.txt", "2.reply.json", "2_0.jpg", "2_1.jpg"]
    assert (folder / "0_0.jpg").read_bytes()[:2] == b"\xff\xd8" and "Short keys" in (folder / "0.prompt.txt").read_text(encoding="utf-8")
    assert json.loads((folder / "0.reply.json").read_text(encoding="utf-8"))["rows"][0]["n"] == "진찰료"
    state.bands = [[], [], []]
    with bind_request("job-1/doc:2"):
        engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")
    assert (dump / "job-1_doc_2" / "2.reply.json").exists()


def test_band_dump_off_writes_nothing(state, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(engine, "_band_dump", lambda *args: pytest.fail("BAND_DUMP_DIR 없이 저장했다"))
    engine.extract(receipt_schema(), state.blocks, state.image, table_extract="band")
    assert [path for path in tmp_path.iterdir() if path.name != "page.png"] == []


# --- 세부내역서 OCR 행 띠: 표 블록을 합치고 항목 표만, 남은 기울기 보정 ------------------------------------


def piece(text, x0, x1, y, slope=0.0, height=8):
    """OCR 줄 하나(쪽 1000×1000): 가운데 x에서 ``slope``만큼 기운 줄."""
    shift = slope * (x0 + x1) / 2
    return {"text": text, "bbox": [x0, y + shift, x1, y + shift + height]}


def statement(rows=30, slope=0.0, split=None):
    """환자정보 표·항목 표(머리글, 행마다 가로로 넷으로 갈린 OCR 줄: 이름 둘·금액 둘, 합계 행)·서명 줄. ``slope``만큼 기울었고(행 양 끝 줄의
    높이 차가 줄 높이보다 크다), ``split`` 번째 행 한가운데에서 레이아웃이 항목 표를 두 블록으로 나눴다(앞 두 줄은 위 블록, 뒤 두 줄은 아래 블록)."""
    def four(texts, y):
        return [piece(text, x0, x1, y, slope) for text, (x0, x1) in zip(texts, ((60, 200), (300, 500), (620, 780), (800, 940)))]
    info = four(["환자등록번호", "환자성명", "진료기간", "진료과"], 100) + four(["0000068743", "서기원", "2019-07-22 00:00", "내과"], 125)
    head = four(["항목 일자", "코드 명칭", "금액 횟수", "일수 총액"], 190)
    body = [four(["진찰료", f"AA{154 + i} 초진진찰료", f"{10000 + i:,} 1", f"1 {10000 + i:,}"] if i < rows else ["합계", "", "", "30,000"],
                 220 + i * 20) for i in range(rows + 1)]
    body[-1] = [line for line in body[-1] if line["text"]]
    sign = [piece("신청인 조동주 의 요청에 따라 발급합니다. 2020 년 01 월 02 일", 60, 940, 240 + (rows + 1) * 20, slope)]
    cut = split if split is not None else len(body)
    top = [line for row in body[:cut] for line in row] + (body[cut][:2] if split is not None else [])
    bottom = (body[cut][2:] if split is not None else []) + [line for row in body[cut + 1:] for line in row]
    block = lambda lines: {"page": 1, "type": "table", "text": "\n".join(l["text"] for l in lines), "page_size": [1000, 1000], "lines": lines,
                           "bbox": [50, min(l["bbox"][1] for l in lines) - 2, 950, max(l["bbox"][3] for l in lines) + 2]}
    blocks = [block(info), block(head + top)] + ([block(bottom)] if bottom else []) + [block(sign)]
    return blocks, info, head, body, sign


def in_band(line, band):
    top, bottom = body(band)
    return top <= (line["bbox"][1] + line["bbox"][3]) / 2 <= bottom


@pytest.mark.parametrize("slope, split", [(0.0, None), (0.0, 14), (0.012, None), (0.012, 14), (-0.012, 7)])
def test_detail_row_bands_cut_the_item_table_alone_between_rows_across_blocks_and_tilt(slope, split):
    blocks, info, head, rows, sign = statement(30, slope, split)
    bands = engine._bands(blocks, len(DPROPS), 12)
    assert len(bands) == 3
    edges = [edge for b in bands for edge in body(b)] + [b["clips"][0][3] * 1000 for b in bands[1:]]
    everything = info + head + [line for row in rows for line in row] + sign
    assert not any(line["bbox"][1] < edge < line["bbox"][3] for line in everything for edge in edges)  # 어느 줄도 띠 경계에 걸치지 않는다
    for row in rows:  # 행의 줄들(블록이 갈라도·기울어도)은 같은 띠 하나에
        assert all(sum(in_band(line, b) for b in bands) == 1 for line in row) and len({i for i, b in enumerate(bands) for line in row if in_band(line, b)}) == 1
    assert not any(in_band(line, b) for line in info + sign for b in bands)  # 환자정보 표·서명 줄은 띠에 들지 않는다
    assert not any(line["bbox"][1] < b["clips"][0][3] * 1000 and line["bbox"][3] > b["clips"][0][1] * 1000 for line in info for b in bands[1:])
    assert all(any(b["clips"][0][1] * 1000 <= line["bbox"][1] and line["bbox"][3] <= b["clips"][0][3] * 1000 for line in head) for b in bands[1:])


def test_detail_row_bands_need_a_header_line_else_rowmajor():
    blocks, info, head, rows, sign = statement(30)
    blocks[1]["lines"] = blocks[1]["lines"][4:]  # 머리글 줄을 못 읽었다
    assert engine._bands(blocks, len(DPROPS), 12) == []


def test_rowmajor_fallback_bands_still_cut_each_block_alone():
    blocks = statement(60, split=30)[0]
    bands = engine._bands(blocks, len(DPROPS))  # per 없음: 블록마다 따로(블록 상자 안에서) 자른다
    assert len(bands) > len(blocks)
    assert all(any(block["bbox"][1] <= b["clips"][-1][1] * 1000 and b["clips"][-1][3] * 1000 <= block["bbox"][3] for block in blocks) for b in bands)


def test_without_the_tilt_correction_a_tilted_row_would_split(monkeypatch):
    """기울기 보정이 하는 일: 보정을 빼면 기운 행의 양 끝 줄이 다른 행으로 갈려 띠 경계가 행을 가른다(위 테스트의 기울기 경우가 보정 덕이다)."""
    monkeypatch.setattr(engine.print_register, "_deskew", lambda boxes: (boxes, 0))
    blocks, info, head, rows, sign = statement(30, 0.012)
    bands = engine._bands(blocks, len(DPROPS), 12)
    assert any(len({i for i, b in enumerate(bands) for line in row if in_band(line, b)}) != 1 for row in rows) or len(bands) != 3
