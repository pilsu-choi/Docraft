"""Conservative, auditable field-sum inference from individually bound OCR amounts."""

import logging
import re
from copy import deepcopy

from . import doctypes, rules, typed_evidence

logger = logging.getLogger(__name__)


_DATE = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")


def _center(box, axis):
    return (box[axis] + box[axis + 2]) / 2


def _aligned_amounts(keys, blocks, doc_type):
    """Bind amounts only when two independent date labels prove one form-wide print offset."""
    spec = doctypes.DOC_TYPES.get(doc_type)
    if not spec:
        return {}
    date_keys = [key for key, meta in spec["fields"].items() if meta["kind"] == "date"]
    results = []
    for block in blocks:
        lines = [line for line in block.get("lines") or [] if line.get("bbox")]
        if len(lines) < 8:
            continue
        vertical = sum((line["bbox"][2] - line["bbox"][0]) <
                       (line["bbox"][3] - line["bbox"][1]) for line in lines) >= .75 * len(lines)
        axis = 0 if vertical else 1
        transverse = 1 - axis
        anchors = []
        for key in date_keys:
            aliases = [re.sub(r"\s+", "", label) for label in rules.LABELS.get(key, (key,))]
            labels = [line for line in lines if any(alias in re.sub(r"\s+", "", line["text"])
                                                     for alias in aliases if len(alias) >= 3)]
            for label in labels:
                label_box = label["bbox"]
                height = label_box[axis + 2] - label_box[axis]
                dates = [line for line in lines if line is not label and _DATE.fullmatch(line["text"].strip())
                         and abs(_center(line["bbox"], axis) - _center(label_box, axis)) <= 1.5 * height
                         and _center(line["bbox"], transverse) >= _center(label_box, transverse)]
                if len(dates) == 1:
                    source = dates[0]
                    offset = _center(source["bbox"], axis) - _center(label_box, axis)
                    if abs(offset) >= height / 3:
                        anchors.append({"field_key": key, "label": label["text"],
                                        "label_bbox": label_box, "source_text": source["text"],
                                        "bbox": source["bbox"], "offset": offset})
        pairs = [(a, b) for i, a in enumerate(anchors) for b in anchors[i + 1:]
                 if a["field_key"] != b["field_key"]
                 and abs(a["offset"] - b["offset"]) <= 3]
        if len(pairs) != 1:
            continue
        pair = pairs[0]
        offset = sum(anchor["offset"] for anchor in pair) / 2
        proposed = {}
        for key in keys:
            leaf = key.split("-")[-1]
            aliases = [*rules.LABELS.get(key, ()), leaf]
            if "및" in leaf:
                aliases.append(leaf.split("및")[-1].removesuffix("부담금"))
            aliases = [re.sub(r"\s+", "", alias) for alias in aliases if len(alias) >= 4]
            labels = [line for line in lines if any(alias in re.sub(r"\s+", "", line["text"])
                                                     for alias in aliases)]
            if len(labels) != 1:
                continue
            label = labels[0]
            label_box = label["bbox"]
            tolerance = max(3, (label_box[axis + 2] - label_box[axis]) / 4)
            amounts = []
            for line in lines:
                if line is label:
                    continue
                matches = list(typed_evidence._AMOUNT_TOKEN.finditer(line["text"]))
                if len(matches) != 1 or len(line["text"].strip()) > 15:
                    continue
                box = line["bbox"]
                if (abs(_center(box, axis) - _center(label_box, axis) - offset) <= tolerance
                        and _center(box, transverse) > _center(label_box, transverse)):
                    value = rules.normalize("amount", matches[0].group())
                    if value is not None:
                        amounts.append((value, line, matches[0].group()))
            if len(amounts) != 1:
                continue
            value, line, token = amounts[0]
            proof = {"verified": True, "evidence_type": "aligned_amount", "match": "inferred",
                     "basis": "form_alignment", "operation": "form_offset", "field_key": key,
                     "target_field": key, "doc_type": doc_type, "label": label["text"],
                     "label_bbox": label_box, "alignment_axis": "x" if vertical else "y",
                     "alignment_anchors": [{name: anchor[name] for name in
                                            ("field_key", "label", "label_bbox", "source_text", "bbox")}
                                           for anchor in pair],
                     "source_text": token, "normalized_value": value,
                     "page": block.get("page"), "page_size": block.get("page_size"),
                     "bbox": line["bbox"], "geometry_scope": "line"}
            if typed_evidence.valid(proof, value):
                proposed[key] = (value, proof)
        if proposed:
            results.append(proposed)
    return results[0] if len(results) == 1 else {}


def sum_group(fields, target, blocks, doc_type=None):
    """Return an atomic (fields, proofs) proposal only for one fully grounded sum."""
    relations = [(total, parts) for total, parts in rules.FIELD_SUMS.items()
                 if target in (total, *parts) and all(key in fields for key in (total, *parts))]
    if len(relations) != 1:
        logger.debug("sum_group: target=%s skipped, relations=%d", target, len(relations))
        return None
    total, parts = relations[0]
    aligned = _aligned_amounts((total, *parts), blocks, doc_type)
    terms = []
    for key in parts:
        found = aligned.get(key) or typed_evidence.amount_candidates(key, blocks)
        if found is None:
            return None
        value, proof = found
        normalized = rules.normalize("amount", value)
        if normalized is None or rules._money(normalized) is None or not typed_evidence.valid(proof, normalized):
            return None
        terms.append({"path": key, "normalized_value": normalized, "provenance": proof})
    candidate = deepcopy(fields)
    for term in terms:
        candidate[term["path"]] = term["normalized_value"]
    computed = str(sum(rules._money(term["normalized_value"]) for term in terms))
    printed_total = aligned.get(total) or typed_evidence.amount_candidates(total, blocks)
    if printed_total is not None:
        printed, proof = printed_total
        if rules.normalize("amount", printed) != computed or not typed_evidence.valid(proof, printed):
            logger.debug("sum_group: target=%s printed total does not match the sum of %d parts", target, len(parts))
            return None
        total_proof = proof
    else:
        total_proof = {"verified": True, "evidence_type": "derived_sum", "match": "derived",
                       "basis": "calculation", "operation": "sum", "normalized_value": computed,
                       "source_text": None, "bbox": None, "target_field": total,
                       "doc_type": doc_type, "terms": terms}
        if not typed_evidence.valid(total_proof, computed):
            return None
    candidate[total] = computed
    if candidate == fields:
        return None
    proofs = {term["path"]: term["provenance"] for term in terms}
    proofs[total] = total_proof
    logger.debug("sum_group: target=%s proposed total=%s parts=%d", target, total, len(parts))
    return candidate, proofs
