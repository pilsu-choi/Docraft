---
type: decision
title: "사고 모드 끄기 — vLLM enable_thinking과 json_schema 호출 포함"
description: "AI_REASONING=off가 OpenRouter reasoning만 보내 자체 vLLM과 json_schema(band·rowmajor) 호출에서는 사고 모드가 꺼지지 않던 문제를, 모든 호출에 reasoning과 chat_template_kwargs.enable_thinking=false를 함께 보내도록 고침"
tags: [docraft, ai, vllm, openrouter, reasoning, config, qwen3.8]
status: active
---

# 사고 모드 끄기 — vLLM enable_thinking과 json_schema 호출 포함

- 날짜: 2026-10-13
- 저장소: Docraft
- 브랜치: `fix/thinking-off`
- 워크트리: `Docraft/.worktrees/thinking-off`

## 배경

배포 담당 세션이 서버 `.env.aws`에 `AI_REASONING`이 없어 기본값 `off`이고, 그래서 json_object 호출에 `reasoning: {"enabled": false}`가 붙는다고 알려 왔다. 사용자는 앞으로 추출 VLM을 `qwen3.8-27b`(사고 모드가 있는 모델)로 바꿀 계획이다.

## 근본 원인

`engine._provider()`가 사고 모드를 끌 때 쓰는 수단은 OpenRouter의 `reasoning` 하나뿐이었고, 그마저 json_object 호출에만 붙였다.

1. **자체 vLLM**: vLLM Chat Completions는 `reasoning` 필드를 모르는 값으로 보고 무시한다. vLLM에서 Qwen 사고 모드를 끄는 방법은 `chat_template_kwargs: {"enable_thinking": false}`다. 고객사(자체 vLLM)에서 사고 모델을 쓰면 `AI_REASONING=off`여도 사고 모드가 켜진 채로 돈다.
2. **json_schema 호출**(band·rowmajor 표 읽기): `require_parameters`와 `reasoning`을 같이 보내면 qwen3-vl-instruct에서는 404가 나서 `reasoning`을 빼 두었다. 이 때문에 사고 모델은 표 호출에서 사고 모드가 켜졌다. [OpenRouter VLM 모델 비교](../../wiki/2026-10-12-openrouter-vlm-model-compare.md)에서 "생각 끔"을 시험할 때 컨테이너 코드를 임시로 고쳐야 했던 이유가 이것이다.

문제 유형: **설정한 사고 끄기가 일부 서버(vLLM)·일부 호출 경로(json_schema)에 전달되지 않음.**

## OpenRouter 실측 (2026-10-13, 작은 JSON 프롬프트)

| 모델 | 보낸 필드 (json_schema + require_parameters) | 결과 | reasoning_tokens |
|---|---|---|---|
| qwen3.8-27b | `reasoning:{enabled:false}` | 200, 2.8초 | 0 |
| qwen3.8-27b | `chat_template_kwargs` 만 | 200 | 35 (무시됨) |
| qwen3.5-27b | `reasoning:{enabled:false}` | 200, 0.5초 | 0 |
| qwen3.5-27b | `chat_template_kwargs` 만 | 200, 15초 | 1378 (무시됨) |
| qwen3-vl-30b-a3b-instruct | `reasoning:{enabled:false}` | **404** No endpoints | – |
| qwen3-vl-30b-a3b-instruct | `chat_template_kwargs` 만 | 200 | 0 |

- OpenRouter는 `chat_template_kwargs`를 무시한다. 어느 모델에 붙여도 오류는 나지 않는다.
- `qwen/qwen3-vl-32b-instruct`는 OpenRouter에서 **2026-10-09 지원 종료**로 404가 난다(제안 대체 모델 `qwen/qwen3.7-plus`). 로컬 `.env`와 `.env.aws.example`의 기본 모델이 이것이므로, OpenRouter를 쓰는 환경은 모델을 바꿔야 한다. 고객사 자체 vLLM 서빙(Qwen3-VL-32B-Instruct)은 영향이 없다.

## 변경 (`backend/engine.py` `_provider`)

- `AI_REASONING=off`(기본)이면 json_object·json_schema **모든 호출**에 `reasoning: {"enabled": false}`와 `chat_template_kwargs: {"enable_thinking": false}`를 함께 넣는다. 각 서버는 다른 서버용 필드를 무시한다.
- `on`이면 두 필드를 모두 보내지 않는다(모델 기본값 유지).
- 바뀐 동작: OpenRouter에서 **사고 모드가 없는 모델**(qwen3-vl-*-instruct 등)을 쓰면 json_schema 호출이 404가 나므로 `AI_REASONING=on`으로 둬야 한다. 자체 vLLM의 Instruct 모델은 템플릿에 없는 `enable_thinking`을 무시하므로 `off` 그대로 쓴다.
- 주석·문서: `backend/config.py`, `.env.example`, README 환경변수 표.

## 테스트

- `tests/test_rowmajor.py::test_json_schema_calls_require_the_parameter_and_turn_thinking_off_on_both_servers`: json_schema·json_object 두 경로 모두 두 필드가 실리는지 확인한다(이전 이름은 `..._leave_out_reasoning`).
- `tests/test_ai_provider.py`: 기본 off이면 두 필드가 실리고, on이면 둘 다 빠지는지 확인한다.
- `pytest tests/test_ai_provider.py tests/test_rowmajor.py`: 184 passed.
- 자체 vLLM 실기 확인은 아직 하지 않았다. qwen3.8-27b를 vLLM으로 서빙할 때 배포 담당 세션에서 `reasoning_tokens`나 `<think>` 출력 여부를 확인해야 한다.

## 남은 일

- 서버·로컬 `.env`의 `AI_VLM_MODEL`이 OpenRouter `qwen3-vl-32b-instruct`라면 교체해야 한다.
- qwen3.8-27b로 갈아탈 때 vLLM에 `--reasoning-parser`를 쓰지 않으면, 사고 모드가 켜진 상태에서 `<think>` 블록이 content에 섞여 JSON 파싱이 실패한다. `off` 기본값을 유지한다.
