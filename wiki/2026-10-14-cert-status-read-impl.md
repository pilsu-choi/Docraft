---
okf_version: "0.2"
type: implementation
title: 진단상태(임상적추정·최종진단) 칸 판독 구현 — harness feat/cert-status-read · Docraft feat/read-options
description: AO가 20% 안팎으로 잘못 읽는 진단서 4종 임상적추정·최종진단을 바로잡는 장치를 구현했다. 하네스는 AO parse 글자 위치로 원본을 맞춰 병명 칸을 잘라 Docraft에 칸 상태만 묻고, 1005 규칙으로 Y/N을 계산한 뒤 AO와 대조한다. 설정 CERT_STATUS_READ로 켜며 기본은 꺼짐이다. 실제 코드끼리 연결해 조정에 쓰지 않은 40건으로 확인한 결과 오답 0, 검수 2, AO 오류 5/5를 고쳤다.
tags: [harness, docraft, 진단서, 임상적추정, 최종진단, checkbox, ao-parse, read-options]
status: active
---

날짜: 2026-10-14
브랜치:
- harness-v2 `feat/cert-status-read` 0b0c155 (dev cb63753 기반)
- Docraft `feat/read-options` 71e985f (dev 2b4bc0e 기반)
워크트리: `harness-v2/.worktrees/cert-status-read`, `Docraft/.worktrees/read-options`
배경·검증 이력: [임상적추정·최종진단 오추출 원인](2026-10-14-cert-diagnosis-status-checkbox-cause.md)

## 흐름

비동기 경로(`fallback=True`)에서만 돈다. 이 경로에서만 AO parse를 받기 때문이다.

1. parse 스레드: `_parse_tables`가 끝나면 이어서 `_read_cert_status`를 돈다. 이 스레드는 Docraft ③과 겹쳐 돌아서 지연이 거의 늘지 않는다.
2. 하네스 `reread/option_crop.py`:
   - `align_page`: AO 보정 틀에 원본을 맞춘다. 후보는 회전 4 × 반전 2 × {늘리기, 축척 1·맞춤 축척의 2차원 위치 격자}다. 잉크 점수는 국소 대비로 계산하고, 원본 방향이 1등의 85% 이상이면 원본 방향을 쓴다.
   - `option_crop`: 선택지 글자의 가장 위 묶음을 기준점으로 잡고, 없으면 `병명` 라벨을 쓴다. 높이 400px 이상으로 키워 자르고, `kinds`도 함께 낸다.
3. Docraft `POST /api/read-options`: 잘라낸 PNG를 받아 두 자리 고정 칸 상태를 돌려준다. 모델은 `OPTION_VLM_MODEL`이고 추론은 끈다. JSON 오류는 1회 다시 호출한다.
4. 하네스 `normalizer/cert_status.py`:
   - `decide_status`: v4 판정(1005 규칙 ①~④)
   - `status_fixes`: AO와 대조한다.

| 판독 | AO | 처리(`action`) |
|---|---|---|
| 값 있음 | 같음 | 확정 `confirmed` (PASS) |
| 값 있음, (Y,Y) 아님 | 다름 | 교정 `corrected` (10-n, `correction_basis=reread`) |
| (Y,Y) | 다름 | 다른 칸은 검토 `review` |
| 판정 불가 | — | 검토 `review`(기본값 N 유지) |
| 판독 안 함(parse·이미지·기준점 없음, Docraft 실패) | — | `not_read`, 증거 없음 |

- 확정한 칸은 ④' 재판정 대상에서 뺀다.
- 기록 위치는 `harness.parser.documents[].cert_status`, 처리 시간은 `timings`의 `cert_status` 구간이다.

## 설정

| 저장소 | 이름 | 기본값 |
|---|---|---|
| harness | `CERT_STATUS_READ` | false |
| harness | `CERT_STATUS_READ_TIMEOUT` | 20.0초 |
| Docraft | `OPTION_VLM_MODEL` | 비우면 `AI_VLM_MODEL` |

## 검증

정렬:
- 합성 1700×2300 쪽에서 0.3초, 4000×5400 쪽에서 0.56초 걸린다.
- 단순 어둡기 점수로 바꾸면 어두운 배경 테스트가 실패하는 것을 확인했다. 국소 대비가 실제로 효과가 있다.

줄 잇기를 기존 함수로 바꾼 영향:
- 하네스는 프로토타입의 줄 잇기 대신 기존 `title_rows`를 재사용한다.
- 80건 실물에서 `kinds`가 같은 문서는 71건이다. 다른 9건 중 8건은 하네스가 놓친 `최종` 글자를 더 찾은 경우이고, 1건은 반대다.

실제 코드 연결 확인(하네스 잘라내기 → Docraft `verify.read_options` → 하네스 `decide_status`):
- 표본은 v4 검증 40건이고, 모델은 qwen/qwen3.8-27b, OpenRouter 40회를 썼다.
- 결과는 자동 정답 38, 자동 오답 0, 검수 2다. AO 오류 5건은 모두 교정됐다.
- 시간은 중앙값 1.4초, 최대 3.9초다.

단위·회귀 테스트:
- 하네스 새 테스트 43건이 통과했다. 변경 영향 11개 파일 706건도 통과했다.
- `test_ui_response.py[입퇴원확인서]` 1건은 dev에서도 같이 실패하는 기존 실패다.
- Docraft 새 테스트와 ai_provider 테스트 61건이 통과했다. 빠른 회귀는 4,123건 통과, 3건 xfail이다.

## 남은 일

- 켜기 전에 배포 모델(Docraft 기본 qwen3-vl-32b)로 다시 재야 한다. 아니면 `OPTION_VLM_MODEL`을 27B로 따로 지정한다.
- 동기·UI 응답 경로에는 AO parse가 없어 이 기능이 돌지 않는다. 고객사 호출 경로를 확인해야 한다.
- `_rule_10n`이 REREAD_ONLY 교정의 근거를 `reread`로 바꾼다. 이 변경은 기존 Docraft 분류 열 채택 교정(`value_fix` 325·377)에도 적용된다.
