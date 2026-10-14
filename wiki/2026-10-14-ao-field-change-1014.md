---
type: fix
title: 고객 AO 추출 항목 변경 대응 (투여량 제거·선택진료료이외총액·입퇴원일자 배열)
description: 2026-10-14 고객 공유 — 세부내역서 투여량 제거·선택진료료외총액→선택진료료이외총액, 진단서 4종 입원일자·퇴원일자 텍스트→배열. 하네스·Docraft·정답지·채점 스크립트를 새 항목 기준으로 맞췄다.
tags: [harness, docraft, 세부내역서, 진단서, 입원일자, 퇴원일자, array, 정답지, 채점]
status: active
---

날짜: 2026-10-14
브랜치: harness-v2 `fix/ao-field-change-1014`(`051f5ff`·`a51a2d4`) → dev `7318fd2`, Docraft `fix/ao-field-change-1014`(`016a8ae`) → dev `484fc3b` (둘 다 미push)
워크트리: `harness-v2/.worktrees/ao-field-change-1014`, `Docraft/.worktrees/ao-field-change-1014` (병합 후 삭제, 브랜치 삭제)

## 고객 변경 (2026-10-14 공유)

| 문서 | 변경 |
|---|---|
| 세부내역서 | 항목 `투여량` 제거 |
| 세부내역서 | 항목명 `선택진료료외총액` → `선택진료료이외총액` |
| 진단서·수술확인서·입퇴원확인서·소견서 | `입원일자`·`퇴원일자` dtype 텍스트 → 배열 |

고객 배치 워크플로우 반영은 10/15 예정.

## 근본 원인과 문제 유형

- 이름으로 항목을 찾는 규칙·설정·정답지가 옛 이름을 들고 있으면 **오류 없이 검사가 빠진다**(합계 검사가 "해당 없음"으로 끝남).
- 배열 전환은 10/12 [배열 필드 원소 단위 처리](../../wiki/2026-10-12-array-field-elements.md)와 같은 유형이다. 이번에 빠져 있던 곳 두 군데를 찾았다.
  1. 날짜 선후 검사(`입원일자 ≤ 퇴원일자`)가 배열 값이면 날짜를 못 읽어 조용히 건너뜀.
  2. 판정 단계에서 Docraft 판독값(글자 하나)을 채택하면 배열 칸이 글자로 나가 고객 dtype 이 깨질 수 있음.
- 문제 유형: "고객 스키마(항목 이름·dtype) 변경이 이름·형식을 가정한 코드에서 조용히 무시됨". 이름 분기 없이 값이 배열인지로 판단하도록 일반화했다(치료연월일·통원일에도 적용).

## 변경 내용

### harness-v2

| 항목 | 위치 | 내용 |
|---|---|---|
| 이름 변경 | `rulesets/detail_0710.yaml`, 테스트, 입력 샘플 1건 | `선택진료료이외총액`. 영수증 표 열 `선택진료료외`는 무관이라 유지 |
| 날짜 선후 | `rules/schema.py` `_date_pairs`·`check_relations` | 배열은 빈 원소·연도 0000 제외, 개수 같으면 순번끼리, 한쪽 하나면 그 하나와 각 원소, 개수가 달라 모호하면 검사 안 함 |
| 배열 형식 보존 | `domain/normalize.py` `keep_array_form`, `arbitration/arbitrator.py` `decide_field` | 원래 값이 배열(리스트·repr 문자열)인데 최종값이 글자면 원래 표현으로 감쌈. 쉼표로 이은 값은 원소로 나눔 |
| 채점 | `cli/bench.py` `_TRUTH_KEY_ALIASES`·`_TRUTH_DROPPED_KEYS` | 정답지 옛 키 → 새 키, `투여량` 채점 제외(`_ZERO_BLANK_KEYS`에서도 뺌) |

규칙셋 버전(`2026.09.24`)은 올리지 않았다. 배포 때 담당 세션과 `RULE_SET_VERSION` 결정 필요.

### Docraft

| 항목 | 위치 | 내용 |
|---|---|---|
| 이름 변경 | `backend/doctypes.py`, `rulesets/rules.yaml`(labels 키·totals 매핑) | 출력 키 `선택진료료이외총액`. 인쇄 표기 별칭(`선택진료료외` 등)은 유지 |
| 투여량 | `doctypes.INTERNAL_COLUMNS`·`public_fields`·`public_quality`, `main.py`(/api/read), `verify.py`(/api/verify) | 판독·열 인식·행 계산(단가×투여량×횟수×일수)에는 계속 쓰고 응답에서만 뺀다 |

입원일자·퇴원일자는 판독 서비스라 글자 하나로 돌려준다(하네스가 비교·형식 보존을 맡음). 입원 기간이 여럿 인쇄된 문서는 불일치로 검토될 수 있다.

### 정답지·채점 스크립트 (저장소 밖)

- `datasets/진료비세부내역서_테스트셋/golden`·`_draft` 각 200건: 키 이름 변경, `투여량` 열·칸 제거. 백업 `*.bak-20261014-before-field-change`. notes 자유 서술문은 손대지 않음. 변환 스크립트는 세션 임시 폴더라 남기지 않았다.
- `exp/e2e_call_test/make_report.py`(59건·205건 채점): 정답지를 읽을 때 `current_keys`로 옛 키→새 키, `투여량` 제외. 배열 값은 빈 원소를 빼고 쉼표로 이어 비교. 백업 `make_report.py.bak-20261014`.
- 손대지 않은 곳: `label_veiwer/storage/bundles/*/golden`(뷰어 실데이터 — 채점 별칭으로 대응), `label_veiwer/backend/doc_templates.json`(서식 정의, 별도 브랜치 필요), `harness-installer/apps/docraft` 사본(설치본 동기화 때 반영), 원본 데이터셋, `exp/e2e_call_test/out/*/scorer` 사본 등 실험 스크립트.

## 테스트

- harness 추가: 날짜 선후 배열 10종(같은 개수 통과·위반, repr 문자열, 한쪽 단일 2, 빈 원소, 개수 불일치, 전부 빈 값, 단일 문자열 2), 배열 형식 보존 4종(리스트, repr, 쉼표 이은 값, 비배열), 채점 별칭·투여량 제외 1종.
- Docraft 추가: 키 이름·합계 매핑, 내부 열 제외 함수, 투여량 인쇄 서식에서 응답 제외 + 행 계산 유지(100×2×3×1=600).
- 빠른 회귀(dev 병합 전, 로컬 `-n 4`): Docraft 4111 통과·3 xfailed. harness 2596 통과·21 실패 — 21건은 병합 전 dev(13b5822)에서도 같은 실패. 원인은 `docs/agentic-ocr-2.0.1-results/수술확인서`·`입퇴원확인서`에 들어온 `*.classification.*.json`(243ef68)이 견본 짝짓기 테스트를 깨는 것으로 이번 변경과 무관(별도 처리 필요).

## 남은 일

- AWS 배포 확인은 배포 담당 세션에 요청(dev push 후).
- `label_veiwer/backend/doc_templates.json` 항목 정의 변경 여부 결정.
- 하네스 README·PRD·sample-output 문서의 옛 이름 정리.
