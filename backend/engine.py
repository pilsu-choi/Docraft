import json
import os
import re
from copy import deepcopy

import httpx
from jsonschema import Draft202012Validator


def _provider(messages, response_schema=None):
    base = os.getenv("AI_BASE_URL")
    key = os.getenv("AI_API_KEY")
    model = os.getenv("AI_MODEL")
    if not (base and key and model):
        return None
    body = {"model": model, "messages": messages, "temperature": 0}
    if response_schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "strict": True, "schema": response_schema}}
    with httpx.Client(timeout=90, transport=httpx.HTTPTransport(retries=2)) as client:
        response = client.post(f"{base.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
        return json.loads(content)


def _field_name(label):
    name = re.sub(r"[^a-zA-Z0-9가-힣]+", "_", label.strip()).strip("_").lower()
    return name or "field"


def generate_schema(prompt, document_text=""):
    system = "Return a practical JSON Schema (draft 2020-12) matching the requested document fields. Include title, type object, properties and required."
    generated = _provider([{"role": "system", "content": system}, {"role": "user", "content": f"Request:\n{prompt}\n\nDocument sample:\n{document_text[:12000]}"}])
    if generated:
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
    text = "\n".join(b["text"] for b in blocks)
    ai = _provider([
        {"role": "system", "content": "Extract only values supported by the document. Use null when absent. Return JSON matching the supplied schema."},
        {"role": "user", "content": f"Schema:\n{json.dumps(schema, ensure_ascii=False)}\n\nDocument:\n{text[:40000]}"},
    ], schema)
    if ai is None:
        return _local_extract(schema, blocks)
    result, groundings = ai, {}
    local_result, local_ground = _local_extract(schema, blocks)
    for name, value in result.items():
        evidence = local_ground.get(name, {}) if local_result.get(name) == value else {}
        groundings[name] = {"confidence": 0.9 if evidence else 0.65, "page": evidence.get("page"), "bbox": evidence.get("bbox"), "source_text": evidence.get("source_text")}
    return result, groundings


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
