---
type: Implementation
title: "하네스 표본 7종 e2e에서 드러난 /api/verify 수정 — 정의 밖 key, 합계식 표 교체의 항목명, 빈 AO 재추출 요청"
description: "harness-v2 표본 7종 210장 e2e(AO 7종 워크플로우 → 하네스 → Docraft)에서 나온 /api/verify 결함 셋과 검토 후 보완. 진단서 계열 사고발생일자 KeyError(502), _balance 가 Docraft 항목명까지 가져오던 문제, 하네스 서식 재분류가 보내는 값 없는 AO 요청의 Judge 생략"
tags: [verify, e2e, harness, balance, judge]
generated: {by: claude-code, at: 2026-09-24}
status: stable
---

# 하네스 표본 7종 e2e에서 드러난 /api/verify 수정

- 날짜: 2026-09-24
- 브랜치: `fix/0924-verify-e2e-sample` (`b68da80`, `df5af1c`), main 미병합, AWS 배포 `df5af1c`
- 짝 문서: harness-v2 `wiki/2026-09-24-표본-7종-e2e-서식재분류-정규화.md`

## 1. 정의 밖 key 가 Judge 에서 corrected 로 오면 502

AO 7종 워크플로우의 진단서 계열은 `진단.사고발생일자`를 낸다. Docraft 진단서 정의에는 없는 key 라 Docraft 값이
없어 늘 다툼이 됐고, Judge 가 `corrected` 를 주면 `_decide` 의 `rules.apply(...)[key]` 가 `KeyError` → 502 였다
(표본 9건 실패, 대부분 입퇴원확인서).

- `b68da80`: `rules.apply(...).get(key, value)` 로 막았다.
- `df5af1c`: 정의 밖 key 는 다툼·Judge 에 보내지 않고 AO 값을 `source=unknown`(`OUT_OF_SPEC`)으로 둔다. Judge 가
  `docraft` 를 고르면 AO 값이 `None` 으로 지워질 수 있었다. 유형 정의가 빈 경우(테스트 대역)는 이 판정을 하지 않는다.

## 2. 합계식으로 Docraft 표를 택하면 Docraft 항목명이 따라온다

`_balance` 는 합계식이 더 맞는 쪽 표를 통째로 택한다. Docraft 가 `투약및조제료_약품비`를 `조제료약품비`,
`주사료_약품비`를 `약품비`로 적은 영수증(KJM02605)에서 행이 통째로 틀렸다. `_with_ao_names` 로 AO 행과 짝지어진
행의 이름 열(`ROW_KEYS` 중 유형 정의 안 text 열 — 영수증 `항목`)은 AO 값으로 두고 금액만 바꾼다.

검토에서 보완(`df5af1c`):
- 이름을 옮기는 열을 유형 정의 안으로 한정(영수증에 `EDI코드`·`시작일자`가 끼지 않게).
- 합계·소계 행은 건너뛴다 — 본문 행과 이름을 주고받으면 `is_total` 이 바뀌어 합계식이 틀어진다.
- 순서로만 이어진 짝(fallback)은 한쪽 이름이 다른 쪽에 들어 있을 때만(`조제료약품비` ⊂ `투약및조제료약품비`)
  같은 항목으로 본다. Docraft 가 행을 빠뜨리고 다른 행을 더하면(`기타약제` ↔ `진찰료`) 옮기지 않는다.

## 3. 값 없는 AO 요청 — 하네스 서식 재분류의 재추출

하네스는 AO 가 서식을 잘못 분류하면(세부내역서 → 진료비영수증) `doc_type` 을 지정하고 `extracted_*` 를 비운 AO 를
보내 Docraft 가 그 서식 스키마로 전체를 추출하게 한다. 이때 모든 칸이 AO 빈 값 vs Docraft 값 다툼이 되어 Judge 가
원소를 빠뜨리면 추출값이 버려졌고, 긴 표를 통째로 되풀이해 시간·절단 위험이 컸다. AO 값이 하나도 없으면 Judge 없이
Docraft 추출값을 `source=docraft`(`BLANK_AO`)로 쓴다(`df5af1c`). 표본에서 이 경로로 다시 추출한 7건: 칸 정확도
17.9% → 89.7%(하네스 최종).

## 검증

- 새 테스트 7개(이름 유지 짝 조건·합계 행·정의 밖 열·정의 밖 key·빈 AO), 전체 484 passed(임시 pgvector DB).
- 표본 86건 전체 검증 재측정: 실패 0(수정 전 9건 502).

## 남은 것

- 문서 전체 검증(hint_paths 없음)의 효과는 표본에서 +0.2%p — 진료비영수증은 열 밀림 교정(DRG 영수증 본인부담금 →
  전액본인부담 11행)이 오히려 틀렸다. 원인 미분석.
- 입퇴원확인서·수술확인서 폴백 38건에서 Docraft 가 대부분 AO 와 같게 읽어 값이 거의 바뀌지 않았다.
