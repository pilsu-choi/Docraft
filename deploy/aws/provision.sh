#!/usr/bin/env bash
# deploy/aws/provision.sh — 서버 1회 준비. 필요한 도구를 확인하고 디렉터리를 만든다(멱등).
#
# harness-v2가 같은 서버에 docker·compose·NVIDIA 런타임을 이미 설치해 두었다. 여기서는 설치하지 않고
# 확인만 한다 — 공유 서버의 docker를 건드리면 harness 스택이 같이 재시작된다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

echo "[provision] 대상: ${REMOTE}"
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
docker info >/dev/null 2>&1 || { echo "[remote] docker를 쓸 수 없습니다(설치·docker 그룹 확인)"; exit 2; }
version="\$(docker compose version --short)"
# 오버레이의 !reset·!override는 compose 2.24부터 지원한다.
printf '%s\n2.24.0\n' "\$version" | sort -V -C 2>/dev/null && { echo "[remote] compose \$version < 2.24"; exit 2; }
docker info 2>/dev/null | grep -i nvidia >/dev/null || { echo "[remote] docker에 NVIDIA 런타임이 없습니다"; exit 2; }
echo "[remote] compose \$version, GPU: \$(nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader)"
sudo mkdir -p "${REMOTE_ROOT}"/{data,images,deploy/aws,deploy/paddleocr}
sudo chown -R "${SSH_USER}:${SSH_USER}" "${REMOTE_ROOT}"
df -h "${REMOTE_ROOT}" | tail -1
REMOTE
echo "[provision] 완료"
