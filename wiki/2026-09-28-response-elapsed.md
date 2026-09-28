---
okf_version: "0.2"
type: change
title: "/api/verify 응답에 요청 처리시간(verify.elapsed_ms) 추가"
description: "업로드 저장부터 응답 직전까지 걸린 시간을 documents[0].verify.elapsed_ms로 반환한다"
tags: [docraft, api, verify, elapsed_ms, observability]
status: active
---

# /api/verify 응답에 요청 처리시간(verify.elapsed_ms) 추가

날짜: 2026-09-28
브랜치: `feat/response-elapsed` (`dev`에 병합 후 브랜치 삭제)
워크트리: `.worktrees/response-elapsed`

## 배경

`/api/verify`는 처리 완료 로그에 `elapsed=%.2fs`를 남겼지만 응답 본문에는 걸린 시간이 없었다. harness-v2도 같은 요청에 `harness.elapsed_ms`를 추가하는 짝 작업을 진행했다.

## 변경

- `backend/main.py`의 `verify_result` 라우트에서 `verify.document(result)["verify"]` 블록에 `elapsed_ms`(정수, ms)를 추가했다. 요청 시작(`started = time.monotonic()`, 업로드 저장 직전)부터 응답 직전까지의 시간이다.
- 로그 메시지를 `elapsed=%.2fs`(초, 소수점 2자리)에서 `elapsed_ms=%d`(정수, ms)로 바꿔 응답 필드와 단위를 맞췄다.
- 응답 위치는 `documents[0].verify.elapsed_ms`이고, UI 호환 형식(`ao_result`가 `{"result": ...}`인 요청)에서는 `result.verify.elapsed_ms`다. `/api/read`의 최상위 `elapsed_ms`(읽기 한 건)는 이번 변경 전부터 있던 별도 필드다.
- README에 `verify`가 `counts`·검사 결과와 함께 `elapsed_ms`를 담는다고 반영했다.

## 검증

- `tests/test_verify.py`의 `test_verify_route_returns_the_corrected_result`에 `documents[0]["verify"]["elapsed_ms"]`가 정수인지 확인하는 검증을 추가했다.
- 같은 파일의 `test_verify_route_accepts_the_ui_result_format`을 `result["verify"]["counts"] == {}`만 확인하도록 고쳐 새 `elapsed_ms` 키가 있어도 통과하게 했다.
- 전체 테스트 616건 통과.

## 통합

- Docraft dev: `f2dfa104a40a94148babc5419c6133683b7b6567` ("병합: /api/verify 응답 처리시간(verify.elapsed_ms)을 dev에 반영")
- harness-v2 dev: `33ffa27c83aaffb179efc3a83ac08600d90dfcba` ("병합: API 응답 처리시간(harness.elapsed_ms)을 dev에 반영")

## 관련 문서

- [harness-v2: API 응답 처리시간(harness.elapsed_ms) 추가](../../harness-v2/wiki/2026-09-28-response-elapsed.md)
- [wiki 색인](index.md)
