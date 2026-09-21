# 경쟁 제품 화면 캡처 (Upstage Studio, LlamaParse, LandingAI)

- 사용자 요청: `refs/landingai`처럼 Upstage Agentic Studio와 LlamaParse 주요 화면을 캡처해 폴더별로 정리한다.
- 캡처 환경: Playwright MCP 전용 Chromium(1600×1000, CSS 배율 1)에서 사용자가 직접 로그인한 세션을 사용했다.
  - Windows Chrome은 원격 디버깅 포트가 WSL(NAT)에서 보이지 않고, 세션 쿠키 반출은 권한 정책상 막혀 이 방식을 택했다.
- 크레딧 소모 없음: Upstage는 라이브러리 예제와 기존 결과, LlamaParse는 "Try a sample file"의 미리 계산된 결과를 사용했다.
- Upstage 워크스페이스에 라이브러리 예제 `보험금 청구 문서 세트 자동 처리 (copy)` 에이전트를 복사해 두었다(편집기 스키마 화면 캡처용).

## refs/upstage (20장)

| 구분 | 파일 |
| --- | --- |
| 탐색 | `home`, `library`, `library_agent_detail`, `agents_list`, `scheduled_tasks` |
| 워크플로 예제 | `workflow_graph`, `classify_results`, `extract_results`, `instruct_results`, `citation_highlight` |
| 에이전트 작업 화면 | `parse_results`, `parse_results_json`, `split_documents_extract`, `table_view_extract`, `table_view_instruct`, `agent_monitor` |
| 에이전트 편집기 | `editor_parse_settings`, `editor_classify_classes`, `editor_extract_schema`, `editor_instruct_decisions` |

## refs/llamaparse (29장)

| 구분 | 파일 |
| --- | --- |
| 탐색 | `home`, `files`, `index`, `batch` |
| Parse | `parse_upload_config`, `parse_advanced_options`, `parse_code`, `parse_results_markdown`, `parse_results_text`, `parse_results_json`, `parse_results_images` |
| Parse bbox | `parse_view_options`, `parse_highlight_levels`, `parse_bbox_layout`, `parse_bbox_line`, `parse_bbox_word`, `parse_bbox_cell` |
| Extract | `extract_upload_config`, `extract_build_config`, `extract_schema_builder`, `extract_schema_json`, `extract_results`, `extract_citation_highlight` |
| Split | `split_upload`, `split_categories`, `split_results` |
| Classify | `classify_upload`, `classify_rules`, `classify_results` |

## refs/landingai (기존 6장 + 보충 21장)

- 기존: `home`, `projects_crud`, `parse_results`, `extract_results`, `build_schema`, `suggested_schema_results`
- 보충은 기존 프로젝트 결과와 "Examples"(Lab Test Reports) 예제만 열어 크레딧을 쓰지 않았다(작업 전후 잔여 454.6).

| 구분 | 파일 |
| --- | --- |
| 탐색·설정 | `home_examples`, `model_select`, `api_library`, `settings_api_key`, `settings_plan_billing`, `settings_usage` |
| Parse | `parse_results_json`, `parse_display_options`, `parse_config`, `parse_block_grounding`, `parse_hover_grounding`, `get_code`, `tool_menu` |
| Extract | `extract_schema_panel`, `extract_field_grounding` |
| Split / Classify / Section / Chat | `split_results`, `classify_results`, `classify_results_json`, `section_parse`, `section_results`, `chat` |

## 참고할 만한 UI 패턴

- Upstage: Parse→Classify→Extract→Instruct를 노드 그래프로 편집하고, 분류 결과별로 문서를 분할해 각 스키마로 추출한다. Instruct 결과의 인용 번호를 누르면 원문 해당 영역이 강조된다.
- LlamaParse: 결과 bbox를 Layout/Line/Word/Cell 단위로 전환해 표시한다. Extract 필드 값을 누르면 해당 페이지로 이동해 근거를 강조하고, 신뢰도 임계값 슬라이더로 낮은 신뢰도 필드를 표시한다.
- LandingAI: 블록 목록과 원문 bbox가 양방향으로 연결되고, Extract 결과 JSON의 항목을 누르면 원문 셀(tableCell)이 강조된다. Display 메뉴에서 단어 신뢰도 임계값(기본 95%)과 atomic grounding 표시를 조절한다.
