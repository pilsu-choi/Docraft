# deploy/aws/_common.sh — AWS 스크립트 공용. 직접 실행하지 않는다.
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.aws"

if [ ! -f "${ENV_FILE}" ]; then
  echo "[aws] ${ENV_FILE}이 없습니다. cp deploy/aws/.env.aws.example deploy/aws/.env.aws 후 값을 채우십시오." >&2
  exit 2
fi
set -a; source "${ENV_FILE}"; set +a

: "${SSH_HOST:?SSH_HOST를 .env.aws에 설정하십시오}"
: "${SSH_USER:=ec2-user}"
: "${REMOTE_ROOT:=/mnt/data/docraft}"
: "${FRONTEND_PORT:=3000}"
: "${FRONTEND_BIND:=127.0.0.1}"
: "${TUNNEL_PORT:=13000}"

KEY_PATH="${SSH_KEY/#\~/$HOME}"
[ -f "$KEY_PATH" ] || KEY_PATH="${REPO_ROOT}/${SSH_KEY#./}"
[ -f "$KEY_PATH" ] || { echo "[aws] SSH 키를 찾을 수 없습니다: ${SSH_KEY}" >&2; exit 2; }
chmod 600 "$KEY_PATH" 2>/dev/null || true

SSH=(ssh -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new "${SSH_USER}@${SSH_HOST}")
SCP=(scp -i "$KEY_PATH" -o StrictHostKeyChecking=accept-new)
REMOTE="${SSH_USER}@${SSH_HOST}"
COMPOSE="docker compose -f compose.yaml -f deploy/aws/docker-compose.aws.override.yml --profile app --profile ocr"

remote_compose() {
  "${SSH[@]}" "cd ${REMOTE_ROOT} && ${COMPOSE} $*"
}
