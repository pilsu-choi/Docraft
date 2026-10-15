---
type: report
title: backend·vLLM 라우터 2파드 고가용성
description: Docraft backend 와 Envoy vLLM 라우터를 2파드로 띄울 때의 차트 값·동시성 합계 나눔·기동 작업 안전성
tags: [docraft, helm, ha, replicas]
status: active
---

날짜: 2026-10-15 · 브랜치: feat/ha-replicas · 워크트리: Docraft/.worktrees/ha-replicas

## 배경
10-14 운영계에서 backend 가 OOMKilled 8회 재시작하는 동안 파드가 하나라 읽기가 전부 실패했다. 노드는 하나라 파드 수준 이중화다.

## 차트
- `backend.replicas`는 있었고 `strategy`가 없어 기본 RollingUpdate(25%)였다 — `maxUnavailable: 0, maxSurge: 1` 로 명시해 교체 중에도 한 파드가 받는다.
- `vllmVlm.router.replicas`(신규, 기본 1)로 Envoy 라우터 복제본을 연다. 라우터는 상태가 없다. least_request 는 라우터마다 자기 연결 기준이라 합쳐서는 근사다.
- 동시성 `vlmConcurrency`·`ocrConcurrency`·`tablePageConcurrency`·`queue.concurrency`는 **전체 합계**로 읽고 `dft.perPod`(templates/_helpers.tpl)가 파드마다 `ceil(합계/replicas)`(최소 1, 0=제한 없음)를 ConfigMap 에 넣는다. 앱은 다시 uvicorn 프로세스(`WEB_CONCURRENCY`)마다 나눈다. 예: l40s-4 VLM 24 → 파드당 12, OCR 6 → 3, 표 8 → 4, 큐 4 → 2.

## 단일 인스턴스 가정 점검
| 항목 | 결과 |
|---|---|
| DB | Postgres 만 사용(SQLite 없음). `init_db`는 `pg_advisory_xact_lock` 으로 동시 기동 안전 |
| 작업 선점 | `claim()`은 `UPDATE … WHERE job_generation=? AND (status='queued' OR 정지된 lease)` 조건부라 한 파드만 성공(동시 4스레드 시험) |
| 기동 `recover()` | queued·정지 작업을 다시 넣는다. 다른 파드 큐에 있던 작업을 중복 투입해도 `claim()`이 한 번만 실행되게 한다 |
| 실패 입력 정리 `failures.prune()` | PVC `/data/failed` 공유. 다른 파드가 먼저 지운 항목(FileNotFoundError)을 건너뛰도록 고침 |
| 파드별 상태 | `cancel-all` 진행 중 요청 취소, `/api/health` `verify_inflight`, 같은 페이지 결과 공유(`READ_CACHE_*`), 마스터 캐시는 파드별 — 알려진 한계 |
| inline 큐 | 파드가 죽으면 그 파드 메모리의 작업이 사라지고 재기동한 파드의 `recover()`가 DB 에서 되살린다(기존 동작) |

## 테스트
`tests/test_ha.py`: 복제본 1/2/3 렌더(replicas·RollingUpdate), 동시성 합계 올림 나눔(복제본 1/2/3/5 × 합계 1/6/24/25), 0 유지, 동시 claim 한 승자, prune 경합. 빠른 회귀 `pytest -n 4` 4224 passed.

