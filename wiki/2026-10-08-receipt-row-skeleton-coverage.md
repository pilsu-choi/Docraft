---
okf_version: "0.2"
type: experiment
title: 진료비영수증 항목표 OCR 행 골격 커버리지 (요약)
description: OCR만으로 만든 인쇄 항목 행 목록의 정답 행 재현율을 쟀다. 튜닝 98건에서 인쇄만 78.0%, 서식 순서 보충을 켜면 93.4%, 현행 A는 90.3%다. 고정 골격은 기각하고 행 후보 목록 방식으로 호출 실험을 이어간다. 상세는 상위 wiki
tags: [experiment, docraft, 진료비영수증, row-skeleton, split-extract]
status: active
---

- 날짜: 2026-10-08
- 브랜치: `docs/receipt-skeleton` (코드 변경 없음, wiki만)
- 워크트리: `.worktrees/receipt-skeleton`
- 상세: 상위 wiki `2026-10-08-receipt-row-skeleton-coverage.md`
- 결과: 상위 `exp/e2e_call_test/out/split_extract/skeleton-coverage/`

## 요약

| 지표 | 인쇄만 | +보충 | 현행 A |
|---|---|---|---|
| 재현율 | 77.95% | 93.44% | 90.34% |
| 정밀도 | 87.16% | 80.61% | 93.49% |

- 행 순서 일치는 99.5%다. 약점은 이름(별칭 누락, 두 줄 칸 하위 행)과 t74의 깨진 parse다.
- 별칭은 `rulesets/shared/receipt_items.yaml`에 보강한다(10-07 인쇄 표기 정책에 따름).
- 다음 단계: 확인셋 99건 재확인 → 행 후보 프롬프트 튜닝셋 호출 실험. 골격이 약하면(인쇄 표준 행 20 미만, 합계 행 미검출) 현행 rowmajor로 대체한다.
