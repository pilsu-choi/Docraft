---
type: Implementation Log
title: "AWS 개발 서버 배포 스크립트"
description: "harness-v2의 deploy/aws 구조를 따라, 같은 EC2(NVIDIA L4)에 Docraft 전체 스택(app + PaddleOCR)을 올리는 스크립트를 추가한 기록"
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
- 서버 조사는 읽기 전용 SSH로만 했다. 실제 배포는 하지 않았다.
