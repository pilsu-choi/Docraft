---
type: Implementation Log
title: "추출 지침·필드 구조 확대 편집 모달"
description: "추출 지침 입력과 스키마 필드 구조를 모달에서 크게 편집하고, 모달을 전체 화면으로 확대·축소하는 기능 구현 기록"
tags: [frontend, feature, feedback, schema]
status: stable
---

# 추출 지침·필드 구조 확대 편집 모달

2026-09-22 · 브랜치 `feat/zoom-modal` · 워크트리 `.worktrees/zoom-modal`

## 배경

`feedback.md`에 들어온 두 가지 요청을 반영했다.

- 추출 지침 입력 칸이 작다. 별도 모달에서 편집하고, 모달을 전체 화면으로 확대·축소할 수 있어야 한다.
- 스키마 편집의 필드 구조도 같은 방식으로 확대·축소할 수 있어야 한다.

## 구현

- `frontend/src/ui.tsx`에 공용 `Modal`을 추가했다. 헤더에 전체 화면·축소 토글과 닫기 버튼이 있다. `Esc` 키나 배경을 클릭해도 닫힌다. 기본 크기는 최대 880×640px이고, 전체 화면으로 바꾸면 뷰포트 전체를 쓴다. `expand`·`shrink`·`close` 아이콘도 함께 추가했다.
- `frontend/src/main.tsx`
  - 추출 지침 칸 아래에 "크게 편집" 버튼을 두었다. 모달 안의 큰 textarea는 기존 입력 칸과 같은 `prompt` 상태를 쓰므로 양쪽 내용이 항상 같다.
  - `VisualSchema`에 선택 prop `expand`를 추가했다. 이 prop이 있으면 헤더에 "크게 보기" 버튼이 나오고, 버튼을 누르면 같은 `schemaText`를 편집하는 `VisualSchema`가 모달에 열린다. 모달 안에서는 `expand`를 넘기지 않아 버튼이 중첩되지 않는다.
  - 어느 모달이 열렸는지는 `zoom: 'prompt' | 'schema' | null` 상태 하나로 관리한다.
- `frontend/src/panels.css`: 모달 스타일을 추가했다. 기존 `.schema-editor .schema-enum` 선택자는 모달 안에서 적용되지 않아서 `.visual-schema .schema-enum`으로 바꿨다.

## 검증

- `npm run build` 통과.
- Playwright로 확인한 항목: 스키마 탭에서 추출 지침 모달 열기 → 전체 화면 전환 → 닫기, 필드 구조 모달에서 필드를 추가하면 뒤쪽 인라인 편집기에 바로 반영되는지, 전체 화면에서 필드 행 레이아웃이 깨지지 않는지.
