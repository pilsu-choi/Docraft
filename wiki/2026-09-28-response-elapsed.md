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

## 루트 공통 기록 보충 (2026-10-03 동기화)

저장소별 구현·검증 기록은 위 내용을 보존한다. 아래는 공통 원본 `/home/pilsu/projects/mirae-assets/wiki/2026-09-28-response-elapsed.md`의 상세 실험·통합 이력으로, 당시 날짜와 기준 커밋을 유지한다. 과거 정책과 수치는 최신 사용자 정책 또는 현재 dev 실행 결과로 해석하지 않는다.

날짜: 2026-09-28
브랜치: `feat/response-elapsed` (harness-v2 `33ffa27`, Docraft `f2dfa10`에서 `dev`에 병합했고 브랜치는 삭제함)
워크트리: `harness-v2/.worktrees/response-elapsed`, `Docraft/.worktrees/response-elapsed` (정리 완료)

## 배경

기존에는 문서마다 Docraft를 부른 시간만 응답에 있었다. 요청 한 건의 전체 처리시간은 로그에만 남았다.

## 변경

| 저장소 | 응답 필드 | 범위 |
|---|---|---|
| harness-v2 | `harness.elapsed_ms` (신규) | 동기(`_run_sync`)·비동기(`run_job`) API의 파이프라인 처리 전체. Docraft 호출 시간도 포함 |
| harness-v2 | `harness.docraft_reads[].elapsed_ms`, `harness.fallback.documents[].elapsed_ms` (기존) | Docraft 호출 1회에 걸린 시간 |
| harness-v2 | `…reprocess.elapsed_ms` (기존) | Docraft 재처리에 걸린 시간 |
| Docraft | `documents[0].verify.elapsed_ms` (UI 형식은 `result.verify.elapsed_ms`, 신규) | `/api/verify`의 업로드 저장부터 응답 직전까지 |
| Docraft | `/api/read` 최상위 `elapsed_ms` (기존) | 읽기 한 건 |

- 하네스 자체 시간은 따로 싣지 않는다. `harness.elapsed_ms`에서 Docraft 호출 시간의 합을 빼서 구한다.
- `harness.elapsed_ms`는 `HarnessPipeline.process()` 결과에 넣지 않고 API 계층에서 넣는다. 같은 입력이면 같은 결과가 나와야 한다는 재현성 요구(§9.4)와 결정성 테스트를 지키기 위해서다. 따라서 CLI 배치 결과에는 이 필드가 없다.
- 스키마 `TRANSACTION_HARNESS_SCHEMA`에 선택 속성으로 추가했다. 두 README도 갱신했다.

## 검증

- harness-v2: 1558건 통과, 2건 건너뜀 (`test_sync_api`에서 두 경로 모두 정수가 실리는지 확인).
- Docraft: 616건 통과 (`test_verify` 라우트 테스트에서 필드가 실리는지 확인).
