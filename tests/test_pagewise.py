"""여러 쪽 표를 쪽 묶음별로 읽기(engine._table_pages·_page_plans·extract): 묶음 크기, 머리글 없는 이어진 쪽의 열 배치,
쪽 순서 이어 붙이기, 쪽 경계의 소계·무리 값 채우기, 한 쪽 실패, 시한·취소, 한 쪽 문서 그대로. LLM 호출은 가짜다."""

import re
import threading
import time
from types import SimpleNamespace

import fitz
import pytest

from backend import doctypes, engine, latency, rules, verify

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
    """첫 쪽 머리글로 정한 열 순서."""
    return list(engine._page_plans("세부내역서", "항목내역", table_schema()["properties"]["항목내역"], blocks)[1][1])


def row(columns, **values):
    return [values.get(column) for column in columns]


# --- 묶음 크기 ----------------------------------------------------------------------


def amounts(number, count):
    return {"page": number, "type": "text", "text": " ".join(["1,000"] * count)}


def grouped(blocks, budget=10 ** 6, plans=None):
    return [engine._pages(group) for group in engine._table_pages(blocks, budget, 1, plans or {})]


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


def test_a_page_over_the_limits_is_its_own_group_and_a_new_plan_starts_a_group(monkeypatch):
    monkeypatch.setattr(engine, "TABLE_REPLY_TOKENS", (40 + 20) * 30)
    blocks = [amounts(1, 1), amounts(2, 100), amounts(3, 1), amounts(4, 1)]
    assert grouped(blocks) == [[1], [2], [3, 4]]
    assert grouped([amounts(n, 1) for n in range(1, 5)], plans={1: "a", 2: "a", 3: "b", 4: "b"}) == [[1, 2], [3, 4]]


# --- 머리글 없는 이어진 쪽 ------------------------------------------------------------


def test_headerless_continuation_pages_reuse_the_nearest_earlier_header():
    spec = table_schema()["properties"]["항목내역"]
    other = (("항목", 0), ("명칭", 100), ("투여량", 200), ("일수", 300), ("총액", 400))
    plans = engine._page_plans("세부내역서", "항목내역", spec, [page(1, None), page(2), page(3, None), page(4, other), page(5, None)])

    assert plans[2] is not None and plans[1] == plans[2] == plans[3]  # 첫 머리글 앞쪽도 그 머리글을 쓴다
    assert plans[4] == plans[5] != plans[2] and "투여량" in plans[4][1]
    assert engine._page_plans("세부내역서", "항목내역", spec, [page(1, None), page(2, None)]) == {1: None, 2: None}


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

    assert [r["항목"] for r in fields["항목내역"]] == ["주사료"] * 3 + ["검사료"] * 2  # 쪽을 넘어 이어 채운다
    assert fields["급여_본인부담총액"] == "480"  # 쪽 소계가 아니라 마지막 합계 행
    assert sum(int(r["본인부담"]) for r in fields["항목내역"]) == 480  # 소계·합계 행은 표에서 빠져 두 번 세지 않는다


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

    with latency.track() as stats:
        result, _ = engine.extract(table_schema(), blocks, provider.source, table_extract="rowmajor")

    assert [r["항목"] for r in result["항목내역"]] == ["P1", "P3"] and stats["table_pages_failed"] == 1
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
