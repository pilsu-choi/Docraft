---
type: Implementation Log
title: "표 병합 셀(rowspan·colspan) 보존"
description: "PaddleOCR-VL이 준 병합 셀 정보를 파서가 버려 표가 어긋나던 문제를 직사각형 격자와 spans로 고치고, 샘플 5종으로 검증하며 남은 모델 인식 오류를 정리한 기록"
tags: [backend, frontend, parser, table, paddleocr]
generated: {by: claude-code/claude-opus-5, at: 2026-09-22}
status: stable
---

# 표 병합 셀(rowspan·colspan) 보존

- 날짜: 2026-09-22
- 브랜치: `fix/table-spans`
- 워크트리: `.worktrees/table-spans`

복합 테이블·병합 셀 문서의 분석 품질 문제를 `samples/agentic-ocr-2.0.1-results/images/` 5종(진료비영수증·세부내역서·소견서·약제비영수증·진단서)으로 확인했다.

## 원인

PaddleOCR-VL(`PaddleOCR-VL-1.6-0.9B`)의 표 HTML에는 `rowspan`/`colspan`이 들어 있다. 하지만 `_HtmlBlocks`가 이 속성을 무시하고 `<td>`를 순서대로 펼쳤다. 그래서 병합 셀 뒤의 값이 왼쪽으로 밀렸다. 추출은 원본 HTML(`block.text`)을 쓰므로 영향이 없었다. 반면 미리보기 카드, Markdown/HTML 출력, 스키마 자동 생성 입력(`doc.markdown`)은 깨진 `rows`를 썼다.

| 표 | 원본 HTML의 span 반영 격자 폭 | 기존 파서의 행 폭 |
| --- | --- | --- |
| 진료비영수증 | 9 (병합 64개) | 1~8 |
| 세부내역서 #1 | 11 (병합 21개) | 2, 6, 10, 11 |
| 소견서 | 9 (병합 13개) | 1, 2, 3, 9 |
| 약제비영수증 #2 | 3 (병합 21개) | 1, 2, 3 |
| 진단서 | 5 (병합 10개) | 2, 3, 4 |

VL의 원본 격자는 7개 표 모두 빈칸 없는 직사각형이었다. 따라서 이번 문제는 모델이 아니라 후처리에서 생긴 것이다.

## 변경

- `backend/parsers.py`: `_HtmlBlocks`가 셀별 `rowspan`/`colspan`을 읽는다. `_grid()`는 이를 직사각형 격자로 펼친다. 병합 셀 값은 덮는 칸마다 반복되므로 각 행을 따로 읽어도 뜻이 통한다. 병합 위치는 `spans: [[행, 열, rowspan, colspan], ...]`로 남긴다. 셀이 없는 `<tr>`만 버리고, 빈 행은 행 위치를 유지하려고 남긴다. `table_format=html` 출력은 `spans`로 셀을 다시 병합한다.
- `frontend/src/Rendered.tsx`: `tableCells()`가 병합된 칸을 건너뛰고 첫 칸에 `rowSpan`/`colSpan`을 붙인다. 미리보기 카드(`Blocks.tsx`)와 HTML 뷰어(`blockHtml`)가 같은 함수를 쓴다.
- DOCX는 python-docx가 세로 병합 칸마다 다른 `_tc`를 돌려줘 병합을 믿을 만하게 판별할 수 없어 이번 범위에서 뺐다. XLSX는 read_only 모드에서 `merged_cells`를 쓸 수 없어 역시 뺐다.

## 검증

- 5종 7개 표 모두 행 폭이 하나로 맞는다. HTML로 출력한 뒤 다시 파싱하면 `rows`와 `spans`가 그대로 복원된다.
- 진료비영수증을 변경 전후로 렌더링해 비교했다. 변경 후 표는 원본 영수증 레이아웃과 같은 모양이다.
- `pytest -q` 88 passed(병합 격자·HTML 재병합 테스트 추가), `npm run build` 통과.

## 남은 모델 인식 오류 (진료비영수증)

후처리를 고친 뒤에도 남는 오류는 PaddleOCR-VL-0.9B 자체의 인식 오류다.

- 헤더 구조: `급여`가 3열(일부 본인부담 2열 + 전액 본인부담)이어야 하는데 2열로 나왔다. `전액 본인부담` 열이 빠지고 `정액 본인부담`으로 잘못 읽혔다.
- 합계 행: `① 7,300 ② 17,300 ③ ④ ⑤ 40,000`이 셀 하나로 합쳐졌다.
- 세로 글자: `기본항목` → `기본 환자 명확 명`, `선택항목` → `개월 년수`.
- 글자 오인식: `료` → `로`(진찰로·입원로 등), `670925` → `670825`, `영수증번호` → `양수증번호`.
- 잡음: 셀 안의 `\n` 문자열, `$ ^{{*}} $` 같은 LaTeX 조각.

이 오류는 표 영역을 잘라 표 전용 모델(PP-StructureV3 표 모듈, TableFormer)이나 더 큰 VLM으로 다시 인식해야 줄일 수 있다. 추출 단계는 `AI_VISION`으로 페이지 이미지를 함께 보내므로 일부를 보정한다([vision-extract](2026-09-22-vision-extract.md)).

후속: 괘선이 인쇄된 표는 VLM 구조 대신 괘선 격자로 복원한다([ruled-table-grid](2026-09-22-ruled-table-grid.md)). 진료비영수증의 헤더 구조·합계 행 오류가 여기서 해소됐다.
