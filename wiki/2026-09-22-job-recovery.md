---
type: Implementation Log
title: "작업 큐 중단 작업 자동 복구(heartbeat lease·기동 시 재등록)"
description: "worker가 처리 중 죽거나 inline 작업이 API 재시작으로 사라져도 문서가 멈추지 않도록 heartbeat lease와 기동 시 recover()를 추가하고 Docker로 검증한 기록"
tags: [backend, queue, celery, redis, recovery]
status: stable
---

# 작업 큐 중단 작업 자동 복구

2026-09-22 · 브랜치 `fix/job-recovery` · 워크트리 `.worktrees/job-recovery`

[작업 큐 구조 도입](2026-09-22-job-queue.md)의 남은 한계 중 운영상 실제로 문제가 되는 두 가지를 고쳤다.

- worker가 처리 중 죽으면 문서가 `parsing`/`extracting`에 그대로 남았다. celery는 `acks_late`로 메시지를 재배달하지만, claim이 `status='queued'`만 받아서 재배달 메시지가 건너뛰어졌다.
- inline 백엔드는 API를 재시작하면 스레드 풀에 있던 대기 작업이 사라져 문서가 `queued`에 남았다.

## 설계

작업 테이블을 새로 만들지 않고 `documents.updated_at`을 lease로 쓴다.

- **heartbeat**: `run_parse`·`run_extract`는 오래 걸리는 호출(`parse()`, `engine.extract()`)을 `with heartbeat(document_id)`로 감싼다. 데몬 스레드가 `JOB_LEASE_SECONDS/3`마다 `updated_at`을 갱신한다. 문서가 진행 상태가 아니면 갱신하지 않는다.
- **claim 확장**: `status='queued'`이거나, 같은 작업의 진행 상태(`parsing` 또는 `extracting`·`validating`)이면서 `updated_at`이 lease보다 오래된 경우 가져간다. 살아 있는 작업은 heartbeat 때문에 가져갈 수 없고, 죽은 작업만 이어받는다. 추출 메시지가 파싱 중인 문서를 가져가는 일은 상태 목록을 작업별로 나눠 막았다(`ACTIVE`).
- **redis 재배달 시간**: Celery `broker_transport_options.visibility_timeout`을 lease와 같게 뒀다. 기본값(1시간)이면 죽은 worker의 메시지가 1시간 뒤에야 다시 나온다.
- **기동 시 recover()**: API lifespan에서 `queued` 문서와 lease가 지난 진행 문서를 다시 enqueue한다. 작업 종류는 `markdown` 유무로 가른다(없으면 parse, 있으면 extract). 추출 대기 문서의 스키마를 알 수 있도록 `mark_queued()`가 큐 등록 시점에 `schema_id`를 저장한다(이전에는 claim 시점에 저장했다).
  - celery 모드에서는 브로커에 이미 있는 메시지와 중복될 수 있지만, 두 번째 메시지는 claim에서 건너뛴다.
  - 브로커 메시지가 유실된 경우(redis flush 등)도 이 경로로 복구된다.

`JOB_LEASE_SECONDS`(기본 600)는 `backend/jobs.py`에 있다. lease보다 오래 걸리는 작업도 heartbeat가 있으므로 다른 worker가 가로채지 않는다.

## 검증

- `pytest` 68 passed. `tests/test_jobs.py`에 3개 추가: lease가 지난 작업은 이어받고 살아 있는 작업은 건너뜀, `recover()`가 유실된 파싱 대기와 중단된 추출을 끝까지 진행, heartbeat가 `updated_at`을 갱신.
- Docker(격리된 compose 프로젝트 `docraft-qt`, `QUEUE_BACKEND=celery`, `JOB_LEASE_SECONDS=30`, 이미지 빌드 포함):
  1. 정상 흐름: 업로드 3건 → worker가 parse 3건 → 일괄 추출 3건 모두 `completed`.
  2. 메시지 유실: worker를 멈추고 업로드(`queued`) → `redis-cli FLUSHALL` → API 재시작 시 `recovered jobs: 1` → worker 기동 후 `parsed`.
  3. 처리 중 worker 강제 종료: 응답하지 않는 AI provider로 추출을 걸어 `extracting` 상태에서 `docker kill` → worker 재기동 후 약 100초 뒤 같은 문서의 `extract start`가 다시 찍히고 heartbeat가 10초마다 `updated_at`을 갱신. provider timeout(90초) 뒤 `failed`로 끝났다.
  - 확인 후 compose 프로젝트, 볼륨, 임시 파일을 지웠다.
- 검증 중 발견: 워크트리처럼 `./data`가 없는 곳에서 compose를 띄우면 Docker가 root 소유로 만들어 backend·worker가 `/data/files` 권한 오류로 죽는다. main 체크아웃에는 `data/`가 있어 영향이 없다. 새 환경에서는 `mkdir -p data`를 먼저 한다.

## 남은 한계

- 복구 지연은 최대 lease(기본 10분) + kombu 재배달 주기다. 더 빨리 복구하려면 `JOB_LEASE_SECONDS`를 줄이되, heartbeat 주기(lease/3)가 DB 쓰기 빈도가 된다.
- lease가 지난 문서는 API 재기동이나 메시지 재배달 때만 다시 실행된다. 주기적으로 도는 reaper는 없다.
- 작업 이력(시작·종료·소요 시간) 테이블은 모니터링(후보 I)에서 다룬다.
