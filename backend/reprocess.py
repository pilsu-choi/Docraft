"""Bounded, evidence-gated recovery after a document has been read once."""

import json
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path

import fitz
from PIL import Image, ImageOps

from . import engine
from .parsers import parse


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
    return engine._grounding_tree(result, [(block, engine._block_rows(block)) for block in blocks], schema)


def _quality(result, schema, blocks):
    grounds = _source(result, schema, blocks)
    return engine.assess(result, schema, blocks, grounds), grounds


def _value(result, path):
    node = result
    for part in path.split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def _candidate_path(original, candidate, path):
    """Map a table cell only by a unique unchanged row identity, never by row index alone."""
    parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")]
    if not isinstance(candidate, dict):
        return None
    if not any(part.isdigit() for part in parts):
        try:
            value = _value(candidate, path)
            return value if not isinstance(value, (dict, list)) else None
        except (KeyError, TypeError):
            return None
    if len(parts) != 3 or not parts[1].isdigit() or not isinstance(candidate.get(parts[0]), list):
        return None
    old_rows, new_rows = original.get(parts[0]), candidate[parts[0]]
    index, column = int(parts[1]), parts[2]
    if not isinstance(old_rows, list) or index >= len(old_rows) or not isinstance(old_rows[index], dict):
        return None
    old = old_rows[index]
    identity = {key: value for key, value in old.items() if key != column and value not in (None, "")}
    if not identity:
        return None
    matches = [row for row in new_rows if isinstance(row, dict) and all(row.get(key) == value for key, value in identity.items())]
    return matches[0].get(column) if len(matches) == 1 else None


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


def _box(source, blocks, root, schema):
    provenance = source.get("provenance") or {}
    if provenance.get("bbox") and provenance.get("page_size"):
        return provenance["page"], provenance["bbox"], provenance["page_size"]
    spec = schema.get("properties", {}).get(root, {})
    labels = [root, str(spec.get("title") or "")]
    for block in blocks:
        if block.get("bbox") and block.get("page_size") and any(label and label in block.get("text", "") for label in labels):
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
        block.update(page=page, page_size=size)
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
    targets = [path for path, item in quality.items() if item["status"] not in {"PASS", "CORRECTED"}]
    if not targets:
        return finished("pass")
    for path in targets:
        if quality.get(path, {}).get("status") in {"PASS", "CORRECTED"}:
            continue
        if attempts >= config["max_attempts"]:
            stop = "attempt_budget"
            break
        if not check():
            stop = "deadline"
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
            for stage in ("rules", "roi_parse", "roi_vlm", "wide_vlm"):
                if attempts >= config["max_attempts"] or not check():
                    stop = "deadline" if time.monotonic() >= deadline else "attempt_budget"
                    break
                if stage == "rules" and normalize is None:
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
                        proposal = normalize(deepcopy(fields), evidence)
                    elif stage == "roi_parse":
                        _, local = parse(roi, "roi.png", "image/png", {"provider": "paddle", "refine_tables": False,
                                                                         "timeout": max(0.1, deadline - time.monotonic()),
                                                                         "deadline": deadline})
                        mapped = _remap(local, region[0], region[2], crop)
                        evidence = [*blocks, *mapped]
                        proposal = normalize(deepcopy(fields), evidence) if normalize else fields
                    else:
                        narrowed = {**schema, "properties": {root: schema["properties"][root]},
                                    "required": [root] if root in schema.get("required", []) else []}
                        def count():
                            nonlocal calls
                            if calls >= config["max_model_calls"]:
                                raise RuntimeError("model budget exceeded")
                            calls += 1
                        proposal, _ = engine.extract(narrowed, local if stage == "roi_vlm" else blocks,
                                                     source=roi if stage == "roi_vlm" else image,
                                                     deadline=deadline, cancel=cancel, on_call=count)
                    if not check():
                        stop = "deadline"
                        break
                    value = _candidate_path(fields, proposal, path)
                    if value is None:
                        record(stage, "no_safe_candidate", before["status"])
                        continue
                    candidate = _patch(fields, path, value)
                    proposed_quality, proposed_groundings = _quality(candidate, schema, evidence)
                    after = proposed_quality.get(path, {})
                    old_rank = {"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(before["status"], 2)
                    new_rank = {"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(after.get("status"), 2)
                    regression = any({"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(item["status"], 2)
                                     > {"PASS": 0, "CORRECTED": 0, "SUSPICIOUS": 1, "UNRESOLVED": 2}.get(quality.get(key, {}).get("status"), 2)
                                     for key, item in proposed_quality.items() if key != path)
                    source_blocks = local if stage in {"roi_parse", "roi_vlm"} else evidence
                    parts = path.split("/")
                    table_cell = (len(parts) == 3 and parts[1].isdigit()
                                  and isinstance(fields.get(root), list))
                    semantic = table_cell or _label_seen(root, schema, source_blocks)
                    exact = after.get("status") == "PASS" and after.get("provenance", {}).get("match") == "exact"
                    rule_clean = True
                    if check_rules is not None:
                        signature = lambda flag: json.dumps(flag, ensure_ascii=False, sort_keys=True, default=str)
                        old_flags = {signature(flag) for flag in check_rules(fields, blocks)}
                        new_flags = {signature(flag) for flag in check_rules(candidate, evidence)}
                        rule_clean = not (new_flags - old_flags)
                    proven = exact and semantic and rule_clean
                    improved = new_rank < old_rank or (candidate != fields and old_rank == 0 and new_rank == 0)
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
                except Exception:
                    if cancel is not None and cancel.is_set():
                        check()
                    record(stage, "parse_failed" if stage == "roi_parse" else "stage_failed", before["status"])
            else:
                stop = "no_improvement"
    if stop == "complete" and any(item["status"] not in {"PASS", "CORRECTED"} for item in quality.values()):
        stop = "unresolved"
    return finished(stop)
