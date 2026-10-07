---
type: change
title: /api/read 재판독의 groundings 자료형·재처리 key 불일치 수정
description: 표 groundings 가 list 로 와서 unit_flags 가 502 를 내던 것과, 좁힌 스키마에 없는 key 가 재처리에 들어가 KeyError 가 나던 것을 계약 단위로 고침
tags: [docraft, api-read, groundings, reprocess, 진료비영수증]
status: active
---

날짜: 2026-10-07
브랜치: `fix/read-groundings-reprocess` (dev `53b8fdf` 기준)
워크트리: `.worktrees/read-groundings-fix`

## 근본 원인
1. 표 groundings 는 두 형태다. 문서 큐는 `{"행 번호": {열: leaf}}`, `/api/read` 는 `verify._read_groundings` 가 `[{열: leaf}, ...]` 로 노출한다. `/api/read` 가 노출 형태를 `engine.apply_integrity -> unit_flags`(d0babbc)에 넘기는데, 소비 지점은 dict 만 가정해 `AttributeError` -> 502.
2. `rules.apply` 는 `only` 와 무관하게 유형의 모든 key 를 낸다. `verify.read` 는 스키마만 `only` 로 좁히고 필드 전체를 `reprocess.run`(1bcee4a)에 넘겨, 요청 밖 key(발행일·의료기관정보-* 등)가 재처리 대상이 되고 `schema["properties"][root]` 에서 KeyError. key 형태(그룹 평탄화·최상위·표)와 스키마 구조 불일치가 아니다(스키마 properties 는 평탄 key 그대로).

## 문제 유형
- 1: 같은 데이터의 두 표현을 소비 지점이 한쪽으로만 가정. `engine._row_grounding` 이 두 형태를 읽는 단일 접근자다.
- 2: 요청 범위(`only`)와 재처리 입력의 범위 불일치. 재처리에는 좁힌 스키마 안의 key 만 넘기고, 요청 밖 key 는 그대로 합쳐 반환한다(AO 비교 `run` 은 전체 필드를 계속 쓴다).

## 같은 유형 점검
- 표 groundings 를 인덱싱하는 곳: `unit_flags`(수정), `assess.walk`·`_read_groundings`·`_merge_recovered_groundings`·`annotate_groundings` 는 이미 형태를 검사하거나 큐 형태만 받아 변경 없음.
- `verify: keys에 알 수 없는 key ['상한액초과금']` 는 같은 원인이 아니다. Docraft 키는 `상환액초과금`이고 하네스는 별칭(`FIELD_KEY_ALIASES`)으로 보낸다. 범위 밖: 하네스가 Docraft 키로 요청하거나 Docraft 가 별칭을 받을지는 별도 결정.

## 테스트
`tests/test_read_contract.py`(DB 없이 `--noconftest`): 두 groundings 형태의 동일 판정, 빈·짧은·None 행 근거, 3개 문서유형에서 재처리 입력 key 가 좁힌 스키마 안인지와 읽기 결과의 전체 key 유지. DB 가 필요한 `test_read.py`·`test_verify.py` 는 로컬에서 돌리지 못했다.
