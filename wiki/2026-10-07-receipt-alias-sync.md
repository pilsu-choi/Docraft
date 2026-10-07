---
type: change
title: 영수증 선별급여 법령 문구 별칭 동기화
description: 하네스와 함께 쓰는 receipt_items.yaml 의 선별급여 별칭을 법령 문구 오독 변형까지 덮도록 넓힌 하네스 변경을 Docraft 사본에 그대로 반영
tags: [docraft, harness, 진료비영수증, item_aliases, sync]
status: active
---

날짜: 2026-10-07
브랜치: `fix/receipt-alias-sync` (dev `88f1956` 기준)
워크트리: `.worktrees/receipt-alias-sync`
상세: 상위 `mirae-assets/wiki/2026-10-07-receipt-parse-row-recognition.md` (harness-v2 dev `fcc2ff3`)

## 요약

- `backend/rulesets/shared/receipt_items.yaml` 은 하네스 `src/mlife_harness/rulesets/shared/receipt_items.yaml` 과 byte-identical 이어야 한다(installer `cmp`).
- 바뀐 것은 `item_aliases` 의 선별급여 별칭 한 줄과 주석: 법령 근거 문구(「국민건강보험법」 제41조의4에 따른 요양급여)가 오독으로 앞부분이 달라져도(제4조의4·제 빠짐·시행법령표) 고정 조각으로 선별급여로 본다. 40자 이하 이름만.
- `선별급여및기타`·`정액수가(요양병원)`·`선별급여항목` 은 그대로(2026-10-07 인쇄 표기 결정 유지).

## 검증

- 두 파일 `cmp` 동일.
- `backend.rules._alias`: 법령 문구 변형 → 선별급여, `선별급여및기타`·`정액수가(요양병원)`·`진찰료`·40자 초과 문구 → 그대로.
- `pytest --noconftest tests/test_rules.py` 398 passed (dev 와 같음). DB 가 필요한 나머지는 로컬 Postgres(5433)가 없어 돌리지 않았다.
