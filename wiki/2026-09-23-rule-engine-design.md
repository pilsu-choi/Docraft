---
type: Design
title: "룰 엔진 선언형 전환 설계안 — VALIDATE·CORRECT·RE-EXTRACT·ESCALATE"
description: "rules.py에 코드로 박힌 검사·교정을 룰 레지스트리와 실행기 하나로 옮기고, 룰별 실행 기록과 반복 교정을 더하는 설계. harness-v2 룰 DSL과의 역할 분담 포함"
tags: [backend, rules, verify, design, harness-v2]
generated: {by: claude-code, at: 2026-09-23}
status: draft
---

# 룰 엔진 선언형 전환 설계안

- 날짜: 2026-09-23
- 브랜치: `docs/rule-engine-design`
- 워크트리: `.worktrees/rule-engine-design`

"OCR → KIE → Rule Engine(검증·정규화·누락·오탐·필드 간 검증) → 교정 → 재검증 → 최종 KV" 구조와 지금 코드를 비교하고, 빠진 부분을 채우는 설계다. 1~3단계는 [rule-registry](2026-09-23-rule-registry.md)에서 구현했다. 범위 룰 `RANGE.NON_NEGATIVE`는 걸릴 일이 없어 넣지 않았다.

## 1. 현재 상태

### Docraft `/api/verify` (`backend/verify.py:285` `run`)

```
parse → engine.extract → rules.apply(정규화·라벨 재탐색·파생)
      → rules.check → rules.correct(룰 교정) → rules.check(남은 이상)
      → judge(LLM, 불일치 필드만) → _decide / _balance(합계식으로 후보 선택)
      → 필드별 value·source·reason, verify.checks·checks_after
```

| 목표 구조 | 상태 | 근거 |
|---|---|---|
| 형식 룰 | 있음 | `rules.normalize` `rules.py:306`, `FIELD_RULES` `rules.py:409` |
| 범위 룰 | 없음 | — |
| 필드 간 룰 | 있음 | `DATE_ORDER` `rules.py:1127`, `FIELD_SUMS` `rules.py:984`, `_detail_checks` |
| 누락 탐지·주변 재탐색 | 있음 | `_add_missing` `verify.py:124`, `_fill` `rules.py:555` |
| 오탐 → 재판정 | 부분 | 이상이 있는 필드만 Judge로 보낸다. confidence로 재추출하지는 않는다 |
| 계산 관계로 후보 선택 | 있음 | `_balance` `verify.py:226` |
| 교정 → 재검증 | 1회 | `correct` 뒤 `check` 한 번 |
| 룰과 LLM 분리 | 있음 | `correct`가 먼저, Judge는 남은 불일치만 |
| 선언형 룰, Action 타입 | 없음 | 표는 Python 상수, 검사·교정은 함수 |
| 룰별 PASS/FAIL 기록 | 없음 | `check`는 걸린 이상만 돌려준다 |
| 룰 등록 UI | 없음 | — |

일반 추출 경로(`engine.validate` `engine.py:559`)에는 JSON Schema 검사와 confidence 0.7 기준만 있다.

### harness-v2에는 선언형 룰 엔진이 이미 있다

`harness-v2/src/mlife_harness/rules/`에는 목표 구조의 VALIDATE 쪽이 이미 구현돼 있다.

- 룰 YAML(`rulesets/*.yaml`, 33개): `id`·`category`(FMT/CALC/LOGIC/MASTER/CROSS/DOMAIN/STRUCT/ENRICH/SORT)·`severity`·`scope`·`target`·`requires`·`expr`·`tolerance`·`on_missing`/`on_false`. `expr`는 AST 허용 목록으로만 평가하고, 룰이 잘못 적혀 있으면 서버가 뜰 때 실패한다.
- 결과는 `pass|fail|warn|not_applicable`이고, 룰이 읽은 필드마다 `RuleEvidence`(rule_id·result·detail·context)를 붙인다.
- 실패한 뒤의 흐름: 합계 룰이 실패하면 영역만 다시 읽는 자기교정(최대 3회) → 판정표(§9.3)로 tier 결정(`pass/repaired/inferred/swap/ambiguous/unresolved/out_of_scope`) → `ambiguous/unresolved`인 필드만 `hint_paths`로 Docraft `/api/verify`를 부른다.
- 사람 검토 큐는 없다. 모든 문서를 적재하고 신뢰 등급(tier)으로 구분한다.

즉 두 시스템을 합치면 이미 "Rule(검증) → RE-EXTRACT → ESCALATE"가 돌고 있다. harness-v2가 **선언형 검증과 등급 판정**을 맡고, Docraft가 **독립 재추출·결정적 교정·LLM 판정**을 맡는다.

## 2. 설계 원칙

1. **DSL을 새로 만들지 않는다.** 선언형 검증식은 harness-v2 형식(`id/category/severity/target/expr/on_false`)을 그대로 쓴다. Docraft에 비슷한 문법을 하나 더 만들면 같은 의미의 기능이 두 벌이 된다.
2. **Docraft 룰은 "탐지기 + 교정기" 쌍으로 등록한다.** 열 밀림, 행 재구성, 마스터 조회처럼 절차가 필요한 로직은 식으로 옮기면 오히려 길어진다. 이런 로직은 Python 함수로 두고, 메타데이터(id·category·action·priority)만 선언한다.
3. **순수 데이터 표만 YAML로 뺀다.** `LABELS`, `TOTALS`, `FIELD_SUMS`, `DATE_ORDER`, `SWAPS`, `ITEM_ALIASES` 등이 대상이다. 코드를 고치지 않고 문서 유형·라벨·산식을 추가할 수 있는 범위가 여기까지다.
4. **리팩터 단계에서는 결과가 바뀌면 안 된다.** `scripts/verify_eval.py`의 캐시 평가(rules·final 단계 정답 수)와 `tests/`의 테스트 166개가 이전과 같아야 다음 단계로 넘어간다.

## 3. 구조

### 3.1 룰 레지스트리 (`backend/rules.py` 안, 새 파일 없음)

```python
@dataclass(frozen=True)
class Rule:
    id: str                 # "SUM.FIELD", "DATE.ORDER", "RECEIPT.ROW_SHIFT" …
    category: str           # harness-v2 RuleCategory 값 그대로: FMT/CALC/LOGIC/MASTER/CROSS/STRUCT
    doc_types: tuple        # 빈 튜플이면 전 유형
    detect: Callable        # (ctx) -> list[flag]   지금의 _date_checks, _row_shifts …
    fix: Callable | None    # (ctx, flag) -> 변경 또는 None   지금 correct()의 분기
    on_fail: str            # CORRECT | RE_EXTRACT | ESCALATE
    priority: int = 0       # 교정 순서. 지금 correct()의 정렬 키를 옮긴다
```

지금 `check()`가 만드는 코드 16종이 룰 하나씩이 된다. 다음은 대표 예다.

| 룰 id | 현재 코드 | category | on_fail |
|---|---|---|---|
| `MASTER.CODE_UNKNOWN` | `code_unknown` | MASTER | RE_EXTRACT |
| `DATE.ORDER` | `bad_date` | LOGIC | RE_EXTRACT |
| `ID.MISMATCH` | `id_mismatch` | CROSS | RE_EXTRACT |
| `SUM.FIELD` | `sum_mismatch`(필드) | CALC | CORRECT(`UNPRINTED_NULL`이면 비움) → RE_EXTRACT |
| `SUM.TABLE` | `sum_mismatch`(표) | CALC | RE_EXTRACT |
| `RECEIPT.ROW_SHIFT` | `row_shift` | STRUCT | CORRECT, priority -2 |
| `RECEIPT.COLUMN_SWAP` | `column_shift`(표 전체) | STRUCT | CORRECT, priority -1 |
| `RECEIPT.COLUMN_SHIFT` | `column_shift`(행) | STRUCT | CORRECT |
| `RECEIPT.ITEM_NAME` | `item_name` | FMT | CORRECT, priority 1 |
| `RECEIPT.ROW_MISSING` | `row_missing` | STRUCT | CORRECT, priority 2 |
| `DETAIL.ROW_ARITH` | `row_arith` | CALC | RE_EXTRACT |
| `DETAIL.LOW_QUALITY` | `low_quality` | STRUCT | ESCALATE |
| `GROUND.UNPRINTED` | `ungrounded` | LOGIC | CORRECT(비움) |
| `RANGE.NON_NEGATIVE` | **새로 추가** | FMT | RE_EXTRACT |

`check()`·`correct()`·`sum_errors()`는 레지스트리를 돌리는 얇은 함수로 줄인다. 이름과 반환 형태는 유지해서 `verify.py`와 테스트가 그대로 돈다.

### 3.2 실행기: 검증 → 교정 → 재검증 반복

```python
def run(doc_type, ao, docraft, blocks, rounds=3) -> tuple[dict, dict, list[dict]]:
    """교정할 게 없어질 때까지(최대 rounds) detect → fix를 반복하고 룰별 기록을 남긴다."""
```

- 한 바퀴에 모든 룰의 `detect`를 돌린다. `on_fail == CORRECT`인 flag는 priority 순서로 `fix`를 적용한다.
- 교정이 하나도 없거나, 같은 상태가 다시 나오면(진동) 멈춘다. harness-v2의 3회 상한을 그대로 쓴다.
- 마지막까지 남은 flag 중 `RE_EXTRACT`는 지금처럼 Judge의 `hint`/`disputes`로 넘긴다. `ESCALATE`는 판정하지 않고 `source: unknown`에 `review: true`를 붙인다.
- `verify.run`의 `check → correct → check`가 이 호출 하나로 바뀐다.

### 3.3 실행 기록 (`verify.trace`)

`target["verify"]`에 `trace`를 더한다.

```json
{"rule": "SUM.FIELD", "category": "CALC", "round": 1, "result": "fail",
 "action": "CORRECT", "key": "급여_급여총액", "message": "…", "fixed": true}
```

- `result`는 harness-v2와 같은 `pass|fail|warn|not_applicable`이다. 적용 대상인데 flag가 없으면 `pass` 한 줄을 남긴다. 그래서 "Rule #12 PASS / FAIL / 교정 / PASS"를 재현할 수 있다.
- `checks`·`checks_after`는 `trace`에서 거꾸로 계산할 수 있다. 다만 테스트와 평가 스크립트가 이 형태에 기대고 있어서 한동안은 그대로 두고, `trace`가 자리를 잡으면 없앤다.
- 필드별 `source`·`reason`은 그대로다. `reason`에 룰 id를 붙인다(`[SUM.FIELD] …`).

### 3.4 데이터 표 YAML (`backend/rulesets/<doc_type>.yaml`)

아래는 형태만 보여 주는 예시다. 값은 실제 표에서 옮겨 온다.

```yaml
doc_type: 진료비영수증
labels:        {진료시작일: [진료기간, 입원기간, 내원일자]}
field_sums:    {진료비총액: [급여_급여총액, 비급여총액]}
date_order:    [[진료시작일, 진료종료일], [입원일자, 퇴원일자]]
swaps:         [[본인부담금, 공단부담금], [선택진료료, 선택진료료외]]
item_aliases:  [["^선택진료\\s*이외", 선택진료료이외]]
ranges:        {"*총액": {min: 0}, "*부담금": {min: 0}}
disable:       [RECEIPT.ROW_MISSING]   # 유형별로 룰 끄기
```

- 파일은 서버가 뜰 때 한 번 읽는다. 모르는 키나 정의되지 않은 룰 id가 있으면 서버가 뜨지 않는다(harness-v2와 같은 방식).
- 절차가 필요한 로직(`_fill`의 순위 매기기, `_receipt_rows`, `pair_rows`, 마스터 조회, `FIELD_RULES`의 정제 함수)은 Python에 남긴다. 표 값만 YAML에서 받는다.
- 문서 유형 스키마(`doctypes.py`)는 이번 범위에 넣지 않는다. 필수 여부 표시가 없어서 누락 규칙을 선언하려면 `required`를 먼저 추가해야 하는데, 이건 4단계에서 다룬다.

### 3.5 Action 대응

| Action | Docraft에서의 뜻 | harness-v2 대응 |
|---|---|---|
| VALIDATE | 룰 `detect` | `RuleEngine.evaluate` |
| CORRECT | 룰 `fix`(LLM 없이) | tier `repaired` |
| RE_EXTRACT | Judge가 이미지를 다시 봄. Docraft 독립 추출과 대조 | reread / 자기교정 |
| ESCALATE | `review: true`, `source: unknown` | tier `ambiguous`/`unresolved` |

## 4. 단계

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| 1 | 레지스트리 + `check`/`correct`를 레지스트리로 교체(동작 변화 없음) | 테스트 전부 통과, 캐시 평가 rules·final 수치가 이전과 같음 |
| 2 | 반복 실행기 `run`, `verify.trace`, `RANGE.NON_NEGATIVE` | 캐시 평가에서 오탐이 늘지 않음. 반복 효과를 수치로 기록 |
| 3 | 데이터 표를 `rulesets/*.yaml`로 옮기고 `disable` 추가 | 1단계와 수치 같음. 옮긴 표가 Python에 두 벌로 남지 않음 |
| 4 | `doctypes`에 `required` 추가, 누락 룰 `MISSING.REQUIRED`(→ `_fill` → RE_EXTRACT) | 누락 필드 복구 수치 |
| 5 | (선택) 일반 파이프라인에서 프로젝트 스키마별 사용자 룰(`expr`) + 룰 등록 UI | 별도 결정 필요(아래 참고) |

1·2단계만으로 "검증 → 교정 → 재검증 → 실행 기록" 구조가 갖춰진다. 3단계부터는 룰을 코드 수정 없이 늘리기 위한 작업이다.

## 5. 결정이 필요한 것

1. **사용자 정의 식(`expr`)과 룰 등록 UI를 어느 쪽에 둘지.** 선택지는 두 가지다.
   - (a) harness-v2의 `rules/expr.py`와 `spec.py`를 공용 패키지로 떼어 두 프로젝트가 같이 쓴다.
   - (b) 식 룰은 harness-v2에만 두고, Docraft는 탐지기·교정기만 가진다.

   권고는 (b)다. 5단계가 정말 필요해지면 그때 (a)로 간다. 지금 Docraft에 식 평가기를 따로 두면 같은 기능이 두 벌이 된다.
2. **ESCALATE의 의미.** harness-v2는 "HITL 없음, 등급으로 적재"로 정했고, Docraft 일반 파이프라인은 `needs_review` 상태로 사람 검토를 한다. `/api/verify`에서는 harness-v2를 따라 표시만 하고, 일반 파이프라인에서는 `needs_review`로 보내는 것을 권고한다.

## 6. 위험

- **교정을 반복하면 과교정이 쌓일 수 있다.** 지금 `correct()`는 한 번만 돌도록 튜닝돼 있다(예: `row_shift`는 flag가 뜨면 조건 없이 옮긴다). 2단계에서 라운드별로 교정 수와 정확도를 따로 재고, 2회차부터 나빠지는 룰은 `rounds=1`로 묶는다.
- **재추출 변동.** 영수증 재실행 변동이 ±43이라 캐시가 아닌 새 추출로 비교하면 차이를 읽을 수 없다. 1·3단계 검증은 반드시 캐시 평가로 한다.
- **harness-v2와의 계약.** harness-v2 `to_reread`(`reread/docraft.py:146`)는 원소별 `value`·`source`·`reason`만 읽고, `source: unknown`인 원소는 버린다. 그래서 ESCALATE를 `unknown`으로 두면 harness-v2 쪽에서는 기존 등급이 그대로 유지된다. 이 세 키의 이름과 의미는 바꾸면 안 되고, 키를 더하는 건 괜찮다.
