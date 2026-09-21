---
type: Implementation Log
title: "스키마 내보내기"
description: "스키마 편집 화면에서 편집 중인 JSON Schema를 title과 함께 파일로 내려받는 기능 구현 기록"
tags: [frontend, feature, feedback, schema]
status: stable
---

# 스키마 내보내기

2026-09-22 · 브랜치 `feat/schema-export` · 워크트리 `.worktrees/schema-export`

## 배경

feedback.md의 `스키마 내보내기` 항목이다. `JSON Schema 불러오기`는 이미 있었지만, 만든 스키마를 다른 프로젝트나 외부 도구로 옮길 방법은 없었다.

## 구현

- `frontend/src/main.tsx`의 `02 스키마 설계` → `스키마 편집` 머리에 `JSON Schema 내보내기` 버튼을 불러오기 버튼 옆에 추가했다.
- `exportSchema()`는 **편집기에 있는 현재 JSON**을 내려받는다. 저장하지 않은 수정도 포함한다.
- 스키마 이름을 JSON Schema의 `title`로 넣는다. 원래 있던 `title`은 현재 이름으로 바꾼다. `importSchema()`가 `title`을 스키마 이름으로 읽으므로 내보냈다가 다시 불러와도 이름이 같다.
- 파일명은 `<스키마 이름>.json`이다. 저장된 스키마면 `<스키마 이름>_v<버전>.json`이다.
- JSON 형식이 틀리면 `JSON Schema 형식이 올바르지 않아 내보낼 수 없습니다.` 오류 알림을 띄운다.
- 편집기 내용을 그대로 내려받으면 되므로 백엔드 API는 추가하지 않았다. API로는 기존 `GET /api/schemas/{id}`의 `json_schema`를 그대로 쓰면 된다.

## 검증

- `tsc --noEmit`와 `npm run build`가 통과했다.
- Playwright(Chromium)로 확인했다. `계약서.json`을 불러와 바로 내보내면 `계약서.json`이 `title: "계약서"`와 함께 내려받아졌다. 저장한 뒤 내보내면 `계약서_v1.json`이 같은 내용으로 내려받아졌다. 테스트 프로젝트는 삭제했다.
