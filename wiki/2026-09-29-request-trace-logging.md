---
type: change
title: 하네스·Docraft 요청 추적 로그와 오류 로그 보강
description: 하네스 API 요청 ID 발급·전파, Docraft 백그라운드 작업의 요청 ID 이어받기, 삼키던 오류의 스택 기록, 로그 없던 모듈 보강, k8s 로그 출력 확인
tags: [harness, docraft, logging, observability, request-id]
status: active
---

날짜: 2026-09-29
브랜치: `fix/request-trace-logging` (harness-v2 병합 `6efbd1d`, Docraft 병합 `81d98a8` 로 `dev` 에 반영·push 했고 브랜치는 삭제함)
워크트리: `harness-v2/.worktrees/request-trace-logging`, `Docraft/.worktrees/request-trace-logging` (정리 완료)

## 배경

점검 결과 로그는 대체로 충분했지만 다음 빈틈이 있었다.

- 하네스 API 가 요청 ID 를 받지도 만들지도 않았다.
- Docraft 는 하네스가 보낸 ID 를 업로드 요청까지만 붙였고, 이어지는 백그라운드 작업 로그에서는 그 ID 를 잃었다.
- 오류를 경고 한 줄로만 남기고 대체 동작으로 넘어가는 곳이 있었다. 하네스의 작업 조회는 DB 장애가 나도 404 로 보였다.
- Docraft 일부 모듈에는 로그가 없었다.

## 변경

| 저장소 | 변경 |
|---|---|
| harness-v2 | HTTP 미들웨어가 `X-Request-ID` 를 이어받거나(ASCII, 최대 64자) 새로 만든다(12자). 요청 안의 모든 로그 줄에 `[req=…]` 가 붙고 응답 헤더로 돌려준다. 작업 제출 로그 `제출 접수` 에 `req`와 `job` 이 한 줄에 남는다 |
| harness-v2 | Docraft 로 보내는 `X-Request-ID` 는 `job.txn.doc` 순으로 만들고, 셋 다 없을 때만 `req` 를 쓴다 |
| harness-v2 | `PostgresJobStore._restore` 실패 시 스택을 남기고 `StorageError` 를 올린다. 앱 전역 핸들러가 이를 **503** 으로 응답한다(이전: 404) |
| harness-v2 | 콜백 최종 실패, 임베딩, 큐 발행, Postgres/ClickHouse 연결, 규칙 오류 경고에 `exc_info=True` 추가(동작 변화 없음) |
| Docraft | `enqueue` 가 현재 rid 를 작업에 넘긴다(inline 은 직접 전달, celery 는 `kwargs={"rid": …}`). 작업 로그 표식이 `[<하네스 rid>>parse:<document_id>]` 가 된다. rid 가 없는 옛 메시지는 기존 `[parse:<id>]` |
| Docraft | `engine.py`(표 보정, 페이지 렌더링)와 `parsers.py`(줄 OCR, 괘선 표) 대체 경고에 스택 추가. `main.py` `frames()` 가 오류를 조용히 삼키지 않고 DEBUG 로 남긴다 |
| Docraft | `reprocess.py` 종료 요약(INFO: 종료 사유·대상 수·시도·모델 호출·소요 시간)과 필드별 단계(DEBUG), 단계 실패(WARNING+스택) 로그 추가 |
| Docraft | `inference.py`, `table_grid.py` 판단 지점 DEBUG 로그, PaddleOCR 페이지별 진행(DEBUG `page i/n`), `master.py` 의 `print()` 를 로거로 교체 |

문서 원문, 필드 값, 프롬프트는 새로 기록하지 않는다. id, 개수, 길이, 시간만 남긴다.

## 로그 따라가기

하네스 요청 하나를 끝까지 따라갈 때는 다음 순서로 본다.

1. 하네스 API 로그에서 `req=<ID>` 를 찾아 `job` 을 얻는다.
2. `job` 으로 하네스 문서 처리 로그를 따라간다.
3. Docraft 로그에서 같은 `job.txn.doc` 값을 검색하면 업로드 요청과 뒤이은 작업(`…>parse:<id>`, `…>extract:<id>`) 이 함께 나온다.

## k8s 로그 출력 확인

Docraft helm 설정은 `templates/config.yaml:13` 에서 `LOG_FILE: ""` 이고, `_helpers.tpl:219` 의 `envFrom` 으로 API(`backend.yaml:73`)와 워커(`backend.yaml:147`) 모두에 들어간다. 따라서 k8s 에서는 파일을 쓰지 않고 표준 출력만 쓰며, `kubectl logs` 로 본다. 하네스도 표준 오류로만 출력한다. 파드가 재시작되면 이전 로그는 `kubectl logs --previous` 로 한 번만 볼 수 있으므로, 오래 보관하려면 로그 수집기가 필요하다.

## 검증

- harness-v2: `uv run pytest -q`, 1591 passed, 2 skipped. 새 테스트 `tests/unit/test_api_request_id.py`
- Docraft: `python -m pytest -q`, 620 passed. `tests/test_jobs.py` 에 rid 전달 테스트 추가. celery 경로는 가짜 `send_task` 로만 확인했다

## 로그 기본값·helm 설정 정리 (후속)

브랜치 `fix/log-defaults` (harness-v2 병합 `efbfb62`, Docraft 병합 `ee81eba`, 정리 완료)

| 저장소 | 변경 |
|---|---|
| harness-v2 | 코드 기본값 `log_level` DEBUG→INFO, `log_values` true→false. 설정이 빠져도 DEBUG 로그·판독값이 새지 않는다. 개발은 `.env.example` 의 `LOG_LEVEL=DEBUG`·`LOG_VALUES=true` 그대로 |
| harness-v2 | helm 워커의 `--loglevel=INFO` 고정값을 `harness.logLevel` 로. `harness.logLevels`(→ `LOG_LEVELS`) 추가 — `helm upgrade --set harness.logLevels="rules=DEBUG"` 로 한 갈래만 자세히 본다 |
| Docraft | `LOG_LEVEL` 기본값 DEBUG→INFO(`backend/config.py`, `compose.yaml`). `.env.example` 은 DEBUG 유지 |

검증: harness-v2 1591 passed(판독값 로그 테스트는 `_log_values` 를 테스트 안에서 켬), Docraft 620 passed, `helm template` 로 워커 레벨·`LOG_LEVELS` 렌더링 확인.

## 남은 일

- 설치 번들 재빌드 전이다.
- k8s 에서 로그를 파일로 오래 남길 방법(수집기 또는 PVC 파일 기록)은 정하지 않았다.
