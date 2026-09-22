"""AO(Agentic OCR 2.0) 결과를 Docraft 추출 결과와 이미지 기준으로 교차검증·교정한다.

두 결과가 같은 필드는 LLM에 보내지 않고 그대로 확정하고(비용 절감), 어긋나는 필드만 모아
이미지 1장과 함께 한 번의 LLM 호출(`judge`)로 판정한다. 응답은 입력 AO JSON과 같은 구조에
최종 `value`와 판정 정보(`ao_value`, `docraft_value`, `source`, `reason`)를 덧붙인 것이다.
"""

import json
import logging
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path

from . import doctypes, engine, rules
from .parsers import parse

logger = logging.getLogger(__name__)

SOURCES = ("agree", "ao", "docraft", "corrected")
NO_VERDICT = "판정 결과가 없어 AO 값을 유지했습니다."
JUDGE_PROMPT = (
    "The image is a Korean medical document of type \"{doc_type}\". Two OCR systems, \"ao\" and \"docraft\", read it "
    "independently and disagree on the fields below, given as JSON {{\"<key>\": {{\"ao\": <value>, \"docraft\": <value>, "
    "\"desc\": <text>}}}}; a table key holds a list of row objects instead of a scalar value and \"desc\" is a "
    "{{\"<column>\": <text>}} map instead, and null means the system read nothing.\n"
    "\"desc\" is that field's (or column's) definition; pick only a value that matches this definition, since a "
    "similar-looking field can be confused for it.\n"
    "For every key, read what is actually printed in the image and decide:\n"
    "- \"ao\" or \"docraft\" when that side matches the image;\n"
    "- \"corrected\" with the value you read in the image when neither side matches, including when both are null "
    "but the document does show the field;\n"
    "- keep the notation used by the \"ao\" side (date format, digit grouping, units, prefixes and suffixes) whichever side you pick.\n"
    "Never invent a value that is not in the image; answer null when the field is genuinely absent.\n"
    "Return only a JSON object keyed by exactly these keys and nothing else: "
    "{{\"<key>\": {{\"value\": <value>, \"source\": \"ao\"|\"docraft\"|\"corrected\", \"reason\": \"<short reason in Korean>\"}}}}. "
    "For a table key return {{\"rows\": [<row object>, ...], \"source\": ..., \"reason\": ...}} instead, listing every row of the "
    "whole table in document order and using the same column keys as the input rows.\n\nFields:\n"
)


def _value(field):
    """AO 원소의 값. 비어 있으면 ``predicted_value``로 보충하고, 끝내 비면 None."""
    for key in ("value", "predicted_value"):
        if (value := field.get(key)) not in (None, ""):
            return value
    return None


def _scalars(document):
    """문서의 스칼라 원소 ``(key, 원소)``. 그룹 필드도 key가 문서 안에서 유일해 같은 평면에 둔다."""
    for field in document.get("extracted_fields") or []:
        yield field["key"], field
    for group in document.get("extracted_groups") or []:
        for field in group.get("fields") or []:
            yield field["key"], field


def flatten(document: dict) -> dict:
    """AO ``documents[i]`` → 정규 dict(`doctypes` 참고). 표는 표 key → 행 dict 목록."""
    return {
        **{key: _value(field) for key, field in _scalars(document)},
        **{table["key"]: [{cell["key"]: _value(cell) for cell in row} for row in table.get("rows") or []]
           for table in document.get("extracted_tables") or []},
    }


def _describe(doc_type, key, entry):
    """분쟁 항목에 필드(스칼라는 desc, 표는 열별 desc 한 번)의 설명을 덧붙인다."""
    spec = doctypes.DOC_TYPES.get(doc_type, {"fields": {}, "tables": {}})
    if key in spec["tables"]:
        return {**entry, "desc": {column: meta["description"] for column, meta in spec["tables"][key].items()}}
    if key in spec["fields"]:
        return {**entry, "desc": spec["fields"][key]["description"]}
    return entry


def judge(image: str, doc_type: str, disputes: dict) -> dict:
    """어긋난 값들을 이미지 1장과 함께 한 번의 LLM 호출로 판정한다. key → 판정 dict."""
    described = {key: _describe(doc_type, key, entry) for key, entry in disputes.items()}
    prompt = JUDGE_PROMPT.format(doc_type=doc_type) + json.dumps(described, ensure_ascii=False)
    reply = engine._provider([engine._user(prompt, engine._page_images(image, [1]))], timeout=300)
    if not isinstance(reply, dict):
        raise RuntimeError("AI provider 응답이 JSON object가 아닙니다.")
    return {key: reply[key] for key in disputes if isinstance(reply.get(key), dict)}


def _rows_same(doc_type, table, ao_rows, docraft_rows):
    """표는 정규화된 행 목록 전체가 같아야 일치로 본다."""
    ao_rows, docraft_rows = ao_rows or [], docraft_rows or []
    return len(ao_rows) == len(docraft_rows) and all(
        all(rules.same(doctypes.kind(doc_type, column, table), a.get(column), b.get(column)) for column in {*a, *b})
        for a, b in zip(ao_rows, docraft_rows))


def _decide(doc_type, key, verdict, ao_value, docraft_value, field="value"):
    """판정 하나를 ``(최종값, source, reason)``으로 편다. 판정이 없으면 AO 값을 유지한다.

    Judge가 ``corrected``로 돌려준 값은 ``rules.apply``에 그 key만 담아 통과시켜 정규화한다
    (표는 합계행 제거·합계 필드 보충도 덤으로 얻는다). 정규화한 값이 AO(또는 Docraft) 값과 같으면
    표기 차이일 뿐이므로 교정으로 세지 않고 해당 쪽 원본 값으로 되돌린다. 정말 둘 다 다를 때만
    정규화된 값으로 ``corrected``에 남는다. 표(``field="rows"``)는 행 목록 전체가 같아야 같다고 본다.
    """
    if verdict is None:
        return ao_value, "ao", NO_VERDICT
    source, reason = verdict.get("source"), verdict.get("reason")
    if source == "ao":
        return ao_value, source, reason
    if source == "docraft":
        return docraft_value, source, reason
    value = verdict.get(field, ao_value)
    if field == "rows":
        rows = [row for row in value or [] if isinstance(row, dict)]
        normalized = rules.apply(doc_type, {key: rows}, [])[key]
        if _rows_same(doc_type, key, normalized, ao_value):
            return ao_value, "ao", reason
        if _rows_same(doc_type, key, normalized, docraft_value):
            return docraft_value, "docraft", reason
        return normalized, "corrected", reason
    normalized = rules.apply(doc_type, {key: value}, [])[key]
    kind = doctypes.kind(doc_type, key)
    if rules.same(kind, normalized, ao_value):
        return ao_value, "ao", reason
    if rules.same(kind, normalized, docraft_value):
        return docraft_value, "docraft", reason
    return normalized, "corrected", reason


def _annotate(element, value, ao_value, docraft_value, source, reason):
    """AO 원소에 최종값과 판정 정보를 덧붙인다."""
    element.update(value=value, ao_value=ao_value, docraft_value=docraft_value, source=source, reason=reason)
    return element


def _table_rows(table, rows, docraft_rows, source, reason):
    """판정된 행 목록을 AO 원소 형식으로 되돌린다. 같은 자리의 원래 셀이 있으면 confidence 등을 보존한다."""
    originals = [{cell["key"]: cell for cell in row} for row in table.get("rows") or []]
    rows = [row for row in rows or [] if isinstance(row, dict)]
    columns = table.get("headers") or list(dict.fromkeys(column for row in rows for column in row))
    # 판정이 늘린 행에는 원래 셀이 없으므로 같은 열 셀의 형식만 빌리고 값은 모두 비운다.
    blanks = {column: {name: None for name in cell} for row in reversed(originals) for column, cell in row.items()}
    out = []
    for index, row in enumerate(rows):
        original = originals[index] if index < len(originals) else {}
        docraft_row = docraft_rows[index] if index < len(docraft_rows) else {}
        out.append([
            _annotate({**blanks.get(column, {}), **original.get(column, {}), "key": column},
                      row.get(column), original.get(column, {}).get("value"), docraft_row.get(column), source, reason)
            for column in columns])
    return out


def run(image: str, ao: dict, doc_type: str | None = None) -> dict:
    """이미지와 AO 응답을 받아 교정된 AO JSON을 돌려준다. 유형을 모르면 ValueError."""
    documents = ao.get("documents") or []
    if not documents:
        raise ValueError("AO 응답에 documents가 없습니다.")
    doc_type = doc_type or documents[0].get("doc_type") or documents[0].get("predicted_doc_type")
    if doc_type not in doctypes.DOC_TYPES:
        raise ValueError(f"지원하지 않는 문서 유형입니다: {doc_type}")
    started = time.monotonic()
    _, blocks = parse(image, Path(image).name, "", {"provider": "paddle"})
    result, _ = engine.extract(doctypes.schema(doc_type), blocks, source=image)
    docraft = rules.apply(doc_type, result, blocks)

    ao_flat = flatten(documents[0])
    disputes = {}
    for key, value in ao_flat.items():
        mine = docraft.get(key)
        if isinstance(value, list):
            if not _rows_same(doc_type, key, value, mine):
                disputes[key] = {"ao": value, "docraft": mine or []}
        elif not rules.same(doctypes.kind(doc_type, key), value, mine):
            disputes[key] = {"ao": value, "docraft": mine}
    verdicts = judge(image, doc_type, disputes) if disputes else {}

    output = deepcopy(ao)
    document, counts = output["documents"][0], Counter()
    for key, field in _scalars(document):
        value, source, reason = (_decide(doc_type, key, verdicts.get(key), ao_flat[key], docraft.get(key))
                                 if key in disputes else (ao_flat[key], "agree", None))
        counts[source] += 1
        _annotate(field, value, field.get("value"), docraft.get(key), source, reason)
    for table in document.get("extracted_tables") or []:
        key = table["key"]
        rows, source, reason = (_decide(doc_type, key, verdicts.get(key), ao_flat[key], docraft.get(key) or [], "rows")
                                if key in disputes else (ao_flat[key], "agree", None))
        counts[source] += 1
        table.update(rows=_table_rows(table, rows, docraft.get(key) or [], source, reason), source=source, reason=reason)
    counts = {name: counts[name] for name in SOURCES}
    document["verify"] = {"doc_type": doc_type, "docraft": docraft, "counts": counts}
    logger.info("verify: doc_type=%s fields=%d disputes=%d counts=%s elapsed=%.2fs",
                doc_type, len(ao_flat), len(disputes), counts, time.monotonic() - started)
    return output
