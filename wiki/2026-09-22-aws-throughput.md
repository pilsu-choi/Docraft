---
type: Experiment and Implementation Log
title: "AWS 이미지 병렬 처리량과 중규모 내구성 측정"
description: "L4 서버에서 PaddleOCR 서비스별 동시성 한계와 이미지 100건 연속 처리를 측정해 QUEUE_CONCURRENCY를 6으로 정하고, 측정 중 발견한 업로드 413과 프로젝트 삭제 시 원본 파일 잔존을 고친 기록"
tags: [aws, performance, queue, paddleocr, upload]
generated: {by: claude-code/claude-opus-5, at: 2026-09-22}
status: stable
---

# AWS 이미지 병렬 처리량과 중규모 내구성 측정

- 날짜: 2026-09-22
- 브랜치: `fix/upload-batch`
- 워크트리: `.worktrees/upload-batch`

사용자 요청에 따라 PDF는 빼고 **이미지만** 측정했다. 샘플은 `samples/agentic-ocr-2.0.1-results/images` 5종(0.5~4.2MB PNG)이고, 설정은 [aws-deploy](2026-09-22-aws-deploy.md)의 L4 서버, `TABLE_REFINE=true`, inline 큐다.

## 서비스 단독 처리량 (backend를 거치지 않고 서버 안에서 직접 호출)

| 동시 요청 | 레이아웃(PaddleOCR-VL, GPU) | 줄 OCR(PP-OCRv5, CPU) |
| --- | --- | --- |
| 1 | 8.4건/분 (건당 7.2초) | 17.5건/분 |
| 2 | 12.0건/분 | 19.6건/분 |
| 4 | 10.9건/분 | 18.6건/분 |
| 8 | 10.4건/분 (건당 34.7초) | 18.2건/분 |

- 레이아웃이 동시 2에서 포화된다(GPU 사용률 약 80%, 메모리 약 10GB). 그 이상은 대기 시간만 늘고 실패는 없다.
- vLLM이 아니라 레이아웃 파이프라인(`paddlex --serve`) 쪽이 한계다.

## 전체 경로 (업로드 → 파싱 완료, 외부 URL 경유)

| 설정 | 문서 | 처리량 | 업로드→완료 평균/최대 | 결과 |
| --- | --- | --- | --- | --- |
| `QUEUE_CONCURRENCY=2` | 20 | 6.5건/분 | 92초 / 180초 | 20 parsed |
| `QUEUE_CONCURRENCY=6` | 20 | 9.6건/분 | 66초 / 121초 | 20 parsed |
| `QUEUE_CONCURRENCY=6` | 100 | 10.6건/분 | 283초 / 556초 | 100 parsed |

- 동시 2에서는 작업 스레드가 줄 OCR·표 교정(OpenRouter) 대기에 묶여 레이아웃을 절반만 쓴다. 그래서 AWS 기본값을 6으로 정했다(`.env.aws.example`).
- 100건 동안 로그 ERROR·WARNING 0건, 컨테이너 재시작 없음, backend 메모리 575MB로 안정적이었다.
- 같은 이미지 20장씩의 결과(표 구조·줄 OCR 블록 수)가 전부 같아서, 동시 처리 중에 품질이 흔들리거나 단계가 조용히 빠지지 않았다.
- 서버를 하루 돌리면 이미지 약 1.5만 건을 처리하는 속도다. 더 늘리려면 레이아웃 서비스를 여러 벌 띄우거나(GPU 여유 13GB) 레이아웃과 줄 OCR을 문서 안에서 병렬로 돌려야 한다.

## 측정 중 발견해 고친 것

- **UI 업로드 413**: UI가 선택한 파일 전부를 한 요청으로 보내는데, nginx `client_max_body_size 30m` 때문에 스캔 이미지 20장(약 33MB)부터 413이 났다. `frontend/src/api.ts`의 `upload`가 파일마다 한 요청씩 순서대로 보내도록 바꿨다. 파일 1개 상한은 backend `MAX_UPLOAD_BYTES`(25MB)라 nginx 제한에 걸리지 않는다.
- **프로젝트 삭제 시 원본 파일 잔존**: 문서 삭제는 원본을 지우지만 프로젝트 삭제는 DB 행만 지워 `data/files`에 파일이 남았다. 두 경로가 `remove_file()`을 함께 쓰도록 했고, 삭제는 커밋 뒤에 한다. `tests/test_projects.py`에서 확인한다(94 passed).
