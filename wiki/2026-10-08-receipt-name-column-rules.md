---
type: change
title: 영수증 항목명 별칭 재선별·위치 제약 이름 맞춤·열 되돌림 근거 제한
description: 고객 스키마 별칭을 되돌리고 OCR 오독·잘림 별칭만 다시 넣었다. item_order를 공유 표로 옮기고, Docraft에 위치로 제약한 항목명 맞춤과 열 되돌림 근거 제한을 넣었다. 저장 응답 재생 raw 채점에서 정답지 30건이 96.44에서 97.37%로 올랐다
tags: [docraft, harness, 진료비영수증, 항목명, receipt_items, item_order, rules]
status: active
---

날짜: 2026-10-08
브랜치:
- harness-v2 `fix/receipt-alias-revert`(dev `9bfced1` 병합 후 삭제)
- Docraft `fix/receipt-position-name`·`fix/receipt-column-realign` 등(dev `475a114`까지 병합 후 삭제)

워크트리: 모두 정리했다.
관련: [정답지 30건 오류 원인](2026-10-08-receipt-g30-error-cause.md), [별칭 보강(되돌림)](2026-10-08-receipt-schema-aliases.md)

## 측정 방법

- `exp/e2e_call_test/name_snap_measure.py`로 `verify.read` 저장 응답을 커밋별로 재생했다. 호출은 0건이다.
- **raw 채점**: 정답 이름을 그대로 두고 채점한다. 정답 이름을 표준화하는 canon 채점은 인쇄 이름 회귀를 가리므로 판정 근거로 쓰지 않는다.
- 같은 커밋을 재생하면 결과가 바이트 단위로 같다.
- 결과: `exp/e2e_call_test/out/split_extract/name-snap/`(`variants/`, `position-name/`, `column-realign/`)

| 셋 | 865ec20 | 1·2 별칭 재선별·item_order(9c5bfb4) | 3 위치 제약 이름(ab2269e) | 4 열 되돌림·묶음 제목(475a114) |
|---|---|---|---|---|
| 정답지 30 (사람 검수) | 96.44 | 96.73 | 97.30 | **97.37** |
| T tune | 86.82 | 87.06 | 88.07 | **88.12** |
| T check | 87.04 | 87.08 | 87.80 | **87.80** |

## 1. 고객 스키마 별칭 되돌림과 오독·잘림 별칭 재선별 (harness `142a811`)

- `d6ef5c9`·`090ad4b`·`feab341`을 되돌렸다. 되돌린 상태는 865ec20과 수치가 같다. `7015cc5`(제증명수수료, 법정 서식)는 남겼다.
- 다시 넣은 것은 OCR 오독·잘림뿐이고, 모두 전체 일치다.
  - `마취`, `치료재료`·`시료제료대`·`재료대`, `방사(선)치료`, `CT/MRI/PET/초음파진단`(료 잘림)
  - 입환료, 검료, `[영명]상진단`, `상급[병면]실`, 투약·주사 오독(행↔생 등)
- 정액수가 요양 별칭: `^정액수가(?!.*장기요양).*요양`. 장기요양은 다른 인쇄 이름이라 삼키지 않고, `정액수가일반요양병원`은 요양병원으로 맞춘다.
- 뺀 것:
  - 인쇄 변형 이름 전부(포괄수가·응급·병실차액·종합검진 등)
  - 표준 항목 추가분(보조기·건강검진료·수혈료)
  - 선별급여 법령 조각: check 1행이 나빠졌다.

## 2. item_order 공유 (harness `09b29be`, Docraft `7e7a5e5`)

- `item_order`를 `schema.yaml`에서 공유 `receipt_items.yaml`로 옮겼다. harness `parser_fill`은 `SHARED["item_order"]`를 읽는다.
- 두 저장소의 yaml은 `cmp`로 일치한다.

## 3. 위치로 제약한 항목명 맞춤 (Docraft `e8d0e61`·`e47c4fb`)

- 문제 유형: 인쇄 항목명이 두 글자 이상 오독되면 표준 항목으로 이어지지 않는다. 기존 `_misread`는 한 글자 오독만 고친다.
- 동작: `_receipt_table` 끝에서 표준 항목이 아닌 이름의 행을 본다.
  - 후보: 위·아래 가장 가까운 `ITEM_ORDER` 행 사이에 올 수 있고, 표에 아직 없는 항목만 둔다.
  - 이 후보로 `_misread(name, near)`를 부른다. 편집거리는 `table_layout._distance`에 `limit` 인자를 더해 재사용했다.
- 조건:
  - 음절 수 차이 ≤1. 길이가 달라진 이름은 인쇄된 다른 이름으로 본다.
  - 유사도 기준 0.55. tune에서만 정했고, 바꾼 이름의 정밀도 ≥0.9를 조건으로 했다.
  - 1·2등 차이 ≥0.1
  - 끝 글자만 다른 후보는 바꾸지 않는다.
  - 비교는 `item()`으로 정규화한 이름으로 한다.
- 바꾼 행 정확도: G 4/5(틀린 1건은 정답 오타), tune 24/26, check 18/19.
- 남은 오교체 3유형: `초음파검사료`, `DITI진단료`, `입원료식대`. 길이가 같은 정상 다른 이름이다. 막을 일반 규칙의 근거가 약해 `xfail(strict)` 테스트로 남겼다.

## 4. 열 되돌림 근거 제한·묶음 제목 머리글 대안 (Docraft `5c98212`)

- A. 문제 유형: 후처리 열 되돌림(`_moves`)이 파서 표의 열 배정만 믿고 모델의 값 있는 칸을 덮어쓴다(한방 소계 열 서식).
  - 수정: 목표 칸이 비었거나, 그 칸 값도 다른 칸으로 옮겨 갈 때(통째 밀림·맞바뀜)만 옮긴다.
  - 같은 유형인 `_column_moves`의 파서 표 밖 경로는 이미 빈 칸만 옮겨서 문제가 없다.
- B. 문제 유형: 서식 미판정 문서에서 '항목' 머리글이 안 보이면 `_headers`가 빈 값을 낸다. 그러면 묶음 제목 `급여`·`비급여` 열을 비우지 못한다.
  - 수정: 마지막 대안으로 `급여`·`비급여` 칸이 있는 행부터 머리글을 본다. 열 배치(프롬프트)는 바꾸지 않았다.

## 테스트

- harness 영향 테스트 449 passed.
- harness 빠른 회귀 2267 passed, 21 failed. 실패 21건은 기준선과 목록이 같다(샘플 데이터).
- Docraft `test_rules`·`test_rules_receipt_accuracy` 423 passed, 3 xfailed. `test_rowmajor`·`test_pagewise` 168 passed.
- Docraft의 DB 필요 테스트는 Postgres가 없어 돌리지 못했다.

## 남은 것

- push와 harness-installer 반영. push 전 전체 회귀가 필요하다.
- T 정답에서 정액수가 장기요양 표기가 일관되지 않다(정답지 검수 필요).
- `시행처지료`는 한방 항목이 `item_order`에 없어 맞춤 대상이 아니다.
