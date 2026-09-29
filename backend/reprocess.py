"""Bounded, evidence-gated recovery after a document has been read once."""

import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path

import fitz
from PIL import Image, ImageOps

from . import doctypes, engine, inference, rules, typed_evidence
from .parsers import parse


_MISSING = object()


def _limit(name, default, ceiling):
    try:
        return max(0, min(int(os.getenv(name, default)), ceiling))
    except ValueError:
        return default


def settings():
    return {"enabled": os.getenv("REPROCESS_ENABLED", "true").lower() not in {"0", "false", "no"},
            "max_ms": _limit("REPROCESS_MAX_MS", 60000, 180000),
            "max_attempts": _limit("REPROCESS_MAX_ATTEMPTS", 4, 8),
            "max_model_calls": _limit("REPROCESS_MAX_MODEL_CALLS", 2, 4)}


def deadline_for(remaining_ms=None):
    """Total request deadline; a caller-supplied budget cannot increase the server ceiling."""
    maximum = _limit("READ_MAX_MS", 180000, 600000)
    budget = maximum if remaining_ms is None else min(max(0, int(remaining_ms)), maximum)
    return time.monotonic() + budget / 1000


def _source(result, schema, blocks):
    return engine.ground(result, schema, blocks)


def _quality(result, schema, blocks, grounds=None):
    grounds = grounds if grounds is not None else _source(result, schema, blocks)
    return engine.assess(result, schema, blocks, grounds), grounds


def _escape(part):
    return str(part).replace("~", "~0").replace("/", "~1")


def _rule_targets(flags, fields, quality):
    """Only a named leaf is a direct violation; broad flags rank existing review leaves."""
    direct, broad = {}, set()
    for flag in flags:
        key = flag.get("key")
        if not isinstance(key, str) or key not in fields:
            continue
        root = _escape(key)
        rows = fields[key]
        row, column = flag.get("row"), flag.get("column")
        if isinstance(rows, list):
            if isinstance(row, int) and 0 <= row < len(rows) and isinstance(rows[row], dict):
                path = f"{root}/{row}/{_escape(column)}" if isinstance(column, str) else None
                if path in quality:
                    direct.setdefault(path, []).append(flag)
                elif column is None:
                    broad.update(path for path in quality if path.startswith(f"{root}/{row}/"))
            elif row is None:
                if isinstance(column, str):
                    broad.update(f"{root}/{index}/{_escape(column)}" for index in range(len(rows))
                                 if f"{root}/{index}/{_escape(column)}" in quality)
                elif column is None:
                    broad.update(path for path in quality if path.startswith(f"{root}/"))
        elif row is None and column is None and not isinstance(rows, dict) and root in quality:
            direct.setdefault(root, []).append(flag)
    return direct, broad


def _mark_rules(quality, direct):
    for path, flags in direct.items():
        item = quality[path]
        item["issue_codes"] = list(dict.fromkeys([*item.get("issue_codes", []), *(flag["code"] for flag in flags)]))
        if item["status"] in {"PASS", "CORRECTED"}:
            item.update(status="SUSPICIOUS", action="RECHECK", stage="rule")


def _positioned(item, blocks, path):
    source = item.get("provenance") or {}
    match = source.get("match")
    if match not in {"exact", "approximate", "contained"} or not source.get("source_text"):
        return 0
    if set(item.get("issue_codes", [])) & {"invalid_geometry", "distant_label", "ambiguous_source", "row_conflict", "row_mismatch"}:
        return 0
    page, box, size = (source.get(key) for key in ("page", "bbox", "page_size"))
    if not isinstance(page, int) or page < 1 or not isinstance(box, (list, tuple)) or len(box) != 4 or not isinstance(size, (list, tuple)) or len(size) != 2:
        return 0
    try:
        if not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
            return 0
    except TypeError:
        return 0
    parts = path.split("/")
    if (len(parts) == 3 and parts[1].isdigit()
            and not all(isinstance(source.get(key), int) for key in ("row", "column"))):
        return 0
    needle = engine._normalized(source["source_text"])
    if not needle:
        return 0
    aligned = any(block.get("page") == page and line.get("bbox") == box and needle in engine._normalized(line.get("text", ""))
                  for block in blocks for line in block.get("lines") or [])
    return (2 if match == "exact" else 1) if aligned else 0


def _value(result, path):
    node = result
    for part in path.split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def _candidate_path(original, candidate, path, doc_type=None):
    """Map a table cell only by a unique unchanged row identity, never by row index alone."""
    parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")]
    if not isinstance(candidate, dict):
        return _MISSING
    if not any(part.isdigit() for part in parts):
        try:
            value = _value(candidate, path)
            return value if not isinstance(value, (dict, list)) else _MISSING
        except (KeyError, TypeError):
            return _MISSING
    if len(parts) != 3 or not parts[1].isdigit() or not isinstance(candidate.get(parts[0]), list):
        return _MISSING
    old_rows, new_rows = original.get(parts[0]), candidate[parts[0]]
    index, column = int(parts[1]), parts[2]
    if not isinstance(old_rows, list) or index >= len(old_rows) or not isinstance(old_rows[index], dict):
        return _MISSING
    old = old_rows[index]
    if doc_type in doctypes.DOC_TYPES and parts[0] in doctypes.spec(doc_type)["tables"]:
        table = parts[0]
        keys = [key for key in rules.ROW_KEYS.get(table, ()) if key != column and old.get(key) not in (None, "")]
        if not keys:
            return _MISSING
        def identity(row):
            if not isinstance(row, dict):
                return None
            return tuple(rules.normalize(doctypes.kind(doc_type, key, table), row.get(key)) for key in keys)
        token = identity(old)
        if any(value is None for value in token):
            return _MISSING
        if (sum(identity(row) == token for row in old_rows) != 1
                or sum(identity(row) == token for row in new_rows) != 1):
            return _MISSING
        row = next(row for row in new_rows if identity(row) == token)
        return row[column] if column in row and not isinstance(row[column], (dict, list)) else _MISSING
    identity = {key: value for key, value in old.items() if key != column and value not in (None, "")}
    if not identity:
        return _MISSING
    matches = [row for row in new_rows if isinstance(row, dict) and all(row.get(key) == value for key, value in identity.items())]
    return matches[0][column] if len(matches) == 1 and column in matches[0] else _MISSING


def _typed(provenance, value):
    from .typed_evidence import valid
    return valid(provenance, value)


def _blank_candidate(fields, path, schema, blocks):
    """Only a proven physical empty cell may propose null; missing extraction is not a proposal."""
    try:
        value = _value(fields, path)
        if value is None:
            return False
        if "/" not in path:
            key = path.replace("~1", "/").replace("~0", "~")
            return typed_evidence.blank_candidate(schema.get("title"), key, value, blocks) is not None
        candidate = _patch(fields, path, None)
        source = engine.ground(candidate, schema, blocks)
        for part in path.split("/"):
            source = source.get(part.replace("~1", "/").replace("~0", "~"), {}) if isinstance(source, dict) else {}
        return isinstance(source, dict) and _typed(source, None)
    except (KeyError, IndexError, TypeError):
        return False


def _patch(result, path, value):
    patched = deepcopy(result)
    parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")]
    node = patched
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(parts[-1])] = value
    else:
        node[parts[-1]] = value
    return patched


def _candidate_groundings(current, candidate, schema, evidence, path):
    """Refresh only the candidate leaf; ROI OCR must not rewrite evidence for unchanged fields."""
    fresh = _source(candidate, schema, evidence)
    parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")]
    for part in parts:
        fresh = fresh.get(part, {}) if isinstance(fresh, dict) else {}
    merged = deepcopy(current)
    node = merged
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = fresh
    return merged


def _box(source, blocks, root, schema):
    provenance = source.get("provenance") or {}
    if provenance.get("bbox") and provenance.get("page_size"):
        return provenance["page"], provenance["bbox"], provenance["page_size"]
    spec = schema.get("properties", {}).get(root, {})
    labels = engine._labels(root, spec)
    for block in blocks:
        if block.get("bbox") and block.get("page_size") and any(label in engine._normalized(block.get("text", "")) for label in labels):
            return block.get("page") or 1, block["bbox"], block["page_size"]
    return None


def _label_seen(root, schema, blocks):
    labels = engine._labels(root, schema.get("properties", {}).get(root, {}))
    return any(label in engine._normalized(block.get("text", ""))
               for block in blocks for label in labels if label)


def _crop(image, page, box, size, factor, target):
    with fitz.open(image) if Path(image).suffix.lower() == ".pdf" else Image.open(image) as source:
        if isinstance(source, fitz.Document):
            sheet = source[page - 1]
            pix = sheet.get_pixmap(matrix=fitz.Matrix(size[0] / sheet.rect.width, size[1] / sheet.rect.height),
                                   colorspace=fitz.csRGB, alpha=False)
            canvas = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        else:
            canvas = ImageOps.exif_transpose(source).convert("RGB")
        sx, sy = canvas.width / size[0], canvas.height / size[1]
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        width, height = max(box[2] - box[0], size[0] * 0.18) * factor, max(box[3] - box[1], size[1] * 0.12) * factor
        left, top = max(0, int((cx - width / 2) * sx)), max(0, int((cy - height / 2) * sy))
        right, bottom = min(canvas.width, int((cx + width / 2) * sx)), min(canvas.height, int((cy + height / 2) * sy))
        if right <= left or bottom <= top:
            return None
        canvas.crop((left, top, right, bottom)).save(target, format="PNG")
        return left / sx, top / sy, (right - left) / sx, (bottom - top) / sy


def _remap(blocks, page, size, crop):
    left, top, width, height = crop
    mapped = deepcopy(blocks)
    for block in mapped:
        local = block.get("page_size") or [width, height]
        sx, sy = width / local[0], height / local[1]
        def convert(box):
            return [left + box[0] * sx, top + box[1] * sy, left + box[2] * sx, top + box[3] * sy]
        if block.get("bbox"):
            block["bbox"] = convert(block["bbox"])
        for line in block.get("lines") or []:
            if line.get("bbox"):
                line["bbox"] = convert(line["bbox"])
        for cell in block.get("cells") or []:
            if cell.get("bbox"):
                cell["bbox"] = convert(cell["bbox"])
            if cell.get("polygon"):
                try:
                    cell["polygon"] = [[left + x * sx, top + y * sy] for x, y in cell["polygon"]]
                    cell["bbox"] = [min(point[0] for point in cell["polygon"]),
                                    min(point[1] for point in cell["polygon"]),
                                    max(point[0] for point in cell["polygon"]),
                                    max(point[1] for point in cell["polygon"])]
                except (TypeError, ValueError):
                    cell.update(verified=False, blank=False)
            cell.update(page=page, page_size=size)
        block.update(page=page, page_size=size)
    return mapped


def _vertical_ocr(blocks):
    """Only retry rotation when enough OCR boxes visibly follow the vertical page axis."""
    boxes = [line.get("bbox") for block in blocks for line in block.get("lines") or []]
    ratios = [(box[2] - box[0]) / (box[3] - box[1]) for box in boxes
              if isinstance(box, (list, tuple)) and len(box) == 4 and box[3] > box[1]]
    return len(ratios) >= 15 and sum(ratio < 1 for ratio in ratios) >= .75 * len(ratios)


def _rotated(image, angle, target):
    with Image.open(image) as source:
        canvas = ImageOps.exif_transpose(source).convert("RGB")
        size = canvas.size
        canvas.rotate(angle, expand=True).save(target, format="PNG")
    return size


def _remap_rotation(blocks, angle, size):
    """Map rotated OCR boxes back to page-local coordinates of the original image."""
    width, height = size
    mapped = deepcopy(blocks)
    def point(x, y):
        return (width - y, x) if angle == 90 else (y, height - x)
    def convert(box):
        corners = [point(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
        return [min(x for x, _ in corners), min(y for _, y in corners),
                max(x for x, _ in corners), max(y for _, y in corners)]
    for block in mapped:
        for item in (block, *(block.get("lines") or []), *(block.get("cells") or [])):
            if item.get("bbox"):
                item["bbox"] = convert(item["bbox"])
            if item.get("polygon"):
                try:
                    item["polygon"] = [list(point(*corner)) for corner in item["polygon"]]
                    item["bbox"] = [min(corner[0] for corner in item["polygon"]),
                                    min(corner[1] for corner in item["polygon"]),
                                    max(corner[0] for corner in item["polygon"]),
                                    max(corner[1] for corner in item["polygon"])]
                    # The small deskew angle is relative to the rotated crop, not to this page.
                    if item.get("blank") is True:
                        item.update(verified=False, blank=False)
                except (TypeError, ValueError):
                    item.update(verified=False, blank=False)
            item["page_size"] = list(size)
    return mapped


def run(image, schema, blocks, result, *, normalize=None, check_rules=None, cancel=None, deadline=None, enabled=None):
    """Return (fields, groundings, quality, trace summary). Only a better grounded leaf can replace a value."""
    started = time.monotonic()
    config = settings()
    deadline = min(deadline or deadline_for(), started + config["max_ms"] / 1000)
    fields = deepcopy(result or {})
    quality, groundings = _quality(fields, schema, blocks)
    trace = []
    calls = 0
    attempts = 0
    stop = "complete"
    corrected = set()
    active = config["enabled"] and enabled is not False

    def finished(reason):
        status = ("UNRESOLVED" if any(item["status"] not in {"PASS", "CORRECTED"} for item in quality.values())
                  else "CORRECTED" if any(item["adopted"] and item["before"] != item["after"] for item in trace)
                  else "PASS")
        return fields, groundings, quality, {"status": status, "attempts": attempts,
                                             "model_calls": calls, "extra_model_calls": calls,
                                             "stop_reason": reason, "elapsed_ms": round((time.monotonic() - started) * 1000),
                                             "trace": trace}

    def check():
        if cancel is not None and cancel.is_set():
            from .verify import Cancelled
            raise Cancelled(getattr(cancel, "reason", None))
        return time.monotonic() < deadline

    if not active:
        return finished("disabled")
    if not config["max_attempts"] or not config["max_ms"]:
        return finished("budget")
    if Path(image).suffix.lower() not in engine.VISION_SUFFIXES:
        quality = engine.assess(fields, schema, blocks, groundings, require_geometry=False)
        return finished("non_visual")
    seen = {repr(fields)}
    initial_flags = check_rules(fields, blocks) if check_rules else []
    direct, broad = _rule_targets(initial_flags, fields, quality)
    _mark_rules(quality, direct)
    targets = [path for path, item in quality.items() if item["status"] not in {"PASS", "CORRECTED"}]
    deterministic = {}
    for path in targets:
        if not check():
            break
        if "/" in path:
            continue
        key = path.replace("~1", "/").replace("~0", "~")
        if schema.get("title") not in doctypes.DOC_TYPES or key not in doctypes.spec(schema["title"])["fields"]:
            continue
        kind = doctypes.kind(schema["title"], key)
        candidate = typed_evidence.schema_alias_candidate(schema["title"], key, fields, groundings)
        if candidate is not None:
            source_key = candidate[1]["terms"][0]["path"]
            source_quality = quality.get(_escape(source_key), {})
            if (source_quality.get("status") not in {"PASS", "CORRECTED"}
                    or source_quality.get("issue_codes")):
                candidate = None
        if candidate is None and kind == "bool":
            candidate = typed_evidence.inferred_checkbox_candidate(schema["title"], key, blocks)
        if candidate is None and fields.get(key) is not None:
            candidate = typed_evidence.blank_candidate(schema["title"], key, fields[key], blocks)
        if candidate is not None and candidate[0] != fields.get(key):
            deterministic[path] = candidate
    def priority(path):
        located = _positioned(quality[path], blocks, path)
        related = path in direct or path in broad
        return (0 if path in deterministic else 1,
                0 if located == 2 and related else 1 if located == 2 else 2 if located == 1
                else 3 if related else 4)
    targets.sort(key=priority)
    if not targets:
        return finished("pass")
    for path in targets:
        if quality.get(path, {}).get("status") in {"PASS", "CORRECTED"}:
            continue
        if not check():
            stop = "deadline"
            break
        if attempts >= config["max_attempts"]:
            stop = "attempt_budget"
            break
        root = path.split("/")[0].replace("~1", "/").replace("~0", "~")
        try:
            original_value = _value(fields, path)
        except (KeyError, IndexError, TypeError):
            original_value = None
        def record(stage, reason, status, proposed=None, adopted=False, provenance=None, checks=None):
            trace.append({"stage": stage, "field": path, "reason": reason, "status": status,
                          "before": original_value, "proposed": proposed,
                          "after": proposed if adopted else original_value, "adopted": adopted,
                          "provenance": provenance or {}, **({"checks": checks} if checks is not None else {})})
        if any(part.isdigit() for part in path.split("/")[1:]) and len(path.split("/")) != 3:
            record("select", "unsupported_path", quality[path]["status"])
            continue
        before = quality[path]
        text_field = (len(path.split("/")) == 1 and schema.get("title") in doctypes.DOC_TYPES
                      and doctypes.kind(schema["title"], root) == "text")
        located = _positioned(before, blocks, path)
        selection = ("located_rule_violation" if path in direct and located == 2 else
                     "located_rule_related" if path in broad and located == 2 else
                     "located_source" if located == 2 else
                     "aligned_approximate_source" if located == 1 else
                     "rule_violation" if path in direct else "rule_related" if path in broad else "fallback")
        record("select", selection, before["status"])
        region = _box(before, blocks, root, schema)
        if not region:
            record("roi_parse", "no_geometry", before["status"])
        with tempfile.TemporaryDirectory() as folder:
            roi = str(Path(folder) / "roi.png")
            try:
                crop = _crop(image, *region, 2, roi) if region else None
            except (OSError, ValueError, IndexError):
                crop = None
            local = []
            mapped = []
            evidence = blocks
            roi_failure = None
            held_text = None
            sum_target = any(root in (total, *parts) for total, parts in rules.FIELD_SUMS.items())
            rotation = (sum_target and _vertical_ocr(blocks)
                        and Path(image).suffix.lower() in engine.VISION_SUFFIXES
                        and Path(image).suffix.lower() != ".pdf")
            stages = ("rules", *(("rotate_ccw", "rotate_cw") if rotation else ()),
                      "roi_parse", "roi_vlm", "wide_vlm")
            for stage in stages:
                if attempts >= config["max_attempts"] or not check():
                    stop = "deadline" if time.monotonic() >= deadline else "attempt_budget"
                    break
                if (stage == "rules" and normalize is None and path not in deterministic
                        and not _blank_candidate(fields, path, schema, evidence)):
                    continue
                if stage == "roi_parse" and not crop:
                    continue
                if stage == "roi_vlm" and not local:
                    continue
                if stage.endswith("vlm") and calls >= config["max_model_calls"]:
                    stop = "model_budget"
                    break
                attempts += 1
                try:
                    if stage == "rules":
                        proposal = normalize(deepcopy(fields), evidence) if normalize else deepcopy(fields)
                        local_proof = deterministic.get(path)
                        if local_proof and isinstance(proposal, dict) and proposal.get(root) == fields.get(root):
                            proposal = _patch(proposal, path, local_proof[0])
                        elif _blank_candidate(fields, path, schema, evidence):
                            proposal = _patch(fields, path, None)
                    elif stage.startswith("rotate_"):
                        angle = 90 if stage == "rotate_ccw" else -90
                        rotated = str(Path(folder) / f"rotated-{angle}.png")
                        size = _rotated(image, angle, rotated)
                        _, rotated_blocks = parse(rotated, "rotated.png", "image/png",
                                                  {"provider": "paddle", "refine_tables": False,
                                                   "timeout": max(0.1, deadline - time.monotonic()),
                                                   "deadline": deadline})
                        mapped = _remap_rotation(rotated_blocks, angle, size)
                        evidence = [*blocks, *mapped]
                        proposal = deepcopy(fields)
                    elif stage == "roi_parse":
                        _, local = parse(roi, "roi.png", "image/png", {"provider": "paddle", "refine_tables": False,
                                                                         "timeout": max(0.1, deadline - time.monotonic()),
                                                                         "deadline": deadline})
                        mapped = _remap(local, region[0], region[2], crop)
                        evidence = [*blocks, *mapped]
                        proposal = normalize(deepcopy(fields), evidence) if normalize else fields
                        if _blank_candidate(fields, path, schema, evidence):
                            proposal = _patch(fields, path, None)
                    else:
                        narrowed = {**schema, "properties": {root: schema["properties"][root]},
                                    "required": [root] if root in schema.get("required", []) else []}
                        def count():
                            nonlocal calls
                            if calls >= config["max_model_calls"]:
                                raise RuntimeError("model budget exceeded")
                            calls += 1
                        blind_wide = stage == "wide_vlm" and text_field
                        proposal, _ = engine.extract(narrowed, local if stage == "roi_vlm" else [] if blind_wide else blocks,
                                                     source=roi if stage == "roi_vlm" else image,
                                                     deadline=deadline, cancel=cancel, on_call=count)
                    if not check():
                        stop = "deadline"
                        break
                    if stage.startswith("rotate_"):
                        grouped = inference.sum_group(fields, root, mapped, schema.get("title"))
                        if grouped is not None:
                            group_fields, proofs = grouped
                            group_groundings = deepcopy(groundings)
                            group_groundings.update(proofs)
                            group_quality, _ = _quality(group_fields, schema, blocks, group_groundings)
                            old_flags = check_rules(fields, mapped) if check_rules else []
                            new_flags = check_rules(group_fields, mapped) if check_rules else []
                            original_flags = check_rules(group_fields, blocks) if check_rules else []
                            group_direct, _ = _rule_targets(original_flags, group_fields, group_quality)
                            mapped_direct, _ = _rule_targets(new_flags, group_fields, group_quality)
                            for key in proofs:
                                group_direct.pop(_escape(key), None)
                                if _escape(key) in mapped_direct:
                                    group_direct[_escape(key)] = mapped_direct[_escape(key)]
                            _mark_rules(group_quality, group_direct)
                            signature = lambda flag: json.dumps(flag, ensure_ascii=False, sort_keys=True, default=str)
                            clean = not ({signature(flag) for flag in new_flags} - {signature(flag) for flag in old_flags})
                            changed = [key for key in proofs if group_fields[key] != fields[key]]
                            unrelated = any(item["status"] not in {"PASS", "CORRECTED"}
                                            and quality.get(key, {}).get("status") in {"PASS", "CORRECTED"}
                                            for key, item in group_quality.items() if key not in proofs)
                            if not check():
                                stop = "deadline"
                                break
                            if (changed and clean and not unrelated and repr(group_fields) not in seen
                                    and all(group_quality[key]["status"] in {"PASS", "CORRECTED"}
                                            and not group_quality[key].get("issue_codes") for key in proofs)):
                                previous = fields
                                fields, quality, groundings = group_fields, group_quality, group_groundings
                                seen.add(repr(fields))
                                corrected.update(changed)
                                for key in corrected:
                                    if quality.get(key, {}).get("status") == "PASS":
                                        quality[key] = {**quality[key], "status": "CORRECTED"}
                                for key in changed:
                                    trace.append({"stage": stage, "field": _escape(key), "reason": "verified_sum_group",
                                                  "status": quality[key]["status"], "before": previous[key],
                                                  "proposed": fields[key], "after": fields[key], "adopted": True,
                                                  "provenance": groundings[key],
                                                  "checks": {"proof_kind": groundings[key].get("evidence_type"),
                                                             "verified": True, "semantic": True,
                                                             "rules": clean, "regression": False}})
                                break
                            record(stage, "sum_group_quality_rejected", before["status"],
                                   checks={"candidate_status": {key: group_quality[key]["status"] for key in proofs},
                                           "candidate_issue_codes": {key: group_quality[key].get("issue_codes", [])
                                                                     for key in proofs},
                                           "rules": clean, "regression": unrelated})
                        else:
                            record(stage, "no_verified_sum_group", before["status"])
                        continue
                    value = _candidate_path(fields, proposal, path, schema.get("title"))
                    if value is _MISSING:
                        record(stage, "no_safe_candidate", before["status"])
                        continue
                    candidate = _patch(fields, path, value)
                    proposed_groundings = _candidate_groundings(groundings, candidate, schema, evidence, path)
                    if stage == "rules" and path in deterministic and value == deterministic[path][0]:
                        proposed_groundings[root] = deterministic[path][1]
                    proposed_quality, _ = _quality(candidate, schema, blocks, proposed_groundings)
                    if evidence is not blocks:
                        roi_quality, _ = _quality(candidate, schema, evidence, proposed_groundings)
                        if path in roi_quality:
                            proposed_quality[path] = roi_quality[path]
                    old_flags = check_rules(fields, evidence) if check_rules else []
                    new_flags = check_rules(candidate, evidence) if check_rules else []
                    original_flags = check_rules(candidate, blocks) if check_rules and evidence is not blocks else new_flags
                    proposed_direct, _ = _rule_targets(original_flags, candidate, proposed_quality)
                    if evidence is not blocks:
                        roi_direct, _ = _rule_targets(new_flags, candidate, proposed_quality)
                        proposed_direct.pop(path, None)
                        if path in roi_direct:
                            proposed_direct[path] = roi_direct[path]
                    _mark_rules(proposed_quality, proposed_direct)
                    after = proposed_quality.get(path, {})
                    if (stage == "rules" and candidate == fields
                            and all(after.get(key) == before.get(key) for key in ("status", "issue_codes", "provenance"))):
                        attempts -= 1  # local normalization did not make a candidate or add evidence
                        record(stage, "no_change", before["status"])
                        continue
                    old_rank = {"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(before["status"], 2)
                    new_rank = {"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(after.get("status"), 2)
                    regression = any({"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(item["status"], 2)
                                     > {"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(quality.get(key, {}).get("status"), 2)
                                     for key, item in proposed_quality.items() if key != path)
                    source_blocks = local if stage in {"roi_parse", "roi_vlm"} else evidence
                    parts = path.split("/")
                    table_cell = (len(parts) == 3 and parts[1].isdigit()
                                  and isinstance(fields.get(root), list))
                    typed = _typed(after.get("provenance", {}), value)
                    semantic = (table_cell or _label_seen(root, schema, source_blocks)
                                or typed and (bool(after.get("provenance", {}).get("label"))
                                              or after.get("provenance", {}).get("evidence_type")
                                              in {"derived_sum", "schema_alias"}))
                    exact = after.get("status") == "PASS" and (after.get("provenance", {}).get("match") == "exact"
                                                                          or typed)
                    rule_clean = True
                    if check_rules is not None:
                        signature = lambda flag: json.dumps(flag, ensure_ascii=False, sort_keys=True, default=str)
                        rule_clean = not ({signature(flag) for flag in new_flags} - {signature(flag) for flag in old_flags})
                    proven = exact and semantic and rule_clean
                    improved = new_rank < old_rank or (candidate != fields and old_rank == 0 and new_rank == 0)
                    if not check():
                        stop = "deadline"
                        break
                    if (stage == "roi_vlm" and isinstance(original_value, str) and original_value and original_value != value
                            and any(engine._normalized(original_value) in engine._normalized(block.get("text", ""))
                                    for block in local)):
                        record(stage, "roi_parse_supports_original", before["status"], value,
                               provenance=after.get("provenance"))
                        break  # ROI OCR이 원값을 그대로 읽었으면 VLM 단독 제안으로 덮어쓰지 않는다
                    long_text = (text_field and isinstance(value, str)
                                 and max(len(value), len(str(original_value or ""))) >= 20)
                    if (stage == "roi_vlm" and long_text and value != original_value
                            and proven and improved and not regression):
                        held_text = engine._normalized(value)
                        record(stage, "await_wide_confirmation", before["status"], value,
                               provenance=after.get("provenance"))
                        continue
                    if stage == "wide_vlm" and held_text is not None and engine._normalized(value) != held_text:
                        record(stage, "conflicting_text_reads", before["status"], value,
                               provenance=after.get("provenance"))
                        continue
                    if proven and improved and not regression and (candidate == fields or repr(candidate) not in seen):
                        old_value = original_value
                        fields, quality, groundings = candidate, proposed_quality, proposed_groundings
                        seen.add(repr(fields))
                        if value != old_value:
                            corrected.add(path)
                        for marked in corrected:
                            if quality.get(marked, {}).get("status") == "PASS":
                                quality[marked] = {**quality[marked], "status": "CORRECTED"}
                        record(stage, "verified", quality[path]["status"], value, True, after.get("provenance"),
                               {"exact": exact, "semantic": semantic, "rules": rule_clean, "regression": regression})
                        break
                    reason = "cycle" if candidate != fields and repr(candidate) in seen else (
                        "unverified_candidate" if not proven else "no_improvement")
                    record(stage, reason, before["status"],
                           value, provenance=after.get("provenance"),
                           checks={"candidate_status": after.get("status"), "candidate_issue_codes": after.get("issue_codes", []),
                                   "exact": exact, "semantic": semantic, "rules": rule_clean,
                                   "regression": regression, "improved": improved})
                    if stage in {"roi_parse", "roi_vlm"}:
                        source = after.get("provenance") or {}
                        failure = (value, after.get("status"), tuple(after.get("issue_codes") or ()),
                                   source.get("match"), source.get("evidence_type"), source.get("source_text"),
                                   source.get("normalized_value"))
                        if stage == "roi_vlm" and roi_failure == failure:
                            record("wide_vlm", "repeated_unverified_evidence", before["status"])
                            break
                        if stage == "roi_parse":
                            roi_failure = failure
                except Exception:
                    if cancel is not None and cancel.is_set():
                        check()
                    record(stage, "parse_failed" if stage == "roi_parse" else "stage_failed", before["status"])
            else:
                stop = "no_improvement"
    if stop == "complete" and any(item["status"] not in {"PASS", "CORRECTED"} for item in quality.values()):
        stop = "unresolved"
    return finished(stop)
