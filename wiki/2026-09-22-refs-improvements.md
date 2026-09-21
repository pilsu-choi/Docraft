---
type: Implementation Log
title: "레퍼런스 기반 개선 1~3단계 구현"
description: "문서 목록 경량화·삭제, 신뢰도 기준·근거 스크롤, 결과 표·일괄 추출·XLSX 내보내기, 블록 연동·스키마 편집·API 탭·파싱 옵션 구현 기록"
tags: [frontend, backend, feature, competitor]
status: stable
---

# 레퍼런스 기반 개선 1~3단계 구현

2026-09-21~22 · 통합 브랜치 `feat/refs-improvements` (워크트리 `.worktrees/refs-improvements`)

[레퍼런스 기반 개선·기능 추가 후보](2026-09-21-refs-improvement-review.md)의 권장 순서 1~3단계를 구현했다. 1번 "긴 문서 추출 안정화"는 `fix/extract-grounding-block-id`에서 따로 진행 중이라 제외했다. 그 브랜치와 충돌하지 않도록 `backend/engine.py`는 건드리지 않았고, 블록 id는 그 브랜치와 같게 `blocks` 배열 인덱스로 맞췄다.

## 진행 방식

단계마다 통합 브랜치에서 backend·frontend 브랜치를 나눠 sub-agent 2개를 병렬로 돌렸다. 계약(API 모양)은 코디네이터가 먼저 정했고, 백엔드는 Sonnet, 규모가 큰 프런트엔드(`main.tsx`)는 Opus가 맡았다. 두 브랜치를 `--no-ff`로 합친 뒤 `pytest`와 `npm run build`로 확인했다.

| 단계 | 브랜치 | 항목 |
| --- | --- | --- |
| 1 | `feat/refs-p1-backend`, `feat/refs-p1-frontend` | #5 문서 목록 경량화, #6 문서 삭제, #2 신뢰도 기준 슬라이더, #3 근거 위치로 스크롤 |
| 2 | `feat/refs-p2-backend`, `feat/refs-p2-frontend` | A 결과 표, B 일괄 추출, #9 CSV 행 펼치기·XLSX(내보내기 코드를 공유하므로 3단계에서 앞당김) |
| 3 | `feat/refs-p3-backend`, `feat/refs-p3-frontend` | #4 파싱 블록↔원문 연동, #7 스키마 편집, #8 API 코드 탭, C 파싱 설정 |

## 백엔드 변경 (`backend/main.py`, `parsers.py`, `db.py`)

| API | 내용 |
| --- | --- |
| `GET /api/projects/{id}/documents` | 쿼리 1회로 요약 필드만 반환한다(`markdown`·`blocks`·`groundings`·`corrections` 제외). 이전에는 문서마다 `document()`를 불러 N+1 조회였다. |
| `DELETE /api/documents/{id}` | 204를 반환한다. 처리 중(`queued`·`parsing`·`extracting`·`validating`)이면 409를 반환한다. 원본 파일은 `FILES` 하위일 때만 지운다. |
| `POST /api/projects/{id}/extract` | `{schema_id, document_ids}`(빈 목록은 전체)를 받아 202 `{queued, skipped[{id, filename, reason}]}`를 반환한다. 단건 추출과 자격 검사·큐 등록 helper를 공유한다. |
| `GET /api/documents/{id}/export`, `GET /api/projects/{id}/export` | `json·csv·xlsx`를 지원한다. `table_rows()`가 객체 목록을 여러 행으로 펼치고, 프로젝트 내보내기는 `document_id, filename, status` 열을 앞에 붙인다. 한글 파일명은 `filename*=UTF-8''`로 내보낸다. |
| `POST /api/documents/{id}/parse` | 선택 body `{pages, provider: auto·library·paddle, table_format: markdown·html}`를 받는다. `documents.parse_options`에 저장하고 상세 조회에 포함한다. PaddleOCR에 페이지 범위를 주면 선택 페이지만 임시 PDF로 보내고 페이지 번호를 원래 번호로 되돌린다. |

PaddleOCR 블록은 `block_label`을 `text·heading·table·figure·marginalia·formula`로 나누고 원래 값은 `label`에 남긴다. HTML 표는 기존 `_HtmlBlocks`로 `rows`를 만들어 프런트엔드가 원시 HTML 없이 표를 그린다.

## 프런트엔드 변경 (`frontend/src`)

- 새 파일
  - `ResultsTable.tsx`: 결과 표
  - `Blocks.tsx`: 분석 블록 카드
  - `ParseSettings.tsx`: 분석 설정
  - `ApiSnippets.tsx`: API 탭
  - `ui.tsx`: `Icon`·`statusText`·`Segments` 공용
- 결과 표
  - 상세 상단의 `문서 작업 | 결과 표`로 전환한다. 스키마 필드 열, 검증 오류 셀 강조, 검색·상태 필터·정렬, 선택 문서 일괄 추출, 프로젝트 내보내기를 제공한다.
  - 문서 상태 polling은 목록 1개로 합쳤다. 처리 중인 문서가 있을 때만 2초마다 조회한다.
- 블록 연동: 블록마다 `#index` 경로를 붙여 추출 필드와 같은 `hovered`·`selected` 상태를 쓴다. 별도 상태를 만들지 않았다. 스크롤은 원문 패널과 블록 목록 컨테이너 안으로 한정했다.
- 스키마 편집: 허용 값(enum), ▲/▼ 순서 변경, JSON Schema 파일 불러오기, 여러 참고 문서로 AI 스키마 생성을 추가했다.
- `04 API` 탭: 단계 목록 하나에서 cURL·Python·JavaScript 예시를 생성한다.

## 검증

- `pytest -q`: 47개 통과(시작 시점 29개).
- `npm run build`: 통과.
- 실제 백엔드 E2E: 임시 PostgreSQL schema, `AI_MODE=local`, 합성 2쪽 PDF 2개로 진행했다. 블록 카드 호버→원문 상자 강조, 2쪽 카드 클릭→페이지 이동, 결과 표에서 전체 선택 후 일괄 추출(2건 모두 `needs_review`), 검증 오류 셀 강조, 390px에서 가로 넘침 없음, 프로젝트 CSV·XLSX(한글 파일명), `pages=2`·`table_format=html` 재분석, 잘못된 페이지 범위 422, 문서 삭제 204를 확인했다. 확인 후 임시 schema와 파일은 지웠다.
- E2E에서 발견해 고친 것
  - 추출 이력이 없으면 결과 표에 스키마가 선택되지 않아 일괄 추출 버튼이 비활성이었다. 첫 스키마를 기본값으로 쓰도록 고쳤다.
  - FastAPI 422의 `detail`이 배열이라 오류 메시지가 `[object Object]`로 보였다. `api.ts`에서 배열·`{message}`·문자열 형태를 모두 처리하도록 고쳤다.

## 남은 것

- 로컬 heuristic 추출(`engine._local_extract`)은 `품목 | 수량` 같은 표 머리글을 `품목: 수량`으로 잘못 읽는다. `engine.py` 작업과 함께 다룬다.
- 일괄 추출은 여전히 BackgroundTasks로 순차 실행된다. 작업 큐·작업 이력 테이블은 후속(후보 I 모니터링)이다.
