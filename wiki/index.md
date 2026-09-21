---
okf_version: "0.2"
---

# Docraft wiki

작업 기록은 Open Knowledge Format v0.2(`type` 등 YAML frontmatter + markdown 본문)을 따르며, 파일명은 `YYYY-MM-DD-<주제>.md`다. 변경 이력은 [log.md](log.md)에 남긴다.


# 계획과 구현 기록

* [추출·스키마 생성에 페이지 이미지 첨부](2026-09-22-vision-extract.md) - OCR 텍스트만 보내던 VLM 호출에 문서 페이지 이미지를 함께 보내 병합 셀 표의 값·합계 오류를 없앤 기록
* [OCR 줄 좌표 기반 grounding](2026-09-22-ocr-line-grounding.md) - 표 블록을 행 수로 균등 분할해 추정하던 grounding bbox를 PP-OCRv5 줄 단위 OCR 좌표로 교체한 기록
* [라벨 기준 grounding과 합계 필드 추출 지시](2026-09-22-label-grounding.md) - 같은 값이 여러 셀에 있을 때 필드 라벨 옆 줄을 고르고, 합계 필드가 개별 항목 값을 가져오던 추출 오류를 프롬프트로 바로잡은 기록
* [Backend P0 implementation (2026-09-21)](2026-09-21-backend-implementation.md) - FastAPI 백엔드 P0 최초 구현(SQLite·Tesseract 시기) 기록 (deprecated)
* [AGENTS.md 작업 규칙 보강](2026-09-21-agents-md-rules.md) - 브랜치·워크트리, 커밋 메시지, wiki 작성 규칙을 AGENTS.md에 명시
* [dev 통합 및 UI 확인](2026-09-21-dev-merge.md) - P0 구현을 dev 브랜치로 통합하고 UI를 실행한 작업 기록
* [작업 큐(Queue·Worker) 구조 도입](2026-09-22-job-queue.md) - 파싱·추출을 inline·celery로 교체 가능한 작업 큐에서 실행하고 공용 redis/Celery 인프라에 붙이는 구성
* [작업 큐 중단 작업 자동 복구](2026-09-22-job-recovery.md) - heartbeat lease와 기동 시 재등록으로 worker 중단·inline 재시작에도 문서가 멈추지 않게 한 구성
* [스키마 내보내기](2026-09-22-schema-export.md) - 편집 중인 JSON Schema를 title(스키마 이름)과 함께 파일로 내려받는 기능
* [프로젝트 전환 시 이전 스키마 상태 노출 수정](2026-09-22-project-state-reset.md) - 새 프로젝트 생성·이동 시 이전 프로젝트의 탭·스키마 편집 상태가 남던 버그의 원인과 수정
* [추출 지침·필드 구조 확대 편집 모달](2026-09-22-zoom-modal.md) - 추출 지침·필드 구조를 모달에서 편집하고 전체 화면으로 확대·축소하는 기능
* [표 병합 셀 보존](2026-09-22-table-spans.md) - PaddleOCR-VL 표의 rowspan·colspan을 직사각형 격자와 spans로 보존하고 남은 모델 인식 오류를 정리
* [작업 진행 중 로딩바](2026-09-22-loading-bar.md) - 요청 대기·백그라운드 문서 처리 중 상단바에 로딩바와 진행 문구를 보여주는 기능
* [추출 페이지 단위 분할 호출](2026-09-22-extract-page-chunking.md) - 긴 문서를 페이지 경계 기준으로 나눠 여러 번 호출하고 스키마에 따라 결과를 병합하는 구현
* [레퍼런스 기반 개선 1~3단계 구현](2026-09-22-refs-improvements.md) - 문서 목록 경량화·삭제, 결과 표·일괄 추출·XLSX, 블록 연동·스키마 편집·API 탭·파싱 옵션 구현
* [피드백 UI 반영](2026-09-21-feedback-ui.md) - feedback.md 4개 항목(필드 근거 호버, Markdown·JSON 토글, 스키마 설명 편집) 반영
* [Markdown·HTML 뷰어](2026-09-21-markdown-html-viewer.md) - Markdown·HTML 원본 렌더링, 분석 결과 미리보기·HTML 출력, HTML 업로드 파싱
* [분석 결과 표 미리보기와 JSON 색상](2026-09-21-table-preview.md) - 블록 카드 미리보기로 OCR 표 렌더링, JSON 문법 색상
* [Agentic OCR 2.0.1 fixture conversion](2026-09-21-fixture-conversion.md) - Agentic OCR 2.0.1 PNG fixture를 텍스트 레이어 포함 PDF로 변환한 절차
* [PRD 구현 작업](2026-09-21-implementation-session.md) - PRD P0 구현 세션의 브랜치·역할 분배·완료 범위
* [구현 기록](2026-09-21-implementation.md) - PRD P0 요구사항과 검증 근거 매핑, 통합 검증 결과
* [백엔드 로깅과 Docker 전체 스택](2026-09-21-logging-docker.md) - 백엔드 레벨별 로깅(docraft.log)과 postgres·backend·frontend Docker 전체 스택 구성
* [PaddleOCR-VL 로컬 Docker 호스팅](2026-09-21-paddleocr-docker.md) - PaddleOCR-VL을 compose ocr profile로 로컬 GPU에 호스팅한 구성과 검증
* [PDF 근거 상자 정밀화](2026-09-21-pdf-line-bbox.md) - PDF 근거 상자를 텍스트 블록에서 줄 단위로 정밀화
* [프로젝트 작업공간 백엔드 변경 기록](2026-09-21-project-workspace-backend.md) - PostgreSQL 전환, 프로젝트·스키마 CRUD, SQLite 이관 도구 기록
* [프로젝트 작업공간 개편](2026-09-21-project-workspace-plan.md) - 프로젝트 작업공간 개편의 사용자 요구와 작업 분배
* [UI 개편 제안 및 진행 상태](2026-09-21-ui-redesign-plan.md) - 단순하고 직관적인 UI 개편 방향과 진행 상태

# 조사

* [레퍼런스 기반 개선·기능 추가 후보](2026-09-21-refs-improvement-review.md) - refs 3사 화면과 현재 UI·backend를 비교한 개선·신규 기능 후보와 우선순위
* [PaddleOCR 호환성 조사](2026-09-21-paddleocr-compatibility.md) - PaddleOCR 원격·on-prem layout-parsing HTTP 계약과 Docraft adapter 출력 규약 조사

# 장애와 버그 수정

* [원문 근거 상자 표시 수정](2026-09-21-bbox-rendering-fix.md) - 원문 근거 상자가 정규화 좌표로 오인돼 잘못 그려지던 문제의 원인과 수정
* [추출 실패: VLM 응답 JSON 파싱 오류](2026-09-21-extract-json-parse-failure.md) - VLM 추출 응답 JSON 파싱 실패(Expecting ',' delimiter)의 원인 분석과 대응 후보
* [추출 grounding 서버 측 계산 전환과 json_object 계약](2026-09-21-extract-grounding-block-id.md) - extract()를 json_object 단일 결과 계약으로 바꾸고, grounding을 모델 응답 대신 서버가 원문 블록에서 값을 찾아 계산하도록 전환한 기록
* [원본 문서 미리보기 크기 수정](2026-09-21-ui-preview-fix.md) - 원본 PDF·이미지 미리보기가 패널보다 커지던 문제의 원인과 수정

# 테스트 기록

* [AI provider 검증 기록](2026-09-21-ai-provider-validation.md) - OpenAI 호환 AI provider 계약 테스트와 OpenRouter Qwen 실호출 검증
* [프로젝트 작업공간 테스트 기록](2026-09-21-project-workspace-tests.md) - 프로젝트 작업공간의 PostgreSQL 격리 통합 테스트와 E2E 결과
