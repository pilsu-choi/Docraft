---
type: change
title: 영수증 문서 단위 인쇄 정합(PRINT_REGISTER) 이식
description: 진료비영수증 금액 층이 양식 칸선에서 반 행가량 통째로 밀려 찍혀 VLM 이 이웃 행에 붙여 읽은 값을, band 위치 상자와 OCR 줄 좌표로 문서마다 이동량 하나를 정해 되돌리는 후처리를 기본 꺼짐 설정으로 이식했다. 저장 결과 재생에서 실험(GRID+b)과 197건·g25 25건 모두 행 단위로 일치(197건 고침 48·깨뜨림 0, g25 0/0)
tags: [docraft, 진료비영수증, 인쇄어긋남, 행어긋남, band, ocr, 후처리]
status: active
---

날짜: 2026-10-09
브랜치: `feat/print-register`(dev 기준, dev 에 `--no-ff` 병합, push 안 함)
워크트리: `Docraft/.worktrees/print-register`(병합 후 정리)
실험·근거: 상위 wiki `2026-10-09-receipt-print-register.md`("g25 재현 확인·항목 격자 한정(GRID)", "Docraft 이식 지점 조사"). 외부 호출·AWS 없음.

## 근본 원인과 문제 유형
- 근본 원인: 미리 인쇄된 양식 위에 프린터가 금액 층을 통째로 평행이동해 찍었다(반 행 위/아래). VLM 은 값은 맞게 읽지만 칸선 기준으로 이웃 행에 붙인다. 값마다 생기는 오류가 아니라 문서 한 장에 한 번 생기는 오류다.
- 문제 유형: **양식 층과 프린터 금액 층의 정합 오류**. 값 하나씩 가까운 행으로 옮기면(이전 실험 ocr_realign 고침 12·깨뜨림 12) 앵커 하나의 오차가 그대로 깨뜨림이 된다. 문서 단위 이동량 하나로 다룬다.
- 동반 유형(같은 원인): 이름 앵커가 항목표 밖 같은 높이 글줄(왼쪽 결제 칸의 '합계' 등)에 오염 → 이름 상자를 항목 격자 왼쪽 끝 오른쪽으로 한정. 위치 응답 `[[x0,y0,x1,y1]]` 한 겹 감싼 형식은 이미 `band.boxes`(`_box`)가 정규화하므로 그대로 쓴다.

## 변경
| 파일 | 내용 |
|---|---|
| `backend/print_register.py`(신규) | 순수 함수 `register(rows, blocks, found, page=1) -> (rows, info)`. 기울기 보정 → 항목 격자 안 숫자 상자를 인쇄 줄로 묶음(한 줄 상자에 금액이 여럿이면 글자 위치 비례로 토큰마다 x 분할, `rules._MULTI_AMOUNT`) → 항목명 글줄 앵커(`rules.item` 정규화 + 이름표 유사도, Theil-Sen 거름) → 구간 보간 행 좌표 → 합계 줄 기준점 → c 탐색(경계 제약: 합계 줄=합계 행, 첫 행~합계 행, 한 행 한 줄) → 게이트(\|c\|≥0.3, 줄 70% 이상이 행 중심 0.25행 안) → 줄 단위 이동, 도착 칸 점유면 문서 포기. 동점 깨기·보조 기준점·산술 되돌림 없음(실험 STEPS=b). 모호하면 손대지 않음 |
| `backend/engine.py` | `extract(..., located=None)`: band 위치 상자(`found`)를 선택 out 인자 dict 로 전달. 반환 구조 불변 |
| `backend/verify.py` | `read` 의 `engine.extract` 직후·`rules.apply` 직전. 진료비영수증·`PRINT_REGISTER` 켜짐일 때만 `located` 를 넘기고, 위치 상자가 있고 1쪽·바로 선 쪽(`_turns` 없음)일 때만 적용. info 는 `latency.note("print_register")`(diagnostics). 적용 시 groundings 다시 계산 |
| `backend/config.py` | `PRINT_REGISTER`(기본 false, `_flag`) |
| `.env.example`·README 설정 표·helm `backend.printRegister`(values·config 템플릿)·`deploy/aws/.env.aws.example` | 같은 이름으로 반영, 모두 false |
| `tests/test_print_register.py`(신규) | 아래 목록 |

- `rules.apply` 안에 두지 않은 이유: `rules.apply` 는 좌표 없는 Judge 정규화·재처리 콜백에서도 불린다.
- `_misplaced_total` 과의 순서: 합계 금액까지 바로 위 행에 붙어 읽힌 문서는 합계 줄을 못 찾는다(실험은 total shift 를 먼저 적용한 입력을 썼다). `register` 가 내부에서 `rules._misplaced_total` 을 먼저 본 행으로 정합하고, 적용할 때만 그 결과를 돌려준다(뒤의 `rules.apply` 는 이미 옮겨진 합계를 다시 옮기지 않음). 같은 기능을 새로 만들지 않고 기존 함수를 재사용.
- 이름표 유사도(difflib)는 Docraft 에 같은 용도(OCR 글줄 ↔ 행 이름) 함수가 없어 모듈 안에 두었다. `pair_rows` 는 표 행끼리 키 열 일치라 쓸 수 없다.

## 1단계: 줄 단위 OCR 확인
- Docraft 줄 OCR(`_attach_lines`)은 PP-OCRv5 검출 상자 하나가 `lines` 한 개(`rec_boxes` 직사각형)다. 실험 OCR(`ocr_gpu_fix_1009`·`ocr_ppcpu_g25_1009`)은 같은 모델(`deploy/paddleocr/ocr_lines.yaml`)의 `dt_polys` 라 단위가 같다. 좌표계는 197건 모두 원근 뺀 보정 이미지(`t200_fixed_nopersp_images`, VLM 입력과 같음).
- 금액 여러 개가 한 상자로 붙은 숫자 상자: 197건 48/14,060(0.34%, 38문서), g25 4/1,733(0.23%), `docraft_ocr_fixed` lines 9/1,893(0.48%). 글자 위치 비례 분할로 대응.

## 재생 검증(호출 없음)
스크립트 `exp/e2e_call_test/print_register_replay.py`: 저장 band 결과 + 위치 응답(`band.boxes` 통과) + OCR(`dt_polys` → 둘러싼 직사각형 bbox, 한 블록)로 `register` 를 돌려 실험 출력 폴더와 행 단위 비교.

| 셋 | 입력 | 실험(GRID+b)과 행 동일 | 적용 문서 | 칸 고침/깨뜨림 |
|---|---|---|---|---|
| 197건 | tshift(실험 입력) | 197/197 | 6(155549239489428·16757…·fax_27·모바일0·모바일5·모바일7(이동 0)) | **+48 / 0**(표 98.054→98.255%) |
| 197건 | 원 band 결과(Docraft 순서, total shift 전) | 196/197(fax_25 는 미적용, tshift 와 원 결과 차이일 뿐) | 같은 6 | 같음 |
| g25 | band 결과 | 25/25 | 0 | 0 / 0 |

- 사유 분포(197건): 합계 줄 못 찾음/받침 없음 79, 정상(c 작음) 63, 줄 부족 26, 앵커 부족 13, 모호 7, 적용 6, 위치 응답 불량 2, 경계 제약 1.
- `_misplaced_total` 선적용 전에는 모바일0 이 합계 줄을 못 찾아 1값(2칸)을 놓쳤다 → 위 순서 처리로 해결.

## 추가 테스트(`tests/test_print_register.py`, 11건)
- 반 행 위 어긋남 고침, 반 행 아래 어긋남 고침
- 정상 인쇄 불변(게이트 c 작음)
- 한 줄 상자에 금액 두 개 붙은 경우 분할 후 고침(분할 없으면 합계 줄 못 찾음)
- 정확히 반 행 어긋나 같은 적합도의 다른 배정 → 모호, 불변
- 도착 칸 점유 → 문서 포기, 불변
- 표 왼쪽 결제 칸 '합계' 글줄 오염: 격자 한정 없으면 정상 문서를 옮기고, 있으면 불변
- 위치 응답 한 겹 감싼 상자(`band.boxes`) 정규화 후 적용
- 합계 금액이 바로 위 행에 붙은 경우 `_misplaced_total` 과 순서 충돌 없음(register → rules.apply 결과 일치)
- `verify.read`: 바로 선 1쪽 영수증은 rules.apply 전에 정합·diagnostics `print_register`, 회전 쪽·설정 꺼짐은 건너뜀(꺼짐이면 `located` 도 안 넘김)
- 영향 테스트 581 passed·3 xfailed, 빠른 회귀(`-m "not slow" -n 4`) 1068 passed·3 xfailed.

## 남은 위험·범위 밖
- 이동 문서가 197건 중 6건뿐이고 같은 셋으로 설계·평가했다. g25 는 인쇄 어긋남 문서가 없어 "깨뜨리지 않음"만 확인. 새 데이터에서 켜기 전 확인 필요해 기본 꺼짐.
- 운영 Docraft 는 레이아웃 블록 밖 OCR 줄을 버린다(`_attach_lines`). 재생은 한 블록에 모든 줄을 담았으므로 표가 레이아웃 블록 밖으로 잘린 문서는 결과가 다를 수 있다. 운영 이미지는 보정 이미지가 아닐 수 있어 기울기·원근이 크면 게이트에서 대부분 걸러진다.
- band 읽기가 실패해 rowmajor 로 읽은 경우에도 위치 상자가 있으면 적용된다(행 값·이름은 같은 쪽 기준이라 기하는 유효).
- 범위 밖: 연속 다중 행 밀림 일부, VLM 행 누락이 겹친 경우(fax_15·fax_35), 이름 밀림(4절), 회전 쪽.
