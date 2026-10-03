---
type: guide
title: 서식 재분류 기본 OFF와 API·worker 재생성 가이드
description: 제목 OCR 서식 재분류의 기본값, 다시 켜기, 로컬·AWS·Helm 적용과 확인 절차
tags: [harness, docraft, installer, classification, operations]
status: active
---

날짜: 2026-10-03

브랜치: harness-v2·harness-installer fix/classification-default-off, Docraft docs/classification-default-off (각 dev 기준)

워크트리: 각 저장소 .worktrees/classification-default-off

## 기본값과 적용 범위

사용자 요청에 따라 제목 OCR 기반 서식 재분류를 기본 OFF로 유지한다.
OFF는 `TITLE_OCR_URL=` 또는 Helm `mlife-harness.harness.titleOcrUrl: ""`이다.
코드·Compose·Helm의 빈 주소 기본값은 그대로 사용하며, 기존에 켜던 AWS 예시와 설치 GPU 프로파일 5종을 OFF로 맞췄다.
루트 작업 공간 `harness-v2/deploy/aws/.env.aws`도 OFF로 변경했다. 기존 설치 환경의 명시적인 ON 값은 자동으로 덮어쓰지 않는다.

이 설정은 하네스의 제목 OCR 확인과 서식 재분류에 따른 Docraft 재추출을 끈다.
Agentic OCR(AO)의 입력 분류는 유지한다. Docraft는 지정받은 `doc_type`으로 읽으므로 자체 자동분류 토글이나 Docraft backend 재생성은 필요 없다.
`auto_reprocess`는 추출값 복구용 ROI 재읽기이며 이 설정과 다르다.

## 다시 켜기 / 끄기

해당 환경 파일만 편집한다: 로컬 `deploy/local/.env.local`, AWS `deploy/aws/.env.aws`.

```dotenv
# OFF (기본)
TITLE_OCR_URL=
# ON으로 바꿀 때 위 줄의 값을 다음 주소로 교체 (중복 키를 추가하지 않는다)
# TITLE_OCR_URL=http://paddleocr-lines-api:8080
```

ON 주소는 API·worker 컨테이너에서 접근 가능한 PaddleX 줄 OCR 서버의 기본 주소다.
위 주소는 AWS Docraft Compose 네트워크에 연결된 구성 예시다. 로컬은 실제 OCR 서비스 주소·공유 네트워크를 확인해 지정한다.
Docraft OCR 서비스(`paddleocr-lines-api`, `ocr` profile)가 실행 중이어야 하며, 서식이 달라 전체 재추출할 때는 `DOCRAFT_URL`도 필요하다.
주소만 있고 Docraft가 없으면 제목 감지만 수행한다.

## 로컬 API·worker에 반영

실행 중인 작업이 끝난 뒤 harness-v2 저장소 루트의 Bash에서 실행한다.
환경변수는 컨테이너 생성 시 고정되므로 `docker compose restart`는 바뀐 값을 적용하지 않는다.
설정 변경에는 아래 재생성을 쓰며 이미지 재빌드는 필요 없다.
공용 helper가 모델·GPU 선택 오버레이를 포함한다. DB·scanner·Docraft는 재생성하지 않는다.

```bash
set -euo pipefail
SCRIPT_DIR="$PWD/deploy/local"
source "$SCRIPT_DIR/_common.sh"
"${COMPOSE[@]}" up -d --no-deps --force-recreate \
  --scale "worker=${WORKER_REPLICAS:-1}" api worker
"${COMPOSE[@]}" ps api worker
"${COMPOSE[@]}" exec -T api python -c 'import os; print("TITLE_OCR_URL=" + os.environ.get("TITLE_OCR_URL", ""))'
"${COMPOSE[@]}" exec -T worker python -c 'import os; print("TITLE_OCR_URL=" + os.environ.get("TITLE_OCR_URL", ""))'
"${COMPOSE[@]}" logs --tail 30 api worker
```

`WORKER_REPLICAS`는 기존 운영 수에 맞춰 둔다. 수동 `--scale`로 증설했다면 위 값도 그 수로 맞춰 유지한다.
워커가 여러 개면 `exec -T --index 2 worker ...`처럼 각 replica의 값도 확인한다.
OFF일 때 출력은 `TITLE_OCR_URL=`이고, 새 비동기 요청 결과에는 `harness.reclassification`이 없어야 한다.
API `/healthz`·`/readyz` 상태를 기존 인증·포트 설정으로 확인한다. 과거 요청 결과는 바뀌지 않는다.

설정을 바꾸지 않고 동일 환경으로 프로세스만 재시작할 때는 다음을 쓸 수 있다.

```bash
"${COMPOSE[@]}" restart api worker
```

## AWS 적용 (배포 담당 세션)

일반 세션은 직접 배포·테스트를 호출하지 않는다. 변경한 `deploy/aws/.env.aws`와 이 가이드를 배포 담당에게 전달한다.
아래는 배포 담당이 기존 AWS 구성에 설정만 적용하는 절차이며, Docker 권한이 있는 SSH 계정을 전제로 한다.
로컬 AWS 환경 파일 편집 후 harness-v2 저장소 루트의 Bash에서 실행한다.

```bash
set -euo pipefail
SCRIPT_DIR="$PWD/deploy/aws"
source "$SCRIPT_DIR/_common.sh"
"${SCP[@]}" "$ENV_FILE" "${SSH_USER}@${SSH_HOST}:${REMOTE_ROOT}/.env.aws"
remote_compose up -d --no-deps --force-recreate \
  --scale "worker=${WORKER_REPLICAS:-2}" api worker
remote_compose ps api worker
remote_compose exec -T api printenv TITLE_OCR_URL
remote_compose exec -T worker printenv TITLE_OCR_URL
remote_compose logs --tail 30 api worker
```

helper는 AWS·모델·GPU 선택 오버레이를 포함하며 원격 기본 경로는 `/opt/mlife-harness`다.
워커 수는 실제 운영 수에 맞춘다. 여러 replica는 `exec -T --index 2 worker printenv TITLE_OCR_URL` 등으로 확인한다.
설정만 바꾸는 경우 전체 `deploy.sh` 실행은 필요 없다. 재시작만 필요할 때는 `remote_compose restart api worker`를 사용한다.

## 설치 번들 / Helm

GPU 프로파일도 기본 OFF다. 기존 설치에 다시 적용하려면 최초 설치 때 사용한 프로파일·values·노드·스토리지·registry 옵션을 유지하고 다음 override를 추가한다.

```bash
# 기존 ./install.sh 명령의 마지막에 추가 (OFF)
--set 'mlife-harness.harness.titleOcrUrl='
# ON으로 바꿀 때는 위 override 대신 추가
--set 'mlife-harness.harness.titleOcrUrl=http://mlife-harness-docraft-paddleocr-lines:8080'
```

`./install.sh` 재실행은 Helm upgrade이며, ConfigMap 변경의 checksum으로 API·worker Deployment가 갱신된다.
Docraft paddleocrLines 서비스는 다른 좌표 판독에서도 쓰므로 끄지 않는다.

## 원인·검증·실행 상태

문제 유형은 배포 환경의 override가 애플리케이션의 기본 OFF를 다시 ON으로 바꾸는 설정 불일치다.
같은 원인을 공유하는 AWS 예시·실제 작업 공간 AWS 설정·GPU 프로파일 5종에 적용했다.
Docraft 추출값 복구와 AO 자체 분류는 범위 밖이다.

검증: 로컬·AWS Compose 렌더링에서 API·worker의 빈 TITLE_OCR_URL 확인, GPU 프로파일 5종 YAML OFF 확인, 기존 서식 재분류 단위 테스트 48건 통과, git diff --check 통과. 새 기능·로직 변경이 없어 추가 테스트 코드는 만들지 않았다.
실제 AWS 재생성·외부 OCR 테스트는 이 세션에서 실행하지 않았다. 변경한 작업 공간 환경 파일은 다음 적용부터 사용된다.
