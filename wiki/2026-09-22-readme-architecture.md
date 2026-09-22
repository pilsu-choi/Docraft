---
okf_version: "0.2"
type: Implementation Log
title: "README 아키텍처·처리 흐름 시각화와 현행화"
description: "실제 코드 기준으로 일반 추출과 AO 검증의 구조·스키마·실행 흐름을 구분하고 Mermaid로 시각화한 문서 갱신"
tags: [documentation, readme, architecture, mermaid, verify]
status: stable
---

# README 아키텍처·처리 흐름 시각화와 현행화

2026-09-22 · 브랜치 `docs/readme-architecture` · 워크트리 `.worktrees/readme-architecture`

## 목적

README의 긴 설명을 서비스 관계도와 처리 흐름으로 바꾸고, 현재 구현과 다른 설명을 바로잡는다. Mermaid를 사용해 GitHub에서 문서 안에 바로 렌더링되도록 한다.

## 변경 사항

- React UI, FastAPI, PostgreSQL, 파일 저장소, 선택적 Celery worker·브로커와 OCR·모델 서비스의 관계를 시각화한다.
- 일반 문서 파싱·추출의 비동기 실행과 AO 검증 요청의 동기 실행을 구분한다.
- 일반 추출은 저장된 사용자 JSON Schema, verify는 `doctypes.py`의 유형별 고정 필드 정의를 사용한다는 차이를 설명한다.
- 트윈리더의 라벨 동의어·정규화·파생 규칙은 Python으로 이식된 것이며 스키마 익스텐션을 동적으로 읽지 않음을 명시한다.
- 취소된 룰 1차 추출은 현행 구조에 포함하지 않는다. verify는 PaddleOCR → LLM 추출 → 룰 보정 → AO 비교 → 필요 시 Judge 흐름을 유지한다.
- 실행 방법, 주요 설정, API 사용과 검증 명령을 정리하고 과거 테스트 개수를 현재 결과처럼 기재하지 않는다.

## 근거와 검증

`backend/main.py`, `jobs.py`, `worker.py`, `parsers.py`, `engine.py`, `verify.py`, `doctypes.py`, `rules.py`, `config.py`, `compose.yaml`, `.env.example`을 대조했다. README와 이 기록의 내부 링크가 모두 유효하며 Mermaid CLI로 다이어그램 3개를 SVG로 렌더링하는 데 성공했다. `git diff --check`를 통과했다. 애플리케이션 코드 변경이 없어 백엔드 테스트와 프론트 빌드는 재실행하지 않았다.

## 관련 문서

- [README](../README.md)
- [작업 큐](2026-09-22-job-queue.md)
- [AO 교차검증](2026-09-22-ocr-verify.md)
