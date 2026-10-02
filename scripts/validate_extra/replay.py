"""저장된 응답에 지금 코드의 규칙·게이트를 다시 적용한다(LLM·OCR 호출 없음). 열 배치·프롬프트가 바뀐 문서만 새로 읽은 결과(--new)를 쓴다.

문서마다: rowmajor 응답(--new에 있으면 그것, 없으면 --rowmajor 저장본) → rules.apply → table_misses ≥ TABLE_RECHECK_RATIO면
asis 저장본(--asis)으로 바꾼다(실제 verify.read 의 다시 읽기와 같다. 지연·호출·토큰은 두 응답을 더한다). asis 저장본도 같은 규칙으로 다시 적용해
<out>/asis 에 쓴다. 저장본의 응답 행은 ``first_rows``(정규화 전)를 쓰고, 없으면(정답지 이식 결과) ``rows``(규칙 적용 뒤)에 규칙을 다시 적용한다
(규칙은 다시 적용해도 같은 값이다). 기록에 맞바꾸거나 의심한 열(column_swaps)을 더한다. --no-filldown 은 무리 값 채우기(섹션 제목·생략 칸·진료기간→행)를 끄고 적용한다.
  replay.py --ocr <ocr> --rowmajor <dir> --asis <dir> [--new <dir>] --out <dir> [--doc-type 세부내역서] [--no-filldown]"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import engine, latency, rules  # noqa: E402

ap = argparse.ArgumentParser()
for name in ("--ocr", "--rowmajor", "--asis", "--out"):
    ap.add_argument(name, type=Path, required=True)
ap.add_argument("--new", type=Path)
ap.add_argument("--doc-type", default="세부내역서")
ap.add_argument("--no-filldown", action="store_true")
args = ap.parse_args()


def one_way_period(out):
    """무리 값 채우기 이전의 ``rules._period``: 표 날짜 → 진료기간 칸만."""
    for key in [key for key in out if isinstance(key, str) and not out.get(key)]:
        column = "시작일자" if "진료시작일" in key else "종료일자" if "진료종료일" in key else None
        if dates := sorted(row[column] for row in out.get(rules.ITEM_TABLE) or [] if column and row.get(column)):
            out[key] = dates[0] if column == "시작일자" else dates[-1]


if args.no_filldown:
    rules._title_lines, rules._carry, rules._period = lambda blocks: [], lambda rows, column: None, one_way_period
    for key in ("환자정보(진료시작일)", "환자정보(진료종료일)"):
        rules.LABELS[key] = [label for label in rules.LABELS[key] if label != "입원기간"]


def load(folder, name):
    path = folder / f"{name}.json" if folder else None
    return json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else None


def rows_of(rec):
    return rec.get("first_rows") if "first_rows" in rec else ((rec.get("rows") or {}).get(rules.ITEM_TABLE))


def applied(rec, blocks):
    """규칙을 다시 적용한 기록. 맞바꾸거나 의심한 열(``column_swaps``)도 남긴다."""
    if rows_of(rec) is None:
        return {**rec, "column_swaps": None}
    with latency.track() as stages:
        rows = rules.apply(args.doc_type, {rules.ITEM_TABLE: rows_of(rec)}, blocks)
    return {**rec, "rows": rows, "column_swaps": stages.get("column_swaps")}


ratio = engine.ai_settings()["table_recheck_ratio"]
for path in sorted(args.ocr.glob("*.json")):
    name, blocks = path.name.removesuffix(".json"), json.loads(path.read_text(encoding="utf-8"))["blocks"]
    first, asis = load(args.new, name) or load(args.rowmajor, name), load(args.asis, name)
    if first is None:
        continue
    out = applied(first, blocks)
    raw = rows_of(first)
    gated = bool(raw) and not first.get("error") and rules.table_misses(args.doc_type, raw, out["rows"]) >= ratio
    if gated and asis:
        again = applied(asis, blocks)
        out = {**out, "rows": again["rows"], "column_swaps": again["column_swaps"], "elapsed_ms": first["elapsed_ms"] + asis["elapsed_ms"], "calls": first["calls"] + asis["calls"],
               "usage": {k: first["usage"][k] + asis["usage"][k] for k in first["usage"]}}
    out.update(extracts=1 + gated, misses=rules.table_misses(args.doc_type, raw, applied(first, blocks)["rows"]) if raw else None,
               source="new" if load(args.new, name) else "saved")
    for arm, rec in (("rowmajor", out), ("asis", applied(asis, blocks) if asis else None)):
        if rec:
            target = args.out / arm / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
