---
type: Bug Fix Log
title: "프로젝트 전환 시 이전 스키마 상태 노출 수정"
description: "새 프로젝트를 만들거나 다른 프로젝트로 이동할 때 이전 프로젝트의 탭·스키마 편집 상태가 남아 보이던 버그의 원인과 수정"
tags: [frontend, bugfix, schema, state]
status: stable
---

# 프로젝트 전환 시 이전 스키마 상태 노출 수정

2026-09-22 · 브랜치 `fix/project-state-reset` · 워크트리 `.worktrees/project-state-reset`

## 증상

기존 프로젝트에서 `02 스키마 설계` 탭을 연 상태로 새 프로젝트를 만들면, 새 프로젝트가 곧바로 스키마 설계 탭으로 열리고 이전 프로젝트의 스키마 이름·필드 구조(예: `Generated schema`, 36개 필드)가 그대로 보였다.

## 원인

`frontend/src/main.tsx`의 `App` 하나가 프로젝트 단위 상태(`tab`, `schemaId`, `schemaText`, `schemaName`, `prompt`, 선택 문서·근거, `view`, 확대 모달)를 모두 들고 있는데, `projectId`가 바뀔 때 `refreshDetail`로 목록만 다시 불러오고 이 상태들은 초기화하지 않았다. 서버 캐시가 아니라 클라이언트 상태가 남은 문제다. `schemaId`는 새 프로젝트의 스키마 목록에 없어 선택이 풀리지만 편집기 내용(`schemaText`·`schemaName`)은 남아 "새 스키마"처럼 보였고, 그대로 저장하면 이전 스키마가 새 프로젝트에 복제될 수 있었다.

## 수정

`projectId` effect에서 새로 불러오기 전에 프로젝트 단위 상태를 비운다: `project`·`docs`·`schemas`·`doc`을 비우고, 기존 `draft()`로 빈 스키마를 세팅하고, `prompt`를 비우고, 탭을 `parse`·화면을 `work`로 되돌리고, 선택·hover·모달을 닫는다. 새 함수는 추가하지 않았다.

## 검증

* `tsc --noEmit`, `vite build` 통과.
* Playwright로 같은 시나리오(기존 프로젝트 스키마 탭에서 저장된 스키마 선택 → 새 프로젝트 생성)를 main과 수정본에서 비교:
  * main: 활성 탭 `스키마 설계`, 스키마 이름 `Generated schema`, 필드 36개 — 재현.
  * 수정본: 활성 탭 `문서 분석`, 스키마 탭 진입 시 이름 `extraction_schema`, 필드 0개, 선택 `새 스키마`.
* 검증용으로 만든 프로젝트 2개는 API로 삭제했다.
