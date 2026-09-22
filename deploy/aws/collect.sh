#!/usr/bin/env bash
# deploy/aws/collect.sh — 서버의 이슈 케이스를 로컬로 모은다. 개선 작업의 입력이다.
#
#   deploy/aws/collect.sh          # 이슈 문서(실패·검토 필요·검증 이슈·사용자 수정)의 원본만 받는다
#   deploy/aws/collect.sh --all    # 모든 문서의 원본을 받는다
#
# 결과: data/aws-collect/<시각>/ (data/는 git 제외)
#   summary.md       상태별 건수, 실패 에러, 사용자 수정(전→후), 검증 이슈, 표 구조, 로그 ERROR·WARNING
#   documents.json   문서 전체(파싱 블록·추출 결과·검증 포함), corrections.json, audit_log.json, schemas.json
#   files/           원본(<문서 id>_<파일명>), logs/  backend 로그(data/logs)
# 업로드 문서에는 개인정보가 들어 있다. 받은 폴더를 공유 경로에 올리지 않는다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

ALL=0
[ "${1:-}" = "--all" ] && ALL=1
OUT="${REPO_ROOT}/data/aws-collect/$(date +%Y%m%d-%H%M%S)"
mkdir -p "${OUT}/files" "${OUT}/logs"

sql() { "${SSH[@]}" "docker exec docraft-postgres-1 psql -U docraft -d docraft -tAc \"$1\""; }
echo "[collect] DB 내보내기"
sql "select coalesce(json_agg(t order by t.created_at), '[]') from (select d.*, p.name as project from documents d join projects p on p.id = d.project_id) t" > "${OUT}/documents.json"
for table in corrections audit_log schemas; do
  sql "select coalesce(json_agg(t order by t.created_at), '[]') from ${table} t" > "${OUT}/${table}.json"
done

echo "[collect] 로그"
"${SCP[@]}" -q "${REMOTE}:${REMOTE_ROOT}/data/logs/*" "${OUT}/logs/" 2>/dev/null || echo "[collect] data/logs가 비어 있습니다(LOG_FILE 설정 전 배포)"

# 이슈 문서 판단은 summary와 같은 기준을 쓰도록 python 한 곳에 둔다.
python3 - "$OUT" "$ALL" > "${OUT}/.files" <<'PY'
import json, sys
out, everything = sys.argv[1], sys.argv[2] == "1"
docs = json.load(open(f"{out}/documents.json"))
corrected = {c["document_id"] for c in json.load(open(f"{out}/corrections.json"))}
for d in docs:
    if everything or d["status"] in {"failed", "needs_review"} or json.loads(d["validation"]) or d["id"] in corrected:
        print(d["id"], d["file_path"].rsplit("/", 1)[-1], d["filename"])
PY
echo "[collect] 원본 $(wc -l < "${OUT}/.files")건"
while read -r id stored name; do
  "${SCP[@]}" -q "${REMOTE}:${REMOTE_ROOT}/data/files/${stored}" "${OUT}/files/${id}_${name}" || echo "[collect] 원본 없음: ${name}"
done < "${OUT}/.files"
rm -f "${OUT}/.files"

python3 - "$OUT" > "${OUT}/summary.md" <<'PY'
import collections, glob, json, sys
out = sys.argv[1]
docs = json.load(open(f"{out}/documents.json"))
corrections = json.load(open(f"{out}/corrections.json"))
names = {d["id"]: f'{d["project"]} / {d["filename"]}' for d in docs}
cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")[:120]
print(f"# AWS 이슈 수집 {out.rsplit('/', 1)[-1]}\n")
print("## 상태별 문서 수\n\n| 상태 | 건수 |\n| --- | --- |")
for status, count in collections.Counter(d["status"] for d in docs).most_common():
    print(f"| {status} | {count} |")
print("\n## 실패\n\n| 문서 | 에러 |\n| --- | --- |")
for d in (d for d in docs if d["status"] == "failed"):
    print(f'| {cell(names[d["id"]])} | {cell(d["error"])} |')
print("\n## 사용자 수정 (추출 오류)\n\n| 문서 | 필드 | 추출값 | 수정값 |\n| --- | --- | --- | --- |")
for c in corrections:
    print(f'| {cell(names.get(c["document_id"], c["document_id"]))} | {c["path"]} | {cell(json.loads(c["old_value"]) if c["old_value"] else "")} | {cell(json.loads(c["new_value"]))} |')
print("\n## 검증 이슈\n\n| 문서 | 코드별 건수 |\n| --- | --- |")
for d in docs:
    issues = collections.Counter(i["code"] for i in json.loads(d["validation"]))
    if issues:
        print(f'| {cell(names[d["id"]])} | {", ".join(f"{k} {v}" for k, v in issues.items())} |')
print("\n## 표 구조 (파싱된 문서)\n\n| 문서 | 표 |\n| --- | --- |")
for d in docs:
    tables = [b for b in json.loads(d["blocks"]) if b["type"] == "table"]
    if tables:
        print(f'| {cell(names[d["id"]])} | {" ".join("%s %dx%d" % (b.get("structure", "vlm"), len(b.get("rows") or []), len((b.get("rows") or [[]])[0])) for b in tables)} |')
lines = [l.rstrip() for f in sorted(glob.glob(f"{out}/logs/*")) for l in open(f, encoding="utf-8", errors="replace") if " ERROR " in l or " WARNING " in l]
print(f"\n## 로그 ERROR·WARNING ({len(lines)}줄, 최근 30줄)\n\n```")
print("\n".join(lines[-30:]))
print("```")
PY
echo "[collect] 완료: ${OUT}/summary.md"
