---
type: Implementation Log
title: "AGENTS.md 작업 규칙 보강"
description: "저장소에서 이미 따르던 브랜치·워크트리, 커밋 메시지, wiki 작성 규칙을 AGENTS.md에 명시했다"
tags: [docs, agents, convention]
status: stable
---

# AGENTS.md 작업 규칙 보강

2026-09-21 · 브랜치 `docs/agents-md-rules` (워크트리 `.worktrees/agents-md-rules`)

세션마다 암묵적으로 따르던 규칙을 AGENTS.md에 적어 일관성을 유지하도록 했다.

## 변경

| 위치 | 변경 |
| --- | --- |
| AGENTS.md | 브랜치·워크트리(`.worktrees/<주제>`, `feat/`·`fix/`·`docs/` 접두사, 병합 후 정리), 커밋(한국어 접두사, `--no-ff` 병합 커밋), wiki(frontmatter 필드, 본문 첫머리, index·log 갱신) 규칙 추가 |
| .gitignore | Playwright MCP 산출물 `.playwright-mcp/` 제외 |

검증 명령, feedback.md 처리 방식, 보안·개인정보 항목은 사용자 요청에 따라 넣지 않았다.
