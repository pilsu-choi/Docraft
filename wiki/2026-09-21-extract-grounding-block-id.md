---
type: Implementation Log
title: "추출 grounding 블록 id 전환과 strict 스키마 계약 정합"
description: "extract() grounding을 블록 id 참조로 바꾸고, strict 스키마 정규화가 만드는 optional null을 결과에서 제거해 저장·검증 계약을 맞춘 기록"
tags: [backend, extraction, ai-provider, grounding]
generated: {by: claude-code/claude-fable-5-1, at: 2026-09-21}
status: stable
---

# 추출 grounding 블록 id 전환과 strict 스키마 계약 정합

[extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md) 사고의 후속 대응으로 `backend/engine.py`의 `extract()` 계약을 바꿨다. 목표는 VLM 응답 크기와 escape 위험을 줄이고, structured output이 실제로 강제되도록 스키마를 정규화하는 것이다.

## 변경 내용

### 1. grounding을 블록 id 참조로 전환

기존에는 모델이 grounding마다 `source_text`·`page`·`bbox`를 직접 베껴 반환했다. 이제 모델은 `{path, confidence, block}`만 반환하고, 서버가 `extract()`에서 `block` id로 원본 블록을 찾아 `page`·`bbox`를 채우고 `path`로 `result`를 읽어 `source_text`를 채운다(`_pointer_value`). `block`이 범위를 벗어나면 `page`/`bbox`는 `null`로 남는다. 모델이 긴 문자열을 직접 옮겨 적지 않으므로 escape 오류로 JSON이 깨질 위험이 줄어든다.

### 2. 모델 입력 블록 단위 직렬화·예산 자르기

소스 블록을 JSON 배열 대신 `[id] text` 줄로 직렬화한다(`_block_lines`). 문자 예산(기본 40000자)을 넘기면 그 지점부터 블록을 통째로 잘라내고 `logger.warning`으로 몇 번째 블록에서 잘렸는지 남긴다. 블록 하나가 예산보다 크면 그 블록부터 이후가 전부 빠진다는 한계가 있다.

### 3. strict 스키마 정규화 + OpenRouter `require_parameters`

`_strict_schema`가 사용자 스키마를 재귀적으로 순회하며 모든 object에 `additionalProperties: false`를 붙이고 `properties`의 모든 키를 `required`에 넣는다. 원래 optional이던 필드는 `type`에 `"null"`을 추가해 nullable로 만든다(예: `{"type": "string"}` → `{"type": ["string", "null"]}`). `base_url`에 `openrouter`가 포함되면 요청 body에 `provider: {require_parameters: true}`를 추가해, OpenRouter가 고른 하위 provider가 `response_format`을 무시하지 못하게 한다.

### 4. optional null 결과 제거 (계약 불일치 수정)

strict 정규화 때문에 모델은 원래 optional인 필드도 값이 없으면 `null`을 반환한다. 그런데 저장과 `validate()`는 **원본**(비-strict) 스키마를 쓰므로, `{"type": "string"}`처럼 null을 허용하지 않는 optional 필드에 `null`이 들어오면 `validate()`가 타입 오류를 낸다.

`_drop_null_optionals(value, schema)`를 추가해 `extract()`가 provider 응답을 받은 직후 원본 스키마 기준으로 적용한다. object의 `properties`와 array의 `items`를 재귀적으로 순회하면서 "값이 `None`이고 원본 스키마의 `required`에 없고 원본 스키마 `type`이 null을 허용하지 않는" 리프를 `result`에서 지운다. required인데 null인 값은 그대로 둬서 `validate()`가 잡게 한다.

지워진 리프의 `path`는 더 이상 `result`에 존재하지 않으므로, `_pointer_value`가 "없음"과 "값이 명시적으로 null"을 구분할 수 있도록 sentinel(`_MISSING`)을 반환하게 바꿨다. `extract()`는 grounding을 순회하며 `_pointer_value`가 `_MISSING`이면 그 grounding 항목 자체를 결과 트리(`_grounding_tree`)에 넣지 않는다.

## 변경 파일

- `backend/engine.py` — `_strict_schema`, `_block_lines`, `_drop_null_optionals`, `_pointer_parts`/`_pointer_value`(+`_MISSING` sentinel), `extract()` 재구성, OpenRouter `require_parameters`
- `tests/test_ai.py` — OpenRouter에서만 `provider.require_parameters`가 붙는지, `_strict_schema`가 optional을 required+nullable로 바꾸는지 검증
- `tests/test_ai_provider.py` — 블록 id grounding이 `page`/`bbox`/`source_text`를 채우는지, 블록 목록이 블록 경계에서 잘리는지, optional null 필드가 결과에서 빠지고 `validate()`에 타입 이슈가 없는지 검증

## 테스트 결과

```
python -m pytest tests -q --ignore=tests/ui_smoke.py --ignore=tests/ui_preview_layout.py --ignore=tests/ui_project_workspace.py
33 passed
```

## 남은 한계

[extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "남은 후보" 절에 정리했다. 요약하면: 파싱 실패 재시도는 `temperature=0`이라 효과가 낮아 보류했고, 단일 블록이 예산을 초과하면 이후 블록이 모두 빠지며, 범위 밖 `block` id는 로깅 없이 조용히 `null` 처리되고, 사고를 낸 실제 문서(`2303314528.png`)로 재현 테스트는 아직 하지 않았다.
