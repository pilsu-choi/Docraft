---
okf_version: "0.2"
type: change
title: "auto_reprocess=false 읽기 오류와 ROI VLM 오채택 수정"
description: "/api/read 에서 auto_reprocess=false 면 502 나던 미할당 변수와, ROI OCR이 지지한 원값을 ROI VLM 단독 제안이 덮어쓰던 채택 조건을 고쳤다"
tags: [docraft, reprocess, read, bugfix]
status: active
---

# auto_reprocess=false 읽기 오류와 ROI VLM 오채택 수정

날짜: 2026-09-29 / 브랜치: `fix/read-reprocess` / 워크트리: `.worktrees/read-reprocess-fix`

## 버그 1: `auto_reprocess=false` 502
* 원인: `backend/verify.py` `read()` 에서 재처리를 건너뛰면 `recovery_groundings` 가 할당되지 않는데, `with_reprocess` 로 `recovered` 만 기본값으로 채워져 근거 계산이 미할당 변수를 읽었다.
* 수정: `recovery_groundings` 를 `None` 으로 초기화하고, 값이 있을 때만 사용하며 없으면 `engine.ground` 로 1차 추출 근거를 쓴다. 응답의 `reprocess` 는 `stop_reason: "disabled"`, `model_calls: 0`. `/api/verify` 도 같은 `read()` 를 쓰므로 함께 해결된다.

## 버그 2: ROI VLM 오채택
* 원인: `backend/reprocess.py` 채택 조건이 VLM 후보의 자체 검증(exact·semantic·rule)만 보고, ROI OCR(roi_parse)이 원값을 그대로 읽었다는 독립 근거를 무시했다(`연세맑은이비인후과` → `연세앎은이비인후과`).
* 수정: roi_vlm 단계에서 원값이 ROI OCR 블록 텍스트에 그대로 있고 VLM 값이 다르면 `roi_parse_supports_original` 로 기록하고 그 필드의 남은 단계를 멈춘다(원값 유지).

## 테스트
* `tests/test_read.py::test_read_with_auto_reprocess_off_returns_first_pass_and_disabled_recovery`
* `tests/test_reprocess.py::test_roi_vlm_does_not_override_value_that_roi_ocr_read_unchanged`
* 전체 618개 통과.
