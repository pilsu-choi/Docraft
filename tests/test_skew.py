"""페이지 기울기: 90도 단위 방향과 작은 기울기를 한 각도로 합쳐 모델 이미지를 돌리고, 띠 상자는 그 이미지 기준으로 맞춘다."""
import base64
import io

import fitz
import numpy as np
import pytest
from PIL import Image, ImageFilter

from backend import engine, parsers
from backend.parsers import expanded, spin, unturn

from test_orientation import _page, _scanned

ANGLES = [0, 2, -2, 5, -5, 90 + 3, 180 - 2, 270 + 4, 90, 180, 20, -30, 40, -44, 90 + 30, 270 - 40]


def _decode(url):
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")


@pytest.fixture
def vision(monkeypatch):
    monkeypatch.setattr(engine, "ai_settings", lambda: {"vision": True})


WIDE = [0, 2, -2, 5, -5, 7, -7, 10, -10, 15, -15, 20, -20, 30, -30, 40, -40, 44, -44]


@pytest.mark.parametrize("tilt", WIDE)
@pytest.mark.parametrize("lying", [0, 90, 180, 270])
def test_tilt_measures_the_turn_that_straightens_a_tilted_page_at_any_quarter_turn(tilt, lying):
    image, _ = _page()
    scan = image.rotate(-tilt, resample=Image.BICUBIC, expand=True, fillcolor="white").rotate(lying, expand=True)
    assert parsers._tilt(scan) == pytest.approx(tilt, abs=0.5)


@pytest.mark.parametrize("tilt", [0.2, -0.2, 0.1])
def test_tilt_below_the_threshold_is_ignored(tilt):
    image, _ = _page()
    assert parsers._tilt(image.rotate(-tilt, resample=Image.BICUBIC, fillcolor="white")) == 0


def test_tilt_past_45_degrees_is_the_other_side_of_a_quarter_turn():
    image, _ = _page()
    assert parsers._tilt(image.rotate(-50, resample=Image.BICUBIC, expand=True, fillcolor="white")) == pytest.approx(-40, abs=0.5)


@pytest.mark.parametrize("page", ["blank", "noise", "blur"])
def test_tilt_declines_a_page_without_lines(page):
    rng = np.random.default_rng(0)
    noise = Image.fromarray(rng.integers(0, 255, (640, 900), dtype=np.uint8))
    image = {"blank": Image.new("RGB", (900, 640), "white"), "noise": noise, "blur": noise.filter(ImageFilter.GaussianBlur(8))}[page]
    assert parsers._tilt(image) == 0


@pytest.mark.parametrize("turn, tilt", [(0, 3), (0, -4), (90, 3), (180, -2), (270, 4), (90, 0), (270, 0)])
def test_upright_puts_the_tilt_on_the_blocks_so_the_angle_is_quarter_turn_plus_tilt(turn, tilt, tmp_path, monkeypatch):
    upright, boxes = _page()
    scan = upright.rotate(-tilt, resample=Image.BICUBIC, fillcolor="white")  # 기울어진 바로 선 페이지
    scan = scan.rotate(-turn, expand=True) if turn else scan  # 시계 방향으로 눕힌 스캔: 반시계 `turn`도로 세운다
    path = tmp_path / "scan.png"
    scan.save(path)
    block = {"page": 1, "text": "x", "bbox": [0, 0, *scan.size], "page_size": list(scan.size), "lines": [{"bbox": boxes[0]}]}
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"page_deskew": True})
    monkeypatch.setattr(parsers, "_vote", lambda image, lines: turn)
    monkeypatch.setattr(parsers, "_read_turned", lambda image, angle, deadline: [dict(block, page_size=list(image.rotate(angle, expand=True).size))])
    [out] = parsers._upright([block], str(path), 1)
    assert out.get("orientation", 0) == turn
    assert engine._angle(out) == pytest.approx(turn + tilt, abs=0.5)


def test_deskew_flag_off_leaves_only_quarter_turns(tmp_path, monkeypatch):
    upright, boxes = _page()
    path = tmp_path / "scan.png"
    upright.rotate(-4, resample=Image.BICUBIC, fillcolor="white").save(path)
    block = {"page": 1, "text": "x", "bbox": [0, 0, *upright.size], "page_size": list(upright.size), "lines": [{"bbox": boxes[0]}]}
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"page_deskew": False})
    monkeypatch.setattr(parsers, "_vote", lambda image, lines: 0)
    assert "skew" not in parsers._upright([block], str(path), 1)[0]


@pytest.mark.parametrize("angle", ANGLES)
def test_a_clip_of_the_turned_page_shows_the_same_place_for_any_angle(angle, tmp_path, vision):
    path = tmp_path / "page.png"
    image = Image.new("RGB", (600, 400), "white")
    image.paste((255, 0, 0), (420, 90, 480, 150))  # 원본 페이지의 빨간 표식
    image.save(path)
    with fitz.open(path) as document:
        size = [document[0].rect.width, document[0].rect.height]
    canvas = expanded(size, angle)
    cx, cy = spin((450 * size[0] / 600, 120 * size[1] / 400), angle, size, canvas)  # 표식 중심이 돌린 페이지에서 놓이는 곳
    half = 8 * size[0] / 600
    on = [(cx - half) / canvas[0], (cy - half) / canvas[1], (cx + half) / canvas[0], (cy + half) / canvas[1]]
    off = [1 - on[2], 1 - on[3], 1 - on[0], 1 - on[1]]  # 돌린 페이지 한가운데를 지나 맞은편: 원본의 흰 곳
    hit, miss = (np.asarray(_decode(engine._page_images(str(path), [1], {1: angle}, [clip])[0])).reshape(-1, 3) for clip in (on, off))
    assert (hit[:, 0] > 200).mean() > 0.9 and (hit[:, 1] < 80).mean() > 0.9
    assert (miss[:, 1] < 80).mean() < 0.1


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_quarter_turns_render_as_before(angle, tmp_path, vision):
    path = tmp_path / "page.png"
    Image.effect_noise((300, 200), 60).convert("RGB").save(path)
    with fitz.open(path) as document:
        page = document[0]
        zoom = min(engine.VISION_MAX_EDGE / max(page.rect.width, page.rect.height), 2.0)
        old = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom).prerotate(-angle), alpha=False).tobytes("jpeg", jpg_quality=90)
        # 띠: 돌린 페이지의 [0.1, 0.2, 0.5, 0.6] 은 원본의 이 영역이다
        size = [page.rect.width, page.rect.height]
        box = [0.1 * expanded(size, angle)[0], 0.2 * expanded(size, angle)[1], 0.5 * expanded(size, angle)[0], 0.6 * expanded(size, angle)[1]]
        corners = [spin(p, -angle, expanded(size, angle), size) for p in ((box[0], box[1]), (box[2], box[3]))]
        origin = fitz.Rect(min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners))
        zoom = min(engine.VISION_MAX_EDGE / max(box[2] - box[0], box[3] - box[1]), 4.0)
        strip = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom).prerotate(-angle), clip=origin, alpha=False).tobytes("jpeg", jpg_quality=90)
    whole, band = engine._page_images(str(path), [1], {1: angle}), engine._page_images(str(path), [1], {1: angle}, [[0.1, 0.2, 0.5, 0.6]])
    assert base64.b64decode(whole[0].split(",", 1)[1]) == old and base64.b64decode(band[0].split(",", 1)[1]) == strip


@pytest.mark.parametrize("angle", [0, 3, -5, 93, 178, 274, 20, -30, 38, 120, 235])
def test_unturn_to_the_turned_page_gives_back_the_straight_line_box(angle):
    size = [900, 640]
    canvas = expanded(size, angle)
    straight = [400, 300, 600, 330]  # 돌린 페이지에서 똑바로 선 줄
    seen = engine._covering(straight, -angle, canvas, size)  # 원본(기울어진) 페이지의 OCR 줄 상자: 기운 줄을 덮는 상자
    block = {"bbox": list(seen), "page_size": size, "lines": [{"bbox": list(seen)}]}
    [mapped] = unturn([block], 360 - angle)
    assert mapped["page_size"] == pytest.approx(canvas)
    assert mapped["lines"][0]["bbox"] == pytest.approx(straight, abs=1e-6)


def test_unturn_keeps_the_box_size_where_the_box_no_longer_tells_the_line_apart():
    block = {"page_size": [900, 640], "lines": [{"bbox": [100, 100, 300, 300]}]}
    line = unturn([block], 360 - 44)[0]["lines"][0]["bbox"]
    assert (line[2] - line[0], line[3] - line[1]) == pytest.approx((200, 200))


@pytest.mark.parametrize("tilt", [10, -20, 30, -35])
def test_text_rows_of_a_steep_page_stay_apart_on_the_turned_page(tilt):
    size = [1200, 900]
    canvas = expanded(size, tilt)
    rows = [[100, 100 + 60 * i, 900, 130 + 60 * i] for i in range(10)]  # 똑바로 세운 페이지의 줄 10개, 30 간격
    lines = [{"text": f"{i} 1,000", "bbox": list(engine._covering(box, -tilt, canvas, size))} for i, box in enumerate(rows)]
    block = {"page": 1, "type": "table", "page_size": size, "skew": tilt, "lines": lines}
    upright = unturn([block], 360 - engine._angle(block))[0]
    assert len(engine._line_rows(upright["lines"])[0]) == 10


@pytest.mark.parametrize("turn, tilt", [(0, 20), (0, -30), (90, 15), (180, 25), (270, -20), (90, -35)])
def test_orientation_is_voted_on_the_straightened_page_of_a_steep_scan(turn, tilt, tmp_path, monkeypatch):
    upright, boxes = _page()
    scan = upright.rotate(-(turn + tilt), resample=Image.BICUBIC, expand=True, fillcolor="white")
    path = tmp_path / "scan.png"
    scan.save(path)
    seen = [list(engine._covering(box, -(turn + tilt), upright.size, scan.size)) for box in boxes]  # OCR 줄 상자: 기운 줄을 덮는 상자
    block = {"page": 1, "text": "x", "bbox": [0, 0, *scan.size], "page_size": list(scan.size), "lines": [{"bbox": box} for box in seen]}
    monkeypatch.setattr(parsers, "ocr_settings", lambda: {"page_deskew": True})
    monkeypatch.setattr(parsers, "_read_turned", lambda image, angle, deadline: [dict(block, page_size=list(image.rotate(angle, expand=True).size))])
    [out] = parsers._upright([block], str(path), 1)
    assert out.get("orientation", 0) == turn
    assert engine._angle(out) == pytest.approx(turn + tilt, abs=0.5)
