---
okf_version: "0.2"
---

# Docraft wiki

작업 기록은 Open Knowledge Format v0.2(`type` 등 YAML frontmatter + markdown 본문)을 따르며, 파일명은 `YYYY-MM-DD-<주제>.md`다. 변경 이력은 [log.md](log.md)에 남긴다.


# 계획과 구현 기록

* [라벨 보충(_fill) 오탐 억제](2026-09-22-kv-fill-false-positives.md) - 영역 제약·상호배제·근거 등급으로 rules 보충 오탐을 줄인 구현과 전후 수치
* [key-value 추출 정확도 개선 지점 검토](2026-09-22-kv-accuracy-review.md) - 76건 rules 단계 오류 분포와 코드 검토를 대조한 정확도 개선 우선순위(구현 없음)

* [정확도 평가 확장과 홀드아웃 라벨 매니페스트](2026-09-22-accuracy-eval-expansion.md) - 기존 36건과 콘텐츠 중복 없는 40건 holdout, 독립 라벨 provenance, strict/legacy 평가 집계

* [룰 검증 성능 개선 우선순위](2026-09-22-rule-performance-review.md) - 표 복원·자동 일치 기준·Judge 범위와 평가 개선 제안

* [README 아키텍처·처리 흐름 시각화](2026-09-22-readme-architecture.md) - 서비스 관계와 일반 추출·AO 검증 흐름을 Mermaid로 정리하고 현행 스키마·설정을 반영

* [verify 룰 1차 추출 전환 계획](2026-09-22-verify-rule-first-plan.md) - 지연 시간 최소화를 위해 모델 추출을 빼고 파싱 블록 룰 추출 + AO 비교 + Judge 1회로 재구성하는 후속 작업 지시서(현황·실측 시간·부작용·단계·완료 기준)
* [Agentic OCR 2.0 결과 교차검증·자동 교정 API 구현](2026-09-22-ocr-verify.md) - POST /api/verify 구현 기록: doctypes·rules(twin reader 이식·확장)·verify(Judge)·AO 키/값 누락 대응·진료비영수증 표 오류 검출·교정과 정답셋 평가 결과
* [Agentic OCR 2.0 결과 교차검증·자동 교정 API 계획](2026-09-22-ocr-verify-plan.md) - Docraft Parse→twin reader 룰→Extract 결과와 AO 응답을 LLM-as-Judge로 비교해 교정 JSON을 돌려주는 API의 작업 지시서
* [AO 교차검증 정답셋(라벨)과 단계별 정확도 평가 스크립트](2026-09-22-ocr-verify-labels.md) - VLM으로 문서 유형 4종 정답셋(gold 4+silver 32)을 라벨링하고 36건을 이미지 대조로 검수한 뒤, 표 행 식별자 정렬·rules.same 일원화로 보정한 raw/rules/ao/final 4단계 정확도 측정 기록
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
* [표 모델 비교와 VLM 셀 텍스트 교정](2026-09-22-table-refine.md) - VL·PP-StructureV3·Qwen3-VL 표 인식 비교와 VL 격자에 VLM 셀 교정을 얹은 TABLE_REFINE
* [표 병합 셀 보존](2026-09-22-table-spans.md) - PaddleOCR-VL 표의 rowspan·colspan을 직사각형 격자와 spans로 보존하고 남은 모델 인식 오류를 정리
* [괘선 격자 기반 표 구조 복원](2026-09-22-ruled-table-grid.md) - 외부 파서 결과를 분석해 격자 우선 방식을 확인하고, VLM 표 HTML 대신 인쇄된 괘선에서 행·열·병합 셀을 복원
* [AWS 개발 서버 배포 스크립트](2026-09-22-aws-deploy.md) - harness-v2와 같은 EC2(NVIDIA L4)에 app + PaddleOCR 스택을 오버레이 방식으로 올리는 deploy/aws 스크립트
* [AWS 이미지 병렬 처리량과 중규모 내구성](2026-09-22-aws-throughput.md) - 서비스별 동시성 한계와 이미지 100건 연속 처리 측정, QUEUE_CONCURRENCY=6 결정, 업로드 413·삭제 파일 잔존 수정
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
