"""Build a searchable image PDF from macOS Vision OCR JSON without printing its text."""

import json
import sys
from pathlib import Path

import pymupdf

KOREAN_FONT = Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")


def convert(image_path: Path, ocr_path: Path, pdf_path: Path) -> None:
    ocr = json.loads(ocr_path.read_text())
    width, height = ocr["width"], ocr["height"]
    document = pymupdf.open()
    page = document.new_page(width=width, height=height)
    page.insert_image(page.rect, filename=str(image_path))
    page.insert_font(fontname="applegothic", fontfile=str(KOREAN_FONT))
    for line in ocr["lines"]:
        point = pymupdf.Point(line["x"] * width, (1 - line["y"]) * height)
        page.insert_text(point, line["text"], fontname="applegothic", fontsize=max(1, line["height"] * height), render_mode=3)
    pdf_path.unlink(missing_ok=True)
    document.save(pdf_path, garbage=4, deflate=True)
    document.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: ocr_json_to_searchable_pdf <input.png> <vision.json> <output.pdf>")
    convert(*(Path(value) for value in sys.argv[1:]))
