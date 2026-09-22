"""라벨셋(scripts/verify_label.py 산출물) 기준으로 Docraft 파이프라인 단계별 필드 정확도를 계산한다.

단계
----
- raw    : ``backend.engine.extract`` 결과 (스키마: ``backend.doctypes.schema`` 또는 fallback)
- rules  : raw에 ``backend.rules.apply`` 적용
- ao     : gold만. AO 응답의 값(``backend.verify.flatten``)
- final  : gold만. ``backend.verify.run(image, ao_json, doc_type)`` 최종값

``backend.doctypes``/``backend.rules``/``backend.verify``가 아직 구현 전이면(``NotImplementedError``/
``ImportError``) 그 단계를 "미구현"으로 표시하고 건너뛴다 — 스크립트 자체는 항상 끝까지 돈다.

정확도 = (라벨이 값을 가진 필드 중 ``rules.same(kind, label, pred)``가 True인 수) / (라벨이 값을 가진 필드 수).
null 라벨은 분모에서 뺀다. 라벨이 null인데 예측이 있으면 오탐(false positive)으로 따로 센다.
표는 라벨 행과 예측 행을 순서대로 짝짓고 셀 단위로 센다 — 행 수가 다르면 남는 라벨 셀은 누락(값이 있으면
오답), 남는 예측 셀은 오탐으로 자연히 집계된다(모자란 쪽을 빈 행으로 채워 같은 채점 로직을 그대로 쓴다).

캐시
----
파싱은 이미지당 20~90초로 느려 ``data/verify/cache/<doc_type>__<stem>.parse.json``에,
추출 결과를 ``<doc_type>__<stem>.extract.json``에 캐시한다(파일명에 doc_type을 붙여 다른 유형 간
동명 이미지 충돌을 막는다). ``--no-cache``로 무시하고 다시 계산한다.

사용법
------
    # gold 4건에 raw 단계만 (다른 단계가 미구현이어도 동작 확인용)
    ../../.venv/bin/python scripts/verify_eval.py --grade gold --stage raw

    # 전체 라벨셋, 전체 단계, verbose로 오답 목록까지
    ../../.venv/bin/python scripts/verify_eval.py --verbose

    # 유형 하나만, 캐시 무시하고 재계산, 동시성 3
    ../../.venv/bin/python scripts/verify_eval.py --doc-type 진단서 --no-cache --workers 3

출력 예시(요약)::

    ## 유형별·단계별 정확도

    | 유형 | raw | rules | ao | final |
    |---|---|---|---|---|
    | 진단서 | 71.4% (20/28) | 미구현 | 92.9% (26/28) | 미구현 |

전체 결과(필드 단위 정오표 포함)는 ``data/verify/eval-<timestamp>.json``에 저장된다.
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 같은 디렉터리: verify_label 임포트용
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo(worktree) root: backend 패키지 임포트용

from verify_label import DOC_TYPES, LABELS_ROOT, REPO_ROOT, schema_for  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("verify_eval")

CACHE_ROOT = REPO_ROOT / "data" / "verify" / "cache"
RESULTS_ROOT = REPO_ROOT / "data" / "verify"
STAGES = ("raw", "rules", "ao", "final")
GOLD_ONLY_STAGES = {"ao", "final"}
NOT_IMPLEMENTED = "미구현"


# --------------------------------------------------------------------------------------
# doctypes.kind / rules.same — 미구현이면 일반 fallback을 쓴다
# --------------------------------------------------------------------------------------

def _fallback_same(a, b) -> bool:
    a = None if a in (None, "") else str(a).strip()
    b = None if b in (None, "") else str(b).strip()
    return a == b


def field_kind(doc_type: str, key: str, table: str | None = None) -> str:
    try:
        from backend import doctypes

        return doctypes.kind(doc_type, key, table=table)
    except NotImplementedError:
        return "text"


def values_same(kind: str, a, b) -> bool:
    try:
        from backend import rules

        return rules.same(kind, a, b)
    except NotImplementedError:
        return _fallback_same(a, b)


# --------------------------------------------------------------------------------------
# 캐시된 parse/extract
# --------------------------------------------------------------------------------------

def _cache_path(kind: str, doc_type: str, stem: str) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{doc_type}__{stem}.{kind}.json"


def cached_parse(image_path: Path, doc_type: str, no_cache: bool):
    path = _cache_path("parse", doc_type, image_path.stem)
    if not no_cache and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["markdown"], data["blocks"]
    from backend import parsers

    media_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    markdown, blocks = parsers.parse(str(image_path), image_path.name, media_type)
    path.write_text(json.dumps({"markdown": markdown, "blocks": blocks}, ensure_ascii=False, default=str), encoding="utf-8")
    return markdown, blocks


def cached_extract(image_path: Path, doc_type: str, blocks: list, schema: dict, no_cache: bool):
    path = _cache_path("extract", doc_type, image_path.stem)
    if not no_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["result"]
    from backend import engine

    result, _grounding = engine.extract(schema, blocks, source=str(image_path))
    path.write_text(json.dumps({"result": result}, ensure_ascii=False, default=str), encoding="utf-8")
    return result


# --------------------------------------------------------------------------------------
# 단계별 예측
# --------------------------------------------------------------------------------------

class Item:
    def __init__(self, label_path: Path):
        self.label_path = label_path
        self.label = json.loads(label_path.read_text(encoding="utf-8"))
        self.doc_type = self.label["doc_type"]
        self.grade = self.label["grade"]
        self.image_path = Path(self.label["image"])
        self.fields = self.label["fields"]
        self.ao_path = self.label.get("ao")


def run_stages(item: Item, schema: dict, stages: tuple[str, ...], no_cache: bool) -> tuple[dict, dict]:
    """(단계 -> 예측 dict|NOT_IMPLEMENTED|None, 단계 -> 오류 메시지)."""
    preds: dict = {}
    errors: dict = {}
    blocks = None
    if "raw" in stages or "rules" in stages:
        try:
            _markdown, blocks = cached_parse(item.image_path, item.doc_type, no_cache)
        except Exception as exc:
            errors["parse"] = str(exc)

    if "raw" in stages:
        if blocks is None:
            preds["raw"] = None
        else:
            try:
                preds["raw"] = cached_extract(item.image_path, item.doc_type, blocks, schema, no_cache)
            except (NotImplementedError, ImportError):
                preds["raw"] = NOT_IMPLEMENTED
            except Exception as exc:
                errors["raw"] = str(exc)
                preds["raw"] = None

    if "rules" in stages:
        raw = preds.get("raw")
        if not isinstance(raw, dict) or blocks is None:
            preds["rules"] = NOT_IMPLEMENTED if raw == NOT_IMPLEMENTED else None
        else:
            try:
                from backend import rules

                preds["rules"] = rules.apply(item.doc_type, raw, blocks)
            except (NotImplementedError, ImportError):
                preds["rules"] = NOT_IMPLEMENTED
            except Exception as exc:
                errors["rules"] = str(exc)
                preds["rules"] = None

    if "ao" in stages and item.grade == "gold" and item.ao_path:
        try:
            from backend.verify import flatten

            ao_doc = json.loads(Path(item.ao_path).read_text(encoding="utf-8"))["documents"][0]
            preds["ao"] = flatten(ao_doc)
        except (NotImplementedError, ImportError):
            preds["ao"] = NOT_IMPLEMENTED
        except Exception as exc:
            errors["ao"] = str(exc)
            preds["ao"] = None

    if "final" in stages and item.grade == "gold" and item.ao_path:
        try:
            from backend import verify as verify_mod
            from backend.verify import flatten

            ao_full = json.loads(Path(item.ao_path).read_text(encoding="utf-8"))
            output = verify_mod.run(str(item.image_path), ao_full, doc_type=item.doc_type)
            preds["final"] = flatten(output["documents"][0])
        except (NotImplementedError, ImportError):
            preds["final"] = NOT_IMPLEMENTED
        except Exception as exc:
            errors["final"] = str(exc)
            preds["final"] = None

    return preds, errors


# --------------------------------------------------------------------------------------
# 채점: score()는 (key, 라벨값, 예측값, kind) 평평한 목록을 내고, aggregate()가 그걸 correct/total/fp/wrong으로 묶는다.
# --------------------------------------------------------------------------------------

def score(doc_type: str, schema: dict, label_fields: dict, pred: dict) -> list[tuple[str, object, object, str]]:
    rows: list[tuple[str, object, object, str]] = []
    for key, prop in schema.get("properties", {}).items():
        if prop.get("type") == "array":
            columns = list(prop.get("items", {}).get("properties", {}).keys())
            label_rows = label_fields.get(key) if isinstance(label_fields.get(key), list) else []
            pred_rows = pred.get(key) if isinstance(pred.get(key), list) else []
            for i in range(max(len(label_rows), len(pred_rows))):
                lrow = label_rows[i] if i < len(label_rows) else {}
                prow = pred_rows[i] if i < len(pred_rows) else {}
                for col in columns:
                    rows.append((f"{key}.{col}", lrow.get(col), prow.get(col), field_kind(doc_type, col, table=key)))
        else:
            rows.append((key, label_fields.get(key), pred.get(key), field_kind(doc_type, key)))
    return rows


def aggregate(rows: list[tuple[str, object, object, str]]) -> dict:
    correct = total = fp = 0
    wrong = []
    for key, label_val, pred_val, kind in rows:
        if label_val in (None, ""):
            if pred_val not in (None, ""):
                fp += 1
                wrong.append((key, label_val, pred_val))
            continue
        total += 1
        if values_same(kind, label_val, pred_val):
            correct += 1
        else:
            wrong.append((key, label_val, pred_val))
    return {"correct": correct, "total": total, "fp": fp, "wrong": wrong}


def process_item(item: Item, stages: tuple[str, ...], no_cache: bool) -> dict:
    item_stages = tuple(s for s in stages if s not in GOLD_ONLY_STAGES or item.grade == "gold")
    schema = schema_for(item.doc_type)
    preds, errors = run_stages(item, schema, item_stages, no_cache)
    stage_stats = {}
    for stage in item_stages:
        pred = preds.get(stage)
        if pred == NOT_IMPLEMENTED:
            stage_stats[stage] = NOT_IMPLEMENTED
        elif not isinstance(pred, dict):
            stage_stats[stage] = {"correct": 0, "total": 0, "fp": 0, "wrong": [], "rows": [], "error": errors.get(stage, "예측 없음")}
        else:
            rows = score(item.doc_type, schema, item.fields, pred)
            stage_stats[stage] = {**aggregate(rows), "rows": rows}
    return {"doc_type": item.doc_type, "grade": item.grade, "image": item.image_path.name, "stages": stage_stats, "errors": errors}


# --------------------------------------------------------------------------------------
# 집계 + 출력
# --------------------------------------------------------------------------------------

def build_summaries(items_out: list[dict], doc_types: list[str], stages: tuple[str, ...]):
    """(유형별·단계별 요약, 유형·필드별·단계별 요약). NOT_IMPLEMENTED가 하나라도 나온 (유형,단계)는 그걸로 표시."""
    summary = {dt: {stage: {"correct": 0, "total": 0, "fp": 0} for stage in stages} for dt in doc_types}
    field_summary: dict = {dt: defaultdict(lambda: {stage: {"correct": 0, "total": 0, "fp": 0} for stage in stages}) for dt in doc_types}
    unimplemented = {dt: set() for dt in doc_types}
    for entry in items_out:
        doc_type = entry["doc_type"]
        for stage, stat in entry["stages"].items():
            if stat == NOT_IMPLEMENTED:
                unimplemented[doc_type].add(stage)
                continue
            agg = summary[doc_type][stage]
            agg["correct"] += stat["correct"]
            agg["total"] += stat["total"]
            agg["fp"] += stat["fp"]
            for key, label_val, pred_val, kind in stat["rows"]:
                cell = field_summary[doc_type][key][stage]
                if label_val in (None, ""):
                    if pred_val not in (None, ""):
                        cell["fp"] += 1
                    continue
                cell["total"] += 1
                if values_same(kind, label_val, pred_val):
                    cell["correct"] += 1
    for doc_type, stage_set in unimplemented.items():
        for stage in stage_set:
            summary[doc_type][stage] = NOT_IMPLEMENTED
            for key in field_summary[doc_type]:
                field_summary[doc_type][key][stage] = NOT_IMPLEMENTED
    return summary, {dt: dict(fields) for dt, fields in field_summary.items()}


def _cell(stat) -> str:
    if stat == NOT_IMPLEMENTED:
        return NOT_IMPLEMENTED
    correct, total, fp = stat["correct"], stat["total"], stat["fp"]
    if total == 0 and fp == 0:
        return "-"
    base = f"{100 * correct / total:.1f}% ({correct}/{total})" if total else "(0/0)"
    return base + (f" fp={fp}" if fp else "")


def print_overview(summary: dict, doc_types: list[str], stages: tuple[str, ...]):
    print("\n## 유형별·단계별 정확도\n")
    print("| 유형 | " + " | ".join(stages) + " |")
    print("|---" * (len(stages) + 1) + "|")
    for doc_type in doc_types:
        cells = [_cell(summary[doc_type][stage]) for stage in stages]
        print(f"| {doc_type} | " + " | ".join(cells) + " |")


def print_field_tables(field_summary: dict, doc_types: list[str], stages: tuple[str, ...]):
    for doc_type in doc_types:
        fields = field_summary.get(doc_type, {})
        if not fields:
            continue
        print(f"\n## 필드별 정확도 — {doc_type}\n")
        print("| 필드 | " + " | ".join(stages) + " |")
        print("|---" * (len(stages) + 1) + "|")
        for key, cells_by_stage in fields.items():
            cells = [_cell(cells_by_stage[stage]) for stage in stages]
            print(f"| {key} | " + " | ".join(cells) + " |")


def print_wrong(items_out: list[dict], stages: tuple[str, ...]):
    print("\n## 틀린 필드 목록\n")
    for entry in items_out:
        for stage in stages:
            stat = entry["stages"].get(stage)
            if not isinstance(stat, dict) or not stat.get("wrong"):
                continue
            print(f"\n### {entry['doc_type']}/{entry['image']} · {stage}")
            for key, label_val, pred_val in stat["wrong"]:
                print(f"- {key}: 라벨={label_val!r} 예측={pred_val!r}")


def strip_rows(entry: dict) -> dict:
    return {
        **entry,
        "stages": {
            stage: ({k: v for k, v in stat.items() if k != "rows"} if isinstance(stat, dict) else stat)
            for stage, stat in entry["stages"].items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doc-type", action="append", choices=DOC_TYPES)
    parser.add_argument("--grade", choices=["gold", "silver", "all"], default="all")
    parser.add_argument("--stage", action="append", choices=STAGES)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    doc_types = args.doc_type or DOC_TYPES
    stages = tuple(args.stage or STAGES)

    label_paths = [p for doc_type in doc_types for p in sorted((LABELS_ROOT / doc_type).glob("*.json"))]
    items = [Item(p) for p in label_paths]
    if args.grade != "all":
        items = [item for item in items if item.grade == args.grade]
    if not items:
        logger.warning("대상 라벨이 없습니다 (doc_type=%s grade=%s)", doc_types, args.grade)
        return

    logger.info("대상: %d건, 단계=%s, workers=%d, no_cache=%s", len(items), stages, args.workers, args.no_cache)
    started = time.monotonic()
    items_out = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_item, item, stages, args.no_cache): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                logger.error("실패: %s/%s: %s", item.doc_type, item.image_path.name, exc)
                continue
            items_out.append(result)
            logger.info(
                "완료: %s/%s (%s) -> %s",
                result["doc_type"], result["image"], result["grade"],
                {s: (v if v == NOT_IMPLEMENTED else f"{v['correct']}/{v['total']}") for s, v in result["stages"].items()},
            )
    elapsed = time.monotonic() - started
    logger.info("전체 완료: %d건, %.1fs 소요", len(items_out), elapsed)

    summary, field_summary = build_summaries(items_out, doc_types, stages)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = RESULTS_ROOT / f"eval-{timestamp}.json"
    out_path.write_text(json.dumps({
        "generated_at": timestamp,
        "args": {"doc_type": doc_types, "grade": args.grade, "stage": list(stages), "workers": args.workers, "no_cache": args.no_cache},
        "summary": summary,
        "items": [strip_rows(entry) for entry in items_out],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("결과 저장: %s", out_path)

    print_overview(summary, doc_types, stages)
    print_field_tables(field_summary, doc_types, stages)
    if args.verbose:
        print_wrong(items_out, stages)


if __name__ == "__main__":
    main()
