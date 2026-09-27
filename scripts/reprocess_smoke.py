"""Replay independent cached readings through the live bounded recovery loop.

Prints only counts and status codes. Original images and cached values stay local.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import doctypes, engine, reprocess, rules


def _escape(part):
    return str(part).replace("~", "~0").replace("/", "~1")


def _parts(path):
    return [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")]


def changed_leaves(before, after, path=""):
    """최종 값이 다른 leaf 경로만 반환한다. 값 자체는 보고서에 싣지 않는다."""
    if isinstance(before, dict) and isinstance(after, dict):
        keys = before.keys() | after.keys()
        return [leaf for key in sorted(keys) for leaf in changed_leaves(before.get(key), after.get(key),
                                                                          f"{path}/{_escape(key)}" if path else _escape(key))]
    if isinstance(before, list) and isinstance(after, list):
        return [leaf for index in range(max(len(before), len(after)))
                for leaf in changed_leaves(before[index] if index < len(before) else None,
                                           after[index] if index < len(after) else None,
                                           f"{path}/{index}")]
    return [path] if before != after else []


def _at(values, path):
    node = values
    for part in _parts(path):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def _unique_row_pair(doc_type, table, row, mate, baseline_rows, label_rows):
    """중복 키나 접두 일치로 묶인 행은 silver 채점에서 제외한다."""
    keys = [key for key in rules.ROW_KEYS.get(table, ()) if key in doctypes.spec(doc_type)["tables"].get(table, ())]
    if not keys or not any(row.get(key) not in (None, "") for key in keys):
        return False
    def same_keys(left, right):
        return all(rules.same(doctypes.kind(doc_type, key, table), left.get(key), right.get(key)) for key in keys)
    return (sum(same_keys(row, other) for other in label_rows) == 1
            and sum(same_keys(other, mate) for other in baseline_rows) == 1
            and same_keys(row, mate))


def changed_silver_matches(doc_type, before, after, paths, label):
    """유일하게 식별된 known leaf만 loose 동치로 채점한다. null/0은 같은 금액으로 취급한다."""
    counts = Counter()
    if not isinstance(label, dict) or not isinstance(label.get("fields"), dict):
        return {"known": 0, "unknown_excluded": 0, "unmatched_or_unlabeled": len(paths),
                "baseline_matches": 0, "candidate_matches": 0, "improved": 0, "regressed": 0}
    truth = label["fields"]
    unknown = set(label.get("provenance", {}).get("unknown_fields", []))
    for path in paths:
        parts = _parts(path)
        label_path = ".".join(parts)
        kind_key, table = parts[-1], None
        value = None
        matched = False
        if len(parts) == 3 and parts[1].isdigit() and isinstance(before.get(parts[0]), list):
            table, index = parts[0], int(parts[1])
            label_rows = truth.get(table)
            if isinstance(label_rows, list) and index < len(before[table]):
                pairs = rules.pair_rows(doc_type, table, before[table], label_rows, fallback=False)
                row = pairs[index][1]
                candidate_rows = after.get(table)
                if (isinstance(row, dict) and parts[2] in row
                        and isinstance(candidate_rows, list) and index < len(candidate_rows)
                        and isinstance(candidate_rows[index], dict)
                        and _unique_row_pair(doc_type, table, before[table][index], row, before[table], label_rows)
                        and _unique_row_pair(doc_type, table, candidate_rows[index], row, candidate_rows, label_rows)):
                    label_index = next((i for i, item in enumerate(label_rows) if item is row), None)
                    if label_index is not None:
                        label_path = f"{table}.{label_index}.{parts[2]}"
                        value, matched = row[parts[2]], True
        elif parts[0] in truth:
            node = truth
            for part in parts:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    break
            else:
                value, matched = node, True
        if any(label_path == key or label_path.startswith(f"{key}.") for key in unknown):
            counts["unknown_excluded"] += 1
        elif not matched:
            counts["unmatched_or_unlabeled"] += 1
        else:
            counts["known"] += 1
            kind = doctypes.kind(doc_type, kind_key, table=table)
            baseline = rules.same(kind, _at(before, path), value)
            candidate = rules.same(kind, _at(after, path), value)
            counts["baseline_matches"] += baseline
            counts["candidate_matches"] += candidate
            counts["improved"] += not baseline and candidate
            counts["regressed"] += baseline and not candidate
    return {key: counts[key] for key in ("known", "unknown_excluded", "unmatched_or_unlabeled",
                                          "baseline_matches", "candidate_matches", "improved", "regressed")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--indices", default="0,20,25")
    parser.add_argument("--seed", action="store_true", help="One deliberately wrong scalar; separately reported from natural cases")
    parser.add_argument("--seed-only", action="store_true", help="Skip natural replay and inspect only the seeded case")
    parser.add_argument("--seed-key", help="Schema scalar key to seed (defaults to the first nonempty scalar)")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    items = manifest["items"]
    report = []
    for index in [int(part) for part in args.indices.split(",")]:
        item = items[index]
        image = Path(item["image"])
        stem = f"{item['doc_type']}__{image.stem}"
        blocks = json.loads((args.cache / f"{stem}.parse.json").read_text())["blocks"]
        raw = json.loads((args.cache / f"{stem}.extract.json").read_text())["result"]
        schema = doctypes.schema(item["doc_type"])
        fields = rules.apply(item["doc_type"], raw, blocks)
        normalize = lambda values, evidence: rules.apply(item["doc_type"], values, evidence)
        check_rules = lambda values, evidence: rules.check(item["doc_type"], values, values, evidence)
        baseline = reprocess.run(str(image), schema, blocks, fields, normalize=normalize,
                                 check_rules=check_rules, enabled=False)[3]
        label_path = Path(manifest["label_root"]) / item["doc_type"] / f"{image.stem}.json"
        label = json.loads(label_path.read_text()) if label_path.exists() else None
        if not args.seed_only:
            output, _, quality, summary = reprocess.run(str(image), schema, blocks, fields, normalize=normalize,
                                                          check_rules=check_rules, deadline=time.monotonic() + 90)
            changed = changed_leaves(fields, output)
            report.append({"index": index, "doc_type": item["doc_type"], "mode": "natural",
                           "before": baseline["status"], "after": summary["status"],
                           "attempts": summary["attempts"], "extra_model_calls": summary["extra_model_calls"],
                           "stop_reason": summary["stop_reason"], "elapsed_ms": summary["elapsed_ms"],
                           "trace": [{name: step.get(name) for name in ("field", "stage", "reason", "status", "adopted", "checks")}
                                     for step in summary["trace"]],
                           "adopted": sum(bool(step["adopted"]) for step in summary["trace"]),
                           "changed_fields": changed, "corrected_values": len(changed),
                           "evidence_only_adoptions": sum(bool(step["adopted"]) and step.get("before") == step.get("after")
                                                          for step in summary["trace"]),
                           "changed_silver_matches": changed_silver_matches(item["doc_type"], fields, output,
                                                                            changed, label),
                           "untouched_roots": sum(output.get(key) == value for key, value in fields.items()),
                           "quality": dict(Counter(entry["status"] for entry in quality.values()))})
            print(json.dumps(report[-1], ensure_ascii=False, default=str), flush=True)
        if (args.seed or args.seed_only) and index == 0:
            key = args.seed_key or next((key for key, value in fields.items() if isinstance(value, str) and value.strip()), None)
            if key not in schema["properties"] or not isinstance(fields.get(key), str) or not fields[key].strip():
                raise ValueError("--seed-key는 결과에 값이 있는 스칼라 필드여야 합니다.")
            if key:
                seeded = {key: "[의도적으로 주입한 오독값]"}
                narrowed = {**schema, "properties": {key: schema["properties"][key]},
                            "required": [key] if key in schema.get("required", []) else []}
                recovered, _, _, seeded_summary = reprocess.run(
                    str(image), narrowed, blocks, seeded, normalize=normalize, check_rules=check_rules,
                    deadline=time.monotonic() + 90)
                silver_value = label["fields"].get(key) if label is not None else None
                kind = doctypes.kind(item["doc_type"], key)
                report.append({"index": index, "doc_type": item["doc_type"], "mode": "seeded",
                               "restored_exact": recovered.get(key) == fields[key],
                               "restored_normalized": engine._normalized(recovered.get(key)) == engine._normalized(fields[key]),
                               "restored_semantic": rules.same(kind, recovered.get(key), fields[key]),
                               "baseline_matches_silver": rules.same(kind, fields[key], silver_value) if silver_value is not None else None,
                               "candidate_matches_silver": rules.same(kind, recovered.get(key), silver_value) if silver_value is not None else None,
                               "status": seeded_summary["status"], "attempts": seeded_summary["attempts"],
                               "extra_model_calls": seeded_summary["extra_model_calls"],
                               "stop_reason": seeded_summary["stop_reason"], "elapsed_ms": seeded_summary["elapsed_ms"],
                               "trace": [{name: step.get(name) for name in ("field", "stage", "reason", "status", "adopted", "checks")}
                                         for step in seeded_summary["trace"]]})
                print(json.dumps(report[-1], ensure_ascii=False, default=str), flush=True)
    print(json.dumps({"cases": report}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
