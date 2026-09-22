# Docraft wiki 변경 이력

## 2026-09-22 (13)
* **Update**: 사용자 우선 목표인 정확도 96%와 유형별 추가 정답 필요량을 [rule-performance-review](2026-09-22-rule-performance-review.md)에 추가했다. 목표 단계·집계 단위는 미확정이며 속도 최적화는 후순위다.
* **Creation**: [rule-performance-review](2026-09-22-rule-performance-review.md)에 코드·저장 평가 기반 개선 우선순위를 기록했다(구현·신규 성능 측정 없음).
* **Update**: [index](index.md)에 분석 문서를 연결했다.

## 2026-09-22 (12)
* **Creation**: [readme-architecture](2026-09-22-readme-architecture.md)에 README 현행화와 Mermaid 아키텍처·처리 흐름 시각화 기록을 추가했다.
* **Update**: [README](../README.md)의 일반 추출·AO 검증, 스키마 출처, 실행·설정·검증 안내를 현재 코드와 대조해 갱신했다. [index](index.md)에 새 문서를 연결했다.

## 2026-09-22 (11)
* **Creation**: verify가 모델 추출 1차·룰 후처리 구조라 지연 시간 목표와 맞지 않는다는 논의를 정리해, 룰 1차 추출 + AO 비교 + Judge 1회로 전환하는 후속 작업 지시서를 [verify-rule-first-plan](2026-09-22-verify-rule-first-plan.md)에 남겼다(현재 단계별 실측 시간, 룰 자산, 평가 기준선, 예상 부작용과 대응, 세부 작업 A~D, 완료 기준).

## 2026-09-22 (10)
* **Creation**: 계획 문서의 미결 3건(정답셋·범위 4종·이미지 1장)을 확정하고 `POST /api/verify`를 구현한 기록을 [ocr-verify](2026-09-22-ocr-verify.md)에 남겼다. `backend/doctypes.py`(유형별 필드 정의)·`backend/rules.py`(twin reader 이식 룰 + 진료비영수증 항목내역 검사·교정)·`backend/verify.py`(평탄화·Judge·파이프라인)를 추가하고, AO 응답의 key·value 누락과 UI 응답 형식을 수용하며, harness-v2 오류 케이스 3건(비급여→급여 오추출·셀 병합·항목명 누락)을 실측했다. 룰 확장으로 36건 rules 단계 정확도가 raw 88.4%→92.9%, gold final은 진단서 100·소견서 90·진료비영수증 98·세부내역서 98.8%가 됐다(245 passed).
* **Update**: [ocr-verify-plan](2026-09-22-ocr-verify-plan.md)의 미결 사항에 결정 내용을 적고 완료 기준을 갱신했다.

## 2026-09-22 (9)
* **Creation**: `feedback.md` TODO의 harness-v2 통합 메모(AO 결과와 Docraft 결과 LLM 비교·선정, twin reader 룰 이식·확장, 자동 교정 JSON API)를 참고 경로·세부 작업·완료 기준·미결 사항을 갖춘 작업 지시서로 정리해 [ocr-verify-plan](2026-09-22-ocr-verify-plan.md)에 기록했다.

## 2026-09-22 (8)
* **Creation**: 요청 대기(`loading`)나 백그라운드 문서 처리(`polling`) 중 상단바에 로딩바와 진행 문구를 보여주는 기능을 [loading-bar](2026-09-22-loading-bar.md)에 기록했다.

## 2026-09-22 (7)
* **Creation**: 추출(`extract`)과 AI 스키마 생성(`generate_schema_from_documents`) 요청에 문서 페이지 이미지를 함께 보내도록 바꾼 작업을 [vision-extract](2026-09-22-vision-extract.md)에 기록했다. `_page_images`/`_data_url`/`_user`를 두 경로가 공유하고, 페이지 단위 청크는 그 청크의 페이지 이미지만 붙이며, 새 설정 `AI_VISION=false`로 기존 텍스트 전용 동작으로 되돌릴 수 있다. 실제 영수증 재검증에서 텍스트 전용이 지어내던 열별 합계(7381/17221)와 빈칸의 47300이 정확한 7300/17300/40000·null로 바뀌었고, 스키마 생성도 열을 불리언 플래그로 바꾸지 않고 열별 숫자 필드로 설계했다(85 passed).

## 2026-09-22 (6)
* **Update**: VL 행 매칭이 실패하거나 배열 합의 행 밖에서만 값을 찾은 leaf를 블록의 OCR 줄 텍스트로 직접 근거를 잡게 하고(`_line_leaf`, band 안일 때만), `_rank`에 4자 이상·비숫자 needle의 한 글자 오차 유사도 매칭(SequenceMatcher ≥0.85)을 더했다. `backend/engine.py` 순증 23줄. 실제 영수증 2건 재검증: leaf 14개가 바뀌었고 전부 개선(`/items/0/item_name` 0.0→1.0 등), 기존에 맞던 leaf는 회귀 0건. [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)의 "줄 텍스트 근거 인정과 유사도 매칭"·"남은 한계"에 기록했다(77 passed, 환경 종속 실패 1건 별개).

## 2026-09-22 (5)
* **Creation**: 새 프로젝트 생성·다른 프로젝트 이동 시 이전 프로젝트의 탭(스키마 설계)과 스키마 편집 내용이 남아 보이던 버그를 `projectId` 변경 시 프로젝트 단위 상태 초기화로 고친 작업을 [project-state-reset](2026-09-22-project-state-reset.md)에 기록했다.

## 2026-09-22 (4)
* **Creation**: 스키마 편집 화면에서 편집 중인 JSON Schema를 title과 함께 내려받는 `JSON Schema 내보내기`를 [schema-export](2026-09-22-schema-export.md)에 기록했다.

## 2026-09-22 (3)
* **Creation**: PaddleOCR-VL은 구조·내용만 담당하고 좌표는 별도 PP-OCRv5 일반 OCR 파이프라인(`PADDLEOCR_LINES_URL`, compose 서비스 `paddleocr-lines-api`)이 준 줄 단위 상자를 쓰도록 바꾼 작업을 [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)에 기록했다. 파서가 각 줄을 중심점이 들어가는 가장 작은 블록에 `block["lines"]`로 붙이고, `backend/engine.py`의 행 bbox 균등 분할 추정(`_row_bbox`)을 삭제했으며 불리언 leaf는 grounding 트리에서 제외했다. 실제 영수증 2건으로 재검증해 균등 분할이 3~5행씩 밀리던 자리가 모두 맞았다(71 passed).
* **Update**: [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)의 "행 bbox 추정" 절과 "남은 한계"의 균등 분할 추정 한계를 폐기됨으로 표시하고 [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)으로 연결했다.

## 2026-09-22 (2)
* **Creation**: 긴 문서를 페이지 경계로 나눠 여러 번 호출하고 스키마에 따라 병합하는 구현을 [extract-page-chunking](2026-09-22-extract-page-chunking.md)에 기록했다(61 passed).
* **Update**: [refs-improvement-review](2026-09-21-refs-improvement-review.md)의 #1 완료 메모에 블록 id grounding이 서버 측 행 grounding으로 교체됐고 이번 브랜치에서 페이지 단위 분할 추출까지 끝났음을 반영했다.

## 2026-09-22
* **Update**: [refs-improvement-review](2026-09-21-refs-improvement-review.md)에 #1(추출 grounding) main 병합 완료를 반영했다.
* **Creation**: refs 기반 개선 1~3단계 구현을 [refs-improvements](2026-09-22-refs-improvements.md)에 기록했다.
* **Update**: [refs-improvement-review](2026-09-21-refs-improvement-review.md)에 항목별 구현 상태를 추가했다.

## 2026-09-21
* **Creation**: AGENTS.md 작업 규칙 보강을 [agents-md-rules](2026-09-21-agents-md-rules.md)에 기록했다.
* **Creation**: 분석 결과 표 미리보기와 JSON 색상을 [table-preview](2026-09-21-table-preview.md)에 기록했다.
* **Creation**: refs 3사 화면과 현재 코드를 비교한 개선·기능 후보를 [refs-improvement-review](2026-09-21-refs-improvement-review.md)에 기록했다.
* **Creation**: feedback.md의 Markdown·HTML 뷰어 항목 구현을 [markdown-html-viewer](2026-09-21-markdown-html-viewer.md)에 기록했다.
* **Update**: 모든 wiki 문서에 날짜 prefix(`2026-09-21-`)를 붙이고 Open Knowledge Format v0.2 frontmatter를 추가했다. [index.md](index.md)를 만들었고, SQLite 시기 기록인 [backend-implementation](2026-09-21-backend-implementation.md)은 `deprecated`로 표시했다.
* **Creation**: 백엔드 로깅과 Docker 전체 스택 구성을 [logging-docker](2026-09-21-logging-docker.md)에 기록했다.
* **Creation**: 추출 JSON 파싱 실패의 원인 분석을 [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)에 기록했다.
* **Update**: [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응" 절을 실제 적용된 내용(블록 id grounding, 블록 단위 입력 자르기, strict 스키마 정규화, optional null 제거)으로 갱신했다.
* **Creation**: extract() grounding을 블록 id 참조로 바꾸고 strict 스키마 정규화가 만드는 optional null을 결과에서 제거한 작업을 [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)에 기록했다.
* **Update**: 사고 문서로 재현 테스트를 진행해 strict `json_schema`가 Alibaba provider에서 응답을 망가뜨리는 실제 원인임을 확인했다. [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)에 재현 실험 표와 최종 대응(철회 이력 포함)을 갱신하고, [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)를 `extract()`의 `response_format: json_object` 전환·`_strict_schema`/`require_parameters` 삭제에 맞춰 다시 썼다. `backend/engine.py`와 `tests/test_ai.py`, `tests/test_ai_provider.py`도 같이 바꿨다(33 passed).
* **Update**: `extract()`를 결과만 요청하는 계약으로 바꾸고 grounding을 서버가 원문 블록에서 값을 찾아 계산하도록 전환했다(같은 문서 재현 테스트 150~200초 → 61초, leaf 199개 전부 bbox 채워짐, 이슈 0건). [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)를 최종 구현에 맞춰 다시 쓰고 블록 id grounding은 중간 단계 이력으로 정리했으며, [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응" 절을 갱신했다(34 passed).

## 2026-09-22
* **Update**: grounding을 블록 단위에서 **행 단위**로 올렸다. table HTML을 `<tr>`/`<td>`로 읽어 값이 든 행을 찾고 블록 bbox를 행 수로 균등 분할해 근거 상자를 만들며, 셀 전체 일치 우선으로 짧은 값 오탐을 없애고, 배열 항목의 합의 행 밖에서만 발견된 값은 `confidence: 0.5`로 낮춘다. 실제 문서에서 leaf 199개 전부 1.0·16행이 서로 다른 `<tr>`에 매핑됐고, 다른 행 값을 주입하면 해당 leaf만 0.5로 잡힌다. [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)에 "행 인식 grounding" 절을 추가하고 [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응"과 README를 갱신했다(38 passed).
* **Creation**: 추출 지침과 필드 구조를 모달에서 크게 편집하고 전체 화면으로 확대·축소하는 기능을 [zoom-modal](2026-09-22-zoom-modal.md)에 기록했다.
* **Creation**: 파싱·추출을 교체 가능한 작업 큐(`QUEUE_BACKEND=inline|celery`)와 worker로 실행하도록 바꾼 작업을 [job-queue](2026-09-22-job-queue.md)에 기록했다(61 passed, redis+celery 스모크 통과).
* **Creation**: worker 중단·inline 재시작 시 멈춘 작업을 heartbeat lease와 기동 시 `recover()`로 자동 복구하고 Docker로 검증한 작업을 [job-recovery](2026-09-22-job-recovery.md)에 기록했다(68 passed).
* **Update**: [job-queue](2026-09-22-job-queue.md)의 남은 한계에 해결된 항목을 표시했다.
* **Creation**: 같은 값이 여러 셀에 있을 때 필드 라벨 옆 줄을 고르는 grounding, 하이픈 허용, 합계 필드 추출 지시를 [label-grounding](2026-09-22-label-grounding.md)에 기록했다(87 passed, 실제 영수증에서 `47,300` 4개 leaf가 각자의 행으로, `공단부담총액` 10717 → 17300).
* **Update**: [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)의 `47,300` 검증 판정이 오판이었음을 표시하고 후속 문서로 연결했다.
* **Creation**: PaddleOCR-VL 표의 병합 셀 정보를 파서가 버려 미리보기·Markdown/HTML·스키마 생성 입력의 표가 어긋나던 문제를 직사각형 격자와 `spans`로 고친 작업을 [table-spans](2026-09-22-table-spans.md)에 기록했다(88 passed, 샘플 5종 7개 표의 행 폭 일치).
* **Creation**: 표 인식 모델 비교(PaddleOCR-VL·PP-StructureV3·Qwen3-VL 32B/8B)와 VL 격자를 유지한 채 VLM으로 셀 텍스트만 교정하는 `TABLE_REFINE`을 [table-refine](2026-09-22-table-refine.md)에 기록했다(90 passed, 진료비영수증 30개 셀 교정).
* **Update**: [table-spans](2026-09-22-table-spans.md)에 PaddleOCR 경로에서 `spans`가 빠지던 버그와 수정 위치를 덧붙였다.
* **Creation**: 외부 파서 결과(`parse_202501020959270c.json`)가 격자 우선 방식임을 분석하고, PaddleOCR-VL 표 HTML 대신 괘선 격자로 행·열·병합 셀을 복원하는 `backend/table_grid.py`를 도입한 작업을 [ruled-table-grid](2026-09-22-ruled-table-grid.md)에 기록했다(93 passed, 진료비영수증 42×15 격자가 원본 양식과 일치).
* **Update**: [table-spans](2026-09-22-table-spans.md)의 "남은 모델 인식 오류"에 괘선 격자 후속 문서 링크를 추가했다.
* **Creation**: harness-v2 방식을 따라 같은 EC2에 Docraft 스택을 올리는 `deploy/aws/` 스크립트와 서버 조사 결과를 [aws-deploy](2026-09-22-aws-deploy.md)에 기록했다(compose 병합 확인, 실제 배포 전).
* **Update**: AWS smoke에서 약제비영수증 표가 2×2 격자로 뭉개져 VLM 결과를 덮어쓴 것을 발견했다. 격자 행 수가 VLM 행 수의 절반 미만이면 VLM 구조를 유지하도록 [ruled-table-grid](2026-09-22-ruled-table-grid.md)에 반영했다(94 passed).
* **Update**: [aws-deploy](2026-09-22-aws-deploy.md)에 실제 배포 결과를 추가했다(6개 컨테이너 healthy, harness 영향 없음, GPU 9.7/23GB, smoke 5종 parsed, 약제비영수증 과소 분할 수정 후 재배포).
* **Update**: [aws-deploy](2026-09-22-aws-deploy.md)에 외부 접근 옵션 `FRONTEND_BIND`(기본 루프백, 0.0.0.0이면 API 키 필수)와 OpenRouter 키 비노출 확인을 추가했다.
* **Update**: [aws-deploy](2026-09-22-aws-deploy.md)에 이슈 수집 스크립트 `collect.sh`와 backend 로그 파일 보존(`/data/logs`, 재배포 시 소실 방지)을 추가했다.
* **Creation**: AWS L4 서버에서 이미지 병렬 처리량(레이아웃 분당 약 12건 포화)과 100건 연속 처리(100/100 성공, 분당 10.6건)를 측정하고, UI 업로드 413과 프로젝트 삭제 시 원본 파일 잔존을 고친 작업을 [aws-throughput](2026-09-22-aws-throughput.md)에 기록했다(94 passed).
* **Creation**: VLM(claude-sonnet-4.5)으로 문서 유형 4종 정답셋(gold 4+silver 32, 36개)을 라벨링하는 `scripts/verify_label.py`와 raw/rules/ao/final 4단계 필드 정확도를 계산하는 `scripts/verify_eval.py`를 구현하고 실제로 돌린 결과를 [ocr-verify-labels](2026-09-22-ocr-verify-labels.md)에 기록했다(라벨 36개 ok=35·skip=1·error=0, gold 4건 전 단계 및 전체 36건 raw·rules 실행 완료).
* **Update**: 라벨 36건(gold 4+silver 32)을 전부 이미지와 대조해 검수하고 `scripts/verify_eval.py`를 보정했다. 표를 행 식별자(`항목`+`EDI코드`, `병명코드`·`수술일자`·`검사일`·`치료일`)로 먼저 짝짓고 남은 행만 순서로 잇도록 바꿨으며, 정오·오탐 판정을 `rules.same` 하나로 일원화하고 `실패 상위 20 필드` 표와 단계·이미지가 붙은 오답 목록을 추가했다. 재평가에서 raw는 진단서 79.6→82.0%·소견서 60.3→82.8%·진료비영수증 69.2→85.6%·세부내역서 80.8→94.5%로 올랐고, gold `final`은 100/90/100/98.6%, 진료비영수증 ao 오탐은 170건→12건이 됐다. [ocr-verify-labels](2026-09-22-ocr-verify-labels.md)에 검수 관례·파일별 수정량·새 평가표를 기록했다.
