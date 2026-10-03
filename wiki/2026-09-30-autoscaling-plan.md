---
type: plan
title: 하네스·Docraft 자동 확장(오토스케일링) 방안
description: 현재 고정 개수로 도는 하네스·Docraft 구성에 자동 확장을 넣는다면 무엇을, 어떤 기준으로, 어떤 제약 아래 늘릴지 정리한 방안. 권장안은 하네스 worker만 작업 대기열 길이 기준으로 늘리고 GPU 쪽은 고정
tags: [harness, docraft, k8s, helm, autoscaling, keda, hpa, 용량]
status: active
---

날짜: 2026-09-30  
브랜치: 해당 없음 — 루트는 Git 저장소가 아님 (근거: harness-v2 `dev` `7ada0db`, Docraft `dev` `b92f75c`, harness-installer `profiles/`)  
워크트리: 해당 없음

## 현재 상태

- 두 Helm 차트와 인스톨러 설정 어디에도 자동 확장 설정(HPA, KEDA, `minReplicas`·`maxReplicas`)이 없다. 모든 개수는 서버 사양 프로필(`profiles/*.yaml`)로 정하는 고정값이다.
- AWS 개발 서버는 EC2 한 대의 docker compose라 자동 확장 대상이 아니다.

| 구성 요소 | 일하는 방식 | 늘리면 효과가 있나 |
|---|---|---|
| 하네스 api | HTTP 요청 접수 | 가벼움. 가용성용 2개면 충분 |
| 하네스 worker | Celery(브로커 Redis), 대기열 `harness.documents`·`harness.batches`·`harness.jobs` | **있음** — 규칙 검사는 빠르고, Docraft 응답을 기다리는 시간이 대부분 |
| 하네스 batch scanner | 폴더 감시 | 없음. **반드시 1개**(중복 접수 방지) |
| Docraft backend | 하네스가 부르는 `/api/read`는 **대기열 없이 HTTP로 바로 처리** | 제한적 — 실제 일은 GPU 모델이 함 |
| Docraft worker | Celery(같은 Redis, `QUEUE_NAME`으로 분리). UI 작업용 | 하네스 경로와 무관 |
| vLLM(Qwen3-VL)·PaddleOCR-VL·줄 OCR·임베딩 | GPU 모델 서버 | **없음** — 여유 GPU가 없으면 새 개수가 자리를 못 잡음 |

## 병목

- 처리량을 막는 것은 **Qwen 생성 속도(요청당 약 16 tok/s)**와 **하네스 worker 슬롯(개수 × 동시 처리)**이다(`profiles/l40s-2.yaml` 주석).
- AWS 측정: Docraft 다시 읽기는 건당 55~302초, Docraft를 부르지 않는 문서는 0~4초.
- 따라서 하네스 worker를 늘리면 **Docraft를 부르지 않는 문서**의 처리량은 늘지만, Docraft를 부르는 문서는 GPU 앞에서 줄만 길어진다.

## 권장안

**하네스 worker만 작업 대기열 길이 기준으로 자동 확장하고, GPU 쪽은 프로필 고정값을 유지한다.**

| 대상 | 방식 | 기준 | 범위(예: L40S 2장) |
|---|---|---|---|
| 하네스 worker | KEDA `ScaledObject` + Redis 대기열 길이 | 대기 작업이 worker 한 개당 8건을 넘으면 늘림 | 최소 2 ~ 최대 4 (동시 처리 4 → 최대 16슬롯) |
| 하네스 api | HPA(CPU 70%) 또는 고정 2 | CPU | 2 ~ 3 |
| Docraft backend | 고정 (GPU 용량에 맞춤) | — | 프로필값 |
| GPU 모델 서버·scanner | 고정 | — | 1 |

- **최대값 정하는 법**: 하네스 최대 슬롯이 Docraft가 동시에 감당하는 요청 수를 크게 넘지 않게 잡는다. 넘으면 Docraft 대기가 길어져 읽기 시간 예산(`remaining_ms`)을 넘기고 실패가 늘어난다.
- **KEDA가 없는 환경**: CPU 기준 HPA는 worker가 대부분 Docraft를 기다리느라 CPU가 낮아서 잘 안 맞는다. 이때는 자동 확장 대신 프로필 고정값을 부하 시험으로 맞추는 쪽이 낫다.

## 넣기 전에 확인할 제약

| 항목 | 내용 | 상태 |
|---|---|---|
| 고객 클러스터 | KEDA 설치 가능 여부(CRD·cluster-admin 권한), metrics-server 유무. 폐쇄망이면 KEDA 이미지를 번들에 넣어야 함 | 고객사 확인 필요 |
| 줄어들 때 작업 유실 | worker가 줄어들 때 실행 중인 작업(Docraft 대기 최대 300초)이 끊기지 않게 종료 유예 시간을 최대 작업 시간보다 길게(예: 600초). Celery는 이미 작업 완료 후 확인(`task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`)으로 설정돼 있어 끊긴 작업은 다시 대기열로 돌아감. 작업 시간 상한 soft 600초·hard 900초 | 설정 있음, 종료 유예만 추가 |
| 대기열 유실 처리 | `queued` 상태로 오래 머문 작업은 이미 `failed/queue_lost`로 옮기는 처리가 있음(`api/jobs.py`) | 있음 |
| DB 연결 수 | worker가 늘면 Postgres 연결이 늘어남. `max_connections` 여유 확인 | 확인 필요 |
| scanner | 자동 확장 대상에서 제외, 1개 고정 | 차트에 이미 1 고정 |
| 시험 환경 | AWS 개발 서버는 compose라 KEDA 시험 불가. k3s·kind 등 쿠버네티스 환경 필요 | 준비 필요 |

## 진행 순서

1. **부하 시험으로 용량 측정** — 프로필별로 Docraft 동시 요청 수와 처리 시간의 관계를 잰다. 이것으로 하네스 최대 슬롯을 정한다.
2. **고객 클러스터 확인** — KEDA 설치 가능 여부, metrics-server 유무.
3. **차트에 선택 기능으로 추가** — `worker.autoscaling.enabled`(기본 꺼짐), `minReplicas`·`maxReplicas`·대기열 기준값, 종료 유예 시간. 꺼져 있으면 지금과 같은 고정 개수.
4. **프로필에 기본값** — 사양별 최소·최대값.
5. **쿠버네티스 시험 환경에서 검증** — 늘어나고 줄어드는 동안 작업 유실 0건인지 확인.
6. **인스톨러 번들·설치 문서 반영**.

## 현재 대기열 제한 (참고)

- 제출 거절: `harness.jobs` 대기 메시지가 `QUEUE_MAX_PENDING`(기본 200) 이상이면 API가 503 + `Retry-After`로 거절. Helm values에는 노출돼 있지 않아 k8s에서는 기본 200 고정.
- 이 제한은 API 제출(`harness.jobs`)만 센다. 배치 스캐너 경로(`harness.documents`·`harness.batches`)에는 상한이 없다.
- 자동 확장 기준(대기열 길이)을 정할 때 이 상한보다 충분히 아래에서 늘어나도록 잡는다.

## 판단이 필요한 것

- 고객 업무량이 **몰리는 시간이 있는지**(일괄 접수 등). 고르게 들어오면 자동 확장 없이 고정값 조정만으로 충분하다.
- 고객 클러스터에 KEDA를 설치해도 되는지.
