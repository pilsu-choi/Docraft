---
type: decision
title: 추출 누락 검증 규칙(룰 1~4) 반영
description: 필수 키 추출률·필수 항목 행·AO parse 표 보충 규칙을 harness·Docraft·installer에 반영한 결정과 결과
tags: [harness, docraft, installer, 추출누락, parse, 공통규칙]
status: active
---

날짜: 2026-09-28  
브랜치: harness-v2·Docraft `feat/0928-coverage-rules`, harness-installer `feat/0928-ao-parse-key` (모두 dev 병합 후 삭제)  
워크트리: 각 저장소 `.worktrees/coverage-rules`, `.worktrees/ao-parse-key` (정리 완료)

## 결정 (사용자, 2026-09-28)

| 룰 | 내용 | 동작 |
|---|---|---|
| 1 | 문서 7종의 "늘 적혀 있어야 하는 키" 중 값이 채워진 비율 < 0.97 | 하네스 검증(검토 등급 → Docraft 재판독) |
| 2 | 진료비영수증 항목내역에 진찰료·CT진단료 행이 모두 있어야 함 | 하나라도 없으면 하네스 검증. 한방 영수증은 CT진단료 제외 |
| 3 | AO 추출 금액 칸이 비었거나 0인데 AO parse 표에 값이 있으면 parse 값으로 보충 | 파서 오류 칸·같은 행에 같은 금액이 이미 있는 칸은 제외 |
| 4 | 재검증(Docraft) 뒤에도 급여·비급여 칸이 비면 parse 숫자(콤마 형식) 값을 후보로 사용 | 룰 3과 같은 함수, 적용 시점만 다름 |

- 기준값은 모두 공통 규칙 표 `rulesets/shared/receipt_items.yaml`(harness·Docraft 동일, installer 빌드가 대조)에 둔다.
- 룰 1의 분모: 값이 인쇄되지 않아 비는 키까지 세면 문서의 약 84%가 걸려서, 정답지에서 95% 이상 값이 있던 키만 분모로 삼았다(2번 방식).
- 파서 오류 판별: 한 칸에 숫자가 둘 이상이면 오류. 또 금액 칸 절삭평균(큰 값 3개 제외)의 **30배**를 넘으면 오류. 표본 정상 칸의 최댓값이 26.2배라 30배로 정했다.
- AO는 빈 금액 칸을 `"0"`으로 낸다. 그래서 0도 빈 칸으로 본다. 대신 같은 금액이 같은 행 다른 칸에 있으면 칸이 헷갈린 것으로 보고 채우지 않는다.

## 표본 결과 (AO 205건 + parse 205건)

| 항목 | 결과 |
|---|---|
| 룰 1 해당 | 7/205건 (소견서 2, 입퇴원확인서 2, 진료비영수증 3) |
| 룰 2 해당 | 영수증 30건 중 2건 (한방 오탐 1건은 예외 처리로 제외) |
| 룰 3 보충 | 영수증 30건에서 9칸(`20220307_120439.jpg`의 5칸 정답지 일치), 세부내역서 20건에서 7칸(7칸 모두 정답지 일치) |
| parse 조회 시간 | 다운로드 중앙값 0.07초, 압축 해제 5ms 이하 |

## 반영 위치

- harness-v2 dev `9dbceae`(세부내역서 적용 `cbbd9ad`): `normalizer/coverage.py`, `normalizer/parser_fill.py`, 설정 `AO_API_URL`·`AO_API_TOKEN`·`AO_API_AUTH`·`AO_API_TIMEOUT`. 저장소 wiki `2026-09-28-추출-누락-검증-규칙.md`.
- Docraft dev `d8995b5`: `MISSING.REQUIRED`가 필수 항목 행(`required_items`, 한방 예외 `required_items_exempt`)도 검사.
- harness-installer dev `5cec40b`(harness 재고정 `76bf2f4`): 공용 Secret에 `AO_API_TOKEN`, values·INSTALL.md에 설정 추가, submodule 두 개를 위 커밋으로 고정.
- 설치 계획서 v0.4: `docs_out/`의 xlsx·docx에 "AO API 키(권한 workflow:result, 하네스 전용 권장) 사전 준비"와 네트워크·설정값 추가.

## 남은 일

- 고객사 AO API 키 발급(권한 `workflow:result`)과 하네스 → AO 네트워크 확인.
- 설치 번들 재빌드와 NAS 반영(`C:\Users\user\Desktop\미래에셋\mlife-ocr-k8s-...`)은 아직 하지 않았다.
- 세부내역서는 수가코드로 행을 맞춘다(중복 코드는 제외). 정상 고액 항목(최대 708배)은 30배 기준에 걸려 보충되지 않는다 — 잘못 채우지는 않는다. 30배 기준을 그대로 두기로 했다(2026-09-28 사용자 결정).

## 용어

| 용어 | 뜻 |
|---|---|
| parse 결과 | Agentic OCR가 추출 전에 만든 문서 구조(표를 HTML로 담음) |
| 하네스 검증 | 문서를 검토 등급으로 올려 Docraft가 해당 칸·표를 다시 읽게 하는 것 |
| 절삭평균 | 가장 큰 값 몇 개를 뺀 나머지의 평균 |
