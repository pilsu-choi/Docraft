---
type: Implementation Log
title: "룰 레지스트리·반복 교정·rulesets YAML 구현 (설계안 1~3단계)"
description: "rules.py 검사·교정 18개를 룰 레지스트리로 옮기고, 검증→교정→재검증 반복 실행기와 룰별 trace, review 표시, 룰 데이터 표 YAML 분리를 구현한 기록. 1·3단계는 동작 변화 0을 대조로 증명"
tags: [backend, rules, verify, refactor]
generated: {by: claude-code, at: 2026-09-23}
status: stable
---

# 룰 레지스트리·반복 교정·rulesets YAML 구현

- 날짜: 2026-09-23
- 브랜치: `feat/rule-registry`
- 워크트리: `.worktrees/rule-registry`

[룰 엔진 설계안](2026-09-23-rule-engine-design.md)의 1~3단계를 구현했다. 4단계(필수 필드 표시와 누락 룰)와 5단계(사용자 정의 식과 룰 등록 UI)는 결정을 기다린다.

## 1단계 — 룰 레지스트리 (`72b8aa1`, 동작 변화 없음)

`rules.Rule(id, code, category, doc_types, detect, fix, on_fail, priority)`와 `RULES` 18개를 정의했다. `check()`는 `RULES`를 순서대로 돌리고, 결과 flag에 `"rule": <id>`를 붙인다. 출력에 새로 생긴 키는 이것 하나뿐이다.

| id | code | category | on_fail | priority |
|---|---|---|---|---|
| MASTER.CODE_UNKNOWN | code_unknown | MASTER | RE_EXTRACT | |
| DATE.ORDER | bad_date | LOGIC | RE_EXTRACT | |
| ID.MISMATCH | id_mismatch | CROSS | RE_EXTRACT | |
| SUM.FIELD | sum_mismatch | CALC | CORRECT | |
| DETAIL.ROW_ARITH | row_arith | CALC | RE_EXTRACT | |
| DETAIL.LOW_QUALITY | low_quality | STRUCT | ESCALATE | |
| DETAIL.ITEM_CLASS | item_class | FMT | CORRECT | |
| GROUND.UNPRINTED | ungrounded | LOGIC | CORRECT | |
| RECEIPT.MULTI_AMOUNT | multi_amount | FMT | RE_EXTRACT | |
| RECEIPT.NO_COLUMN | no_column | STRUCT | RE_EXTRACT | |
| RECEIPT.ROW_COPY | row_copy | STRUCT | RE_EXTRACT | |
| RECEIPT.ROW_MISSING | row_missing | STRUCT | CORRECT | 2 |
| RECEIPT.ROW_EXTRA | row_extra | STRUCT | RE_EXTRACT | |
| RECEIPT.COLUMN_SHIFT | column_shift(행) | STRUCT | CORRECT | |
| RECEIPT.ITEM_NAME | item_name | FMT | CORRECT | 1 |
| RECEIPT.ROW_SHIFT | row_shift | STRUCT | CORRECT | -2 |
| SUM.TABLE | sum_mismatch(표) | CALC | RE_EXTRACT | |
| RECEIPT.COLUMN_SWAP | column_shift(표 전체) | STRUCT | CORRECT | -1 |

- 코드를 여러 개 내던 검사 함수(`_detail_checks`, `_row_checks`, `_sum_checks`)는 룰 하나에 코드 하나가 되도록 쪼갰다. 쪼갠 뒤에도 flag가 나오는 순서는 그대로다.
- 검사 함수는 문서 하나를 담은 `_Doc`을 받는다. `_Doc`은 파서 표 복원(`rebuilt`)을 한 번만 계산해 둔다. "진료비영수증이고 AO 항목내역 행이 있을 때만 본다"는 조건은 `_Doc.sees`로 옮겼다.
- 교정 함수는 `fix(state, flags)` 형태로, 그 룰의 flag를 한꺼번에 받는다. priority 순으로 돌려서 기존 `correct()`의 정렬 결과를 그대로 재현한다.

## 2단계 — 반복 실행기·trace·review (`fd264dd`)

- `rules.run(doc_type, ao, docraft, blocks, rounds=3) -> (fixes, history, trace)`. 한 라운드는 검사 후 교정이다. 상태가 바뀌지 않거나, 이전 상태가 다시 나오거나, 3회에 이르면 멈춘다. `correct()`는 `_correct`로 감췄고, 공개 진입점은 `run` 하나다.
- `verify.run`에서 `check → correct → check`를 `rules.run` 한 번으로 바꿨다. `checks`는 첫 라운드 flag, Judge 힌트는 마지막 라운드 flag에서 가져온다. `checks_after`는 `rules.run(..., rounds=0)`으로 구한다.
- `verify.trace`는 라운드마다, 적용되는 룰마다 한 줄씩 남긴다: `{rule, category, round, result: pass|fail, action, flags, fixed}`. 최종 상태는 `round: "final"`로 적는다.
- 교정 사유는 룰 id로 시작한다(`[RECEIPT.COLUMN_SHIFT] …`).
- `checks_after`에 ESCALATE 룰 flag가 남은 필드나 표에는 `review: true`를 붙인다. low_quality는 지금처럼 Judge 힌트로도 계속 넘긴다. harness-v2 `to_reread`는 `value`·`source`·`reason`만 읽으므로 이 추가는 호환된다.

### 측정 (캐시만, 네트워크 없이)

- 스냅숏 328건(실제 AO 7건, 라벨, 원시 추출, 일부러 변형한 라벨 포함)에서 2라운드 이상에서 교정이 더 나온 경우는 **0건**이었다. 한 번에 교정된 건이 62건, 교정할 게 없던 건이 266건이다.
- 라벨 대비 정확도(`rules.same` 기준)는 1라운드와 3라운드가 같았다. 실제 AO 7건은 532/562(오탐 4), 변형 라벨은 15080/15379(오탐 83)다. 변형 라벨에서 오탐이 11에서 83으로 는 것은 이전 `correct()`에서부터 있던 동작이다.
- 0922 AO 59건(블록 없이)에서는 1건(`2020010684177`)에서 2라운드가 돌았다.
  - 1라운드에서 열 통째 맞바꿈과 합계 행 이동이 부딪쳐 검사료의 비급여 50,000이 선택진료료외 열로 갔고, 2라운드가 이를 되돌려 Docraft 값과 합계식이 맞았다.
  - 이 충돌은 main의 원래 `check`+`correct`(`1191c43`)에서도 똑같이 생긴다. 레지스트리로 옮기면서 생긴 게 아니다.
  - 나빠진 경우가 없어서 기본값을 3라운드로 뒀다.
- 테스트는 424개에서 426개가 됐다. 룰 단계 평가 수치는 그대로다.

### 버린 룰 — `RANGE.NON_NEGATIVE`

- 음수 값을 가진 라벨: 93건 중 0건. 실제 AO 7건: 0건.
- 0922 AO 59건에는 음수 칸이 21개 있었지만, 전부 끝수처리조정금액·조정금액·기타및보정금액 행이라 정상 값이다. 이 행들을 빼면 AO에서는 룰이 걸릴 일이 없다.
- 원시 추출에서 잘못된 음수 2칸(영수증 1건)이 나왔지만, 이건 Docraft 자체 추출이라 AO 검사 룰이 볼 대상이 아니다.
- 걸릴 일이 없는 코드가 되므로 넣지 않았다.

## 3단계 — 룰 데이터 표 YAML (`f81be79`, 동작 변화 없음)

- 표 23개를 [`backend/rulesets/rules.yaml`](../backend/rulesets/rules.yaml) 한 파일로 옮겼다: LABELS, MASTER_NAMES, EXCLUSIVE, SECTIONS, FIELD_SECTION, EXPLICIT, LAST_DATE, TOTALS, UNPRINTED_NULL, KEEP_TOTALS, ROW_KEYS, NOTES, MARKS, TOTAL_FIELDS, FIELD_SUMS, SWAPS, HEADER_COLUMNS, GROUPED, ITEM_ALIASES, RECEIPT_ITEM_NAMES, DATE_ORDER, ISSUED, LATER_OK.
  - 문서 유형으로 나뉜 표가 TOTALS·KEEP_TOTALS·EXPLICIT 셋뿐이라, 유형별로 파일을 쪼개지 않았다.
  - 각 표의 설명 주석은 YAML 주석으로 옮겼다.
- 불러올 때 원래 Python 이름과 자료형(tuple·set·frozenset·컴파일된 정규식)으로 되살린다. 그래서 `verify.py`와 `scripts/`는 고치지 않았다.
- Python에 남긴 것: OCR_DIGITS, 정규식 기본 부품, FIELD_RULES(정제 함수), TOLERANCE·SHIFT_REACH·SENTENCE·OLDEST 같은 수치 상수, ITEM_TABLE·ITEM_COLUMNS·LUMP_ITEMS.
- `disable: {<doc_type>: [룰 id]}`: `_Doc.sees`가 이 설정을 존중하므로 check·run·sum_errors에 모두 적용된다. 모르는 표 이름이나 룰 id가 있으면 import할 때 실패한다. 테스트 2개를 추가했다.
- PyYAML은 그동안 uvicorn[standard]를 통해서만 설치되고 있었다. `requirements.txt`에 `PyYAML==6.0.3`을 직접 적었다. Dockerfile이 `COPY backend`로 폴더 전체를 복사하므로 YAML도 이미지에 들어간다. Docker 빌드는 돌려 보지 않았다.
- rules.py는 1660줄에서 1537줄로 줄었고, 218줄짜리 YAML이 새로 생겼다.

## 동작 변화 0 증명 (1·3단계)

- **스냅숏 대조.** 7개 유형 × (실제 AO, 라벨, 원시 추출, 변형 라벨)에 대해 check flag, 교정, 라운드별 flag, trace, sum_errors를 저장했다. 여기에 캐시된 추출 132건의 `apply()` 결과를 더했고, 전후 파일이 바이트 단위로 같다.
- **옛 코드와 새 코드 대조.** 마스터를 준비된 것으로 흉내 내고 337건을 돌렸다. 코드 16종 모두에서 차이가 0이었고, 교정 결과의 key 순서까지 같다.
- **테스트와 평가.** 3단계 뒤 테스트는 428개 통과다. 룰 단계 평가는 7종 모두 같다(진단서 118/132, 소견서 119/145, 진료비영수증 1871/2044, 세부내역서 1991/2025, 수술확인서 267/291, 입퇴원확인서 299/312, 약제비영수증 217/229).
- **한계.** 대조 스크립트(`/tmp/rules_snapshot.py`, `/tmp/rules_ab.py`)는 커밋하지 않았다. 실제 AO가 붙은 라벨 문서는 유형마다 1건뿐이라, 변형 라벨로 입력 범위를 넓혔다.

## 남은 일

- 4단계: `doctypes`에 필수 필드 표시(`required`)를 넣고 누락 룰을 추가한다. 유형별로 어떤 필드가 필수인지는 업무 정의가 필요하다.
- 5단계: 사용자 정의 식과 룰 등록 UI. 설계안 §5의 결정이 필요하다.
- 1라운드에서 열 통째 맞바꿈과 합계 행 이동이 부딪치는 순서 문제는 반복 교정이 가려 주고 있을 뿐이다. 교정 순서를 고치는 일은 따로 남겨 둔다.
