---
okf_version: "0.2"
type: Implementation Log
title: "합계식으로 Judge 판정 보조와 정답셋 선별급여 표기 통일"
description: "Judge가 합계식에 안 맞는 읽기를 고르면 합계식 불일치가 줄어드는 AO·Docraft 값으로 되돌리는 verify._balance(rules.sum_errors)를 구현하고, 정답셋 라벨 7건의 선별급여 행 이름을 conform 경로로 통일한 기록"
tags: [backend, verify, rules, judge, labels, 진료비영수증]
generated: {by: claude-code/claude-opus-5-5, at: 2026-09-23}
status: active
---

# 합계식으로 Judge 판정 보조와 정답셋 선별급여 표기 통일

- 날짜: 2026-09-23
- 브랜치: `feat/sum-guard-labels`
- 워크트리: `.worktrees/sum-guard-labels`

## 배경

[receipt-issues-0923](2026-09-23-receipt-issues-0923.md)에서 남긴 두 가지를 처리했다.

1. 한방 영수증(흐린 팩스)에서 Judge가 AO의 맞는 값 대신 Docraft 오독을 골랐다. AO는 2,726·71,608·286,032·836,420, Docraft는 2,720·71,808·288,032·838,420이었다. 진료비총액 1,072,450 = 236,030 + 836,420이라 합계식으로는 AO가 맞았다.
2. 정답셋 라벨 7건이 선별급여 행을 원문 이름(`국민건강보험법제41조의4에따른요양급여`·`시행령별표2제4호의요양급여`)으로 두어 새 `item_name` 규칙과 어긋났다.

## 1. 합계식 판정 보조

- `rules.sum_errors(doc_type, fields)`는 합계식 불일치 수를 센다. 모든 유형에 합계 필드 간 식(`FIELD_SUMS`)을 보고, 진료비영수증이면 합계 행·열별 합·합계 필드 식(`_sum_checks`의 `sum_mismatch`)을 더 본다. `check`와 같은 계산을 쓴다.
- `verify._balance`: 모든 key의 판정을 먼저 모은 뒤 불일치 수를 센다. 불일치가 있으면 key마다(표 먼저) AO 값과 Docraft 값으로 바꿔 보고, 불일치가 **줄 때만** 그 값을 택한다. `source`는 그쪽(ao/docraft)이 되고 `reason`에 전후 건수를 남긴다.
- 빈 값(None·빈 문자열·빈 표)으로는 바꾸지 않는다. 검사할 식이 사라져 불일치가 준 것처럼 보이기 때문이다. 기존 테스트(AO에 없던 표를 Docraft 표로 채우는 경우)가 이 허점을 잡아냈다.
- `verify.run`은 판정을 key별로 먼저 모두 정한 뒤(`chosen`) 주석을 붙이도록 순서만 바꿨다.

### 결과

| 대상 | 결과 |
|---|---|
| 이슈 260923 한방 문서(스크린샷 기반 AO, Judge 포함) | 항목 표가 AO 값(2,726·71,608·286,032·836,420)으로 되돌아왔다 |
| 같은 문서의 공단부담총액 | AO 입력에 없는 필드라 Docraft 값(838,420)이 남는다. 빈 값으로는 되돌리지 않으므로 `sum_mismatch` 경고로 드러난다 |
| gold 4건 final 단계 | 합계 보조가 판정을 바꾼 곳은 0건이다(`합계식:` 사유 0). main과의 final 차이(영수증 227→231)는 재추출·Judge 흔들림이다 |
| 테스트 | 418 passed(합계 되돌림, 빈 값 유지, `sum_errors` 신규 2개) |

## 2. 라벨 선별급여 표기 통일

- 두 라벨 루트(`data/verify/labels`, `data/verify/accuracy-20260922/labels`)를 먼저 드라이런했다. `verify_label.conform`(= `rules.derive`)으로 바뀌는 곳은 영수증 7건의 선별급여 행 이름뿐이었고, 다른 유형·필드는 바뀌지 않았다.
- 백업 `data/verify/labels-backup-20260923-before-seonbyeol.tar.gz`를 만든 뒤 `scripts/verify_label.py --conform-only`(두 번째 루트는 `--labels-root`)로 적용했다. 3건 + 4건이다.
- 76건 `rules` 단계(캐시 `accuracy-20260922/pipeline-cache`)의 새 기준점은 진단서 236/260, 소견서 262/310, 진료비영수증 **4261**/4479(strict 2927, fp 12), 세부내역서 3940/4189다. 영수증은 라벨 변경 전 4259에서 올랐다.

## 남은 것

- AO 항목 프롬프트의 `→ 신별급여` 오타 수정(AO 쪽)
- 합계 보조는 AO·Docraft 두 읽기 중에서만 고른다. 둘 다 틀렸거나 한쪽이 비어 있으면 경고로만 남는다.
