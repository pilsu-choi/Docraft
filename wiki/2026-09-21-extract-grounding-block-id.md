---
type: Implementation Log
title: "추출 grounding 서버 측 계산 전환과 json_object 계약"
description: "extract()를 json_object 단일 결과 계약으로 바꾸고, grounding을 모델 응답 대신 서버가 원문 블록에서 값을 찾아 계산하도록 전환한 기록"
tags: [backend, extraction, ai-provider, grounding]
generated: {by: claude-code/claude-fable-5-1, at: 2026-09-21}
status: stable
---

# 추출 grounding 서버 측 계산 전환과 json_object 계약

[extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md) 사고의 후속 대응으로 `backend/engine.py`의 `extract()` 계약을 두 단계에 걸쳐 바꿨다. 최종 상태는 **모델에게 추출 결과만 요청하고, grounding은 서버가 계산하는 것**이다.

## 최종 계약

### 1. 모델은 결과만 반환한다

`_provider()`는 `response_format: {"type": "json_object"}`로 요청하고, system prompt는 "주어진 스키마를 그대로 따르는 JSON object 하나를 래핑 키 없이, 스키마의 필드 순서를 유지해 반환하라"고만 지시한다. `Never invent values. Use null when allowed and absent.` 문구는 그대로 유지했다. grounding·블록 id 관련 지시는 전부 없앴고, 모델 입력의 블록 목록도 `[id] text`가 아닌 블록 텍스트 줄만 넘긴다.

응답이 dict가 아니면 `RuntimeError("AI provider 응답이 JSON object가 아닙니다.")`를 낸다.

### 2. 서버가 result의 모든 leaf에 grounding을 계산한다

`_grounding_tree(value, sources)`가 `result`를 재귀 순회하며 grounding 트리를 만든다. 트리 형태는 예전과 같다: object는 중첩 dict, 배열은 인덱스를 문자열 키(`"0"`, `"1"`…)로 쓰는 dict, leaf는 `{confidence, page, bbox, source_text}`. `backend/main.py`의 `grounding_list()`가 이 트리를 점 경로로 평탄화해 프론트엔드에 넘기므로 소비 측은 그대로 둘 수 있었다.

leaf 하나의 처리:

- 값이 `None`이면 `{"confidence": 0, "page": None, "bbox": None, "source_text": None}` — `_local_extract`가 값을 못 찾았을 때 쓰는 관례와 같다.
- 값이 있으면 그 값을 담은 블록을 찾는다. 비교는 양쪽 모두 `_normalized()`(공백·쉼표 제거)를 거친 문자열의 부분 문자열 포함으로 한다. OCR 텍스트는 `12,380`인데 모델 값은 숫자 `12380`이고, `전액\n본인부담`처럼 줄바꿈이 끼며, table 블록 텍스트는 `<td>` HTML 마크업이라서 정규화 없이는 거의 매칭되지 않는다. float가 정수값이면(`1.0`) `"1.0"`과 `"1"` 둘 다 후보로 본다. 첫 번째로 매칭되는 블록을 쓴다.
- 찾으면 `{"confidence": 1.0, "page": block.page, "bbox": block.bbox, "source_text": str(value)}`, 못 찾으면 `{"confidence": 0.0, "page": None, "bbox": None, "source_text": str(value)}`.

`confidence`의 의미가 바뀌었다. 예전에는 모델이 스스로 매긴 확신도였고 이제는 **원문 블록에서 그 값을 찾았는지 여부**라서 `1.0` 아니면 `0.0`만 나온다. 못 찾은 leaf는 `validate()`의 `low_confidence` 기준(0.7 미만)에 걸려 화면에 "원문 근거 없음"으로 자연히 드러난다.

### 3. optional null 결과 제거

모델이 스키마상 optional인 필드에 값이 없을 때 `null`을 반환하는 경우가 있다. 저장과 `validate()`는 원본 스키마를 쓰므로 `{"type": "string"}`처럼 null을 허용하지 않는 필드에 `null`이 들어오면 타입 오류가 난다. `_drop_null_optionals(value, schema)`가 provider 응답 직후 "값이 `None`이고 원본 스키마의 `required`에 없고 `type`이 null을 허용하지 않는" 리프를 지운다. required인데 null인 값은 그대로 둬서 `validate()`가 잡게 한다. grounding 트리는 이 정리 뒤의 `result`로 만들므로 지워진 리프는 트리에도 없다.

### 4. 모델 입력 블록 단위 예산 자르기

`_block_lines`는 블록 텍스트를 줄로 이어 붙이되 문자 예산(기본 40000자)을 넘기면 그 지점부터 블록을 통째로 잘라내고 `logger.warning`으로 몇 번째 블록에서 잘렸는지 남긴다.

## 이력: 블록 id grounding은 중간 단계였다

그 전 단계에서는 모델이 grounding마다 `{path, confidence, block}`을 반환하고 서버가 `block` id로 `page`·`bbox`를, `path`로 `source_text`를 채웠다. 모델이 긴 원문을 옮겨 적지 않게 해 escape 오류를 줄이자는 의도였다. 실제 재현 테스트로 세 가지가 드러나 폐기했다.

- **느리다.** 같은 문서(표 16행 × 12필드)에서 `result`만 요청하면 41초, `groundings`를 함께 요청하면 150~200초였다. 응답 시간의 대부분이 grounding 생성이었다.
- **정보량이 없다.** 돌아온 grounding 204개가 전부 `block 1`, `confidence 1.0`이었다. 이 문서는 표 전체가 OCR 블록 하나라서 모델이 고를 블록이 사실상 하나뿐이었고, confidence도 상수였다.
- **조용히 깨진다.** 모델이 `"block": "1"`처럼 id를 문자열로 돌려주면 서버는 정수만 받아 `page`/`bbox`를 전부 `null`로 채웠고, 오류도 로그도 남지 않았다. 범위 밖 id도 마찬가지였다.

서버가 값 텍스트를 블록에서 찾는 방식은 같은 정보를 LLM 호출 없이 얻는다. 모델이 `path`를 잘못 쓰거나 leaf를 빠뜨릴 여지도 사라져서 `_pointer_value`·`_MISSING`·`_pointer_parts`와 기형 grounding 방어 로직이 전부 필요 없어졌고 삭제했다.

strict `json_schema` 정규화(`_strict_schema`)와 OpenRouter `provider.require_parameters: true`도 앞서 철회했다. 사고 문서의 재현 실험에서 Alibaba provider가 strict 모드에서 응답 키를 정렬해 컬럼이 밀리고 degeneration 루프로 JSON이 끊기는 것이 확인됐기 때문이다. 자세한 실험 표는 [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)에 있다.

## 변경 파일

- `backend/engine.py` — `extract()`를 단일 결과 계약으로 재구성, `_normalized()`와 값 기반 `_grounding_tree(value, sources)` 추가, `_pointer_parts`/`_pointer_value`/`_MISSING`/기존 path 기반 `_grounding_tree` 삭제, `_block_lines`에서 `[id]` prefix 제거
- `tests/test_ai_provider.py` — 정규화 매칭으로 page/bbox가 채워지는지, 블록에 없는 값이 confidence 0으로 `validate()`의 `low_confidence`를 내는지, 배열·중첩 트리 형태가 유지되는지, 응답이 object가 아니면 `RuntimeError`인지, optional null 제거와 블록 예산 자르기를 검증. 블록 id·기형 grounding 방어 테스트는 삭제
- (2026-09-22) `backend/engine.py` — `_block_rows`/`_needles`/`_hits`/`_agreed_row`/`_row_bbox`/`_leaf` 추가, `_grounding_tree`를 합의 행 기반으로 교체(순증 약 57줄). `tests/test_ai_provider.py` — 행별 bbox 분할, 짧은 값이 다른 셀에 걸리지 않음, 다른 행에서 온 배열 항목 값의 0.5, 문장 속 값과 날짜 구분자 변형, 최상위 leaf의 블록 분산을 검증하는 테스트 4개 추가. `README.md` — 근거 상자가 행 단위임을 설명

## 재현 테스트 (2026-09-21)

사고 문서(`2303314528.png`, OCR 블록 3개, 표 16행 × 12필드) + 스키마 `a23d4d53…` + `qwen/qwen3-vl-32b-instruct`(OpenRouter → Alibaba)로 최종 코드를 돌렸다.

| 계약 | 응답 시간 | 결과 |
|------|-----------|------|
| `json_object` + `result`/`groundings` (이전) | 150~200초 | 16행 정확, grounding 199~204개 전부 block 1·confidence 1.0 |
| `json_object` + 결과만, 서버 측 grounding (현재) | **61초** | 16행 정확, grounded leaf 199개 전부 `bbox` 채워짐, `validate()` 이슈 0건 |

매칭 실패로 `bbox`가 `null`이 된 leaf는 없었다. 쉼표가 들어간 금액(`12,380`), 줄바꿈이 낀 문자열, `1.0` ↔ `1`이 모두 정규화로 잡혔다.

## 테스트 결과

```
python -m pytest tests -q --ignore=tests/ui_smoke.py --ignore=tests/ui_preview_layout.py --ignore=tests/ui_project_workspace.py
38 passed
```

## 행 인식 grounding (2026-09-22)

위 "남은 한계"의 앞 세 가지(블록 단위 해상도, 짧은 값 오탐, 행 밀림을 못 잡음)를 같은 기반 위에서 한 번에 고쳤다. 기반은 **블록을 행과 셀로 읽는 것**이다.

### 왜 셀 좌표를 쓰지 않았나

PaddleOCR-VL 응답을 직접 확인했다. 좌표는 `parsing_res_list[].block_bbox` 하나뿐이고 셀 단위 좌표는 없다. table 블록의 `block_content`는 `<table><tr><td colspan="2">…</td>…</tr>…</table>` HTML 문자열이라서, 셀 위치를 얻으려면 이 HTML의 구조를 좌표로 환산하는 수밖에 없다.

### 블록 → 행 → 셀

`_block_rows(block)`가 블록 하나를 정규화된 셀 목록의 행 리스트로 바꾼다. `extract()`에서 블록마다 한 번만 계산해 `_grounding_tree`에 넘긴다.

- docx·xlsx·csv 파서가 만든 `rows`(list[list[str]])가 있으면 그대로 쓴다.
- table HTML은 `<tr>`로 행을, `<td>`/`<th>`로 셀을 나눈다. 속성(`colspan`, `rowspan`)은 무시하고 셀 안의 태그는 지운다.
- 그 외 텍스트 블록은 행 1개로 보되, 셀은 `[정규화된 전체 텍스트, 공백 기준 토큰들…]`이다. 전체 텍스트 셀이 문장 속 값(`신청인 이현창 (환자와의 관계…`의 `이현창`)을 잡고, 토큰 셀이 짧은 값의 전체 일치를 가능하게 한다.

`_normalized()`는 공백·쉼표에 더해 OCR이 셀 안 줄바꿈 자리에 넣는 리터럴 `\n` 두 글자도 지운다.

### 셀 단위 매칭

`_hits(value, sources)`는 값이 들어 있는 `(블록, 행)` 목록을 돌려준다. **정규화된 셀 전체 일치를 우선**하고, 전체 일치가 하나도 없을 때만 부분 문자열 일치를 쓴다. 부분 문자열은 needle이 3자 이상일 때만 허용한다. 이것으로 `0`이나 `1`이 `12,380` 셀 안에 걸리는 오탐이 사라졌고, `AA254`가 `AA254030` 셀에 먼저 걸리는 문제도 전체 일치 우선으로 해소됐다.

후보 문자열(`_needles`)은 기존 `1.0` ↔ `1`에 날짜 구분자 변형(`2023.03.11` ↔ `2023-03-11` ↔ `2023/03/11`)과 끝에 붙은 통화·단위 기호(`원`, `₩`, `%`) 제거를 더했다.

### 합의 행과 confidence

객체 하나의 스칼라 leaf들이 각자 찾은 행 중 **가장 많은 leaf가 가리키는 행**을 합의 행으로 고른다(`_agreed_row`). 동률이면 앞 배열 항목이 이미 차지하지 않은 행을, 그래도 동률이면 첫 행을 쓴다. 코드만 다른 유사 행이 여러 개여도 형제 값 일치 수가 올바른 행을 고른다.

`confidence`의 의미는 이렇게 세 단계가 됐다.

| 값 | 뜻 |
|----|-----|
| `1.0` | 합의 행에서 찾았다(또는 배열 항목이 아니어서 감점 대상이 아니다) |
| `0.5` | 배열 항목 안인데 합의 행에는 없고 다른 행에서만 찾았다 → 행·컬럼 밀림 의심 |
| `0.0` | 어디에서도 못 찾았다 → 모델이 지어냈을 가능성 |

`0.5`와 `0.0`은 둘 다 `validate()`의 `low_confidence`(0.7 미만)에 걸려 화면에 드러난다. 최상위 객체처럼 배열 항목이 아닌 객체는 leaf가 서로 다른 블록에서 오는 게 정상이라 감점하지 않고, 합의 행은 짧은 값의 위치를 고르는 동률 해소에만 쓴다.

### 행 bbox 추정

매칭된 행이 i번째(총 n행)이고 블록 bbox가 `[x0,y0,x1,y1]`이면 grounding bbox는 `[x0, y0+(y1-y0)*i/n, x1, y0+(y1-y0)*(i+1)/n]`이다. 블록을 행 수만큼 균등 분할한 가로 띠다. 행이 1개이거나 블록에 bbox가 없으면(docx/xlsx/csv 블록) 블록 bbox를 그대로 쓴다.

### 실제 데이터 검증 (2026-09-22)

사고 문서(`2303314528.png`, 블록 3개, table 블록의 `<tr>` 25개)의 저장된 추출 결과에 새 grounding을 그대로 적용했다.

- leaf 199개 전부 `confidence: 1.0`. 정상 데이터에서 오탐(0.5/0.0)은 0건이다.
- 배열 항목 16개가 데이터 행인 `<tr>` 6~21에 1:1로 매핑됐고, 행 bbox의 y 범위가 항목 순서대로 `502.4→547.9`부터 `1185.8→1231.3`까지 45.56px씩 겹치지 않고 증가한다.
- 최상위 `환자성명`·`진료기간`은 환자 정보 행(`<tr>` 1, y `274.6~320.1`), 중첩 객체 `합계`의 5개 leaf는 합계 행(`<tr>` 24, y `1322.4~1368.0`)을 가리킨다.
- 오류 주입: `항목정보[0].금액`을 다음 행 값(`2710`)으로 바꾸면 그 leaf만 `0.5` + `low_confidence`가 되고 나머지 198개는 `1.0`으로 남는다. 원문에 없는 값(`김철수`, `존재하지않는명칭`)을 넣으면 `0.0`이 된다.
- 같은 문서로 실제 provider 호출까지 한 번 더 돌렸다. 40.4초, 16행 정확, leaf 199개 전부 `bbox` 채워짐, `validate()` 이슈 0건, 행 매핑도 위와 같았다.

## 남은 한계

- **같은 행 안의 컬럼 밀림은 못 잡는다.** `항목정보[0].일자`를 같은 행의 코드 값 `AA254`로 바꾸거나 한 행 안에서 필드를 통째로 한 칸씩 민 결과도 전부 `1.0`으로 남는다. 합의는 행 단위라서 행만 맞으면 통과한다. 이걸 잡으려면 표 헤더와 스키마 필드를 컬럼으로 매핑해야 하는데, 그건 별도 기능이다.
- **행 bbox는 균등 분할 추정이다.** `rowspan`을 무시하고 행 높이가 모두 같다고 가정하므로, 머리글이 2행으로 병합됐거나 행 높이가 들쭉날쭉한 표에서는 실제 행보다 위나 아래로 어긋난다. 검증 문서에서는 25행이 거의 균등해 눈에 띄는 오차가 없었지만 보장은 아니다. 셀 단위 정확한 좌표는 OCR 응답에 없으므로(위 참조) 파서가 표를 더 잘게 나누기 전에는 개선 여지가 없다.
- `confidence`는 여전히 추출 품질이 아니라 "원문의 어느 행에서 값을 찾았는지"를 뜻한다. 모델이 잘못 뽑은 값이라도 그 행에 그 문자열이 있으면 `1.0`이다.
- `_block_lines`는 예산을 넘는 블록 하나를 만나면 그 지점에서 멈추므로, 그 블록 자체가 예산보다 크면 이후 블록이 전부 빠진다.
