---
type: Test Record
title: "AI provider 검증 기록"
description: "OpenAI 호환 AI provider 계약 테스트와 OpenRouter Qwen 실호출 검증"
tags: [ai-provider, test]
status: stable
---

# AI provider 검증 기록

## 2026-09-21

- `tests/test_ai_provider.py`에 OpenAI 호환 provider 계약 테스트를 추가했다.
- 모든 테스트는 HTTP client를 mock하므로 외부 provider 비용이나 비밀값을 사용하지 않는다.
- 설정된 `AI_BASE_URL`, `AI_API_KEY`, `AI_VLM_MODEL` (`AI_MODEL` 호환)이 chat completions URL·Bearer 인증·model body에 반영되는지 검증한다.
- `AI_MODE=local`일 때만 로컬 heuristic 경로를 사용하고, provider 설정 누락·401·잘못된 JSON·추출 응답 오류는 로컬 fallback으로 숨기지 않는 계약을 검증한다.
- `finish_reason=length`인 잘린 응답은 유효 JSON처럼 처리하지 않아야 한다. backend의 명시적 오류 처리와 함께 테스트를 통과했다.
- OpenRouter 공개 모델 목록에서 기존 입력 slug가 없음을 확인하고 사용자 승인 후 `qwen/qwen3-vl-32b-instruct`로 변경했다.
- 비밀값을 출력하지 않는 합성 문서 1건으로 실제 schema 생성 연결을 검증했으며 object schema와 요청한 두 필드를 반환했다.
- 이미지와 스캔 PDF는 로컬 모델 없이 명시적으로 설정한 PaddleOCR full layout API만 사용한다. 일반 VLM을 PaddleOCR로 표시하거나 암묵적으로 대체하지 않는다.
- API 키 원문은 테스트·문서에 포함하지 않는다. 실제 설정은 ignored `.env`에만 두고 `.env.example`에는 빈 placeholder만 둔다.
- 실제 Qwen provider로 합성 TXT의 schema 생성과 structured extraction/grounding을 각각 확인했다.
- Chrome UI에서 TXT 업로드 → AI schema 생성 → 추출 → 수정 → 승인 → JSON 다운로드 흐름을 완료했고 `/tmp/docraft-ui-smoke.png`에 결과 화면을 남겼다.
- parsing 기본값은 `PARSE_PROVIDER=library`이며 이미지 OCR은 비활성이다. Paddle은 별도 on-prem `/layout-parsing` endpoint가 명시된 경우에만 사용하고 로컬 패키지나 모델을 설치하지 않는다.
