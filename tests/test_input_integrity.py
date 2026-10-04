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
