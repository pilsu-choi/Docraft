#!/usr/bin/env bash
# deploy/aws/down.sh — 원격 스택 정지. GPU를 harness에 돌려주려면 이것으로 내린다.
#   deploy/aws/down.sh             # 정지(DB·모델 볼륨과 data/ 보존)
#   deploy/aws/down.sh --volumes   # 볼륨까지 삭제. DB가 사라진다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"
if [ "${1:-}" = "--volumes" ]; then
  read -r -p "서버의 Docraft DB 볼륨을 삭제합니다. 계속하려면 'yes' 입력: " ok
  [ "$ok" = yes ] || { echo "취소"; exit 1; }
  remote_compose "down --volumes --remove-orphans"
else
  remote_compose "down --remove-orphans"
fi
