import json
import logging
import re
import time
from collections import Counter
from copy import deepcopy

import httpx
from jsonschema import Draft202012Validator

from .config import ai_settings

logger = logging.getLogger(__name__)


class ProviderConfigurationError(RuntimeError):
    pass


def _truncate(text, limit=2000):
    return text if len(text) <= limit * 2 else f"{text[:limit]}...<truncated>...{text[-limit:]}"


def _provider(messages):
    settings = ai_settings()
    if not settings["configured"] or settings["mode"] == "local":
        raise ProviderConfigurationError("AI provider가 설정되지 않았습니다. AI_BASE_URL, AI_API_KEY, AI_VLM_MODEL을 확인해 주세요.")
    body = {"model": settings["model"], "messages": messages, "temperature": 0, "response_format": {"type": "json_object"}}
    prompt_chars = sum(len(m.get("content") or "") for m in messages)
    logger.debug("provider call: model=%s messages=%d prompt_chars=%d", settings["model"], len(messages), prompt_chars)
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


def generate_schema(prompt, document_text=""):
    logger.debug("generate_schema: mode=%s prompt_chars=%d doc_chars=%d", ai_settings()["mode"], len(prompt), len(document_text))
    if ai_settings()["mode"] != "local":
        system = (
            "Return only a JSON object containing a practical JSON Schema draft 2020-12. Include title, type object, properties and required. "
            "Use nested objects and arrays when the request or document implies them. "
            "Every property, including nested and array item properties, must have a title and a description that explains what to extract and in which format. "
            "Write titles and descriptions in Korean first; keep other languages only for proper nouns, codes or units. Property keys stay short snake_case identifiers."
        )
        generated = _provider([{"role": "system", "content": system}, {"role": "user", "content": f"Request:\n{prompt}\n\nDocument sample:\n{document_text[:12000]}"}])
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
    return generate_schema(prompt or "Infer useful structured fields from these parsed documents.", text)


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


def _block_lines(blocks, budget=40000):
    """Serialize block texts as lines, dropping whole blocks beyond the character budget."""
    lines, used = [], 0
    for index, block in enumerate(blocks):
        line = block["text"]
        if used + len(line) > budget:
            logger.warning("extract: block list truncated at %d/%d blocks (budget=%d)", index, len(blocks), budget)
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


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


def extract(schema, blocks):
    if ai_settings()["mode"] == "local":
        logger.debug("extract: local mode blocks=%d", len(blocks))
        return _local_extract(schema, blocks)
    evidence = _block_lines(blocks)
    logger.debug("extract: provider mode blocks=%d evidence_chars=%d", len(blocks), len(evidence))
    result = _provider([
        {"role": "system", "content": (
            "Extract values using document context and layout. Never invent values. Use null when allowed and absent. "
            "Return only a single JSON object that itself follows the given schema, with no wrapper key "
            "and with the schema's field order kept."
        )},
        {"role": "user", "content": f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\nSource blocks:\n{evidence}"},
    ])
    if not isinstance(result, dict):
        raise RuntimeError("AI provider 응답이 JSON object가 아닙니다.")
    _drop_null_optionals(result, schema)
    return result, _grounding_tree(result, [(block, _block_rows(block)) for block in blocks])


def _normalized(text):
    """Drop whitespace, thousands separators and literal `\\n` so `12,380`, `12380` and `전액\\n본인부담` compare equal."""
    return re.sub(r"[\s,]+|\\n", "", str(text))


def _block_rows(block):
    """Read a block as rows of normalized cells: parsed table rows, table HTML `<tr>`, or one row of the text and its tokens."""
    if block.get("rows"): return [[_normalized(cell) for cell in row] for row in block["rows"]]
    text = block["text"]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S) or ([text] if re.search(r"<t[dh][\s>]", text) else [])
    if rows: return [[_normalized(re.sub(r"<[^>]+>", "", cell)) for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)] for row in rows]
    return [[_normalized(text), *(_normalized(token) for token in text.split())]]


def _needles(value):
    """Normalized forms of a value: `1.0` ↔ `1`, date separator variants, a trailing currency or unit sign."""
    forms = {str(value)}
    if isinstance(value, float) and value.is_integer(): forms.add(str(int(value)))  # the model returns 1.0 where the document shows 1
    for form in list(forms):
        forms.add(re.sub(r"[원₩%]$", "", form.strip()))
        if re.fullmatch(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", form): forms.update(re.sub(r"[.\-/]", separator, form) for separator in ".-/")
    return {needle for needle in map(_normalized, forms) if needle}


def _hits(value, sources):
    """Rows holding the value; whole-cell matches win and substring matches need a needle of 3+ characters."""
    needles, exact, loose = _needles(value), [], []
    for index, (_, rows) in enumerate(sources):
        for row_no, cells in enumerate(rows):
            if any(cell == needle for cell in cells for needle in needles): exact.append((index, row_no))
            elif any(needle in cell for cell in cells for needle in needles if len(needle) >= 3): loose.append((index, row_no))
    return exact or loose


def _agreed_row(hits, taken):
    """The row most of an object's leaves agree on; ties prefer a row no earlier array item took."""
    counts = Counter(position for positions in hits.values() for position in positions)
    if not counts: return None
    agreed = min(counts, key=lambda position: (-counts[position], position in taken, position))
    taken.add(agreed)
    return agreed


def _row_bbox(bbox, row_no, total):
    """Split the block box into equal horizontal bands, one per row; rowspan and uneven row heights are ignored."""
    if not bbox or total <= 1: return bbox
    x0, y0, x1, y1 = bbox
    return [x0, y0 + (y1 - y0) * row_no / total, x1, y0 + (y1 - y0) * (row_no + 1) / total]


def _leaf(value, hits, agreed, strict, sources):
    """Leaf grounding; inside an array item a value found only outside the agreed row drops to 0.5."""
    if value is None: return {"confidence": 0, "page": None, "bbox": None, "source_text": None}
    position = agreed if agreed in hits else (hits[0] if hits else None)
    if position is None: return {"confidence": 0.0, "page": None, "bbox": None, "source_text": str(value)}
    block, rows = sources[position[0]]
    return {
        "confidence": 1.0 if position == agreed or not strict else 0.5,
        "page": block.get("page"),
        "bbox": _row_bbox(block.get("bbox"), position[1], len(rows)),
        "source_text": str(value),
    }


def _grounding_tree(value, sources, taken=None, strict=False):
    """Ground every leaf of the result against the rows of the source blocks."""
    if isinstance(value, list):
        taken = set()
        return {str(index): _grounding_tree(item, sources, taken, True) for index, item in enumerate(value)}
    if isinstance(value, dict):
        hits = {key: _hits(sub, sources) for key, sub in value.items() if sub is not None and not isinstance(sub, (dict, list))}
        agreed = _agreed_row(hits, set() if taken is None else taken)
        return {key: _grounding_tree(sub, sources) if isinstance(sub, (dict, list)) else _leaf(sub, hits.get(key, []), agreed, strict, sources)
                for key, sub in value.items()}
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
