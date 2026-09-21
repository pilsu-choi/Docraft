---
type: Incident
title: "추출 실패: VLM 응답 JSON 파싱 오류"
description: "VLM 추출 응답 JSON 파싱 실패(Expecting ',' delimiter)의 원인 분석(재현 테스트로 strict json_schema가 원인임을 확인)과 최종 대응"
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

### 재현 테스트로 확인한 실제 원인 (2026-09-21)

사고를 낸 바로 그 문서(`2303314528.png`, 블록 3개: 제목 text 1 + table 2, 표 전체가 블록 1 하나) + 스키마 `a23d4d53…` + `qwen/qwen3-vl-32b-instruct`(OpenRouter가 Alibaba provider로 라우팅)로 직접 재현했다. 위 추정 2·3번은 부분적으로 틀렸다: 진짜 원인은 "따옴표 escape 누락"이 아니라 **Alibaba provider의 strict `json_schema` constrained decoding 자체가 출력을 망가뜨리는 것**이었다.

| # | 실험 | 결과 |
|---|------|------|
| 1 | 당시 코드(strict `json_schema` + `require_parameters`)로 재현 | 실패. `Unterminated string … (char 18262)`, `finish_reason=stop`, 130초. 응답은 키가 알파벳/코드포인트 순으로 정렬돼 `groundings`(204개, 전부 block 1·confidence 1.0)가 `result`보다 먼저 나오고, `result` 첫 행에서 `"일자": "AA254"`(오추출) 후 `"횟수": "1.0000…"` 0이 411개 반복되는 degeneration 루프로 끊겼다 |
| 2 | strict `json_schema`로 `result`만 요청 | 5초 만에 파싱은 되지만 1행짜리 전부 빈 문자열 — 쓰레기 출력 |
| 3 | `response_format: json_object`로 `result`만 요청 | 41초, 16행 전부 정확(숫자도 number 타입, 컬럼 순서 유지) |
| 4 | `json_object` + `result`/`groundings` 계약(프롬프트로 형식만 지시) | 200초, 16행 정확, `validate()` 이슈 0, `page`/`bbox` 정상 채워짐 |

결론: strict `json_schema`는 이 provider에서 키 정렬을 강제해 컬럼이 밀리고, 모델이 그 어긋난 상태를 메우려다 반복 루프에 빠져 JSON을 끊어 먹는다. `response_format`을 `json_object`로 바꾸고 출력 계약을 프롬프트로만 지시하는 쪽이 이 provider에서는 훨씬 안정적이다. strict 정규화(실험 3의 추정 #3)는 "적용 안 됐을 수도" 정도가 아니라 **적용됐고, 그 자체가 해로웠다**.

## 대응

최종 적용 상태는 [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)에 기록했다. 요약하면:

- **적용됨**
  - `extract()`를 `response_format: json_object`로 전환하고, 응답 JSON object 자체가 스키마를 따르는 결과(래핑 키 없음, 필드 순서 유지)라는 계약을 system prompt로 지시.
  - grounding은 모델에 요청하지 않고 **서버가 계산한다**. `result`의 모든 leaf에 대해 값 문자열을 원문 블록에서 찾아 `page`·`bbox`를 채우고, 못 찾으면 `confidence: 0.0`으로 남겨 `validate()`가 `low_confidence` 이슈로 드러내게 한다. 비교는 양쪽 모두 공백·쉼표를 제거한 정규화 문자열의 부분 문자열 포함이다.
  - 모델 입력을 블록 단위로 평문화·예산 자르기(`_block_lines`, 기본 40000자).
  - optional 필드가 `null`로 오면 원본 스키마 기준으로 결과에서 제거(`_drop_null_optionals`).
- **철회됨** (재현 테스트로 해로움이 확인돼 제거)
  - strict `json_schema` 정규화(`_strict_schema`)와 OpenRouter `provider.require_parameters: true`. 둘 다 Alibaba provider에서 키 정렬 강제 → 컬럼 오정렬 → degeneration 루프로 이어져 삭제했다.
  - 모델에게 `{path, confidence, block}` grounding을 받는 중간 단계. 응답 시간이 41초 → 150~200초로 늘고, 돌아온 grounding 204개가 전부 block 1·confidence 1.0이라 정보량이 없었으며, 모델이 block id를 문자열로 주면 조용히 `page`/`bbox`가 `null`이 됐다. 서버 측 계산으로 대체한 뒤 같은 문서가 61초에 leaf 199개 전부 `bbox` 채워짐·이슈 0건으로 끝났다.
- **남은 후보**
  - grounding 해상도가 OCR 블록 단위라, 표 전체가 블록 하나인 이 문서에서는 모든 leaf가 같은 `bbox`를 가리킨다. 셀 단위 근거는 파서가 블록을 더 잘게 나눠야 가능하다.
  - 부분 문자열 매칭이라 `0`, `1` 같은 짧은 값은 블록이 여러 개인 문서에서 엉뚱한 블록에 먼저 걸릴 수 있다.
  - `_block_lines`는 예산을 넘는 블록 하나를 만나면 그 지점에서 멈추므로, 그 블록 자체가 예산보다 크면 이후 블록이 전부 빠진다.
  - `_provider()`의 httpx `timeout=90`초는 현재 응답(61초)에는 여유가 있지만, 표가 더 긴 문서에서는 다시 빠듯해질 수 있다.
