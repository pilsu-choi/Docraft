---
type: Implementation Log
title: "작업 진행 중 로딩바"
description: "API 요청 대기나 백그라운드 문서 처리 중에 상단바에 로딩바와 진행 문구를 보여주는 기능 구현 기록"
tags: [frontend, feature, feedback, ux]
status: stable
---

# 작업 진행 중 로딩바

2026-09-22 · 브랜치 `feat/loading-bar` · 워크트리 `.worktrees/loading-bar`

## 배경

`feedback.md`의 "작업 진행 중일 때 로딩바 노출" 요청을 반영했다. 스키마 생성·업로드처럼 오래 걸리는 요청이나 파싱·추출처럼 백그라운드에서 도는 작업 중에 화면에 진행 표시가 없었다.

## 구현

- `frontend/src/main.tsx`: 이미 있던 두 상태를 하나의 `working` 문구로 묶었다. 새 상태나 컴포넌트는 만들지 않았다.
  - `loading`(`run()`이 요청을 기다리는 중) → `작업 처리 중…`
  - `polling`(프로젝트에 `queued`·`parsing`·`extracting`·`validating` 문서가 있음) → `문서 N개 처리 중…`
- `working`이 있으면 상단바 오른쪽에 문구(`role="status"`)를, 상단바 하단 경계에 3px 높이의 반복 애니메이션 로딩바(`.progress`)를 보여준다.
- `frontend/src/styles.css`: `.topbar`를 `position:relative`로 두고 `.progress`를 하단에 절대 배치해 레이아웃이 밀리지 않는다. `prefers-reduced-motion`에서는 애니메이션 없이 막대만 채워 보여준다.

## 검증

- `npm run build` 통과.
- 개발 서버에서 POST 요청을 멈춰 둔 채 `프로젝트 만들기`를 눌러 로딩바·`작업 처리 중…` 문구 노출과 버튼 비활성화를 확인했다.
