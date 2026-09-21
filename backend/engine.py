import json
import re
from copy import deepcopy

import httpx
from jsonschema import Draft202012Validator

from .config import ai_settings


class ProviderConfigurationError(RuntimeError):
    pass


def _provider(messages, response_schema=None):
    settings = ai_settings()
    if not settings["configured"] or settings["mode"] == "local":
        raise ProviderConfigurationError("AI provider가 설정되지 않았습니다. AI_BASE_URL, AI_API_KEY, AI_VLM_MODEL을 확인해 주세요.")
    body = {"model": settings["model"], "messages": messages, "temperature": 0}
    if response_schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "strict": True, "schema": response_schema}}
    else:
        body["response_format"] = {"type": "json_object"}
    with httpx.Client(timeout=90, transport=httpx.HTTPTransport(retries=2)) as client:
        response = client.post(f"{settings['base_url']}/chat/completions", headers={"Authorization": f"Bearer {settings['api_key']}"}, json=body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"AI provider 요청 실패 (HTTP {response.status_code})") from exc
        try:
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") == "length":
                raise RuntimeError("AI provider 응답이 토큰 제한으로 잘렸습니다.")
            content = choice["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise RuntimeError("AI provider 응답 형식을 해석할 수 없습니다.") from exc
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        return json.loads(content)


def _field_name(label):
    name = re.sub(r"[^a-zA-Z0-9가-힣]+", "_", label.strip()).strip("_").lower()
    return name or "field"


def generate_schema(prompt, document_text=""):
    if ai_settings()["mode"] != "local":
        system = "Return only a JSON object containing a practical JSON Schema draft 2020-12. Include title, type object, properties and required. Use nested objects and arrays when the request or document implies them."
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
            properties[_field_name(label)] = {"type": "string", "title": label.strip()}
    if not properties:
        properties["value"] = {"type": "string", "title": "value"}
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


def extract(schema, blocks):
    if ai_settings()["mode"] == "local":
        return _local_extract(schema, blocks)
    evidence = [
        {"text": b["text"], "page": b.get("page"), "bbox": b.get("bbox")}
        for b in blocks
    ]
    grounding_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "JSON Pointer to the extracted leaf value"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "source_text": {"type": ["string", "null"]},
                "page": {"type": ["integer", "null"]},
                "bbox": {"type": ["array", "null"], "items": {"type": "number"}},
            },
            "required": ["path", "confidence", "source_text", "page", "bbox"],
            "additionalProperties": False,
        },
    }
    response_schema = {
        "type": "object",
        "properties": {"result": schema, "groundings": grounding_schema},
        "required": ["result", "groundings"],
        "additionalProperties": False,
    }
    ai = _provider([
        {"role": "system", "content": "Extract values using document context and layout. Never invent values. Use null when allowed and absent. For every extracted leaf, return exact source text and its JSON Pointer. Page and bbox must come from the supplied block metadata; otherwise null."},
        {"role": "user", "content": f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\nSource blocks (use only these coordinates):\n{json.dumps(evidence, ensure_ascii=False)[:40000]}"},
    ], response_schema)
    for item in ai["groundings"]:
        bbox = item.get("bbox")
        if bbox is not None and not any(
            source["page"] == item.get("page") and source["bbox"] == bbox and
            item.get("source_text") and item["source_text"] in source["text"]
            for source in evidence
        ):
            item["bbox"] = None
    return ai["result"], _grounding_tree(ai["groundings"])


def _grounding_tree(items):
    root = {}
    for item in items:
        parts = [part.replace("~1", "/").replace("~0", "~") for part in item["path"].strip("/").split("/") if part]
        if not parts:
            continue
        target = root
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = {key: item.get(key) for key in ("confidence", "page", "bbox", "source_text")}
    return root


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
