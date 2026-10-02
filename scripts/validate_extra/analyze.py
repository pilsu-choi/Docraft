"""정답 없는 표본의 rowmajor·asis 결과를 정답 없이 비교한다(LLM·OCR 호출 없음).
산출: <base>/summary.json, per_doc.csv, diff_cells.csv
지표: 머리글 열 순서 판별률·실패 사유, 행 산술 통과율, 열 합과 인쇄된 합계 대조, 게이트 발동, asis 대체(fallback), 두 방식 칸 일치율, 행 수, 지연, 출력 토큰."""
import csv
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, "/home/pilsu/projects/mirae-assets/e2e")
from backend import doctypes, rules, table_layout  # noqa: E402
from make_report import norm  # noqa: E402

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/pilsu/projects/mirae-assets/e2e/out/extra-detail-1002")
DOC, TABLE, ARMS = "세부내역서", rules.ITEM_TABLE, ("rowmajor", "asis")
SPEC = doctypes.DOC_TYPES[DOC]["tables"][TABLE]
COLUMNS = list(SPEC)
GROUPS = {"금액": ["단가", "총액", "본인부담", "공단부담", "전액본인부담", "비급여", "급여", "선택진료료", "선택진료료외"],
          "코드·명칭": ["EDI코드", "원내코드", "EDI명칭", "항목"], "수량": ["투여량", "횟수", "일수"], "일자": ["시작일자", "종료일자"],
          "구분": ["급여구분"]}
GROUP_OF = {c: g for g, cs in GROUPS.items() for c in cs}
SUM_COLUMNS = ["총액", "본인부담", "공단부담", "전액본인부담", "비급여"]


def pct(values, p):
    s = sorted(values)
    return round(s[round((len(s) - 1) * p)], 1) if s else None


def plan_reason(blocks):
    """머리글 열 순서 판별 결과와 실패 사유."""
    union = {k: (v or {}).get("description", "") if isinstance(v, dict) else "" for k, v in SPEC.items()}
    if not any(b.get("type") == "table" for b in blocks):
        return "표 블록 없음"
    if not any(b.get("type") == "table" and b.get("lines") for b in blocks):
        return "표 줄 상자 없음"
    if table_layout.plan(DOC, TABLE, blocks, "", union):
        return "판별"
    tokens = [t for t in table_layout._tokens(blocks) if table_layout._concepts(t["text"])[0]]
    return "머리글 낱말 없음" if not tokens else "한 줄에 4열 미만"


def arith(fields):
    """(총액 있는 행 수, 행 산술 실패 행 수)"""
    doc = rules._Doc(DOC, fields or {}, {}, [])
    rule = next(rule for rule in rules.RULES if rule.detect is rules._row_arith)
    checkable = sum(rules._money(row.get("총액")) is not None for row in doc.rows)
    if not checkable or not doc.sees(rule):
        return checkable, 0
    return checkable, len({flag["row"] for flag in rule.detect(doc)})


def total_check(rows, blocks):
    """합계가 인쇄된 문서에서 행 열 합(총액·본인부담·공단부담·비급여)이 문서 글자 어딘가에 그대로 찍혀 있는지.
    스키마가 합계 행을 표에 넣지 않게 하므로 합계 행 대신 인쇄된 합계 금액과 맞춘다. (상태, 맞은 열, 비교 열)"""
    text = "\n".join([*rules._lines(blocks), *(str(c or "") for b in blocks for r in b.get("rows") or [] for c in r)])
    if not re.search(r"합\s*계|총\s*계|소\s*계", text):
        return "합계 없음", 0, 0
    compared = matched = 0
    for column in SUM_COLUMNS:
        total = sum(rules._money(r.get(column)) or 0 for r in rows or [])
        if total <= 0:
            continue
        compared += 1
        matched += rules._printed(int(total) if float(total).is_integer() else total, blocks)
    if not compared:
        return "금액 없음", 0, 0
    return ("일치" if matched == compared else "일부 일치" if matched else "불일치"), matched, compared


def key(row, mode):
    """mode: 0 = (코드 또는 명칭)+총액, 1 = 코드 또는 명칭, 2 = 명칭+총액(코드 오독), 3 = 총액·단가(명칭 오독)"""
    ident = norm(row.get("EDI코드")) or norm(row.get("원내코드")) or re.sub(r"\W", "", str(row.get("EDI명칭") or ""))
    name = re.sub(r"\W", "", str(row.get("EDI명칭") or ""))
    money = f"{rules._money(row.get('총액'))}|{rules._money(row.get('단가'))}"
    value = (f"{ident}|{rules._money(row.get('총액'))}", ident, f"{name}|{rules._money(row.get('총액'))}", money)[mode]
    return f"#{id(row)}" if not value or value.startswith(("|", "None|None")) else value  # 빈 열쇠끼리는 짝짓지 않는다


def align(a, b):
    """두 방식 행을 (코드 또는 명칭)+총액 순서 맞춤으로 짝짓고, 남은 행은 코드/명칭, 명칭+총액, 총액+단가 순으로 다시 짝짓는다."""
    pairs, used_a, used_b = [], set(), set()
    for mode in range(4):
        ia = [i for i in range(len(a)) if i not in used_a]
        ib = [j for j in range(len(b)) if j not in used_b]
        sm = difflib.SequenceMatcher(None, [key(a[i], mode) for i in ia], [key(b[j], mode) for j in ib], autojunk=False)
        for block in sm.get_matching_blocks():
            for k in range(block.size):
                i, j = ia[block.a + k], ib[block.b + k]
                pairs.append((i, j))
                used_a.add(i)
                used_b.add(j)
    return sorted(pairs), len(a) - len(used_a), len(b) - len(used_b)


def same(x, y):
    return (norm(x) or "0") == (norm(y) or "0")


def main():
    sample = {r["file"]: r for r in csv.DictReader((BASE / "sample.csv").open(encoding="utf-8"))}
    docs, diffs = [], []
    for name, meta in sample.items():
        ocr = json.loads((BASE / "ocr" / f"{name}.json").read_text(encoding="utf-8")) if (BASE / "ocr" / f"{name}.json").exists() else None
        if ocr is None:
            docs.append({"file": name, "pattern": meta["pattern"], "ext": meta["ext"], "pages": meta["pages"], "ocr": "실패"})
            continue
        blocks = ocr["blocks"]
        row = {"file": name, "pattern": meta["pattern"], "ext": meta["ext"], "pages": meta["pages"], "ocr": "성공",
               "ocr_s": round(ocr["ocr_ms"] / 1000, 1), "turns": json.dumps(ocr.get("turns") or {}), "header": plan_reason(blocks)}
        recs = {}
        for arm in ARMS:
            f = BASE / "runs" / arm / f"{name}.json"
            rec = recs[arm] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            if rec is None:
                row[f"{arm}_error"] = "결과 없음"
                continue
            rows = ((rec["rows"] or {}).get(TABLE)) or []
            logs = " ".join(rec["warnings"])
            checkable, missed = arith(rec["rows"])
            status, tm, tc = total_check(rows, blocks)
            row.update({f"{arm}_error": rec["error"] or "", f"{arm}_rows": len(rows), f"{arm}_calls": rec["calls"],
                        f"{arm}_s": round(rec["elapsed_ms"] / 1000, 1), f"{arm}_out_tok": rec["usage"]["completion_tokens"],
                        f"{arm}_arith_rows": checkable, f"{arm}_arith_miss": missed, f"{arm}_total": status,
                        f"{arm}_total_cols": f"{tm}/{tc}", f"{arm}_first_misses": rec.get("misses"),
                        f"{arm}_gate": int(rec.get("extracts", 1) >= 2 and arm == "rowmajor"),
                        f"{arm}_planned": int("planned=True" in logs),
                        f"{arm}_fallback": ("여러 조각·이미지 없음" if "needs one chunk" in logs else
                                            "행 계약 위반" if re.search(r"rowmajor table=\S+ failed", logs) else "")})
        if all(recs.values()) and not any(r["error"] for r in recs.values()):
            a = ((recs["rowmajor"]["rows"] or {}).get(TABLE)) or []
            b = ((recs["asis"]["rows"] or {}).get(TABLE)) or []
            pairs, only_a, only_b = align(a, b)
            cells = agree = 0
            by_group = Counter()
            for i, j in pairs:
                for column in COLUMNS:
                    x, y = a[i].get(column), b[j].get(column)
                    if (norm(x) or "0") == "0" and (norm(y) or "0") == "0":
                        continue
                    cells += 1
                    if same(x, y):
                        agree += 1
                        continue
                    by_group[GROUP_OF.get(column, "기타")] += 1
                    diffs.append({"file": name, "row_rowmajor": i, "row_asis": j, "column": column, "group": GROUP_OF.get(column, "기타"),
                                  "rowmajor": x, "asis": y, "code": a[i].get("EDI코드") or b[j].get("EDI코드"),
                                  "name": a[i].get("EDI명칭") or b[j].get("EDI명칭"), "total": a[i].get("총액")})
            for side, rows_, unmatched in (("rowmajor만", a, only_a), ("asis만", b, only_b)):
                matched = {p[0] if side == "rowmajor만" else p[1] for p in pairs}
                for k, r in enumerate(rows_):
                    if k not in matched:
                        diffs.append({"file": name, "row_rowmajor": k if side == "rowmajor만" else "", "row_asis": k if side == "asis만" else "",
                                      "column": "(행)", "group": side, "rowmajor": "", "asis": "", "code": r.get("EDI코드"),
                                      "name": r.get("EDI명칭"), "total": r.get("총액")})
            row.update({"pairs": len(pairs), "only_rowmajor": only_a, "only_asis": only_b, "cells": cells, "agree": agree,
                        "agree_rate": round(agree / cells, 4) if cells else None,
                        **{f"diff_{g}": by_group[g] for g in GROUPS}})
        docs.append(row)

    fields = list(dict.fromkeys(k for d in docs for k in d))
    with (BASE / "per_doc.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(docs)
    with (BASE / "diff_cells.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(diffs[0]) if diffs else ["file"])
        w.writeheader()
        w.writerows(diffs)

    ok = [d for d in docs if d.get("ocr") == "성공"]
    paired = [d for d in ok if "agree" in d]
    summary = {"docs": len(docs), "ocr_ok": len(ok), "paired_ok": len(paired),
               "turned_docs": sum(d["turns"] != "{}" for d in ok), "turns": dict(Counter(d["turns"] for d in ok if d["turns"] != "{}")),
               "header": dict(Counter(d["header"] for d in ok)),
               "agreement": {"cells": sum(d["cells"] for d in paired), "agree": sum(d["agree"] for d in paired),
                             "rate": round(sum(d["agree"] for d in paired) / max(1, sum(d["cells"] for d in paired)), 4),
                             "docs_full_agree": sum(d["cells"] and d["agree"] == d["cells"] and not d["only_rowmajor"] and not d["only_asis"] for d in paired),
                             "pairs": sum(d["pairs"] for d in paired), "only_rowmajor_rows": sum(d["only_rowmajor"] for d in paired),
                             "only_asis_rows": sum(d["only_asis"] for d in paired),
                             "diff_by_group": {g: sum(d[f"diff_{g}"] for d in paired) for g in GROUPS},
                             "docs_row_count_differs": sum(d["rowmajor_rows"] != d["asis_rows"] for d in paired)}}
    for arm in ARMS:
        rs = [d for d in ok if f"{arm}_rows" in d]
        good = [d for d in rs if not d[f"{arm}_error"]]
        secs = [d[f"{arm}_s"] for d in good]
        arith_rows = sum(d[f"{arm}_arith_rows"] for d in good)
        totals = Counter(d[f"{arm}_total"] for d in good)
        summary[arm] = {
            "docs": len(rs), "errors": len(rs) - len(good), "error_list": [f"{d['file']}: {d[f'{arm}_error']}" for d in rs if d[f"{arm}_error"]],
            "zero_row_docs": sum(d[f"{arm}_rows"] == 0 for d in good), "rows_total": sum(d[f"{arm}_rows"] for d in good),
            "rows_per_doc": round(sum(d[f"{arm}_rows"] for d in good) / max(1, len(good)), 1),
            "arith_rows": arith_rows, "arith_miss": sum(d[f"{arm}_arith_miss"] for d in good),
            "arith_pass_rate": round(1 - sum(d[f"{arm}_arith_miss"] for d in good) / arith_rows, 4) if arith_rows else None,
            "docs_miss_ratio_ge_0.3": sum(d[f"{arm}_arith_rows"] and d[f"{arm}_arith_miss"] / d[f"{arm}_arith_rows"] >= 0.3 for d in good),
            "total_rows": dict(totals), "total_match_rate": round(totals["일치"] / (totals["일치"] + totals["일부 일치"] + totals["불일치"]), 4) if totals["일치"] + totals["일부 일치"] + totals["불일치"] else None,
            "total_cols": f'{sum(int(d[f"{arm}_total_cols"].split("/")[0]) for d in good)}/{sum(int(d[f"{arm}_total_cols"].split("/")[1]) for d in good)}',
            "gate": sum(d[f"{arm}_gate"] for d in good), "planned": sum(d[f"{arm}_planned"] for d in good),
            "fallback": dict(Counter(d[f"{arm}_fallback"] for d in good if d[f"{arm}_fallback"])),
            "latency_s": {"p50": pct(secs, .5), "p90": pct(secs, .9), "max": max(secs, default=None), "total": round(sum(secs), 1)},
            "out_tokens": {"total": sum(d[f"{arm}_out_tok"] for d in good), "mean": round(sum(d[f"{arm}_out_tok"] for d in good) / max(1, len(good)))},
            "calls": sum(d[f"{arm}_calls"] for d in rs)}
    (BASE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
