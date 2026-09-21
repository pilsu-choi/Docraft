---
type: Incident
title: "추출 실패: VLM 응답 JSON 파싱 오류"
description: "VLM 추출 응답 JSON 파싱 실패(Expecting ',' delimiter)의 원인 분석과 대응 후보"
tags: [extraction, ai-provider, incident]
generated: {by: claude-code/claude-fable-5-1, at: 2026-09-21}
status: stable
---

# 추출 실패: VLM 응답 JSON 파싱 오류

## 2026-09-21 발생

- 문서 `6b9d27e71b264cd19107a360e86d29d5` (`2303314528.png`, 진료비 세부산정내역, 4.2MB)
- 스키마 `a23d4d5314244de1b030b19ac3d31b0a` (최상위 필드 2개 + `항목정보` 배열 1개, 배열 항목당 필드 12개)
- 모델 `qwen/qwen3-vl-32b-instruct` (OpenRouter)
- `POST /extract` 요청은 `202 Accepted`로 받아들여졌다. 화면은 1.8초마다 상태를 조회하며 기다렸고, 13:46:16 UTC에 상태가 `failed`로 바뀌었다.

```
추출 실패: Expecting ',' delimiter: line 1426 column 242 (char 30760)
```

OCR 결과(`markdown`)에는 표 전체가 정상으로 들어 있었다. 실패한 곳은 `backend/engine.py`의 `_provider()`가 VLM 응답을 `json.loads`로 읽는 단계였다.

## 원인 분석

그 당시 서버는 모델의 원본 응답을 로그에 남기지 않아 직접 확인할 수 없었다. 아래는 정황을 바탕으로 한 추정이다.

1. **응답이 원래 크다.** `extract()`는 값이 들어가는 모든 필드(leaf)마다 `groundings` 항목(`path`, `confidence`, `source_text`, `page`, `bbox`)을 요구한다. 이 문서는 표 16행 × 12필드라서 grounding이 약 200개가 된다. 모델이 이를 들여쓰기 포함 JSON으로 출력하면 1400줄, 30KB 정도가 된다. 처음에는 모델이 같은 내용을 반복했다고 의심했지만, 응답 크기만으로는 반복을 단정할 수 없다.
2. **따옴표 escape 누락 가능성이 높다.** OCR 블록 텍스트에는 `<td colspan="2">` 같은 HTML 표 마크업이 들어 있다. 모델이 이 텍스트를 `source_text`에 옮기면서 `"`를 escape하지 않으면 `Expecting ',' delimiter`가 발생한다. 오류 위치가 242열인 것도 긴 `source_text` 줄 한가운데라는 점과 맞는다.
3. **structured output이 강제되지 않았을 수 있다.** 요청에 `response_format: json_schema, strict: true`를 넣지만 사용자 스키마에는 `additionalProperties: false`가 없고, 필드 대부분에 `type`도 없으며, 모든 필드가 `required`인 것도 아니다. 따라서 OpenRouter의 하위 provider가 strict decoding을 적용하지 않거나 무시했을 수 있다. 강제됐다면 JSON 문법이 깨지는 일은 없어야 한다.
4. `finish_reason == "length"`로 잘린 경우는 아니다. 그랬다면 "토큰 제한으로 잘렸습니다" 오류가 났어야 한다.

## 대응

- 백엔드 로깅을 추가했다([logging-docker](2026-09-21-logging-docker.md)). 이제 `_provider()`가 JSON 파싱 실패 시 응답 길이, `finish_reason`, 원본 응답의 앞뒤 일부를 ERROR로 남기므로 같은 오류가 다시 나면 `docraft.log`에서 원인을 바로 확인할 수 있다.
- 아래 네 가지를 적용했다([extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)).
  - **grounding을 블록 id 참조로 바꿨다.** 모델은 더 이상 `source_text`·`page`·`bbox`를 직접 베끼지 않고 `{path, confidence, block}`만 반환한다. `page`·`bbox`는 서버가 `block` id로 원본 블록을 찾아 채우고, `source_text`는 서버가 `path`로 `result`에서 값을 읽어 채운다. escape가 필요한 긴 문자열을 모델이 직접 옮겨 적을 일이 없어졌다.
  - **모델 입력을 블록 단위로 평문화·예산 자르기했다.** 소스 블록을 JSON 배열 대신 `[id] text` 줄로 직렬화하고(`_block_lines`), 문자 예산(기본 40000자)을 넘기면 그 지점 이후 블록을 통째로 잘라 로그에 경고를 남긴다.
  - **사용자 스키마를 strict 호환 형태로 정규화해서 보낸다.** `_strict_schema`가 모든 object에 `additionalProperties: false`와 전체 `required`를 채우고, 원래 optional이던 필드는 `type`에 `null`을 추가해 nullable로 만든다. OpenRouter로 보낼 때는 `provider.require_parameters: true`를 추가해 하위 provider가 strict decoding을 무시하지 못하게 한다.
  - **optional 필드가 null로 오면 결과에서 제거한다.** strict 정규화 때문에 모델이 원래 optional인 필드를 `null`로 채워 보내는데, 저장·`validate()`는 원본(비-strict) 스키마를 쓰므로 그 null이 `{"type": "string"}` 같은 non-nullable 필드에 들어가면 타입 오류가 난다. `_drop_null_optionals`가 응답을 원본 스키마와 대조해 "null이고 required가 아니며 원본 스키마가 null을 허용하지 않는" 리프를 재귀적으로 지운다. required인데 null인 값은 그대로 둬서 `validate()`가 잡게 한다. 지워진 리프에 대한 grounding 항목도 트리에 남기지 않는다.
- 남은 후보(보류):
  - 파싱 실패 시 한 번 재시도하는 안은 `temperature=0`이라 같은 오류가 그대로 재현될 가능성이 높아 보류했다.
  - `_block_lines`는 예산을 넘는 블록 하나를 만나면 그 지점에서 멈추므로, 그 블록 자체가 예산보다 크면 이후 블록이 전부 빠진다(블록 내부를 잘라 이어 보내는 방식은 아님).
  - 응답의 `block` id가 범위를 벗어나면 `page`/`bbox`가 조용히 `null`로 채워질 뿐, 별도 로깅은 없다.
  - 이번 사고를 낸 문서(`2303314528.png`, 스키마 `a23d4d5314244de1b030b19ac3d31b0a`)로 실제 재현 테스트는 아직 하지 않았다. 위 대응은 코드 수준 계약 테스트로만 검증됐다.
