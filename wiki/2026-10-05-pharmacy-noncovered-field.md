---
type: feature
title: 약제영수증 진료비내역-비급여 칸 반영
description: 1005 약제영수증 추출 스키마의 비급여 열(④환자부담액 대체)을 하네스 검증과 Docraft 판독 스키마에 평탄 키 진료비내역-비급여로 추가했다.
tags: [harness, docraft, schema, 약제비영수증]
status: active
---

날짜: 2026-10-05
브랜치: harness-v2 `feat/pharmacy-noncovered` → dev `4056948`, Docraft `feat/pharmacy-noncovered` → dev `744dfe6` (둘 다 미push, 브랜치·워크트리 정리 완료)
워크트리: `harness-v2/.worktrees/pharmacy-noncovered`, `Docraft/.worktrees/pharmacy-noncovered` (삭제)

## 배경

요구사항: `harness-v2/docs/requirements/진단서4종_약제영수증_추출_항목_수정_1005/`. 관련 조사·진료소견 구현은 [진단서4종 진단.진료소견 추가와 약제영수증 키 변경 요구사항](../../wiki/2026-10-05-clinical-opinion-field.md) (상위 wiki)에 있다.

0927판 프롬프트(`약제비영수증_필수_키/latest/20260927-1448_약제비영수증_final.md`)와 1005판 스키마를 비교한 결과다.

| 위치 | 0927 | 1005 | 하네스·Docraft 영향 |
|---|---|---|---|
| 소득공제대상 | 총수납액 | 수납금액 | 없음. 평탄 키 `소득공제대상액-수납금액`이 이미 새 이름과 맞다 |
| 진료비내역[i] | ④환자부담액 | 비급여 | **반영**: `진료비내역-비급여` 추가 |
| 환자정보 | 환자명 | 환자성명 | 없음(평탄 키가 `환자성명`). 요청 글에는 없는 변경이라 의도 확인 필요 |
| 진료비내역[i] | ①~③ 번호 붙은 열 제목 | 번호 없음 | 없음 |

요청 글은 "환자수납액→비급여"라고 적었지만 0927 파일의 실제 키는 `④환자부담액`이다.

## 변경

- 하네스 `rulesets/shared/schema.yaml` 약제영수증: `진료비내역-비급여: {kind: amount, non_negative: true}`. 다른 진료비내역 금액 칸과 같은 형식·음수 검사다.
- Docraft `backend/doctypes.py` 약제비영수증: `진료비내역-비급여` amount 필드. 설명에 "비급여 칸이 따로 인쇄된 서식만, 비급여및전액본인부담금 칸 값이 아니다"를 적었다.
- 합계식 `비급여및전액본인부담금 = 전액본인부담 + 비급여`는 넣지 않았다. 1005 스키마는 계산서 서식에서 전액본인부담·비급여를 0으로 두고 ③에만 금액을 적게 해서, 0과 미인쇄를 구분할 수 없어 정상 문서를 위반으로 잡는다.
- Docraft 라벨 동의어(`rules.yaml` labels)에 '비급여'를 넣지 않았다. `amount_candidates`가 라벨을 부분 문자열로 맞춰서 '비급여및전액본인부담금' 줄 금액을 비급여로 잘못 집는다.

## 테스트

- 하네스: `test_schema_declarations.py`에 비급여 음수·숫자 아님 경고 2건 추가, 정상 문서 fixture에 비급여 0. `test_docraft_fallback.py` 약제 표 머리글 `환자부담액`→`비급여`. 대상 파일 164 passed. 전체 unit 2076 passed, 17 failed는 dev에서도 같은 기존 실패(수술확인서·입퇴원확인서 AO 예시 JSON이 2건씩 있음).
- Docraft: `test_rules.py` 약제 테스트에 비급여 kind·금액 정규화(`1,200원`→`1200`) 확인. AO 2.0.1 예시(09-09)에는 이 키가 없으므로 `AO_LATER_KEYS`로 예시 뒤 생긴 키를 따로 두고 키 일치·순서·`_add_missing` 테스트가 이를 반영한다. 전체 908 passed.

## 남은 일

- 하네스·Docraft dev push, AWS 반영은 배포 담당 세션에 요청.
- AO 그룹 키(`소득공제대상.수납금액`, `진료비내역[i].비급여`)를 납품 평탄 키로 바꾸는 매핑 위치를 하네스 소스에서 찾지 못했다(DB·플랫폼 설정으로 추정). 신규 AO 출력 샘플이 들어오면 키 이름을 확인한다.
- 보험 조제·보험 약가·비 보험 조제·비 보험 약가, 요양기관종류, 여러 행 날짜별 표의 Docraft 재판독은 원래 없던 항목으로 범위 밖이다.
