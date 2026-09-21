---
type: Implementation Log
title: "Markdown·HTML 뷰어"
description: "Markdown·HTML 원본 렌더링, 분석 결과 미리보기·HTML 출력, HTML 업로드 파싱"
tags: [frontend, backend, feedback, viewer]
status: stable
---

# Markdown·HTML 뷰어

2026-09-21 · 브랜치 `feat/md-html-viewer` (워크트리 `.worktrees/md-html-viewer`)

`feedback.md`의 남은 항목 "markdown, html viewer 지원"을 반영했다. 나머지 4개 항목은 [피드백 UI 반영](2026-09-21-feedback-ui.md)에서 처리했다.

| 위치 | 변경 |
| --- | --- |
| 원문 패널 | `.md` 원본은 Markdown을 HTML로 렌더링하고, `.html`·`.htm` 원본은 그대로 렌더링한다. 이전에는 "미리보기를 지원하지 않는 파일"로 표시됐다. |
| 문서 분석 결과 | 토글을 `미리보기 \| Markdown \| HTML \| JSON`으로 늘렸다. 기본값은 렌더링된 `미리보기`이고, `HTML`은 Markdown에서 변환한 HTML 소스를 보여 준다. |
| 업로드·파싱 | `.html`·`.htm` 업로드를 허용한다. 표준 라이브러리 `HTMLParser`로 제목(`heading`), 본문(`text`), 표(`table`, `rows` 포함) 블록을 만들고 `script`·`style`·`head`는 버린다. |
| Markdown 생성 | 표 블록에 `rows`가 있으면 ` ```text ` 코드 블록 대신 GFM 표로 쓰고, 제목 블록은 `## `로 쓴다. `rows`가 없는 PaddleOCR 표(HTML)는 원문 그대로 넣어 렌더링되게 했다. `.txt`·`.md`는 PDF처럼 줄 단위(`\n`)로 잇는다. |

## 구현

- 공용 `frontend/src/Rendered.tsx`: `markdownHtml()`(`marked`, GFM·줄바꿈 유지)과 `Rendered` 컴포넌트 하나를 원문 패널과 분석 결과가 같이 쓴다.
- 보안: `Rendered`는 `sandbox=""` iframe의 `srcDoc`에 CSP(`default-src 'none'; style-src 'unsafe-inline'; img-src data:`)를 붙여 렌더링한다. 업로드된 HTML의 스크립트·폼·외부 리소스 요청이 모두 막히므로 별도 sanitizer 의존성을 두지 않았다.
- Chromium에서 sandbox iframe의 `srcDoc`을 빈 값에서 내용으로 바꾸면 그려지지 않았다. 원문을 받은 뒤에만 iframe을 마운트(`key={doc.id}`)해 해결했다.

## 검증

- 백엔드: `pytest -q tests` 29개 통과. `tests/test_parsers.py`가 HTML 제목·본문·표 블록과 GFM 표(`|` escape 포함) Markdown을 확인한다.
- 프론트: `npm run build` 성공.
- 이 브랜치의 백엔드(8010)와 Vite(5180)를 띄워 Playwright로 확인: `.md` 원본의 목록·굵게·표 렌더링, `.html` 원본 렌더링, 분석 결과 미리보기·HTML 소스 표시, 업로드 HTML의 `<script>`가 sandbox로 차단됨(콘솔 "Blocked script execution"), 문서 전환 후에도 원문 뷰어가 다시 그려짐.
- 문서를 바꿀 때 직전 문서의 해제된 blob URL을 한 번 fetch하며 콘솔 오류가 남지만, 결과는 무시되고 새 URL로 다시 불러온다.
