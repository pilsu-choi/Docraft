---
type: Implementation Log
title: "피드백 UI 반영"
description: "feedback.md 4개 항목(필드 근거 호버, Markdown·JSON 토글, 스키마 설명 편집) 반영"
tags: [frontend, feedback]
status: stable
---

# 피드백 UI 반영

2026-09-21 · 브랜치 `feat/feedback-ui` (워크트리 `.worktrees/feedback-ui`)

`feedback.md`의 4개 항목을 반영했다.

| 피드백 | 반영 |
| --- | --- |
| 추출 필드마다 b-box 호버링 | 결과 필드에 마우스를 올리면 해당 grounding 상자가 강조되고, 페이지가 다르면 그 페이지로 이동한다. 원문의 필드 상자(초록)에 올리면 해당 결과 행이 강조되고 경로·근거 텍스트 툴팁을 보여 준다. 원문 근거 카드는 호버 중인 필드, 없으면 클릭한 필드를 보여 준다. 위치가 없는 필드는 `위치 없음`으로 표시한다. |
| 문서 분석 행 기반 배치 (`markdown \| json`) | 세로로 쌓인 `details` 두 개를 `Markdown \| JSON` 세그먼트 토글과 단일 출력 영역으로 바꿨다. |
| 스키마 필드 설명 자동 생성·수정, 한글 우선 | 시각 편집기의 각 필드 아래에 설명 입력을 추가했다. 유형을 바꿔도 `title`·`description`을 유지한다. AI 생성 프롬프트는 중첩·배열 항목을 포함한 모든 필드에 한국어 우선 `title`·`description`을 요구한다. local 모드 fallback도 설명을 채운다. |
| 데이터 추출 JSON 미리보기 | 추출 결과에 `필드 \| JSON` 토글을 추가했다. |

- 두 토글은 공용 `Segments` 컴포넌트 하나를 쓴다. `Preview`의 `selected` prop은 `active`(호버 우선, 없으면 선택)와 `onHover`로 바꿨다.
- 필드 근거 상자는 평소에는 테두리만 있고 강조될 때만 채운다. 따라서 기존 `tests/ui_preview_layout.py`의 투명 배경 검사는 그대로 통과한다.

## 검증

- `frontend`: `npm run build` 성공.
- 백엔드: `uv run ... pytest -q tests` 27개 통과.
- API를 전부 모킹한 Playwright 검사(Vite 5176, 합성 PDF): Markdown/JSON 전환, 스키마 설명 불러오기·수정·JSON 반영·유형 변경 후 유지, 결과 행 호버 → 상자 강조와 근거 카드, 호버 해제, 상자 호버 → 행 강조, 결과 JSON 파싱, 390px 가로 넘침 없음을 확인했다. 실제 AI provider의 한국어 설명 생성은 호출하지 않았다.
- WSL에는 Chromium 의존 라이브러리(libnspr4, libnss3, libasound2)가 없다. sudo 없이 `apt-get download` 후 `dpkg -x`로 푼 경로를 `LD_LIBRARY_PATH`에 지정해 실행했다.
