#!/usr/bin/env bash
# deploy/aws/deploy.sh — 로컬 빌드 → 이미지 반입 → 기동.
#
#   deploy/aws/deploy.sh              # 빌드·전송·기동
#   deploy/aws/deploy.sh --no-build   # 이미 만든 이미지로 전송·기동만
#
# backend·frontend 이미지는 로컬에서 빌드해 tar로 올린다(서버에 소스·빌드 도구를 두지 않는다).
# PaddleOCR 이미지(수십 GB)는 서버가 레지스트리에서 직접 받는다. 첫 배포는 이 pull 때문에 오래 걸린다.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

BUILD=1
for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    *) echo "[deploy] 알 수 없는 인자: $arg" >&2; exit 2 ;;
  esac
done

TAG="$(git -C "$REPO_ROOT" rev-parse --short HEAD)$(git -C "$REPO_ROOT" diff --quiet HEAD || echo -dirty)"
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
REMOTE

cat <<MSG

[deploy] 완료(${TAG}). 서버에는 frontend만 루프백 ${FRONTEND_PORT}로 열려 있습니다.
  deploy/aws/tunnel.sh --bg   # http://localhost:${TUNNEL_PORT}
  deploy/aws/smoke.sh         # 샘플 문서 파싱 왕복
  deploy/aws/logs.sh backend  # 로그
MSG
