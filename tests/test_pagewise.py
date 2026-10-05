"""여러 쪽 표를 쪽 묶음별로 읽기(engine._table_pages·_page_plans·extract): 묶음 크기, 머리글 없는 이어진 쪽의 열 배치,
쪽 순서 이어 붙이기, 쪽 경계의 소계·무리 값 채우기, 한 쪽 실패, 시한·취소, 한 쪽 문서 그대로. LLM 호출은 가짜다."""

import re
import threading
import time
from types import SimpleNamespace

import fitz
import pytest

from backend import doctypes, engine, latency, rules, table_layout, verify

HEADER = (("항목", 0), ("명칭", 100), ("단가", 200), ("일수", 300), ("총액", 400), ("본인부담", 500))


def page(number, header=HEADER, text=""):
    """한 쪽 표 블록. ``header``가 있으면 머리글 줄을 싣는다(이어진 쪽은 머리글이 없다)."""
    return {"page": number, "type": "table", "text": f"PAGE{number} {text}".strip(), "rows": [],
            "lines": [{"text": word, "bbox": [x, 0, x + 40, 20]} for word, x in header or ()]}


def table_schema(*keys):
    return verify._restrict(doctypes.schema("세부내역서"), set(keys) or {"항목내역"})


@pytest.fixture
def provider(monkeypatch, tmp_path):
    """provider 모드, 4쪽 PDF, 쪽마다 한 묶음. ``state.rows[n]``·``state.objects[n]``은 n쪽 응답(예외면 던진다).
    뒤쪽 응답이 먼저 끝나게 늦춰 이어 붙이는 순서가 끝난 순서가 아님을 본다."""
    for name, value in (("AI_MODE", "provider"), ("AI_BASE_URL", "https://provider.invalid/v1"), ("AI_API_KEY", "key"),
                        ("AI_MODEL", "test/model"), ("AI_VISION", "true")):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", 0)
    document = fitz.open()
    for _ in range(4):
        document.new_page(width=200, height=200)
    document.save(tmp_path / "doc.pdf")
    state = SimpleNamespace(rows={}, objects={}, calls=[], source=str(tmp_path / "doc.pdf"), lock=threading.Lock())

    def fake(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        content = messages[1]["content"]
        text = content[-1]["text"] if isinstance(content, list) else content
        pages = [int(n) for n in re.findall(r"PAGE(\d)", text)]
        with state.lock:
            state.calls.append({"messages": messages, "json_schema": json_schema, "text": text, "pages": pages,
                                "images": sum(isinstance(content, list) and part["type"] == "image_url" for part in content)})
        time.sleep(0.02 * (5 - (pages or [5])[0]))
        reply = (state.rows if json_schema is not None else state.objects).get(pages[0] if len(pages) == 1 else None, {})
        if isinstance(reply, Exception):
            raise reply
        return {"rows": reply} if json_schema is not None else reply
    monkeypatch.setattr(engine, "_provider", fake)
    return state


def names(blocks):
    """문서 머리글로 정한 열 순서."""
    return list(engine._table_plan("세부내역서", "항목내역", table_schema()["properties"]["항목내역"], blocks)[1])


def row(columns, **values):
    return [values.get(column) for column in columns]


# --- 묶음 크기 ----------------------------------------------------------------------


def amounts(number, count):
    return {"page": number, "type": "text", "text": " ".join(["1,000"] * count)}


def grouped(blocks, budget=10 ** 6):
    return [engine._pages(group) for group in engine._table_pages(blocks, budget, 1)]


def test_pages_are_grouped_while_the_reply_cap_stays_under_the_limit(monkeypatch):
    blocks = [amounts(number, 2) for number in range(1, 7)]
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", (4 + 20) * 30)  # 두 쪽(금액 4개)까지
    assert grouped(blocks) == [[1, 2], [3, 4], [5, 6]]
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", (4 + 20) * 30 - 1)
    assert grouped(blocks) == [[n] for n in range(1, 7)]


def test_a_group_holds_at_most_the_image_limit_and_fits_the_chunk_budget(monkeypatch):
    blocks = [amounts(number, 1) for number in range(1, 7)]
    assert grouped(blocks) == [[1, 2, 3, 4], [5, 6]]
    assert grouped(blocks, budget=len(blocks[0]["text"]) * 2 + 1) == [[1, 2], [3, 4], [5, 6]]


def test_a_page_over_the_limits_is_its_own_group(monkeypatch):
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", (40 + 20) * 30)
    blocks = [amounts(1, 1), amounts(2, 100), amounts(3, 1), amounts(4, 1)]
    assert grouped(blocks) == [[1], [2], [3, 4]]


# --- 머리글 없는 이어진 쪽 ------------------------------------------------------------


def test_one_plan_for_the_document_from_the_header_most_pages_agree_on():
    spec = table_schema()["properties"]["항목내역"]
    misread = tuple(word for word in HEADER if word[0] != "본인부담")  # OCR이 한 낱말을 놓친 쪽
    plan = engine._table_plan("세부내역서", "항목내역", spec, [page(1, None), page(2), page(3, None), page(4, misread), page(5)])
    alone = table_layout.plan("세부내역서", "항목내역", [page(2)], spec["description"],
                              {key: prop.get("description", "") for key, prop in spec["items"]["properties"].items()})

    assert plan == alone and "본인부담" in plan[1]  # 머리글 없는 쪽(1·3)과 오독한 쪽(4)도 이 배치로 읽는다
    assert engine._table_plan("세부내역서", "항목내역", spec, [page(1, None), page(2, None)]) is None


# --- 이어 붙이기 ---------------------------------------------------------------------


def test_pages_are_read_in_parallel_with_one_plan_and_concatenated_in_page_order(provider):
    blocks = [page(1), page(2, None), page(3, None)]
    columns = names(blocks)
    provider.rows = {n: [row(columns, 항목=f"P{n}-{i}", 총액="100") for i in (1, 2)] for n in (1, 2, 3)}

    result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor")

    assert [r["항목"] for r in result["항목내역"]] == ["P1-1", "P1-2", "P2-1", "P2-2", "P3-1", "P3-2"]
    assert sorted(call["pages"] for call in provider.calls) == [[1], [2], [3]]
    assert all(call["json_schema"] and call["images"] == 1 for call in provider.calls)
    order = {re.search(r"Position order: .*", call["text"])[0] for call in provider.calls}
    assert order == {"Position order: " + ", ".join(f"{i}={c}" for i, c in enumerate(columns, 1)) + "."}
    continuation = next(call for call in provider.calls if call["pages"] == [2])["text"]
    assert "These are page(s) 2 of a table printed over page(s) 1-3" in continuation and "no header row" in continuation


def test_asis_reads_the_table_page_by_page_beside_one_call_for_the_other_fields(provider):
    provider.objects = {n: {"항목내역": [{"항목": f"P{n}"}]} for n in (1, 2)}
    provider.objects[None] = {"환자성명": "홍길동"}

    result, _ = engine.extract(table_schema("환자성명", "항목내역"), [page(1), page(2, None)], provider.source)

    assert result["환자성명"] == "홍길동" and [r["항목"] for r in result["항목내역"]] == ["P1", "P2"]
    other = [call for call in provider.calls if len(call["pages"]) != 1]
    assert len(provider.calls) == 3 and len(other) == 1 and '"항목내역"' not in other[0]["text"]


def test_subtotals_and_fill_down_see_the_concatenated_table(provider):
    blocks = [page(1), page(2, None)]
    columns = names(blocks)
    provider.rows = {
        1: [row(columns, 항목="주사료", 총액="100", 본인부담="100"), row(columns, 총액="200", 본인부담="200"),
            row(columns, 항목="소계", 본인부담="300")],
        2: [row(columns, 총액="50", 본인부담="50"), row(columns, 항목="검사료", 총액="60", 본인부담="60"),
            row(columns, 총액="70", 본인부담="70"), row(columns, 항목="합계", 본인부담="480")],
    }
    schema = table_schema("항목내역", "급여_본인부담총액")
    provider.objects[None] = {"급여_본인부담총액": None}

    result, _ = engine.extract(schema, blocks, provider.source, table_extract="rowmajor")
    fields = rules.apply("세부내역서", result, [])

    labels = [r["항목"] for r in fields["항목내역"]]
    assert labels == ["주사료"] * 2 + ["소계", "주사료"] + ["검사료"] * 2 + ["합계"]  # 쪽을 넘어 이어 채우고, 인쇄된 집계 행은 제자리에 남는다
    assert fields["급여_본인부담총액"] == "480"  # 쪽 소계가 아니라 마지막 합계 행
    assert sum(int(r["본인부담"]) for r in fields["항목내역"] if not rules.is_total(r)) == 480  # 집계 행은 더하지 않는다


# --- 한 쪽 실패 -----------------------------------------------------------------------


def test_a_failed_page_is_reread_asis_alone(provider):
    blocks = [page(1), page(2, None), page(3, None)]
    columns = names(blocks)
    provider.rows = {1: [row(columns, 항목="P1")], 2: [["너무 짧은 행"]], 3: [row(columns, 항목="P3")]}
    provider.objects = {2: {"항목내역": [{"항목": "P2"}]}}

    result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor")

    assert [r["항목"] for r in result["항목내역"]] == ["P1", "P2", "P3"]
    asis = [call for call in provider.calls if not call["json_schema"]]
    assert [call["pages"] for call in asis] == [[2]] and "part 2 of 3" in asis[0]["messages"][0]["content"]


def test_a_page_lost_both_ways_keeps_the_other_pages_and_is_counted(provider):
    blocks = [page(1), page(2, None), page(3, None)]
    columns = names(blocks)
    provider.rows = {1: [row(columns, 항목="P1")], 2: RuntimeError("잘림"), 3: [row(columns, 항목="P3")]}
    provider.objects = {2: RuntimeError("잘림")}

    completeness = {}
    with latency.track() as stats:
        result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor", completeness=completeness)

    assert [r["항목"] for r in result["항목내역"]] == ["P1", "P3"] and stats["table_pages_failed"] == 1
    assert completeness == {"partial": True, "pages": [1, 2, 3], "successful_pages": [1, 3], "failed_pages": [2],
                            "tables": {"항목내역": {"successful_pages": [1, 3], "failed_pages": [2]}}}
    assert stats["extraction_completeness"] == completeness
    provider.rows = {n: RuntimeError("잘림") for n in (1, 2, 3)}
    provider.objects = {n: RuntimeError("잘림") for n in (1, 2, 3)}
    with pytest.raises(RuntimeError):
        engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor")


# --- 시한·취소 ------------------------------------------------------------------------


@pytest.mark.parametrize("arm", ["rowmajor", "asis"])
def test_deadline_and_cancel_stop_the_read_instead_of_losing_pages(provider, arm):
    blocks = [page(1), page(2, None)]
    with pytest.raises(TimeoutError):
        engine.extract(table_schema(), blocks, provider.source, deadline=time.monotonic() - 1, table_extract=arm)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(RuntimeError, match="cancelled"):
        engine.extract(table_schema(), blocks, provider.source, cancel=cancel, table_extract=arm)
    assert provider.calls == []


def test_every_page_call_is_counted_and_capped_by_the_deadline(provider, monkeypatch):
    blocks = [page(1), page(2, None), page(3, None)]
    provider.rows = {n: [row(names(blocks), 항목=f"P{n}")] for n in (1, 2, 3)}
    calls, caps = [], []
    original = engine._provider

    def capped(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        caps.append(timeout_cap)
        return original(messages, timeout, timeout_cap, json_schema, max_tokens)
    monkeypatch.setattr(engine, "_provider", capped)

    engine.extract(table_schema(), blocks, provider.source, deadline=time.monotonic() + 60, on_call=lambda: calls.append(1),
                   table_extract="rowmajor")

    assert len(calls) == 3 and all(0 < cap <= 60 for cap in caps)


# --- 한 쪽 문서 -----------------------------------------------------------------------


def test_a_table_that_fits_one_reply_is_read_in_one_call_as_before(provider, monkeypatch):
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", 10 ** 6)
    for blocks in ([page(1)], [page(1), page(2, None)]):
        provider.calls.clear()
        provider.rows = dict.fromkeys((None, 1), [row(names(blocks), 항목="진찰료")])

        result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor")

        assert len(provider.calls) == 1 and "These are page(s)" not in provider.calls[0]["text"]
        assert provider.calls[0]["images"] == len(blocks) and result["항목내역"][0]["항목"] == "진찰료"


@pytest.mark.parametrize("arm", ["asis", "rowmajor"])
def test_completeness_tracks_all_pages_in_a_failed_group(provider, monkeypatch, arm):
    blocks = [page(n) for n in (1, 2, 3, 4)]
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", 10 ** 6)
    monkeypatch.setattr(engine, "VISION_MAX_IMAGES", 2)
    provider.rows = {None: RuntimeError("lost two pages")}
    provider.objects = {None: RuntimeError("lost two pages")}
    original = engine._provider
    def fail_first_group(messages, **kwargs):
        content = messages[1]["content"]
        text = content[-1]["text"] if isinstance(content, list) else content
        if "PAGE3" in text:
            return {"rows": [row(names(blocks), 항목="P3")]} if kwargs.get("json_schema") else {"항목내역": [{"항목": "P3"}]}
        return original(messages, **kwargs)
    monkeypatch.setattr(engine, "_provider", fail_first_group)
    completeness = {}
    result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract=arm, completeness=completeness)
    assert result["항목내역"][0]["항목"] == "P3"
    assert completeness["failed_pages"] == [1, 2] and completeness["successful_pages"] == [3, 4]
    assert completeness["partial"] is True


@pytest.mark.parametrize("reply", [{}, {"항목내역": None}, {"항목내역": "broken"}, {"항목내역": ["broken"]}])
def test_invalid_page_table_contract_is_partial_instead_of_an_empty_success(provider, reply):
    provider.objects = {1: {"항목내역": [{"항목": "P1"}]}, 2: reply}
    completeness = {}
    result, _ = engine.extract(table_schema(), [page(1), page(2)], provider.source, completeness=completeness)
    assert result["항목내역"][0]["항목"] == "P1"
    assert completeness["partial"] and completeness["failed_pages"] == [2]


def test_valid_empty_page_table_is_complete(provider):
    provider.objects = {1: {"항목내역": [{"항목": "P1"}]}, 2: {"항목내역": []}}
    completeness = {}
    engine.extract(table_schema(), [page(1), page(2)], provider.source, completeness=completeness)
    assert completeness["partial"] is False and completeness["successful_pages"] == [1, 2]


# --- 빽빽한 쪽의 행 띠 -----------------------------------------------------------------
# 머리글 줄(y 0~10) 아래에 R1..Rn 행(y 20i~20i+10, 금액 하나). 열 1개면 행당 상한 30토큰이고, 상한 720이면 띠당 금액 4개다.


def dense(rows=30, wrapped=(), tall=None, number=1, orientation=None):
    lines = [{"text": "항목", "bbox": [0, 0, 40, 10]}, {"text": "금액", "bbox": [50, 0, 90, 10]}]
    y = 20
    for i in range(1, rows + 1):
        lines += [{"text": f"R{i}", "bbox": [0, y, 40, y + 10]}, {"text": "1,000", "bbox": [50, y, 90, y + 10]}]
        if i in wrapped:  # 이름이 다음 줄로 넘어간 행: 금액이 없는 줄
            y += 20
            lines.append({"text": f"R{i}b", "bbox": [0, y, 40, y + 10]})
        y += 20
    if tall:
        lines.append({"text": "검사료", "bbox": [95, tall[0], 100, tall[1]]})
    block = {"page": number, "type": "table", "bbox": [0, 0, 100, y], "page_size": [100, 1000], "lines": lines,
             "text": " ".join(line["text"] for line in lines)}
    return {**block, "orientation": orientation} if orientation else block


def band_rows(band):
    return re.findall(r"R\d+b?", band["text"])


@pytest.fixture
def narrow(monkeypatch):
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", 30 * 24)


def test_a_page_under_the_provider_limit_is_not_cut(monkeypatch):
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", 30 * 24)
    assert [len(group) for group in engine._table_pages([dense(rows=28)], 10 ** 6, 1)] == [1]  # (28+20)×30 = 2×720
    assert "clips" not in engine._table_pages([dense(rows=28)], 10 ** 6, 1)[0][0]
    assert all("clips" in group[0] for group in engine._table_pages([dense(rows=29)], 10 ** 6, 1))


def test_bands_cut_in_line_gaps_into_even_bands_that_repeat_one_row(narrow):
    bands = engine._bands([dense()], 1)
    rows = [band_rows(band) for band in bands]
    assert [len(r) for r in rows] == [4, 5, 5, 5, 5, 5, 5, 3]  # 30행을 새 행 4개씩 띠 8개로, 뒤 띠는 앞 띠의 마지막 행을 다시 읽는다
    assert all(a[-1] == b[0] for a, b in zip(rows, rows[1:]))
    assert sorted({r for band in rows for r in band}, key=lambda r: int(r[1:])) == [f"R{i}" for i in range(1, 31)]
    assert all(band["text"].startswith("항목 | 금액") for band in bands)  # 모든 띠가 머리글 줄을 근거로 받는다
    edges = [y * 1000 for band in bands for clip in band["clips"] for y in (clip[1], clip[3])]
    assert all(y in (0, 620) or y % 20 == 15 for y in edges)  # 줄 사이 틈(행 i의 아래 20i+10과 다음 행 위의 가운데)
    assert bands[0]["clips"] == [[0, 0, 1, 0.095]]  # 첫 띠는 머리글부터
    assert all(band["clips"][0] == [0, 0, 1, 0.015] and len(band["clips"]) == 2 for band in bands[1:])  # 뒤 띠는 머리글 띠 + 행 띠


def test_a_cut_never_falls_before_a_wrapped_line_and_the_repeat_holds_the_whole_row(narrow):
    bands = engine._bands([dense(wrapped=range(1, 31))], 1)
    rows = [band_rows(band) for band in bands]
    assert all(r[0].endswith(tuple("0123456789")) for r in rows)  # 띠는 금액이 있는 줄에서 시작한다
    assert all(a[-2:] == b[:2] and b[1] == b[0] + "b" for a, b in zip(rows, rows[1:]))  # 넘어간 줄까지 함께 반복


def test_merged_cell_lines_go_to_every_band_they_overlap_and_not_into_the_rows(narrow):
    bands = engine._bands([dense(tall=(100, 300))], 1)  # R5(y 100)~R14(y 280~290)에 걸친 병합 칸
    assert ["검사료" in band["text"] for band in bands] == [
        any(5 <= int(r[1:]) <= 14 for r in band_rows(band)) for band in bands] == [False, True, True, True, False, False, False, False]
    assert all(r.startswith("R") for band in bands for r in band_rows(band))


def test_no_bands_without_line_boxes_or_when_nothing_needs_cutting(narrow):
    assert engine._bands([{**dense(), "lines": []}], 1) == []
    assert engine._bands([dense(rows=3)], 1) == []
    assert engine._bands([{"page": 1, "type": "text", "text": "1,000 " * 100}], 1) == []


def test_bands_of_a_turned_page_are_cut_upright_and_clipped_in_the_original_frame(narrow):
    upright = dense()
    from backend.parsers import unturn
    turned = unturn([upright], 90)[0]  # 90° 돌아간 쪽에서 읽은 블록(좌표는 원본 기준)
    want = [[unturn([{"bbox": [c[0] * 100, c[1] * 1000, c[2] * 100, c[3] * 1000], "page_size": [100, 1000]}], 90)[0]["bbox"]
             for c in band["clips"]] for band in engine._bands([upright], 1)]
    got = engine._bands([turned], 1)
    assert [band_rows(band) for band in got] == [band_rows(band) for band in engine._bands([upright], 1)]
    assert [[[round(v * s, 6) for v, s in zip(c, (1000, 100, 1000, 100))] for c in band["clips"]] for band in got] == \
        [[[round(v, 6) for v in box] for box in boxes] for boxes in want]
    assert all(band["orientation"] == 90 for band in got)


def test_the_stitch_keeps_one_read_of_the_repeated_row():
    spec = {"type": "array", "items": {"type": "object"}}
    full, part = {"항목": "주사료", "총액": "1,000"}, {"총액": "1000"}
    assert engine._merge_chunk_results([[{"항목": "A"}, part], [full, {"항목": "B"}]], spec) == [{"항목": "A"}, full, {"항목": "B"}]
    assert engine._merge_chunk_results([[full], [part]], spec) == [full]
    assert engine._merge_chunk_results([[full], [full]], spec) == [full]
    other = {"항목": "주사료", "총액": "2,000"}  # 다른 값이 있으면 다른 행이다
    assert engine._merge_chunk_results([[full], [other]], spec) == [full, other]
    assert engine._merge_chunk_results([[full], [{"항목": None}]], spec) == [full, {"항목": None}]  # 빈 행은 같은 행이 아니다


def test_a_dense_page_is_read_band_by_band_and_a_failed_band_alone_is_read_asis(provider, monkeypatch):
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", 210 * 24)  # 스키마 19열: 띠당 금액 4개
    def fake(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
        content = messages[1]["content"]
        text = content[-1]["text"]
        names = list(dict.fromkeys(re.findall(r"R\d+", text.split("[[SOURCE_END]]")[0] if json_schema else text)))
        with provider.lock:
            provider.calls.append({"json_schema": json_schema, "names": names, "text": text,
                                   "images": sum(part["type"] == "image_url" for part in content)})
        if json_schema is not None:
            if "R10" in names:
                raise RuntimeError("broken JSON")
            width = json_schema["properties"]["rows"]["items"]["minItems"]
            return {"rows": [[name] + [None] * (width - 1) for name in names]}
        return {"항목내역": [{"항목": name} for name in names]}
    monkeypatch.setattr(engine, "_provider", fake)
    monkeypatch.setattr(engine, "_table_plan", lambda *args: None)
    blocks = [dense()]
    completeness = {}

    result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor", completeness=completeness)

    assert [row["항목"] for row in result["항목내역"]] == [f"R{i}" for i in range(1, 31)]
    asis = [call for call in provider.calls if call["json_schema"] is None]
    assert len(asis) == 1 and asis[0]["names"] == ["R8", "R9", "R10", "R11", "R12"]  # 깨진 띠 하나만 asis로 다시 읽는다
    assert len(provider.calls) == len(engine._bands(blocks, 19)) + 1
    assert all(call["images"] == 2 for call in provider.calls if "R1" not in call["names"])
    assert all("horizontal strip" in call["text"] for call in provider.calls if call["json_schema"])
    assert completeness["partial"] is False
