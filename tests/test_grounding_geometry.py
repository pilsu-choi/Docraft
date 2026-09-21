"""Grounding geometry must be usable by the red document overlay."""

import fitz

from backend.parsers import parse, parse_pdf


def test_pdf_text_grounding_bbox_is_a_non_degenerate_page_coordinate_rect(tmp_path):
    path = tmp_path / "synthetic.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=240, height=160)
    page.insert_text((30, 50), "synthetic invoice")
    pdf.save(path)
    pdf.close()

    item = next(block for block in parse_pdf(path) if "synthetic invoice" in block["text"])
    x0, y0, x1, y1 = item["bbox"]
    width, height = item["page_size"]
    assert item["page"] == 1
    assert 0 <= x0 < x1 <= width
    assert 0 <= y0 < y1 <= height
    # Consumers normalize as percentages, so these are finite and on-canvas.
    assert 0 <= x0 / width < x1 / width <= 1
    assert 0 <= y0 / height < y1 / height <= 1


def test_pdf_multiline_block_becomes_ordered_line_boxes(tmp_path):
    path = tmp_path / "multiline.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=240, height=180)
    page.insert_textbox(fitz.Rect(20, 20, 220, 150), "first line\nsecond line", fontsize=12)
    pdf.save(path)
    pdf.close()

    blocks = parse_pdf(path)
    assert [item["text"] for item in blocks] == ["first line", "second line"]
    assert all(item["page"] == 1 and item["page_size"] == [240, 180] for item in blocks)
    assert blocks[0]["bbox"][3] < blocks[1]["bbox"][3]
    assert all(item["bbox"][3] - item["bbox"][1] < 20 for item in blocks)
    markdown, parsed = parse(path, path.name, "application/pdf")
    assert markdown == "first line\nsecond line"
    assert parsed == blocks
