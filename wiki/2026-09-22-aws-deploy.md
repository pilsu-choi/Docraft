---
type: Implementation Log
title: "AWS 개발 서버 배포 스크립트"
description: "harness-v2의 deploy/aws 구조를 따라 같은 EC2(NVIDIA L4)에 Docraft 전체 스택(app + PaddleOCR)을 올리는 스크립트를 추가하고, 실제 배포·smoke로 검증한 기록"
tags: [deploy, aws, docker, paddleocr, gpu]
generated: {by: claude-code/claude-opus-5, at: 2026-09-22}
status: stable
---

# AWS 개발 서버 배포 스크립트

- 날짜: 2026-09-22
- 브랜치: `feat/aws-deploy`
- 워크트리: `.worktrees/aws-deploy`

## 배경

로컬 GPU(RTX 4070 12GB)보다 큰 GPU로 테스트할 수 있도록 harness-v2(`../harness-v2/deploy/aws`)와 같은 방식의 배포 스크립트를 `deploy/aws/`에 만들었다. harness 방식에서 가져온 것:
- compose 정의는 로컬 것을 그대로 쓰고 차이만 오버레이로 덮는다.
- 이미지는 로컬에서 빌드해 tar로 반입한다.
- 서버 포트는 루프백에만 열고 SSH 터널로 접근한다.

## 서버 조사 (읽기 전용 확인, 2026-09-22)

| 항목 | 값 |
| --- | --- |
| GPU | NVIDIA L4 23GB, 사용 1.4GB(harness `vllm-embedding`) |
| 디스크 | `/` 8.8GB(여유 3.4GB), `/mnt/data` 300GB(여유 231GB), docker root `/mnt/data/docker` |
| 도구 | Docker 29.7, compose 5.4, nvidia 런타임 등록됨 |
| 사용 중 포트 | 22, 9010(0.0.0.0), 5433·8124·9001(루프백) |
| 기타 | RAM 241GB, 64코어, ec2-user uid 1000 |

## 결정

- `REMOTE_ROOT=/mnt/data/docraft`: 루트 디스크가 작아 업로드 파일과 compose 정의를 데이터 디스크에 둔다.
- 호스트 포트는 frontend `127.0.0.1:3000` 하나만 연다. `compose.yaml`의 postgres 기본 포트 5433이 harness postgres와 겹쳐서 postgres·backend·PaddleOCR 포트를 `!reset []`으로 막았다.
- `vllm_config.aws.yaml`은 `gpu-memory-utilization: 0.35`(약 8GB)다. harness 임베딩 vLLM(0.15)과 나눠 쓰고, 로컬 4070에서 검증한 크기(0.6 × 12GB ≈ 7.3GB)와 맞췄다.
- `provision.sh`는 설치하지 않고 확인만 한다. 공유 서버의 docker 재시작은 harness 스택을 같이 내린다.
- `.env.aws`를 서버에 `.env`로 올린다. compose 변수와 backend `env_file`을 한 파일로 맞춰 설정이 갈라지지 않게 했다.
- 이미지 태그는 git 짧은 커밋이고 `latest`도 같이 붙인다. 오버레이 기본값이 `latest`라 `logs.sh`·`down.sh`처럼 태그 없이 부르는 compose 명령도 같은 이미지를 가리킨다.

## 검증

- `bash -n`으로 모든 스크립트의 문법을 확인했다.
- 로컬에서 `docker compose -f compose.yaml -f deploy/aws/docker-compose.aws.override.yml --profile app --profile ocr config`로 병합 결과를 확인했다.
  - backend·frontend는 build 없이 `docraft-*:latest` 이미지를 쓴다.
  - 호스트 포트는 frontend `127.0.0.1:3000`만 열린다.
  - vLLM은 `vllm_config.aws.yaml`을 마운트한다.
- 서버 조사는 읽기 전용 SSH로 했다.

## 실제 배포 (2026-09-22)

- `provision.sh` 통과. `deploy.sh` 첫 배포에서 PaddleOCR 이미지 두 개를 서버가 받았다(`paddleocr-vl` 10.5GB, `paddleocr-genai-vllm-server` 22GB). 모두 docker 저장소가 있는 `/mnt/data`에 쌓였다.
- harness의 `vllm/vllm-openai:v0.29.0`은 베이스가 달라 레이어를 공유하지 못한다. vLLM 0.29는 PaddleOCR-VL을 지원하므로 이 이미지로 바꿀 수는 있다. 하지만 `offline` 이미지에 든 모델 가중치를 따로 받아야 하고 로컬과 구성이 갈라져서 이번에는 쓰지 않았다.
- Docraft 6개 컨테이너가 모두 healthy이고 harness 8개 컨테이너는 영향 없이 계속 돌았다. GPU 사용량은 harness를 포함해 9.7/23GB다.
- `smoke.sh`(샘플 5종 PNG, 문서당 12~28초, `TABLE_REFINE=true`) 결과:

| 문서 | 표 구조 |
| --- | --- |
| 세부내역서 | ruled 24×15, vlm 2×4 |
| 소견서 | ruled 11×10 |
| 약제비영수증 | vlm 9×3, vlm 26×3 |
| 진단서 | ruled 12×7 |
| 진료비영수증 | ruled 42×15 |

- 첫 smoke에서 약제비영수증 오른쪽 표가 `ruled 2×2`로 VLM 26행을 덮어쓴 것을 발견했다. 격자 행이 VLM 행의 절반 미만이면 VLM을 유지하도록 고쳐 재배포했다([ruled-table-grid](2026-09-22-ruled-table-grid.md)). 재배포는 backend 이미지만 교체돼 1분 안에 끝났다.
- 줄 OCR 서비스가 큰 PDF에서 재시작되는 문제는 이번 smoke가 PNG만 써서 확인하지 않았다.

## 외부 접근 (FRONTEND_BIND)

- 사용자 요청으로 SSH 키 없이 URL로 접속할 수 있게 `FRONTEND_BIND`를 추가했다. 기본은 `127.0.0.1`이고, `0.0.0.0`이면 `http://<서버>:3000`으로 열린다. harness의 `API_BIND`와 같은 방식이다.
- `0.0.0.0`인데 `DOCRAFT_API_KEY`가 비어 있으면 `deploy.sh`가 배포를 거부한다.
- 보안그룹 3000 포트는 사용자가 직접 연다.
- TLS가 없으므로 소스 IP 제한이 전제다.
- OpenRouter 키(`AI_API_KEY`)는 backend 환경변수에만 있다. `public_ai_settings()`는 호스트명·모델명만 공개한다. 배포 후 실제 응답·프론트 번들·로그에 키 문자열이 없는지 확인했다.

## 이슈 수집 (collect.sh)과 로그 보존

- 서버 테스트에서 나온 이슈를 개선 작업으로 옮기려고 `deploy/aws/collect.sh`를 추가했다. 결과는 로컬 `data/aws-collect/<시각>/`(git 제외)에 쌓인다.
  - DB 기록: `documents`·`corrections`·`audit_log`·`schemas`를 JSON으로 내보낸다.
  - 원본: 이슈 문서(실패·검토 필요·검증 이슈·사용자 수정)만 받는다. `--all`이면 모든 문서를 받는다.
  - backend 로그를 함께 받는다.
  - `summary.md`: 상태별 건수, 실패 에러, 수정 전→후, 검증 이슈, 표 구조(ruled/vlm, 행×열), 로그 ERROR·WARNING을 정리한다.
- 확인해 보니 backend 로그가 컨테이너 표준 출력에만 있어 `deploy.sh`로 재생성될 때마다 지워졌다. 오버레이에서 `LOG_FILE=/data/logs/docraft.log`를 지정해 서버 디스크에 남기도록 했다. 컨테이너 로그는 json-file 50MB × 3으로 제한했다.
- 첫 수집(2026-09-22 09:16): 문서 11건 모두 `parsed`, 실패·수정·검증 이슈 0건. 사용자 테스트 문서 `2303000012.tif`는 ruled 29×15로 나왔다.


## 재배포 (2026-09-23, 브랜치 `fix/aws-frontend-port`·`docs/aws-redeploy-0923`)

- 영수증 룰 보강 3건([receipt-issue-cases](2026-09-23-receipt-issue-cases.md), [receipt-issues-0923](2026-09-23-receipt-issues-0923.md), [sum-guard-labels](2026-09-23-sum-guard-labels.md))을 서버에 반영했다. 이전 backend 이미지는 2026-09-22 빌드였다.
- 첫 재배포(`e5563bd`) 뒤 서버 3000 포트가 응답하지 않았다. `721c900`에서 frontend를 비특권 nginx(8080)로 바꾸며 `compose.yaml`은 `:8080`으로 고쳤지만, AWS 오버레이는 `:80`에 연결하고 있었다. 오버레이를 `:8080`으로 고치고(`a2d8def`) `--no-build`로 다시 배포했다.
- 확인 결과
  - `smoke.sh` 5종 parsed. 진료비영수증 ruled 42×14, 세부내역서 ruled 24×15 등이다.
  - 컨테이너 안 `backend/rules.py`에 새 함수(`_row_shifts`·`_absent_columns`·`sum_errors`·`_misread`)가 있고 `verify.py`에 `_balance`가 있다.
  - `/api/verify`에 이슈 260923 현상 1 문서(공단부담금 열 전체가 `선택진료료외`로 간 AO)를 보냈다. `no_column`·`column_shift`가 떴고, 4행 모두 공단부담금으로 교정됐으며, 교정 후 남은 경고는 0이다.
- 이미지 태그는 `7170ecc-dirty`다. main 작업 폴더의 다른 세션 미커밋 문서 때문이다. 이미지에는 `backend/`·`frontend/`만 복사되므로 내용에는 영향이 없다.
