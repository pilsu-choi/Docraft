#!/usr/bin/env bash
# deploy/aws/deploy.sh — 로컬 빌드 → 이미지 반입 → 기동.
#
#   deploy/aws/deploy.sh              # 빌드·전송·기동
#   deploy/aws/deploy.sh --no-build   # 이미 만든 이미지로 전송·기동만
#   DEPLOY_FORCE=1 deploy/aws/deploy.sh   # /api/verify 처리 중이어도 교체
#
# 서버는 여러 세션이 함께 쓴다. 배포 내내 서버의 deploy.lock을 잡아 겹치는 배포를 막고, 직전 배포 기록(DEPLOYED)을
# 보여 준 뒤, backend가 /api/verify를 처리 중이면(health의 verify_inflight) 교체하지 않는다.
# backend·frontend 이미지는 로컬에서 빌드해 tar로 올린다(서버에 소스·빌드 도구를 두지 않는다).
# PaddleOCR 이미지(수십 GB)는 서버가 레지스트리에서 직접 받는다. 첫 배포는 이 pull 때문에 오래 걸린다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"
if [ "$FRONTEND_BIND" != 127.0.0.1 ] && [ -z "${DOCRAFT_API_KEY:-}" ]; then
  echo "[deploy] FRONTEND_BIND=${FRONTEND_BIND}(외부 노출)인데 DOCRAFT_API_KEY가 비어 있습니다. 인증 없이 열 수 없습니다." >&2; exit 2
fi

BUILD=1
for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    *) echo "[deploy] 알 수 없는 인자: $arg" >&2; exit 2 ;;
  esac
done

TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)$(git -C "$REPO_ROOT" diff --quiet HEAD || echo -dirty)"
WHO="revision=${TAG} time=$(date -u +%FT%TZ) by=$(id -un)@$(hostname) branch=$(git -C "$REPO_ROOT" branch --show-current)"

# 잠금은 이 ssh 세션이 살아 있는 동안(=이 스크립트가 끝날 때까지) 유지된다. 잠금 파일에는 잡은 쪽을 적어 둔다
coproc LOCK { "${SSH[@]}" "cd ${REMOTE_ROOT} && exec flock -n deploy.lock sh -c 'echo \"\$1\" > deploy.lock; echo locked; exec cat >/dev/null' _ $(printf %q "$WHO")"; }
read -r -u "${LOCK[0]}" LOCKED || true
if [ "${LOCKED:-}" != locked ]; then
  echo "[deploy] 서버 배포 잠금을 잡지 못했습니다(다른 배포 중이거나 연결 실패): $("${SSH[@]}" "cat ${REMOTE_ROOT}/deploy.lock" 2>/dev/null)" >&2; exit 3
fi
echo "[deploy] 직전 배포: $("${SSH[@]}" "cat ${REMOTE_ROOT}/DEPLOYED 2>/dev/null || echo 없음")"

busy_guard() {  # backend가 /api/verify를 처리 중이면 멈춘다(health가 없거나 옛 backend면 0으로 본다)
  local n
  n="$("${SSH[@]}" "curl -fsS --max-time 5 http://127.0.0.1:${FRONTEND_PORT}/api/health" 2>/dev/null | grep -o '"verify_inflight": *[0-9]*' | grep -o '[0-9]*$' || echo 0)"
  [ "$n" = 0 ] && return
  if [ "${DEPLOY_FORCE:-0}" = 1 ]; then echo "[deploy] /api/verify ${n}건 처리 중이지만 DEPLOY_FORCE=1로 교체합니다" >&2; return; fi
  echo "[deploy] backend가 /api/verify ${n}건을 처리 중입니다. 끝난 뒤 다시 하거나 DEPLOY_FORCE=1로 강제하십시오." >&2; exit 3
}
busy_guard  # 빌드·전송 전에 한 번, 교체 직전에 한 번
IMAGES=(docraft-backend docraft-frontend)
if [ "$BUILD" = 1 ]; then
  echo "[deploy] 이미지 빌드: ${TAG}"
  docker build -t "docraft-backend:${TAG}" -t docraft-backend:latest -f "${REPO_ROOT}/backend/Dockerfile" "$REPO_ROOT"
  docker build -t "docraft-frontend:${TAG}" -t docraft-frontend:latest -f "${REPO_ROOT}/frontend/Dockerfile" "$REPO_ROOT"
fi

TAR="/tmp/docraft-images.tar.gz"
trap 'rm -f "$TAR"' EXIT
docker save "${IMAGES[@]/%/:latest}" | gzip -1 > "$TAR"
echo "[deploy] 이미지 전송: $(du -h "$TAR" | cut -f1)"
"${SCP[@]}" "$TAR" "${REMOTE}:${REMOTE_ROOT}/images/"

echo "[deploy] compose·설정 전송"
"${SCP[@]}" "${REPO_ROOT}/compose.yaml" "${REMOTE}:${REMOTE_ROOT}/"
"${SCP[@]}" "${ENV_FILE}" "${REMOTE}:${REMOTE_ROOT}/.env"
"${SCP[@]}" "${REPO_ROOT}"/deploy/paddleocr/*.yaml "${REMOTE}:${REMOTE_ROOT}/deploy/paddleocr/"
"${SCP[@]}" "${SCRIPT_DIR}/docker-compose.aws.override.yml" "${SCRIPT_DIR}/vllm_config.aws.yaml" "${REMOTE}:${REMOTE_ROOT}/deploy/aws/"

busy_guard
echo "[deploy] 원격 기동"
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_ROOT}"
gunzip -c images/docraft-images.tar.gz | docker load
rm -f images/docraft-images.tar.gz
${COMPOSE} up -d
for _ in \$(seq 1 60); do
  [ "\$(docker inspect -f '{{.State.Health.Status}}' docraft-backend-1 2>/dev/null)" = healthy ] && break
  sleep 5
done
${COMPOSE} ps --format 'table {{.Service}}\t{{.Status}}'
echo $(printf %q "$WHO") > DEPLOYED
REMOTE

cat <<MSG

[deploy] 완료(${TAG}). 서버에는 frontend만 ${FRONTEND_BIND}:${FRONTEND_PORT}로 열려 있습니다.
  deploy/aws/tunnel.sh --bg   # http://localhost:${TUNNEL_PORT}
  deploy/aws/smoke.sh         # 샘플 문서 파싱 왕복
  deploy/aws/logs.sh backend  # 로그
MSG
