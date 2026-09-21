---
type: Implementation Log
title: "PaddleOCR-VL 로컬 Docker 호스팅"
description: "PaddleOCR-VL을 compose ocr profile로 로컬 GPU에 호스팅한 구성과 검증"
tags: [ocr, paddleocr, docker]
status: stable
---

# PaddleOCR-VL 로컬 Docker 호스팅

## 2026-09-21

공식 `deploy/paddleocr_vl_docker/accelerators/nvidia-gpu` compose를 기준으로 루트 `compose.yaml`에 `ocr` profile을 추가했다. `docker compose up -d`는 기존처럼 PostgreSQL만 띄우고, `docker compose --profile ocr up -d`일 때만 OCR 컨테이너가 뜬다.

| 서비스 | 이미지 (`latest-nvidia-gpu-offline`) | 역할 |
|---|---|---|
| `paddleocr-vlm-server` | `paddleocr-genai-vllm-server` (22GB) | vLLM으로 PaddleOCR-VL-1.6-0.9B 서빙, 내부 8080 |
| `paddleocr-vl-api` | `paddleocr-vl` (17GB) | PP-DocLayoutV3 layout + `POST /layout-parsing`, 호스트 `127.0.0.1:${PADDLEOCR_PORT:-8080}` |

공식 구성과 다른 점:

- `shm_size`를 64g → 4gb로 줄였다(WSL RAM 15GB).
- API 포트는 localhost에만 바인딩한다. GPU 번호는 `PADDLEOCR_GPU`, 이미지 태그는 `PADDLEOCR_IMAGE_TAG`로 바꾼다.
- vLLM 설정을 `deploy/paddleocr/vllm_config.yaml`로 마운트한다. RTX 4070(12GB, 데스크톱이 약 2GB 사용)에서 `gpu-memory-utilization: 0.5`는 multimodal profiling(encoder budget 131072 tokens) 뒤 `No available memory for the cache blocks`로 실패했다. `max-num-batched-tokens: 16384`, `max-num-seqs: 32`, `gpu-memory-utilization: 0.6`으로 KV cache 4.8GiB를 확보했고 두 컨테이너 실행 시 GPU 사용량은 약 9.7GB/12.3GB였다.

## 검증

- 합성 한글 영수증 PNG(1200x700)와 이를 이미지로만 넣은 스캔 PDF를 `parsers.parse`로 처리했다. 워밍업 이후 페이지당 약 1초, 5개 영역 모두 `block_bbox`와 `page_size`가 채워졌다.
- 인식 결과 4/5 줄이 정확했다. `환자명: 홍길동`은 `환자명허흐김동`으로 오인식됐다(합성 36px 나눔고딕 이미지). 실제 문서 품질 평가는 별도로 필요하다.
- 격리 schema(`ocr_e2e`, 확인 후 삭제)로 띄운 Docraft API에 두 파일을 업로드해 `parsed` 상태와 저장된 block bbox를 확인했다. 개발 DB와 사용자 파일은 건드리지 않았다.
- 백엔드 테스트 28개 통과(영역 bbox 매핑 테스트 추가).

## 2026-09-21 모델 설정 단일화

- 기존에는 `.env`의 `PADDLEOCR_MODEL`(`PaddleOCR-VL-1.6`)이 `/api/ai/status` 표시에만 쓰였고, 실제 모델은 compose `--model_name`과 API 이미지 내부 `pipeline_config_vllm.yaml`에 고정돼 있었다.
- compose가 저장소 루트 `.env`를 interpolation에 쓰므로 `${PADDLEOCR_MODEL:-PaddleOCR-VL-1.6-0.9B}`를 두 서비스에 넣었다. API 컨테이너는 시작 시 이미지 기본 설정의 `model_name: PaddleOCR-VL...` 줄만 바꾼 사본(`/tmp/pipeline.yaml`)으로 서빙한다. layout 모델(PP-DocLayoutV3)과 `pipeline_name`은 이미지 기본값을 유지한다.
- 앱 기본값과 `.env.example`을 실제 서빙 이름 `PaddleOCR-VL-1.6-0.9B`로 맞췄다.
- 추출·스키마용 `AI_VLM_MODEL`은 텍스트 전용 `qwen/qwen3-32b`였다. 현재 `engine.py`는 텍스트 block만 보내 동작에는 문제가 없었지만, 변수 의도와 README 예시에 맞춰 이미지 입력과 structured outputs를 지원하는 `qwen/qwen3-vl-32b-instruct`로 바꿨다(OpenRouter model 목록에서 확인).
