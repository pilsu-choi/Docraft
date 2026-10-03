---
type: experiment
title: AWS 통합 배포(하네스 6d30de5·Docraft 79a11bd)와 정답지 59건 1회 테스트
description: 배포 담당 세션(9f)이 떠 있는 세션의 요청을 모아 하네스·Docraft 를 한 번에 AWS 에 배포하고, 정답지 59건을 현재 검수본 기준으로 한 번 돌려 채점한 결과와 인계 내용
tags: [harness, docraft, aws, golden-set, deploy, benchmark]
status: active
---

날짜: 2026-10-02  
브랜치: 없음 — 배포용 분리 HEAD `harness-v2/.worktrees/aws-deploy-1002b`(origin/dev `6d30de5`), `Docraft/.worktrees/aws-deploy-1002b`(origin/dev `79a11bd`), 배포 후 정리  
워크트리: 위 두 개(정리함)

## 취합
- 취합 안내 09:21 KST(마감 09:51), 전원 회신·GO 확인 후 09:2x 배포. 기록 `e2e/out/aws-deploy-1002b/requests.md`.
- 요청 세션: mirae-assets-6f(하네스 1bd2c3c·Docraft 79a11bd, 확인 문서 12종), harness-v2-f1(요양기관종류 b·d, 6d30de5), harness-v2-37(취합 이관·a3), mirae-assets-f3(서버 테스트 종료, 오케스트레이터 e2e 는 d8a4a62 에서 완료돼 취소), 6c(없음).

## 배포
| 저장소 | 커밋 | 비고 |
|---|---|---|
| harness-v2 | origin/dev `6d30de5` | 서버 보고 규칙셋 2026.09.15(`.env.aws` `RULE_SET_VERSION` 같이 올림) |
| Docraft | origin/dev `79a11bd` | 요청한 `88087b5`와는 AGENTS.md 만 다르다 — 서버 DEPLOYED `revision=79a11bd` |

배포: 각 워크트리에서 `deploy/aws/deploy.sh`(Docraft → 하네스 순). 하네스 워크트리에는 `.env.aws` 복사와 `dist` 심볼릭 링크(모델 체크섬)가 필요하다.

## 테스트 (1회, 59건)
- 입력: `e2e/out/golden0930-aws`의 원본·AO 추출(`aiocr.adapted.json`), **정답은 label_veiwer 번들 `20260930-1444-5491` golden 현재본**(10/02 09:00까지 수정된 11건 반영).
- 실행: `cd e2e && python3 collect_harness.py --sample out/golden1002-aws-r3 --inflight 6` → `../Docraft/.venv/bin/python grade_samples.py --sample out/golden1002-aws-r3 --out out/golden1002-aws-r3/채점.xlsx`
- 비교 기준: 10/02 오전 dba1755 결과(`out/golden1002-aws`)를 같은 정답으로 다시 채점한 `out/golden1002-aws-base`(AWS 호출 없음).
- 결과: 59/59 완료, 실패·타임아웃 0. 등급 unresolved 33·repaired 22·pass 4. Docraft 호출 33건. 처리 시간 중앙값 80초·최대 201초.

| | 하네스 dba1755 | 하네스 6d30de5 | AO |
|---|---|---|---|
| 전체 | 96.46% | **97.27%** | 97.33% |
| `급여구분`=`열추출` 제외 | 98.28% | **99.10%** | 97.28% |

- 판정 변화(dba1755 → 6d30de5): 오검출→일치 61, 누락→일치 41, 칸 새로 생김→일치 40, 불일치→일치 21 / 일치→불일치 4, 일치→누락 3, 불일치→누락 2.
- 새로 틀린 7칸
  - `SA2019123157847_…390i`·`…400b` 요양기관종류: 새 Docraft 가 체크 표시 `V`만 돌려줘(quality SUSPICIOUS) 분기 9 로 AO 값(의원급)이 남았다. dba1755 때 Docraft 는 `병원급`을 읽었다.
  - `2020010684177`(정답 `의원`)·`SA2019123157794`(정답 `병원`) 요양기관종류: 하네스가 표준 값(`의원급·보건기관`·`병원급`)으로 바꿨는데 정답지는 원문 표기 — 정답지 표기 정책 차이.
  - `2303314855` 10행 투여량·횟수·일수: `0` → 빈 값(정답 `0`).
- 요양기관종류·요청 문서별 상세: `e2e/out/golden1002-aws-r3/비교요약.txt`.

## 인계
- 다음 배포부터 담당은 mirae-assets-6c(사용자 지시). 서버 현재: 하네스 `6d30de5`(2026.09.15), Docraft `79a11bd`. 서버 호스트에 f3 의 콜백 수신기(`/tmp/cbrecv-f3.py`, :18999)와 오케스트레이터 스택(aiocr-orchestrator, aiocr-e2e-oracle)이 떠 있다.
