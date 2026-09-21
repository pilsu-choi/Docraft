# Docraft wiki 변경 이력

## 2026-09-22 (4)
* **Update**: VL 행 매칭이 실패하거나 배열 합의 행 밖에서만 값을 찾은 leaf를 블록의 OCR 줄 텍스트로 직접 근거를 잡게 하고(`_line_leaf`, band 안일 때만), `_rank`에 4자 이상·비숫자 needle의 한 글자 오차 유사도 매칭(SequenceMatcher ≥0.85)을 더했다. `backend/engine.py` 순증 23줄. 실제 영수증 2건 재검증: leaf 14개가 바뀌었고 전부 개선(`/items/0/item_name` 0.0→1.0 등), 기존에 맞던 leaf는 회귀 0건. [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)의 "줄 텍스트 근거 인정과 유사도 매칭"·"남은 한계"에 기록했다(77 passed, 환경 종속 실패 1건 별개).

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
