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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--indices", default="0,20,25")
    parser.add_argument("--seed", action="store_true", help="One deliberately wrong scalar; separately reported from natural cases")
    parser.add_argument("--seed-only", action="store_true", help="Skip natural replay and inspect only the seeded case")
    parser.add_argument("--seed-key", help="Schema scalar key to seed (defaults to the first nonempty scalar)")
    args = parser.parse_args()
    items = json.loads(args.manifest.read_text())["items"]
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
        if not args.seed_only:
            output, _, quality, summary = reprocess.run(str(image), schema, blocks, fields, normalize=normalize,
                                                          check_rules=check_rules, deadline=time.monotonic() + 90)
            report.append({"index": index, "doc_type": item["doc_type"], "mode": "natural",
                           "before": baseline["status"], "after": summary["status"],
                           "attempts": summary["attempts"], "extra_model_calls": summary["extra_model_calls"],
                           "stop_reason": summary["stop_reason"], "elapsed_ms": summary["elapsed_ms"],
                           "trace": [{name: step.get(name) for name in ("field", "stage", "reason", "status", "adopted", "checks")}
                                     for step in summary["trace"]],
                           "adopted": sum(bool(step["adopted"]) for step in summary["trace"]),
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
                label_path = Path(json.loads(args.manifest.read_text())["label_root"]) / item["doc_type"] / f"{image.stem}.json"
                label = json.loads(label_path.read_text())["fields"].get(key) if label_path.exists() else None
                kind = doctypes.kind(item["doc_type"], key)
                report.append({"index": index, "doc_type": item["doc_type"], "mode": "seeded",
                               "restored_exact": recovered.get(key) == fields[key],
                               "restored_normalized": engine._normalized(recovered.get(key)) == engine._normalized(fields[key]),
                               "restored_semantic": rules.same(kind, recovered.get(key), fields[key]),
                               "baseline_matches_silver": rules.same(kind, fields[key], label) if label is not None else None,
                               "candidate_matches_silver": rules.same(kind, recovered.get(key), label) if label is not None else None,
                               "status": seeded_summary["status"], "attempts": seeded_summary["attempts"],
                               "extra_model_calls": seeded_summary["extra_model_calls"],
                               "stop_reason": seeded_summary["stop_reason"], "elapsed_ms": seeded_summary["elapsed_ms"],
                               "trace": [{name: step.get(name) for name in ("field", "stage", "reason", "status", "adopted", "checks")}
                                         for step in seeded_summary["trace"]]})
                print(json.dumps(report[-1], ensure_ascii=False, default=str), flush=True)
    print(json.dumps({"cases": report}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
