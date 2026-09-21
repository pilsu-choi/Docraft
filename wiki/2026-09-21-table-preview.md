---
type: Implementation Log
title: "분석 결과 표 미리보기와 JSON 색상"
description: "문서 분석 미리보기를 블록 카드로 렌더링해 OCR 표를 표로 보여 주고, JSON 출력에 문법 색상을 입혔다"
tags: [frontend, viewer, table, json]
status: stable
---

# 분석 결과 표 미리보기와 JSON 색상

2026-09-21 · 브랜치 `feat/table-preview` (워크트리 `.worktrees/table-preview`)

LandingAI Parse 화면(`refs/landingai/parse_results.png`, `parse_results_json.png`)처럼 분석 결과의 표를 렌더링된 표로 보여 달라는 요청을 반영했다.

## 원인

미리보기는 저장된 `documents.markdown`을 `marked`로 렌더링했다. 이전 파서가 PaddleOCR 표 HTML을 ` ```text ` 코드 블록으로 감싸 저장했기 때문에, [Markdown·HTML 뷰어](2026-09-21-markdown-html-viewer.md)에서 파서를 고친 뒤에도 재분석하지 않은 문서는 표가 코드 텍스트로 보였다.

## 변경

| 위치 | 변경 |
| --- | --- |
| 미리보기 | `doc.markdown` 대신 `doc.blocks`를 `blocksHtml()`로 렌더링한다. 블록마다 `번호 - 유형 · p.페이지` 태그가 붙은 카드이며, 표는 `rows`가 있으면 표로 만들고 PaddleOCR 표는 HTML 원문(` ``` ` 펜스 제거, 셀 안 `\n` 문자열은 `<br>`)을 넣는다. 재분석 없이 기존 문서에도 적용된다. |
| HTML 탭 | 미리보기와 같은 `blocksHtml()` 소스를 보여 준다. Markdown 탭은 저장된 Markdown 그대로다. |
| JSON | `Json` 컴포넌트가 key(적색)·문자열(청색)·숫자(녹색)·true/false/null(보라)을 구분하고, 숫자·문자열만 담은 배열(bbox, page_size)은 한 줄로 접는다. 분석 JSON, 추출 결과 JSON, 검증·수정 기록에 쓴다. |
| 표 셀 | `word-break:keep-all`로 한글 단어가 글자 단위로 줄바꿈되지 않게 했고, 넓은 표는 카드 안에서 가로 스크롤된다. |
| 타입 | `types.ts`에 `Block`을 두고 `Document.blocks`를 `Block[]`로 바꿨다. `Preview.tsx`의 bbox 필터 타입 가드가 불필요해져 단순화했다. |

## 보안

PaddleOCR 표 HTML은 escape하지 않고 넣지만, 기존과 같이 `sandbox=""` iframe과 CSP 안에서만 렌더링된다. 텍스트·제목·`rows` 셀은 escape한다.

## 검증

- `npm run build` 성공.
- 이 브랜치의 Vite(5181)를 기존 백엔드(8000)에 붙여 Playwright로 PaddleOCR 결과 문서(`2303314528.png`)를 확인했다: 미리보기에 `1 - Text`, `2 - Table`, `3 - Table` 카드와 rowspan·colspan이 반영된 표가 보였고, JSON 탭에 색상과 한 줄 bbox 배열이 보였다.
- 텍스트 레이어 PDF는 여전히 줄 단위 `text` 블록만 만들므로 표 구조가 없다. 표로 보려면 표 인식이 되는 파서(PaddleOCR 레이아웃)를 거쳐야 한다.
