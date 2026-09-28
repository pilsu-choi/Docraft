"""Field-specific OCR evidence; conversions retain the printed token and its role."""

import re
import math
from decimal import Decimal, InvalidOperation

from . import doctypes, rules


_MARKED = set("✓✔√☑■●▣")
_EMPTY_BOX = set("□☐○")
_RANGES = ("진료기간", "입원기간", "입원치료기간", "입퇴원일", "통원기간")
_AMOUNT_TOKEN = re.compile(r"(?<![0-9A-Za-z])[-−]?\d[\d,]*(?:\.\d+)?(?![0-9A-Za-z])")


def _geometry(source):
    box, size, page = source.get("bbox"), source.get("page_size"), source.get("page")
    return (isinstance(page, int) and page >= 1 and isinstance(box, (list, tuple)) and len(box) == 4
            and isinstance(size, (list, tuple)) and len(size) == 2
            and all(isinstance(n, (int, float)) and math.isfinite(n) for n in (*box, *size))
            and 0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1])


def _derived(source, value):
    evidence, operation = source.get("evidence_type"), source.get("operation")
    terms = source.get("terms")
    if (source.get("verified") is not True or source.get("match") != "derived"
            or source.get("bbox") is not None or source.get("source_text") is not None
            or not isinstance(terms, list) or not terms or len(terms) > 8):
        return False
    paths = [term.get("path") for term in terms if isinstance(term, dict)]
    if len(paths) != len(terms) or len(set(paths)) != len(paths) or any(not isinstance(p, str) or not p for p in paths):
        return False
    allowed = ({"labelled_amount", "table_cell", "aligned_amount"} if evidence == "derived_sum"
               else {"date_equivalent", "date_range_start"} if evidence == "schema_alias" else set())
    for term in terms:
        proof = term.get("provenance")
        if (not isinstance(proof, dict) or proof.get("field_key") != term["path"]
                or proof.get("evidence_type") not in allowed
                or evidence == "derived_sum" and proof.get("evidence_type") == "table_cell"
                and proof.get("transform") != "amount_normalize"
                or not valid(proof, term.get("normalized_value"))):
            return False
    if evidence == "derived_sum":
        relation = rules.FIELD_SUMS.get(source.get("target_field"), ())
        if (operation != "sum" or source.get("basis") != "calculation" or len(terms) < 2
                or len(relation) != len(paths) or set(paths) != set(relation)
                or source.get("doc_type") not in doctypes.DOC_TYPES
                or source.get("target_field") not in doctypes.spec(source["doc_type"])["fields"]):
            return False
        try:
            amounts = [Decimal(rules.normalize("amount", term["normalized_value"])) for term in terms]
            total = Decimal(rules.normalize("amount", value))
            bound = Decimal(rules.normalize("amount", source.get("normalized_value")))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return total == bound == sum(amounts)
    if evidence == "schema_alias":
        source_key = doctypes.SCHEMA_ALIASES.get(source.get("doc_type"), {}).get(source.get("target_path"))
        return (operation == "schema_date_alias" and source.get("basis") == "schema_rule"
                and source_key == paths[0] and len(terms) == 1
                and rules.normalize("date", terms[0]["normalized_value"]) is not None
                and rules.normalize("date", terms[0]["normalized_value"])
                == rules.normalize("date", source.get("normalized_value"))
                == rules.normalize("date", value))
    return False


def valid(source, value):
    """A typed claim must bind one value to a page-local source token or a verified empty cell."""
    if not isinstance(source, dict):
        return False
    if source.get("evidence_type") in {"derived_sum", "schema_alias"}:
        return _derived(source, value)
    if source.get("verified") is not True or not source.get("label") or not _geometry(source):
        return False
    evidence, transform, role = (source.get(key) for key in ("evidence_type", "transform", "role"))
    printed, bound = source.get("source_text"), source.get("normalized_value")
    if evidence == "table_blank":
        scope = source.get("geometry_scope")
        polygon = source.get("polygon")
        if scope == "rotated_cell_hull":
            if (source.get("blank_method") != "deskewed_closed_cell_noise_floor_v1"
                    or not isinstance(polygon, list) or len(polygon) != 4
                    or not 0.1 <= abs(source.get("rotation_degrees", 0)) <= 3):
                return False
            if (any(not isinstance(point, list) or len(point) != 2
                    or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in point)
                    or not 0 <= point[0] <= source["page_size"][0]
                    or not 0 <= point[1] <= source["page_size"][1] for point in polygon)
                    or [min(point[0] for point in polygon), min(point[1] for point in polygon),
                        max(point[0] for point in polygon), max(point[1] for point in polygon)] != source["bbox"]):
                return False
            crosses = [((polygon[(i + 1) % 4][0] - polygon[i][0])
                        * (polygon[(i + 2) % 4][1] - polygon[(i + 1) % 4][1])
                        - (polygon[(i + 1) % 4][1] - polygon[i][1])
                        * (polygon[(i + 2) % 4][0] - polygon[(i + 1) % 4][0]))
                       for i in range(4)]
            if len({tuple(point) for point in polygon}) != 4 or not (all(n > 0 for n in crosses) or all(n < 0 for n in crosses)):
                return False
        elif scope != "cell" or source.get("blank_method") not in {"closed_cell_noise_floor_v1", "closed_cell"}:
            return False
        return (value is None and bound is None and printed == "" and source.get("match") == "blank"
                and transform == "blank_to_null" and role in {"field_cell", "total_cell", "data_cell"}
                and source.get("field_key"))
    if value is None or source.get("match") not in {"typed", "inferred"} or not isinstance(printed, str) or not printed:
        return False
    if evidence == "checkbox_mark":
        return (source.get("match") == "typed" and transform == "checkbox_to_bool" and role in {"checked", "unchecked"}
                and printed in (_MARKED if role == "checked" else _EMPTY_BOX)
                and bound == ("Y" if role == "checked" else "N") == rules.normalize("bool", value))
    if evidence in {"date_equivalent", "date_range_start", "date_range_end"}:
        expected_role = "direct" if evidence == "date_equivalent" else evidence.rsplit("_", 1)[1]
        expected_transform = "date_ymd" if expected_role == "direct" else f"range_{expected_role}"
        return (source.get("match") == "typed" and role == expected_role and transform == expected_transform
                and rules.normalize("date", printed) is not None
                and bound == rules.normalize("date", printed) == rules.normalize("date", value))
    if evidence == "table_cell":
        kind = transform.removesuffix("_normalize") if isinstance(transform, str) else None
        return (source.get("match") == "typed" and kind in {"amount", "number"} and transform == f"{kind}_normalize"
                and role in {"total_cell", "data_cell"} and source.get("geometry_scope") == "cell"
                and rules.normalize(kind, printed) is not None
                and bound == rules.normalize(kind, printed) == rules.normalize(kind, value))
    if evidence == "labelled_amount":
        return (source.get("match") == "typed" and transform == "amount_normalize" and role == "field_value"
                and source.get("geometry_scope") == "line" and source.get("basis") == "ocr_typed"
                and rules.normalize("amount", printed) is not None
                and bound == rules.normalize("amount", printed) == rules.normalize("amount", value))
    if evidence == "inferred_checkbox_unselected":
        doc_type, target = source.get("doc_type"), source.get("target_path")
        group = doctypes.EXCLUSIVE_CHECKBOX_GROUPS.get(doc_type, ())
        terms = source.get("terms")
        if (source.get("match") != "inferred" or source.get("basis") != "form_choice"
                or source.get("operation") != "exclusive_choice" or source.get("role") != "unselected"
                or target not in group or source.get("field_key") != target or len(group) != 2
                or not isinstance(terms, list) or len(terms) != 1
                or not isinstance(terms[0], dict) or terms[0].get("path") != next(name for name in group if name != target)
                or source.get("normalized_value") != "N" or rules.normalize("bool", value) != "N"
                or source.get("source_text") not in _MARKED or not _geometry({**source, "bbox": source.get("target_label_bbox")})
                or not any(_compact(label) in _compact(source.get("target_line_text")) for label in _labels(target))):
            return False
        selected = terms[0]["provenance"]
        return (isinstance(selected, dict) and selected.get("field_key") == terms[0]["path"]
                and selected.get("evidence_type") == "checkbox_mark" and selected.get("role") == "checked"
                and selected.get("source_text") == source.get("source_text")
                and selected.get("page") == source.get("page") and terms[0].get("normalized_value") == "Y"
                and valid(selected, "Y"))
    if evidence == "aligned_amount":
        doc_type, key = source.get("doc_type"), source.get("target_field")
        if (source.get("match") != "inferred" or source.get("basis") != "form_alignment"
                or source.get("operation") != "form_offset" or source.get("field_key") != key
                or doc_type not in doctypes.DOC_TYPES or key not in doctypes.spec(doc_type)["fields"]
                or doctypes.kind(doc_type, key) != "amount" or source.get("geometry_scope") != "line"
                or rules.normalize("amount", printed) is None
                or bound != rules.normalize("amount", printed) or bound != rules.normalize("amount", value)):
            return False
        leaf = key.split("-")[-1]
        labels = [*_labels(key), leaf]
        if "및" in leaf:
            labels.append(leaf.split("및")[-1].removesuffix("부담금"))
        if not any(_compact(label) in _compact(source.get("label")) for label in labels if len(_compact(label)) >= 4):
            return False
        axis = {"x": 0, "y": 1}.get(source.get("alignment_axis"))
        anchors = source.get("alignment_anchors")
        if axis is None or not isinstance(anchors, list) or len(anchors) != 2:
            return False
        def center(box, dimension):
            return (box[dimension] + box[dimension + 2]) / 2
        if not _geometry({**source, "bbox": source.get("label_bbox")}):
            return False
        offsets, keys = [], []
        label_boxes, value_boxes = [], []
        date_fields = {field for field, meta in doctypes.spec(doc_type)["fields"].items() if meta["kind"] == "date"}
        for anchor in anchors:
            if not isinstance(anchor, dict) or anchor.get("field_key") not in date_fields:
                return False
            keys.append(anchor["field_key"])
            label_boxes.append(tuple(anchor.get("label_bbox") or ()))
            value_boxes.append(tuple(anchor.get("bbox") or ()))
            if (not _geometry({**source, "bbox": anchor.get("label_bbox")})
                    or not _geometry({**source, "bbox": anchor.get("bbox")})
                    or not any(_compact(label) in _compact(anchor.get("label"))
                               for label in _labels(anchor["field_key"]) if len(_compact(label)) >= 3)
                    or rules.normalize("date", anchor.get("source_text")) is None):
                return False
            offset = center(anchor["bbox"], axis) - center(anchor["label_bbox"], axis)
            label_size = anchor["label_bbox"][axis + 2] - anchor["label_bbox"][axis]
            if (abs(offset) < label_size / 3 or abs(offset) > 1.5 * label_size
                    or center(anchor["bbox"], 1 - axis) < center(anchor["label_bbox"], 1 - axis)):
                return False
            offsets.append(offset)
        if (len(set(keys)) != 2 or len(set(label_boxes)) != 2 or len(set(value_boxes)) != 2
                or abs(offsets[0] - offsets[1]) > 3):
            return False
        label_box, box = source["label_bbox"], source["bbox"]
        tolerance = max(3, (label_box[axis + 2] - label_box[axis]) / 4)
        return (abs(center(box, axis) - center(label_box, axis) - sum(offsets) / 2) <= tolerance
                and center(box, 1 - axis) > center(label_box, 1 - axis))
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
                proof = _proof(block, box, token, label, evidence_type, transform, role, scope, expected)
                proof["field_key"] = key
                found.append(proof)
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
                proof = _proof(block, box, mark, label, "checkbox_mark", "checkbox_to_bool", role, scope, expected)
                proof["field_key"] = key
                found.append(proof)
    if any(item["geometry_scope"] == "line" for item in found):
        found = [item for item in found if item["geometry_scope"] == "line"]
    unique = {(item["page"], tuple(item["bbox"]), item["source_text"], item["role"]): item for item in found
              if isinstance(item.get("page"), int) and item.get("page_size")}
    return next(iter(unique.values())) if len(unique) == 1 else None


def amount_candidates(key, blocks):
    """A unique amount printed beside this field's label, with the amount line's actual geometry."""
    labels = [_compact(label) for label in _labels(key)]
    if key == "진료비내역-비급여및전액본인부담금":
        labels += ["비급여(전액본인)", "비급여전액본인"]
    found = []
    for block in blocks:
        lines = [line for line in block.get("lines") or [] if line.get("bbox")]
        for anchor in lines:
            compact = _compact(anchor.get("text"))
            matched = [label for label in labels if label and label in compact]
            if not matched:
                continue
            label = max(matched, key=len)
            suffix = compact.split(label, 1)[1]
            amounts = [token.group() for token in _AMOUNT_TOKEN.finditer(suffix)]
            source = anchor
            if len(amounts) != 1 or not _geometry({**block, "bbox": source["bbox"]}):
                continue
            value = rules.normalize("amount", amounts[0])
            if value is None:
                continue
            proof = _proof(block, source["bbox"], amounts[0], label, "labelled_amount",
                           "amount_normalize", "field_value", "line", value)
            proof["field_key"] = key
            found.append((value, proof))
    unique = {(proof["page"], tuple(proof["bbox"]), value): (value, proof) for value, proof in found}
    return next(iter(unique.values())) if len(unique) == 1 else None


def schema_alias_candidate(doc_type, key, fields, groundings):
    """Only the schema's declared alias, derived from a directly proven printed date."""
    source_key = doctypes.SCHEMA_ALIASES.get(doc_type, {}).get(key)
    if not source_key:
        return None
    source_value = fields.get(source_key)
    proof = groundings.get(source_key, {})
    if (not isinstance(proof, dict) or proof.get("evidence_type") not in {"date_equivalent", "date_range_start"}
            or not valid(proof, source_value)):
        return None
    date = rules.normalize("date", source_value)
    if date is None:
        return None
    derived = {"confidence": proof.get("confidence", 1.0), "page": None, "bbox": None,
               "source_text": None, "match": "derived", "evidence_type": "schema_alias",
               "operation": "schema_date_alias", "role": "schema_alias",
               "target_path": key, "doc_type": doc_type, "normalized_value": date,
               "verified": True, "basis": "schema_rule",
               "terms": [{"path": source_key, "normalized_value": date, "provenance": proof}]}
    return (date, derived) if valid(derived, date) else None


def inferred_checkbox_candidate(doc_type, key, blocks):
    """The other member of one printed two-option diagnosis group is N when exactly one is checked."""
    if doc_type not in doctypes.DOC_TYPES:
        return None
    choices = doctypes.EXCLUSIVE_CHECKBOX_GROUPS.get(doc_type, ())
    if len(choices) != 2 or key not in choices:
        return None
    selected = next(name for name in choices if name != key)
    found = []
    for block in blocks:
        lines = [line for line in block.get("lines") or [] if line.get("bbox")]
        selection = [(line, label) for line in lines for label in _labels(selected)
                     if _compact(label) in _compact(line.get("text"))]
        target = [(line, label) for line in lines for label in _labels(key)
                  if _compact(label) in _compact(line.get("text"))]
        if not selection or not target:
            continue
        selected_lines = {id(line): line for line, _ in selection}
        target_lines = {id(line): line for line, _ in target}
        if len(selected_lines) != 1 or len(target_lines) != 1:
            continue
        selected_line = next(iter(selected_lines.values()))
        target_line = next(iter(target_lines.values()))
        if selected_line is not target_line:
            a, b = selected_line["bbox"], target_line["bbox"]
            height = max(1, a[3] - a[1], b[3] - b[1])
            if (abs((a[1] + a[3] - b[1] - b[3]) / 2) > 4 * height
                    or abs((a[0] + a[2] - b[0] - b[2]) / 2) > 6 * height):
                continue
        marks = [mark for line in {id(selected_line): selected_line, id(target_line): target_line}.values()
                 for mark in str(line.get("text", "")) if mark in _MARKED]
        if len(marks) != 1 or any(mark in str(target_line.get("text", "")) for mark in _MARKED) and selected_line is not target_line:
            continue
        selected_proof = scalar(selected, "Y", "bool", [block], choices)
        if not selected_proof or selected_proof.get("source_text") != marks[0]:
            continue
        if not _geometry({**block, "bbox": target_line["bbox"]}):
            continue
        proof = {"verified": True, "evidence_type": "inferred_checkbox_unselected",
                 "match": "inferred", "basis": "form_choice", "operation": "exclusive_choice",
                 "doc_type": doc_type, "target_path": key, "field_key": key,
                 "role": "unselected", "label": key,
                 "target_line_text": target_line["text"], "target_label_bbox": target_line["bbox"],
                 "source_text": selected_proof["source_text"], "normalized_value": "N",
                 "page": block.get("page"), "page_size": block.get("page_size"),
                 "bbox": target_line["bbox"], "geometry_scope": "line_group",
                 "terms": [{"path": selected, "normalized_value": "Y", "provenance": selected_proof}]}
        if valid(proof, "N"):
            found.append(proof)
    return ("N", found[0]) if len(found) == 1 else None


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
            _blank_geometry(proof, cell)
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
        proof["field_key"] = f"{table}/{index}/{key}"
        found.append(proof)
    return found[0] if len(found) == 1 else None


def _blank_geometry(proof, cell):
    proof["blank_method"] = cell.get("blank_method", "closed_cell")
    if cell.get("rotation_degrees") is not None and abs(cell["rotation_degrees"]) >= 0.1:
        proof.update(geometry_scope="rotated_cell_hull", polygon=cell.get("polygon"),
                     rotation_degrees=cell["rotation_degrees"])


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
                       and cell.get("verified") is True and cell.get("rowspan", 1) == 1
                       and cell.get("blank") is True and isinstance(cell.get("bbox"), (list, tuple))]
            if len(targets) == 1:
                cell = targets[0]
                proof = _proof(block, cell["bbox"], "", label_cell["text"], "table_blank",
                               "blank_to_null", "field_cell", "cell", None)
                proof["match"] = "blank"
                proof["basis"] = "image_cell_blank"
                proof.update(row=cell["row"], column=cell["column"])
                proof["field_key"] = key
                _blank_geometry(proof, cell)
                found.append(proof)
        # Short payment labels are safe only within a printed payment group spanning
        # the row; the physical value cell must itself be closed and image-blank.
        suffix = key.removeprefix("납부한금액_")
        if key.startswith("납부한금액_") and len(suffix) >= 2:
            groups = [cell for cell in cells if "납부한금액" in _compact(cell.get("text"))
                      and cell.get("rowspan", 1) > 1 and cell.get("verified") is True]
            for group in groups:
                payment_labels = [cell for cell in cells if group["row"] <= cell["row"] < group["row"] + group["rowspan"]
                          and cell["column"] >= group["column"] + group.get("colspan", 1)
                          and _compact(cell.get("text")) == _compact(suffix)]
                if len(payment_labels) != 1:
                    continue
                label_cell = payment_labels[0]
                next_col = label_cell["column"] + label_cell.get("colspan", 1)
                targets = [cell for cell in cells if cell["row"] == label_cell["row"]
                           and cell["column"] == next_col and cell.get("verified") is True
                           and cell.get("blank") is True and cell.get("rowspan", 1) == 1]
                if len(targets) != 1:
                    continue
                cell = targets[0]
                proof = _proof(block, cell["bbox"], "", label_cell["text"], "table_blank",
                               "blank_to_null", "field_cell", "cell", None)
                proof.update(match="blank", basis="image_cell_blank", row=cell["row"],
                             column=cell["column"], field_key=key,
                             group_label=group["text"], group_bbox=group["bbox"])
                _blank_geometry(proof, cell)
                found.append(proof)
    return found[0] if len(found) == 1 else None


def blank_candidate(doc_type, key, current_value, blocks):
    """Propose null only for a unique empty physical cell with no conflicting narrative source."""
    if doc_type not in doctypes.DOC_TYPES or key not in doctypes.spec(doc_type)["fields"]:
        return None
    if current_value is None:
        return None
    kind = doctypes.kind(doc_type, key)
    proof = _field_blank(key, blocks) or _scalar_total(doc_type, key, None, kind, blocks)
    if not proof or not valid(proof, None):
        return None
    if kind in {"date", "text"}:
        narratives = [str(line.get("text", "")) for block in blocks
                      for line in block.get("lines") or [] if line.get("bbox")]
        if kind == "date":
            current = rules.normalize("date", current_value)
            dates = {date for line in narratives for date, _ in _date_tokens(line)}
            if (current and current in dates) or len(dates) >= 2:
                return None
        elif isinstance(current_value, str) and len(_compact(current_value)) >= 3:
            if any(_compact(current_value) in _compact(line) for line in narratives):
                return None
    return None, proof


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
                _blank_geometry(proof, cell)
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
            proof["field_key"] = key
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
    for key in doctypes.SCHEMA_ALIASES.get(doc_type, {}):
        candidate = schema_alias_candidate(doc_type, key, result, groundings)
        if candidate and rules.normalize("date", result.get(key)) == candidate[0]:
            groundings[key] = candidate[1]
    for key in doctypes.EXCLUSIVE_CHECKBOX_GROUPS.get(doc_type, ()):
        candidate = inferred_checkbox_candidate(doc_type, key, blocks)
        if candidate and rules.normalize("bool", result.get(key)) == candidate[0]:
            groundings[key] = candidate[1]
    return groundings
