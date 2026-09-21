---
type: Experiment and Implementation Log
title: "표 모델 비교와 VLM 셀 텍스트 교정(TABLE_REFINE)"
description: "PaddleOCR-VL·PP-StructureV3 표 모듈·Qwen3-VL 32B/8B를 샘플 5종 표 7개로 비교하고, VL의 격자에 VLM 셀 교정을 얹는 하이브리드를 구현한 기록"
tags: [backend, parser, table, paddleocr, vlm, experiment]
generated: {by: claude-code/claude-opus-5, at: 2026-09-22}
status: stable
---

# 표 모델 비교와 VLM 셀 텍스트 교정(TABLE_REFINE)

- 날짜: 2026-09-22
- 브랜치: `feat/table-refine`
- 워크트리: `.worktrees/table-refine`

[table-spans](2026-09-22-table-spans.md)의 후속이다. 병합 셀 보존을 고친 뒤에도 남는 PaddleOCR-VL-0.9B의 인식 오류를 줄일 모델을 `samples/agentic-ocr-2.0.1-results/images/` 5종(표 7개)으로 비교했다. 표 영역은 VL의 `block_bbox`로 잘랐다.

## 비교 결과

| 후보 | 구조(행·열·병합) | 글자 | 비고 |
| --- | --- | --- | --- |
| PaddleOCR-VL-0.9B (현행) | 7개 모두 빈칸 없는 직사각형 격자. 원본과 거의 일치 | `료`→`로`, `670925`→`670825`, 세로 글자 오독 | 기준 |
| PP-StructureV3 표 모듈 (SLANeXt + RT-DETR 셀 검출, `korean_PP-OCRv5_mobile_rec`, CPU) | 무너짐. 세부내역서는 여러 품목이 한 행에 합쳐지고, 진료비영수증 오른쪽 영역이 어긋남 | 정확 (`진찰료`, `기본항목`, `선택항목`) | 표 방향 분류(`PP-LCNet_x1_0_doc_ori`)가 crop을 180° 돌려 글자가 뒤집혔다. `use_table_orientation_classify=False`가 필요했다 |
| Qwen3-VL-32B (OpenRouter, crop → HTML) | 행 폭이 제각각. 진료비영수증은 빈칸 81개 | 정확 | 표당 7~72초 |
| Qwen3-VL-8B | 행 폭이 제각각 | 대체로 정확 | 셀 교정 실험에서 값을 지우고(`나동휘`→빈칸) 약품명을 지어냄(`아섹젝`→`아세트아미노펜`) |

VL-0.9B는 구조를 잘 잡고 글자를 틀린다. 큰 VLM은 반대로 글자는 정확하지만 구조를 잃는다. 어느 쪽도 다른 쪽을 대체하지 못하므로 둘을 합쳤다.

## 구현: VL 격자 + VLM 셀 교정

- `backend/engine.py` `refine_table(block, source)`는 표 영역을 OCR 이미지 해상도 이하로 잘라(`_data_url(page, clip, max_zoom)`) 셀 목록 `{번호: 텍스트}`와 함께 `AI_VLM_MODEL`로 보낸다. 모델은 틀린 셀만 `{번호: 교정 텍스트}`로 돌려주고, 코드는 해당 `<td>`의 내용만 바꾼다. 태그와 속성은 손대지 않으므로 격자가 바뀔 수 없다.
- 처음에는 셀 목록 전체를 같은 길이로 돌려받게 했다. 모델이 뭉친 셀(합계 행)을 쪼개 7개 중 4개가 길이 불일치로 버려져서, 번호별 교정 방식으로 바꿨다. 모델이 `corrections`로 감싸지 않고 번호 객체를 바로 돌려줄 때도 받는다.
- 반영하지 않는 교정(`_edit`):
  - `<img>` 같은 태그가 든 셀. 직인이나 약 사진 셀을 지우거나, 없는 글자(`김선미 (서명 김선미)`)를 채워 넣었다. 이런 셀은 모델에 보내지 않는다.
  - 값을 비우거나 빈칸을 채우는 교정. 예: `현금영수증`→`''`.
  - 원문과 유사도 0.5 미만인 교정. 셀 사이로 텍스트를 옮긴 경우다. 예: `2. 전액 본인부담…`→`1. 일부 본인부담…`, `현금영수증`→`현금승인번호`. 3자 이하 셀은 예외라서 `⑧`→`⑥`은 허용한다.
- `backend/parsers.py`의 `parse()`는 PaddleOCR 표 블록에 교정을 적용한 뒤 `rows`와 `spans`를 다시 만든다.
- `TABLE_REFINE`(기본 `false`)으로 켠다. provider가 설정되지 않았거나(`AI_MODE=local`) 호출이 실패하면 VL 원문을 유지한다. provider 호출 제한 시간은 300초다.
- 같이 고친 버그: PaddleOCR 경로(`_remote_paddle`)가 `_html_table_rows()`로 `rows`만 받아 `spans`가 저장되지 않았다. 그래서 스캔 문서 미리보기에서 병합 셀이 합쳐지지 않았다. `_html_table()`이 `rows`와 `spans`를 함께 돌려주도록 바꿨다.

## 검증 (실제 파이프라인, qwen3-vl-32b)

| 문서 | 교정 수 | 대표 교정 | 소요 |
| --- | --- | --- | --- |
| 진료비영수증 | 30 | `진 찰 로`→`진찰료`, `670825`→`670925`, `양수증번호`→`영수증번호`, `정액`→`전액 본인부담`, `홍액`→`총액`, `⑩납부한`→`⑪납부한`, `③ 4 ⑤`→`③ ④ ⑤`, `억삼동`→`역삼동`, `연세앙은`→`연세밝은` | 32초 |
| 세부내역서 | 5 + 2 | `아세트아미노렌`→`아세트아미노펜`, `영양수택`→`영양수액`, `덕스판테놀`→`덱스판테놀` | 6초 |
| 진단서 | 3 | `이상체증강소`→`이상체증감소`, `끝다공증`→`골다공증`, `입 상 책 추 정`→`임상적 추정` | 2초 |
| 소견서 | 4 | `항원시`→`창원시` | 3초 |
| 약제비영수증 | 4 + 1 | `아섹젝`→`아세정`, `필름코딩쟁`→`필름코팅정` | 2초 |

남은 한계:
- 세로 글자는 여전히 틀린다(`기본항목`→`기본 환자 항목`, `선택항목`→`개월 년수`).
- 확인할 수 없는 교정이 일부 있다(`당의정`→`타원정`, `성`→`명`, `박상우`→`박상우 [○]`).
- 교정 전 원문은 블록에 남기지 않고 로그(`table refine: cells=… changed=…`)만 남긴다.
- 테스트는 `pytest -q` 90 passed다. PaddleOCR 표의 `spans` 보존과, 교정 규칙(이미지 셀 제외, 비우기·텍스트 이동 거부, 격자 불변)을 추가로 검증했다.

## 재현

- PP-StructureV3: `paddlex --get_pipeline_config table_recognition_v2`로 설정을 받아 layout·doc preprocessor를 끄고, OCR을 `PP-OCRv5_server_det` + `korean_PP-OCRv5_mobile_rec`으로 바꾼다. 그다음 `paddleocr-vl` 이미지에서 `create_pipeline(..., device="cpu").predict(crop, use_table_orientation_classify=False)`로 실행한다. 모델 볼륨은 `docraft_docraft_paddlex_models`를 재사용했다.
- VLM: OpenRouter `qwen/qwen3-vl-32b-instruct`, `qwen/qwen3-vl-8b-instruct`, temperature 0.
