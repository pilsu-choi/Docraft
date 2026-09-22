---
type: Plan
title: "Agentic OCR 2.0 결과 교차검증·자동 교정 API 계획"
description: "Docraft Parse→twin reader 룰→Extract 결과와 Agentic OCR 2.0 응답을 LLM-as-Judge로 비교해 필드별로 선정·교정한 JSON을 돌려주는 API의 작업 지시서"
tags: [plan, agentic-ocr, rule-base, llm-judge, api, harness-v2]
status: draft
---

# Agentic OCR 2.0 결과 교차검증·자동 교정 API 계획

2026-09-22 · 브랜치 `docs/ocr-verify-plan` · 워크트리 `.worktrees/ocr-verify-plan`

`feedback.md` TODO의 "harness-v2 통합" 메모를 에이전트가 바로 착수할 수 있는 작업 지시서로 정리한 문서다. 구현은 별도 브랜치(`feat/ocr-verify` 등)에서 진행한다.

## 1. 배경과 목적

- **Agentic OCR 2.0**(이하 AO)은 Parse(OCR) 후 LLM key-value 매핑으로 Extract 결과 JSON을 내는 제품이다.
- **Docraft**는 같은 문서를 독립적으로 Parse·Extract해 AO 결과를 **검증·보정**하는 것이 목적이다.
- 현재 Docraft의 LLM Extract는 key-value 오매핑이 있어, **룰 기반 후처리(twin reader plugin 방식)**를 더해 정확도를 보강한다.
- 최종 산출물: **이미지 + AO 응답 JSON을 받아 자동 교정된 JSON을 반환하는 API**.

## 2. 목표 파이프라인

```
입력: 문서 이미지 + AO 응답 JSON
  ① Docraft Parse (OCR)
  ② 문서 유형별 rule-base schema/plugin 적용   ← twin reader plugin 이식·확장
  ③ Docraft Extract → Docraft JSON
  ④ LLM-as-Judge: 이미지 + AO JSON + Docraft JSON → 필드별로 더 정확한 값 선정/교정
  ⑤ 교정된 최종 JSON 반환 (필드별 판정 근거 포함)
```

harness-v2 통합 시에는 **harness 룰 검증에서 `status: failed`인 건만** 이 API로 보낸다. 이번 범위는 API 단건 호출 동작까지다.

## 3. 참고 자료

| 구분 | 경로 | 내용 |
|---|---|---|
| AO 응답 예시 (API 입력 포맷) | `/home/pilsu/projects/mirae-assets/harness-v2/docs/agentic-ocr-2.0.1-results/<문서유형>/` | 7종(세부내역서·소견서·수술확인서·약제비영수증·입퇴원확인서·진단서·진료비영수증), 유형별 이미지 1장 + `*.classification.<uuid>.json`. 핵심 필드: `documents[].extracted_fields[]`의 `key`, `value`, `confidence`, `predicted_value` |
| twin reader plugin (JS) | `refs/postprocess_schema_example/20260828_v1.1/plugin/미래에셋생명_고도화/` | 진료비영수증, 진단서_5종(진단서·소견서·수술확인서·입원확인서·진료확인서), 진료비세부내역서, 약제비영수증. `항목리스트.json`, `*_plugin.js`, `pluginUtil_*.js`, `format_*.js` |
| twin reader schema | `refs/postprocess_schema_example/20260828_v1.1/schema/미래에셋생명_고도화/` | 유형별 `*_main.json` |
| twin reader 결과 예시 | `refs/postprocess_schema_example/20260828_v1.1/json/반출_<유형>/` | `PageN.metaData` + `values[]` 구조, 유형별 약 3건 |
| 확장·검증 샘플 (repo) | `data/files/{진단서,소견서,진료비영수증,세부내역서}_samples/` | 145 / 78 / 137 / 1장 |
| 확장·검증 샘플 (Windows) | `/mnt/c/Users/user/Downloads/{진료비영수증,진료비세부산정내역서,진단서,소견서}-20260806T*-1-001/` | 약 4,828 / 823 / 451 / 100 파일 |
| (참고) 채점표 | `/mnt/c/Users/user/Downloads/0917_진단서4종_추출항목_채점표_문서별10장__통합본_진단일추가.xlsx` | 정답셋 활용 가능 여부 확인 필요 |

## 4. 세부 작업

### A. twin reader 룰 이식

- JS plugin의 룰(정규식·포맷 정규화·항목 매핑·후처리)을 분석해 Docraft backend에 Python으로 이식한다. 대상은 `extractionResultData.result`에 적용되는 로직이다.
- plugin 내부 LLM 호출(`llm/plugin_llm_*.js`)과 excel 경로 의존은 이식하지 않는다. 필요하면 Docraft 기존 LLM 경로로 대체한다.
- 항목명은 `항목리스트.json`을 기준으로 하고, AO `key`와의 매핑 표를 만든다.

### B. 룰 확장 (탐지 케이스 증대)

- 3절 샘플을 Docraft로 Parse해 기존 룰이 놓치는 패턴(날짜·금액 포맷, 라벨 변형, 병합 셀, 복합 테이블 등)을 수집하고 룰에 추가한다.
- 확장 전후 필드별 추출률·정확도를 비교할 수 있도록 측정 스크립트와 결과를 남긴다.
- Downloads 샘플은 양이 많으므로 유형별 표본을 뽑아 먼저 진행한다.

### C. LLM-as-Judge 비교·선정

- 입력: 이미지(또는 페이지 이미지), AO JSON, Docraft JSON.
- 필드별 판정: `{key, ao_value, docraft_value, final_value, source: "ao"|"docraft"|"corrected", reason}`.
- 두 값이 일치하는 필드는 LLM 호출 없이 확정한다(비용 절감).
- LLM은 기존 Docraft 설정의 LLM 클라이언트를 재사용한다.

### D. API

- 예: `POST /api/verify`. 이름·경로는 기존 `backend/main.py` 규칙을 따른다.
- **Request**: multipart로 `image` 파일 + `ao_result`(AO 응답 JSON 원문). 문서 유형은 AO 응답에서 추론하고, 불가하면 파라미터로 받는다.
- **Response**: AO 응답과 같은 구조(`extracted_fields[]`)에 교정된 `value`를 채우고, 필드별 판정 정보(`source`, `reason`, 원래 값)를 덧붙인다.
- 기존 인증(`Depends(auth)`)을 적용한다.

## 5. 완료 기준

- [ ] AO 결과 7종 예시 각각에 대해 API가 교정 JSON을 반환한다.
- [ ] 룰 확장 전후 필드별 정확도 비교표가 있다.
- [ ] `tests/`에 샘플 기반 테스트를 추가하고 통과한다.
- [ ] wiki 문서, `wiki/index.md`, `wiki/log.md`를 갱신하고 필요하면 README도 갱신한다.

## 6. 작업 규칙 (AGENTS.md 요약)

- 워크트리 `.worktrees/ocr-verify`, 브랜치 `feat/ocr-verify`에서 작업한다.
- 커밋은 한국어 접두사(`기능:` 등), main에는 `--no-ff` 병합 커밋을 남긴다.
- A(룰 이식·확장)와 C(Judge)는 인터페이스를 먼저 정하면 sub-agent로 병렬 진행할 수 있다.
- 비슷한 기능의 클래스·함수를 중복으로 만들지 않고 기존 extract 경로를 재사용한다.
- GPU가 부족하면 `harness-v2/deploy/aws`를 참고한다.

## 7. 미결 사항

1. **정답셋**: 0917 채점표 xlsx를 정답으로 써도 되는가, 아니면 LLM Judge 결과만으로 충분한가?
2. **범위**: 7종 전부인가, 샘플이 있는 4종(진단서·소견서·진료비영수증·세부내역서)부터인가?
3. **입력 단위**: 다중 페이지 문서(PDF·TIF)도 받아야 하는가, 이미지 1장인가?
