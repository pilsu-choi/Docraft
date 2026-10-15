---
okf_version: "0.2"
type: change
title: 판독 실패 진단성 개선 (타임아웃 분류·실패 한 줄·입력 보존·Envoy 로그·디스크 한도)
description: 고객사 502 "timed out (19.0s)"를 로그만으로 원인 구분하지 못한 문제를 고친다. httpx 시간 초과 408 통일, 실패 한 줄, VLM 호출 X-Request-ID·upstream·느린 호출 INFO, 실패 입력 보존과 replay, Envoy 로그 형식, ephemeral-storage/sizeLimit, health version.
tags: [docraft, observability, timeout, envoy, helm, airgap, ephemeral-storage]
status: active
---

날짜: 2026-10-15
브랜치: `feat/debug-observability`(GitLab dev 780e1e2 기준)
워크트리: `Docraft/.worktrees/debug-observability`

## 근본 원인

- `/api/read-options`가 502로 응답한 "timed out (19.0s)"는 호출자가 보낸 `remaining_ms`(19초)로 잘린 httpx `ReadTimeout`이었다. 로그에는 traceback뿐이라 호출 timeout인지 요청 시한인지 자리 대기인지, 어느 파드인지 알 수 없었다.
- `httpx.ReadTimeout`은 builtin `TimeoutError`가 아니라서 `/api/read`·`/api/verify`의 `except TimeoutError → 408`을 지나쳐 502가 됐고, `/api/read-options`에는 408 분기가 아예 없었다. PaddleOCR 호출의 `ReadTimeout`은 `ParseError`(ValueError)로 감싸 422가 됐다.

## 문제 유형과 범위

"타임아웃 예외 종류가 여러 개인데 한 종류만 408로 분류" → 예외 사슬 전체를 보는 공용 분류 `failures.classify`(408 시간 초과/502 상위 서버/422 입력)를 세 읽기 경로와 스키마 생성(`/schemas/generate`)이 함께 쓴다. httpx 시간 초과는 `latency.remote_call`이 `latency.Timeout`(종류·timeout 포함 `TimeoutError`)으로 바꾸므로 VLM(`engine._provider`)·OCR(`parsers._ocr_pages`)이 같은 경로를 탄다. 줄 OCR 실패는 기존대로 소프트 폴백(`latency.Timeout` 포함).

범위 밖: 백그라운드 작업(`run_parse`·`run_extract`)은 문서 `error` 텍스트로 남기는 구조라 그대로 둔다(이제 `Timeout` 메시지에 종류와 timeout이 들어간다).

## 변경

| 항목 | 내용 |
| --- | --- |
| 분류 | `backend/failures.py` `classify`/`response`; 연결 거부도 502(하네스는 408/502를 같은 "판독 불가"로 처리, 503은 재시도 지시로 읽혀 제외) |
| 실패 한 줄 | `failures.Call.fail`: rid·endpoint·doc_type·status·stage·kind·timeout_s·budget_ms·remaining_s·elapsed_ms·vlm_calls·upstream + 단계 합계. `latency.timed`가 예외 통과 시 가장 안쪽 단계를 `_stage`로 남김. traceback은 DEBUG(`kind=error`만 ERROR) |
| VLM 호출 | `X-Request-ID: <rid>#<n>` 전달, 응답 헤더 `x-upstream-host` 읽기, `VLM_SLOW_MS`(15000) 초과·실패 호출 INFO/WARNING 한 줄 |
| Envoy | 접근 로그에 `rid`·`in/out`·`try`·`fail` 추가, 라우트 `response_headers_to_add: x-upstream-host=%UPSTREAM_REMOTE_ADDRESS%` |
| 입력 보존 | `failed/<날짜>/<rid>/{input.*,meta.json,vlm_replies.json}`, `FAILED_KEEP_DAYS`(7, 0=끔)·`FAILED_MAX_MB`(2048), 시작·저장 시 정리, `python -m backend.replay` |
| 디스크 | 모든 컨테이너 ephemeral-storage requests/limits, 모든 emptyDir `sizeLimit`(`ephemeral.tmp`·`masterSource`), vLLM·vlm-server 한도 30Gi |
| health | `/api/health.version` = `DOCRAFT_COMMIT`(Dockerfile ARG/ENV, `deploy/aws/deploy.sh`가 전달). 설치 번들 `build-bundle.sh`의 docraft-backend 빌드는 `--build-arg DOCRAFT_COMMIT=<커밋>`을 넘겨야 한다(이 저장소 밖) |

## 하네스 영향 확인 (읽기 전용 점검)

하네스 `reread/docraft.py`는 상태 코드를 가리지 않는다. `_raise_for_status`가 2xx 외를 모두 `httpx.HTTPStatusError`(detail 포함)로 올리고, 호출부는 `_FAILURES = (httpx.HTTPError, OSError, ValueError, TypeError)`로 잡아 `unavailable(...)`(증거 없이 진행·검토 대상)로 처리한다. 408과 502에 다른 분기가 없어 408 증가가 하네스 동작을 바꾸지 않는다. `normalizer/cert_status.py`는 `reason`이 있으면 판독 안 함으로 기록만 한다.

## 검증

- `tests/test_failures.py`: 타임아웃 9종 × 3 엔드포인트 408, 상위 서버 오류 7종 × 3 엔드포인트 502, 한 줄 필드, X-Request-ID 인덱스·upstream·느린 호출 로그, 보존·정리(일수·용량·0일)·저장 실패 비차단·replay, helm 렌더(ephemeral/sizeLimit/Envoy 형식).
- 전체 빠른 회귀(`pytest -n 4`) 통과. 전체 회귀·AWS 반영은 별도(배포 담당).
- Envoy 바이너리가 없어 설정은 YAML 파싱·문서(1.35 헤더 포맷터 `%UPSTREAM_REMOTE_ADDRESS%`)로만 확인했다. 클러스터 적용 시 라우터 파드가 `Ready`인지 먼저 본다.
