from backend.parsers import parse


def test_html_becomes_heading_text_and_table_markdown(tmp_path):
    path = tmp_path / "invoice.html"
    path.write_text("<html><head><title>x</title><style>p{}</style></head><body><h1>청구서</h1><p>병원: ABC <b>Hospital</b></p>"
                    "<table><tr><th>항목</th><th>금액</th></tr><tr><td>진료|비</td><td>120000</td></tr></table><script>alert(1)</script></body></html>", encoding="utf-8")
    markdown, blocks = parse(path, path.name, "text/html")
    assert [b["type"] for b in blocks] == ["heading", "text", "table"]
    assert blocks[2]["rows"] == [["항목", "금액"], ["진료|비", "120000"]]
    assert markdown == "## 청구서\n\n병원: ABC Hospital\n\n| 항목 | 금액 |\n| --- | --- |\n| 진료\\|비 | 120000 |"
