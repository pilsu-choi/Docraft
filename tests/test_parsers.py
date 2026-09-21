import httpx
import fitz
import pytest

from backend import parsers
from backend.parsers import ParseError, parse


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
