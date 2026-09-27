---
okf_version: "0.2"
type: Implementation Log
title: "요청 ID 로그 문맥과 실패 사유 기록"
description: "모든 로그 줄에 [rid] 를 붙여 동시 /api/verify 의 중간 줄(LLM 호출 등)을 요청별로 가르고, 하네스가 보낸 X-Request-ID(job.txn.doc)로 두 시스템 로그를 잇게 한 기록. 4xx 사유·AI provider HTTP 오류 본문도 남긴다"
tags: [backend, logging, observability, verify, harness]
generated: {by: claude-code/claude-opus-5-5, at: 2026-09-27}
status: active
---

# 요청 ID 로그 문맥과 실패 사유 기록

- 날짜: 2026-09-27
- 브랜치: `feat/0927-logging`, 워크트리 `.worktrees/logging`
- 짝 작업: harness-v2 `feat/0927-logging` — [하네스 wiki](../../harness-v2/wiki/2026-09-27-워커-로깅-Docraft-요청ID.md)

## 문제

- 로그 형식이 `시각 레벨 모듈: 메시지` 뿐이라 `/api/verify` 가 동시에 돌면 중간 줄(`provider call`, `table refine`,
  `extract` 등)이 어느 요청의 것인지 알 수 없었다. 파일명은 마지막 `verify finished` 줄에만 있었다.
- 하네스 로그와 이을 식별자가 없었다.
- `HTTPException` 사유(detail)와 AI provider HTTP 오류 본문이 로그에 남지 않았다.

## 바꾼 것

| 위치 | 내용 |
|---|---|
| `config.py` | `request_id` contextvar, `bind_request()`, `new_request_id()`(허용 글자 `A-Za-z0-9._:/=-`, 64자, 없으면 12hex 생성). 핸들러에 `_RequestIdFilter`, 형식 `%(asctime)s %(levelname)s %(name)s [%(rid)s] %(message)s` |
| `main.py` `log_requests` 미들웨어 | 요청마다 `X-Request-ID` 를 받거나 만들어 묶고, 응답 헤더로 돌려준다. 결말 한 줄(`GET /api/... -> 200 elapsed=…`) — 4xx·5xx 는 WARNING, `/api/health` 는 DEBUG |
| `main.py` `log_http_error` | `HTTPException` 의 상태·detail 을 WARNING 으로 남기고 기본 처리로 넘긴다 |
| `jobs.py` `task()` | 등록 작업을 `bind_request("<작업>:<첫 인자>")` 로 감싼다 — inline·celery 공통, 예 `[parse:<document_id>]` |
| `engine.py` | provider HTTP 오류에 응답 본문(`_truncate`)을 붙인다 |

`/api/verify` 본체는 `asyncio.to_thread` 로 돌고, `to_thread` 는 contextvar 를 복사하므로 그 안의 로그에도 `[rid]` 가 붙는다.

## 검증

- `tests/test_api.py::test_request_id_is_echoed_and_tags_every_log_line`: 걸러진 rid 가 응답 헤더와 로그 줄에 남고, 404 사유가 기록된다.
- 전체 `pytest tests`: 497 passed.

## 로그 보관

k8s 차트는 `LOG_FILE=""` 라 파일을 쓰지 않고 stdout 만 쓴다 — 노드 `/var/log/pods` 에서 kubelet 기본 순환(10Mi × 5)만
적용되고 파드가 없어지면 함께 사라진다. 파일 로그(`RotatingFileHandler` 10MB × 3)는 AWS compose(`/data/logs`)와 로컬 실행에서만 쓴다.
