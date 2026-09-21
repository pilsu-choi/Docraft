#!/usr/bin/env bash
# deploy/aws/smoke.sh — 원격 스택에 샘플 문서를 올려 파싱까지 왕복한다. 기동과 실제 동작은 다르다.
#   deploy/aws/smoke.sh [파일...]   # 기본: samples/agentic-ocr-2.0.1-results/images/*/*.png
# 터널이 없으면 임시로 열고 끝나면 닫는다. 결과는 표마다 structure(ruled/vlm)와 행×열이다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

API="http://localhost:${TUNNEL_PORT}/api"
AUTH=(); [ -n "${DOCRAFT_API_KEY:-}" ] && AUTH=(-H "X-API-Key: ${DOCRAFT_API_KEY}")
OWN_TUNNEL=0
if ! curl -sf "${API}/health" >/dev/null 2>&1; then
  "${SCRIPT_DIR}/tunnel.sh" --bg >/dev/null; OWN_TUNNEL=1
  for _ in $(seq 1 20); do curl -sf "${API}/health" >/dev/null 2>&1 && break; sleep 1; done
fi
trap '[ "$OWN_TUNNEL" = 1 ] && "${SCRIPT_DIR}/tunnel.sh" --stop >/dev/null' EXIT
echo "[smoke] health: $(curl -sf "${API}/health")"

FILES=("$@"); [ ${#FILES[@]} -gt 0 ] || FILES=("${REPO_ROOT}"/samples/agentic-ocr-2.0.1-results/images/*/*.png)
project="$(curl -sf "${AUTH[@]}" -H 'Content-Type: application/json' -d '{"name":"aws-smoke"}' "${API}/projects" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
for file in "${FILES[@]}"; do
  doc="$(curl -sf "${AUTH[@]}" -F "files=@${file}" "${API}/projects/${project}/documents" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')"
  started=$SECONDS
  while :; do
    body="$(curl -sf "${AUTH[@]}" "${API}/documents/${doc}")"
    status="$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
    case "$status" in queued|parsing) [ $((SECONDS - started)) -lt 900 ] && { sleep 3; continue; } ;; esac
    break
  done
  printf '  %-28s %-7s %4ss  %s\n' "$(basename "$(dirname "$file")")/$(basename "$file" | cut -c1-12)" "$status" $((SECONDS - started)) \
    "$(printf '%s' "$body" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(d.get("error") or " ".join("%s:%dx%d" % (b.get("structure","vlm"), len(b.get("rows") or []), len((b.get("rows") or [[]])[0])) for b in d["blocks"] if b["type"]=="table") or "-")')"
done
echo "[smoke] 프로젝트 aws-smoke(${project})에 결과가 남아 있습니다. UI: http://localhost:${TUNNEL_PORT}"
