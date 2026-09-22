---
type: implementation
title: POST /api/verify에 hint_paths 필드 추가
description: harness-v2 룰 엔진이 확정하지 못한 필드만 골라 Docraft 교차검증·Judge를 돌리는 선택 form 필드 hint_paths 구현
tags: [verify, api, cost-optimization, harness-v2]
status: active
---

2026-09-23, 브랜치 `feat/verify-hint-paths`, 워크트리 `.worktrees/verify-hint-paths`.

## 배경

`POST /api/verify`는 지금까지 AO 응답의 모든 필드·표를 Docraft 추출 결과와 비교하고, 어긋나는 항목만
Judge LLM에 보냈다(비교 자체는 전체 필드 대상). 호출자인 harness-v2는 이미 자체 룰 엔진으로 상당수
필드를 확정하므로, 룰 엔진이 확신하지 못한 필드만 Docraft에 보내 비교·판정 비용(VLM 추출 + Judge
호출)을 더 줄일 수 있다.

## 요청 계약

`POST /api/verify`에 선택 form 필드 `hint_paths`를 추가했다.

- 형식: JSON 배열 문자열(`ao_result`와 같은 관례). 예: `hint_paths=["병원명", "항목내역"]`
- 원소는 `backend/verify.py`가 필드·표·그룹을 식별할 때 쓰는 key(그룹 접두사를 뗀 이름, 표는 표 key)와
  같다 — `verify._name()`이 `"그룹.키"`·`"표[0].열"`에서 떼어내는 바로 그 이름.
- 생략하거나 빈 배열(`[]`)이면 기존과 동일하게 전체 필드를 비교·판정한다.
- JSON으로 해석할 수 없거나 배열이 아니면(원소가 문자열이 아니어도) `422`.
- 정의에 없는 key는 무시하고 `backend.verify` 로거에 경고를 한 번 남긴다(요청당 1회, key 목록을 묶어서).

```bash
curl -X POST http://127.0.0.1:8000/api/verify \
  -F 'image=@document.tif' \
  -F 'ao_result=<ao_response.json' \
  -F 'doc_type=진료비영수증' \
  -F 'hint_paths=["병원명", "항목내역"]'
```

## 동작

`backend/verify.py::run(image, ao, doc_type=None, hint_paths=None)`이 새 인자를 받는다.

- `hint_paths`가 있으면(비어 있지 않은 목록) 정의된 key만 남긴 집합(`only`)을 만들고, 이후 단계를 모두
  그 집합으로 좁힌다.
- **추출 스키마 축소**: `doctypes.schema(doc_type)`의 `properties`·`required`를 `only`로 필터링한
  뒤(`verify._restrict`) `engine.extract`에 넘긴다 — 스키마가 작을수록 VLM 호출 비용이 준다.
- **누락 필드 보충 축소**: `_add_missing`이 AO에 없는 정의된 필드·표를 빈 원소로 끼워 넣던 동작도
  `only` 안의 key만 대상으로 한다.
- **비교·Judge 축소**: 불일치 판정(`disputes`)도 `only` 안의 key만 검사해 Judge 프롬프트에 싣는다.
- **최종 반영**: 필드/표별 최종 값 계산 루프(`_scalars`/`_tables` 순회)도 `only` 밖의 key는 건너뛴다 —
  즉 그 필드·표 원소는 입력 AO 값 그대로 출력에 남고 `value`·`source`·`reason`·`ao_value`·
  `docraft_value`가 **전혀 붙지 않는다**. 호출자는 `"source" in field`(또는 dict에 그 key가 있는지)로
  판정 여부를 가릴 수 있다. 이름 없는(`key`·`display_label` 둘 다 없는) 원소는 힌트 여부와 무관하게
  기존처럼 `unknown`으로 표시한다.
- `verify.counts`는 `only` 안에서 실제로 판정된 key만 센다 — `agree`·`ao`·`docraft`·`corrected`·
  `added` 모두 힌트 밖 필드는 포함하지 않는다.

## 구현 메모

- 스키마 축소는 `doctypes.schema()`가 돌려주는 일반 dict를 `verify.py` 쪽에서 얕게 필터링하는
  방식으로 넣었다(`doctypes.py` 자체는 건드리지 않음) — 최소 변경으로 끝나 "쉬우면 하고 복잡하면
  건너뛴다"는 지시에 맞춰 그대로 채택했다. 복잡해질 지점(테이블 열 단위 부분 스키마 등)은 없었다.
- `_add_missing(document, doc_type, only=None)`처럼 기존 함수에 선택 인자를 더하는 형태로 넣어 별도
  함수를 만들지 않았다(코드 최소화 지시).
- `rules.check`/`rules.correct`(이상 검사·룰 교정)는 `only` 없이 문서 전체를 대상으로 그대로 돌린다 —
  `verify.checks`/`checks_after`는 힌트와 무관하게 전체 결과를 보고한다. 값 반영만 `only`로 걸렀다.

## 테스트

`tests/test_verify.py`에 `hinted_stub()` 헬퍼(기존 `stub()` 위에 `doctypes.spec`/`doctypes.schema`를
실제 형태로 얹음)와 함께 다음을 추가했다.

- `hint_paths`가 주어지면 그 key만 Judge에 가고(disputes), 힌트 밖 필드는 `source`가 없고, counts가
  힌트 안 key만 반영하는지
- 추출 스키마의 `properties`/`required`가 `hint_paths`로 좁혀지는지
- `hint_paths`가 없거나 빈 배열이면 기존과 동일하게 전체 key가 대상이 되는지
- 정의에 없는 key만 주면 Judge를 아예 부르지 않고 경고 로그가 남는지
- 라우트가 `hint_paths`를 파싱해 `verify.run`에 그대로 넘기는지, 잘못된 JSON·배열이 아닌 값이 `422`가
  되는지

기존 `test_verify_route_returns_the_corrected_result`·`test_verify_route_accepts_the_ui_result_format`의
`verify.run` monkeypatch 시그니처에 `hint_paths=None`을 추가해 새 위치 인자와 맞췄다.

`pytest tests/test_verify.py`: 51 passed. 전체 스위트 `pytest`: 376 passed.

## 관련 자료

- [Agentic OCR 2.0 결과 교차검증·자동 교정 API 구현](2026-09-22-ocr-verify.md) — `verify.run`의 기본
  구조·Judge 설계
