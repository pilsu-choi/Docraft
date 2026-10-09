---
type: change
title: 영수증 항목표 band 읽기(TABLE_EXTRACT=band) 이식
description: 실험으로 검증한 위치 찾기 → 3개 가로 띠 짧은 키 읽기 → 이름 순서 겹침 합치기 → 금액산정 블록 따로 읽기를 BAND_DOC_TYPES 유형에만 켜는 모드로 이식했다. 저장 응답 195건 재생에서 실험 최종 결과와 전부 일치
tags: [docraft, 진료비영수증, band, table_extract, vlm]
status: active
---

날짜: 2026-10-09
브랜치: `feat/receipt-band`(dev 기준)
워크트리: `Docraft/.worktrees/receipt-band`

## 동작

- `TABLE_EXTRACT=band`는 `BAND_DOC_TYPES`(기본 진료비영수증) 유형의 한 쪽 이미지 문서에만 쓴다. 그 밖의 유형, 이미지 없음, 여러 쪽, 위치 응답 불량이면 `rowmajor`로 읽고 `band_fallback`(locate·read·summary)을 진단 값으로 남긴다. 기본값은 `rowmajor` 그대로다.
- 위치 호출 1회(쪽 전체 그림, 0~1000 상자): 항목표·머리글·첫 행·합계 행·금액산정 블록. `backend/band.py`가 후처리(감싼 목록 풀기, 금액산정 패널과 겹치는 표 오른쪽 자르기, 높이 8% 미만 블록 무시)와 크롭 계산을 맡는다.
- 띠: 첫 행 윗선~합계 행 아래 1.5%를 3등분(10% 겹침). 첫 띠는 머리글 위 1%부터, 나머지 띠는 머리글 띠(첫 데이터 행 제외)가 첫 이미지로 붙는다. 회전한 쪽은 `engine._clip`이 원본 좌표로 되돌린다(OCR 띠 `_bands`와 공용).
- 읽기 형식: 항목 스키마 순서로 만든 짧은 키(n, a, b…)를 모든 행에 빠짐없이 쓰게 하고 빈칸 ""→"0", 모르는 키·키 빠진 행은 `band_unknown_keys`·`band_missing_keys`로 센다.
- 합치기: `read_bands`가 이름 순서 겹침(difflib 0.7, 최대 8행)으로 앞 띠 끝과 겹치는 행을 버리고 합계 행은 마지막 것만 둔다(OCR 띠는 기존 `_same_row` 유지).
- 금액산정 블록은 띠와 병렬로 따로 잘라 읽고 그 키의 최종 값이다(빈칸은 null, 쪽 전체 읽기로 메우지 않음). 쪽 전체 읽기에서는 그 키를 뺀다. 블록 실패·상자 없음이면 쪽 전체 읽기에서 읽는다.
- `rules._totals`: 영수증 공단부담총액은 최종 합계 행에 인쇄된 공단부담금(0 포함)을 옮긴다. 합계식에 맞는 기존 값도 이 값으로 바뀐다(기존 테스트 기대값 변경).

## 설정

`BAND_DOC_TYPES`, `VLM_CONCURRENCY`(기본 8, `latency.provider_slot`이 `engine._provider` HTTP 호출을 감쌈, 0이면 제한 없음), `REPETITION_PENALTY`(비우면 보내지 않음). `.env.example`·AWS 예시·helm·README 표에 반영.

## 검증

- 변경 영향 테스트 847건 통과(`tests/test_band.py` 신규, test_rowmajor·test_latency·test_rules 보강).
- 저장 응답 재생(API 호출 없음): t200 고정·원근 보정 없음 195건을 실험 설정 1-3-4-6-8-9-10-15-16의 저장 응답으로 `engine.extract`에 흘려 `rules.apply`까지 거친 최종 필드·행이 실험 결과와 전부 일치.

## 추가: 방향 판정 보강·dev 병합(2026-10-09)
- 방향 판정 보강(`feat/receipt-orient` 0218018): `parsers._vote` 가 정하지 못한 쪽만 줄 상자 모양으로 후보(0/180 또는 90/270)를 정하고 후보 각도로 다시 읽어 인식 점수(`rec_scores`, 줄마다 `line["score"]`) 평균이 높은 쪽을 고른다. 한쪽 읽기에 점수 줄이 없으면 돌리지 않는다. `ORIENTATION_SCORE_CHECK`(기본 켬). 197건 원본: 마침표 투표가 확신한 133쪽은 틀림 0, 미정 64쪽만 추가 읽기 - 저장 각도별 OCR 재생 197/197 일치.
- 공단부담총액 규칙은 모든 모드에 적용(기존 rowmajor 경로 포함): 기존 하네스 결과(`measure_v2_v10`, 194칸)에 적용하면 143→168칸(고침 31·깨짐 6), band 결과에서도 블록 값 우선(162)보다 합계 행 복사(173)가 낫다. 그래서 기존 테스트 기대값(합계식 맞는 필드 값 유지)을 새 정책으로 바꿨다.
- dev 병합: c700851(방향)·67e082c(band), 영향 테스트 808 passed·3 xfailed. 워크트리·브랜치 정리. 미push.
