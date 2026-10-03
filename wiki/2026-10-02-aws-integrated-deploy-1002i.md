---
type: worklog
title: AWS 통합 배포 1002i — Docraft /api/read 지연·408 대응
description: Docraft 298570b와 READ_MAX_MS=280000을 배포하고 정답지 59건(5491 golden 현재본)을 1회 돌려 같은 정답으로 다시 채점한 r8과 비교
tags: [aws, 배포, docraft, 성능, 테스트]
status: active
---

- 날짜: 2026-10-02 (취합 13:52~14:0x, 전원 회신으로 조기 진행)
- 배포 담당: mirae-assets-6c
- 워크트리: Docraft `.worktrees/deploy-1002i` (mlife/dev 기준 detached, 배포 후 정리)
- 취합 기록: `e2e/out/aws-deploy-1002i/requests.md`

## 배포 내용

| 저장소 | 커밋 | 요청 세션 | 내용 |
|---|---|---|---|
| Docraft | mlife/dev `298570b` (`cba1b3b` 포함) | 6f | 같은 페이지 OCR·표 교정을 필드·표 요청이 공유, 표 교정 병렬·큰 표 분할, PaddleOCR 동시성 세마포어(2), 시한 근접 시 원격 단계 생략, 벽시계 시한, 단계별 시간 로그 |
| harness-v2 | `f9d417f` 유지 | - | - |

- Docraft `deploy/aws/.env.aws`에 `READ_MAX_MS=280000`을 새로 넣었다(예시 파일에만 주석으로 있었음). 하네스 `DOCRAFT_TIMEOUT`(300초)보다 짧다. 이 파일은 서버 `.env`로 복사돼 backend `env_file`로 읽힌다.
- harness-installer `4a490a1`(Docraft 고정 커밋 갱신)은 AWS 배포 대상이 아니라 기록만 했다.
- Docraft 서버 로그: `/mnt/data/docraft/data/logs/docraft.log` (단계별 시간은 6f가 집계).

## 테스트 (정답지 59건 1회, 실패 0) — `e2e/out/golden1002-aws-r9/`

- 정답: label_veiwer 번들 5491 golden 현재본(b2 권고 — 급여구분 열추출 통일·요약 행 0→빈칸 등 포함). r8을 같은 정답으로 다시 채점해 비교 기준으로 삼았다(AWS 호출 없음).

| | r8 (같은 정답) | r9 |
|---|---|---|
| 세부내역서 | 99.38% | 99.38% |
| 진료비영수증 | 99.41% | 99.41% |
| 전체 | 99.40% | **99.40%** |

| Docraft 요청 (34건) | r8 | r9 |
|---|---|---|
| 실패(408·timeout) | 3 | **0** |
| 소요 중앙값 | 129초 | **86초** |
| p90 | 185초 | **144초** |
| 최대 | 278초 | **152초** |

- **개선 9칸 — 전부 소계포함_SA2019123045314**: 표 요청이 처음으로 성공해 선별급여 행(r15, 8칸)과 끝수처리조정금액 행(r17)이 복원됐다.
- **악화 1칸**: SA2019123157847_201912311546400b 납부할금액 정답 0 → 11000.
- 요양기관종류 28/29 유지(남은 1건 SA2019123039576).
