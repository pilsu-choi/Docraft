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
34 passed
```

## 남은 한계

- grounding의 해상도는 OCR 블록 단위다. 이 문서처럼 표 전체가 블록 하나면 199개 leaf가 전부 같은 `bbox`를 가리켜서 화면의 근거 상자가 표 전체를 덮는다. 셀 단위 근거가 필요하면 파서가 블록을 더 잘게 나눠야 한다.
- 부분 문자열 매칭이라 `0`, `1` 같은 짧은 값은 아무 블록에나 걸린다. 블록이 여러 개인 문서에서는 엉뚱한 블록이 첫 매칭이 될 수 있다.
- `confidence`는 이제 추출 품질이 아니라 "원문에서 값을 찾았는지"만 뜻한다. 모델이 잘못 뽑은 값이라도 그 문자열이 원문 어딘가에 있으면 `1.0`이 된다.
- `_block_lines`는 예산을 넘는 블록 하나를 만나면 그 지점에서 멈추므로, 그 블록 자체가 예산보다 크면 이후 블록이 전부 빠진다.
