---
okf_version: "0.2"
type: experiment
title: 진료비영수증 테스트셋 Docraft 항목표 오류 원인 분석 (요약)
description: 197건 Docraft 항목표 오류의 60%는 0원 행 미출력이고, 이를 빼면 Docraft·AO가 같은 수준이다. 출력 뒷부분 저하 가설은 기각, 표 구조 인식이 주원인. 상세는 상위 wiki
tags: [experiment, docraft, 진료비영수증, error-analysis, split-extract]
status: active
---

- 날짜: 2026-10-08
- 브랜치: `docs/receipt-error-cause` (코드 변경 없음, wiki만)
- 워크트리: `.worktrees/receipt-error-cause`
- 상세: 상위 wiki `2026-10-08-receipt-docraft-error-cause.md`
- 결과: 상위 `exp/e2e_call_test/out/split_extract/baseline-error-cause/`

## 요약

- 대상은 rowmajor 현행(`865ec20`)의 저장 응답이고, 새 호출은 0건이다.
- 정확도는 채점 그대로 86.93%(AO 76.34%)다. 금액이 전부 0인 정답 행의 미출력(오류 2,551칸, 59.5%)을 빼면 94.26%(AO 94.16%)다.
- 금액 있는 행의 누락은 표 앞쪽(첫 행 진찰료)에 더 많다. 숫자 오독은 82칸뿐이다. 그래서 키 수·출력 길이 때문에 품질이 떨어진다는 신호는 없다.
- 주원인은 표 구조 인식이다. 육안 검수 18건의 주원인은 다음과 같다.
  - 행 라벨 밀림 5건
  - 열 배치 오류 4건(서식 미판정)
  - 표 밖 영역 혼입 3건
  - 항목명 변형 3건
  - 이미지 품질 2건
  - 첫 행 누락 1건
- 다음 후보는 다음과 같다.
  - 표 영역 크롭·확대
  - 서식·열 배치 판정 보강(`table_layout`, 서식 미판정 33건이 문서당 오류 최다)
  - 행 골격 고정
  - 0원 행 채점 정책 결정
