import csv
import io
import base64
import html
import logging
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
import fitz
import httpx
from PIL import Image

from .config import ocr_settings
from .table_grid import ruled_table

logger = logging.getLogger(__name__)

LABEL_TYPES = {
    "table": "table", "doc_title": "heading", "paragraph_title": "heading",
    "image": "figure", "chart": "figure", "figure_title": "figure", "header_image": "figure", "footer_image": "figure",
    "header": "marginalia", "footer": "marginalia", "number": "marginalia", "footnote": "marginalia", "aside_text": "marginalia",
    "formula": "formula",
}


class ParseError(ValueError):
    pass


def block(text, kind="text", page=None, bbox=None, **extra):
    return {"type": kind, "page": page, "bbox": bbox, "text": str(text), **extra}


def _pages_from_range(spec, total):
    """"1-3,5" (1-based) -> sorted page numbers within [1, total]; drops out-of-range pages."""
    pages = set()
    for part in spec.split(","):
        start, _, end = part.partition("-")
        start, end = int(start), int(end or start)
        pages.update(range(start, end + 1))
    return sorted(p for p in pages if 1 <= p <= total)


def _page_pdf(path, pages):
    """A temporary single-use PDF containing only `pages` (1-based); caller deletes it."""
    with fitz.open(path) as src, fitz.open() as sub:
        for number in pages:
            sub.insert_pdf(src, from_page=number - 1, to_page=number - 1)
        target = Path(path).with_name(f".{uuid.uuid4().hex}.pdf")
        sub.save(target)
    return target


def parse_pdf(path, provider="auto", pages=None):
    with fitz.open(path) as pdf:
        total = len(pdf)
    selected = _pages_from_range(pages, total) if pages else list(range(1, total + 1))
    if not selected:
        raise ParseError("선택한 페이지 범위에 유효한 페이지가 없습니다.")
    result = []
    if provider != "paddle":
        with fitz.open(path) as pdf:
            for number in selected:
                page = pdf[number - 1]
                for region in page.get_text("dict")["blocks"]:
                    for line in region.get("lines", []):
                        text = "".join(span["text"] for span in line["spans"]).strip()
                        if text:
                            result.append(block(text, page=number, bbox=list(line["bbox"]), page_size=[page.rect.width, page.rect.height]))
        if result:
            return result
        if provider == "library" or ocr_settings()["provider"] != "paddle":
            raise ParseError("스캔 PDF OCR은 비활성화되어 있습니다. PARSE_PROVIDER=paddle과 원격 endpoint를 설정해 주세요.")
    subset = _page_pdf(path, selected) if pages else None
    try:
        result = _remote_paddle(subset or path, 0, page_map=selected if subset else None)
    finally:
        if subset:
            subset.unlink(missing_ok=True)
    if not result:
        raise ParseError("PaddleOCR가 스캔 PDF에서 텍스트를 찾지 못했습니다.")
    return result


def parse_image(path, provider="auto"):
    if provider == "library" or (provider == "auto" and ocr_settings()["provider"] != "paddle"):
        raise ParseError("이미지 OCR은 비활성화되어 있습니다. PARSE_PROVIDER=paddle과 원격 endpoint를 설정해 주세요.")
    return _remote_paddle(path, 1)


def _html_table_rows(content):
    if "<table" not in content.lower():
        return None
    parser = _HtmlBlocks()
    parser.feed(content)
    parser.close()
    parser.flush()
    table = next((b for b in parser.blocks if b["type"] == "table"), None)
    return table["rows"] if table else None


def _attach_lines(blocks, encoded, file_type, settings, page_map):
    """Add PP-OCRv5 text line boxes (`block["lines"]`) so grounding can point at a line instead of a whole block.

    The layout pipeline only returns block coordinates; this plain OCR pipeline returns one box per
    text line in the same image coordinates. Each line joins the smallest block containing its center;
    lines outside every block are dropped. A failure here only costs precision, so it is not fatal."""
    started = time.monotonic()
    headers = {"Authorization": f"Bearer {settings['token']}"} if settings["token"] else {}
    try:
        response = httpx.post(f"{settings['lines_url']}/ocr", json={"file": encoded, "fileType": file_type, "visualize": False}, headers=headers, timeout=settings["timeout"])
        response.raise_for_status()
        pages = response.json()["result"]["ocrResults"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning("paddleocr line OCR failed, grounding falls back to block boxes: %s", exc)
        return
    for index, page in enumerate(pages[:len(page_map)] if page_map else pages, 1):
        page_no = page_map[index - 1] if page_map else index
        targets = [b for b in blocks if b["page"] == page_no and b["bbox"]]
        pruned = page.get("prunedResult") or {}
        for text, box in zip(pruned.get("rec_texts") or [], pruned.get("rec_boxes") or []):
            x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            inside = [b for b in targets if b["bbox"][0] <= x <= b["bbox"][2] and b["bbox"][1] <= y <= b["bbox"][3]]
            if inside and str(text).strip():
                smallest = min(inside, key=lambda b: (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1]))
                smallest.setdefault("lines", []).append({"text": str(text), "bbox": [float(v) for v in box]})
    logger.debug("paddleocr line OCR: elapsed=%.2fs pages=%d lines=%d", time.monotonic() - started, len(pages), sum(len(b.get("lines") or []) for b in blocks))


def _ruled_tables(blocks, path, file_type, page_map):
    """Replace the VLM's generated table structure with the printed-rule grid (`table_grid`) where a table has one.

    Needs the OCR lines `_attach_lines` put on each table. Tables without a usable grid, or pages that cannot be
    rendered, keep the VLM structure."""
    tables = [b for b in blocks if b["type"] == "table" and b["bbox"] and b.get("lines") and b.get("page_size")]
    if not tables:
        return
    started = time.monotonic()
    try:
        with fitz.open(path) if file_type == 0 else Image.open(path) as source:
            for page_no in sorted({b["page"] for b in tables}):
                width, height = next(b["page_size"] for b in tables if b["page"] == page_no)
                if file_type == 0:
                    page = source[page_map.index(page_no) if page_map else page_no - 1]
                    pix = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, height / page.rect.height), colorspace=fitz.csGRAY)
                    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                else:
                    image = source.convert("L").resize((round(width), round(height)))
                for table in (b for b in tables if b["page"] == page_no):
                    grid = ruled_table(image, table["bbox"], table["lines"])
                    if grid:
                        rows, spans = grid
                        table.pop("spans", None)
                        table.update(rows=rows, structure="ruled", **({"spans": spans} if spans else {}))
                        table["text"] = _markdown(table, "html")
    except (OSError, ValueError, RuntimeError) as exc:
        logger.warning("ruled table grid skipped, keeping VLM table structure: %s", exc)
        return
    logger.debug("ruled tables: elapsed=%.2fs tables=%d ruled=%d", time.monotonic() - started, len(tables), sum(b.get("structure") == "ruled" for b in tables))


def _remote_paddle(path, file_type, page_map=None):
    settings = ocr_settings()
    if not settings["base_url"]:
        raise ParseError("PaddleOCR 원격 서비스가 설정되지 않았습니다. PADDLEOCR_BASE_URL을 설정해 주세요.")
    endpoint = settings["base_url"]
    if not endpoint.endswith("/layout-parsing"):
        endpoint += "/layout-parsing"
    headers = {"Authorization": f"Bearer {settings['token']}"} if settings["token"] else {}
    encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    payload = {"file": encoded, "fileType": file_type, "visualize": False, "returnMarkdownImages": False}
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
    for index, page in enumerate(pages, 1):
        page_no = page_map[index - 1] if page_map else index
        pruned = page.get("prunedResult") or {}
        size = [pruned["width"], pruned["height"]] if pruned.get("width") and pruned.get("height") else None
        regions = [r for r in pruned.get("parsing_res_list") or [] if str(r.get("block_content") or "").strip()]
        for region in regions:
            bbox = region.get("block_bbox")
            label = region.get("block_label")
            kind = LABEL_TYPES.get(label, "text")
            content = region["block_content"].strip()
            extra = {"label": label}
            if kind == "table":
                rows = _html_table_rows(content)
                if rows is not None:
                    extra["rows"] = rows
            blocks.append(block(content, kind, page=page_no, bbox=list(bbox) if bbox and len(bbox) == 4 else None, page_size=size, source="paddleocr_remote", **extra))
        markdown = page.get("markdown", {})
        text = markdown.get("text") if isinstance(markdown, dict) else None
        if not regions and text and text.strip():
            blocks.append(block(text.strip(), "text", page=page_no, bbox=None, source="paddleocr_remote"))
    if not blocks:
        raise ParseError("PaddleOCR 원격 응답에서 텍스트를 찾지 못했습니다.")
    if settings["lines_url"]:
        _attach_lines(blocks, encoded, file_type, settings, page_map)
        _ruled_tables(blocks, path, file_type, page_map)
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
        self.blocks, self.text, self.rows, self.span, self.skip = [], "", None, (1, 1), 0

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
            attrs = dict(attrs)
            self.text, self.span = "", tuple(int(attrs[name]) if str(attrs.get(name)).isdigit() and int(attrs[name]) > 0 else 1 for name in ("rowspan", "colspan"))
        elif tag in self.BLOCKS:
            self.flush()

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.skip = max(0, self.skip - 1)
        elif tag == "table" and self.rows is not None:
            rows, spans = _grid([row for row in self.rows if row])
            self.rows, self.text = None, ""
            if any(map(any, rows)):
                self.blocks.append(block("\n".join(" | ".join(row) for row in rows), "table", rows=rows, **({"spans": spans} if spans else {})))
        elif self.rows is not None and tag in {"td", "th"} and self.rows:
            self.rows[-1].append((" ".join(self.text.split()), *self.span))
            self.text = ""
        elif self.rows is None and tag in self.BLOCKS:
            self.flush("heading" if tag[0] == "h" and tag[1:].isdigit() else "text")

    def handle_data(self, data):
        if not self.skip:
            self.text += data


def _grid(cells):
    """Lay out rows of (text, rowspan, colspan) on a rectangular grid. A merged cell's text fills every position it
    covers so each row reads on its own; `spans` keeps [row, col, rowspan, colspan] of each merged cell for rendering."""
    grid, spans = {}, []
    for r, row in enumerate(cells):
        c = 0
        for text, rowspan, colspan in row:
            while (r, c) in grid:
                c += 1
            rowspan = min(rowspan, len(cells) - r)
            grid.update({(r + i, c + j): text for i in range(rowspan) for j in range(colspan)})
            if rowspan > 1 or colspan > 1:
                spans.append([r, c, rowspan, colspan])
            c += colspan
    width = max((c + 1 for _, c in grid), default=0)
    return [[grid.get((r, c), "") for c in range(width)] for r in range(len(cells))], spans


def parse_html(path):
    parser = _HtmlBlocks()
    parser.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    parser.close()
    parser.flush()
    return parser.blocks


def _markdown(item, table_format="markdown"):
    rows = item.get("rows")
    if item["type"] == "heading":
        return f"## {item['text']}"
    if item["type"] != "table" or not rows:
        return item["text"]
    if table_format == "html":
        spans = {(r, c): (rowspan, colspan) for r, c, rowspan, colspan in item.get("spans") or []}
        covered = {(r + i, c + j) for (r, c), (rowspan, colspan) in spans.items() for i in range(rowspan) for j in range(colspan)} - spans.keys()
        attrs = lambda rowspan=1, colspan=1: (f' rowspan="{rowspan}"' if rowspan > 1 else "") + (f' colspan="{colspan}"' if colspan > 1 else "")
        return "<table>" + "".join("<tr>" + "".join(f"<td{attrs(*spans.get((r, c), ()))}>{html.escape(cell)}</td>" for c, cell in enumerate(row) if (r, c) not in covered) + "</tr>" for r, row in enumerate(rows)) + "</table>"
    width = max(map(len, rows))
    lines = ["| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in row + [""] * (width - len(row))) + " |" for row in rows]
    return "\n".join([lines[0], "|" + " --- |" * width, *lines[1:]])


def parse(path, filename, media_type, options=None):
    options = options or {}
    pages, provider, table_format = options.get("pages"), options.get("provider", "auto"), options.get("table_format", "markdown")
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        blocks = parse_pdf(path, provider, pages)
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        blocks = parse_image(path, provider)
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
    markdown = separator.join(_markdown(item, table_format) for item in blocks)
    logger.debug("parse: suffix=%s blocks=%d markdown_chars=%d", suffix, len(blocks), len(markdown))
    return markdown, blocks
