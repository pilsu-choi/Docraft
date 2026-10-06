---
type: worklog
title: AWS 통합 배포 1006a — harness 4438155·Docraft 134f385 최신화
description: 사용자 지시로 harness origin/dev 4438155(규칙셋 2026.09.22)와 Docraft mlife/dev 134f385를 AWS에 배포했다. 테스트 호출은 하지 않았다.
tags: [aws, 배포, harness, docraft]
status: active
---

- 날짜: 2026-10-06 (15:0x~15:1x KST)
- 배포 실행: mirae-assets-fd. 지시를 받을 때 담당 6c가 없어서 대행했고, 도중에 새 담당 3b가 이번 건은 fd가 끝까지 하도록 확인했다.
- 워크트리: harness-v2 `.worktrees/aws-deploy-20261006-aws`(origin/dev 기준 detached), Docraft `.worktrees/aws-deploy-20261006-aws`(mlife/dev 기준 detached). 배포 후 둘 다 정리했다.

## 진행 확인(GO/HOLD)

떠 있던 세션 4개에 물어 모두 GO를 받았다. 이번 배포에 함께 넣을 커밋은 없었다.

| 세션 | 회신 | 참고 |
|---|---|---|
| mirae-assets-e0 | GO | 합성 생성기만 작업했다 |
| mirae-assets-04 | GO | label-viewer를 dev c5d96d5로 재배포했다(:8765, 볼륨 `label-viewer_*`). 건드리지 말 것 |
| synthetics-56 | GO | Studio 동시 부하는 분석만 했다 |
| generator-63 | GO | medical-studio를 배포했다(:8768, `/mnt/data/medical-studio`). 건드리지 말 것 |

## 배포 내용

| 저장소 | 이전 | 이번 | 비고 |
|---|---|---|---|
| Docraft | `298570b` (10/02) | `134f385` (mlife/dev = origin/dev) | 커밋 89개 |
| harness-v2 | `cd1461a`, 규칙셋 2026.09.20 | origin/dev `4438155`, 규칙셋 2026.09.22 | 로컬 dev `5319b38`은 문서만 추가된 상태라 push된 커밋으로 배포했다 |

`.env.aws`에 새로 생긴 키(Docraft `AI_REASONING`·`TABLE_EXTRACT`·`TABLE_RECHECK_RATIO`·`HARNESS_DATABASE_URL`, harness `DOCRAFT_MAX_CONCURRENCY`·`VLLM_EMBEDDING_GPU_*`)는 서버 값에 넣지 않았다. 따라서 코드 기본값(rowmajor 등)으로 동작한다.

## 확인 결과

- Docraft: `/api/health` ok, `verify_inflight` 0, OCR ready, VLM `qwen/qwen3-vl-32b-instruct`(openrouter). 서버 `DEPLOYED`는 `revision=134f385 time=2026-10-06T06:08:49Z`이고 `deploy.lock`은 풀려 있다(flock 확인).
- harness: `/healthz` ok. 컨테이너 안의 `get_settings().rule_set_version`은 `2026.09.22`. api·worker 2개·scanner·postgres를 재기동했고, vllm-embedding·clickhouse·redis는 그대로 두었다.
- label-viewer와 medical-studio는 건드리지 않았고 둘 다 healthy다.
- 테스트 호출: 0건. 59건 회귀가 필요한지는 배포 담당 3b가 판단하고 취합해서 1회 돌린다.

## 관련 문서

- [AWS 배포 담당 인계 — 6c에서 3b로](2026-10-06-aws-deploy-owner-3b.md)
- 직전 배포: [AWS 통합 배포 1002j](2026-10-02-aws-integrated-deploy-1002j.md)
