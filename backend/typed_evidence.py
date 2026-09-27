"""Field-specific OCR evidence; conversions retain the printed token and its role."""

import re
import math

from . import doctypes, rules


_MARKED = set("✓✔√☑■●▣")
_EMPTY_BOX = set("□☐○")
_RANGES = ("진료기간", "입원기간", "입원치료기간", "입퇴원일", "통원기간")


def valid(source, value):
    """A typed claim must bind one value to a page-local source token or a verified empty cell."""
    if not isinstance(source, dict) or source.get("verified") is not True or not source.get("label"):
        return False
    box, size, page = source.get("bbox"), source.get("page_size"), source.get("page")
    if (not isinstance(page, int) or page < 1 or not isinstance(box, (list, tuple)) or len(box) != 4
            or not isinstance(size, (list, tuple)) or len(size) != 2
            or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in (*box, *size))
            or not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1])):
        return False
    evidence, transform, role = (source.get(key) for key in ("evidence_type", "transform", "role"))
    printed, bound = source.get("source_text"), source.get("normalized_value")
    if evidence == "table_blank":
        return (value is None and bound is None and printed == "" and source.get("match") == "blank"
                and transform == "blank_to_null" and role in {"field_cell", "total_cell", "data_cell"}
                and source.get("geometry_scope") == "cell")
    if value is None or source.get("match") != "typed" or not isinstance(printed, str) or not printed:
        return False
    if evidence == "checkbox_mark":
        return (transform == "checkbox_to_bool" and role in {"checked", "unchecked"}
                and printed in (_MARKED if role == "checked" else _EMPTY_BOX)
                and bound == ("Y" if role == "checked" else "N") == rules.normalize("bool", value))
    if evidence in {"date_equivalent", "date_range_start", "date_range_end"}:
        expected_role = "direct" if evidence == "date_equivalent" else evidence.rsplit("_", 1)[1]
        expected_transform = "date_ymd" if expected_role == "direct" else f"range_{expected_role}"
        return (role == expected_role and transform == expected_transform
                and bound == rules.normalize("date", printed) == rules.normalize("date", value))
    if evidence == "table_cell":
        kind = transform.removesuffix("_normalize") if isinstance(transform, str) else None
        return (kind in {"amount", "number"} and transform == f"{kind}_normalize"
                and role in {"total_cell", "data_cell"} and source.get("geometry_scope") == "cell"
                and bound == rules.normalize(kind, printed) == rules.normalize(kind, value))
    return False


def _compact(text):
    return re.sub(r"\s+", "", str(text or ""))


def _segments(blocks):
    for block in blocks:
        if block.get("lines"):
            for line in block["lines"]:
                if line.get("bbox"):
                    yield block, line["text"], line["bbox"], "line"
        elif (block.get("bbox") and "<table" not in block.get("text", "").lower()
              and len(block.get("text", "")) <= 120 and "\n" not in block.get("text", "")
              and len(block.get("rows") or []) <= 1):
            yield block, block.get("text", ""), block["bbox"], "block"


def _field_segments(key, blocks):
    yield from _segments(blocks)
    labels = [_compact(label) for label in _labels(key)]
    other_labels = {_compact(label) for spec in doctypes.DOC_TYPES.values()
                    for other in spec["fields"] if other != key
                    for label in rules.LABELS.get(other, (other,)) if len(_compact(label)) >= 3}
    for block in blocks:
        lines = [line for line in block.get("lines") or [] if line.get("bbox")]
        for anchor in lines:
            if not any(label in _compact(anchor.get("text")) for label in labels):
                continue
            box = anchor["bbox"]
            height = max(1, box[3] - box[1])
            right = sorted((line for line in lines if line is not anchor
                            and line["bbox"][0] >= box[2] - height / 3
                            and abs((line["bbox"][1] + line["bbox"][3] - box[1] - box[3]) / 2) <= height / 2),
                           key=lambda line: line["bbox"][0])
            selected, edge = [], box[2]
            for line in right:
                if line["bbox"][0] - edge > 8 * height:
                    break
                if any(label in _compact(line.get("text")) for label in other_labels) and not any(
                    label in _compact(line.get("text")) for label in labels
                ):
                    break
                selected.append(line)
                edge = max(edge, line["bbox"][2])
            if selected:
                area = [min([box[0], *(line["bbox"][0] for line in selected)]),
                        min([box[1], *(line["bbox"][1] for line in selected)]),
                        max([box[2], *(line["bbox"][2] for line in selected)]),
                        max([box[3], *(line["bbox"][3] for line in selected)])]
                yield block, " ".join([anchor["text"], *(line["text"] for line in selected)]), area, "line_group"


def _labels(key):
    return sorted({*rules.LABELS.get(key, ()), key}, key=len, reverse=True)


def _date_tokens(text):
    tokens = []
    for found in rules._DATE.finditer(text):
        date = rules.normalize("date", found.group())
        if date:
            tokens.append((date, found.group().strip()))
    return tokens


def _date_role(key, label):
    if not any(word in label for word in _RANGES):
        return "direct"
    if "종료" in key or "퇴원" in key:
        return "end"
    if "시작" in key or "입원" in key:
        return "start"
    return None


def _proof(block, box, token, label, evidence_type, transform, role, scope, normalized_value):
    return {"confidence": 1.0, "page": block.get("page"), "bbox": box,
            "page_size": block.get("page_size"), "source_text": token, "match": "typed",
            "evidence_type": evidence_type, "transform": transform, "role": role,
            "label": label, "geometry_scope": scope, "normalized_value": normalized_value,
            "verified": True, "basis": "ocr_typed"}


def scalar(key, value, kind, blocks, bool_labels=()):
    """A unique labelled date or explicit checkbox mark, never a date inferred from an unrelated field."""
    if value is None or kind not in {"date", "bool"}:
        return None
    expected = rules.normalize(kind, value)
    if expected is None:
        return None
    found = []
    for block, text, box, scope in _field_segments(key, blocks):
        compact = _compact(text)
        labels = [label for label in _labels(key) if _compact(label) in compact]
        if not labels:
            continue
        label = labels[0]
        if kind == "date":
            tokens = _date_tokens(text)
            role = _date_role(key, label)
            if role is None or (role in {"start", "end"} and len(tokens) != 2):
                continue
            if role == "direct" and len(tokens) != 1:
                continue
            date, token = tokens[0 if role != "end" else -1]
            if date == expected:
                evidence_type = "date_equivalent" if role == "direct" else f"date_range_{role}"
                transform = "date_ymd" if role == "direct" else f"range_{role}"
                found.append(_proof(block, box, token, label, evidence_type, transform, role, scope, expected))
        else:
            spans = [(other, at, at + len(_compact(other))) for other in bool_labels
                     for at in [compact.find(_compact(other))] if at >= 0]
            owned = []
            for pos, mark in enumerate(compact):
                if mark not in _MARKED | _EMPTY_BOX:
                    continue
                distances = [(max(start - pos - 1, pos - end, 0), other) for other, start, end in spans]
                nearest = min((distance for distance, _ in distances), default=99)
                winners = {other for distance, other in distances if distance == nearest}
                if nearest <= 2 and winners == {label}:
                    owned.append(mark)
            if len(owned) != 1:
                continue
            mark = owned[0]
            role = "checked" if mark in _MARKED else "unchecked"
            if expected == ("Y" if role == "checked" else "N"):
                found.append(_proof(block, box, mark, label, "checkbox_mark", "checkbox_to_bool", role, scope, expected))
    if any(item["geometry_scope"] == "line" for item in found):
        found = [item for item in found if item["geometry_scope"] == "line"]
    unique = {(item["page"], tuple(item["bbox"]), item["source_text"], item["role"]): item for item in found
              if isinstance(item.get("page"), int) and item.get("page_size")}
    return next(iter(unique.values())) if len(unique) == 1 else None


def _cells(block):
    return [cell for cell in block.get("cells") or [] if isinstance(cell, dict)
            and isinstance(cell.get("row"), int) and isinstance(cell.get("column"), int)]


def _physical(cell):
    return (cell.get("verified") is True and cell.get("rowspan", 1) == 1
            and cell.get("colspan", 1) == 1 and isinstance(cell.get("bbox"), (list, tuple))
            and len(cell["bbox"]) == 4 and isinstance(cell.get("page"), int))


def _table_row(row, source_rows):
    """A unique printed item/total row; never assume extraction and OCR row indexes coincide."""
    name = row.get("항목") if isinstance(row, dict) else None
    if not name:
        return None
    total = rules.is_total({"항목": name})
    matches = [index for index, source in enumerate(source_rows)
               if (total and any(rules.is_total({"항목": cell}) for cell in source)
                   or not total and any(rules.item(cell) == rules.item(name) for cell in source if cell))]
    return matches[0] if len(matches) == 1 else None


def _column(block, row, key, group=None):
    """A unique unmerged leaf header above the data row; group titles cannot name a leaf."""
    if not group and key in rules.GROUPED and any(
        any(_compact(sub) in _compact(cell.get("text")) for sub in rules.GROUPED[key][1])
        for cell in _cells(block) if cell["row"] < row
    ):
        return None
    aliases = {_compact(key), _compact(key.removesuffix("금")), _compact(key.replace("금", "액")),
               _compact(key + "금"), _compact(key + "액")}
    aliases.discard("")
    if group:
        parents = [cell for cell in _cells(block) if cell["row"] < row
                   and _compact(cell.get("text")) in aliases]
        children = [cell for cell in _cells(block) if cell["row"] < row and cell.get("colspan", 1) == 1
                    and _compact(cell.get("text")) == _compact(group)]
        pairs = [(child["column"], parent["text"]) for parent in parents for child in children
                 if parent["row"] < child["row"]
                 and parent["column"] <= child["column"] < parent["column"] + parent.get("colspan", 1)]
        return pairs[0] if len(pairs) == 1 else None
    candidates = [cell for cell in _cells(block) if cell["row"] < row and cell.get("colspan", 1) == 1
                  and _compact(cell.get("text")) in aliases]
    columns = {cell["column"] for cell in candidates}
    return (next(iter(columns)), max(candidates, key=lambda cell: cell["row"])["text"]) if len(columns) == 1 else None


def _table_proofs(table, index, key, value, kind, blocks, rows):
    found = []
    for block in blocks:
        source_rows = block.get("rows") or []
        if not _cells(block) or not source_rows:
            continue
        source_row = _table_row(rows[index], source_rows)
        if source_row is None:
            continue
        selected = _column(block, source_row, key)
        if selected is None:
            continue
        col, label = selected
        targets = [cell for cell in _cells(block) if cell["row"] == source_row and cell["column"] == col and _physical(cell)]
        if len(targets) != 1:
            continue
        cell = targets[0]
        if cell.get("blank") is True and value is None:
            proof = _proof(block, cell["bbox"], "", label, "table_blank", "blank_to_null",
                           "total_cell" if rules.is_total(rows[index]) else "data_cell", "cell", None)
            proof["match"] = "blank"
            proof["basis"] = "image_cell_blank"
        elif cell.get("blank") is False and value is not None and kind in {"amount", "number"}:
            printed = str(cell.get("text") or "")
            normalized = rules.normalize(kind, printed)
            if not printed or normalized is None or normalized != rules.normalize(kind, value):
                continue
            proof = _proof(block, cell["bbox"], printed, label, "table_cell", f"{kind}_normalize",
                           "total_cell" if rules.is_total(rows[index]) else "data_cell", "cell", normalized)
        else:
            continue
        proof.update(row=source_row, column=col)
        found.append(proof)
    return found[0] if len(found) == 1 else None


def _field_blank(key, blocks):
    labels = {_compact(label) for label in _labels(key) if len(_compact(label)) >= 4}
    found = []
    for block in blocks:
        cells = _cells(block)
        for label_cell in cells:
            if _compact(label_cell.get("text")) not in labels:
                continue
            next_col = label_cell["column"] + label_cell.get("colspan", 1)
            targets = [cell for cell in cells if cell["row"] == label_cell["row"] and cell["column"] == next_col
                       and _physical(cell) and cell.get("blank") is True]
            if len(targets) == 1:
                cell = targets[0]
                proof = _proof(block, cell["bbox"], "", label_cell["text"], "table_blank",
                               "blank_to_null", "field_cell", "cell", None)
                proof["match"] = "blank"
                proof["basis"] = "image_cell_blank"
                proof.update(row=cell["row"], column=cell["column"])
                found.append(proof)
    return found[0] if len(found) == 1 else None


def _scalar_total(doc_type, key, value, kind, blocks):
    """Bind a scalar total only to the printed total row and its unique leaf column."""
    columns = [(table, column) for table, mapping in rules.TOTALS.get(doc_type, {}).items()
               for column, field in mapping.items() if field == key]
    found = []
    for table, column in columns:
        for block in blocks:
            rows = block.get("rows") or []
            if not _cells(block) or not rows:
                continue
            totals = [index for index, row in enumerate(rows)
                      if any(rules.is_total({"항목": cell}) for cell in row)]
            if len(totals) != 1:
                continue
            row = totals[0]
            selected = _column(block, row, column, "급여" if key.startswith("급여_") else None)
            if selected is None:
                continue
            col, label = selected
            cells = [cell for cell in _cells(block) if cell["row"] == row and cell["column"] == col and _physical(cell)]
            if len(cells) != 1:
                continue
            cell = cells[0]
            if cell.get("blank") is True and value is None:
                proof = _proof(block, cell["bbox"], "", label, "table_blank", "blank_to_null",
                               "total_cell", "cell", None)
                proof["match"] = "blank"
                proof["basis"] = "image_cell_blank"
            elif cell.get("blank") is False and value is not None and kind in {"amount", "number"}:
                printed = str(cell.get("text") or "")
                normalized = rules.normalize(kind, printed)
                if not printed or normalized is None or normalized != rules.normalize(kind, value):
                    continue
                proof = _proof(block, cell["bbox"], printed, label, "table_cell", f"{kind}_normalize",
                               "total_cell", "cell", normalized)
            else:
                continue
            proof.update(table=table, row=row, column=col)
            found.append(proof)
    return found[0] if len(found) == 1 else None


def augment(result, schema, blocks, groundings):
    """Add typed proof to known medical scalar fields; generic schemas keep their existing grounding."""
    doc_type = schema.get("title")
    if doc_type not in doctypes.DOC_TYPES:
        return groundings
    spec = doctypes.spec(doc_type)
    definitions = spec["fields"]
    bool_labels = tuple(key for key, meta in definitions.items() if meta["kind"] == "bool")
    for key, value in result.items():
        if key in definitions and not isinstance(value, (dict, list)):
            kind = definitions[key]["kind"]
            proof = (_field_blank(key, blocks) if value is None else scalar(key, value, kind, blocks, bool_labels))
            proof = proof or _scalar_total(doc_type, key, value, kind, blocks)
            if proof:
                groundings[key] = proof
        elif isinstance(value, list) and key in spec["tables"]:
            columns = spec["tables"][key]
            for index, row in enumerate(value):
                if not isinstance(row, dict):
                    continue
                for column, cell_value in row.items():
                    if column in columns:
                        proof = _table_proofs(key, index, column, cell_value, columns[column]["kind"], blocks, value)
                        if proof:
                            groundings.setdefault(key, {}).setdefault(str(index), {})[column] = proof
    return groundings
