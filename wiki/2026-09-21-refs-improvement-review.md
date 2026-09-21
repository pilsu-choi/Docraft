---
type: Research
title: "레퍼런스 기반 개선·기능 추가 후보"
description: "refs(Upstage·LlamaParse·LandingAI) 화면과 현재 UI·backend를 비교해 정리한 개선·신규 기능 후보와 우선순위"
tags: [research, plan, frontend, backend, competitor]
status: stable
---

# 레퍼런스 기반 개선·기능 추가 후보

2026-09-21 · 브랜치 `docs/refs-improvement-review` (워크트리 `.worktrees/refs-review`)

`refs/` 캡처 76장([경쟁 제품 화면 캡처](refs-competitor-capture.md))을 제품별 sub-agent(Sonnet)가 판독하고, 현재 `main`(999696c)의 `backend/*.py`, `frontend/src/*`를 직접 읽어 비교했다. 이 문서는 조사 결과이며 코드는 바꾸지 않았다.

## 진행 상태

2026-09-22에 권장 순서 1~3단계(#1 제외: `fix/extract-grounding-block-id`에서 별도 진행)를 구현했다. #2~#9, A, B, C가 완료됐고, 구현 기록은 [레퍼런스 기반 개선 1~3단계 구현](2026-09-22-refs-improvements.md)에 있다. #1은 `fix/extract-grounding-block-id`가 main에 병합되면서(`b42ce95`) 완료됐다. 남은 후보는 D~K다.

`#1`은 애초 제안한 "블록 id 참조 grounding"이 아니라 [서버 측 행 grounding](2026-09-21-extract-grounding-block-id.md)으로 교체돼 완료됐고, `#1`이 함께 언급한 "페이지 단위 분할 추출"은 별도 브랜치 `fix/extract-page-chunking`에서 마저 구현했다([추출 페이지 단위 분할 호출](2026-09-22-extract-page-chunking.md)). 긴 문서에서 예산을 넘는 뒤쪽 블록을 조용히 버리던 `_block_lines`를 페이지 경계를 지키는 다중 호출과 스키마 기반 병합으로 대체했다.

## 조사 시점 상태 요약

- 이미 있음: 프로젝트 CRUD, 업로드·파싱(pypdf/fitz 줄 단위 bbox, PaddleOCR-VL), `미리보기|Markdown|HTML|JSON`, AI 스키마 생성, 시각 스키마 편집기(문자열·숫자·참거짓·객체·객체 목록, required, 필드 설명), 스키마 버전, 추출 신뢰도·검증, 필드↔bbox 호버 연동, 수정·승인, JSON/CSV 내보내기.
- 레퍼런스 대비 비어 있음: 파싱 옵션, 블록 타입 세분화·블록 목록 연동, 신뢰도 임계값 UI, 다중 문서 결과 표, 분류·분할, 배치, 사용량·키 관리.

## 1. 기존 흐름 품질 개선 (우선 권장)

| # | 항목 | 근거 ref | 현재 코드 상태 | 규모 |
| --- | --- | --- | --- | --- |
| 1 | 긴 문서 추출 안정화: 블록 id 참조 grounding, 페이지 단위 분할 추출 | - | `engine.extract()`가 근거 JSON을 문자열로 `[:40000]` 잘라 보내 JSON 중간이 끊긴다. bbox는 좌표 문자열 일치로 검증한다. `fix/extract-grounding-block-id` 브랜치에 블록 id 방식이 미병합 상태로 있다. | M |
| 2 | 신뢰도 임계값 슬라이더와 일괄 강조 | llamaparse `extract_results`, landingai `parse_display_options` | 임계값 0.7이 `engine.validate()`에 고정돼 있다. | S |
| 3 | 결과 필드 클릭 시 해당 페이지로 이동·스크롤, 스키마 필드까지 3방향 강조 | llamaparse `extract_citation_highlight`, landingai `extract_field_grounding` | 페이지 전환은 되지만 확대 상태에서 bbox로 스크롤하지 않는다. | S |
| 4 | 파싱 블록 목록(번호·타입 라벨)↔원문 bbox 양방향 연동, 타입별 색상 | landingai `parse_results`·`parse_block_grounding`, upstage `parse_results` | 파싱 블록 bbox는 표시만 되고 상호작용이 없다. 블록 타입은 text/table/heading뿐이다. | M |
| 5 | 문서 목록 API 경량화 | - | `list_documents`가 문서마다 `markdown`·`blocks`·`result` 전체를 돌려준다. 목록용 요약 필드만 반환하면 된다. | S |
| 6 | 문서 삭제 | landingai `projects_crud` | 문서 삭제 endpoint와 UI가 없다. | S |
| 7 | 스키마 enum 타입, 필드 순서 변경, JSON Schema 파일 업로드 | llamaparse `extract_schema_builder`, landingai `build_schema`·`suggested_schema_results` | enum이 없고, AI 생성은 UI에서 현재 문서 1건만 보낸다(백엔드는 `document_ids` 다건 지원). | S |
| 8 | 코드 스니펫 탭(curl·Python·JS) | landingai `get_code`, llamaparse `parse_code` | README에는 `API` 탭이 있다고 적혀 있지만 현재 UI에는 탭이 없다. | S |
| 9 | CSV 내보내기에서 객체 목록을 행으로 펼치기, XLSX | llamaparse `parse_results_json` | `flatten()`이 배열을 JSON 문자열 한 칸으로 넣는다. | S |

## 2. 신규 기능 후보

| # | 기능 | 근거 ref | 설명 | 규모 |
| --- | --- | --- | --- | --- |
| A | 다중 문서 결과 표 | upstage `table_view_extract`·`table_view_instruct` | 프로젝트 문서×스키마 필드를 한 표로 비교·필터·정렬하고 한 번에 내보낸다. 리뷰 시간(PRD 핵심 KPI) 단축에 직접 기여한다. | M |
| B | 일괄 추출(배치) | llamaparse `batch`, upstage `agents_list` | 선택 문서 전체에 스키마를 한 번에 적용한다. BackgroundTasks 대신 작업 큐·작업 테이블(상태·소요 시간)이 필요하다. | M |
| C | 파싱 설정 | llamaparse `parse_upload_config`·`parse_advanced_options`, landingai `parse_config`·`model_select`, upstage `editor_parse_settings` | 페이지 범위, 파서 선택(library/paddle), 표 출력 형식(HTML/Markdown), 결과 캐시를 문서·프로젝트 단위로 지정한다. | M |
| D | 문서 분류 | upstage `editor_classify_classes`·`classify_results`, llamaparse `classify_*`, landingai `classify_*` | 클래스(이름+설명)를 정의하면 문서·페이지를 분류하고 신뢰도와 근거를 붙인다. 클래스별 스키마 자동 매핑으로 이어진다. PRD Later. | M |
| E | 문서 분할 | upstage `split_documents_extract`, llamaparse `split_*`, landingai `split_results` | 여러 서식이 섞인 PDF를 페이지 구간별 하위 문서로 나눈다. D 이후 진행한다. PRD Later. | L |
| F | 판정(Instruct) 단계 | upstage `editor_instruct_decisions`·`instruct_results`·`citation_highlight` | 추출값을 `@필드`로 참조하는 프롬프트와 사용자 정의 판정값(승인/보류 등), 각주식 인용을 붙인다. PRD의 Validation Agent에 해당한다. | L |
| G | 계층 목차(Section) | landingai `section_parse`·`section_results` | 파싱 블록을 목차 트리로 묶고 원문 영역과 연결한다. | M |
| H | 문서 채팅 | landingai `chat`, llamaparse `index` | 단일 문서 질의응답. 근거 bbox 인용을 재사용한다. | M |
| I | 작업 모니터링 | upstage `agent_monitor`, landingai `settings_usage` | 작업별 소요 시간·실패율·수정률(correction)을 집계한다. `audit_log`와 `corrections`를 재사용한다. PRD Evaluation Dashboard. | M |
| J | 예제·템플릿 갤러리 | landingai `home_examples`, upstage `library`, llamaparse `extract_schema_builder`(Browse templates) | 샘플 문서와 업종별 스키마 템플릿으로 첫 추출까지 시간을 줄인다. | S~M |
| K | Webhook·API 키 관리 | llamaparse `parse_advanced_options`, landingai `settings_api_key` | 완료 알림과 다중 키 발급. 현재는 단일 `DOCRAFT_API_KEY`다. | M |

범위 밖으로 둔 것: 과금·플랜(landingai `settings_plan_billing`), 노드 그래프 워크플로 편집기(upstage `workflow_graph`), 스케줄·외부 드라이브 연동(upstage `scheduled_tasks`). 모두 D·F·B가 먼저 있어야 의미가 있다.

## 권장 순서

1. 1번(추출 안정화) → 5·6번(목록 경량화·삭제) → 2·3번(임계값·근거 이동). 기존 흐름의 신뢰도와 속도를 먼저 올린다.
2. A(결과 표) + B(일괄 추출): 여러 문서를 다루는 실사용 흐름을 만든다.
3. 4·7·8·9와 C: 파싱·스키마·API 편의 기능.
4. D → E → F: 분류·분할·판정 파이프라인(PRD Later).
