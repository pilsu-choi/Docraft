import base64
import difflib
import html
import json
import logging
import os
import re
import time
from collections import Counter
from copy import deepcopy
from itertools import groupby
from pathlib import Path

import fitz
import httpx
from PIL import Image
from jsonschema import Draft202012Validator

from .config import ai_settings, limit
from . import doctypes, table_layout
from .latency import note, parallel, remaining

logger = logging.getLogger(__name__)

VISION_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
VISION_MAX_IMAGES = 4  # Page images per provider call.
VISION_MAX_EDGE = 2000  # Longest side of an attached page image, in pixels.
VISION_SCHEMA_PAGES = [1, 2]  # Pages taken from each reference document when generating a schema.
VISION_NOTE = (
    " The page image is attached: read the table structure (merged cells, column headers) from the image, "
    "and use the OCR text only as a spelling aid."
)
TABLE_NOTE = (  # Only for schemas with a table field: rows must be evidence, not recall.
    " Table rows are evidence, not recall: return exactly the rows the document prints, in printed order, "
    "and never add a row the document does not print. Keep the item name the document prints even when it is "
    "not one of the standard names you know."
)


class ProviderConfigurationError(RuntimeError):
    pass


def _message_text(content):
    """The text of a message; attached image data stays out of logs and character counts."""
    return "".join(part.get("text", "") for part in content) if isinstance(content, list) else content or ""


def _data_url(page, clip=None, max_zoom=2.0, turn=0):
    """One rendered page (or its `clip` region) as a base64 JPEG data URL, scaled so its longest side stays within
    VISION_MAX_EDGE and turned `turn` degrees counter-clockwise (the parser's `orientation`) so the text is upright."""
    area = clip or page.rect
    zoom = min(VISION_MAX_EDGE / max(area.width, area.height), max_zoom)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom).prerotate(-turn), clip=clip, alpha=False)
    return "data:image/jpeg;base64," + base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=90)).decode()


def _turns(blocks):
    """page → `orientation` of the blocks the parser read from a turned page."""
    return {b["page"]: b["orientation"] for b in blocks if b.get("orientation")}


def _page_images(source, pages, turns=None, clips=None):
    """Page images of the document file `source` for the given 1-based page numbers (the same numbering the
    parser puts on blocks), each turned upright by `turns` (page → `orientation`). Empty when vision is off, the
    format has no page image (docx/xlsx/csv/txt/html), or rendering fails — the call then falls back to the OCR text alone.
    `clips` (boxes as page fractions [x0, y0, x1, y1] of the first page, e.g. a row band of `_bands`) attach those regions
    of that page instead, at up to twice the whole-page zoom: a strip is smaller than the page."""
    if not source or not ai_settings()["vision"] or Path(source).suffix.lower() not in VISION_SUFFIXES:
        return []
    pages = list(pages)
    if len(pages) > VISION_MAX_IMAGES:
        logger.warning("vision: %d pages exceed the %d image limit, attaching the first %d", len(pages), VISION_MAX_IMAGES, VISION_MAX_IMAGES)
        pages = pages[:VISION_MAX_IMAGES]
    try:
        with fitz.open(source) as document:
            if clips:
                page, turn = document[pages[0] - 1], (turns or {}).get(pages[0], 0)
                width, height = page.rect.width, page.rect.height
                return [_data_url(page, fitz.Rect(x0 * width, y0 * height, x1 * width, y1 * height) & page.rect, 4.0, turn)
                        for x0, y0, x1, y1 in clips]
            return [_data_url(document[number - 1], turn=(turns or {}).get(number, 0)) for number in pages if 1 <= number <= len(document)]
    except Exception as exc:
        logger.warning("vision: page image rendering failed for %s: %s", Path(source).name, exc, exc_info=True)
        return []


def _user(text, images):
    """A user message; attached page images turn its content into the OpenAI content array."""
    if not images:
        return {"role": "user", "content": text}
    return {"role": "user", "content": [*({"type": "image_url", "image_url": {"url": url}} for url in images), {"type": "text", "text": text}]}


def _provider(messages, timeout=None, timeout_cap=None, json_schema=None, max_tokens=None):
    # 호출마다 준 값과 AI_TIMEOUT(기본 90초) 중 큰 값 — 느린 GPU(L40S 요청당 약 16 tok/s)에서는 긴 응답(스키마 생성·
    # 행 많은 표)이 90초를 넘는다.
    timeout = max(timeout or 0, float(os.getenv("AI_TIMEOUT", "90")))
    if timeout_cap is not None:
        timeout = min(timeout, max(0.1, timeout_cap))
    settings = ai_settings()
    if not settings["configured"] or settings["mode"] == "local":
        raise ProviderConfigurationError("AI provider가 설정되지 않았습니다. AI_BASE_URL, AI_API_KEY, AI_VLM_MODEL을 확인해 주세요.")
    body = {"model": settings["model"], "messages": messages, "temperature": 0, "response_format": {"type": "json_object"}}
    if json_schema is not None:
        # The server constrains the reply to the schema (vLLM structured outputs, OpenRouter json_schema). OpenRouter routes
        # only to providers honoring it (require_parameters); none of those for qwen3-vl takes `reasoning`, so it is left
        # out (an instruct model has no reasoning mode). vLLM ignores the unknown `provider` field.
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "response", "schema": json_schema}}
        body["provider"] = {"require_parameters": True}
    elif not settings["reasoning"]:
        # OpenRouter standard param; providers/models without reasoning support just ignore it.
        body["reasoning"] = {"enabled": False}
    if max_tokens:
        body["max_tokens"] = max_tokens
    prompt_chars = sum(len(_message_text(m.get("content"))) for m in messages)
    images = sum(1 for m in messages if isinstance(m.get("content"), list) for part in m["content"] if part.get("type") == "image_url")
    logger.debug("provider call: model=%s messages=%d images=%d prompt_chars=%d", settings["model"], len(messages), images, prompt_chars)
    started = time.monotonic()
    with httpx.Client(timeout=timeout, transport=httpx.HTTPTransport(retries=0 if timeout_cap is not None else 2)) as client, \
            client.stream("POST", f"{settings['base_url']}/chat/completions", headers={"Authorization": f"Bearer {settings['api_key']}"}, json=body) as response:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("provider HTTP error: status=%s elapsed=%.2fs", response.status_code, time.monotonic() - started)
            raise RuntimeError(f"AI provider 요청 실패 (HTTP {response.status_code})") from exc
        # httpx timeout은 바이트 사이 간격만 잰다. OpenRouter는 응답 전까지 keep-alive 공백을 흘려 보내므로 시한은 직접 잰다.
        raw = b""
        for chunk in response.iter_bytes():
            raw += chunk
            if timeout_cap is not None and time.monotonic() - started > max(0.1, timeout_cap):
                raise TimeoutError("AI provider 응답이 요청 시한을 넘었습니다.")
        elapsed = time.monotonic() - started
        try:
            choice = json.loads(raw)["choices"][0]
            finish_reason = choice.get("finish_reason")
            if finish_reason == "length":
                logger.warning("provider response truncated: finish_reason=length elapsed=%.2fs", elapsed)
                raise RuntimeError("AI provider 응답이 토큰 제한으로 잘렸습니다.")
            content = choice["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            logger.error("provider response format error: %s elapsed=%.2fs", exc, elapsed)
            raise RuntimeError("AI provider 응답 형식을 해석할 수 없습니다.") from exc
        logger.debug("provider response: elapsed=%.2fs finish_reason=%s len=%d", elapsed, finish_reason, len(content))
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error("provider json decode failed: len=%d finish_reason=%s tail=%r", len(content), finish_reason, content[-200:])
            raise


TABLE_CELL = re.compile(r"(<t[dh][^>]*>)(.*?)(</t[dh]>)", re.S)
TABLE_REFINE_PROMPT = (
    "The image is a table. Below is a JSON object of its cells keyed by cell number in reading order (row by row, left to right), "
    "transcribed by an OCR model that sometimes misreads Korean characters, digits and vertical text, and leaves LaTeX or literal \\n noise. "
    "Compare every cell with the image and return {\"corrections\": {cell number: corrected text}} for the cells whose text is wrong. "
    "Keep each cell as one cell even if it looks merged; leave correct cells out.\n\n"
)


TABLE_PART_NOTE = "These are only some rows of the table; cell numbers count over the whole table. "


def _row_parts(text, cells, max_cells):
    """Split the sendable `cells` ({cell number: text}) into consecutive whole-row groups of at most `max_cells` cells.

    Cell numbers keep counting over the whole table, so corrections from every group merge back unchanged. A row larger
    than `max_cells` stays whole; `max_cells` 0 or an HTML without <tr> rows sends the table as one group."""
    widths = [len(TABLE_CELL.findall(row)) for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S)]
    if not max_cells or len(cells) <= max_cells or sum(widths) != len(TABLE_CELL.findall(text)):
        return [cells]
    parts, start = [{}], 0
    for width in widths:
        row = {index: cells[index] for index in range(start, start + width) if index in cells}
        if parts[-1] and len(parts[-1]) + len(row) > max_cells:
            parts.append({})
        parts[-1].update(row)
        start += width
    return [part for part in parts if part]


def refine_tables(blocks, source, deadline=None):
    """Correct the cell text of OCR table HTML blocks against the table region of the page image (`TABLE_REFINE`).

    The OCR model keeps a sound grid but misreads text; a larger VLM reads text well but loses the grid. So the model
    only returns corrections keyed by cell number and unknown numbers are ignored: the grid never changes. Every table,
    and every `REFINE_MAX_CELLS` row group of a large table (the call time grows with the cell count), is one provider call;
    up to `REFINE_CONCURRENCY` calls run at once. Returns the corrected HTML per block, None where refinement is off,
    unavailable, failed or found nothing to correct. Raises TimeoutError once `deadline` has passed."""
    settings = ai_settings()
    if not settings["table_refine"] or not settings["configured"] or settings["mode"] == "local":
        return [None] * len(blocks)
    max_cells = limit("REFINE_MAX_CELLS", 300, 100000)
    texts, calls = {}, []
    try:
        with fitz.open(source) as document:
            for number, block in enumerate(blocks):
                if not block.get("bbox") or not block.get("page_size"):
                    continue
                # Cells holding markup (a seal or drug photo <img>) stay out: models blank them or write text into them.
                texts[number] = {index: html.unescape(cell) for index, (_, cell, _) in enumerate(TABLE_CELL.findall(block["text"])) if "<" not in cell}
                page = document[(block["page"] or 1) - 1]
                scale = page.rect.width / block["page_size"][0]  # OCR image pixels -> page points
                clip = fitz.Rect([value * scale for value in block["bbox"]]) & page.rect
                image = _data_url(page, clip, max_zoom=1 / scale, turn=block.get("orientation", 0))  # no upscaling beyond the OCR resolution; upright like the re-read page
                parts = _row_parts(block["text"], texts[number], max_cells)
                calls += [(number, image, part, len(parts) > 1) for part in parts]
    except Exception as exc:
        logger.warning("table refine skipped, keeping OCR text: %s", exc, exc_info=True)
        return [None] * len(blocks)

    def correct(call):
        number, image, cells, partial = call
        started = time.monotonic()
        try:
            messages = [_user(TABLE_REFINE_PROMPT + (TABLE_PART_NOTE if partial else "") + json.dumps(cells, ensure_ascii=False), [image])]
            reply = _provider(messages, timeout=300) if deadline is None else _provider(messages, timeout=300, timeout_cap=remaining(deadline))
            reply = reply.get("corrections", reply)  # models also answer with the bare {cell number: text} object
            fixed = {index: str(reply[str(index)]) for index, text in cells.items() if str(index) in reply and _edit(text, str(reply[str(index)]))}
        except Exception as exc:
            logger.warning("table refine failed, keeping OCR text: %s", exc, exc_info=True)
            return {}
        logger.info("table refine: page=%s cells=%d changed=%d elapsed=%.2fs", blocks[number]["page"], len(cells), len(fixed), time.monotonic() - started)
        return fixed

    corrections = {}
    for (number, *_), fixed in zip(calls, parallel(correct, calls, limit("REFINE_CONCURRENCY", 4, 32))):
        corrections.setdefault(number, {}).update(fixed)
    remaining(deadline)  # a call cut by the deadline must not leave a half-refined result behind as if it were complete
    result = []
    for number, block in enumerate(blocks):
        fixed = corrections.get(number)
        if not fixed:
            result.append(None)
            continue
        index = iter(range(len(TABLE_CELL.findall(block["text"]))))
        result.append(TABLE_CELL.sub(lambda m: m[1] + (html.escape(fixed[i], quote=False) if (i := next(index)) in fixed else m[2]) + m[3], block["text"]))
    return result


def _edit(old, new):
    """A table correction must edit the OCR text, not blank, invent or replace it: otherwise models move text between cells."""
    return old != new and bool(old.strip()) and bool(new.strip()) and (max(len(old), len(new)) <= 3 or difflib.SequenceMatcher(None, old, new).ratio() >= 0.5)


def _field_name(label):
    name = re.sub(r"[^a-zA-Z0-9가-힣]+", "_", label.strip()).strip("_").lower()
    return name or "field"


def generate_schema(prompt, document_text="", images=()):
    logger.debug("generate_schema: mode=%s prompt_chars=%d doc_chars=%d images=%d", ai_settings()["mode"], len(prompt), len(document_text), len(images))
    if ai_settings()["mode"] != "local":
        system = (
            "Return only a JSON object containing a practical JSON Schema draft 2020-12. Include title, type object, properties and required. "
            "Use nested objects and arrays when the request or document implies them. "
            "Every property, including nested and array item properties, must have a title and a description that explains what to extract and in which format. "
            "Write titles and descriptions in Korean first; keep other languages only for proper nouns, codes or units. Property keys stay short snake_case identifiers."
        )
        if images:
            system += (
                " The page images are attached: follow the real column header structure shown there (merged headers included), "
                "giving every value column its own field, and never turn a column into a boolean flag."
            )
        generated = _provider([{"role": "system", "content": system}, _user(f"Request:\n{prompt}\n\nDocument sample:\n{document_text[:12000]}", images)])
        generated.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
        return generated
    terms = re.split(r"[,，、\n]|(?:와|과|및|그리고)|\band\b", prompt, flags=re.I)
    properties = {}
    for term in terms:
        label = re.sub(r"(추출|해줘|해주세요|필드|정보|이 문서에서|이 문서의)", "", term).strip(" .")
        if not label:
            continue
        lowered = label.lower()
        kind = "number" if any(word in lowered for word in ("amount", "total", "price", "금액", "합계", "가격")) else "string"
        properties[_field_name(label)] = {"type": kind, "title": label, "description": f"문서의 {label}"}
    if not properties and document_text:
        for label in re.findall(r"(?m)^\s*([^:\n]{2,40})\s*:", document_text)[:12]:
            properties[_field_name(label)] = {"type": "string", "title": label.strip(), "description": f"문서의 {label.strip()}"}
    if not properties:
        properties["value"] = {"type": "string", "title": "값", "description": "문서에서 추출할 값"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Generated schema", "type": "object", "properties": properties, "required": list(properties)}


def generate_schema_from_documents(prompt, docs):
    text = "\n\n".join(f"Document {doc['filename']}:\n{doc.get('markdown') or ''}" for doc in docs)
    if ai_settings()["mode"] == "local":
        return generate_schema(prompt, text)
    images = [url for doc in docs for url in _page_images(doc.get("file_path"), VISION_SCHEMA_PAGES)][:VISION_MAX_IMAGES]
    return generate_schema(prompt or "Infer useful structured fields from these parsed documents.", text, images)


def _coerce(value, schema):
    value = value.strip()
    kind = schema.get("type")
    try:
        if kind == "integer": return int(re.sub(r"[^\d.-]", "", value))
        if kind == "number": return float(re.sub(r"[^\d.-]", "", value))
        if kind == "boolean": return value.lower() in {"true", "yes", "y", "1", "예", "네"}
    except ValueError:
        return value
    return value


def _local_extract(schema, blocks):
    text = "\n".join(b["text"] for b in blocks)
    result, groundings = {}, {}
    for name, spec in schema.get("properties", {}).items():
        labels = [name.replace("_", " "), spec.get("title", ""), spec.get("description", "")]
        match = None
        source = None
        for candidate in filter(None, labels):
            pattern = rf"(?im)(?:^|\n|\|)\s*{re.escape(candidate)}\s*[:：|]\s*([^\n|]+)"
            match = re.search(pattern, text)
            if match:
                source = next((b for b in blocks if match.group(0).strip() in b["text"] or match.group(1).strip() in b["text"]), None)
                break
        if match:
            result[name] = _coerce(match.group(1), spec)
            groundings[name] = {"confidence": 0.82, "page": source.get("page") if source else None, "bbox": source.get("bbox") if source else None, "source_text": match.group(0).strip()}
        elif spec.get("type") == "object":
            child, child_ground = _local_extract(spec, blocks)
            result[name], groundings[name] = child, child_ground
        elif spec.get("type") == "array":
            items = spec.get("items", {})
            rows_result, rows_grounding = [], {}
            if items.get("type") == "object":
                fields = items.get("properties", {})
                for source in (b for b in blocks if b.get("rows") and len(b["rows"]) > 1):
                    headers = [str(value).strip().lower() for value in source["rows"][0]]
                    mapping = {}
                    for field, child_spec in fields.items():
                        labels = {field.lower(), field.replace("_", " ").lower(), child_spec.get("title", "").lower()}
                        index = next((i for i, header in enumerate(headers) if header in labels), None)
                        if index is not None: mapping[field] = index
                    if mapping:
                        for row_no, row in enumerate(source["rows"][1:]):
                            item = {field: _coerce(str(row[index]), fields[field]) if index < len(row) and str(row[index]).strip() else None for field, index in mapping.items()}
                            if any(value is not None for value in item.values()):
                                index = len(rows_result); rows_result.append(item)
                                rows_grounding[str(index)] = {field: {"confidence": 0.84, "page": source.get("page"), "bbox": source.get("bbox"), "source_text": str(row[column])} for field, column in mapping.items() if column < len(row)}
                        break
            result[name] = rows_result
            groundings[name] = rows_grounding or {"confidence": 0, "page": None, "bbox": None, "source_text": None}
        else:
            result[name], groundings[name] = None, {"confidence": 0, "page": None, "bbox": None, "source_text": None}
    return result, groundings


def _page_chunks(blocks, budget=40000):
    """Group blocks into chunks of whole pages whose serialized text fits the budget, keeping page boundaries and block order.
    A page that alone exceeds the budget is split at block boundaries; a single block that alone exceeds the budget
    becomes its own chunk (truncated later when serialized)."""
    pages = [list(group) for _, group in groupby(blocks, key=lambda b: b.get("page"))]
    chunks, current, current_len = [], [], 0
    for page_blocks in pages:
        page_len = sum(len(b["text"]) + 1 for b in page_blocks)
        if page_len > budget:
            if current:
                chunks.append(current)
                current, current_len = [], 0
            sub, sub_len = [], 0
            for block in page_blocks:
                block_len = len(block["text"]) + 1
                if sub and sub_len + block_len > budget:
                    chunks.append(sub)
                    sub, sub_len = [], 0
                sub.append(block)
                sub_len += block_len
            if sub:
                chunks.append(sub)
        elif current_len + page_len > budget:
            chunks.append(current)
            current, current_len = list(page_blocks), page_len
        else:
            current.extend(page_blocks)
            current_len += page_len
    if current:
        chunks.append(current)
    return chunks


def _chunk_text(chunk_blocks, budget):
    """Serialize a chunk's block texts as lines; truncates only the pathological case of a single block over budget."""
    text = "\n".join(b["text"] for b in chunk_blocks)
    if len(text) > budget:
        logger.warning("extract: chunk still exceeds budget after page split, truncating (%d > %d chars, blocks=%d)", len(text), budget, len(chunk_blocks))
        text = text[:budget]
    return text


def _pages(chunk_blocks):
    return sorted({b.get("page") for b in chunk_blocks if b.get("page") is not None})


def _page_range(chunk_blocks):
    pages = _pages(chunk_blocks)
    if not pages:
        return "unknown"
    return f"{pages[0]}-{pages[-1]}" if pages[0] != pages[-1] else str(pages[0])


def _merge_chunk_results(results, schema):
    """Merge per-chunk extraction results by schema: object recurses per key, array concatenates in chunk
    order (dropping an exact duplicate item at a chunk boundary), scalar keeps the first non-null value."""
    kind = schema.get("type")
    if kind == "object":
        merged = {}
        for key, sub_schema in schema.get("properties", {}).items():
            values = [r.get(key) if isinstance(r, dict) else None for r in results]
            merged[key] = _merge_chunk_results(values, sub_schema)
        return merged
    if kind == "array":
        items = []
        for r in results:
            if not isinstance(r, list):
                continue
            chunk_items = r[1:] if r and items and r[0] == items[-1] else r
            items.extend(chunk_items)
        return items
    return next((value for value in results if value is not None), None)


def _same_row(a, b):
    """True when `a` and `b` are two reads of the row a band repeats (`_bands`): the amount-like values (two at least: one
    shared date or count says nothing) of one are all among the other's, whatever columns the two reads put them in."""
    one, other = sorted((Counter(_normalized(v) for v in row.values() if ROW_AMOUNT.fullmatch(str(v).strip())) for row in (a, b)),
                        key=lambda values: values.total())
    return one.total() >= 2 and not one - other


def _drop_null_optionals(value, schema):
    """Remove leaves the model filled with null for optional fields, per the original schema."""
    if isinstance(value, dict) and schema.get("type") == "object":
        required, props = set(schema.get("required", [])), schema.get("properties", {})
        for key, sub in list(value.items()):
            types = props.get(key, {}).get("type")
            allows_null = types is None or types == "null" or (isinstance(types, list) and "null" in types)
            if sub is None and key not in required and not allows_null:
                del value[key]
            else:
                _drop_null_optionals(sub, props.get(key, {}))
    elif isinstance(value, list) and schema.get("type") == "array":
        for item in value:
            _drop_null_optionals(item, schema.get("items", {}))
    return value


ROWS_SYSTEM = (  # rowmajor table reading: one value array per row, field i always at position i.
    "You will be given a document image and, in the user message, a table to find and a list of fields (in a fixed order) "
    "to use for every row of that table.\n\nOutput rules:\n"
    "- Output one array per data row (exclude header/title rows) — never a JSON object keyed by field name.\n"
    "- Each row array must have exactly as many values as fields given, in that exact position order. Position i in every "
    "row array is always field i from the list — never output field names, only values, and never reorder them. If a cell "
    "is empty, put null at that position — never skip or shorten the array.\n"
    "- Default: copy each value as shown in the document. Exception: if a position's own field description (given in the "
    "user message) requires a specific format or exclusion (e.g. a date format, dropping a foreign-script gloss or a "
    "parenthetical annotation), write the value in that format instead. This changes formatting only — never which row a "
    "value belongs to, never its position. Unsure whether the description applies? Copy raw. Emit rows top-to-bottom in "
    "the same order they appear in the image. Stop once you reach the last data row — do not pad with extra empty rows, "
    "invent rows, or repeat rows.\n"
    "- A subtotal or grand-total row (its first column reads e.g. 소계, 합계, 계, or 끝수처리금액/끝처리 조정금액) is still a "
    "data row — output it too, in its place in the top-to-bottom order, even though most of its other cells are blank and "
    "only a label plus one or two totals are filled in. This applies whether it sits between item groups or as the very "
    "last row of the table — do not treat it as a footer and stop before it."
)
ROWS_USER = (
    "Reference OCR text (extracted separately from this document by a different OCR system; it may contain OCR errors or "
    "misaligned columns — the image is still the primary source of truth for structure and cell values, but use this text "
    "to double-check that you have not missed or duplicated any row):\n[[SOURCE_START]]\n{evidence}\n[[SOURCE_END]]\n\n"
    "Find and transcribe this table: {table} — {description}\n"
    "Fields, in the exact order you must use for every row (do not reorder, rename, invent, or translate):\n{fields}\n\n"
    "Position order: {order}.\n\nExtract this table now."
)


TABLE_REPLY_TOKENS = 16000  # Reply cap a page group of one table aims under: half the provider output limit (32k).
PAGES_NOTE = (" These are page(s) {pages} of a table printed over page(s) {span}: read only the rows printed on these pages. "
              "A continuation page may have no header row; the fields above still give its columns in printed order.")
BAND_NOTE = (" The image shows only a horizontal strip of this table: transcribe only the rows in it.",
             " The first image is only the table's header (no rows to output); the second image is a horizontal strip of "
             "this table: transcribe only the rows in it.")
ROW_AMOUNT = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?![\d,])|(?<![\d.,])\d{3,}(?![\d.,])")  # 금액 꼴 숫자('12,300'·'4500')


def _reply_cap(evidence, columns):
    """Output token cap of a rowmajor reply: (amount-like numbers in the OCR evidence + 20) rows × (10 tokens per column + 20).
    Every printed row carries an amount, and saved replies use at most half of it."""
    return (len(ROW_AMOUNT.findall(evidence)) + 20) * (10 * columns + 20)


def _read_rows(table, spec, plan, evidence, images, part="", deadline=None, cancel=None, on_call=None):
    """One table as positional rows (`TABLE_EXTRACT=rowmajor`): the model writes each row as a value array in the column
    order of `plan` (`table_layout.plan`: printed columns read from the document; the schema's column order when it is None),
    and the values go back under the schema's column keys. Raises RuntimeError when the reply has no row or a row of the
    wrong length.

    The reply is capped at `_reply_cap`: a longer reply repeats rows, so it stops at the cap (finish_reason=length →
    RuntimeError) and the table is read asis instead of looping to the provider limit."""
    union = {key: prop.get("description", "") for key, prop in spec["items"]["properties"].items()}
    description, columns, fill = plan or (spec.get("description", ""), union, None)
    names = list(columns)
    if cancel is not None and cancel.is_set():
        raise RuntimeError("extraction cancelled")
    if on_call is not None:
        on_call()
    prompt = ROWS_USER.format(evidence=evidence, table=table, description=description + part,
                              fields="\n".join(f"{index}. {key}: {text}" for index, (key, text) in enumerate(columns.items(), 1)),
                              order=", ".join(f"{index}={key}" for index, key in enumerate(names, 1)))
    row = {"type": "array", "minItems": len(names), "maxItems": len(names), "items": {"type": ["string", "null"]}}
    reply = _provider([{"role": "system", "content": ROWS_SYSTEM}, _user(prompt, images)], timeout_cap=remaining(deadline),
                      json_schema={"type": "object", "properties": {"rows": {"type": "array", "items": row}}, "required": ["rows"]},
                      max_tokens=_reply_cap(evidence, len(names)))
    rows = reply.get("rows") if isinstance(reply, dict) else None
    if not rows or not all(isinstance(values, list) and len(values) == len(names) for values in rows):
        raise RuntimeError(f"rowmajor 응답의 행이 없거나 열 수({len(names)})가 맞지 않습니다.")
    logger.info("extract: rowmajor table=%s columns=%d planned=%s rows=%d", table, len(names), plan is not None, len(rows))
    return [{key: dict(zip(names, values)).get(key, fill) for key in union} for values in rows]


def _table_plan(doc_type, table, spec, blocks):
    """The table's column plan (`table_layout.plan`) for the whole document. Each page is planned from its own blocks (pages
    share coordinates, so mixing them blurs the header), and the plan most pages agree on wins (ties: more columns, then the
    earlier page): a long table repeats one printed header, and a page whose header OCR misread a word or carries no header
    (a continuation page) reads with the same plan as the others."""
    union = {key: prop.get("description", "") for key, prop in spec["items"]["properties"].items()}
    pages = [table_layout.planned(doc_type, table, list(group), spec.get("description", ""), union)
             for _, group in groupby(blocks, key=lambda b: b.get("page"))]
    plans = [plan for plan, *_ in pages if plan]
    best = max(plans, key=lambda plan: (plans.count(plan), len(plan[1])), default=None)
    source, reason = next(((source, reason) for plan, source, reason, _ in pages if plan == best), ("union", None))
    note("table_plan", source, add=False)  # 운영 지표: 열 배치 출처와 머리글을 못 읽은 사유(첫 쪽)
    note("table_plan_reason", reason or next((reason for _, _, reason, _ in pages if reason), None), add=False)
    # 근거가 약해 추측하지 않은 열(table_layout.planned 알림): 고른 배치를 낸 쪽들의 것
    note("table_plan_flags", sorted({tuple(flag) for plan, _, _, flags in pages if plan == best for flag in flags}) or None, add=False)
    return best


def _table_pages(blocks, budget, columns):
    """Consecutive whole pages grouped for reading one table so that each group's reply cap (`_reply_cap`) stays within
    TABLE_REPLY_TOKENS, its text within the chunk budget and its pages within VISION_MAX_IMAGES. A page whose reply cap
    alone is over the provider output limit (2 × TABLE_REPLY_TOKENS: its reply may not fit one call) is cut into row bands
    (`_bands`), each its own group; any other page over the limits, or one that cannot be cut, is its own group."""
    groups = []
    for _, group in groupby(blocks, key=lambda b: b.get("page")):
        group = list(group)
        if _reply_cap("\n".join(b["text"] for b in group), columns) > 2 * TABLE_REPLY_TOKENS and (bands := _bands(group, columns)):
            groups += [[band] for band in bands]
            continue
        last = groups[-1] if groups else None
        if (last and "clips" not in last[0] and len(_pages(last)) < VISION_MAX_IMAGES
                and len(text := "\n".join(b["text"] for b in last + group)) <= budget
                and _reply_cap(text, columns) <= TABLE_REPLY_TOKENS):
            last.extend(group)
        else:
            groups.append(group)
    return groups


def _line_rows(lines):
    """OCR lines grouped into printed text rows top to bottom, each (top, bottom, its lines' text left to right joined by
    ' | '): a line whose middle lies above the bottom of a row's first line joins that row. Lines over twice the median line
    height (a merged cell's text across rows) are left out of the rows and returned second."""
    heights = sorted(line["bbox"][3] - line["bbox"][1] for line in lines)
    tall = [line for line in lines if line["bbox"][3] - line["bbox"][1] > 2 * heights[len(heights) // 2]]
    rows = []
    for line in sorted((line for line in lines if line not in tall), key=lambda line: line["bbox"][1] + line["bbox"][3]):
        top, bottom = line["bbox"][1], line["bbox"][3]
        if rows and (top + bottom) / 2 <= rows[-1][1]:
            rows[-1][2] = max(rows[-1][2], bottom)
            rows[-1][3].append(line)
        else:
            rows.append([top, bottom, bottom, [line]])
    return [(top, bottom, " | ".join(line["text"] for line in sorted(parts, key=lambda line: line["bbox"][0])))
            for top, _, bottom, parts in rows], tall


def _bands(page_blocks, columns):
    """Row bands of a page too dense for one reply. Each table block's OCR text rows (`_line_rows`) from its first row
    carrying an amount (the rows above are its header) are cut into the fewest bands of about equal amount count whose
    reply cap (`_reply_cap`) stays within TABLE_REPLY_TOKENS. A cut falls in the gap between two text rows, before a row
    carrying an amount (a printed row's amounts are on its first line; a wrapped name line has none), and the next band
    repeats the band's last printed row (from its last text row carrying an amount) so a row cut anyway is whole in one
    band (`repeats`); `extract` keeps one of the two reads (`_same_row`). A band is a block with the header rows, its rows and the merged-cell lines it overlaps as text, and
    `clips` (page fractions): the header strip (bands after the first) and the band strip, both table-wide.
    Empty when a table block has no OCR line boxes or no block needs cutting (its lines carry fewer amounts than the page
    text): the page is then read whole."""
    from .parsers import unturn  # parsers → engine 순환을 피한다
    tables = [b for b in page_blocks if b.get("type") == "table"]
    if not tables or not all(b.get("page_size") and any(line.get("bbox") for line in b.get("lines") or []) for b in tables):
        return []
    most = max(1, TABLE_REPLY_TOKENS // (10 * columns + 20) - 20)  # amounts a band's reply cap allows
    bands = []
    for block in tables:
        turn = block.get("orientation", 0)
        upright = unturn([block], 360 - turn)[0] if turn else block
        rows, tall = _line_rows([line for line in upright["lines"] if line.get("bbox") and str(line["text"]).strip()])
        amounts = [len(ROW_AMOUNT.findall(row[2])) for row in rows]
        head = next((i for i, count in enumerate(amounts) if count), 0)
        target = -(-sum(amounts) // -(-sum(amounts) // most)) if sum(amounts) else 0  # 고른 띠 크기
        x0, y0, x1, y1 = upright["bbox"]

        def cut(i):
            return y0 if i == 0 else y1 if i == len(rows) else (rows[i - 1][1] + rows[i][0]) / 2

        def clip(top, bottom):
            box = [x0, top, x1, bottom]
            box = unturn([{"bbox": box, "page_size": upright["page_size"]}], turn)[0]["bbox"] if turn else box
            width, height = block["page_size"]
            return [box[0] / width, box[1] / height, box[2] / width, box[3] / height]

        start = fresh = head
        while fresh < len(rows):
            end = len(rows) if sum(amounts[fresh:]) <= most else fresh + 1  # 남은 행이 한 띠에 들면 다 넣는다
            while end < len(rows) and sum(amounts[fresh:end + 1]) <= target:
                end += 1
            if end < len(rows):
                end = next((i for i in range(end, fresh, -1) if amounts[i]), end)
            top, bottom = cut(0 if start == head else start), cut(end)
            text = [row[2] for row in rows[:head] + rows[start:end]] + [line["text"] for line in tall if line["bbox"][1] < bottom and line["bbox"][3] > top]
            bands.append({"page": block.get("page"), "type": "table", "page_size": block["page_size"], **({"orientation": turn} if turn else {}),
                          **({"repeats": True} if start < fresh else {}),
                          "text": "\n".join(text), "clips": [clip(y0, cut(head)), clip(top, bottom)] if start > head and head else [clip(top, bottom)]})
            start, fresh = next((i for i in range(end - 1, fresh - 1, -1) if amounts[i]), end - 1), end
    return bands if len(bands) > len(tables) else []


def _read_chunk(schema, chunk, index, count, source, budget, deadline=None, cancel=None, on_call=None):
    """The schema read as one JSON object from chunk `index` of `count`."""
    system = (
        "Extract values using document context and layout. Never invent values. Use null when allowed and absent. "
        "A total or sum field takes the value printed in the document's total row or labelled total cell, never a single line item's value. "
        "Return only a single JSON object that itself follows the given schema, with no wrapper key "
        "and with the schema's field order kept."
    )
    if any(prop.get("type") == "array" for prop in schema.get("properties", {}).values()):
        system += TABLE_NOTE
    if cancel is not None and cancel.is_set():
        raise RuntimeError("extraction cancelled")
    left = deadline - time.monotonic() if deadline is not None else None
    if left is not None and left <= 0:
        raise TimeoutError("extraction deadline exceeded")
    page_range = _page_range(chunk)
    evidence = _chunk_text(chunk, budget)
    images = _page_images(source, _pages(chunk), _turns(chunk), chunk[0].get("clips") if chunk else None)
    logger.debug("extract: chunk %d/%d pages=%s blocks=%d evidence_chars=%d images=%d", index + 1, count, page_range, len(chunk), len(evidence), len(images))
    system += VISION_NOTE if images else ""
    if count > 1:
        system += (
            f" This is part {index + 1} of {count} of the document, covering page(s) {page_range}; "
            "return null/empty for fields not present in this part."
        )
    if on_call is not None:
        on_call()
    messages = [
        {"role": "system", "content": system},
        _user(f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\nSource blocks:\n{evidence}", images),
    ]
    result = _provider(messages, timeout_cap=left) if left is not None else _provider(messages)
    if not isinstance(result, dict):
        raise RuntimeError("AI provider 응답이 JSON object가 아닙니다.")
    return result


def _read_chunks(schema, chunks, source, budget, deadline=None, cancel=None, on_call=None):
    """The schema read as one JSON object per chunk, merged by schema."""
    return _merge_chunk_results([_read_chunk(schema, chunk, index, len(chunks), source, budget, deadline, cancel, on_call)
                                 for index, chunk in enumerate(chunks)], schema)


def extract(schema, blocks, source=None, *, deadline=None, cancel=None, on_call=None, table_extract="asis", completeness=None):
    """`source` is the original document file path; its page images are attached to each chunk call when available.

    `table_extract="rowmajor"` reads each table field (array of objects) in its own call as positional rows (`_read_rows`),
    in parallel with one call for the other fields. It needs a single chunk with page images; otherwise, and for a table
    whose rowmajor reply fails, the table is read as part of the JSON object (`asis`).
    `completeness`, when provided, receives page/table success and failure ranges; partial rows remain usable for review.

    A table whose pages do not fit one reply (`_table_pages` gives several page groups) is read page group by page group in
    parallel (`TABLE_PAGE_CONCURRENCY`, default 4) and its rows are concatenated in page order: one call has to hold the
    whole table otherwise, and a long table runs past the provider output limit. rowmajor reads each group with the column
    plan most pages agree on (`_table_plan`), and a group whose reply fails is read asis alone."""
    coverage = {"partial": False, "pages": _pages(blocks), "successful_pages": _pages(blocks), "failed_pages": [], "tables": {}}
    def report():
        failed = sorted({page for item in coverage["tables"].values() for page in item["failed_pages"]})
        coverage.update(partial=bool(failed), failed_pages=failed,
                        successful_pages=[page for page in coverage["pages"] if page not in failed])
        if completeness is not None:
            completeness.clear()
            completeness.update(coverage)
        note("extraction_completeness", coverage, add=False)

    if ai_settings()["mode"] == "local":
        report()
        logger.debug("extract: local mode blocks=%d", len(blocks))
        return _local_extract(schema, blocks)
    if table_extract not in ("asis", "rowmajor"):
        raise ValueError("TABLE_EXTRACT는 asis 또는 rowmajor여야 합니다.")
    budget = ai_settings()["chunk_chars"]
    if budget <= 0:
        raise ValueError("EXTRACT_CHUNK_CHARS는 양수여야 합니다.")
    chunks = _page_chunks(blocks, budget) or [[]]
    logger.info("extract: provider mode blocks=%d chunks=%d budget=%d pages=%s", len(blocks), len(chunks), budget, [_page_range(chunk) for chunk in chunks])
    properties = schema.get("properties", {})
    tables = _table_fields(schema)
    rowmajor = table_extract == "rowmajor"
    plans = {table: _table_plan(schema.get("title"), table, properties[table], blocks) if rowmajor else None for table in tables}
    groups = {table: _table_pages(blocks, budget, len(properties[table]["items"]["properties"])) for table in tables}
    paged = [table for table in tables if len(groups[table]) > 1]
    images = _page_images(source, _pages(blocks), _turns(blocks)) if rowmajor and len(paged) < len(tables) and len(chunks) == 1 else []
    whole = [table for table in tables if table not in paged] if images else []
    if rowmajor and len(whole) + len(paged) < len(tables):
        logger.info("extract: rowmajor needs one chunk with page images (chunks=%d), reading tables asis", len(chunks))

    def narrowed(keys):
        return {**schema, "properties": {key: prop for key, prop in properties.items() if key in keys},
                "required": [key for key in schema.get("required", []) if key in keys]}

    def read_group(table, group, index, count):
        pages = _page_range(group)
        if rowmajor and (group_images := _page_images(source, _pages(group), _turns(group), group[0].get("clips"))):
            try:
                return _read_rows(table, properties[table], plans[table], _chunk_text(group, budget), group_images,
                                  PAGES_NOTE.format(pages=pages, span=_page_range(blocks))
                                  + (BAND_NOTE[len(group_images) > 1] if "clips" in group[0] else ""), deadline, cancel, on_call)
            except (RuntimeError, ValueError) as exc:  # a reply that broke the row contract: read these pages asis
                if cancel is not None and cancel.is_set():
                    raise
                logger.warning("extract: rowmajor table=%s pages=%s failed, reading them asis: %s", table, pages, exc)
        try:
            rows = _read_chunk(narrowed({table}), group, index, count, source, budget, deadline, cancel, on_call).get(table)
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise RuntimeError("표 응답이 객체 행 목록이 아닙니다.")
            return rows
        except (RuntimeError, ValueError) as exc:  # one page group lost, not the whole table: counted as table_pages_failed
            if cancel is not None and cancel.is_set():
                raise
            logger.warning("extract: table=%s pages=%s could not be read, its rows are missing: %s", table, pages, exc)
            note("table_pages_failed", 1)
            return exc

    def read_pages(table):
        count = len(groups[table])
        logger.info("extract: table=%s read in %d page groups %s", table, count, [_page_range(group) for group in groups[table]])
        parts = parallel(lambda item: read_group(table, item[1], item[0], count), enumerate(groups[table]), limit("TABLE_PAGE_CONCURRENCY", 4, 32))
        coverage["tables"][table] = {
            "successful_pages": [page for group, part in zip(groups[table], parts) if not isinstance(part, Exception) for page in _pages(group)],
            "failed_pages": [page for group, part in zip(groups[table], parts) if isinstance(part, Exception) for page in _pages(group)],
        }
        if all(isinstance(part, Exception) for part in parts):
            raise parts[-1]
        for group, before, part in zip(groups[table][1:], parts, parts[1:]):  # 띠가 다시 읽은 앞 띠의 마지막 행은 한 번만
            if group[0].get("repeats") and before and part and not isinstance(before, Exception) and not isinstance(part, Exception) \
                    and _same_row(before[-1], part[0]):
                before[-1] = max(before[-1], part.pop(0), key=lambda row: sum(value not in (None, "") for value in row.values()))
        return _merge_chunk_results([part for part in parts if not isinstance(part, Exception)], properties[table])

    def read(table):
        if table is None:
            return _read_chunks(narrowed(set(properties) - set(separate)) if separate else schema, chunks, source, budget, deadline, cancel, on_call)
        if table in paged:
            return read_pages(table)
        try:
            return _read_rows(table, properties[table], plans[table],
                              _chunk_text(blocks, budget), images, "", deadline, cancel, on_call)
        except (RuntimeError, ValueError) as exc:  # a reply that broke the row contract: read the table asis below
            logger.warning("extract: rowmajor table=%s failed, reading it asis: %s", table, exc)
            note("rowmajor_fallback", str(exc)[:200], add=False)
            return None

    separate = whole + paged
    parts = ([None] if len(separate) < len(properties) or not properties else []) + separate
    read_parts = dict(zip(parts, parallel(read, parts, len(parts))))
    merged = read_parts.pop(None, None) or {}
    failed = [table for table, rows in read_parts.items() if rows is None]
    if failed:
        merged.update(_read_chunks(narrowed(set(failed)), chunks, source, budget, deadline, cancel, on_call))
    merged = {**merged, **{table: rows for table, rows in read_parts.items() if rows is not None}}
    if separate:
        merged = {key: merged.get(key) for key in properties}
    for table in tables:
        coverage["tables"].setdefault(table, {"successful_pages": coverage["pages"], "failed_pages": []})
    report()
    _drop_null_optionals(merged, schema)
    return merged, ground(merged, schema, blocks)


def _normalized(text):
    """Drop whitespace, thousands separators and literal `\\n` so `12,380`, `12380` and `전액\\n본인부담` compare equal."""
    return re.sub(r"[\s,]+|\\n", "", str(text))


def _block_rows(block):
    """Read a block as rows of normalized cells: table HTML `<tr>` (every row kept, so row indexes stay geometric), parsed table rows, or one row of the text and its tokens."""
    text = block.get("text", "")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S) or ([text] if re.search(r"<t[dh][\s>]", text) else [])
    if rows: return [[_normalized(re.sub(r"<[^>]+>", "", cell)) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)] for row in rows]
    if block.get("rows"): return [[_normalized(cell) for cell in row] for row in block["rows"]]
    return [[_normalized(text), *(_normalized(token) for token in text.split())]]


def _source_cell(block, row_no, value):
    """Return the printed cell text when a table supplied it; otherwise the OCR block text."""
    raw = block.get("rows")
    if not raw:
        content = block.get("text", "")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", content, re.S) or ([content] if re.search(r"<t[dh][\s>]", content) else [])
        raw = [[html.unescape(re.sub(r"<[^>]+>", "", cell)) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)] for row in rows]
    if row_no < len(raw):
        needles = _needles(value)
        return next((str(cell) for cell in raw[row_no] if _normalized(cell) in needles),
                    next((str(cell) for cell in raw[row_no] if any(n in _normalized(cell) for n in needles)), block.get("text", "")))
    return block.get("text", "")


def _needles(value):
    """Normalized forms of a value: `1.0` ↔ `1`, date separator variants, a trailing currency or unit sign."""
    forms = {str(value)}
    if isinstance(value, float) and value.is_integer(): forms.add(str(int(value)))  # the model returns 1.0 where the document shows 1
    for form in list(forms):
        forms.add(re.sub(r"[원₩%]$", "", form.strip()))
        if re.fullmatch(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", form): forms.update(re.sub(r"[.\-/]", separator, form) for separator in ".-/")
    return {needle for needle in map(_normalized, forms) if needle}


def _rank(cells, needles):
    """2 for a whole-cell match, 1 for a substring match of a 3+ character needle or a close (>=0.85) fuzzy match of a 4+ character non-numeric needle, 0 for none."""
    cells = [*cells, *(cell.replace("-", "") for cell in cells if "-" in cell)]  # `201-90-97318` is extracted as `2019097318`
    if any(cell == needle for cell in cells for needle in needles): return 2
    if any(needle in cell for cell in cells for needle in needles if len(needle) >= 3): return 1
    fuzzy = [needle for needle in needles if len(needle) >= 4 and not needle.isdigit()]
    return 1 if any(abs(len(cell) - len(needle)) <= 2 and difflib.SequenceMatcher(None, cell, needle).ratio() >= 0.85
                     for cell in cells for needle in fuzzy) else 0


def _hits(value, sources):
    """Rows holding the value; whole-cell matches win over substring matches."""
    needles, exact, loose = _needles(value), [], []
    for index, (_, rows) in enumerate(sources):
        for row_no, cells in enumerate(rows):
            rank = _rank(cells, needles)
            if rank == 2: exact.append((index, row_no))
            elif rank: loose.append((index, row_no))
    return exact or loose


def _agreed_row(hits, taken):
    """The row most of an object's leaves agree on; ties prefer a row no earlier array item took."""
    counts = Counter(position for positions in hits.values() for position in positions)
    if not counts: return None
    agreed = min(counts, key=lambda position: (-counts[position], position in taken, position))
    taken.add(agreed)
    return agreed


def _position(hits, agreed):
    return agreed if agreed in hits else (hits[0] if hits else None)


def _center(bbox):
    return (bbox[1] + bbox[3]) / 2


def _ranked_lines(value, blocks):
    """(block, line) pairs across `blocks` whose OCR line text best matches the value; empty when nothing matches."""
    needles = _needles(value)
    ranked = [(_rank([_normalized(line["text"])], needles), block, line) for block in blocks for line in block.get("lines") or []]
    best = max((rank for rank, _, _ in ranked), default=0)
    return [(block, line) for rank, block, line in ranked if rank == best] if best else []


def _value_lines(value, hits, agreed, sources):
    """OCR line boxes of the matched block that hold the value, whole-line matches first; empty when the parser collected no lines."""
    position = _position(hits, agreed)
    if position is None: return []
    return [line for _, line in _ranked_lines(value, [sources[position[0]][0]])]


def _band(candidates):
    """Median y center of the siblings that matched exactly one line — the vertical band their object occupies."""
    centers = sorted(_center(lines[0]["bbox"]) for lines in candidates if len(lines) == 1)
    return centers[len(centers) // 2] if centers else None


def _labels(key, schema, aliases=True):
    """Normalized label texts, including the existing rule registry's aliases."""
    from .rules import LABELS
    return {label for label in (_normalized(str(text).replace("_", ""))
                          for text in (key, schema.get("title", ""), *(LABELS.get(key, ()) if aliases else ()))) if len(label) >= 2}


def _labelled(lines, anchors, reach):
    """The line beside or right under one of the field's label lines, within `reach` line heights; None when no line sits that close."""
    def gap(line):
        return min((abs(_center(line["bbox"]) - _center(anchor["bbox"])) for anchor in anchors if anchor is not line and anchor["bbox"][0] <= line["bbox"][2]), default=float("inf"))
    near = [line for line in lines if gap(line) <= reach * (line["bbox"][3] - line["bbox"][1])]
    return min(near, key=gap, default=None)


def _pick(value, lines, band, block, anchors):
    """The candidate line next to the field's label, else the one nearest the object's band (the first one when there is no band).
    Without a candidate, a line under the label that still resembles the value, else the whole block box."""
    if not lines:
        needles = _needles(value)
        alike = [line for line in block.get("lines") or [] if any(difflib.SequenceMatcher(None, _normalized(line["text"]), needle).ratio() >= 0.5 for needle in needles)]
        line = _labelled(alike, anchors, 2)
        return line["bbox"] if line else block.get("bbox")
    line = _labelled(lines, anchors, 1) if len(lines) > 1 else None
    if line: return line["bbox"]
    if band is None: return lines[0]["bbox"]
    return min(lines, key=lambda line: abs(_center(line["bbox"]) - band))["bbox"]


def _line_leaf(value, sources, band):
    """A leaf built straight from an OCR line matching the value, for when the row match failed or missed the agreed row; None unless a candidate line sits inside the object's band (or there is no band)."""
    candidates = _ranked_lines(value, [block for block, _ in sources])
    if band is not None:
        candidates = [(block, line) for block, line in candidates if abs(_center(line["bbox"]) - band) <= line["bbox"][3] - line["bbox"][1]]
    if not candidates: return None
    block, line = candidates[0]
    seen = _normalized(line["text"])
    exact = seen in _needles(value)
    contained = any(needle in form for needle in _needles(value) for form in (seen, seen.replace("-", "")))
    return {"confidence": 1.0 if contained else 0.5, "page": block.get("page"), "bbox": line["bbox"], "page_size": block.get("page_size"),
            "source_text": line["text"], "match": "exact" if exact else ("contained" if contained else "approximate")}


def _leaf(value, hits, agreed, strict, sources, band=None, labels=()):
    """Leaf grounding; inside an array item a value found only outside the agreed row drops to 0.5 unless a nearby OCR line confirms it."""
    if value is None: return {"confidence": 0, "page": None, "bbox": None, "source_text": None}
    position = _position(hits, agreed)
    confirmed = position is not None and (position == agreed or not strict)
    if not confirmed:
        fallback = _line_leaf(value, sources, band)
        if fallback: return fallback
    if position is None: return {"confidence": 0.0, "page": None, "bbox": None, "source_text": None, "match": "none"}
    block = sources[position[0]][0]
    anchors = [line for other, _ in sources if other.get("page") == block.get("page") for line in other.get("lines") or []
               if any(label in _normalized(line["text"]) for label in labels)]
    row = sources[position[0]][1][position[1]]
    exact = any(cell in _needles(value) for cell in row)
    contained = any(needle in form for cell in row for form in (cell, cell.replace("-", "")) for needle in _needles(value))
    bbox = _pick(value, _value_lines(value, hits, agreed, sources), band, block, anchors)
    source_text = next((line["text"] for line in block.get("lines") or [] if line["bbox"] == bbox),
                       _source_cell(block, position[1], value))
    ambiguous = len(hits) > 1 and not strict and not anchors
    return {
        "confidence": 1.0 if confirmed and contained and not ambiguous else 0.5,
        "page": block.get("page"),
        "page_size": block.get("page_size"),
        "bbox": bbox,
        "source_text": source_text,
        "match": "ambiguous" if ambiguous else ("exact" if exact else ("contained" if contained else "approximate")),
        "block": position[0], "row": position[1],
        "column": next((index for index, cell in enumerate(row) if cell in _needles(value)), None),
        "row_mismatch": bool(strict and agreed is not None and position != agreed and block.get("structure") == "ruled"),
        "row_conflict": bool(strict and agreed is not None and position != agreed and block.get("structure") != "ruled"),
    }


def _grounding_tree(value, sources, schema, taken=None, strict=False):
    """Ground every leaf of the result against the rows of the source blocks; booleans are derived values absent from the source text, so they stay out of the tree.
    Outside arrays a repeated value goes to the line next to the field's label; array item keys are column headers, so their rows stay with the sibling band."""
    if isinstance(value, list):
        taken = set()
        return {str(index): _grounding_tree(item, sources, schema.get("items", {}), taken, True) for index, item in enumerate(value) if not isinstance(item, bool)}
    if isinstance(value, dict):
        hits = {key: _hits(sub, sources) for key, sub in value.items() if sub is not None and not isinstance(sub, (bool, dict, list))}
        agreed = _agreed_row(hits, set() if taken is None else taken)
        band = _band([_value_lines(value[key], positions, agreed, sources) for key, positions in hits.items()])
        props = schema.get("properties", {})
        return {key: _grounding_tree(sub, sources, props.get(key, {})) if isinstance(sub, (dict, list))
                else _leaf(sub, hits.get(key, []), agreed, strict, sources, band, () if strict else _labels(key, props.get(key, {})))
                for key, sub in value.items() if not isinstance(sub, bool)}
    return _leaf(value, _hits(value, sources), None, False, sources)


def ground(result, schema, blocks):
    from .typed_evidence import augment
    return augment(result, schema, blocks,
                   _grounding_tree(result, [(block, _block_rows(block)) for block in blocks], schema))


def validate(result, schema, groundings):
    issues = []
    for error in Draft202012Validator(schema).iter_errors(result):
        issues.append({"path": "/" + "/".join(map(str, error.absolute_path)), "code": error.validator, "message": error.message})
    def check_groundings(values, prefix=""):
        for name, grounding in values.items():
            path = f"{prefix}/{name}"
            if isinstance(grounding, dict) and "confidence" in grounding:
                if grounding["confidence"] < 0.7:
                    issues.append({"path": path, "code": "low_confidence", "message": "원문 근거 또는 추출 신뢰도가 낮습니다."})
            elif isinstance(grounding, dict):
                check_groundings(grounding, path)
    check_groundings(groundings)
    return issues


def assess(result, schema, blocks, groundings=None, require_geometry=True):
    """Describe per-field evidence without changing a value or treating OCR as image truth.

    An OCR match establishes where a value was read, not whether the pixels were read correctly.
    Missing or approximate evidence is sent to review; a schema violation is unresolved.
    """
    evidence = groundings if groundings is not None else ground(result, schema, blocks)
    problems = validate(result, schema, evidence)
    by_path = {}
    for issue in problems:
        by_path.setdefault(issue["path"], []).append(issue["code"])
    quality = {}

    def distant_label(path, source):
        parts = path.strip("/").split("/")
        if len(parts) != 1 or not source.get("bbox") or len(source["bbox"]) != 4:
            return False
        labels = _labels(parts[0], schema.get("properties", {}).get(parts[0], {}))
        anchors = [line for block in blocks if block.get("page") == source.get("page")
                   for line in block.get("lines") or []
                   if any(label in _normalized(line["text"]) for label in labels)]
        if not anchors:
            return False
        height = max(1, source["bbox"][3] - source["bbox"][1])
        return min(abs(_center(source["bbox"]) - _center(line["bbox"])) for line in anchors) > 3 * height

    def printed_label(path):
        parts = path.strip("/").split("/")
        if len(parts) != 1:
            return False
        labels = _labels(parts[0], schema.get("properties", {}).get(parts[0], {}), aliases=False)
        for block in blocks:
            text = _normalized(block.get("text", ""))
            for label in labels:
                if label in text and not re.match(r"[:：]?((미기재|해당없음|없음)|[-–—])(?:$|[<\n])", text.split(label, 1)[1]):
                    return True
        return False

    def walk(value, source, spec, path=""):
        if isinstance(value, dict):
            for key in spec.get("required", []):
                if key not in value:
                    missing = f"{path}/{key.replace('~', '~0').replace('/', '~1')}".lstrip("/")
                    quality[missing] = {"status": "UNRESOLVED", "issue_codes": ["required"],
                                        "stage": "extract", "action": "REVIEW", "provenance": {}}
            for key, child in value.items():
                walk(child, source.get(key, {}) if isinstance(source, dict) else {}, spec.get("properties", {}).get(key, {}),
                     f"{path}/{key.replace('~', '~0').replace('/', '~1')}")
        elif isinstance(value, list):
            cardinality = [code for code in by_path.get(path, []) if code in {"minItems", "maxItems"}]
            if cardinality:
                quality[path.lstrip("/")] = {"status": "UNRESOLVED", "issue_codes": cardinality,
                                              "stage": "extract", "action": "REVIEW", "provenance": {}}
            for index, child in enumerate(value):
                walk(child, source.get(str(index), {}) if isinstance(source, dict) else {}, spec.get("items", {}), f"{path}/{index}")
        else:
            codes = list(dict.fromkeys(by_path.get(path, [])))
            from .typed_evidence import valid as valid_typed
            typed = (isinstance(source, dict) and valid_typed(source, value)
                     and (not source.get("field_key") or source["field_key"] == path.lstrip("/"))
                     and (source.get("evidence_type") not in {"derived_sum", "schema_alias", "aligned_amount", "inferred_checkbox_unselected"}
                          or source.get("doc_type") == schema.get("title")
                          and source.get("target_field", source.get("target_path")) == path.lstrip("/")))
            if isinstance(source, dict) and source.get("match") in {"typed", "blank", "derived", "inferred"} and not typed:
                codes.append("invalid_typed_proof")
            if value is None:
                codes = [code for code in codes if code != "low_confidence"]
                if printed_label(path) and not typed:
                    codes.append("missing_value")
            if value is not None and not isinstance(value, bool):
                if not typed and (not isinstance(source, dict) or not source.get("source_text") or (require_geometry and (source.get("page") is None or not source.get("bbox")))):
                    codes.append("no_source")
                elif source.get("match") == "approximate":
                    codes.append("approximate_source")
                elif source.get("match") == "ambiguous":
                    codes.append("ambiguous_source")
                if isinstance(source, dict) and source.get("row_mismatch"):
                    codes.append("row_mismatch")
                if isinstance(source, dict) and source.get("row_conflict"):
                    codes.append("row_conflict")
                if isinstance(source, dict) and source.get("bbox") and source.get("page_size"):
                    box, size = source["bbox"], source["page_size"]
                    valid = (len(box) == 4 and len(size) == 2 and
                             all(isinstance(number, (int, float)) for number in (*box, *size)))
                    if not valid or not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
                        codes.append("invalid_geometry")
                if isinstance(source, dict) and not typed and distant_label(path, source):
                    codes.append("distant_label")
            codes = list(dict.fromkeys(codes))
            hard = {"row_mismatch", "invalid_geometry"}
            state = "UNRESOLVED" if any(code in hard or code not in {"low_confidence", "no_source", "approximate_source", "ambiguous_source", "distant_label", "missing_value", "row_conflict"} for code in codes) else ("SUSPICIOUS" if codes else "PASS")
            quality[path.lstrip("/")] = {"status": state, "issue_codes": codes,
                                           "stage": "undetermined" if codes else None,
                                           "action": "REVIEW" if state == "UNRESOLVED" else ("RECHECK" if codes else "ACCEPT"),
                                           "provenance": {key: source.get(key) for key in ("page", "bbox", "page_size", "source_text", "block", "row", "column", "table", "match", "evidence_type", "transform", "role", "label", "geometry_scope", "normalized_value", "verified", "basis", "operation", "target_field", "target_path", "doc_type", "terms", "field_key", "label_bbox", "alignment_axis", "alignment_anchors", "blank_method", "polygon", "rotation_degrees", "group_label", "group_bbox", "target_line_text", "target_label_bbox") if key in source} if isinstance(source, dict) else {}}

    walk(result, evidence, schema)
    return quality


def _table_fields(schema):
    """Top-level fields that are arrays of objects (the tables)."""
    return [key for key, prop in schema.get("properties", {}).items()
            if prop.get("type") == "array" and prop.get("items", {}).get("type") == "object"]


INTEGRITY_NODES = {"downscaled": "AUX.INPUT", "decode_failed": "AUX.INPUT", "image_not_sent": "P.MIS.AREA.1",
                   "duplicate_page": "P.OVR.DUP.1", "boundary_repeat": "E.OVR.DUP.1", "duplicate_run": "E.OVR.DUP.1",
                   "page_order": "P.WRG.ORDER.1", "row_page_order": "P.WRG.ORDER.1", "table_page_gap": "P.STR.LINK.1",
                   "document_boundary": "P.STR.DOC"}
# 근사 중복 쪽(P.OVR.DUP.1): 다시 스캔·캡처한 같은 쪽은 OCR 글자가 조금 달라 본문이 같지 않다. 그 쪽에서 한 번만 나오는
# 2자리 이상 숫자(금액·날짜·번호)가 DUPLICATE_SIMILARITY 이상 겹치고(둘 다 DUPLICATE_MIN_NUMBERS개 이상) 인쇄된 날짜가 모두 같으며, 쪽 그림의 16×16 dHash가
# DUPLICATE_IMAGE_DISTANCE 이하로 다를 때만 중복으로 본다. 같은 서식의 다른 문서(이어지는 쪽·같은 환자의 다른 날 영수증)는
# 서식 글자·그림이 비슷해도 숫자가 갈린다. 근거: wiki/2026-10-05-page-integrity.md(359쪽·31,626쌍).
DUPLICATE_SIMILARITY = 0.9
DUPLICATE_MIN_NUMBERS = 5
DUPLICATE_IMAGE_DISTANCE = 0.3
# 서식 제목 줄(P.STR.DOC): 표 밖 줄 중 기호를 지워 TITLE_MAX_CHARS자 이하이고 doctypes.TITLES에 맞으며, 글자 높이가 그 쪽 줄 높이
# 중앙값의 TITLE_HEIGHT_RATIO배 이상인 줄. 안내문 속 서식 이름(「…진단서는 무효임」)은 본문 크기라 빠진다.
TITLE_MAX_CHARS = 24
TITLE_HEIGHT_RATIO = 1.3


def input_report(source, blocks, schema):
    """What decoding did to the page images the model sees (AUX.INPUT): page count, EXIF turn, parser turns, per page the
    shrink factor (< 1 loses detail beyond VISION_MAX_EDGE) and whether any call attached its image (P.MIS.AREA.1).
    A page with a loss carries `codes`; the report only measures, it never changes a value."""
    if not source or Path(source).suffix.lower() not in VISION_SUFFIXES:
        return {}
    report = {"node": "AUX.INPUT", "page_count": 0, "exif_turned": False, "decode_failed": False, "pages": {}}
    try:
        with fitz.open(source) as document:
            report["page_count"] = len(document)
            for number, page in enumerate(document, 1):
                report["pages"][number] = {"scale": round(min(VISION_MAX_EDGE / max(page.rect.width, page.rect.height), 2.0), 3), "codes": []}
        if Path(source).suffix.lower() != ".pdf":
            with Image.open(source) as image:
                report["exif_turned"] = image.getexif().get(274, 1) != 1
    except Exception as exc:
        logger.warning("input report: %s could not be decoded: %s", Path(source).name, exc)
        report["decode_failed"] = True
        report["pages"] = {number: {"codes": ["decode_failed"]} for number in _pages(blocks)}
    for number, turn in _turns(blocks).items():
        report["pages"].setdefault(number, {"codes": []})["turned"] = turn
    for number, item in report["pages"].items():
        if item.get("scale", 1) < 1:
            item["codes"].append("downscaled")
    if ai_settings()["vision"]:
        budget = ai_settings()["chunk_chars"]
        groups = [chunk for chunk in _page_chunks(blocks, budget)]
        groups += [group for table in _table_fields(schema) for group in _table_pages(blocks, budget, len(schema["properties"][table]["items"]["properties"]))]
        sent = {page for group in groups for page in _pages(group)[:VISION_MAX_IMAGES]}
        for number in _pages(blocks):
            if number not in sent and not report["decode_failed"]:
                report["pages"].setdefault(number, {"codes": []})["codes"].append("image_not_sent")
    return report


def _row_signature(row):
    return tuple(_normalized(value) for value in row.values() if value not in (None, "")) if isinstance(row, dict) else ()


def _row_page(row_grounding):
    return next((leaf["page"] for leaf in (row_grounding or {}).values() if isinstance(leaf, dict) and leaf.get("page") is not None), None)


def _page_numbers(page_blocks):
    """`(distinct, dates)` of a page: numbers of 2+ digits printed exactly once (separators dropped, so `2019-02-17` is one
    token) and every printed YYYYMMDD date. Two pages of one document print the same dates; another day's copy does not."""
    found = Counter(re.sub(r"\D", "", token) for block in page_blocks
                    for token in re.findall(r"\d(?:[\d,./-]*\d)?", re.sub(r"<[^>]+>", " ", block.get("text", ""))))
    return ({token for token, count in found.items() if count == 1 and len(token) >= 2},
            {token for token in found if re.fullmatch(r"(?:19|20)\d\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])", token)})


def _page_hashes(source, pages, turns):
    """page → 16×16 difference hash (256 bits) of the upright grayscale page image; empty for formats without page images."""
    if not pages or not source or Path(source).suffix.lower() not in VISION_SUFFIXES:
        return {}
    hashes = {}
    try:
        with fitz.open(source) as document:
            for number in pages:
                if 1 <= number <= len(document):
                    page = document[number - 1]
                    zoom = 256 / max(page.rect.width, page.rect.height)
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom).prerotate(-turns.get(number, 0)), colorspace=fitz.csGRAY, alpha=False)
                    pixels = list(Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples).resize((17, 16), Image.BOX).getdata())
                    hashes[number] = [pixels[i + 1] > pixels[i] for i in range(len(pixels) - 1) if (i + 1) % 17]
    except Exception as exc:
        logger.warning("integrity: page images of %s could not be hashed: %s", Path(source).name, exc)
    return hashes


def _page_titles(page_blocks):
    """Document types of the form-title lines on a page (top to bottom): short non-table lines matching doctypes.TITLES
    whose glyph height is at least TITLE_HEIGHT_RATIO × the page's median line height."""
    lines = [(line.get("text", ""), line["bbox"]) for block in page_blocks if block.get("type") != "table"
             for line in (block.get("lines") or [{"text": block.get("text", ""), "bbox": block.get("bbox")}]) if line.get("bbox")]
    heights = sorted(bbox[3] - bbox[1] for _, bbox in lines)
    titles = []
    for text, bbox in sorted(lines, key=lambda line: line[1][1]):
        cleaned = re.sub(r"[\W_\d]+", "", text)
        if cleaned and len(cleaned) <= TITLE_MAX_CHARS and bbox[3] - bbox[1] >= TITLE_HEIGHT_RATIO * heights[len(heights) // 2]:
            titles += [kind for kind, pattern in doctypes.TITLES.items() if re.search(pattern, cleaned)][:1]
    return titles


def unit_flags(result, schema, groundings, blocks, source=None):
    """Repeats, order anomalies and document boundaries across page and row boundaries (E.OVR.DUP.1, P.OVR.DUP.1,
    P.WRG.ORDER.1, P.STR.LINK.1, P.STR.DOC). Each flag is `{code, node, pages | table + rows}`; values are never changed
    (B2 only drops one exact repeat at a chunk boundary). A page repeats an earlier one when its text is equal, or when
    its distinct numbers and its image (`source`) are both near that page's; a document boundary is a page printing
    form titles of two types, or whose first title differs from the previous titled page's last."""
    flags = []

    def flag(code, **where):
        flags.append({"code": code, "node": INTEGRITY_NODES[code], **where})

    order = [block["page"] for block in blocks if block.get("page") is not None]
    if order != sorted(order):
        flag("page_order", pages=sorted(set(order)))
    pages = {number: [block for block in blocks if block.get("page") == number] for number in _pages(blocks)}
    texts = {number: "".join(_normalized(block.get("text", "")) for block in found) for number, found in pages.items()}
    numbers = {number: _page_numbers(found) for number, found in pages.items()}
    near = [(a, b) for a in pages for b in pages if a < b and numbers[a][1] == numbers[b][1]
            and min(len(numbers[a][0]), len(numbers[b][0])) >= DUPLICATE_MIN_NUMBERS
            and 2 * len(numbers[a][0] & numbers[b][0]) / (len(numbers[a][0]) + len(numbers[b][0])) >= DUPLICATE_SIMILARITY]
    hashes = _page_hashes(source, {number for pair in near for number in pair}, _turns(blocks))
    near = {pair for pair in near if all(n in hashes for n in pair)
            and sum(x != y for x, y in zip(hashes[pair[0]], hashes[pair[1]])) / len(hashes[pair[0]]) <= DUPLICATE_IMAGE_DISTANCE}
    first = {}
    for b in pages:
        a = next((a for a in pages if a < b and ((a, b) in near or (texts[a] == texts[b] and len(texts[a]) >= 20))), None)
        if a is not None:
            first[b] = first.get(a, a)
    for origin in sorted(set(first.values())):
        flag("duplicate_page", pages=[origin, *sorted(b for b, a in first.items() if a == origin)])
    titles = {number: _page_titles(found) for number, found in pages.items()}
    titled = [number for number in pages if titles[number]]
    boundary = {number for number in titled if len(set(titles[number])) > 1}
    boundary |= {b for a, b in zip(titled, titled[1:]) if titles[a][-1] != titles[b][0]}
    if boundary:
        flag("document_boundary", pages=sorted(boundary), titles={number: titles[number] for number in titled})
    covered = set()
    for table in _table_fields(schema):
        rows = result.get(table) if isinstance(result, dict) else None
        rows = rows if isinstance(rows, list) else []
        signatures = [_row_signature(row) for row in rows]
        pages = [_row_page((groundings.get(table) or {}).get(str(index))) for index in range(len(rows))]
        covered.update(page for page in pages if page is not None)
        boundary = [i for i in range(1, len(rows)) if signatures[i] and signatures[i] == signatures[i - 1]
                    and None not in (pages[i - 1], pages[i]) and pages[i] != pages[i - 1]]
        seen, run = {}, set()
        for i in range(len(rows) - 2):
            window = tuple(signatures[i:i + 3])
            if all(window) and len(set(window)) > 1:
                if seen.setdefault(window, i) + 3 <= i:
                    run.update(range(i, i + 3))
        known = [(i, page) for i, page in enumerate(pages) if page is not None]
        reversed_rows = [i for (_, before), (i, after) in zip(known, known[1:]) if after < before]
        for code, found in (("boundary_repeat", boundary), ("duplicate_run", sorted(run)), ("row_page_order", reversed_rows)):
            if found:
                flag(code, table=table, rows=found)
    table_pages = {block["page"] for block in blocks if block.get("type") == "table" and block.get("page") is not None}
    gap = sorted(page for page in table_pages if covered and min(covered) < page < max(covered) and page not in covered)
    if gap:
        flag("table_page_gap", pages=gap)
    return flags


def apply_integrity(quality, result, schema, groundings, blocks, source):
    """Record input-integrity and unit-boundary evidence on every document path (document queue and /api/read).

    Adds the codes to `issue_codes` of the affected results (by page, or by table row) and returns the summary
    `{input, flags, lossy_pages}`. A confirmed value stays PASS unless `INTEGRITY_REVIEW=true`, which turns it into a RECHECK suspect."""
    report = input_report(source, blocks, schema)
    flags = unit_flags(result, schema, groundings, blocks, source)
    by_page = {number: list(item["codes"]) for number, item in report.get("pages", {}).items() if item["codes"]}
    by_row = {}
    for item in flags:
        for number in item.get("pages", []) if "table" not in item else []:
            by_page.setdefault(number, []).append(item["code"])
        for row in item.get("rows", []):
            by_row.setdefault(f"{item['table']}/{row}/", []).append(item["code"])
    for path, item in quality.items():
        codes = by_page.get((item.get("provenance") or {}).get("page"), []) + [
            code for prefix, found in by_row.items() if path.startswith(prefix) for code in found]
        if codes:
            item["issue_codes"] = list(dict.fromkeys([*item["issue_codes"], *codes]))
            if ai_settings()["integrity_review"] and item["status"] == "PASS":
                item.update(status="SUSPICIOUS", stage="undetermined", action="RECHECK")
    return {"input": report, "flags": flags, "lossy_pages": sorted(by_page)}


def annotate_groundings(groundings, quality):
    """Persist quality beside each leaf so document APIs can expose the assessment."""
    for path, item in quality.items():
        node = groundings
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")]
        for part in parts[:-1]:
            node = node.setdefault(part, {}) if isinstance(node, dict) else None
        if isinstance(node, dict):
            node = node.setdefault(parts[-1], {"confidence": 0, "page": None, "bbox": None, "source_text": None})
            if "confidence" not in node:
                node = node.setdefault("_quality", {"confidence": 0, "page": None, "bbox": None, "source_text": None})
        if isinstance(node, dict) and "confidence" in node:
            node.update(status=item["status"], issue_codes=item["issue_codes"])
    return groundings


def set_pointer(document, pointer, value):
    if not pointer.startswith("/"):
        pointer = "/" + pointer.replace(".", "/")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    result = deepcopy(document)
    target = result
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    key = parts[-1]
    old = target[int(key)] if isinstance(target, list) else target.get(key)
    if isinstance(target, list): target[int(key)] = value
    else: target[key] = value
    return result, old
