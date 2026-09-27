---
okf_version: "0.2"
type: implementation
title: "근거 기반 자동 재처리 루프"
description: "Docraft 일반 추출과 의료 문서 읽기에 공통으로 적용하는 제한된 ROI 재파싱·재추출과 채택 조건"
tags: [docraft, parse, extract, verification, reprocess]
status: active
---

# 근거 기반 자동 재처리 루프

날짜: 2026-09-27
브랜치: `feat/auto-reprocess`
워크트리: `Docraft/.worktrees/auto-reprocess`

## 동작

일반 문서 추출 잡과 의료 문서 `/api/read`·`/api/verify`가 `backend.reprocess.run`을 공유한다. 최초 Parse·Extract 뒤 `engine.assess`가 남긴 필드별 문제를 대상으로 기존 규칙(`rules.apply`) 재적용, 원본 좌표를 확장한 ROI 재파싱, ROI 이미지 VLM, 전체 이미지 VLM 순으로 시도하고 각 후보를 스키마·근거·의료 규칙으로 다시 검사한다. `PASS`가 된 단일 leaf만 채택하며 값 변경은 `CORRECTED`, 값 그대로 근거만 확보한 경우 `PASS`, 해결되지 않은 경우 요약 `UNRESOLVED`다. 정상 필드와 대상 외 필드는 유지한다. 표는 유일하게 확인된 행의 셀만 바꾸며, 행 대응이 불명확하거나 표 전체 교체가 필요한 후보는 검토 대상으로 남긴다.

후보 채택은 OCR 원문과 좌표의 정확한 일치, 해당 key 라벨이 판독 영역에 존재함, 새 스키마·규칙 오류 없음, 다른 필드 품질 악화 없음, 실제 품질 개선을 모두 요구한다. OCR 일치는 픽셀의 참값 보증이 아니므로 `PASS`도 원문 근거 기준 판정이다. 중첩 객체의 scalar leaf는 보존적으로 패치하고, 중첩 배열 등 안전한 행 identity를 확정할 수 없는 경로는 `unsupported_path`로 남긴다. 값이 `null`인 후보는 빈칸이라는 이미지 근거가 없어 자동 채택하지 않는다.

## 예산과 취소

기본 `REPROCESS_ENABLED=true`, 추가 재처리 상한 `REPROCESS_MAX_MS=60000`, `REPROCESS_MAX_ATTEMPTS=4`, `REPROCESS_MAX_MODEL_CALLS=2`다. 규칙 재평가·ROI 재파싱·ROI VLM·넓은 VLM의 4단계를 각각 시도로 센다. 각 값은 서버 상한으로 clamp된다. `/api/read`와 `/api/verify`의 multipart `remaining_ms`는 최초 읽기부터 적용되는 전체 요청 예산이며 서버 `READ_MAX_MS=180000`을 넘길 수 없다. 0이면 최초 OCR·모델 호출도 시작하지 않고 408을 반환한다. 최초 읽기만 필요하면 `auto_reprocess=false`를 보낸다. 서버 `REPROCESS_ENABLED=false`는 클라이언트 설정보다 우선한다. 추가 모델 호출은 청크마다 전송 직전에 세며 재처리 중에는 transport 재시도를 끈다. 취소 Event·시한은 각 단계와 모델 호출 전후에 확인한다.

`reprocess`에는 `status`, `attempts`, `model_calls`(추가 호출), `extra_model_calls`, `initial_extract_model_calls`, `stop_reason`, `elapsed_ms`, `trace`가 있다. trace는 `field`, `stage`, `reason` 코드, 이전 값·후보 값·최종 값, 채택 여부, 근거를 포함하며 일반 문서 DB에도 보존한다. 개인정보가 있으므로 로그에는 값이 기록되지 않는다. `/api/read`는 최종 `field_quality`를 함께 내려주며 채택된 값은 `CORRECTED`와 원문 근거를 유지한다.

## 검증과 한계

전체 회귀 570개가 통과했다. 단일 필드 교정과 다른 필드 보존, 표 행 identity, ROI 좌표 역변환·EXIF·PDF, 후보 거절, 같은 값의 새 근거, 중단·예산·취소, 일반 문서 API의 감사 이력 저장을 확인한다. 독립 35건 cache의 자연 표본 3건 재생에서는 추가 모델 호출 1·2·2회, 채택 0건으로 기존 값이 보존됐다. 앞쪽 미확정 필드가 문서당 4회 시도를 소비해 뒤쪽 필드가 재처리되지 않은 사례가 있으며, 문서 필드 순서와 공유 예산에 따른 기회 제한이 남는다. 진단일 의도적 오독은 ROI·넓은 VLM 후보가 모두 `distant_label`·비정확 출처로 거절됐다. 별도 주소 오독은 ROI VLM 한 번으로 `CORRECTED`가 되었고 초기 추출값과 공백 정규화 기준으로 같아졌지만, 최초값과 교정값 모두 미검수 silver 라벨과 일치하지 않는다. 이 실험은 자동 후보 채택 동작만 입증하며 정답 복구나 자연 정확도 향상으로 계산하지 않는다. 재생 도구는 `scripts/reprocess_smoke.py`다.

HTTP의 read timeout은 전송 단계별 제한이므로 느린 단일 응답 스트림을 운영체제 수준에서 즉시 강제 종료하는 hard wall deadline은 아니다. 단일 원격 호출이 늦게 돌아오면 그 결과는 시한 후 채택하지 않고 408 또는 `UNRESOLVED`로 끝난다. 스캔 PDF 초기 파싱에는 페이지 경계와 원격 OCR timeout을 전달한다. 비시각 파일은 기존 추출 결과를 유지하고 `non_visual`로 남긴다. 중첩 배열 행 추가·삭제, 눈으로만 식별 가능한 빈칸, 마스터 전 범위 검증은 자동 채택하지 않는다.
