---
okf_version: "0.2"
type: Implementation
title: "표 행을 키 열로 대응하고 세분 항목명을 보존"
description: "verify와 채점이 따로 쓰던 표 행 짝짓기 규칙을 rules.pair_rows 한 곳으로 모으고, 영수증 항목 행을 파서 표 순서·세분 항목명으로 바로잡고, 소계 행을 보존한 기록. 76건 rules 단계 전후 수치를 포함한다."
tags: [verify, rules, extraction, accuracy, evaluation, table]
status: active
---

# 표 행을 키 열로 대응하고 세분 항목명을 보존

2026-09-22 · 브랜치 `feat/kv-row-align` · 워크트리 `.worktrees/kv-row-align`

## 배경

[key-value 추출 정확도 개선 지점 검토](2026-09-22-kv-accuracy-review.md)가 꼽은 1순위(표 행 정렬·세분 항목명)를 구현한다.
기준선은 main `6f13166`의 76건 rules 단계 평가(`data/verify/eval-20260922-195058.json`)다. 캐시된 파싱·추출을
쓰므로 모델 호출은 없다.

## 원인 확인 (오류 사례 대조)

`items[].stages.rules.wrong`의 영수증 항목·세부내역서 행 오류를 원문 파싱 캐시(`*.parse.json`)와 대조했다.

| 확인한 원인 | 근거 | 조치 |
|---|---|---|
| `_receipt_table`이 파서 표에서 복원한 세분 항목 행을 표 **맨 끝**에 덧붙이고, 모델이 뭉친 상위 항목 행(`투약및조제료`·`주사료`)을 그대로 남겨 중복·순서 붕괴 | `1546387085517921.jpg`는 라벨 24행인데 26행이 되고 `투약및조제료_행위료`가 19번째에 붙었다. `SA2019070400018`은 `주사료`가 두 번 남았다 | 파서 표를 뼈대로 삼아 모델 행을 제자리에 맞추도록 재작성 |
| 채점·교차검증이 `항목`+`EDI코드`만 키로 써서, EDI코드 한 글자 오인식이 두 행의 시작일자·횟수를 서로 뒤바꿈 | `1120210831…tif` 16·17행(`CN001`/`DN001`, 라벨은 둘 다 `DN001`) → 시작일자 2건·횟수 2건 오답 | 키에 `시작일자`를 더하고 정의를 `rules.ROW_KEYS` 한 곳으로 |
| `_totals`가 소계 행을 무조건 삭제 | 코드 경로. 이 데이터셋에는 소계 행이 하나도 없어 수치로는 드러나지 않는다 | 집계 행을 표에 두는 유형(`KEEP_TOTALS`)은 소계도 남기고 합계 계산에서만 뺀다 |
| `verify._rows_same`이 행 순서·개수 완전 일치를 요구 | 코드 경로(rules 단계 평가는 `verify.py`를 타지 않아 수치에 잡히지 않는다) | 키 열 대응 + 셀 단위 비교로 교체 |

검토 문서가 지목한 "`rules.item()`이 `입원료_1인실`을 `입원료`로 뭉갠다"는 **재현되지 않았다**.
`ITEM_ALIASES`는 오히려 `입원료 1인실 → 입원료_1인실`로 세분 항목을 만든다. 실제 세분 항목 손실은
모델 추출이 상위 항목 하나로 뭉쳐 읽는 데서 오고, 파서 표에는 세분 항목명이 남아 있다.

## 변경

| 파일 | 함수 | 내용 |
|---|---|---|
| `backend/rules.py` | `ROW_KEYS`(신규) | 표 → 행 식별 열. 항목내역은 `항목`+`EDI코드`+`시작일자`(스키마에 없는 열은 건너뛴다) |
| | `pair_rows`(신규) | 키 열 값이 같은 행 → 접두가 같은 행(`_prefix_same`) → `fallback`이면 순서 순으로 짝짓는다. 짝 없는 행은 상대가 `None` |
| | `is_total`(신규) | 합계·소계 등 집계 행 판별. `_totals`·`_row_checks`·`_sum_checks`·채점이 함께 쓴다 |
| | `_totals` | 소계 행을 삭제하지 않는다(`KEEP_TOTALS` 유형). 합계 필드는 합계 행만 채운다 |
| | `_receipt_table` | 파서 표가 항목명 중복 없이 넉넉히 복원되면 그 목록을 뼈대로 삼아 모델 행을 `pair_rows(fallback=False)`로 제자리에 맞춘다(값은 모델 우선, 빈 칸만 파서 표로). 복원이 부실하면 빠진 항목만 인쇄 순서 자리(`_insert_at`)에 보충 |
| `backend/verify.py` | `_row_diff`(구 `_rows_same`) | 키 열로 행을 대응시켜, 대응된 행은 어긋난 **셀**만 `{"row","column","ao","docraft"}`로, 대응 안 된 행만 행 단위로 낸다. 빈 목록이면 두 표가 같다 |
| | `run`·`_decide` | 표 분쟁에 `diff`를 실어 Judge가 다시 읽을 셀을 짚어 준다. Judge 응답 형식(행 전체 반환)과 병합 경로는 그대로 |
| | `JUDGE_PROMPT` | `diff` 설명 한 문단 추가 |
| `scripts/verify_eval.py` | `pair_rows` | 자체 `ROW_KEYS`·`starts_with`·`is_total_row`를 지우고 `rules.pair_rows`·`rules.is_total`에 위임 |

## 결과 (76건, rules 단계)

명령: `scripts/verify_eval.py --manifest data/verify/accuracy-20260922/manifest.json --stage rules --cache-root data/verify/accuracy-20260922/pipeline-cache`

| 유형 | 정확도 전 | 후 | strict 전 | 후 | fp 전 | 후 |
|---|---|---|---|---|---|---|
| 진단서 | 85.0% (216/254) | 85.0% | 78.7% | 78.7% | 42 | 42 |
| 소견서 | 73.4% (215/293) | 73.4% | 71.7% | 71.7% | 51 | 51 |
| 진료비영수증 | 91.6% (2851/3111) | 91.6% | 76.7% | **76.8%** | 111 | **102** |
| 세부내역서 | 86.0% (3891/4524) | **86.1%** (3897/4524) | 84.4% | **84.6%** | 161 | 161 |
| 전체 | 87.7% (7173/8182) | 87.7% (7179/8182) | 80.9% | **81.0%** | 365 | **356** |

`--split holdout`(10건×4유형) 단독 실행은 전후가 완전히 같다.

| 유형 | 정확도 | strict | fp |
|---|---|---|---|
| 진단서 | 81.8% (99/121) | 77.7% | 28 |
| 소견서 | 65.5% (97/148) | 64.9% | 39 |
| 진료비영수증 | 92.6% (1918/2072) | 78.4% | 51 |
| 세부내역서 | 74.9% (1765/2355) | 73.8% | 105 |

기존 36건(existing)에만 효과가 났다: 전체 94.5→94.7%, strict 87.9→88.1%, fp 142→133.
필드 단위로는 영수증 `항목내역.항목` 오류 159→157(fp 34→32), 본인부담금 23→20·공단부담금 24→21(fp 각 6→3),
세부내역서 `시작일자`·`종료일자` 각 50→48이다. **나빠진 지표는 없다.**

## 되돌린 변경

`_receipt_item`의 표준 항목명 화이트리스트(`RECEIPT_ITEM_NAMES`)를 "료·대·비·실·금·액으로 끝나는 이름도 허용"으로
넓혀 보았다. 영수증 정확도 91.6→91.4%, strict 76.8→76.2%, fp 102→111로 나빠져 되돌렸다 —
표준 목록에 없는 행을 복원하면 안내문·머리글 조각이 항목 행으로 섞여 들어온다.

## 남은 오류의 주된 원인

1. **모델 추출이 인쇄된 표와 다르다.** holdout 영수증은 서식에 `의학료`·`혈액진단료`·`내복불출치료료`가 인쇄돼
   있는데 모델이 표준 항목 목록을 그대로 써 낸다. 반대로 `155799374711284.jpg`는 라벨 3행인데 26행을 지어낸다.
   행 짝짓기로는 손댈 수 없고 추출 프롬프트·근거 제약의 문제다.
2. **OCR 글자 오인식.** 세부내역서 `EDI명칭` 128건은 대부분 1~2글자 차이(`모티리톤`/`모티리론`)이고,
   영수증도 `제증명`→`제중영`, `전화상담료`→`전화봉화료`처럼 파싱 단계에서 이미 깨져 있다. 코드 마스터 대조
   (검토 문서 3순위)가 있어야 고친다.
3. **파서 표 복원 실패.** `SA2019101165425` 두 건처럼 TIF 품질이 나쁘면 머리글의 `항목` 셀조차 잡히지 않아
   `_receipt_rows`가 0행을 돌려주고 뼈대 보정이 아예 동작하지 않는다(라벨 28행 대 예측 7행).

라벨 자체 오류도 남아 있다(`3022033117174302-1.png`의 시작일자 `20020226`은 `20200226`이어야 한다).

## 테스트

`.venv/bin/python -m pytest tests -q` → 261 passed. 추가·수정한 항목:

* `test_pair_rows_matches_by_key_columns_not_by_order` — EDI코드 한 글자가 어긋나도 시작일자로 행이 밀리지 않는다(회귀 사례).
* `test_pair_rows_attaches_a_collapsed_item_name_to_its_detailed_row` — `주사료` 두 행이 `주사료_행위료`/`주사료_약품비`에 순서대로 붙는다.
* `test_pair_rows_leaves_a_row_without_a_counterpart_unpaired_when_asked` — `fallback=False`.
* `test_receipt_table_restores_detailed_item_names_in_printed_order` — 뭉친 항목명이 파서 표의 세분 항목명·순서로 복구된다.
* `test_apply_keeps_both_the_subtotal_and_the_total_row_of_a_receipt` — 소계 보존, 합계 필드는 합계 행만, 합계 검사는 소계를 빼고 계산(기존 "소계를 지운다" 테스트를 대체).
* `test_row_diff_ignores_row_order` / `…_reports_only_the_differing_cell_of_a_matched_row` / `…_reports_a_row_only_one_side_read_as_a_whole_row` — 셀 단위 dispute.

## 관련 자료

* [key-value 추출 정확도 개선 지점 검토](2026-09-22-kv-accuracy-review.md)
* [정확도 평가 확장과 홀드아웃 라벨 매니페스트](2026-09-22-accuracy-eval-expansion.md)
* [AO 교차검증 정답셋과 단계별 정확도 평가 스크립트](2026-09-22-ocr-verify-labels.md)
