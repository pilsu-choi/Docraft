"""페이지 기울기: 90도 단위 방향과 작은 기울기를 한 각도로 합쳐 모델 이미지를 돌리고, 띠 상자는 그 이미지 기준으로 맞춘다."""
import base64
import io

import fitz
import numpy as np
import pytest
from PIL import Image

from backend import engine, parsers
from backend.parsers import expanded, spin, unturn

from test_orientation import _page, _scanned

ANGLES = [0, 2, -2, 5, -5, 90 + 3, 180 - 2, 270 + 4, 90, 180]


def _decode(url):
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")


@pytest.fixture
def vision(monkeypatch):
    monkeypatch.setattr(engine, "ai_settings", lambda: {"vision": True})


@pytest.mark.parametrize("tilt", [0, 2, -2, 5, -5, 7, -7])
def test_tilt_measures_the_turn_that_straightens_a_tilted_page(tilt):
    image, _ = _page()
    assert parsers._tilt(image.rotate(-tilt, resample=Image.BICUBIC, fillcolor="white")) == pytest.approx(tilt, abs=0.5)


@pytest.mark.parametrize("tilt", [0.2, -0.2, 0.1])
def test_tilt_below_the_threshold_is_ignored(tilt):
    image, _ = _page()
    assert parsers._tilt(image.rotate(-tilt, resample=Image.BICUBIC, fillcolor="white")) == 0


def test_tilt_beyond_the_search_limit_is_not_trusted():
    image, _ = _page()
    assert parsers._tilt(image.rotate(-12, resample=Image.BICUBIC, fillcolor="white")) == 0


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
    hit, miss = (np.asarray(_decode(url)).reshape(-1, 3) for url in engine._page_images(str(path), [1], {1: angle}, [on, off]))
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


@pytest.mark.parametrize("angle", [0, 3, -5, 93, 178, 274])
def test_unturn_to_the_turned_page_moves_each_box_centre_where_the_image_puts_it(angle):
    size = [900, 640]
    block = {"bbox": [100, 200, 300, 260], "page_size": size, "lines": [{"bbox": [100, 200, 300, 230]}]}
    [mapped] = unturn([block], 360 - angle)
    canvas = expanded(size, angle)
    assert mapped["page_size"] == pytest.approx(canvas)
    expected = spin((200, 215), angle, size, canvas)
    line = mapped["lines"][0]["bbox"]
    assert ((line[0] + line[2]) / 2, (line[1] + line[3]) / 2) == pytest.approx(expected)
    assert (line[2] - line[0], line[3] - line[1]) == pytest.approx((300 - 100, 30) if angle % 180 < 45 or angle % 180 > 135 else (30, 200), abs=1e-6)
