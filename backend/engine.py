import base64
import difflib
import json
import logging
import re
import time
from collections import Counter
from copy import deepcopy
from itertools import groupby
from pathlib import Path

import fitz
import httpx
from jsonschema import Draft202012Validator

from .config import ai_settings

logger = logging.getLogger(__name__)

VISION_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}
VISION_MAX_IMAGES = 4  # Page images per provider call.
VISION_MAX_EDGE = 2000  # Longest side of an attached page image, in pixels.
VISION_SCHEMA_PAGES = [1, 2]  # Pages taken from each reference document when generating a schema.
VISION_NOTE = (
    " The page image is attached: read the table structure (merged cells, column headers) from the image, "
    "and use the OCR text only as a spelling aid."
)


class ProviderConfigurationError(RuntimeError):
    pass


def _truncate(text, limit=2000):
    return text if len(text) <= limit * 2 else f"{text[:limit]}...<truncated>...{text[-limit:]}"


def _message_text(content):
    """The text of a message; attached image data stays out of logs and character counts."""
    return "".join(part.get("text", "") for part in content) if isinstance(content, list) else content or ""


def _data_url(page):
    """One rendered page as a base64 JPEG data URL, scaled so its longest side stays within VISION_MAX_EDGE."""
    zoom = min(VISION_MAX_EDGE / max(page.rect.width, page.rect.height), 2.0)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return "data:image/jpeg;base64," + base64.b64encode(pixmap.tobytes("jpeg", jpg_quality=90)).decode()


def _page_images(source, pages):
    """Page images of the document file `source` for the given 1-based page numbers (the same numbering the
    parser puts on blocks). Empty when vision is off, the format has no page image (docx/xlsx/csv/txt/html),
    or rendering fails — the call then falls back to the OCR text alone."""
    if not source or not ai_settings()["vision"] or Path(source).suffix.lower() not in VISION_SUFFIXES:
        return []
    pages = list(pages)
    if len(pages) > VISION_MAX_IMAGES:
        logger.warning("vision: %d pages exceed the %d image limit, attaching the first %d", len(pages), VISION_MAX_IMAGES, VISION_MAX_IMAGES)
        pages = pages[:VISION_MAX_IMAGES]
    try:
        with fitz.open(source) as document:
            return [_data_url(document[number - 1]) for number in pages if 1 <= number <= len(document)]
    except Exception as exc:
        logger.warning("vision: page image rendering failed for %s: %s", Path(source).name, exc)
        return []


def _user(text, images):
    """A user message; attached page images turn its content into the OpenAI content array."""
    if not images:
        return {"role": "user", "content": text}
    return {"role": "user", "content": [*({"type": "image_url", "image_url": {"url": url}} for url in images), {"type": "text", "text": text}]}


def _provider(messages):
    settings = ai_settings()
    if not settings["configured"] or settings["mode"] == "local":
        raise ProviderConfigurationError("AI provider가 설정되지 않았습니다. AI_BASE_URL, AI_API_KEY, AI_VLM_MODEL을 확인해 주세요.")
    body = {"model": settings["model"], "messages": messages, "temperature": 0, "response_format": {"type": "json_object"}}
    prompt_chars = sum(len(_message_text(m.get("content"))) for m in messages)
    images = sum(1 for m in messages if isinstance(m.get("content"), list) for part in m["content"] if part.get("type") == "image_url")
    logger.debug("provider call: model=%s messages=%d images=%d prompt_chars=%d", settings["model"], len(messages), images, prompt_chars)
    started = time.monotonic()
    with httpx.Client(timeout=90, transport=httpx.HTTPTransport(retries=2)) as client:
        response = client.post(f"{settings['base_url']}/chat/completions", headers={"Authorization": f"Bearer {settings['api_key']}"}, json=body)
        elapsed = time.monotonic() - started
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("provider HTTP error: status=%s elapsed=%.2fs", response.status_code, elapsed)
            raise RuntimeError(f"AI provider 요청 실패 (HTTP {response.status_code})") from exc
        try:
            choice = response.json()["choices"][0]
            finish_reason = choice.get("finish_reason")
            if finish_reason == "length":
                logger.warning("provider response truncated: finish_reason=length elapsed=%.2fs", elapsed)
                raise RuntimeError("AI provider 응답이 토큰 제한으로 잘렸습니다.")
            content = choice["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            logger.error("provider response format error: %s elapsed=%.2fs", exc, elapsed)
            raise RuntimeError("AI provider 응답 형식을 해석할 수 없습니다.") from exc
        logger.debug("provider response: elapsed=%.2fs finish_reason=%s len=%d content=%s", elapsed, finish_reason, len(content), _truncate(content))
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error("provider json decode failed: len=%d finish_reason=%s content=%s", len(content), finish_reason, _truncate(content))
            raise


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


def extract(schema, blocks, source=None):
    """`source` is the original document file path; its page images are attached to each chunk call when available."""
    if ai_settings()["mode"] == "local":
        logger.debug("extract: local mode blocks=%d", len(blocks))
        return _local_extract(schema, blocks)
    budget = ai_settings()["chunk_chars"]
    chunks = _page_chunks(blocks, budget) or [[]]
    logger.info("extract: provider mode blocks=%d chunks=%d budget=%d pages=%s", len(blocks), len(chunks), budget, [_page_range(chunk) for chunk in chunks])
    system = (
        "Extract values using document context and layout. Never invent values. Use null when allowed and absent. "
        "Return only a single JSON object that itself follows the given schema, with no wrapper key "
        "and with the schema's field order kept."
    )
    results = []
    for index, chunk in enumerate(chunks):
        page_range = _page_range(chunk)
        evidence = _chunk_text(chunk, budget)
        images = _page_images(source, _pages(chunk))
        logger.debug("extract: chunk %d/%d pages=%s blocks=%d evidence_chars=%d images=%d", index + 1, len(chunks), page_range, len(chunk), len(evidence), len(images))
        chunk_system = system + (VISION_NOTE if images else "")
        if len(chunks) > 1:
            chunk_system += (
                f" This is part {index + 1} of {len(chunks)} of the document, covering page(s) {page_range}; "
                "return null/empty for fields not present in this part."
            )
        result = _provider([
            {"role": "system", "content": chunk_system},
            _user(f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\nSource blocks:\n{evidence}", images),
        ])
        if not isinstance(result, dict):
            raise RuntimeError("AI provider 응답이 JSON object가 아닙니다.")
        results.append(result)
    merged = _merge_chunk_results(results, schema)
    _drop_null_optionals(merged, schema)
    return merged, _grounding_tree(merged, [(block, _block_rows(block)) for block in blocks])


def _normalized(text):
    """Drop whitespace, thousands separators and literal `\\n` so `12,380`, `12380` and `전액\\n본인부담` compare equal."""
    return re.sub(r"[\s,]+|\\n", "", str(text))


def _block_rows(block):
    """Read a block as rows of normalized cells: table HTML `<tr>` (every row kept, so row indexes stay geometric), parsed table rows, or one row of the text and its tokens."""
    text = block["text"]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S) or ([text] if re.search(r"<t[dh][\s>]", text) else [])
    if rows: return [[_normalized(re.sub(r"<[^>]+>", "", cell)) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)] for row in rows]
    if block.get("rows"): return [[_normalized(cell) for cell in row] for row in block["rows"]]
    return [[_normalized(text), *(_normalized(token) for token in text.split())]]


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


def _pick(lines, band, block):
    """The candidate line nearest the object's band (the first one when there is no band), or the whole block box without lines."""
    if not lines: return block.get("bbox")
    if band is None: return lines[0]["bbox"]
    return min(lines, key=lambda line: abs(_center(line["bbox"]) - band))["bbox"]


def _line_leaf(value, sources, band):
    """A leaf built straight from an OCR line matching the value, for when the row match failed or missed the agreed row; None unless a candidate line sits inside the object's band (or there is no band)."""
    candidates = _ranked_lines(value, [block for block, _ in sources])
    if band is not None:
        candidates = [(block, line) for block, line in candidates if abs(_center(line["bbox"]) - band) <= line["bbox"][3] - line["bbox"][1]]
    if not candidates: return None
    block, line = candidates[0]
    return {"confidence": 1.0, "page": block.get("page"), "bbox": line["bbox"], "source_text": str(value)}


def _leaf(value, hits, agreed, strict, sources, band=None):
    """Leaf grounding; inside an array item a value found only outside the agreed row drops to 0.5 unless a nearby OCR line confirms it."""
    if value is None: return {"confidence": 0, "page": None, "bbox": None, "source_text": None}
    position = _position(hits, agreed)
    confirmed = position is not None and (position == agreed or not strict)
    if not confirmed:
        fallback = _line_leaf(value, sources, band)
        if fallback: return fallback
    if position is None: return {"confidence": 0.0, "page": None, "bbox": None, "source_text": str(value)}
    block = sources[position[0]][0]
    return {
        "confidence": 1.0 if confirmed else 0.5,
        "page": block.get("page"),
        "bbox": _pick(_value_lines(value, hits, agreed, sources), band, block),
        "source_text": str(value),
    }


def _grounding_tree(value, sources, taken=None, strict=False):
    """Ground every leaf of the result against the rows of the source blocks; booleans are derived values absent from the source text, so they stay out of the tree."""
    if isinstance(value, list):
        taken = set()
        return {str(index): _grounding_tree(item, sources, taken, True) for index, item in enumerate(value) if not isinstance(item, bool)}
    if isinstance(value, dict):
        hits = {key: _hits(sub, sources) for key, sub in value.items() if sub is not None and not isinstance(sub, (bool, dict, list))}
        agreed = _agreed_row(hits, set() if taken is None else taken)
        band = _band([_value_lines(value[key], positions, agreed, sources) for key, positions in hits.items()])
        return {key: _grounding_tree(sub, sources) if isinstance(sub, (dict, list)) else _leaf(sub, hits.get(key, []), agreed, strict, sources, band)
                for key, sub in value.items() if not isinstance(sub, bool)}
    return _leaf(value, _hits(value, sources), None, False, sources)


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
