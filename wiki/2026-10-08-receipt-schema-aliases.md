---
type: change
title: 영수증 항목 별칭을 고객 후처리 스키마 근거로 보강
description: 공유 receipt_items.yaml에 고객 후처리 스키마(keywordInfo)와 법정 서식을 근거로 한 별칭을 전체 일치로만 추가하고, 정액수가 별칭이 장기요양까지 삼키던 규칙을 좁혔다. 기존 표준 항목과 충돌하는 4건은 결정 대기
tags: [harness, docraft, 진료비영수증, 항목명, receipt_items, alias]
status: active
---

날짜: 2026-10-08
브랜치: harness-v2 `fix/receipt-form-aliases`(dev 병합 후 삭제), Docraft `fix/receipt-alias-sync-1008`(dev 병합 후 삭제)
워크트리: harness-v2 `.worktrees/receipt-form-aliases`, Docraft `.worktrees/receipt-alias-sync-1008`(모두 정리)

## 배경과 결정

- [행 골격 커버리지](2026-10-08-receipt-row-skeleton-coverage.md, 상위 wiki)에서 인쇄 항목명이 표준 항목으로 이어지지 않아 행을 놓쳤다. 구 서식 표기나 병원별 표기 때문이다.
- 문제 유형: 서식 개정판·병원별 표기 변형이 표준 항목으로 이어지지 않는다.
- 별칭은 출처가 있는 이름만 넣는다. 튜닝셋에서 관찰한 실패는 출처의 빈 곳을 찾는 단서로만 썼다.
- 출처는 두 가지다.
  - 법정 서식: 별지 제6·7·12호(2024-07-18). 여기서 `제증명수수료`를 추가했다(`7015cc5`).
  - 고객 후처리 스키마: 2026-10-08 사용자가 출처로 인정했다. `Docraft/refs/postprocess_schema_example/20260828_v1.1/schema/미래에셋생명_고도화/진료비영수증/진료비영수증_main.json`의 `keywordInfo`에서 `---오탈자---`·`---잘림---` 앞 구간만 썼다.
- [10-07 인쇄 표기 정책](2026-10-07-receipt-item-print-name.md, 상위 wiki)을 따른다.
  - 비교는 기호를 뗀 키로 하고, 반환은 인쇄 표기 표준명으로 한다.
  - 별칭은 전체 일치(`$`)로만 넣어 앞부분 일치가 다른 항목을 삼키지 않게 했다.

## 변경

- 별칭 추가(예):
  - `진찰비`→진찰료
  - `포괄수가`·`포괄수가제`→질병군포괄수가
  - `종합검진`·`검진료`→건강검진료
  - `보조기기`·`보장구`→보조기
  - `정액(완화)`→정액수가(완화의료)
  - `별표2제4호의요양급여`→선별급여
  - `기타및보정금액`→끝수처리조정금액
  - 투약·주사 행위/약품 오독(생위·조세료·주시·역품) 등. 전체 목록은 커밋 `d6ef5c9` diff에 있다.
- 표준 항목 추가: 건강검진료, 보조기, 수혈료(스키마 키).
- 기존 규칙 수정:
  - `^정액수가.*요양`이 `정액수가(장기요양)`까지 정액수가(요양병원)으로 삼켰다. 바로 이어질 때만 일치하도록 좁혔고, 완화 쪽도 같은 방식으로 좁혔다.
  - `보철·교정료·기타`→보철교정료. 스키마 근거로 기대값을 바꿨다.
- 제외: `검사`→검사료는 Docraft "짧은 이름 유지" 결정과 충돌해 뺐다(`090ad4b`).

## 결정 대기 (기존 yaml과 스키마가 충돌해 넣지 않음)

| 항목 | yaml | 고객 스키마 |
|---|---|---|
| 포괄수가진료비 | 별도 표준 항목 | 질병군포괄수가의 별칭(행 골격 튜닝셋에서 25건 놓친 원인) |
| 응급의료관리료·응급의학관리료·응급관리료 | 표준 항목 셋 | `응급의학관리료` 하나 |
| 시술및처치료 | 표준 항목 | 키가 `시술및처치료(한방)` |
| 선별급여및기타·선별급여항목 | 인쇄 표기 유지(10-07 결정) | 선별급여의 별칭 |

- 보류: 스키마 키이지만 yaml 표준 항목이 아닌 것이다. 의료질평가료·간병료·구급차료·예방접종료·탕전료·기준병실료 등.
- 스키마 안에서 서로 모순되거나 모호한 것도 넣지 않았다. `MRI/PET진단료`, `정밀혈액검사`, `영양제`가 해당한다.

## 검증

- harness 영향 테스트(`test_value_fix`·`test_coverage_rules`·`test_parse_rebuild`·`test_schema_declarations`): 468 passed. 별칭 변형 약 35건과 삼키면 안 되는 이웃 약 17건을 추가했다.
- harness 빠른 회귀(slow 제외, xdist 없음): 2281 passed, 21 failed. 21건은 입퇴원확인서 샘플 문제이고, 변경 전 dev에서도 같다.
- Docraft `test_rules`·`test_rules_receipt_accuracy`·`test_typed_evidence`: 423 passed(`--noconftest`).
- 사본 일치: harness와 Docraft의 `receipt_items.yaml`이 `cmp`로 동일하다.

## 커밋

- harness dev:
  - `7015cc5` 법정 서식
  - `d6ef5c9` 고객 스키마 → 병합 `235e07f`
  - `090ad4b` 검사 제외 → 병합 `e629c51`
- Docraft dev: `59a10a3` → 병합 `fe2e6ae`
- push 안 함. installer의 Docraft gitlink는 다음 일괄 push 때 갱신한다.
