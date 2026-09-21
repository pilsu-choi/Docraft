import httpx
import fitz
import pytest
from PIL import Image, ImageDraw

from backend import parsers
from backend.parsers import ParseError, parse
from backend.table_grid import ruled_table


def _pdf(tmp_path, *texts):
    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    for text in texts:
        doc.new_page().insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def test_page_range_selects_subset_and_ignores_out_of_range_pages(tmp_path):
    path = _pdf(tmp_path, "one", "two", "three")
    markdown, blocks = parse(path, path.name, "application/pdf", {"pages": "1,3,9"})
    assert [b["page"] for b in blocks] == [1, 3]
    assert "one" in markdown and "three" in markdown and "two" not in markdown


def test_page_range_with_no_pages_remaining_is_a_parse_error(tmp_path):
    path = _pdf(tmp_path, "one")
    with pytest.raises(ParseError):
        parse(path, path.name, "application/pdf", {"pages": "9"})


def test_table_format_html_renders_an_html_table(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes(b"a,b\n1,2\n")
    markdown, _ = parse(path, path.name, "text/csv", {"table_format": "html"})
    assert markdown == "<table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>"


def test_provider_library_never_uses_ocr_for_images(tmp_path):
    path = tmp_path / "scan.png"
    path.write_bytes(b"fake-image-bytes")
    with pytest.raises(ParseError, match="이미지 OCR은 비활성화"):
        parse(path, path.name, "image/png", {"provider": "library"})


LAYOUT_RESPONSE = {"result": {"layoutParsingResults": [{"prunedResult": {"width": 100, "height": 100, "parsing_res_list": [
    {"block_bbox": [0, 0, 100, 100], "block_label": "text", "block_content": "머리글"},
    {"block_bbox": [0, 40, 100, 100], "block_label": "table", "block_content": "<table><tr><td>진찰료</td></tr></table>"},
]}}]}}
LINES_RESPONSE = {"result": {"ocrResults": [{"prunedResult": {
    "rec_texts": ["머리글", "진찰료", "여백"],
    "rec_boxes": [[10, 5, 40, 20], [10, 50, 40, 70], [200, 200, 240, 220]],
}}]}}


def _paddle(monkeypatch, lines_response, lines_url="http://lines.invalid"):
    """Mock both PaddleOCR pipelines; `lines_response` may be an exception to simulate the line service failing."""
    monkeypatch.setenv("PARSE_PROVIDER", "paddle")
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "http://layout.invalid")
    monkeypatch.setenv("PADDLEOCR_LINES_URL", lines_url)
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        body = lines_response if url.endswith("/ocr") else LAYOUT_RESPONSE
        if isinstance(body, Exception):
            raise body
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(parsers.httpx, "post", post)
    return calls


def test_ocr_lines_join_the_smallest_block_containing_them(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    path.write_bytes(b"fake-image-bytes")
    calls = _paddle(monkeypatch, LINES_RESPONSE)

    _, blocks = parse(path, path.name, "image/png")

    assert calls == ["http://layout.invalid/layout-parsing", "http://lines.invalid/ocr"]
    # The table box is nested in the page-wide text box, so the 진찰료 line belongs to the table.
    assert blocks[0]["lines"] == [{"text": "머리글", "bbox": [10.0, 5.0, 40.0, 20.0]}]
    assert blocks[1]["lines"] == [{"text": "진찰료", "bbox": [10.0, 50.0, 40.0, 70.0]}]
    # A line whose center falls outside every block is dropped.
    assert "여백" not in str(blocks)


def test_line_ocr_failure_keeps_parsing_without_lines(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    path.write_bytes(b"fake-image-bytes")
    _paddle(monkeypatch, httpx.ConnectError("refused"))

    _, blocks = parse(path, path.name, "image/png")

    assert [b["text"] for b in blocks] == ["머리글", "<table><tr><td>진찰료</td></tr></table>"]
    assert all("lines" not in block for block in blocks)


def test_line_ocr_is_skipped_when_not_configured(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    path.write_bytes(b"fake-image-bytes")
    calls = _paddle(monkeypatch, LINES_RESPONSE, lines_url="")

    _, blocks = parse(path, path.name, "image/png")

    assert calls == ["http://layout.invalid/layout-parsing"]
    assert all("lines" not in block for block in blocks)


def test_html_becomes_heading_text_and_table_markdown(tmp_path):
    path = tmp_path / "invoice.html"
    path.write_text("<html><head><title>x</title><style>p{}</style></head><body><h1>청구서</h1><p>병원: ABC <b>Hospital</b></p>"
                    "<table><tr><th>항목</th><th>금액</th></tr><tr><td>진료|비</td><td>120000</td></tr></table><script>alert(1)</script></body></html>", encoding="utf-8")
    markdown, blocks = parse(path, path.name, "text/html")
    assert [b["type"] for b in blocks] == ["heading", "text", "table"]
    assert blocks[2]["rows"] == [["항목", "금액"], ["진료|비", "120000"]]
    assert markdown == "## 청구서\n\n병원: ABC Hospital\n\n| 항목 | 금액 |\n| --- | --- |\n| 진료\\|비 | 120000 |"


def test_merged_cells_become_a_rectangular_grid_and_render_back_with_spans(tmp_path):
    path = tmp_path / "receipt.html"
    path.write_text("<table><tr><td rowspan=\"2\">항목</td><td colspan=\"2\">급여</td></tr><tr><td>본인</td><td>공단</td></tr>"
                    "<tr><td>진찰료</td><td>4,593</td><td>10,717</td></tr></table>", encoding="utf-8")
    markdown, blocks = parse(path, path.name, "text/html", {"table_format": "html"})
    assert blocks[0]["rows"] == [["항목", "급여", "급여"], ["항목", "본인", "공단"], ["진찰료", "4,593", "10,717"]]
    assert blocks[0]["spans"] == [[0, 0, 2, 1], [0, 1, 1, 2]]
    assert markdown == ("<table><tr><td rowspan=\"2\">항목</td><td colspan=\"2\">급여</td></tr><tr><td>본인</td><td>공단</td></tr>"
                        "<tr><td>진찰료</td><td>4,593</td><td>10,717</td></tr></table>")


def _ruled_form(path=None):
    """400x200 form: header row whose right cell spans two columns, then two body rows. Rules are 2px black."""
    image = Image.new("L", (400, 200), 255)
    draw = ImageDraw.Draw(image)
    for y in (10, 70, 130, 188):
        draw.rectangle((10, y, 390, y + 1), fill=0)
    for x in (10, 130, 388):
        draw.rectangle((x, 10, x + 1, 189), fill=0)
    draw.rectangle((260, 70, 261, 189), fill=0)  # no rule above y=70: 금액 spans both value columns
    if path:
        image.save(path)
    return image


FORM_LINES = [
    {"text": "항목", "bbox": [20, 30, 80, 50]}, {"text": "금액", "bbox": [230, 30, 290, 50]},
    {"text": "진찰료", "bbox": [20, 90, 90, 110]}, {"text": "1,000", "bbox": [140, 90, 200, 110]},
    {"text": "2,000", "bbox": [270, 90, 330, 110]}, {"text": "합계", "bbox": [20, 150, 80, 170]},
    # PP-OCR joined two cells into one line across the rule at x=260; it is cut at the word gap.
    {"text": "10 20", "bbox": [200, 150, 320, 170]},
]


def test_ruled_table_reads_structure_from_rules_and_splits_lines_joined_across_a_rule():
    rows, spans = ruled_table(_ruled_form(), [0, 0, 400, 200], FORM_LINES)
    assert rows == [["항목", "금액", "금액"], ["진찰료", "1,000", "2,000"], ["합계", "10", "20"]]
    assert spans == [[0, 1, 1, 2]]


def test_ruled_table_is_none_without_rules():
    assert ruled_table(Image.new("L", (400, 200), 255), [0, 0, 400, 200], FORM_LINES) is None


def _paddle_form(tmp_path, monkeypatch, vlm_html):
    path = tmp_path / "form.png"
    _ruled_form(path)
    layout = {"result": {"layoutParsingResults": [{"prunedResult": {"width": 400, "height": 200, "parsing_res_list": [
        {"block_bbox": [0, 0, 400, 200], "block_label": "table", "block_content": vlm_html},
    ]}}]}}
    lines = {"result": {"ocrResults": [{"prunedResult": {
        "rec_texts": [line["text"] for line in FORM_LINES], "rec_boxes": [line["bbox"] for line in FORM_LINES]}}]}}
    monkeypatch.setenv("PARSE_PROVIDER", "paddle")
    monkeypatch.setenv("PADDLEOCR_BASE_URL", "http://layout.invalid")
    monkeypatch.setenv("PADDLEOCR_LINES_URL", "http://lines.invalid")
    monkeypatch.setattr(parsers.httpx, "post", lambda url, **_: httpx.Response(
        200, json=lines if url.endswith("/ocr") else layout, request=httpx.Request("POST", url)))
    return parse(path, path.name, "image/png")[1][0]


def test_paddle_table_takes_the_ruled_grid_over_the_vlm_html(tmp_path, monkeypatch):
    table = _paddle_form(tmp_path, monkeypatch, "<table><tr><td>항목</td><td>금액</td></tr></table>")
    assert table["structure"] == "ruled"
    assert table["rows"][2] == ["합계", "10", "20"] and table["spans"] == [[0, 1, 1, 2]]
    assert table["text"].startswith('<table><tr><td>항목</td><td colspan="2">금액</td>')


def test_paddle_table_keeps_vlm_rows_when_the_grid_has_fewer_than_half(tmp_path, monkeypatch):
    vlm_html = "<table>" + "<tr><td>행</td></tr>" * 7 + "</table>"
    table = _paddle_form(tmp_path, monkeypatch, vlm_html)
    assert "structure" not in table and len(table["rows"]) == 7 and table["text"] == vlm_html


def test_paddle_table_keeps_merged_cell_spans(tmp_path, monkeypatch):
    path = tmp_path / "scan.png"
    path.write_bytes(b"fake-image-bytes")
    response = {"result": {"layoutParsingResults": [{"prunedResult": {"parsing_res_list": [{"block_label": "table",
        "block_content": "<table><tr><td colspan=\"2\">급여</td></tr><tr><td>본인</td><td>공단</td></tr></table>"}]}}]}}
    _paddle(monkeypatch, None, lines_url="")
    monkeypatch.setattr(parsers.httpx, "post", lambda url, **_: httpx.Response(200, json=response, request=httpx.Request("POST", url)))
    _, blocks = parse(path, path.name, "image/png")
    assert blocks[0]["rows"] == [["급여", "급여"], ["본인", "공단"]] and blocks[0]["spans"] == [[0, 0, 1, 2]]


def test_table_refine_corrects_cell_text_but_never_the_grid(tmp_path, monkeypatch):
    from PIL import Image
    from backend import engine
    path = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(path)
    html = ("<table><tr><td rowspan=\"2\">진 찰 로</td><td>670825</td><td>현금영수증</td><td>⑧</td></tr>"
            "<tr><td><img src=\"seal.jpg\"></td><td>현금영수증</td><td></td></tr></table>")
    block = {"type": "table", "page": 1, "bbox": [0, 0, 100, 100], "page_size": [100, 100], "text": html}
    monkeypatch.setenv("AI_MODE", "provider")
    monkeypatch.setenv("TABLE_REFINE", "true")
    monkeypatch.setenv("AI_BASE_URL", "http://ai.invalid")
    monkeypatch.setenv("AI_API_KEY", "key")
    monkeypatch.setenv("AI_VLM_MODEL", "vlm")
    sent = []
    # Model replies with the bare {cell: text} object, blanks a cell, moves text from another cell and writes into the empty and image cells.
    monkeypatch.setattr(engine, "_provider", lambda messages, timeout: sent.append(messages) or
                        {"0": "진찰료", "1": "670925", "2": "", "3": "⑥", "4": "직인", "5": "현금승인번호", "6": "40,000"})
    refined = engine.refine_table(block, str(path))
    assert refined == ("<table><tr><td rowspan=\"2\">진찰료</td><td>670925</td><td>현금영수증</td><td>⑥</td></tr>"
                       "<tr><td><img src=\"seal.jpg\"></td><td>현금영수증</td><td></td></tr></table>")
    assert '"4"' not in sent[0][0]["content"][-1]["text"]  # the image cell is never sent
    monkeypatch.setenv("TABLE_REFINE", "false")
    assert engine.refine_table(block, str(path)) is None
