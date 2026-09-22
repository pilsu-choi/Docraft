"""파서 표 복원 품질을 모델과 무관한 구조 지표로 진단한다.

추출·평가 지표는 VLM 응답에 따라 흔들려서 파서 변경의 효과를 가린다. 여기서는 parse 캐시(또는 라이브
파싱 결과)의 표 블록만 보고 다음을 센다.

- ``tables``/``ruled`` : 표 블록 수와 그중 괘선 격자(``structure == "ruled"``)로 복원된 수
- ``header``           : ``rules._headers``가 항목 표 머리글을 찾았는지(항목 열 판별 성공)
- ``rebuilt``          : ``rules._receipt_rows``가 돌려준 항목 행 수(진료비영수증 뼈대 보정의 입력)
- ``rows``/``label``   : 머리글 아래 본문 행 수와 라벨 ``항목내역`` 행 수, 그 차이 ``gap``
- ``multi``            : 한 셀에 금액이 둘 이상 든 셀 수(``rules._MULTI_AMOUNT``) — 행 병합 오판의 흔적

사용법::

    .venv/bin/python scripts/parse_audit.py --cache-root data/verify/accuracy-20260922/grounded-v3
    .venv/bin/python scripts/parse_audit.py --cache-root <root> --json out.json --doc-type 진료비영수증
    .venv/bin/python scripts/parse_audit.py --image <파일>          # 캐시 없이 직접 파싱해 한 건만
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import rules  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "data" / "verify" / "accuracy-20260922" / "manifest.json"


def _tables(blocks):
    return [b for b in blocks or [] if b.get("type") == "table" and b.get("rows")]


def _header_at(rows):
    """'항목'으로 끝나는 셀이 있는 첫 행 번호. ``rules._headers``와 같은 기준이다."""
    return next((i for i, row in enumerate(rows) if any(rules._key(cell).endswith("항목") for cell in row)), None)


def audit(blocks, label_rows=None):
    """파싱 블록 하나의 구조 지표."""
    tables = _tables(blocks)
    body = 0
    for table in tables:
        start = _header_at(table["rows"])
        if start is not None:
            body = max(body, sum(1 for row in table["rows"][start + 1:] if any(str(c or "").strip() for c in row)))
    metrics = {
        "tables": len(tables),
        "ruled": sum(t.get("structure") == "ruled" for t in tables),
        "header": any(_header_at(t["rows"]) is not None for t in tables),
        "rebuilt": len(rules._receipt_rows(blocks)),
        "rows": body,
        "multi": sum(bool(rules._MULTI_AMOUNT.search(str(cell or ""))) for t in tables for row in t["rows"] for cell in row),
    }
    if label_rows is not None:
        metrics["label"] = label_rows
        metrics["gap"] = body - label_rows
    return metrics


def _blocks(cache_root, doc_type, stem, image=None):
    path = Path(cache_root) / f"{doc_type}__{stem}.parse.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["blocks"]
    if image is None:
        return None
    import mimetypes

    from backend import parsers

    return parsers.parse(str(image), Path(image).name, mimetypes.guess_type(str(image))[0] or "image/png")[1]


def _rows_of(item, label_root):
    """라벨 ``항목내역`` 행 수. 매니페스트가 경로를 주지 않는 holdout은 ``label_root``에서 찾는다."""
    path = Path(item["label"]) if item.get("label") else Path(label_root) / item["doc_type"] / f"{Path(item['image']).stem}.json"
    if not path.exists():
        return 0
    fields = json.loads(path.read_text(encoding="utf-8")).get("fields") or {}
    return len(fields.get(rules.ITEM_TABLE) or [])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--cache-root", default=str(REPO_ROOT / "data" / "verify" / "cache"))
    ap.add_argument("--doc-type", action="append", help="여러 번 줄 수 있다")
    ap.add_argument("--image", help="매니페스트 대신 이미지 한 건을 직접 파싱해 본다")
    ap.add_argument("--json", help="결과를 이 경로에 저장")
    args = ap.parse_args()

    if args.image:
        print(json.dumps(audit(_blocks(args.cache_root, "", "", args.image)), ensure_ascii=False, indent=2))
        return

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items, label_root = manifest["items"], manifest.get("label_root", "")
    if args.doc_type:
        items = [i for i in items if i["doc_type"] in args.doc_type]
    report = []
    for item in items:
        stem = Path(item["image"]).stem
        blocks = _blocks(args.cache_root, item["doc_type"], stem)
        if blocks is None:
            continue
        report.append({"doc_type": item["doc_type"], "split": item["split"], "stem": stem,
                       **audit(blocks, _rows_of(item, label_root))})

    print(f"| 유형 | split | 문서 | 표 | ruled | 머리글 | rebuilt | 행 | 라벨 | 차이 | multi |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in report:
        print(f"| {r['doc_type']} | {r['split']} | {r['stem'][:28]} | {r['tables']} | {r['ruled']} | "
              f"{'O' if r['header'] else 'X'} | {r['rebuilt']} | {r['rows']} | {r['label']} | {r['gap']:+d} | {r['multi']} |")

    print("\n## 요약")
    print("| 유형 | 문서 | 머리글 O | rebuilt>0 | 행 일치(±1) | multi 합 | ruled 표/전체 |")
    print("|---|---|---|---|---|---|---|")
    for doc_type in dict.fromkeys(r["doc_type"] for r in report):
        group = [r for r in report if r["doc_type"] == doc_type]
        print(f"| {doc_type} | {len(group)} | {sum(r['header'] for r in group)} | {sum(r['rebuilt'] > 0 for r in group)} | "
              f"{sum(r['label'] > 0 and abs(r['gap']) <= 1 for r in group)} | {sum(r['multi'] for r in group)} | "
              f"{sum(r['ruled'] for r in group)}/{sum(r['tables'] for r in group)} |")

    print("\n## 실패 문서")
    for r in report:
        why = [name for name, bad in (("머리글 미검출", not r["header"]),
                                      ("rebuilt 0", r["doc_type"] == "진료비영수증" and not r["rebuilt"]),
                                      ("행 차이 큼", r["label"] and abs(r["gap"]) > 3),
                                      ("다중 금액 셀", r["multi"] >= 3)) if bad]
        if why:
            print(f"- {r['doc_type']}/{r['stem'][:40]} ({r['split']}): {', '.join(why)} "
                  f"[표 {r['tables']}, ruled {r['ruled']}, 행 {r['rows']}/{r['label']}, multi {r['multi']}]")

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
