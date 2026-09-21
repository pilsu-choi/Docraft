import csv
import io
import base64
import logging
import time
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
import fitz
import httpx

from .config import ocr_settings

logger = logging.getLogger(__name__)


class ParseError(ValueError):
    pass


def block(text, kind="text", page=None, bbox=None, **extra):
    return {"type": kind, "page": page, "bbox": bbox, "text": str(text), **extra}


def parse_pdf(path):
    result = []
    with fitz.open(path) as pdf:
        for number, page in enumerate(pdf, 1):
            for region in page.get_text("dict")["blocks"]:
                for line in region.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if text:
                        result.append(block(text, page=number, bbox=list(line["bbox"]), page_size=[page.rect.width, page.rect.height]))
    if not result:
        if ocr_settings()["provider"] != "paddle":
            raise ParseError("스캔 PDF OCR은 비활성화되어 있습니다. PARSE_PROVIDER=paddle과 원격 endpoint를 설정해 주세요.")
        result = _remote_paddle(path, 0)
    if not result:
        raise ParseError("PaddleOCR가 스캔 PDF에서 텍스트를 찾지 못했습니다.")
    return result


def parse_image(path):
    if ocr_settings()["provider"] != "paddle":
        raise ParseError("이미지 OCR은 비활성화되어 있습니다. PARSE_PROVIDER=paddle과 원격 endpoint를 설정해 주세요.")
    return _remote_paddle(path, 1)


def _remote_paddle(path, file_type):
    settings = ocr_settings()
    if not settings["configured"]:
        raise ParseError("PaddleOCR 원격 서비스가 설정되지 않았습니다. PADDLEOCR_BASE_URL을 설정해 주세요.")
    endpoint = settings["base_url"]
    if not endpoint.endswith("/layout-parsing"):
        endpoint += "/layout-parsing"
    headers = {"Authorization": f"Bearer {settings['token']}"} if settings["token"] else {}
    payload = {"file": base64.b64encode(Path(path).read_bytes()).decode("ascii"), "fileType": file_type, "visualize": False, "returnMarkdownImages": False}
    logger.debug("paddleocr request: endpoint=%s file_type=%s bytes=%d", endpoint, file_type, len(payload["file"]))
    started = time.monotonic()
    try:
        response = httpx.post(endpoint, json=payload, headers=headers, timeout=settings["timeout"])
        response.raise_for_status()
        pages = response.json()["result"]["layoutParsingResults"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.error("paddleocr request failed: status=%s elapsed=%.2fs %s", status, time.monotonic() - started, exc)
        suffix = f" (HTTP {status})" if status else ""
        raise ParseError(f"PaddleOCR 원격 처리 실패{suffix}") from exc
    logger.debug("paddleocr response: elapsed=%.2fs pages=%d", time.monotonic() - started, len(pages))
    blocks = []
    for page_no, page in enumerate(pages, 1):
        pruned = page.get("prunedResult") or {}
        size = [pruned["width"], pruned["height"]] if pruned.get("width") and pruned.get("height") else None
        regions = [r for r in pruned.get("parsing_res_list") or [] if str(r.get("block_content") or "").strip()]
        for region in regions:
            bbox = region.get("block_bbox")
            kind = "table" if region.get("block_label") == "table" else "text"
            blocks.append(block(region["block_content"].strip(), kind, page=page_no, bbox=list(bbox) if bbox and len(bbox) == 4 else None, page_size=size, source="paddleocr_remote"))
        markdown = page.get("markdown", {})
        text = markdown.get("text") if isinstance(markdown, dict) else None
        if not regions and text and text.strip():
            blocks.append(block(text.strip(), "text", page=page_no, bbox=None, source="paddleocr_remote"))
    if not blocks:
        raise ParseError("PaddleOCR 원격 응답에서 텍스트를 찾지 못했습니다.")
    return blocks


def parse_docx(path):
    doc = Document(path)
    result = [block(p.text, "heading" if p.style.name.startswith("Heading") else "text") for p in doc.paragraphs if p.text.strip()]
    for table_no, table in enumerate(doc.tables):
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        result.append(block("\n".join(" | ".join(row) for row in rows), "table", rows=rows, table=table_no))
    return result


def parse_xlsx(path):
    result = []
    book = load_workbook(path, read_only=True, data_only=True)
    for sheet in book.worksheets:
        rows = [["" if value is None else str(value) for value in row] for row in sheet.iter_rows(values_only=True)]
        rows = [row for row in rows if any(row)]
        if rows:
            result.append(block("\n".join(" | ".join(row) for row in rows), "table", rows=rows, sheet=sheet.title))
    return result


def parse_csv(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    return [block("\n".join(" | ".join(row) for row in rows), "table", rows=rows)]


def parse_text(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return [block(line) for line in text.splitlines() if line.strip()]


class _HtmlBlocks(HTMLParser):
    BLOCKS = {"p", "div", "li", "br", "section", "article", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.blocks, self.text, self.rows, self.skip = [], "", None, 0

    def flush(self, kind="text"):
        if self.text.strip():
            self.blocks.append(block(" ".join(self.text.split()), kind))
        self.text = ""

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.skip += 1
        elif tag == "table":
            self.flush()
            self.rows = []
        elif self.rows is not None and tag == "tr":
            self.rows.append([])
        elif self.rows is not None and tag in {"td", "th"}:
            self.text = ""
        elif tag in self.BLOCKS:
            self.flush()

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.skip = max(0, self.skip - 1)
        elif tag == "table" and self.rows is not None:
            rows = [row for row in self.rows if any(row)]
            self.rows, self.text = None, ""
            if rows:
                self.blocks.append(block("\n".join(" | ".join(row) for row in rows), "table", rows=rows))
        elif self.rows is not None and tag in {"td", "th"} and self.rows:
            self.rows[-1].append(" ".join(self.text.split()))
            self.text = ""
        elif self.rows is None and tag in self.BLOCKS:
            self.flush("heading" if tag[0] == "h" and tag[1:].isdigit() else "text")

    def handle_data(self, data):
        if not self.skip:
            self.text += data


def parse_html(path):
    parser = _HtmlBlocks()
    parser.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    parser.close()
    parser.flush()
    return parser.blocks


def _markdown(item):
    rows = item.get("rows")
    if item["type"] == "heading":
        return f"## {item['text']}"
    if item["type"] != "table" or not rows:
        return item["text"]
    width = max(map(len, rows))
    lines = ["| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in row + [""] * (width - len(row))) + " |" for row in rows]
    return "\n".join([lines[0], "|" + " --- |" * width, *lines[1:]])


def parse(path, filename, media_type):
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        blocks = parse_pdf(path)
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        blocks = parse_image(path)
    elif suffix == ".docx":
        blocks = parse_docx(path)
    elif suffix == ".xlsx":
        blocks = parse_xlsx(path)
    elif suffix == ".csv":
        blocks = parse_csv(path)
    elif suffix in {".html", ".htm"}:
        blocks = parse_html(path)
    elif suffix in {".txt", ".md"} or media_type.startswith("text/"):
        blocks = parse_text(path)
    else:
        raise ParseError(f"지원하지 않는 파일 형식입니다: {suffix or media_type}")
    if not blocks:
        raise ParseError("문서에서 내용을 찾지 못했습니다.")
    separator = "\n" if suffix in {".pdf", ".txt", ".md"} else "\n\n"
    markdown = separator.join(map(_markdown, blocks))
    logger.debug("parse: suffix=%s blocks=%d markdown_chars=%d", suffix, len(blocks), len(markdown))
    return markdown, blocks
