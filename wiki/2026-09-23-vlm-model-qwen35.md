---
okf_version: "0.2"
type: Implementation Log
title: "추출 VLM qwen3.5-27b 전환과 AI_REASONING"
description: "추출 VLM을 qwen/qwen3.5-27b로 바꾼 배경과 OpenRouter 확인, 기본 사고 모드로 인한 10배 지연 실측, AI_REASONING 설정으로 사고 모드를 끄는 구현"
tags: [backend, ai, vlm, openrouter, reasoning, config]
generated: {by: claude-code/claude-sonnet-5, at: 2026-09-23}
status: active
---

# 추출 VLM qwen3.5-27b 전환과 AI_REASONING

- 날짜: 2026-09-23
- 브랜치: `feat/ai-reasoning`
- 워크트리: `.worktrees/ai-reasoning`

## 배경

추출·스키마 생성에 쓰는 기본 VLM을 이전 `qwen/qwen3-vl-32b-instruct`에서 `qwen/qwen3.5-27b`로 바꿨다(사용자 결정, 커밋 `a237484` 설정: 추출 VLM 기본 모델을 qwen/qwen3.5-27b로 변경). 이 문서는 그 전환에서 확인한 provider 계약과, 전환 직후 드러난 사고(reasoning) 모드 지연 문제 및 대응(`AI_REASONING`)을 함께 기록한다.

## OpenRouter 확인 (모델 전환 시점)

- slug `qwen/qwen3.5-27b`가 OpenRouter 목록에 존재하고 이미지 입력(vision)과 `response_format: json_object`를 지원한다.
- 컨텍스트 길이 262k 토큰.
- 단가(입력/출력, $ per M 토큰): `qwen3.5-27b` $0.195 / $1.56, 이전 `qwen3-vl-32b-instruct` $0.104 / $0.416. 입력 기준 약 1.9배, 출력 기준 약 3.75배 비싸다.
- 엔진 호출로 실제 JSON 응답을 검증해 계약(스키마 필드, `response_format` 처리)에 문제가 없음을 확인했다.

## 문제: 기본 사고 모드로 인한 10배 이상 지연

전환 후 실제 문서 추출 호출이 222~541초로 걸려, 이전 모델의 10~30초 대비 10배 이상 느려졌다. 원인은 `qwen3.5-27b`가 사고(reasoning) 모드를 기본으로 켠 채 응답하기 때문이다.

### 실측

| 항목 | reasoning 기본(on) | `reasoning.enabled=false` |
| --- | --- | --- |
| 추출 호출 3건 소요 | 중앙값 222초, 최대 541초 | 1.7~16초 |
| 작은 프롬프트 `reasoning_tokens` | 135 | 0 |
| JSON 응답 내용 | 정상 | 정상(동일) |

요청 본문에 `"reasoning": {"enabled": false}`를 넣으면 `reasoning_tokens`가 0이 되고 소요 시간이 이전 모델 수준(1.7~16초)으로 돌아오며, JSON 응답 내용도 정상이다. 이전 모델 `qwen/qwen3-vl-32b-instruct`(reasoning 미지원)로 같은 파라미터를 보내도 200 OK가 돌아온다 — OpenRouter가 미지원 모델에서는 이 필드를 무시한다.

### provider 편차

OpenRouter가 `qwen/qwen3.5-27b` 요청을 SiliconFlow·Novita·AtlasCloud 등 여러 upstream provider로 라우팅한다. 어느 provider가 선택되는지에 따라 지연 편차가 크게 났다(위 222~541초 범위도 이 라우팅 차이를 포함한다). 한 번은 빈 응답(`{}`)이 온 사례가 있었으나 재시도에서 정상 JSON으로 돌아왔다 — 특정 upstream의 일시적 불안정으로 보고 별도 대응 없이 기존 재시도(`httpx.HTTPTransport(retries=2)`)에 맡긴다.

## 구현: `AI_REASONING`

- `backend/config.py`의 `ai_settings()`에 `AI_REASONING`(`off`(기본)/`on`)을 추가했다. `off`면 `reasoning: False`를 반환한다.
- `backend/engine.py`의 `_provider()`에서 설정이 `off`일 때만 요청 본문에 `"reasoning": {"enabled": False}`를 넣는다. `on`이면 아무것도 넣지 않아 모델·provider 기본값을 그대로 둔다. 이 필드는 OpenRouter 표준 파라미터이며 조건은 설정값 하나만 보고, provider별 분기는 두지 않는다 — reasoning을 지원하지 않는 provider·모델은 필드를 무시하므로 안전하다.
- 응답의 `message.reasoning`이 있어도 `content`만 쓰는 기존 로직은 그대로 둔다(사고 내용을 결과에 섞지 않음).
- `tests/test_ai_provider.py`에 `AI_REASONING` 미설정(기본 off)·`on` 두 경우 요청 본문을 검증하는 테스트 2건을 추가했다. 전체 294 passed.

### 설정 파일

`.env.example`, `deploy/aws/.env.aws.example`에 `AI_REASONING=off`를 추가하고, README 환경변수 표에 `AI_REASONING` 행을 더했다.

## 76건 기준선 결과

`AI_REASONING=off` 상태에서 76건을 재추출해(`data/verify/accuracy-20260922/model-qwen35`, 같은 parse 캐시 복사 후 추출만 재실행) 최종 코드·최종 라벨로 이전 모델과 같은 조건에서 채점했다.

| 지표 (rules 단계, 76건 9,238셀) | 이전 `qwen3-vl-32b-instruct` | 새 `qwen3.5-27b` |
| --- | --- | --- |
| correct | 8,794 (95.2%) | 8,569 (92.8%) |
| strict | 7,764 (84.0%) | 7,411 (80.2%) |
| fp | 330 | 321 |
| 추출 호출 지연 | 10~30초(과거 기록) | 중앙값 36.9초·p90 105초·최대 268초 |

사고 모드를 껐는데도 지연 중앙값이 이전 모델보다 높고(사고 모드 on일 때의 222초보다는 훨씬 낫다), 정확도는 유형 전반에서 낮다. 다만 fp는 소견서 14→4 등으로 줄어 환각 억제는 새 모델이 낫다. 유형별·existing/holdout 표, 뒤진 원인 상위 5개, 단가 대비 해석과 권고는 [label-alignment-and-model-compare](2026-09-23-label-alignment-and-model-compare.md)에 정리했다.

## 남은 과제

모델 전환 여부 결정은 사용자에게 보류돼 있다. 현 벤치마크 기준으로는 정확도·지연·단가 모두 이전 모델이 우세하므로 별도 전환 사유가 없으면 `qwen/qwen3-vl-32b-instruct` 유지를 권고한다 — 근거와 반대 근거는 [label-alignment-and-model-compare](2026-09-23-label-alignment-and-model-compare.md) "권고" 절 참고.
