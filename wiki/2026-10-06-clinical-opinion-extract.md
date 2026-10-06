---
type: feature
title: 진단서4종 진료소견 Docraft 판독 필드 추가
description: 1005 요구사항의 진단.진료소견을 Docraft 재판독 스키마에 text 필드로 추가했다. 하네스는 키 이름으로 읽어 변경이 없다.
tags: [docraft, harness, schema, 진단서, 진료소견]
status: active
---

날짜: 2026-10-06
브랜치: Docraft `feat/clinical-opinion-extract` → dev `3d4f9e5` (기능 `27334fd`, 미push, 브랜치·워크트리 정리 완료)
워크트리: `Docraft/.worktrees/clinical-opinion-extract` (삭제)

## 배경

요구사항: `harness-v2/docs/requirements/진단서4종_약제영수증_추출_항목_수정_1005/` 1번(`진단.진료소견` 추가). 정답 쪽(label_veiwer·synthetics)은 [진단서4종 진단.진료소견 추가](../../wiki/2026-10-05-clinical-opinion-field.md)에서 반영했고, 이 문서는 추출 쪽이다.

## 키 이름 판단

- 고객 스키마 경로는 `진단.진료소견`(같은 그룹: 진단일·발급일·사고발생일자).
- 하네스는 그룹 이름 없이 마지막 키 이름으로 규칙을 찾는다(`harness-v2/src/mlife_harness/rulesets/medical_cert.yaml:7-17`). 그래서 키는 `진료소견`이다.
- 1차 사업 납품 형식도 항목명 `진료소견`을 쓴다(`Docraft/refs/postprocess_schema_example/20260828_v1.1/json/반출_*`의 `img_extc_itnm`, `plugin/.../항목리스트.json`). 그룹은 상위 항목 번호로만 표시된다. AO 그룹 키를 납품 항목명으로 바꾸는 일은 플랫폼 플러그인이 하며 하네스·Docraft 범위 밖이다.

## 변경

- Docraft `backend/doctypes.py` `_MEDICAL_FIELDS`: `진단일` 뒤에 `진료소견` text 필드. 설명에 라벨 6종, 인쇄된 그대로, 줄바꿈은 공백 한 칸, 라벨이 없거나 비면 빈 값을 적었다. 4종(진단서·소견서·수술확인서·입퇴원확인서)이 같은 정의를 쓴다.
- Docraft `rules.yaml` labels에는 넣지 않았다. 이 목록은 값에 섞여 들어온 라벨 글자를 걸러내는 데 쓰인다. '소견' 같은 짧은 낱말을 넣으면 소견 본문까지 라벨로 잘못 판단할 수 있다.
- 하네스는 바꾸지 않는다. 진단서 필드 목록을 따로 두지 않고, `schema.yaml`의 text 선언은 검사가 없다. 필수 항목(`required_keys`)에는 넣지 않는다. 소견 칸이 없는 서식(수술확인서·입퇴원확인서·소견서 일부)이 있어서다.

## 테스트

- `tests/test_rules.py` `AO_LATER_KEYS`에 4종 진료소견 추가(AO 2.0.1 예시 응답에는 없는 키). `test_clinical_opinion_is_text_field` 4건 추가.
- 영향 테스트 `test_rules.py`·`test_verify.py` 469 passed. 빠른 회귀 `pytest -n 4` 958 passed.

## 남은 일

- Docraft dev push(harness-installer 서브모듈 갱신과 함께 30분 주기), AWS 확인은 배포 담당 세션에 요청: 진단서 4종 표본에서 진료소견 출력, 소견 칸 없는 서식은 `""`.
- 정답지 59건·205건에 진료소견 정답이 없다. 채점하려면 정답 추가와 서술문 비교 방식(공백 정규화 등) 결정이 필요하다.
- 같은 스키마에서 `입원통원치료.치료일자` → `일자 내역.치료연월일`로 키 이름이 바뀌었다. 하네스 영향은 아직 확인하지 않았다.
