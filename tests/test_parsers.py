import fitz
import pytest

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


def test_html_becomes_heading_text_and_table_markdown(tmp_path):
    path = tmp_path / "invoice.html"
    path.write_text("<html><head><title>x</title><style>p{}</style></head><body><h1>청구서</h1><p>병원: ABC <b>Hospital</b></p>"
                    "<table><tr><th>항목</th><th>금액</th></tr><tr><td>진료|비</td><td>120000</td></tr></table><script>alert(1)</script></body></html>", encoding="utf-8")
    markdown, blocks = parse(path, path.name, "text/html")
    assert [b["type"] for b in blocks] == ["heading", "text", "table"]
    assert blocks[2]["rows"] == [["항목", "금액"], ["진료|비", "120000"]]
    assert markdown == "## 청구서\n\n병원: ABC Hospital\n\n| 항목 | 금액 |\n| --- | --- |\n| 진료\\|비 | 120000 |"
