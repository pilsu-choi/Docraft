---
type: change
title: 영수증 맨 오른쪽 열 — 열 맞바꿈 쪽 고르기·금액산정 경계 자르기
description: 합계 행과 항목 행 열 합이 엇갈릴 때 인쇄 머리글로 틀린 쪽(항목 행/합계 행)을 고르고, 표 오른쪽 끝을 금액산정 패널 라벨 정렬선으로 정한다. 197건 재생 표 98.05→98.14%(고침 22·깨뜨림 1), g25 변화 없음, 크롭 잘림 16→4칸
tags: [docraft, 진료비영수증, band, rules, 열맞바꿈, 크롭]
status: active
---

날짜: 2026-10-12
브랜치: `fix/rightcol-band`(dev 21db625 기준)
워크트리: `Docraft/.worktrees/rightcol-fix`

근거 감사: `datasets/진료비영수증_테스트셋/rightcol_audit_1012/report.md`(맨 오른쪽 열 놓침 원인), `locate_audit_1012/report.md`(위치 잘림). LLM·VLM·외부 API 호출 없음(저장 응답 재생).

## B. 열 맞바꿈이 맞던 항목 행을 옮김

- 근본 원인: `rules._swaps` 는 합계 행과 항목 행의 두 열 합이 엇갈리면 항상 "항목 행이 틀렸다"고 보고 항목 행 열을 바꿨다. 합만으로는 "항목 행을 이웃 열로 읽음"과 "합계 행만 이웃 열로 읽음"이 대칭이라 가를 수 없다. band 읽기는 본문 띠를 선택진료료외로 맞게 읽고 합계 행이 든 마지막 띠만 비급여·선택진료료로 적는 일이 있어 맞던 값을 틀린 열로 옮겼다.
- 문제 유형: 대칭인 두 설명 중 근거 없이 한쪽을 고르는 후처리. 범위는 영수증 열 맞바꿈의 두 경로 — `apply`(최종 출력)와 `check`·`run`(AO 교정 `RECEIPT.COLUMN_SWAP`). 세부내역서 `_detail_swaps` 는 이미 인쇄 자리 근거를 쓴다.
- 수정(`backend/rules.py`):
  - `_printed_under(blocks, doc_type)` 를 두 문서에 쓴다. 세부내역서는 기존대로 가장 가까운 머리글 x, 진료비영수증은 금액 칸 위에 겹쳐 찍힌 글자 줄을 아래부터 위아래로 붙은 무리로 묶어 `_receipt_column` 으로 열 이름이 되는 첫 무리(`_receipt_head`). 쪼개 인쇄된 '선택진료료 / 이외'를 이어 읽는다. 영수증 머리글은 `table_layout.header_positions`(세부내역서 낱말)로 잡히지 않아(10건 모두 `few_header_columns`) 별도 읽기가 필요했다.
  - `_swaps(rows, blocks)` 는 `(a, b, 합계 행만인지)` 를 낸다. 두 열 값이 인쇄된 칸의 머리글이 모두 항목 행 쪽 읽기와 맞으면 합계 행만, 합계 행 쪽과 맞으면 항목 행을 바꾼다. 근거가 없거나 엇갈리면 항목 행을 바꾼다(기존 동작).
  - `_swap` 은 `(a, b, True)` 쌍이면 합계 행만 바꾼다. `check` 알림에 `totals`, `run` 사유에 "합계 행"이 붙는다.
  - `_OTHER_THAN` 이 '선택'을 '선태'로 읽은 한 글자 오독도 받는다(기존 '이외'→'미외' 허용과 같은 유형).
- 근거 없을 때의 선택(197건 재생): 맞바꿈이 걸린 10건 중 머리글 근거가 생긴 8건은 모두 정답지와 같은 쪽을 골랐다(합계 행만 6건, 항목 행 2건: 104330541…·3-8). 근거 없는 2건(fax_34: 머리글 OCR 오독, 홈페이지3: OCR 에 값 없음)에서 항목 행 바꿈 4칸·바꾸지 않음 3칸·합계 행만 2칸이라 기존 동작(항목 행)을 유지했다. 참고로 근거 없이 일괄로 정하면 합계 행만 +11칸·맞바꿈 끔 +7칸이지만, 항목 행이 실제로 틀린 3건(104330541…·3-8·fax_34)을 깨뜨린다 — 대칭이라 일괄 규칙은 어느 쪽이든 틀린다.

## C. 금액산정 경계 자르기가 맨 오른쪽 열을 자름

- 근본 원인: 위치 응답의 표·패널 경계가 한 열쯤 어긋난다(패널 상자가 표 맨 오른쪽 열을 덮음: 일반 2, 표 상자가 그 열 앞에서 끝남: 모바일9·100599096…HK001_1). `band.boxes` 는 패널 상자 왼쪽 끝을 그대로 표 끝으로 썼다.
- 수정: `band.boxes(reply, lines)` — 패널이 표 옆(표 가로 40% 오른쪽)이면 표 오른쪽 끝 = 패널 라벨(한글 두 글자 이상, 패널 상자 안·표 본문 높이)의 왼쪽 정렬선(`band.panel_edge`: 왼쪽 끝이 15/1000 안에 가장 많이 모인 자리). 표와 패널에 걸친 안내 문구·표 칸 오독 글자가 섞여도 정렬선은 그대로다. 라벨 근거가 없으면 기존대로 패널이 겹칠 때만 그 왼쪽에서 자른다. `engine._page_lines` 가 같은 쪽 OCR 줄을 모델 이미지처럼 바로 세워(`parsers.unturn`) 1000 정규화로 넘긴다. 띠 여백(±20)은 그대로.
- 측정(`exp/e2e_call_test/rightcol_clip_measure.py`, locate_audit 방식: 정답 칸 OCR 상자가 띠 크롭 합집합 안인지):

| | inside | partial | outside | 패널 글자 줄이 크롭에 절반 이상 든 수 / 문서 |
|---|---|---|---|---|
| 수정 전(dev) | 2,371 | 11 | 5 | 372 / 86 |
| 수정 후 | 2,383 | 2 | 2 | 640 / 112 |
| (참고) 라벨 정렬선 −5 | 2,383 | 2 | 2 | 470 / 88 |

  잘림 16칸 중 12칸이 풀렸고 새로 잘린 칸은 없다. 남은 4칸은 다른 원인(1-47 아래쪽, 영수증6 왼쪽, 일반 10 은 표 맨 오른쪽 열이 패널보다 더 오른쪽에 인쇄된 서식). 정렬선에서 −10 이상 당기면 새 잘림이 4~23칸 생겨(표 끝과 라벨 사이가 10/1000 안인 서식이 많다) 정렬선 그대로 두었다. 가장 왼쪽 라벨(최솟값)을 쓰면 걸친 문구 탓에 2칸이 새로 잘렸다.
- 한계: 크롭이 바뀌면 띠 판독 응답이 달라지므로 재생으로 정확도를 잴 수 없다. 잰 것은 정답 칸 상자가 크롭 안에 드는지와 패널 글자 줄이 얼마나 더 드는지뿐이다. 패널 글자가 더 든 문서 26건의 이웃 값 오인 여부는 재호출(AWS) 측정이 필요하다. `PRINT_REGISTER`(기본 꺼짐)는 같은 `located` 상자를 쓰므로 켤 때 표 오른쪽 끝이 바뀐 상자를 받는다.

## 재생 결과(B, 호출 없음)

`exp/e2e_call_test/rightcol_fix_replay.py`: 저장된 띠·금액산정·F 응답을 실험 합치기로 다시 합쳐 지정 Docraft 의 `rules.apply` 에 저장 OCR(한 표 블록)과 함께 넣고 채점. 산출물 `datasets/진료비영수증_테스트셋/rightcol_fix_1012/`(base_*·fixB_* 폴더의 cells.csv).

| 셋 | 수정 전 표 | 수정 후 표 | 고침 / 깨뜨림 |
|---|---|---|---|
| 197건 `vlm_band2_1-3-4-6-8-9-10_t200fixnp`(OCR 블록) | 23,429/23,894 = 98.05% | 23,450 = 98.14% | 22 / 1 |
| 197건 같은 응답, OCR 없음(`rules.apply(…, [])`, 실험 저장 결과와 196/197 동일) | 98.05% | 98.05% | 0 / 0 |
| 197건 짧은 키 `…-15-16_t200fixnp`(Docraft 이식 형식) | 23,380 = 97.85% | 23,403 = 97.95% | 23 / 0 |
| g25 `vlm_band2_1-3-4-6-8-9-10_g25`(OCR 블록) | 2,867/2,889 = 99.24% | 99.24% | 0 / 0 |

고친 문서: 100599096…HK001_1·2-9·Fax 4·Fax 5·fax_20·scan_10(짧은 키 셋은 fax_29 포함). 깨뜨림 1칸(scan_10 처치및수술료 선택진료료외)은 모델이 값을 다른 행(검사료)에 적은 행 어긋남 탓이며 맞바꿈 쪽 자체는 맞다. 재생의 OCR 블록은 GPU OCR 줄을 한 표 블록으로 넣은 근사라 실제 파싱 블록(셀 행 포함)과 다른 규칙 경로가 있을 수 있다.

## 테스트

변경 영향 테스트 16개 파일 1,026 passed·3 xfailed(`-n 4`). 추가: `test_rules.py` — `test_a_column_swap_turns_back_the_side_the_printed_header_disagrees_with`(합계 행만 틀림·항목 행 틀림·'선태' 오독·머리글 없음·OCR 없음 5개), `test_a_total_row_read_into_the_neighbour_column_is_the_one_turned_back`(apply·check·run), `test_conflicting_printed_headers_leave_the_swap_to_the_item_rows`, `test_receipt_head_reads_a_header_split_over_lines_and_skips_text_that_names_no_column`. `test_band.py` — `test_the_table_ends_where_the_panel_labels_begin`(패널이 열을 덮음·표 상자가 짧음·걸친 문구·라벨이 본문 높이 밖·OCR 없음·패널이 아래 6개), `test_band_locates_the_table_end_from_the_upright_ocr_lines_of_the_page`. 기존 `test_a_whole_column_read_into_its_neighbour_is_swapped_back`(OCR 없음 → 항목 행 되돌림)은 그대로 통과.
