---
type: decision
title: 진료비영수증 항목명 원본 인쇄 표기 유지(Docraft 요약)
description: Docraft rules.py 항목명 정규화가 괄호·이름 접미를 잃지 않도록 인쇄 표기 표준명을 반환하게 한 요약
tags: [docraft, 진료비영수증, 항목명, receipt_items]
status: active
---

날짜: 2026-10-07
브랜치: Docraft `fix/receipt-item-print-name` → dev `9ced432` (수정 `9b63fc7`, 미push)
워크트리: `Docraft/.worktrees/receipt-item-print-name`

상세·근거·결정은 상위 wiki [2026-10-07-receipt-item-print-name.md](../../wiki/2026-10-07-receipt-item-print-name.md)(harness 쪽은 `harness-v2/wiki` 동기화본)에 있다.

- 결정: 항목명은 원본 인쇄 표기 유지(`한약(첩약)`, `선별급여및기타`). 2026-09-24 "기호를 뗀다" 결정 중 괄호 부분 변경.
- 변경: 공유 `receipt_items.yaml`(harness와 바이트 동일) 표준명·별칭 수정. `rules.py`에 `_plain`, `_PRINTED` 추가, `item()`/`_misread`가 기호 뗀 키로 비교하고 인쇄 표기 표준명 반환, `_item_names` 정규식에 괄호 허용.
- 테스트: `tests/test_rules.py` 398 passed(`--noconftest`), `test_item_names_flags_misprints_but_keeps_printed_standard_names` 추가. DB 의존 테스트 미실행.
- 후속: 정답지 라벨(`한약첩약`·`선별급여`) 수정 필요.
