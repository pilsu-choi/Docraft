"""라벨셋(scripts/verify_label.py 산출물) 기준으로 Docraft 파이프라인 단계별 필드 정확도를 계산한다.

단계
----
- raw    : ``backend.engine.extract`` 결과 (스키마: ``backend.doctypes.schema`` 또는 fallback)
- rules  : raw에 ``backend.rules.apply`` 적용
- ao     : 실제 AO JSON이 연결된 문서. AO 응답의 값(``backend.verify.flatten``)
- final  : 실제 AO JSON이 연결된 문서. ``backend.verify.run(image, ao_json, doc_type)`` 최종값

``backend.doctypes``/``backend.rules``/``backend.verify``가 아직 구현 전이면(``NotImplementedError``/
``ImportError``) 그 단계를 "미구현"으로 표시하고 건너뛴다 — 스크립트 자체는 항상 끝까지 돈다.

정확도 = (라벨이 값을 가진 필드 중 ``rules.same(kind, label, pred)``가 True인 수) / (라벨이 값을 가진 필드 수).
null 라벨은 분모에서 뺀다. 값의 같고 다름은 오탐 판정까지 전부 ``rules.same``에 맡긴다 — 라벨 null과
예측 ``"0"``·빈 문자열처럼 표기만 다른 쌍을 오탐에서 뺄지는 ``rules.same``이 정한다.
정규화 후 완전 일치(strict)와 strict 오탐도 별도로 집계한다. AO가 없는 문서는 skipped,
실행에 실패한 문서는 error로 기록하며, 정확도는 평가에 성공한 문서의 필드를 대상으로 한다.

표 행은 ``backend.rules.pair_rows``가 행 식별 열(``rules.ROW_KEYS``)로 짝짓는다 — 채점과 교차검증이
같은 규칙을 쓰도록 정의를 한 곳에 둔다. 끝내 짝이 없는 행은 빈 행과 맞물려 누락(라벨 쪽)·과잉(예측 쪽)으로
집계된다. 라벨에 집계 행이 없으면 예측의 합계·소계 행은 채점에서 뺀다(표기 관례 차이일 뿐이다).

캐시
----
파싱은 이미지당 20~90초로 느려 ``data/verify/cache/<doc_type>__<stem>.parse.json``에,
추출 결과를 ``<doc_type>__<stem>.extract.json``에 캐시한다(파일명에 doc_type을 붙여 다른 유형 간
동명 이미지 충돌을 막는다). ``--no-cache``로 무시하고 다시 계산한다.
``--cache-root``로 실험별 캐시를 격리할 수 있다. 모델·스키마를 바꿀 때는 새 경로나 ``--no-cache``를 쓴다.
캐시 대상은 raw·rules가 쓰는 parse·extract뿐이다. ``ao``는 AO json을 그대로 읽고 ``final``은 매번
``backend.verify.run``을 새로 호출하므로(그 안에서 parse·extract를 다시 돈다) verify.py가 바뀌면 곧바로 반영된다.

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


def strict_same(kind: str, a, b) -> bool:
    """정규화 뒤 완전 일치. ``rules.same``의 접두/0-빈칸 관용은 적용하지 않는다."""
    try:
        from backend import rules

        return rules.normalize(kind, a) == rules.normalize(kind, b)
    except (NotImplementedError, ImportError):
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
    # rules만 요청해도 그 입력인 raw를 계산한다. raw는 결과 단계로 노출하지 않는다.
    if "raw" in stages or "rules" in stages:
        try:
            _markdown, blocks = cached_parse(item.image_path, item.doc_type, no_cache)
        except Exception as exc:
            errors["parse"] = str(exc)

    if "raw" in stages or "rules" in stages:
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

    has_ao = bool(item.ao_path and Path(item.ao_path).is_file())
    if "ao" in stages and has_ao:
        try:
            from backend.verify import flatten

            ao_doc = json.loads(Path(item.ao_path).read_text(encoding="utf-8"))["documents"][0]
            preds["ao"] = flatten(ao_doc)
        except (NotImplementedError, ImportError):
            preds["ao"] = NOT_IMPLEMENTED
        except Exception as exc:
            errors["ao"] = str(exc)
            preds["ao"] = None

    if "final" in stages and has_ao:
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

def pair_rows(doc_type: str, table: str, columns: list[str], label_rows: list, pred_rows: list) -> list[tuple[dict, dict]]:
    """행을 짝짓는다. 짝짓기 규칙(키 열 ``rules.ROW_KEYS``)은 ``rules.pair_rows``가 한 곳에서 정한다.

    라벨에 집계 행이 없으면 예측의 합계·소계 행도 채점에서 뺀다 — 집계 행을 표에 둘지는 표기 관례 차이일 뿐이다.
    """
    try:
        from backend import rules
    except ImportError:
        return list(zip(label_rows, pred_rows))
    if "항목" in columns and not any(rules.is_total(row) for row in label_rows):
        pred_rows = [row for row in pred_rows if not rules.is_total(row)]
    return [(lrow or {}, prow or {})
            for lrow, prow in rules.pair_rows(doc_type, table, label_rows, pred_rows, columns)]


def score(doc_type: str, schema: dict, label_fields: dict, pred: dict) -> list[tuple[str, object, object, str]]:
    rows: list[tuple[str, object, object, str]] = []
    for key, prop in schema.get("properties", {}).items():
        if prop.get("type") == "array":
            columns = list(prop.get("items", {}).get("properties", {}).keys())
            label_rows = label_fields.get(key) if isinstance(label_fields.get(key), list) else []
            pred_rows = pred.get(key) if isinstance(pred.get(key), list) else []
            for lrow, prow in pair_rows(doc_type, key, columns, label_rows, pred_rows):
                for col in columns:
                    rows.append((f"{key}.{col}", lrow.get(col), prow.get(col), field_kind(doc_type, col, table=key)))
        else:
            rows.append((key, label_fields.get(key), pred.get(key), field_kind(doc_type, key)))
    return rows


def verdict(label_val, pred_val, kind: str) -> str:
    """``correct``·``wrong``·``fp``(라벨 null인데 예측이 다름)·``skip``(둘 다 비어 일치). 판정은 전부 ``rules.same``이 한다."""
    agrees = values_same(kind, label_val, pred_val)
    if label_val in (None, ""):
        return "skip" if agrees else "fp"
    return "correct" if agrees else "wrong"


def aggregate(rows: list[tuple[str, object, object, str]]) -> dict:
    stat = {"correct": 0, "total": 0, "fp": 0, "strict_correct": 0, "strict_total": 0, "strict_fp": 0}
    wrong = []
    for key, label_val, pred_val, kind in rows:
        result = verdict(label_val, pred_val, kind)
        strict = strict_same(kind, label_val, pred_val)
        if result == "skip":
            stat["strict_fp"] += not strict
            continue
        if result == "fp":
            stat["fp"] += 1
            stat["strict_fp"] += not strict
        else:
            stat["total"] += 1
            stat["correct"] += result == "correct"
            stat["strict_total"] += 1
            stat["strict_correct"] += strict
        if result != "correct":
            wrong.append((key, label_val, pred_val))
    return {**stat, "wrong": wrong}


def process_item(item: Item, stages: tuple[str, ...], no_cache: bool) -> dict:
    item_stages = stages
    schema = schema_for(item.doc_type)
    preds, errors = run_stages(item, schema, item_stages, no_cache)
    stage_stats = {}
    for stage in item_stages:
        pred = preds.get(stage)
        if pred == NOT_IMPLEMENTED:
            stage_stats[stage] = NOT_IMPLEMENTED
        elif not isinstance(pred, dict):
            reason = errors.get(stage, "AO 결과 없음" if stage in {"ao", "final"} else "예측 없음")
            stage_stats[stage] = {"correct": 0, "total": 0, "fp": 0, "strict_correct": 0, "strict_total": 0, "strict_fp": 0, "wrong": [], "rows": [], "error": reason}
        else:
            rows = score(item.doc_type, schema, item.fields, pred)
            stage_stats[stage] = {**aggregate(rows), "rows": rows}
    return {"doc_type": item.doc_type, "grade": item.grade, "image": item.image_path.name,
            "label": str(item.label_path.resolve()), "labeler": item.label.get("labeler"),
            "label_provenance": item.label.get("provenance"), "split": getattr(item, "split", None), "stages": stage_stats, "errors": errors}


# --------------------------------------------------------------------------------------
# 집계 + 출력
# --------------------------------------------------------------------------------------

def build_summaries(items_out: list[dict], doc_types: list[str], stages: tuple[str, ...]):
    """(유형별·단계별 요약, 유형·필드별·단계별 요약). NOT_IMPLEMENTED가 하나라도 나온 (유형,단계)는 그걸로 표시."""
    summary = {dt: {stage: {"correct": 0, "total": 0, "fp": 0, "strict_correct": 0, "strict_total": 0, "strict_fp": 0,
                            "evaluated": 0, "skipped": 0, "error": 0} for stage in stages} for dt in doc_types}
    field_summary: dict = {dt: defaultdict(lambda: {stage: {"correct": 0, "total": 0, "fp": 0} for stage in stages}) for dt in doc_types}
    unimplemented = {dt: set() for dt in doc_types}
    for entry in items_out:
        doc_type = entry["doc_type"]
        for stage, stat in entry["stages"].items():
            if stat == NOT_IMPLEMENTED:
                unimplemented[doc_type].add(stage)
                continue
            agg = summary[doc_type][stage]
            if stat.get("error"):
                if stat["error"] == "AO 결과 없음":
                    agg["skipped"] += 1
                else:
                    agg["error"] += 1
                continue
            agg["evaluated"] += 1
            agg["correct"] += stat["correct"]
            agg["total"] += stat["total"]
            agg["fp"] += stat["fp"]
            agg["strict_correct"] += stat["strict_correct"]
            agg["strict_total"] += stat["strict_total"]
            agg["strict_fp"] += stat["strict_fp"]
            for key, label_val, pred_val, kind in stat["rows"]:
                cell = field_summary[doc_type][key][stage]
                result = verdict(label_val, pred_val, kind)
                if result == "skip":
                    continue
                if result == "fp":
                    cell["fp"] += 1
                    continue
                cell["total"] += 1
                cell["correct"] += result == "correct"
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
    counts = f" eval={stat['evaluated']} skip={stat['skipped']} error={stat['error']}" if "evaluated" in stat else ""
    if total == 0 and fp == 0:
        return "-" + counts
    base = f"{100 * correct / total:.1f}% ({correct}/{total})" if total else "(0/0)"
    strict = (f" strict={100 * stat['strict_correct'] / stat['strict_total']:.1f}% ({stat['strict_correct']}/{stat['strict_total']})"
              if stat.get("strict_total") else (" strict=-" if "strict_total" in stat else ""))
    return base + strict + (f" fp={fp}" if fp else "") + (f" strict_fp={stat['strict_fp']}" if stat.get("strict_fp") else "") + counts


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


def print_top_failures(field_summary: dict, doc_types: list[str], stages: tuple[str, ...], limit: int = 20):
    """유형·필드별 오답(+오탐)을 합쳐 많은 순으로 — 룰 확장 대상을 고르는 표다."""
    ranked = []
    for doc_type in doc_types:
        for key, by_stage in field_summary.get(doc_type, {}).items():
            cells = [by_stage[s] for s in stages if by_stage[s] != NOT_IMPLEMENTED]
            miss = sum(cell["total"] - cell["correct"] + cell["fp"] for cell in cells)
            if miss:
                ranked.append((miss, doc_type, key, by_stage))
    if not ranked:
        return
    ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
    print(f"\n## 실패 상위 {limit} 필드 (셀은 오답수/분모, fp=오탐)\n")
    print("| # | 유형 | 필드 | 실패 | " + " | ".join(stages) + " |")
    print("|---" * (len(stages) + 4) + "|")
    for rank, (miss, doc_type, key, by_stage) in enumerate(ranked[:limit], 1):
        cells = []
        for stage in stages:
            cell = by_stage[stage]
            if cell == NOT_IMPLEMENTED:
                cells.append(NOT_IMPLEMENTED)
                continue
            wrong = cell["total"] - cell["correct"]
            cells.append(f"{wrong}/{cell['total']}" + (f" fp={cell['fp']}" if cell["fp"] else "") if wrong or cell["fp"] else "-")
        print(f"| {rank} | {doc_type} | {key} | {miss} | " + " | ".join(cells) + " |")


def print_wrong(items_out: list[dict], stages: tuple[str, ...]):
    print("\n## 틀린 필드 목록 — `단계 | 이미지 | 필드: 라벨 | 예측`\n")
    for entry in items_out:
        for stage in stages:
            stat = entry["stages"].get(stage)
            if not isinstance(stat, dict) or not stat.get("wrong"):
                continue
            print(f"\n### {entry['doc_type']}/{entry['image']} · {stage} ({len(stat['wrong'])}건)")
            for key, label_val, pred_val in stat["wrong"]:
                print(f"- {stage} | {entry['image']} | {key}: {label_val!r} | {pred_val!r}")


def strip_rows(entry: dict) -> dict:
    return {
        **entry,
        "stages": {
            stage: ({k: v for k, v in stat.items() if k != "rows"} if isinstance(stat, dict) else stat)
            for stage, stat in entry["stages"].items()
        },
    }


def main():
    global CACHE_ROOT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doc-type", action="append", choices=DOC_TYPES)
    parser.add_argument("--grade", choices=["gold", "silver", "all"], default="all")
    parser.add_argument("--stage", action="append", choices=STAGES)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-root", type=Path, help="실험별 파싱·추출 캐시 경로 (기존 캐시와 격리)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--manifest", type=Path, help="확장 매니페스트의 기존+holdout 라벨만 평가한다")
    parser.add_argument("--split", choices=["existing", "holdout", "all"], default="all", help="--manifest 평가 split (기본 all)")
    args = parser.parse_args()
    if args.cache_root:
        CACHE_ROOT = args.cache_root.resolve()

    doc_types = args.doc_type or DOC_TYPES
    stages = tuple(args.stage or STAGES)

    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        selected_items = [item for item in manifest["items"] if item["doc_type"] in doc_types and
                          (args.split == "all" or item.get("split") == args.split)]
        selected = {(item["doc_type"], str(Path(item["image"]).resolve())) for item in selected_items}
        split_by_image = {(item["doc_type"], str(Path(item["image"]).resolve())): item.get("split") for item in selected_items}
        roots = {LABELS_ROOT, Path(manifest["label_root"])}
        label_paths = []
        for root in roots:
            for path in root.glob("*/*.json"):
                label = json.loads(path.read_text(encoding="utf-8"))
                if (label.get("doc_type"), str(Path(label.get("image", "")).resolve())) in selected:
                    label_paths.append(path)
        label_paths = sorted(set(label_paths))
        found = {(json.loads(path.read_text(encoding="utf-8")).get("doc_type"),
                  str(Path(json.loads(path.read_text(encoding="utf-8")).get("image", "")).resolve())) for path in label_paths}
        missing = selected - found
        if missing:
            raise RuntimeError(f"매니페스트 라벨 누락: {len(missing)}건 (먼저 verify_label.py --manifest 실행 필요)")
    else:
        label_paths = [p for doc_type in doc_types for p in sorted((LABELS_ROOT / doc_type).glob("*.json"))]
    items = [Item(p) for p in label_paths]
    if args.manifest:
        for item in items:
            item.split = split_by_image[(item.doc_type, str(item.image_path.resolve()))]
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
                result = {"doc_type": item.doc_type, "grade": item.grade, "image": item.image_path.name,
                          "label": str(item.label_path.resolve()), "labeler": item.label.get("labeler"),
                          "split": getattr(item, "split", None), "errors": {"process": str(exc)},
                          "stages": {stage: {"correct": 0, "total": 0, "fp": 0, "strict_correct": 0,
                                             "strict_total": 0, "strict_fp": 0, "wrong": [], "rows": [], "error": str(exc)} for stage in stages}}
                items_out.append(result)
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
    split_summary = {split: build_summaries([entry for entry in items_out if entry.get("split") == split], doc_types, stages)[0]
                     for split in ("existing", "holdout") if any(entry.get("split") == split for entry in items_out)}

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = RESULTS_ROOT / f"eval-{timestamp}.json"
    out_path.write_text(json.dumps({
        "version": 2,
        "generated_at": timestamp,
        "args": {"doc_type": doc_types, "grade": args.grade, "stage": list(stages), "workers": args.workers, "no_cache": args.no_cache,
                 "manifest": str(args.manifest.resolve()) if args.manifest else None,
                 "cache_root": str(CACHE_ROOT.resolve())},
        "provenance": {"labels": [str(path.resolve()) for path in label_paths], "comparison": "legacy rules.same + strict rules.normalize exact"},
        "summary": summary,
        "split_summary": split_summary,
        "items": [strip_rows(entry) for entry in items_out],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("결과 저장: %s", out_path)

    print_overview(summary, doc_types, stages)
    print_field_tables(field_summary, doc_types, stages)
    print_top_failures(field_summary, doc_types, stages)
    if args.verbose:
        print_wrong(items_out, stages)


if __name__ == "__main__":
    main()
