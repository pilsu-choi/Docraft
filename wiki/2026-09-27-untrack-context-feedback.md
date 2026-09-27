---
okf_version: "0.2"
type: Implementation Log
title: "임시 맥락·피드백 문서 Git 추적 해제"
description: "정제 전 context.md와 feedback.md를 저장소 추적 대상에서 제거하고 재추가를 방지한 기록"
tags: [git, repository, documentation]
status: active
---

# 임시 맥락·피드백 문서 Git 추적 해제

- 날짜: 2026-09-27
- 브랜치: `fix/untrack-context-feedback`
- 워크트리: `.worktrees/untrack-context-feedback`

## 배경

정제 전 `context.md`와 `feedback.md`가 `dev`에 커밋되어 원격에 올라갔다. 두 파일은 로컬 작업 메모이므로 저장소의 현재 파일 목록에서 제외한다.

## 변경

- 두 파일을 Git 인덱스에서 제거했다. 작업용 로컬 사본은 유지한다.
- 루트 `.gitignore`에 `/context.md`와 `/feedback.md`를 추가해 실수로 다시 추적되지 않게 했다.
- 기존 공유 커밋 기록은 유지한다. 이전 커밋에 들어간 파일 내용까지 삭제하는 이력 재작성은 이번 변경에 포함되지 않는다.

## 확인

- `git ls-files context.md feedback.md` 결과가 비어 있는지 확인한다.
- `git check-ignore context.md feedback.md`로 무시 규칙을 확인한다.
