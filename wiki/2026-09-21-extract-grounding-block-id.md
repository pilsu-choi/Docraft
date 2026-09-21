---
type: Implementation Log
title: "추출 grounding 블록 id 전환과 json_object 계약 전환"
description: "extract() grounding을 블록 id 참조로 바꾸고, 재현 테스트로 해로움이 확인된 strict json_schema 정규화 대신 response_format: json_object로 전환한 기록"
tags: [backend, extraction, ai-provider, grounding]
generated: {by: claude-code/claude-fable-5-1, at: 2026-09-21}
status: stable
---

# 추출 grounding 블록 id 전환과 json_object 계약 전환

[extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md) 사고의 후속 대응으로 `backend/engine.py`의 `extract()` 계약을 바꿨다. 목표는 VLM 응답 크기와 escape 위험을 줄이는 것이었고, 이후 재현 테스트로 실제 파싱 실패의 원인이 strict `json_schema` constrained decoding 자체였음이 드러나면서 structured output 강제 방식도 바꿨다.

## 변경 내용

### 1. grounding을 블록 id 참조로 전환

기존에는 모델이 grounding마다 `source_text`·`page`·`bbox`를 직접 베껴 반환했다. 이제 모델은 `{path, confidence, block}`만 반환하고, 서버가 `extract()`에서 `block` id로 원본 블록을 찾아 `page`·`bbox`를 채우고 `path`로 `result`를 읽어 `source_text`를 채운다(`_pointer_value`). `block`이 범위를 벗어나면 `page`/`bbox`는 `null`로 남는다. 모델이 긴 문자열을 직접 옮겨 적지 않으므로 escape 오류로 JSON이 깨질 위험이 줄어든다.

### 2. 모델 입력 블록 단위 직렬화·예산 자르기

소스 블록을 JSON 배열 대신 `[id] text` 줄로 직렬화한다(`_block_lines`). 문자 예산(기본 40000자)을 넘기면 그 지점부터 블록을 통째로 잘라내고 `logger.warning`으로 몇 번째 블록에서 잘렸는지 남긴다. 블록 하나가 예산보다 크면 그 블록부터 이후가 전부 빠진다는 한계가 있다.

### 3. (철회) strict 스키마 정규화 + OpenRouter `require_parameters`

최초 대응으로 `_strict_schema`를 추가해 사용자 스키마를 재귀적으로 순회하며 모든 object에 `additionalProperties: false`를 붙이고 `properties`의 모든 키를 `required`에 넣었다. 원래 optional이던 필드는 `type`에 `"null"`을 추가해 nullable로 만들었다(예: `{"type": "string"}` → `{"type": ["string", "null"]}`). `base_url`에 `openrouter`가 포함되면 요청 body에 `provider: {require_parameters: true}`를 추가해 OpenRouter가 고른 하위 provider가 `response_format`을 무시하지 못하게 했다.

이후 사고 문서로 재현 테스트를 해보니([extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "재현 테스트로 확인한 실제 원인" 참고) 이 정규화가 오히려 해로웠다: Alibaba provider(OpenRouter가 이 모델을 라우팅하는 하위 provider)가 strict `json_schema`에서 응답 키를 알파벳/코드포인트 순으로 정렬해 출력했고, 그 결과 표 데이터의 컬럼이 밀리면서 모델이 degeneration 루프에 빠져 JSON이 중간에 끊겼다. 그래서 `_strict_schema`와 `require_parameters` 분기를 모두 삭제했다.

### 4. `extract()`를 `response_format: json_object`로 전환

`_provider()`는 이제 `response_schema` 인자를 받지 않고 항상 `response_format: {"type": "json_object"}`로 요청한다. 출력 계약(하나의 JSON object, 키 `result`와 `groundings`, `result`는 스키마 필드 순서 유지, `groundings`는 `{path, confidence, block}` 배열)은 system prompt 문구로만 지시한다. 모델이 이 계약을 어길 수 있으므로 `extract()`가 방어적으로 처리한다:

- `ai["result"]`가 dict가 아니면 `RuntimeError("AI provider 응답에서 result를 찾을 수 없습니다.")`를 명시적으로 낸다.
- `ai["groundings"]`가 없거나 list가 아니면 빈 리스트로 취급한다.
- grounding 항목이 dict가 아니거나 `path`가 문자열이 아니면 건너뛴다.
- `confidence`가 숫자가 아니면 `0`으로 채운다.

재현 테스트(위 표의 실험 3·4)에서 `json_object` 모드는 16행 모두 정확했고(숫자 타입·컬럼 순서 유지), `result`+`groundings` 계약을 함께 요청해도(실험 4) `validate()` 이슈 0으로 정상 동작했다.

### 5. optional null 결과 제거 (계약 불일치 수정)

`json_object` 모드에서도 모델이 스키마상 optional인 필드에 값이 없으면 `null`을 반환하는 경우가 있다. 저장과 `validate()`는 원본 스키마를 쓰므로, `{"type": "string"}`처럼 null을 허용하지 않는 optional 필드에 `null`이 들어오면 `validate()`가 타입 오류를 낸다.

`_drop_null_optionals(value, schema)`가 `extract()`에서 provider 응답을 받은 직후 원본 스키마 기준으로 적용된다. object의 `properties`와 array의 `items`를 재귀적으로 순회하면서 "값이 `None`이고 원본 스키마의 `required`에 없고 원본 스키마 `type`이 null을 허용하지 않는" 리프를 `result`에서 지운다. required인데 null인 값은 그대로 둬서 `validate()`가 잡게 한다.

지워진 리프의 `path`는 더 이상 `result`에 존재하지 않으므로, `_pointer_value`가 "없음"과 "값이 명시적으로 null"을 구분할 수 있도록 sentinel(`_MISSING`)을 반환한다. `extract()`는 grounding을 순회하며 `_pointer_value`가 `_MISSING`이면 그 grounding 항목 자체를 결과 트리(`_grounding_tree`)에 넣지 않는다.

## 변경 파일

- `backend/engine.py` — `_provider()`를 `response_schema` 인자 없이 항상 `json_object`로 단순화(`_strict_schema`·`require_parameters` 분기 삭제), `_block_lines`, `_drop_null_optionals`(docstring을 strict 언급 없이 "optional 필드 null 제거" 취지로 수정), `_pointer_parts`/`_pointer_value`(+`_MISSING` sentinel), `extract()`를 `result`/`groundings` 방어 로직과 함께 재구성
- `tests/test_ai.py` — `_provider()`가 항상 `response_format: json_object`로 요청하는지 검증(strict/`require_parameters`/`_strict_schema` 테스트는 삭제)
- `tests/test_ai_provider.py` — 블록 id grounding이 `page`/`bbox`/`source_text`를 채우는지, 요청 body가 `json_object`인지, 블록 목록이 블록 경계에서 잘리는지, optional null 필드가 결과에서 빠지고 `validate()`에 타입 이슈가 없는지, grounding이 누락되거나 기형이어도(`path` 없음·`confidence` 비숫자·비-dict 항목) `extract()`가 방어적으로 처리하는지, `result`가 없으면 명시적 `RuntimeError`를 내는지 검증

## 재현 테스트 (2026-09-21)

사고 문서(`2303314528.png`, 블록 3개, 표 16행) + 스키마 `a23d4d53…` + `qwen/qwen3-vl-32b-instruct`로 직접 재현했다. 상세 실험 표는 [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "재현 테스트로 확인한 실제 원인" 절에 있다. 요지: strict `json_schema`는 이 provider에서 키 정렬을 강제해 컬럼이 밀리고 degeneration 루프로 이어졌다(130초, 파싱 실패). `json_object` + 현재 계약은 200초에 16행 모두 정확했고 `validate()` 이슈가 없었다.

최종 코드로 다시 돌렸을 때 추출은 성공했지만 grounding 199개의 `page`/`bbox`가 모두 null이었다. 모델이 블록 id를 `"block": "1"`처럼 문자열로 돌려줬고 서버는 정수만 받았기 때문이다. `"1"`, `"[1]"` 형태의 id도 정수로 읽도록 고친 뒤에는 152초에 16행 정확, grounding 199개 전부 `bbox`가 채워졌고 `validate()` 이슈는 0건이었다.

## 테스트 결과

```
python -m pytest tests -q --ignore=tests/ui_smoke.py --ignore=tests/ui_preview_layout.py --ignore=tests/ui_project_workspace.py
33 passed
```

## 남은 한계

[extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응 > 남은 후보" 절에 정리했다. 요약하면: grounding 생성이 응답 시간의 대부분을 차지하고 재현 문서에서는 정보량이 낮아 서버 측 계산 방식 검토가 필요하며, 단일 블록이 예산을 초과하면 이후 블록이 모두 빠지고, 범위 밖 `block` id는 로깅 없이 조용히 `null` 처리되며, `_provider()`의 httpx `timeout=90`초는 실험 4의 실응답 200초보다 짧다.
