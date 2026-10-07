---
type: decision
title: 진료비영수증 필드 키 상한액초과금으로 정정
description: 법정 서식 용어에 맞춰 Docraft 키 상환액초과금을 상한액초과금으로 바꾼 기록
tags: [docraft, 진료비영수증, 상한액초과금, 키]
status: active
---

# 진료비영수증 필드 키 상한액초과금으로 정정

- 날짜: 2026-10-07 / 브랜치: `fix/limit-excess-key` / 워크트리: `.worktrees/limit-excess-key`
- 원인: Docraft가 키를 오기 `상환액초과금`으로 정의해, 하네스의 `상한액초과금` 요청이 `verify: keys에 알 수 없는 key`로 무시됐다(AWS 2026-10-07 로그).
- 변경: `backend/doctypes.py` 필드 키, `backend/rulesets/rules.yaml` 라벨 키, 관련 테스트를 `상한액초과금`으로 통일.
- 입력 별칭: AO 원소 이름을 키로 되돌리는 별칭 장치(`doctypes.SCHEMA_ALIASES`는 인쇄 필드→파생 필드, `ALIASES`는 doc_type)가 없어 `상환액초과금` 입력 별칭은 넣지 않았다. 예전 키의 AO 값은 added 필드로 취급된다.
- `rulesets/shared/receipt_items.yaml`에는 이 키가 없어 영향 없음.
