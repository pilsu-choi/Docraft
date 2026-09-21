#!/usr/bin/env bash
# deploy/aws/logs.sh — 원격 로그. 인자가 없으면 전체, 있으면 그 서비스만.
#   deploy/aws/logs.sh backend
#   deploy/aws/logs.sh paddleocr-vl-api
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"
remote_compose "logs --tail 100 -f $*"
