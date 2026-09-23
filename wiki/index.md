---
okf_version: "0.2"
---

# Docraft wiki

작업 기록은 Open Knowledge Format v0.2(`type` 등 YAML frontmatter + markdown 본문)을 따르며, 파일명은 `YYYY-MM-DD-<주제>.md`다. 변경 이력은 [log.md](log.md)에 남긴다.


# 계획과 구현 기록

* [0922 테스트 산출물 59건 AWS 교차검증 재테스트](2026-09-23-verify-test-0922.md) - AO 대비 변경 797곳을 원본 이미지로 감사: 영수증 교정 163 맞음/15 악화, 세부내역서는 집계 행 삭제 등으로 84 맞음/303 악화, `/api/verify` 이벤트 루프 차단 버그 수정, 후속 과제 5개
* [합계식 Judge 판정 보조와 선별급여 라벨 통일](2026-09-23-sum-guard-labels.md) - Judge 판정이 합계식을 더 어기면 불일치가 줄어드는 AO·Docraft 값으로 되돌리는 `verify._balance`(`rules.sum_errors`)와 한방 흐린 팩스 문서 결과, 정답셋 선별급여 행 이름 7건 conform과 76건 새 기준점
* [진료비영수증 이슈 정리 260923 룰 해결](2026-09-23-receipt-issues-0923.md) - 열 전체가 서식에 없는 열로 간 매핑 오류(파서 머리글 기준 `no_column`, 교정은 `column_shift`로 통합), 선별급여 유의어·한방 항목·한 글자 오독 항목명 교정(`item_name`), 한방 소계 열 오매핑 비우기와 퇴행·라벨 관례 충돌 측정
* [진료비영수증 고객 이슈 3건 룰 해결](2026-09-23-receipt-issue-cases.md) - harness-v2 요구사항의 비급여→급여·파싱 에러·항목명 누락 이슈를 AWS 파서+OpenRouter로 끝까지 돌려 원본과 대조하고, 세로 행 밀림 `row_shift`·`선택진료료 이외` 머리글 오독·파서 행 부족 시 열 되돌림·포괄수가 합계 `row_copy` 헛경고를 보강해 3건 모두 원본과 일치시킨 기록
* [마스터 명칭 유사도 검토 필요 플래그 — 임계값 스윕 결과와 보류 결정](2026-09-23-master-name-mismatch-flag.md) - 코드는 마스터에 있는데 인쇄 명칭이 후보 전부와 크게 다른 행을 `검토 필요`로 표시하는 안을 difflib로, 이어서 harness-v2 BAAI/bge-m3 임베딩 코사인 유사도로 76건 재평가(임계값 0.05~0.95 스윕, 결합 규칙 포함)했으나 최고 정밀도가 병명 40%·EDI 21%로 목표(70%) 미달이라 검사는 추가하지 않고 두 조회 함수(difflib `similarity()`, 임베딩) 모두 제거한 결정 기록
* [KCD·EDI 마스터 원본 소스를 harness DB·docraft DB로 재사용](2026-09-23-master-source-reuse.md) - `data/master`(dockerignore 대상, 로컬 전용) 대신 harness-v2 Postgres 재사용 → docraft DB `master_code` 재사용 → `MASTER_SOURCE_DIR` 원본 신규 적재 순으로 소스를 해석하는 구현: advisory lock으로 감싼 COPY 적재, `python -m backend.master --source` 강제 재적재, compose/helm 배포 배선, 381 passed
* [POST /api/verify에 hint_paths 필드 추가](2026-09-23-verify-hint-paths.md) - harness-v2 룰 엔진이 확정 못한 필드만 골라 Docraft 교차검증·Judge를 돌리는 선택 form 필드 `hint_paths` 구현: 추출 스키마 축소, 힌트 밖 필드는 판정 정보 없이 AO 값 그대로 반환, counts는 판정된 key만 집계
* [Docraft Helm 차트(k8s, GPU 서빙 포함)](2026-09-23-k8s-helm-chart.md) - harness-installer 우산 차트의 서브차트로 쓸 `deploy/k8s/helm/docraft`를 harness-v2 mlife-harness 차트 관례로 구현. backend/worker/frontend, 외부 Postgres·Redis 연결(existingSecret 패턴), PaddleOCR-VL·PP-OCRv5·Qwen3-VL(vLLM) 세 GPU 컴포넌트의 deviceIds 기반 카드 지정과 L40S 2장 배치 기본값, helm lint/template 검증과 정수 quote 버그 수정 기록
* [수술확인서·입퇴원확인서·약제비영수증 유형 추가](2026-09-23-doctypes-3more.md) - 남은 3종 정의(진단서 스키마 재사용, 약제비 15필드, AO 이름 alias), 제목 확인으로 고른 57건 평가셋, VLM 라벨 검수 248건, 검수 후속 룰 보강과 rules 정확도(수술 92.1%, 입퇴원 96.2%, 약제비 94.8%)
* [룰 엔진 엣지케이스 확장](2026-09-23-rules-edge-cases.md) - 열 밀림·통째 맞바꿈·산술·근거·형식·표 구조 엣지케이스 목록과 룰별 캐시 평가 효과(세부내역서 fp 273→43, 영수증 fp 27→11), 헛경고 측정, 버린 룰, main 급여 열 관례 조정
* [라벨 관례 정렬 결과와 추출 모델 비교](2026-09-23-label-alignment-and-model-compare.md) - 확정 관례를 76건 정답셋에 적용한 단계별 수치 변화와 분모 변경 경고, 같은 parse·라벨·코드로 채점한 `qwen3-vl-32b-instruct` vs `qwen3.5-27b`(사고 모드 off) 유형별 비교·뒤진 원인·지연·단가 해석과 권고(결정 보류)
* [rules 후처리 흐름 예시 풀이](2026-09-23-rules-flow-example.md) - 진단서·진료비영수증 예시를 rules.apply·check·correct에 통과시켜 단계별 교정을 보여 주는 설명과 이름 도장 표시(`(인)`) 버그 수정
* [추출 VLM qwen3.5-27b 전환과 AI_REASONING](2026-09-23-vlm-model-qwen35.md) - qwen3.5-27b 전환 배경·OpenRouter 확인(단가·컨텍스트)과, 기본 사고 모드로 인한 추출 호출 10배 지연 실측 및 `AI_REASONING` 설정으로 끄는 구현
* [홀드아웃 40건 라벨 이미지 검수](2026-09-23-label-review.md) - 정확도 평가용 홀드아웃 40건 silver 라벨을 이미지 대조로 교정한 감사 집계, 캐시 재사용 재채점 전후(existing 36건 무변화로 검증), 남은 진짜 오류 요약, 기존 36건과의 관례 불일치 7건 통일 권고안

* [파서 표 복원 보강(기울기 보정·해상도 비례 격자)](2026-09-22-table-restore.md) - 모델과 무관한 파서 구조 지표(`scripts/parse_audit.py`), 기울기·`_runs` 정렬 버그·셀 병합 오판 분류, 38건 구조 지표와 76건 정확도 전후

* [추출 프롬프트에 인쇄 항목명·코드 근거 제약 추가](2026-09-22-extract-grounding.md) - 인쇄되지 않은 표준 항목 행 생성과 표준 명칭 치환을 프롬프트로 억제한 구현, 모델 재실행 변동 폭 측정과 1차 지침 실패·2차 채택 근거

* [key-value 정확도 개선 3건 통합 평가](2026-09-22-kv-accuracy-integration.md) - 행 정렬·보충 오탐 억제·마스터 명칭 교정 세 브랜치 병합과 76건 재평가, 가산성 확인과 남은 오류 원인

* [KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md) - 마스터 조회 CSV 생성과 코드 일치 행의 1글자 명칭 교정, 76건 전후 수치와 임계값 근거

* [라벨 보충(_fill) 오탐 억제](2026-09-22-kv-fill-false-positives.md) - 영역 제약·상호배제·근거 등급으로 rules 보충 오탐을 줄인 구현과 전후 수치

* [표 행을 키 열로 대응하고 세분 항목명을 보존](2026-09-22-kv-row-align.md) - 짝짓기 규칙을 rules.pair_rows 한 곳으로 모으고, 영수증 항목 행을 파서 표 순서·세분 항목명으로 바로잡고 소계 행을 보존한 구현(76건 전후 수치 포함)

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
