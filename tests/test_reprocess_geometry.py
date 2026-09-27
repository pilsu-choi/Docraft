"""Geometry regressions for crops rendered from oriented images and multi-page PDFs."""

import fitz
from PIL import Image, ImageDraw

from backend.reprocess import _crop, _remap


def _oriented_image(path, orientation):
    image = Image.new("RGB", (120, 80), "red")
    ImageDraw.Draw(image).rectangle((60, 0, 119, 79), fill="blue")
    exif = Image.Exif()
    exif[274] = orientation
    image.save(path, format="JPEG", quality=100, exif=exif)


def test_exif_6_and_8_crop_uses_transposed_source_coordinates(tmp_path):
    for orientation, expected in ((6, "red"), (8, "blue")):
        source = tmp_path / f"orientation-{orientation}.jpg"
        target = tmp_path / f"crop-{orientation}.png"
        _oriented_image(source, orientation)

        crop = _crop(str(source), 1, [10, 10, 30, 30], [80, 120], 2, str(target))

        assert crop is not None
        sample = Image.open(target).convert("RGB").getpixel((20, 20))
        if expected == "red":
            assert sample[0] > sample[2] * 2
        else:
            assert sample[2] > sample[0] * 2


def test_pdf_crop_selects_page_two_and_remaps_roi_boxes_to_original_page(tmp_path):
    source = tmp_path / "two-pages.pdf"
    document = fitz.open()
    first = document.new_page(width=200, height=100)
    first.draw_rect(fitz.Rect(0, 0, 200, 100), color=(1, 0, 0), fill=(1, 0, 0))
    second = document.new_page(width=200, height=100)
    second.draw_rect(fitz.Rect(0, 0, 200, 100), color=(0, 0, 1), fill=(0, 0, 1))
    document.save(source)
    document.close()
    target = tmp_path / "page-two-crop.png"

    crop = _crop(str(source), 2, [110, 20, 150, 60], [200, 100], 2, str(target))

    assert crop == (90.0, 0.0, 80.0, 80.0)
    pixel = Image.open(target).convert("RGB").getpixel((40, 40))
    assert pixel[2] > pixel[0] * 2
    mapped = _remap([{"bbox": [5, 10, 25, 30], "page_size": [40, 40],
                      "lines": [{"text": "x", "bbox": [10, 5, 20, 15]}]}],
                    2, [200, 100], crop)[0]
    assert mapped["page"] == 2
    assert mapped["page_size"] == [200, 100]
    assert mapped["bbox"] == [100.0, 20.0, 140.0, 60.0]
    assert mapped["lines"][0]["bbox"] == [110.0, 10.0, 130.0, 30.0]


def test_crop_clamps_regions_at_page_edges_and_rejects_off_page_bbox(tmp_path):
    source = tmp_path / "page.png"
    Image.new("RGB", (100, 80), "green").save(source)
    target = tmp_path / "edge-crop.png"

    crop = _crop(str(source), 1, [-10, -10, 10, 10], [100, 80], 2, str(target))

    assert crop == (0.0, 0.0, 20.0, 20.0)
    assert Image.open(target).size == (20, 20)
    assert _crop(str(source), 1, [300, 300, 320, 320], [100, 80], 2, str(target)) is None
