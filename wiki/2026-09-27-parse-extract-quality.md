---
okf_version: "0.2"
type: implementation
title: Parse·Extract 근거와 검토 상태 보강
description: OCR 원문 근거·행 관계·스키마 검사 결과를 필드별로 기록하고 76건 캐시의 오류 탐지와 오탐을 측정한 작업
tags: [parse, extract, provenance, validation, evaluation]
status: active
---

날짜: 2026-09-27  
브랜치: `feat/parse-extract-quality`  
워크트리: `Docraft/.worktrees/parse-extract-quality`

## 문제와 현재 흐름

Parse는 PDF 텍스트 레이어 또는 원격 PaddleOCR layout 결과에서 블록·표·좌표를 만든다. 선택적으로 PP-OCRv5 줄 좌표와 괘선 표 격자를 보강한다. Extract는 페이지별 VLM 결과를 합치고 OCR 행·줄에 값을 다시 연결한다. 일반 문서 API의 기존 검사는 JSON Schema와 `confidence < 0.7`뿐이었다. 의료문서 `/api/verify`는 `rules.run` 반복 교정·Judge 판정·최종 룰 재검사를 수행하지만, OCR 근거와 최종 값의 관계를 필드별 상태로 내보내지 않았다.

## 변경한 계약

- 근거의 `source_text`는 추출값의 복사가 아니라 실제 OCR 줄·표 셀·블록 원문이다. 출처가 없으면 `null`이다. 블록·행·열, 매칭 종류, 원본 페이지 크기도 근거에 둔다.
- `engine.assess`는 필드별 `status`(`PASS`, `SUSPICIOUS`, `UNRESOLVED`, 교정 뒤 `CORRECTED`), `issue_codes`, `action`(`ACCEPT`, `RECHECK`, `REVIEW`), `stage`, `provenance`를 계산한다. `stage: undetermined`는 Parse와 Extract 중 원인을 증거만으로 구별할 수 없다는 뜻이다.
- `/api/read`는 기존 `fields`와 `groundings` 외에 `field_quality`를 반환한다. 경로는 스칼라 `병원명`, 표 셀 `병명내역/0/열` 형식이다. `/api/verify`는 `documents[i].verify.field_quality`를 반환하고 최종 룰 검사 뒤의 이상을 합친다. 사람이 고친 일반 문서 값은 `CORRECTED`로 기록한다.
- `no_source`, OCR 근사 일치, 중복 위치, 명시된 key의 누락, 먼 label, 구조가 불확실한 행 충돌은 `RECHECK` 신호다. 스키마 위반, 페이지 밖 좌표, 괘선 표에서 검증된 행 불일치는 `REVIEW`다. 소프트 신호는 결과를 임의 교정하지 않는다. 일반 문서 API는 두 신호 모두 `needs_review`에 남겨 완료 상태와 미확정을 혼동하지 않게 한다. 이 선택은 자동 처리율을 낮춘다.
- PaddleOCR가 요청 페이지 수와 다른 페이지 수를 반환하면 일부 성공으로 숨기지 않고 ParseError를 낸다.

## 검증과 측정

전체 테스트 `546 passed`. 새 변형 테스트는 한 글자 오인식, 출처 부재·중복, 빈 값과 명시 key, 먼 label, 잘못된 행·페이지 좌표, 누락 페이지 응답을 포함한다.

기존 `accuracy-20260922`의 76건 Parse·raw Extract 캐시를 새 코드에서 다시 근거 연결해 평가했다. 이 캐시는 새 provenance를 기록한 결과가 아니므로 운영에서의 탐지율을 직접 증명하지 않는다. raw 단계의 동일한 라벨과 예측을 비교하면 스칼라 정답 798개 중 362개에 소프트 경고가 생겼고, 오답 72개 중 23개, 라벨이 빈데 값을 넣은 94개 중 55개에 경고가 생겼다. 스칼라 정답의 약 45%를 경고하는 현재 신호를 모두 자동 차단에 쓰면 처리율이 크게 떨어진다. 값이 OCR에 존재해도 다른 날짜·금액 역할을 고른 오류는 여전히 PASS일 수 있다. 전체 10,582 leaf 중 8,959 PASS, 나머지 1,623은 근거·관계·형식의 재확인 또는 검토 신호였다(괘선 근거가 없는 캐시의 행 충돌은 소프트 분류).

## 남은 한계

OCR 근거 일치는 이미지 픽셀의 정답을 보장하지 않는다. `PASS`는 구현된 검사 통과일 뿐 최종 정확성 인증이 아니다. OCR가 누락했지만 VLM이 올바르게 읽은 값은 `RECHECK`로 남는다. 같은 값이 문서의 다른 역할에도 인쇄된 경우 일반 근거 검사만으로 역할을 확정할 수 없다. 마스터·산술 관계는 기존 의료문서 룰이 다루는 범위에 한정된다. 자동 선택적 이미지 재확인과 그 결과의 독립 재검증, 영역 재파싱, 페이지 경계·표 연속성 검증, 고객 문서의 대규모 gold 평가는 완료되지 않았다. 이번 변경으로 정확도 97%를 달성했다고 주장하지 않는다.

## 관련 문서

- [Docraft 읽기 API](2026-09-27-read-api.md)
- [Harness와 Docraft 추출 흐름 점검](2026-09-27-harness-docraft-kv-pipeline-review.md)
- [wiki 색인](index.md)
