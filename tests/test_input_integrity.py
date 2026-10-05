"""입력 무결성(AUX.INPUT·P.MIS.AREA.1)과 쪽·표·행 경계 반복·순서 탐지. 값은 바꾸지 않고 issue_codes만 남긴다."""
import fitz
import pytest
from PIL import Image

from backend import engine

TABLE = {"type": "object", "properties": {"행": {"type": "array", "items": {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}}}}


def blocks_of(*texts, kind="text"):
    return [{"type": kind, "page": page, "text": text} for page, text in enumerate(texts, 1)]


def grounded(pages):
    return {"행": {str(i): {"a": {"page": page, "bbox": [0, 0, 1, 1]}} for i, page in enumerate(pages)}}


def flags(rows, pages, blocks=None, schema=TABLE):
    return {(f["code"], tuple(f.get("rows", f.get("pages", [])))) for f in
            engine.unit_flags({"행": rows}, schema, grounded(pages), blocks or blocks_of("가", "나"))}


def row(a, b="1"):
    return {"a": a, "b": b}


@pytest.fixture(autouse=True)
def vision(monkeypatch):
    monkeypatch.setattr(engine, "ai_settings", lambda: {"vision": True, "chunk_chars": 40000, "integrity_review": False})


def test_big_page_reports_downscale_and_normal_page_does_not(tmp_path):
    big, small = tmp_path / "big.png", tmp_path / "small.png"
    Image.new("RGB", (3000, 1000), "white").save(big)
    Image.new("RGB", (600, 400), "white").save(small)
    assert engine.input_report(str(big), blocks_of("x"), TABLE)["pages"][1]["codes"] == ["downscaled"]
    assert engine.input_report(str(small), blocks_of("x"), TABLE)["pages"][1]["codes"] == []


def test_multi_frame_tif_counts_frames_and_unreadable_file_is_flagged(tmp_path):
    path = tmp_path / "scan.tif"
    frames = [Image.new("RGB", (50, 50), "white") for _ in range(3)]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    assert engine.input_report(str(path), blocks_of("a", "b", "c"), TABLE)["page_count"] == 3
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    report = engine.input_report(str(bad), blocks_of("a"), TABLE)
    assert report["decode_failed"] and report["pages"][1]["codes"] == ["decode_failed"]


def test_pages_beyond_the_image_limit_are_reported_not_sent(tmp_path):
    path = tmp_path / "six.pdf"
    with fitz.open() as pdf:
        for _ in range(6):
            pdf.new_page()
        pdf.save(path)
    text = blocks_of(*["가"] * 6)
    report = engine.input_report(str(path), text, {"properties": {"s": {"type": "string"}}})
    assert [n for n, p in report["pages"].items() if "image_not_sent" in p["codes"]] == [5, 6]
    assert engine.input_report(str(path), text, TABLE)["pages"][5]["codes"] == []  # 표 쪽 묶음은 4장 이하라 모두 전송
    assert engine.input_report(None, text, TABLE) == {}


def test_boundary_repeat_only_across_pages():
    assert ("boundary_repeat", (2,)) in flags([row("x"), row("y"), row("y")], [1, 1, 2])
    assert not flags([row("x"), row("y"), row("y")], [1, 2, 2])  # 같은 쪽의 반복은 정상일 수 있다
    assert not flags([row("x"), row("y"), row("z")], [1, 1, 2])
    assert not flags([{}, {}], [1, 2])  # 빈 행


def test_duplicate_run_detects_a_table_read_twice_but_not_blank_or_uniform_rows():
    base = [row("a"), row("b"), row("c")]
    assert ("duplicate_run", (3, 4, 5)) in flags(base + base, [1, 1, 1, 2, 2, 2])
    assert not flags([row("0")] * 6, [1] * 6)
    assert not flags(base + [row("d")], [1, 1, 2, 2])


def test_page_order_and_duplicate_page_and_gap():
    assert ("row_page_order", (2,)) in flags([row("a"), row("b"), row("c")], [1, 3, 2])
    assert not flags([row("a"), row("b")], [1, 2])
    same = blocks_of("진료비 영수증 같은 내용이 한 쪽 전체에 반복해서 인쇄된 경우", "진료비 영수증 같은 내용이 한 쪽 전체에 반복해서 인쇄된 경우")
    assert ("duplicate_page", (1, 2)) in flags([], [], same)
    assert not flags([], [], blocks_of("서로", "다른"))
    assert ("page_order", (1, 2)) in flags([], [], [*blocks_of("a", "b")[1:], *blocks_of("a")])
    tables = blocks_of("t", "t", "t", kind="table")
    assert ("table_page_gap", (2,)) in flags([row("a"), row("b")], [1, 3], tables)
    assert not flags([row("a"), row("b"), row("c")], [1, 2, 3], tables)


def test_apply_integrity_marks_pages_and_rows_without_changing_values(tmp_path, monkeypatch):
    path = tmp_path / "big.png"
    Image.new("RGB", (3000, 1000), "white").save(path)
    rows = [row("x"), row("y"), row("y")]
    quality = {"행/2/a": {"status": "PASS", "issue_codes": [], "stage": None, "action": "ACCEPT", "provenance": {"page": 2}},
               "행/0/a": {"status": "PASS", "issue_codes": [], "stage": None, "action": "ACCEPT", "provenance": {"page": 1}}}
    summary = engine.apply_integrity(quality, {"행": rows}, TABLE, grounded([1, 1, 2]), blocks_of("가", "나"), str(path))
    assert quality["행/2/a"]["issue_codes"] == ["boundary_repeat"] and quality["행/2/a"]["status"] == "PASS"
    assert quality["행/0/a"]["issue_codes"] == ["downscaled"]
    assert summary["input"]["node"] == "AUX.INPUT" and rows == [row("x"), row("y"), row("y")]
    monkeypatch.setattr(engine, "ai_settings", lambda: {"vision": True, "chunk_chars": 40000, "integrity_review": True})
    engine.apply_integrity(quality, {"행": rows}, TABLE, grounded([1, 1, 2]), blocks_of("가", "나"), str(path))
    assert quality["행/2/a"]["status"] == "SUSPICIOUS" and quality["행/2/a"]["action"] == "RECHECK"


def scan(path, layouts):
    """A PDF whose page i draws ruled boxes `layouts[i]` (list of (x0, y0, x1, y1)) — a stand-in for the page image."""
    with fitz.open() as pdf:
        for boxes in layouts:
            page = pdf.new_page(width=400, height=560)
            for box in boxes:
                page.draw_rect(fitz.Rect(*box), color=(0, 0, 0), fill=(0.2, 0.2, 0.2), width=1)
        pdf.save(path)
    return str(path)


RECEIPT = [(20, 20, 380, 60), (20, 80, 200, 300), (220, 80, 380, 160), (220, 180, 380, 300), (20, 320, 380, 520)]
DETAIL = [(x, 20, x + 6, 540) for x in range(20, 380, 30)]  # 열마다 세로줄이 그어진 표
NUMBERS = ("2019-02-17 2019-02-28 40,000 32,000 8,000 1234567 4111436549 15,020 21,320 6,300 "
           "11,800 3,540 2,210 760 13 18 45 1,500 92,170 2024-01-02")


def page_blocks(*texts):
    return [{"type": "table", "page": page, "text": f"<table><tr><td>{text}</td></tr></table>"} for page, text in enumerate(texts, 1)]


def page_flags(blocks, source=None):
    return {(f["code"], tuple(f["pages"])) for f in engine.unit_flags({}, TABLE, {}, blocks, source) if "pages" in f}


def test_rescanned_page_with_slightly_different_ocr_is_a_duplicate(tmp_path):
    shifted = [(x0 + 3, y0 + 4, x1 + 3, y1 + 4) for x0, y0, x1, y1 in RECEIPT]  # 다시 스캔해 조금 밀린 같은 쪽
    path = scan(tmp_path / "rescan.pdf", [RECEIPT, shifted])
    misread = NUMBERS.replace("15,020", "15,O20") + " 진료비 영수증 7"  # 숫자를 잘못 읽고 얼룩을 더 읽어 본문이 같지 않다
    assert ("duplicate_page", (1, 2)) in page_flags(page_blocks(NUMBERS, misread), path)
    assert ("duplicate_page", (1, 3)) in page_flags(page_blocks(NUMBERS, "2020-01-01 1,000 2,000", misread),
                                                    scan(tmp_path / "three.pdf", [RECEIPT, DETAIL, shifted]))


def test_same_form_with_other_numbers_or_other_layout_is_not_a_duplicate(tmp_path):
    same_form = scan(tmp_path / "form.pdf", [RECEIPT, RECEIPT])
    other_day = NUMBERS.replace("2019-02-17", "2019-10-21").replace("2019-02-28", "2019-10-31")  # 같은 환자 다른 날 영수증
    assert not page_flags(page_blocks(NUMBERS, other_day), same_form)
    assert not page_flags(page_blocks(NUMBERS, NUMBERS + " 세부내역"), scan(tmp_path / "two.pdf", [RECEIPT, DETAIL]))  # 같은 금액, 다른 서식
    assert not page_flags(page_blocks(NUMBERS, NUMBERS + " 세부내역"))  # 쪽 그림이 없으면 본문이 같을 때만 중복
    assert not page_flags(page_blocks("1 2 3 40,000", "1 2 3 40,000 가"), same_form)  # 고유 숫자가 너무 적다


def title_page(page, *lines):
    """Text lines `(text, height)` stacked top to bottom on `page`."""
    out, top = [], 0
    for text, height in lines:
        out.append({"type": "text", "page": page, "text": text, "bbox": [10, top, 300, top + height],
                    "lines": [{"text": text, "bbox": [10, top, 300, top + height]}]})
        top += height + 5
    return out


BODY = [("환자성명 홍길동", 10), ("발급일 2024-01-02", 10), ("병명 급성 기관지염", 10)]


def test_two_form_titles_on_one_page_or_a_switch_between_pages_is_a_document_boundary():
    two = title_page(1, ("진 료 비 계산서·영수증", 22), *BODY, ("약제비 계산서·영수증", 20), *BODY)
    found = engine.unit_flags({}, TABLE, {}, two)
    assert [(f["code"], f["node"], f["pages"]) for f in found] == [("document_boundary", "P.STR.DOC", [1])]
    assert found[0]["titles"] == {1: ["진료비영수증", "약제비영수증"]}
    bundle = [*title_page(1, ("진단서", 24), *BODY), *title_page(2, ("진료비 세부산정내역", 24), *BODY)]
    assert page_flags(bundle) == {("document_boundary", (2,))}


def test_one_form_title_and_body_text_mentions_are_not_a_boundary():
    assert not page_flags(title_page(1, ("수술 확인서", 24), *BODY, ("*상기 내용은 진단서와는 무관함.*", 10)))
    assert not page_flags(title_page(1, ("[별지 제1호 서식] 진료비 세부산정내역", 12), ("진료비 세부산정내역", 24), *BODY))
    continued = [*title_page(1, ("진료비 세부산정내역", 24), *BODY), *title_page(2, *BODY), *title_page(3, ("세부산정내역", 22), *BODY)]
    assert not page_flags(continued)  # 같은 서식이 이어지는 쪽, 제목 없는 쪽은 경계가 아니다
