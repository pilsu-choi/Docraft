import csv
import io
import base64
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
import fitz
import httpx

from .config import ocr_settings


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
    try:
        response = httpx.post(endpoint, json=payload, headers=headers, timeout=settings["timeout"])
        response.raise_for_status()
        pages = response.json()["result"]["layoutParsingResults"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        suffix = f" (HTTP {status})" if status else ""
        raise ParseError(f"PaddleOCR 원격 처리 실패{suffix}") from exc
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
    elif suffix in {".txt", ".md"} or media_type.startswith("text/"):
        blocks = parse_text(path)
    else:
        raise ParseError(f"지원하지 않는 파일 형식입니다: {suffix or media_type}")
    if not blocks:
        raise ParseError("문서에서 내용을 찾지 못했습니다.")
    separator = "\n" if suffix == ".pdf" else "\n\n"
    markdown = separator.join(b["text"] if b["type"] != "table" else f"```text\n{b['text']}\n```" for b in blocks)
    return markdown, blocks
