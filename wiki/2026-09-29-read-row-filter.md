---
okf_version: "0.2"
type: change
title: "/api/read row_filter: 빠진 행만 다시 읽기"
description: "표 전체 재읽기(약 1,800 토큰, L40S 100~160초) 대신 지정한 행만 모델이 생성하도록 /api/read 에 row_filter 를 추가했다"
tags: [docraft, read, row-filter, latency]
status: active
---

# /api/read row_filter

날짜: 2026-09-29 / 브랜치: `feat/read-row-filter` / 워크트리: `.worktrees/read-row-filter`

## 배경
harness 가 영수증에서 필수 행(진찰료·CT진단료)이 없으면 `keys=["항목내역"]` 으로 표 전체를 다시 읽는다. 24줄 표는 Qwen3-VL-32B 가 약 1,800 토큰을 생성해 L40S 에서 100~160초(decode 96%)가 걸린다.

## 변경
* `POST /api/read` 선택 폼 필드 `row_filter`: `{"표key": ["행 식별 값", ...]}` JSON 문자열. 행 식별 열은 표 첫 열(영수증·세부내역서 "항목").
* `verify.resolve_row_filter`: 형식 검증(틀리면 422), `keys` 밖·정의 밖 표 제거(정의 밖은 경고 1회).
* `verify._narrow_rows`: 모델에 주는 표 스키마 description 앞에 "항목 열 값이 [...] 중 하나인 행만 적고 나머지는 생략" 지시, `maxItems=len(목록)` 추가 → 생성 토큰 감소.
* `verify.read`: `rules.apply` 뒤 목록 밖 행을 걸러(모델이 지시를 어겨도 필터됨) 응답한다. 근거(groundings)는 행 내용 서명 매칭이라 부분 표에서도 유지된다.
* 재처리: 필터된 표는 행 단위 자동 재처리에서 제외(부분 표는 합계·행 검증이 성립하지 않음). 그 표만 요청하면 재처리가 건너뛰어져 `stop_reason: no_schema`. `field_quality` 에도 그 표는 없다.
* `/api/verify` 경로는 변경 없음(`row_filter` 기본값 None).

## 테스트
`tests/test_read.py` +7: 스키마 지시·maxItems 반영, 목록 밖 행 제거, 인자 없을 때 동일, 재처리 제외, 해석 함수, 라우트 응답, 잘못된 JSON 422. 전체 629 passed.
