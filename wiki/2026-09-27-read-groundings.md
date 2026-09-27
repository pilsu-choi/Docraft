---
type: Implementation
title: "/api/read 최종 값의 원문 좌표 반환"
description: "추출 근거를 규칙 적용 후 최종 값과 안전하게 다시 연결해 /api/read groundings로 전달한다."
tags: [read, grounding, api, harness]
status: stable
---

# /api/read 최종 값의 원문 좌표 반환

- 날짜: 2026-09-27
- 브랜치: `feat/read-groundings`
- 워크트리: `.worktrees/read-groundings`

## 문제

`engine.extract`가 필드·표 셀의 `page`, `bbox`, `source_text`, `confidence`를 만들지만 `verify.read`가 근거를 버렸다. `rules.apply`는 값과 표 행을 바꿀 수 있으므로 추출 당시 좌표를 최종 값에 그대로 복사하면 잘못된 위치를 가리킨다.

## 구현

- `verify.read(..., with_groundings=True)`가 최종 `fields`와 검증된 `groundings`를 함께 반환한다. 기본 반환형은 `/api/verify`를 위해 그대로 둔다.
- 스칼라는 추출값에 첫 정규화 규칙을 적용한 값과 최종 값이 같고 근거에 유효한 페이지·픽셀 좌표·신뢰도(0.7 이상)가 있을 때만 전달한다.
- 표는 전체 정규화 행이 원본 행 중 유일하게 대응할 때만 그 행의 셀 근거를 전달한다. 행 순서 변경·삭제 후에도 좌표를 원래 행에 연결한다. 중복 행, 새 행, 교정된 행은 빈 근거 객체를 둔다.
- `/api/read`는 기존 `fields`를 유지하고 `groundings`를 추가한다. 표 근거 목록의 인덱스는 최종 `fields` 행 인덱스다. leaf의 `basis: image_pixel`은 요청 이미지 픽셀 좌표이며 페이지는 1부터 시작한다. `source_text`는 추출 엔진이 기록한 값 후보라 원문 줄 전체를 뜻하지 않는다.

## 검증과 제한

`tests/test_read.py`에서 정규화된 스칼라, 바뀐 스칼라, 재정렬·삽입·중복 표 행, 수정된 셀 및 낮은 신뢰도를 검사했다. 표 행에서 한 셀만 바뀌어도 전체 행의 근거를 생략하므로 사용 가능한 근거가 일부 줄 수 있지만, 다른 행의 좌표를 붙이지 않는다. 좌표는 OCR 파서가 반환한 픽셀 좌표이므로 이미지 전처리나 크롭을 거친 호출자는 입력 이미지 기준으로 표시해야 한다. 전체 테스트는 534건 통과했다.
