"""AO(Agentic OCR 2.0) 결과를 Docraft 추출 결과와 이미지 기준으로 교차검증·교정한다.

두 결과가 같은 필드는 LLM에 보내지 않고 그대로 확정하고(비용 절감), 어긋나는 필드와 ``rules.run``의
검사·교정 반복 뒤에도 남은 이상 징후만 모아 이미지 1장과 함께 한 번의 LLM 호출(`judge`)로 판정한다. 응답은 입력 AO JSON과
같은 구조에 최종 `value`와 판정 정보(`ao_value`, `docraft_value`, `source`, `reason`)를 덧붙인 것이다.

표는 행 순서·개수가 아니라 키 열(``rules.ROW_KEYS``)로 행을 대응시켜 비교한다 — 대응된 행은 어긋난
셀만, 대응되지 않은 행만 행 단위로 Judge에 알린다(``_row_diff``).

AO 응답은 API 형식(``documents[].extracted_fields/_tables/_groups``)과 UI 형식
(``result.fields/tables/groups``)을 모두 받는다. 형식 판별은 ``document``·``_keys``가 한 곳에서 한다.
"""

import json
import logging
import re
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path

from . import doctypes, engine, rules
from .parsers import parse

logger = logging.getLogger(__name__)

SOURCES = ("agree", "ao", "docraft", "corrected", "unknown")
NO_VERDICT = "판정 결과가 없어 AO 값을 유지했습니다(이미지로 확인되지 않음)."
OUT_OF_SPEC = "유형 정의 밖 key 라 판정하지 않고 AO 값을 유지했습니다."
BLANK_AO = "AO 값이 없는 재추출 요청이라 Docraft 추출값을 그대로 썼습니다."
UNKNOWN = "key도 display_label도 없어 판정 대상에서 제외했습니다."
FORMATS = (("extracted_fields", "extracted_tables", "extracted_groups"),  # API 응답 documents[i]
           ("fields", "tables", "groups"))                                # UI 응답 result
JUDGE_PROMPT = (
    "The image is a Korean medical document of type \"{doc_type}\". Two OCR systems, \"ao\" and \"docraft\", read it "
    "independently and disagree on the fields below, given as JSON {{\"<key>\": {{\"ao\": <value>, \"docraft\": <value>, "
    "\"desc\": <text>}}}}; a table key holds a list of row objects instead of a scalar value and \"desc\" is a "
    "{{\"<column>\": <text>}} map instead, and null means the system read nothing.\n"
    "\"desc\" is that field's (or column's) definition; pick only a value that matches this definition, since a "
    "similar-looking field can be confused for it.\n"
    "\"hint\", when present, is a rule-based warning about what looks wrong in that field: use it to decide what to "
    "re-read in the image, but trust the image over the hint.\n"
    "\"diff\", on a table key, lists only where the two sides disagree after their rows were matched by the table's "
    "key columns: {{\"row\": <index into the \"ao\" rows>, \"column\": <column>, \"ao\": <value>, \"docraft\": <value>}} for a "
    "cell, or the same entry without \"column\" and with one side null for a row only one side read. Re-read those "
    "cells and rows first; still return every row of the table.\n"
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


def document(ao: dict) -> dict:
    """판정 대상 문서. API 형식은 ``documents[0]``, UI 형식은 ``result``."""
    documents = ao.get("documents") if isinstance(ao, dict) else None
    chosen = documents[0] if documents else (ao or {}).get("result")
    if not isinstance(chosen, dict):
        raise ValueError("AO 응답에 documents(또는 result)가 없습니다.")
    return chosen


def _keys(document):
    """문서가 쓰는 필드·표·그룹 목록 키 이름."""
    return next((keys for keys in FORMATS if any(key in document for key in keys)), FORMATS[0])


def _name(element):
    """원소 이름. 그룹·표 접두사(``그룹.키``·``표[0].열``)를 떼고, 비어 있으면 ``display_label``로 대신한다."""
    for source in (element.get("key"), element.get("display_label")):
        name = str(source or "").rpartition(".")[2].strip()
        if name:
            return name
    return None


def _value(field):
    """AO 원소의 값. 비어 있으면 ``predicted_value``로 보충하고, 못 뽑은(``not_extracted``) 원소는 None."""
    if field.get("not_extracted"):
        return None
    for key in ("value", "predicted_value"):
        if (value := field.get(key)) not in (None, ""):
            return value
    return None


def _scalars(document):
    """문서의 스칼라 원소 ``(이름, 원소)``. 그룹 필드도 key가 유일해 같은 평면에 둔다. 이름이 없으면 None."""
    fields, _, groups = _keys(document)
    for field in document.get(fields) or []:
        yield _name(field), field
    for group in document.get(groups) or []:
        for field in group.get("fields") or []:
            yield _name(field), field


def _tables(document):
    """문서의 표 원소 ``(이름, 표)``."""
    for table in document.get(_keys(document)[1]) or []:
        yield _name(table), table


def _cells(table, row):
    """표 한 행의 ``(열 이름, 셀)``. 셀 key가 없으면 ``headers``의 같은 열 위치로 보충한다."""
    headers = table.get("headers") or []
    for index, cell in enumerate(row):
        name = _name(cell) or (headers[index] if index < len(headers) else None)
        if name:
            yield name, cell


def flatten(document: dict) -> dict:
    """AO 문서 → 정규 dict(`doctypes` 참고). 표는 표 이름 → 행 dict 목록. 이름 없는 원소는 뺀다."""
    return {
        **{key: _value(field) for key, field in _scalars(document) if key},
        **{key: [{name: _value(cell) for name, cell in _cells(table, row)} for row in table.get("rows") or []]
           for key, table in _tables(document) if key},
    }


def _add_missing(document, doc_type, only=None):
    """doctypes에 있는데 AO 응답에 아예 없는 필드·표를 빈 원소로 끼운다(``only``가 있으면 그 key만). 판정은 공통 경로가 맡는다."""
    spec, present = doctypes.spec(doc_type), set(flatten(document))
    fields_key, tables_key, _ = _keys(document)
    wanted = lambda key: key not in present and (only is None or key in only)
    new = {
        fields_key: [{"key": key, "value": None, "added": True} for key in spec["fields"] if wanted(key)],
        tables_key: [{"key": key, "headers": list(columns), "rows": [], "added": True}
                     for key, columns in spec["tables"].items() if wanted(key)],
    }
    for key, elements in new.items():
        document[key] = [*(document.get(key) or []), *elements]
    return sum(map(len, new.values()))


def _describe(doc_type, key, entry):
    """분쟁 항목에 필드(스칼라는 desc, 표는 열별 desc 한 번)의 설명을 덧붙인다."""
    spec = doctypes.spec(doc_type)
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


def _row_diff(doc_type, table, ao_rows, docraft_rows):
    """두 표를 키 열(``rules.ROW_KEYS``)로 행 대응시켜 어긋난 곳만 낸다. 빈 목록이면 두 표는 같다.

    대응된 행은 셀 단위로 비교해 다른 셀만 ``{"row", "column", "ao", "docraft"}``로 남기고, 대응되지
    않은 행(누락·과잉)만 없는 쪽이 null인 행 단위 항목으로 남긴다 — 한 행이 어긋나도 표 전체를
    Judge에 다시 쓰게 하지 않는다.
    """
    diff = []
    pairs = rules.pair_rows(doc_type, table, ao_rows or [], docraft_rows or [])
    for index, (mine, theirs) in enumerate(pairs):
        if mine is None or theirs is None:
            diff.append({"row": index, "ao": mine, "docraft": theirs})
            continue
        diff += [{"row": index, "column": column, "ao": mine.get(column), "docraft": theirs.get(column)}
                 for column in dict.fromkeys([*mine, *theirs])
                 if not rules.same(doctypes.kind(doc_type, column, table), mine.get(column), theirs.get(column))]
    return diff


def _decide(doc_type, key, verdict, ao_value, docraft_value, field="value"):
    """판정 하나를 ``(최종값, source, reason)``으로 편다. 판정이 없으면 AO 값을 유지하되 확인된 것이 아니므로 ``unknown``으로 둔다.

    Judge가 ``corrected``로 돌려준 값은 ``rules.apply``에 그 key만 담아 통과시켜 정규화한다
    (표는 합계행 정리·합계 필드 보충도 덤으로 얻는다). 정규화한 값이 AO(또는 Docraft) 값과 같으면
    표기 차이일 뿐이므로 교정으로 세지 않고 해당 쪽 원본 값으로 되돌린다. 정말 둘 다 다를 때만
    정규화된 값으로 ``corrected``에 남는다. 표(``field="rows"``)는 ``_row_diff``가 키 열로 행을 대응시켜 본다.
    """
    if verdict is None:
        return ao_value, "unknown", NO_VERDICT
    source, reason = verdict.get("source"), verdict.get("reason")
    if source == "ao":
        return ao_value, source, reason
    if source == "docraft":
        return docraft_value, source, reason
    value = verdict.get(field, ao_value)
    if field == "rows":
        rows = [row for row in value or [] if isinstance(row, dict)]
        normalized = _agreed(doc_type, key, rules.apply(doc_type, {key: rows}, []).get(key, rows), ao_value, docraft_value)
        if not _row_diff(doc_type, key, normalized, ao_value):
            return ao_value, "ao", reason
        if not _row_diff(doc_type, key, normalized, docraft_value):
            return docraft_value, "docraft", reason
        return normalized, "corrected", reason
    # rules.apply 는 유형 정의에 있는 key 만 돌려준다 — 정의 밖 AO key(진단서 계열 사고발생일자 등)는 판정값 그대로 둔다
    normalized = rules.apply(doc_type, {key: value}, []).get(key, value)
    kind = doctypes.kind(doc_type, key)
    if rules.same(kind, normalized, ao_value):
        return ao_value, "ao", reason
    if rules.same(kind, normalized, docraft_value):
        return docraft_value, "docraft", reason
    return normalized, "corrected", reason


def _agreed(doc_type, key, rows, ao_rows, docraft_rows):
    """Judge가 고친 표에서 AO(룰 교정 뒤)와 Docraft가 같게 읽은 칸은 그 값으로 되돌린다. 두 읽기가 모두 비운 칸에
    인쇄되지 않은 금액을 지어내거나 한쪽만 읽은 열을 통째로 비우는 것을 막는다. 두 읽기 모두와 키 열로 짝지어진 행만 본다."""
    def mates(others):
        return [mate for _, mate in rules.pair_rows(doc_type, key, rows, others or [], fallback=False)[:len(rows)]]

    return [{**row, **{column: ao.get(column) for column in row
                       if rules.same(doctypes.kind(doc_type, column, key), ao.get(column), mine.get(column))}} if ao and mine else row
            for row, ao, mine in zip(rows, mates(ao_rows), mates(docraft_rows))]


def _with_totals(doc_type, key, original, rows):
    """판정에서 뺀 AO 집계 행(소계·계·합계 등)을 판정된 행 목록의 원래 자리 — AO에서 바로 앞 항목 행과
    짝지어진 행 뒤 — 에 되돌린다. 앞 항목 행이 없으면 맨 앞에 둔다."""
    body = [row for row in original if not (isinstance(row, dict) and rules.is_total(row))]
    mates = iter(mate for _, mate in rules.pair_rows(doc_type, key, body, rows, fallback=False)[:len(body)])
    position = {id(row): index for index, row in enumerate(rows)}
    after, anchor = {}, -1
    for row in original:
        if isinstance(row, dict) and rules.is_total(row):
            after.setdefault(anchor, []).append(row)
        else:
            anchor = position.get(id(next(mates)), anchor)
    return after.get(-1, []) + [out for index, row in enumerate(rows) for out in (row, *after.get(index, []))]


def _balance(doc_type, chosen, ao_flat, docraft):
    """판정 결과가 합계식을 어기면 key를 하나씩(표 먼저) AO·Docraft 값으로 바꿔 보고, 불일치가 줄면 그 값을 택한다.

    흐린 숫자를 두 읽기가 다르게 읽었을 때 Judge가 합계식에 안 맞는 쪽을 고르는 경우를 되돌린다. 불일치가
    줄 때만 바꾸므로 합계식과 무관한 key나 이미 맞는 판정은 그대로다. 빈 값으로는 바꾸지 않는다(검사할 식이
    사라져 불일치가 준 것처럼 보인다). ``chosen``은 key → ``(값, source, reason)``.
    """
    def errors(**changed):
        return rules.sum_errors(doc_type, {**ao_flat, **{key: value for key, (value, _, _) in chosen.items()}, **changed})

    count = errors()
    for key in sorted(chosen, key=lambda key: not isinstance(chosen[key][0], list)):
        if not count:
            break
        value, source, _ = chosen[key]
        for side, other in (("ao", ao_flat.get(key)), ("docraft", _with_ao_names(doc_type, key, docraft.get(key), ao_flat.get(key)))):
            if side == source or other in (None, "", []) or other == value or (trial := errors(**{key: other})) >= count:
                continue
            chosen[key] = (other, side, f"합계식: 판정 값은 불일치 {count}건, {side} 값은 {trial}건이라 {side} 값을 택했다")
            count = trial
            break
    return chosen


def _with_ao_names(doc_type, key, rows, ao_rows):
    """Docraft 표에서 AO 행과 짝지어진 행의 이름 열(``ROW_KEYS`` 중 text 열, 영수증 ``항목``)은 AO 값으로 둔다.

    합계식은 금액만 따지므로 ``_balance``가 표를 통째로 Docraft 쪽으로 바꾸면 Docraft가 달리 적은 항목명
    ('투약및조제료_약품비' → '조제료약품비')까지 따라 들어와 행이 통째로 틀린다. 코드·날짜 열·유형 정의 밖 열은
    Docraft가 바로 고친 값일 수 있어 건드리지 않는다. 합계 행과, 행 수가 다른 표의 순서 짝은 제외한다.
    """
    if not isinstance(rows, list) or not isinstance(ao_rows, list) or not ao_rows:
        return rows
    columns = doctypes.spec(doc_type)["tables"].get(key, {})
    names = [column for column in rules.ROW_KEYS.get(key, ())
             if column in columns and doctypes.kind(doc_type, column, key) == "text"]
    if not names:
        return rows
    index = {id(row): position for position, row in enumerate(rows)}
    out = [dict(row) for row in rows]
    for mine, ao in rules.pair_rows(doc_type, key, rows, ao_rows):
        # 합계·소계 행은 이름이 곧 행의 역할이다 — 본문 행과 이름을 주고받으면 합계식이 틀어진다
        if mine is None or ao is None or rules.is_total(mine) or rules.is_total(ao):
            continue
        # 순서로만 이어진 짝(fallback)은 한쪽 이름이 다른 쪽에 들어 있을 때만 같은 항목으로 본다
        # ('조제료약품비' ⊂ '투약및조제료약품비'). Docraft 가 행을 빠뜨리고 다른 행을 더했으면 이름이 전혀 다르다.
        if not all(_same_item(mine.get(column), ao.get(column)) for column in names):
            continue
        out[index[id(mine)]].update({column: ao[column] for column in names if ao.get(column) not in (None, "")})
    return out


def _same_item(mine, ao):
    """두 이름이 같은 항목을 가리키는가 — 기호를 뗀 한쪽이 다른 쪽에 들어 있다(둘 다 비었거나 한쪽이 비면 참)."""
    a, b = (re.sub(r"[\W_]+", "", str(value or "")) for value in (mine, ao))
    return not a or not b or a in b or b in a


def _annotate(element, value, ao_value, docraft_value, source, reason):
    """AO 원소에 최종값과 판정 정보를 덧붙인다. ``predicted_value``도 최종값으로 맞춘다 — 빈 ``value``를
    ``predicted_value``로 채워 읽는 쪽(``_value``)이 AO의 옛 값을 보지 않게 한다. AO 값은 ``ao_value``에 남는다."""
    element.update(value=value, ao_value=ao_value, docraft_value=docraft_value, source=source, reason=reason)
    if "predicted_value" in element:
        element["predicted_value"] = value
    return element


def _mates(doc_type, key, rows, others):
    """rows 각 행과 짝이 되는 others의 행(``rules.pair_rows``, 남은 행은 순서대로). 짝이 없으면 None."""
    return [mate for _, mate in rules.pair_rows(doc_type, key, rows, others)[:len(rows)]]


def mark_review(doc_type, document, checks_after, only=None):
    """자동 통과시키지 않을 칸에 ``review: true``를 붙이고 ``{"cells": 판정한 칸 수, "review": 그중 검토 칸 수}``를 돌려준다.
    AO와 Docraft가 다르게 읽은 칸(Judge가 골랐어도)과, 최종값에 남은 계산·구조 이상(CALC·STRUCT 룰)이 가리키는
    행·열(행 번호가 없으면 그 필드·표 전체, 표 원소에도 붙인다 — 빠진 행은 칸이 없다)이다."""
    category = {rule.id: rule.category for rule in rules.RULES}
    broken = [flag for flag in checks_after if category.get(flag.get("rule")) in ("CALC", "STRUCT")]
    counts = Counter()

    def mark(element, kind, key, row=None, column=None):
        if "ao_value" not in element:  # 판정하지 않은 원소(힌트 밖·이름 없음)
            return
        hit = any(flag["key"] == key and flag.get("row") in (None, row) and flag.get("column") in (None, column) for flag in broken)
        if hit or not rules.same(kind, element["ao_value"], element["docraft_value"], strict=True):
            element["review"] = True
        counts["cells"] += 1
        counts["review"] += bool(element.get("review"))

    for key, field in _scalars(document):
        if key and (only is None or key in only):
            mark(field, doctypes.kind(doc_type, key), key)
    for key, table in _tables(document):
        if key and (only is None or key in only):
            if any(flag["key"] == key and flag.get("row") is None and flag.get("column") is None for flag in broken):  # 빠진 행은 칸이 없어 표로 표시한다
                table["review"] = True
            for index, row in enumerate(table.get("rows") or []):
                for column, cell in _cells(table, row):
                    mark(cell, doctypes.kind(doc_type, column, key), key, index, column)
    return dict(counts)


def _table_rows(doc_type, key, table, rows, docraft_rows, source, reason):
    """판정된 행 목록을 AO 원소 형식으로 되돌린다. 행마다 짝이 되는 원래 행의 셀에서 confidence 등을 보존한다.

    자리 번호로 잇지 않는다 — 판정이 행을 끼우면 뒤쪽 행이 다른 행의 셀(예측값)을 물려받는다.
    """
    originals = [dict(_cells(table, row)) for row in table.get("rows") or []]
    rows = [row for row in rows or [] if isinstance(row, dict)]
    columns = table.get("headers") or list(dict.fromkeys(column for row in rows for column in row))
    # 판정이 늘린 행에는 원래 셀이 없으므로 같은 열 셀의 형식만 빌리고 값은 모두 비운다.
    blanks = {column: {name: None for name in cell} for row in reversed(originals) for column, cell in row.items()}
    flats = [{name: _value(cell) for name, cell in original.items()} for original in originals]
    position = {id(flat): index for index, flat in enumerate(flats)}
    mates = _mates(doc_type, key, rows, flats)
    docraft_mates = _mates(doc_type, key, rows, docraft_rows)
    out = []
    for row, mate, docraft_row in zip(rows, mates, docraft_mates):
        original = originals[position[id(mate)]] if mate is not None else {}
        docraft_row = docraft_row or {}
        cells = []
        for column in columns:
            cell = {**blanks.get(column, {}), **original.get(column, {})}
            cell["key"] = cell.get("key") or column
            cells.append(_annotate(cell, row.get(column), original.get(column, {}).get("value"),
                                   docraft_row.get(column), source, reason))
        out.append(cells)
    return out


def _restrict(schema, only):
    """스키마를 ``only`` key로만 좁힌다(추출 비용 절감). ``only``가 None이면 그대로."""
    if only is None:
        return schema
    return {**schema, "properties": {key: prop for key, prop in schema["properties"].items() if key in only},
            "required": [key for key in schema["required"] if key in only]}


class Cancelled(Exception):
    """호출자가 ``cancel``을 세워 교차검증을 중단했다(예: 클라이언트 연결 끊김)."""


def _check(cancel):
    """``cancel``이 세워졌으면 다음 단계(추출·Judge LLM 호출)로 넘어가지 않고 멈춘다."""
    if cancel is not None and cancel.is_set(): raise Cancelled


def run(image: str, ao: dict, doc_type: str | None = None, hint_paths: list[str] | None = None, cancel=None) -> dict:
    """이미지와 AO 응답(API·UI 형식)을 받아 교정된 AO JSON을 돌려준다. 유형을 모르면 ValueError.

    ``hint_paths``를 주면(비어 있지 않은 목록) 그 key(필드·표 key)만 비교·Judge 대상으로 삼고, 추출
    스키마도 그만큼 좁힌다. 나머지 필드·표는 AO 입력 그대로 돌아가며 ``source``·``reason`` 등 판정
    정보가 붙지 않는다 — 그 유무로 호출자가 판정 여부를 가릴 수 있다. 정의에 없는 key는 무시하고
    한 번 경고 로그를 남긴다. 유효한 key가 하나도 없으면(모두 정의 밖) 파싱·추출 전에 ValueError.

    ``cancel``(``threading.Event``)이 세워지면 추출·Judge 직전에 ``Cancelled``로 멈춘다 — 진행 중인 호출은 끝까지 간다.
    """
    given = document(ao)
    doc_type = doc_type or given.get("doc_type") or given.get("predicted_doc_type")
    doc_type = doctypes.ALIASES.get(doc_type, doc_type)
    if doc_type not in doctypes.DOC_TYPES:
        raise ValueError(f"지원하지 않는 문서 유형입니다: {doc_type}")
    only = None
    if hint_paths:
        spec = doctypes.spec(doc_type)
        known = {*spec["fields"], *spec["tables"]}
        only, unknown = {key for key in hint_paths if key in known}, {key for key in hint_paths if key not in known}
        if unknown:
            logger.warning("verify: hint_paths에 알 수 없는 key가 있습니다: %s", sorted(unknown))
        if not only:  # 유효한 key가 하나도 없으면 파싱·추출 전에 끊는다(route가 ValueError를 422로 옮긴다)
            raise ValueError(f"hint_paths에 {doc_type}에 정의된 key가 없습니다: {sorted(hint_paths)}")
    started = time.monotonic()
    _, blocks = parse(image, Path(image).name, "", {"provider": "paddle"})
    _check(cancel)
    result, _ = engine.extract(_restrict(doctypes.schema(doc_type), only), blocks, source=image)
    docraft = rules.apply(doc_type, result, blocks)

    output = deepcopy(ao)
    target = document(output)
    added = _add_missing(target, doc_type, only)
    ao_flat = flatten(target)
    totals = {}  # Docraft가 집계 행을 뽑지 않는 유형은 AO의 인쇄된 집계 행을 판정에서 빼 두었다가 되돌린다
    if doc_type not in rules.KEEP_TOTALS:
        for key, value in ao_flat.items():
            if isinstance(value, list) and any(isinstance(row, dict) and rules.is_total(row) for row in value):
                totals[key], ao_flat[key] = value, [row for row in value if not (isinstance(row, dict) and rules.is_total(row))]
    # 확실한 이상은 Judge 없이 룰로 교정하기를 되풀이하고, 그 뒤에도 남은 이상만 Judge에 알린다
    fixes, history, trace = rules.run(doc_type, ao_flat, docraft, blocks)
    checks = history[0]
    ao_flat.update({key: value for key, (value, _) in fixes.items()})
    hints = {}
    for flag in history[-1]:
        hints.setdefault(flag["key"], []).append(flag["message"])

    spec = doctypes.spec(doc_type)
    known = {*spec["fields"], *spec["tables"]}
    # AO 값이 하나도 없으면(하네스 서식 재분류의 재추출 요청) 다툴 AO 값이 없다 — Judge 없이 Docraft 추출값을 쓴다.
    # Judge 가 원소를 빠뜨리면 Docraft 값이 버려지고, 긴 표를 통째로 되풀이하게 해 시간·절단 위험만 는다.
    blank = all(value in (None, "", []) for value in ao_flat.values())
    disputes = {}
    for key, value in ao_flat.items():
        if only is not None and key not in only:
            continue
        if known and key not in known:  # 유형 정의 밖 AO key(진단서 계열 사고발생일자 등) — Docraft 값이 없어 다툼이 성립하지 않는다
            continue
        mine, rows = docraft.get(key), isinstance(value, list)
        diff = _row_diff(doc_type, key, value, mine) if rows else None
        if diff or (not rows and not rules.same(doctypes.kind(doc_type, key), value, mine)) or key in hints:
            disputes[key] = {"ao": value, "docraft": (mine or []) if rows else mine,
                             **({"diff": diff} if diff else {}),
                             **({"hint": " ".join(hints[key])} if key in hints else {})}
    _check(cancel)
    if blank:
        verdicts = {key: {"source": "docraft", "reason": BLANK_AO} for key in disputes}
    else:
        verdicts = judge(image, doc_type, disputes) if disputes else {}

    def resolve(key, value, field="value"):
        """판정·룰 교정을 합쳐 ``(최종값, source, reason)``. 룰이 고친 값을 Judge가 받아들이면 corrected로 남긴다."""
        if known and key not in known:
            return value, "unknown", OUT_OF_SPEC
        chosen = (_decide(doc_type, key, verdicts.get(key), value, docraft.get(key) or ([] if field == "rows" else None), field)
                  if key in disputes else (value, "agree", None))
        if key in fixes and chosen[1] in ("agree", "ao", "unknown"):
            return chosen[0], "corrected", " / ".join(filter(None, (fixes[key][1], chosen[2])))
        return chosen

    chosen = _balance(doc_type, {key: resolve(key, value, "rows" if isinstance(value, list) else "value")
                                 for key, value in ao_flat.items() if only is None or key in only}, ao_flat, docraft)
    for key in set(totals) & set(chosen):
        value, source, reason = chosen[key]
        chosen[key] = (_with_totals(doc_type, key, totals[key], value), source, reason)
    counts, final = Counter(), {}
    for key, field in _scalars(target):
        if not key:
            counts["unknown"] += 1
            field.update(source="unknown", reason=UNKNOWN)
            continue
        if only is not None and key not in only:  # 힌트 밖 필드는 AO 값 그대로, 판정 정보 없이 둔다
            continue
        final[key], source, reason = chosen[key]
        counts[source] += 1
        _annotate(field, final[key], field.get("value"), docraft.get(key), source, reason)
    for key, table in _tables(target):
        if not key:
            counts["unknown"] += 1
            table.update(source="unknown", reason=UNKNOWN)
            continue
        if only is not None and key not in only:
            continue
        final[key], source, reason = chosen[key]
        counts[source] += 1
        table.update(rows=_table_rows(doc_type, key, table, final[key], docraft.get(key) or [], source, reason),
                     source=source, reason=reason)
    counts = {**{name: counts[name] for name in SOURCES}, "added": added}
    _, (checks_after,), last = rules.run(doc_type, {**ao_flat, **final}, docraft, blocks, rounds=0)
    trace += [{**entry, "round": "final"} for entry in last]
    escalate = {entry["rule"] for entry in last if entry["action"] == "ESCALATE"}
    review = {flag["key"] for flag in checks_after if flag["rule"] in escalate and (only is None or flag["key"] in only)}
    for key, element in (*_scalars(target), *_tables(target)):  # 최종값에도 남은 ESCALATE 이상은 사람이 본다
        if key in review:
            element["review"] = True
    target["verify"] = {"doc_type": doc_type, "docraft": docraft, "counts": counts, "checks": checks,
                        "checks_after": checks_after, "trace": trace,
                        "review": mark_review(doc_type, target, checks_after, only)}
    logger.info("verify: doc_type=%s fields=%d disputes=%d checks=%d counts=%s elapsed=%.2fs",
                doc_type, len(ao_flat), len(disputes), len(checks), counts, time.monotonic() - started)
    return output
