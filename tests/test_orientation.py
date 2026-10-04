"""스캔 방향 정규화: 돌아간 페이지를 바로 세워 다시 읽고, 좌표는 원본 파일 기준으로 되돌린다."""
import base64
import io

import fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from backend import engine, parsers, reprocess
from backend.parsers import orientation, unturn

LINES = ["2024.12.24 1,234,560", "진료비 12.5 3,900", "합계 15,810.00", "2023.11.14 8,130", "1,000 2.5 660",
         "본인부담금 6,799.", "B1091A 4,878", "0.15 1,589,000"]


def _page(width=900, height=640):
    """흰 바탕에 날짜·금액 줄을 찍은 바로 선 페이지와 줄 상자(OCR 줄 좌표 역할)."""
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=30)
    boxes = []
    for index, text in enumerate(LINES):
        x, y = 40 + (index % 2) * 420, 40 + (index // 2) * 140
        left, top, right, bottom = draw.textbbox((x, y), text, font=font)
        draw.text((x, y), text, fill="black", font=font)
        boxes.append([left - 3, top - 4, right + 3, bottom + 4])
    return image, boxes


def _forward(box, turn, size):
    """원본 좌표 → `turn`도 반시계로 돌린 페이지 좌표(`unturn`의 역)."""
    width, height = size
    point = {90: lambda x, y: (y, width - x), 180: lambda x, y: (width - x, height - y),
             270: lambda x, y: (height - y, x)}[turn]
    corners = [point(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
    return [min(x for x, _ in corners), min(y for _, y in corners), max(x for x, _ in corners), max(y for _, y in corners)]


def _scanned(scan_turn):
    """바로 선 페이지를 `scan_turn`도 반시계로 돌려 스캔한 이미지와 그 위의 줄 상자."""
    image, boxes = _page()
    if not scan_turn:
        return image, boxes
    return image.rotate(scan_turn, expand=True), [_forward(box, scan_turn, image.size) for box in boxes]


@pytest.mark.parametrize("scan_turn", [0, 90, 180, 270])
def test_orientation_returns_the_turn_that_makes_the_page_upright(scan_turn):
    image, boxes = _scanned(scan_turn)
    assert orientation(image, boxes) == (360 - scan_turn) % 360


def test_orientation_keeps_pages_without_clear_evidence():
    blank = Image.new("RGB", (400, 300), "white")
    assert orientation(blank, []) == 0
    assert orientation(blank, [[10, 10, 300, 40], [10, 50, 30, 250]]) == 0  # 잉크 없는 상자
    image, boxes = _page()
    assert orientation(image, boxes[:1]) == 0  # 마침표·쉼표 표가 너무 적으면 돌리지 않는다


@pytest.mark.parametrize("turn", [90, 180, 270])
def test_unturn_inverts_the_turn_for_boxes_lines_cells_and_polygons(turn):
    size = (100, 80)
    box = [20, 40, 30, 50]
    turned_size = [80, 100] if turn % 180 else [100, 80]
    polygon = [[20, 40], [30, 40], [30, 50], [20, 50]]
    point = lambda x, y: _forward([x, y, x, y], turn, size)[:2]
    block = {"bbox": _forward(box, turn, size), "page_size": turned_size, "lines": [{"bbox": _forward(box, turn, size)}],
             "cells": [{"bbox": _forward(box, turn, size), "page_size": turned_size, "rotation_degrees": 1.2,
                        "polygon": [point(x, y) for x, y in polygon], "blank": True, "verified": True}]}
    [mapped] = unturn([block], turn)
    assert mapped["bbox"] == mapped["lines"][0]["bbox"] == mapped["cells"][0]["bbox"] == box
    assert mapped["page_size"] == mapped["cells"][0]["page_size"] == list(size)
    assert sorted(map(tuple, mapped["cells"][0]["polygon"])) == sorted(map(tuple, polygon))
    assert mapped["cells"][0]["verified"] is True and mapped["orientation"] == turn
    assert unturn([block], 0) == [block] and "orientation" not in block


def _ocr(boxes, size, text="표"):
    """원격 OCR 응답 대역: 페이지 하나의 블록에 줄 상자를 붙인다."""
    return [parsers.block(text, "table", page=1, bbox=[0, 0, *size], page_size=list(size),
                          source="paddleocr_remote", lines=[{"text": "x", "bbox": box} for box in boxes],
                          cells=[{"bbox": boxes[0], "page": 1, "page_size": list(size)}])]


def test_turned_image_is_reread_upright_and_reported_in_the_original_frame(tmp_path, monkeypatch):
    scan, boxes = _scanned(270)  # 시계 방향 90도로 누운 스캔(고객 세부내역서 a0·a2·a3과 반대 방향)
    path = tmp_path / "scan.tif"
    scan.save(path)
    upright, upright_boxes = _page()
    calls = []

    def remote(file, file_type, **kwargs):
        with Image.open(file) as sent:
            calls.append(sent.size)
        return _ocr(boxes, scan.size, "누운") if len(calls) == 1 else _ocr(upright_boxes, upright.size, "바로")

    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"provider": "paddle"})
    monkeypatch.setattr(parsers, "_remote_paddle", remote)
    [block] = parsers.parse_image(str(path), "paddle")
    assert calls == [scan.size, upright.size]
    assert block["text"] == "바로" and block["orientation"] == 90 and block["page"] == 1
    assert block["page_size"] == list(scan.size) and block["bbox"] == [0, 0, *scan.size]
    assert block["lines"][0]["bbox"] == pytest.approx(boxes[0])
    assert block["cells"][0]["bbox"] == pytest.approx(boxes[0]) and block["cells"][0]["page_size"] == list(scan.size)


def test_upright_image_is_read_once(tmp_path, monkeypatch):
    image, boxes = _page()
    path = tmp_path / "scan.png"
    image.save(path)
    calls = []
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"provider": "paddle"})
    monkeypatch.setattr(parsers, "_remote_paddle", lambda *args, **kwargs: calls.append(1) or _ocr(boxes, image.size))
    [block] = parsers.parse_image(str(path), "paddle")
    assert len(calls) == 1 and "orientation" not in block


def test_failed_upright_reread_keeps_the_first_reading(tmp_path, monkeypatch):
    scan, boxes = _scanned(90)
    path = tmp_path / "scan.png"
    scan.save(path)
    first = _ocr(boxes, scan.size)

    def remote(*args, **kwargs):
        if remote.called:
            raise parsers.ParseError("down")
        remote.called = True
        return first
    remote.called = False
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"provider": "paddle"})
    monkeypatch.setattr(parsers, "_remote_paddle", remote)
    assert parsers.parse_image(str(path), "paddle") == first


def test_multi_page_tif_is_read_as_one_page_per_frame(tmp_path, monkeypatch):
    scan, boxes = _scanned(180)
    upright, upright_boxes = _page()
    path = tmp_path / "scan.tif"
    scan.save(path, save_all=True, append_images=[upright])
    calls = []

    def remote(file, file_type, **kwargs):
        if file_type == 0:
            calls.append(kwargs["expected_pages"])
            with fitz.open(file) as pdf:
                assert len(pdf) == 2
            return _ocr(boxes, scan.size) + [{**b, "page": 2} for b in _ocr(upright_boxes, upright.size, "둘째")]
        return _ocr(upright_boxes, upright.size, "다시")
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"provider": "paddle"})
    monkeypatch.setattr(parsers, "_remote_paddle", remote)
    blocks = parsers.parse_image(str(path), "paddle")
    assert calls == [2] and {b["page"] for b in blocks} == {1, 2}
    assert [b.get("orientation", 0) for b in blocks if b["page"] == 1] == [180] and not any(b.get("orientation") for b in blocks if b["page"] == 2)


def test_scanned_pdf_rereads_only_the_turned_page(tmp_path, monkeypatch):
    upright, upright_boxes = _page()
    scan, boxes = _scanned(90)
    path = tmp_path / "scan.pdf"
    with fitz.open() as pdf:
        for image in (upright, scan):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            page = pdf.new_page(width=image.width, height=image.height)
            page.insert_image(page.rect, stream=buffer.getvalue())
        pdf.save(path)
    sizes = []

    def remote(file, file_type, **kwargs):
        if file_type == 0:
            first = _ocr(upright_boxes, upright.size, "1쪽")
            second = [{**b, "page": 2} for b in _ocr(boxes, scan.size, "2쪽 누운")]
            return first + second
        with Image.open(file) as sent:
            sizes.append(sent.size)
        return _ocr(upright_boxes, upright.size, "2쪽 바로")
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"provider": "paddle"})
    monkeypatch.setattr(parsers, "_remote_paddle", remote)
    blocks = parsers.parse_pdf(str(path), "paddle")
    assert sizes == [upright.size]
    assert [(b["page"], b["text"], b.get("orientation")) for b in blocks] == [(1, "1쪽", None), (2, "2쪽 바로", 270)]
    assert blocks[1]["page_size"] == list(scan.size) and blocks[1]["cells"][0]["page"] == 2


def test_vision_page_image_is_turned_upright(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    image = Image.new("RGB", (200, 100), "white")
    image.paste((0, 0, 0), (0, 0, 20, 20))  # 왼쪽 위 표식
    image.save(path)
    monkeypatch.setattr(engine, "ai_settings", lambda: {"vision": True})
    [url] = engine._page_images(str(path), [1], {1: 90})
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as sent:
        assert sent.height > sent.width  # 반시계 90도: 왼쪽 위 표식이 왼쪽 아래로
        assert sent.convert("L").getpixel((3, sent.height - 4)) < 80 and sent.convert("L").getpixel((3, 3)) > 200


def test_roi_crop_of_a_turned_page_is_read_upright_and_mapped_back(tmp_path):
    source = tmp_path / "scan.png"
    Image.new("RGB", (100, 80), "white").save(source)
    target = tmp_path / "roi.png"
    crop = reprocess._crop(str(source), 1, [20, 20, 60, 40], [100, 80], 1, str(target), 90)
    with Image.open(target) as roi:
        unturned = (roi.height, roi.width)
    assert unturned == (round(crop[2]), round(crop[3]))
    # 바로 세운 ROI 기준 줄 상자 → 원본 페이지 좌표
    local = [{"bbox": _forward([0, 0, 10, 5], 90, unturned), "page_size": [unturned[1], unturned[0]]}]
    [mapped] = reprocess._remap(unturn(local, 90), 1, [100, 80], crop)
    assert mapped["bbox"] == pytest.approx([crop[0], crop[1], crop[0] + 10, crop[1] + 5])


def test_table_refine_crop_of_a_turned_page_is_sent_upright(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    Image.new("RGB", (200, 100), "white").save(path)  # 원본(돌아간) 페이지: 가로로 긴 표 영역
    block = {"type": "table", "page": 1, "bbox": [0, 0, 200, 100], "page_size": [200, 100], "orientation": 90,
             "text": "<table><tr><td>진 찰 로</td></tr></table>"}
    for name, value in {"AI_MODE": "provider", "TABLE_REFINE": "true", "AI_BASE_URL": "http://ai.invalid",
                        "AI_API_KEY": "key", "AI_VLM_MODEL": "vlm"}.items():
        monkeypatch.setenv(name, value)
    sent = []
    monkeypatch.setattr(engine, "_provider", lambda messages, timeout: sent.append(messages) or {})
    engine.refine_tables([block], str(path))
    url = sent[0][0]["content"][0]["image_url"]["url"]
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
        assert image.height > image.width  # 반시계 90도로 바로 세운 크롭
