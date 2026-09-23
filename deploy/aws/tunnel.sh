#!/usr/bin/env bash
# deploy/aws/tunnel.sh — 서버의 frontend(루프백)로 SSH 터널을 연다. /api도 nginx가 backend로 넘긴다.
#   deploy/aws/tunnel.sh          # 포그라운드(Ctrl-C로 종료)
#   deploy/aws/tunnel.sh --bg     # 백그라운드
#   deploy/aws/tunnel.sh --stop   # 백그라운드 터널 종료
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

# 백그라운드 터널은 포트별 제어 소켓으로만 다룬다 — 패턴으로 프로세스를 찾지 않으니 다른 세션의 터널은 건드리지 않는다
SOCK="/tmp/docraft-tunnel-${TUNNEL_PORT}.sock"
if [ "${1:-}" = "--stop" ]; then
  if [ -S "$SOCK" ] && ssh -S "$SOCK" -O exit "$REMOTE" 2>/dev/null; then echo "[tunnel] 종료"
  else echo "[tunnel] 실행 중인 터널이 없습니다"; rm -f "$SOCK"; fi
  exit 0
fi

FORWARD=(-o ExitOnForwardFailure=yes -L "${TUNNEL_PORT}:127.0.0.1:${FRONTEND_PORT}")
echo "[tunnel] http://localhost:${TUNNEL_PORT} → ${SSH_HOST}:${FRONTEND_PORT}"
if [ "${1:-}" = "--bg" ]; then
  ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "${FORWARD[@]}" -M -S "$SOCK" -fN "$REMOTE"
  echo "[tunnel] 백그라운드(${SOCK}). 종료: $0 --stop"
else
  exec ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "${FORWARD[@]}" -N "$REMOTE"
fi
