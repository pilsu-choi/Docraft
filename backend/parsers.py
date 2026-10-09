import csv
import io
import base64
import hashlib
import html
import json
import logging
import tempfile
import time
import uuid
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
import fitz
import httpx
import numpy as np
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from . import latency
from .config import ai_settings, ocr_settings
from .engine import refine_tables
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


def parse_pdf(path, provider="auto", pages=None, deadline=None):
    with fitz.open(path) as pdf:
        total = len(pdf)
    selected = _pages_from_range(pages, total) if pages else list(range(1, total + 1))
    if not selected:
        raise ParseError("선택한 페이지 범위에 유효한 페이지가 없습니다.")
    result = []
    if provider != "paddle":
        with fitz.open(path) as pdf:
            for number in selected:
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("PDF parse deadline exceeded")
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
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("PDF parse deadline exceeded")
    subset = _page_pdf(path, selected) if pages else None
    try:
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise TimeoutError("PDF parse deadline exceeded")
        result = _remote_paddle(subset or path, 0, page_map=selected if subset else None,
                                expected_pages=len(selected), timeout=remaining, deadline=deadline)
    finally:
        if subset:
            subset.unlink(missing_ok=True)
    if not result:
        raise ParseError("PaddleOCR가 스캔 PDF에서 텍스트를 찾지 못했습니다.")
    return _upright(result, path, 0, deadline)


def parse_image(path, provider="auto", timeout=None, deadline=None):
    if provider == "library" or (provider == "auto" and ocr_settings()["provider"] != "paddle"):
        raise ParseError("이미지 OCR은 비활성화되어 있습니다. PARSE_PROVIDER=paddle과 원격 endpoint를 설정해 주세요.")
    # 이름과 실제 바이트 형식이 다른 스캔도 있으므로 OCR과 표 좌표 계산에
    # 동일하게 디코딩한 프레임을 사용한다. 다중 프레임(TIFF)은 프레임마다 한 쪽이 되도록 PDF로 펼친다.
    try:
        with Image.open(path) as source, tempfile.NamedTemporaryFile(suffix=".pdf" if getattr(source, "n_frames", 1) > 1 else ".png") as normalized:
            frames = [ImageOps.exif_transpose(frame).convert("RGB") for frame in ImageSequence.Iterator(source)]
            frames[0].save(normalized, format="PDF" if len(frames) > 1 else "PNG", save_all=True, append_images=frames[1:], resolution=72.0)
            normalized.flush()
            file_type = 0 if len(frames) > 1 else 1
            blocks = _remote_paddle(normalized.name, file_type, expected_pages=len(frames), timeout=timeout, deadline=deadline)
            return _upright(blocks, normalized.name, file_type, deadline)
    except UnidentifiedImageError:
        # OCR 자체가 지원하는 형식 및 기존 synthetic 호출 계약은 원격 오류에 맡긴다.
        return _remote_paddle(path, 1, expected_pages=1, timeout=timeout, deadline=deadline)


def _html_table(content):
    """`rows` and `spans` of the first table in an HTML fragment; empty when there is none."""
    if "<table" not in content.lower():
        return {}
    parser = _HtmlBlocks()
    parser.feed(content)
    parser.close()
    parser.flush()
    table = next((b for b in parser.blocks if b["type"] == "table"), {})
    return {key: table[key] for key in ("rows", "spans") if key in table}


def _attach_lines(blocks, encoded, file_type, settings, page_map, deadline=None):
    """Add PP-OCRv5 text line boxes (`block["lines"]`) so grounding can point at a line instead of a whole block.

    The layout pipeline only returns block coordinates; this plain OCR pipeline returns one box per
    text line in the same image coordinates. Each line joins the smallest block containing its center;
    lines outside every block are dropped. A failure here only costs precision, so it is not fatal."""
    started = time.monotonic()
    headers = {"Authorization": f"Bearer {settings['token']}"} if settings["token"] else {}
    try:
        response = httpx.post(f"{settings['lines_url']}/ocr", json={"file": encoded, "fileType": file_type, "visualize": False}, headers=headers, timeout=latency.capped(settings["timeout"], deadline))
        response.raise_for_status()
        pages = response.json()["result"]["ocrResults"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning("paddleocr line OCR failed, grounding falls back to block boxes: %s", exc, exc_info=True)
        return
    for index, page in enumerate(pages[:len(page_map)] if page_map else pages, 1):
        page_no = page_map[index - 1] if page_map else index
        targets = [b for b in blocks if b["page"] == page_no and b["bbox"]]
        pruned = page.get("prunedResult") or {}
        texts, boxes = pruned.get("rec_texts") or [], pruned.get("rec_boxes") or []
        for text, box, score in zip(texts, boxes, [*(pruned.get("rec_scores") or []), *[None] * len(texts)]):
            x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            inside = [b for b in targets if b["bbox"][0] <= x <= b["bbox"][2] and b["bbox"][1] <= y <= b["bbox"][3]]
            if inside and str(text).strip():
                smallest = min(inside, key=lambda b: (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1]))
                smallest.setdefault("lines", []).append({"text": str(text), "bbox": [float(v) for v in box], **({"score": float(score)} if score is not None else {})})
    logger.debug("paddleocr line OCR: elapsed=%.2fs pages=%d lines=%d", time.monotonic() - started, len(pages), sum(len(b.get("lines") or []) for b in blocks))


def _ruled_tables(blocks, path, file_type, page_map):
    """Replace the VLM's generated table structure with the printed-rule grid (`table_grid`) where a table has one.

    Needs the OCR lines `_attach_lines` put on each table. Tables without a usable grid, a grid with fewer than half
    the VLM's rows, or pages that cannot be rendered keep the VLM structure."""
    tables = [b for b in blocks if b["type"] == "table" and b["bbox"] and b.get("lines") and b.get("page_size")]
    if not tables:
        return
    started = time.monotonic()
    try:
        for page_no in sorted({b["page"] for b in tables}):
            size = next(b["page_size"] for b in tables if b["page"] == page_no)
            image = _page_image(path, file_type, page_map.index(page_no) if page_map else page_no - 1, size, "L")
            for table in (b for b in tables if b["page"] == page_no):
                grid = ruled_table(image, table["bbox"], table["lines"], with_geometry=True)
                # Faint rules found only in part collapse many rows into a few; the VLM rows are then the better guess.
                if grid and len(grid[0]) * 2 >= len(table.get("rows") or []):
                    rows, spans, cells = grid
                    table.pop("spans", None)
                    table.update(rows=rows, structure="ruled", **({"spans": spans} if spans else {}))
                    table["cells"] = [{**cell, "page": page_no, "page_size": table["page_size"]} for cell in cells]
                    table["text"] = _markdown(table, "html")
    except (OSError, ValueError, RuntimeError) as exc:
        logger.warning("ruled table grid skipped, keeping VLM table structure: %s", exc, exc_info=True)
        return
    logger.debug("ruled tables: elapsed=%.2fs tables=%d ruled=%d", time.monotonic() - started, len(tables), sum(b.get("structure") == "ruled" for b in tables))


def _page_image(path, file_type, index, size, mode):
    """Page `index` (0-based) of a PDF (`file_type` 0) or the image file, rendered at the OCR page `size` in `mode`."""
    width, height = (round(v) for v in size)
    if file_type == 0:
        with fitz.open(path) as pdf:
            page = pdf[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, height / page.rect.height),
                                  colorspace=fitz.csGRAY if mode == "L" else fitz.csRGB, alpha=False)
            return Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    with Image.open(path) as source:
        return source.convert(mode).resize((width, height))


TURNS = (0, 90, 180, 270)


def _otsu(pixels):
    """Otsu threshold of a uint8 array: pixels at or below it are ink."""
    share = np.bincount(pixels.ravel(), minlength=256) / pixels.size
    weight, mean = np.cumsum(share), np.cumsum(share * np.arange(256))
    with np.errstate(divide="ignore", invalid="ignore"):
        return int(np.nanargmax((mean[-1] * weight - mean) ** 2 / (weight * (1 - weight))))


def _baseline_marks(ink):
    """Positions (0 = top, 1 = bottom of the text band) of the small marks — '.', ',' — in one text line that runs along axis 1."""
    rows = ink.sum(1)
    band = np.flatnonzero(rows >= .25 * rows.max()) if rows.any() else []
    if len(band) == 0 or band[-1] - band[0] < 7:
        return []
    top, height = band[0], band[-1] - band[0] + 1
    edges = np.diff(np.concatenate(([0], ink.any(0).astype(np.int8), [0])))
    marks = []
    for start, end in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        hit = np.flatnonzero(ink[:, start:end].any(1))
        low, high = hit[0], hit[-1]
        if (0 < low and high < len(rows) - 1 and end - start <= .35 * height and high - low < .3 * height
                and ink[:, start:end].sum() >= max(4, .01 * height * height)
                and top - .2 * height <= low and high <= top + 1.2 * height):
            marks.append(((low + high) / 2 - top) / (height - 1))
    return marks


def orientation(image, lines):
    """Counter-clockwise turn (PIL ``rotate`` degrees, one of TURNS) that makes the page text upright.

    Periods and commas sit on the baseline in Korean and Latin print alike, so each such mark near one long
    edge of an OCR line box votes for that edge being the bottom; a tall box is text lying on its side. The
    page turns only on a clear majority — anything else keeps it as scanned (0). `_vote` tells "upright" from
    "undecided" apart for `_upright`."""
    return _vote(image, lines) or 0


def _vote(image, lines):
    """The `orientation` turn when the baseline marks give a clear majority (0 = clearly upright), else None."""
    pixels = np.asarray(image.convert("L"))
    votes = dict.fromkeys(TURNS, 0)
    for box in lines:
        left, top, right, bottom = (int(round(v)) for v in box)
        width, height = right - left, bottom - top
        if min(width, height) < 6 or max(width, height) < 2 * min(width, height):
            continue
        crop = pixels[max(0, top):bottom, max(0, left):right]
        if crop.size == 0 or int(crop.max()) - int(crop.min()) < 40:
            continue
        ink = crop <= _otsu(crop)
        tall = height > width
        for mark in _baseline_marks(ink.T if tall else ink):
            if .25 < mark < .75:
                continue
            down = mark >= .75  # the mark sits at the far edge: bottom for a wide box, right for a tall one
            votes[(270 if down else 90) if tall else (0 if down else 180)] += 1
    turn = max(votes, key=votes.get)
    others = sum(votes.values()) - votes[turn]
    return turn if votes[turn] >= 4 and votes[turn] >= 3 * others else None


def _mean_score(blocks):
    """Mean recognition score of the OCR lines with at least two visible characters; None without such lines."""
    scores = [line["score"] for b in blocks for line in b.get("lines") or []
              if "score" in line and len("".join(line["text"].split())) >= 2]
    return sum(scores) / len(scores) if scores else None


def _read_turned(image, turn, deadline):
    """OCR blocks of `image` turned `turn` degrees counter-clockwise (in the turned frame, before `unturn`)."""
    with tempfile.NamedTemporaryFile(suffix=".png") as turned:
        image.rotate(turn, expand=True).save(turned, format="PNG")
        turned.flush()
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise TimeoutError("parse deadline exceeded")
        return _remote_paddle(turned.name, 1, expected_pages=1, timeout=remaining, deadline=deadline)


def _turn_by_score(image, current, boxes, deadline):
    """(turn, blocks read at that turn or None) for a page whose baseline vote was undecided.

    Line box shape picks the family: mostly tall boxes mean text lying on its side ({90, 270}), otherwise {0, 180}.
    The page is read at each candidate turn and the one the OCR recognizes with the higher mean score wins; if any
    compared reading has no scored lines the page is left as scanned."""
    tall = sum(b[3] - b[1] > 1.5 * (b[2] - b[0]) for b in boxes)
    wide = sum(b[2] - b[0] > 1.5 * (b[3] - b[1]) for b in boxes)
    candidates = (90, 270) if tall > wide else (0, 180)
    readings = {turn: current if turn == 0 else _read_turned(image, turn, deadline) for turn in candidates}
    means = {turn: _mean_score(blocks) for turn, blocks in readings.items()}
    if None in means.values():
        return 0, None
    best = max(means, key=means.get)
    return best, readings[best] if best else None


def unturn(blocks, turn):
    """Map blocks read from a page turned by `turn` (counter-clockwise degrees) back to the unturned page.

    Each block's `page_size` is the turned page it was read from; boxes, lines, cells and polygons come back in
    the original frame with the original `page_size`, and `orientation` adds up the turns. A quarter turn keeps a
    deskew `rotation_degrees` valid, because plane rotations commute."""
    mapped = deepcopy(blocks)
    for block in mapped:
        if not turn or not block.get("page_size"):
            continue
        width, height = block["page_size"]
        point = {90: lambda x, y: (height - y, x), 180: lambda x, y: (width - x, height - y),
                 270: lambda x, y: (y, width - x)}[turn]
        size = [height, width] if turn % 180 else [width, height]
        def box(values):
            corners = [point(x, y) for x in (values[0], values[2]) for y in (values[1], values[3])]
            return [min(x for x, _ in corners), min(y for _, y in corners), max(x for x, _ in corners), max(y for _, y in corners)]
        for item in (block, *(block.get("lines") or []), *(block.get("cells") or [])):
            if item.get("polygon"):
                item["polygon"] = [list(point(x, y)) for x, y in item["polygon"]]
                item["bbox"] = [min(x for x, _ in item["polygon"]), min(y for _, y in item["polygon"]),
                                max(x for x, _ in item["polygon"]), max(y for _, y in item["polygon"])]
            elif item.get("bbox"):
                item["bbox"] = box(item["bbox"])
            if "page_size" in item:
                item["page_size"] = size
        block["orientation"] = (block.get("orientation", 0) + turn) % 360
    return mapped


def _upright(blocks, path, file_type, deadline=None):
    """Re-read every page whose text is not upright (`orientation`) from an upright copy.

    The re-read blocks keep the coordinate frame of the file as given (`bbox`, `page_size`) and carry the
    `orientation` turn, so clients and image crops need no change. Without OCR lines nothing is judged; a
    failed re-read keeps the first reading."""
    pages = sorted({b["page"] for b in blocks if b.get("lines") and b.get("page_size")})
    for page_no in pages:
        current = [b for b in blocks if b["page"] == page_no]
        size = next(b["page_size"] for b in current if b.get("page_size"))
        try:
            image = _page_image(path, file_type, page_no - 1, size, "RGB")
            boxes = [line["bbox"] for b in current for line in b.get("lines") or []]
            turn, fresh = _vote(image, boxes), None
            if turn is None and ocr_settings().get("orientation_score") and boxes:
                turn, fresh = _turn_by_score(image, current, boxes, deadline)
            if not turn:
                continue
            logger.info("page %d is turned, re-reading it rotated %d degrees counter-clockwise", page_no, turn)
            fresh = fresh or _read_turned(image, turn, deadline)
        except (ParseError, TimeoutError, OSError, ValueError) as exc:
            logger.warning("upright re-read of page %d failed, keeping the scanned orientation: %s", page_no, exc)
            continue
        fresh = [{**b, "page": page_no} for b in unturn(fresh, turn)]
        for cell in (cell for b in fresh for cell in b.get("cells") or []):
            cell["page"] = page_no
        at = blocks.index(current[0])
        blocks = [*blocks[:at], *fresh, *(b for b in blocks[at:] if b["page"] != page_no)]
    return blocks


def _remote_paddle(path, file_type, page_map=None, expected_pages=None, timeout=None, deadline=None):
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
        with latency.ocr_slot(deadline):  # GPU 레이아웃 모델은 동시 2건에서 포화된다 — 몰리면 줄을 세운다
            budget = min(settings["timeout"], timeout) if timeout is not None else settings["timeout"]
            response = httpx.post(endpoint, json=payload, headers=headers, timeout=latency.capped(budget, deadline))
        response.raise_for_status()
        pages = response.json()["result"]["layoutParsingResults"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.error("paddleocr request failed: status=%s elapsed=%.2fs %s", status, time.monotonic() - started, exc)
        suffix = f" (HTTP {status})" if status else ""
        raise ParseError(f"PaddleOCR 원격 처리 실패{suffix}") from exc
    logger.debug("paddleocr response: elapsed=%.2fs pages=%d", time.monotonic() - started, len(pages))
    if expected_pages is not None and len(pages) != expected_pages:
        raise ParseError(f"PaddleOCR가 {expected_pages}페이지 중 {len(pages)}페이지를 반환했습니다.")
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
            extra = {"label": label, **(_html_table(content) if kind == "table" else {})}
            blocks.append(block(content, kind, page=page_no, bbox=list(bbox) if bbox and len(bbox) == 4 else None, page_size=size, source="paddleocr_remote", **extra))
        markdown = page.get("markdown", {})
        text = markdown.get("text") if isinstance(markdown, dict) else None
        if not regions and text and text.strip():
            blocks.append(block(text.strip(), "text", page=page_no, bbox=None, source="paddleocr_remote"))
        logger.debug("paddleocr page %d/%d: regions=%d elapsed=%.2fs", index, len(pages), len(regions), time.monotonic() - started)
    if not blocks:
        raise ParseError("PaddleOCR 원격 응답에서 텍스트를 찾지 못했습니다.")
    if settings["lines_url"] and (deadline is None or time.monotonic() < deadline):
        _attach_lines(blocks, encoded, file_type, settings, page_map, deadline)
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
    """``(markdown, blocks)``. 원격 OCR(``provider="paddle"``) 결과는 같은 파일·설정의 동시·연이은 요청이 나눠 쓴다(``latency.shared``)."""
    options = options or {}
    if options.get("provider") != "paddle":
        return _parse(path, filename, media_type, options)
    ocr, ai = ocr_settings(), ai_settings()
    key = json.dumps([hashlib.sha256(Path(path).read_bytes()).hexdigest(), Path(filename).suffix.lower(), media_type,
                      [options.get("pages"), options.get("table_format"), options.get("refine_tables", True)],
                      [ocr[name] for name in ("base_url", "lines_url", "model")],
                      [ai[name] for name in ("mode", "base_url", "model", "vision", "table_refine", "reasoning")]])
    return latency.shared(key, lambda: _parse(path, filename, media_type, options), options.get("deadline"))


def _parse(path, filename, media_type, options):
    pages, provider, table_format = options.get("pages"), options.get("provider", "auto"), options.get("table_format", "markdown")
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        blocks = parse_pdf(path, provider, pages, options.get("deadline"))
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}:
        blocks = parse_image(path, provider, options.get("timeout"), options.get("deadline"))
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
    tables = [item for item in blocks if options.get("refine_tables", True) and item["type"] == "table" and item.get("source") == "paddleocr_remote"]
    with latency.timed("refine_ms"):
        refined = refine_tables(tables, path, options.get("deadline")) if tables else []
    for item, text in zip(tables, refined):
        if text:
            # Refinement edits HTML cell text without updating OCR cell witnesses; do not reuse stale typed proof.
            item.pop("cells", None)
            item.update(text=text, **_html_table(text))
    separator = "\n" if suffix in {".pdf", ".txt", ".md"} else "\n\n"
    markdown = separator.join(_markdown(item, table_format) for item in blocks)
    logger.debug("parse: suffix=%s blocks=%d markdown_chars=%d", suffix, len(blocks), len(markdown))
    return markdown, blocks
