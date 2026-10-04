# Docraft 오류 예방·탐지·보정 메커니즘 목록

대상: `/home/pilsu/projects/mirae-assets/Docraft` `dev` 3c56752 (읽기 전용 조사). 경로는 모두 `backend/` 기준.
읽은 파일: engine, parsers, table_grid, table_layout(+table_layouts.yaml), rules(+rules.yaml), typed_evidence, inference, verify, reprocess, master, doctypes, config, latency, jobs, main(추출 파이프라인·승인 부분). 프롬프트는 별도 파일이 없고 전부 코드 상수다(engine.py, verify.py, doctypes.py, table_layouts.yaml).

범례
- 종류: 예방(프롬프트·전처리) / 탐지 / 보정 / 보류(표시)
- 일반성: 하(드코딩, 대상 병기) / 파(라미터화: yaml·설정 표, 대상 병기) / 완(전 일반)
- 단위: 문자·값·필드·행·열·표(표/그룹)·쪽(페이지)·문서·묶음
- 연산: 누락·변경(오독)·정규화·추가(근거 없는)·중복·위치(행/열/필드 오배정)·경계(합침/분리)·순서·관계(머리글/병합/라벨-값/문맥상속)·상태(선택표시·확실성·버전·판독불가)·계약(스키마·값제약·근거·완결성)

경로 구분: R = `/api/read`(Docraft 단독 읽기: parse → extract → rules.apply → reprocess), V = `/api/verify`(AO 결과와 교차검증, rules.run·Judge 추가), J = 문서 작업 큐(`main.run_parse`/`run_extract`: parse → engine.extract → reprocess.run → validate).
중요한 비대칭: R·J 경로에서 `rules.apply`는 R만 거친다. J(`run_extract`)는 `rules.apply`·`verify`를 거치지 않는다(engine.extract + reprocess.run + engine.validate/assess만). 유형별 후처리 룰(N·F절)은 R·V 전용이다.

---

## A. 입력 전처리·Parse

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| A1 pdf-text-layer-first | parsers.py:parse_pdf | 예방 | PDF 텍스트 층이 있으면 OCR 없이 줄 단위 블록(bbox·page_size) 사용 | 완 | 쪽 | 변경(OCR 오독 회피) | 텍스트 층이 틀렸거나 숨은 텍스트면 그대로 신뢰, 표 구조 없음 |
| A2 scan-needs-ocr | parse_pdf/parse_image | 탐지 | 텍스트 층 없는데 OCR 미설정 → ParseError(실패) | 완 | 문서 | 계약 | 없음 |
| A3 page-range-select | parsers.py:_pages_from_range/_page_pdf | 예방 | 선택 쪽만 하위 PDF로 OCR, 범위 밖 쪽 버림, 빈 범위는 오류 | 완 | 쪽 | 계약·경계 | 쪽 번호를 `page_map`으로 되돌림(잘못 매핑되면 쪽 오배정) |
| A4 exif-normalize | parse_image | 예방 | EXIF 방향 적용·RGB PNG로 재저장 후 OCR와 표 좌표가 같은 픽셀을 보게 함 | 완 | 쪽 | 위치(좌표)·변환 | 디코딩 실패(이름과 형식 불일치) 시 원본을 그대로 OCR에 보냄 |
| A5 expected-pages | parsers.py:_remote_paddle | 탐지 | OCR 응답 쪽 수 ≠ 요청 쪽 수 → ParseError | 완 | 쪽·문서 | 누락·계약 | 실패로 끝남(재시도 없음) |
| A6 empty-ocr | _remote_paddle | 탐지/예방 | 영역 없음이면 markdown 텍스트로 대체, 둘 다 없으면 ParseError | 완 | 쪽·문서 | 누락 | bbox 없는 블록은 이후 근거(bbox) 불가 |
| A7 ocr-lines-attach | parsers.py:_attach_lines | 예방 | PP-OCRv5 줄 상자를 중심점이 든 가장 작은 블록에 붙임. 실패해도 계속 | 완 | 문자(줄)·값 | 위치(근거 좌표), 경계 | 블록 밖 줄은 버려짐, 실패 시 근거가 블록 상자로 거칠어짐 |
| A8 orientation-detect | parsers.py:orientation | 탐지 | 줄 상자 안의 마침표·쉼표 위치(밑줄)로 0/90/180/270 투표. 득표 ≥4이고 나머지의 3배 이상일 때만 회전 | 완(글자 종류 무관, 마침표·쉼표가 있어야 함) | 쪽 | 상태(방향) | 마침표가 거의 없는 쪽은 판정 불가로 그대로 둠 |
| A9 upright-reread | parsers.py:_upright/unturn | 보정 | 돌아간 쪽을 바로 세워 OCR 재호출, 좌표를 원본 프레임으로 되돌려(`unturn`) `orientation` 기록. 재읽기 실패면 첫 읽기 유지 | 완 | 쪽 | 변경·위치·변환 | 재 OCR 1회 추가, 오판 시 정상 쪽을 돌려 읽음. 기울기(deskew)는 회전 아님(아래 A13) |
| A10 upright-for-vlm | engine.py:_data_url/_turns/_page_images | 예방 | VLM에 줄 쪽 이미지를 `orientation`만큼 돌려 바로 세움 | 완 | 쪽 | 상태(방향)·변경 | 없음 |
| A11 resize-limit | engine.py:_data_url, VISION_MAX_EDGE=2000, max_zoom 2 | 예방 | 긴 변 2000px, 확대 2배 한계, JPEG q90 | 완 | 쪽 | 변경(해상도) | 큰 쪽의 작은 글자는 해상도 손실(타일 분할 없음, 아래 갭) |
| A12 image-count-cap | engine.py:_page_images, VISION_MAX_IMAGES=4 | 예방 | 한 호출에 쪽 이미지 4장 초과 시 앞 4장만 첨부(경고 로그만) | 완 | 쪽 | 누락(5쪽 이후 이미지 없음) | 조용한 잘림: OCR 텍스트만으로 읽음 |
| A13 ruled-table-rebuild | parsers.py:_ruled_tables + table_grid.py:ruled_table | 보정 | VLM이 만든 표 HTML 대신 그림의 가로·세로 괘선으로 격자를 재구성하고 OCR 줄로 채움. 격자 행수×2 < VLM 행수면 VLM 구조 유지 | 완(괘선 있는 표만) | 표·행·열 | 경계(병합 칸)·위치(행/열)·관계 | 흐린 괘선이면 행이 뭉침(위 행수 가드로 일부 방어), 괘선 없는 표는 해당 없음 |
| A14 grid-deskew-binarize | table_grid.py:_skew/_straighten/_dark | 예방 | 기울기 ±3도 탐색해 표 크롭과 OCR 상자를 함께 회전, 국소 평균 이진화 | 완 | 표·열·행 | 위치 | 기울기 0.1도 미만은 안 돌림 |
| A15 grid-merge-rules | table_grid.py:ruled_table(`FIRM`,`COVER`,`_split`,`kept`) | 보정 | 다수 행에서 괘선이 있는 경계는 약한 행에서도 실제 열로 보고, 글자가 괘선을 가로지르면 합침, 단어 틈에서 상자 분리, 빈 이미지 칸 표시 | 완 | 열·표 | 경계(합침/분리)·위치 | 임계값(`FIRM`=0.5 등) 의존 |
| A16 table-cell-refine | engine.py:refine_tables/_edit/_row_parts (기본 `TABLE_REFINE=false`) | 보정(기본 꺼짐) | VLM이 셀 번호별 교정만 반환(표 구조 불변). 교정은 비우기·발명 금지(`_edit`: 길이 ≤3이 아니면 유사도 ≥0.5) | 완 | 문자·값(셀) | 변경(오독) | 켜면 표당 호출 추가, 이미지 `<img>` 셀 제외, 실패 시 OCR 텍스트 유지 |
| A17 non-image-formats | parsers.py:parse_docx/xlsx/csv/html,`_grid` | 예방 | 병합 칸 텍스트를 덮는 모든 위치에 채움, 빈 행 제거, csv utf-8-sig, 스크립트·스타일 제외 | 완 | 표·행 | 경계·관계(병합) | `errors=replace`로 깨진 글자가 `?`로 남음 |
| A18 upload-guards | main.py:save_upload/process_image/frames | 예방/탐지 | 확장자(415)·크기(413)·**다중 프레임 TIF는 422 거부**(분리·병합 처리 없음) | 완 | 문서·쪽 | 계약·경계 | 다중 쪽 문서는 이 API에서 아예 못 읽음 |
| A19 shared-parse | parsers.py:parse → latency.shared | 예방(운영) | 같은 파일·설정의 동시 요청은 OCR 1회로 공유 | 완 | 문서 | (운영 일관성) | 캐시 TTL 180초 동안 설정이 같으면 같은 결과 재사용 |

## B. 청크·쪽 이어 붙이기

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| B1 page-chunk | engine.py:_page_chunks(budget 40000자) | 예방 | 쪽 경계를 지키며 청크로 묶고, 한 쪽이 넘으면 블록 경계에서 분할 | 완 | 쪽 | 경계 | 단일 블록이 예산 초과면 `_chunk_text`가 **조용히 잘라냄**(경고) |
| B2 chunk-merge | engine.py:_merge_chunk_results | 보정 | 객체는 키별, 배열은 청크 순서대로 이어 붙이되 **경계의 완전히 같은 연속 항목 1개** 제거, 스칼라는 첫 비null | 완 | 행·필드 | 중복(경계 1건), 경계, 순서 | 청크 간 스칼라 충돌은 첫 값 승리, 실제 반복 행이 경계에서 삭제될 수 있음 |
| B3 table-page-groups | engine.py:_table_pages/read_pages/`TABLE_PAGE_CONCURRENCY` | 예방/보정 | 답 상한(`_reply_cap`)·텍스트·이미지 4장 한도 안에서 연속 쪽 묶음별로 표를 병렬 읽고 쪽 순서로 이음 | 완 | 표·쪽·행 | 경계·순서·누락(출력 한도 초과 방지) | 쪽 묶음 사이에 같은 행이 겹치면 중복 제거는 B2뿐 |
| B4 continuation-plan | engine.py:_table_plan | 보정 | 쪽마다 열 배치를 정해 **가장 많은 쪽이 동의하는 배치**를 모든 쪽에 사용(머리글 없는 이어지는 쪽 대응) | 완(배치 규칙 자체는 C절 대상 한정) | 표·열·쪽 | 관계(머리글 상속)·위치 | 쪽마다 서식이 다른 표에는 맞지 않음 |
| B5 PAGES_NOTE | engine.py:464-465 | 예방(프롬프트) | "이 쪽들만 읽고, 이어지는 쪽은 머리글이 없을 수 있으니 위 필드 순서를 따르라" | 완 | 표·쪽 | 관계·경계 | 없음 |
| B6 completeness | engine.py:extract(coverage/report), main.py:completeness_issues | 탐지 | 실패한 쪽 묶음 기록 → `partial_extraction` 이슈가 승인을 막음. 한 묶음 실패는 그 쪽만 asis 재읽기, 전부 실패면 예외 | 완 | 쪽·표 | 누락·계약 | 부분 결과를 계속 노출(검토용) |

## C. 표 읽기 방식 (rowmajor)

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| C1 rowmajor-positional | engine.py:_read_rows, config `TABLE_EXTRACT=rowmajor`(기본) | 예방 | 모델이 행마다 **값 배열**만 쓰고 i번째 값이 i번째 열(열 이름을 쓰지 않음) → 키 이름 오배정을 구조적으로 차단 | 완(배열 필드면 어떤 스키마든) | 열·행 | 위치(열 오배정) | 단일 청크+쪽 이미지가 있어야 동작, 아니면 asis로 읽음 |
| C2 rowmajor-decoder-contract | engine.py:_read_rows(`json_schema` minItems=maxItems=열 수) + 길이 검증 | 예방+탐지 | 서버 제약 디코딩으로 행 길이 고정, 응답 행이 없거나 길이 다르면 RuntimeError | 완 | 행·열 | 계약 | 실패는 C5로 넘어감 |
| C3 reply-cap | engine.py:_reply_cap, TABLE_REPLY_TOKENS | 예방+탐지 | 금액꼴 숫자 수로 정한 출력 토큰 상한. 반복·루프하면 `finish_reason=length` → RuntimeError → asis | 완(금액이 있는 표 가정) | 행 | 중복(무한 반복), 누락(잘림) | 금액 없는 표는 상한이 작게 잡혀 정상 응답이 잘릴 수 있음 |
| C4 column-plan | table_layout.py:plan/planned, table_layouts.yaml `tables` | 예방 | 문서의 인쇄 열을 OCR로 판별해 합집합 열 중 **인쇄된 열만, 인쇄 순서로** 모델에 줌. 못 정하면 None(합집합 순서) | 하(진료비영수증·세부내역서의 항목내역만) | 열·표 | 위치·누락(인쇄 안 된 열 제외) | 판별 오류 시 열 하나가 이웃 값을 가로챔 |
| C5 plan-layout | table_layout.py:receipt_form + yaml `layout.forms` 1~5 | 예방 | 표 셀 낱말로 진료비영수증 양식 1~5 판별 → 그 양식의 열·열 설명·미인쇄 열 값("0") | 하(진료비영수증 양식 5종) | 열 | 위치·관계 | 양식 3/4 구분 불가면 None(`unknown_form`) |
| C6 plan-header | table_layout.py:_header/_concepts/_segment/_words/_spans/printed_columns, yaml `header.*` | 예방 | 머리글 낱말(편집거리 ≤1, 끝말, 붙어 쓴 머리글 분해, 한 칸 두 값 `spans`, 짝 열 `pairs`, 선택열 `optional`)을 x 좌표순으로 열로 정함. 읽지 못한 머리글 글자·넓은 간격이 있으면 그 자리 열을 유지 | 파(세부내역서 낱말 표, yaml) | 열 | 위치·관계(머리글)·누락 | 오독 허용 폭(거리 1)으로 오분류 가능, 낱말 표 갱신 필요 |
| C7 plan-value-shape | table_layout.py:shaped_columns/_column_shapes/_shape | 예방 | 머리글을 못 읽으면 셀 값 꼴(날짜·코드·글자·금액·수)의 순서로 열 결정 | 하(세부내역서 열 이름 규칙) | 열 | 위치 | 값 꼴이 비슷한 열끼리 혼동 |
| C8 plan-note | table_layouts.yaml `header.note` | 예방(프롬프트) | "열 순서는 문서 머리글 순서, 값은 머리글 열 아래 칸 그대로, 빈 칸은 null, 옆 칸으로 옮기지 말라" | 파 | 열·값 | 위치 | 없음 |
| C9 rowmajor-fallback | engine.py:read_group/read(`except RuntimeError, ValueError`) | 보정 | rowmajor 응답 계약 위반 시 해당 표(또는 쪽 묶음)를 asis(객체 JSON)로 다시 읽음. `rowmajor_fallback` 기록 | 완 | 표·쪽 | 위치·누락 | 호출 1회 추가, asis는 열 오배정에 취약 |
| C10 table-recheck-gate | rules.py:table_misses → verify.py:read, `TABLE_RECHECK_RATIO=0.6` | 탐지+보정 | 행 산술 실패·금액 전부 빈 행·열 종류 안 맞는 행 비율이 0.6 이상이면 항목내역을 asis로 **다시 읽고 그 결과 채택** | 하(세부내역서 항목내역, 산술 규칙을 쓰는 유형만) | 표·행 | 위치(열 통째 밀림)·누락(열 비움) | 두 읽기 중 어느 쪽이 더 나은지 재비교 없이 asis 결과로 교체 |

## D. 프롬프트의 지시·제약 (프롬프트 파일 내용 확인)

| id | 위치 | 종류 | 지시·제약 내용 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| D1 ROWS_SYSTEM | engine.py:435-452 | 예방 | 행마다 배열(열 이름 금지)·자리 고정·빈 칸 null·길이 고정·원문 그대로 복사(필드 설명이 형식을 요구할 때만 예외)·위→아래 순서·마지막 행에서 중단(패딩·발명·반복 금지)·소계/합계/끝수처리금액 행도 데이터 행으로 출력 | 하(마지막 항목에 "소계·합계·계·끝수처리금액" 한국 의료서식 용어) | 행·열·값 | 위치·순서·추가·중복·누락 | 지시만으로는 보장 불가(탐지는 C2·C3·assess) |
| D2 ROWS_USER | engine.py:453-460 | 예방 | OCR 참조 텍스트는 **이미지가 우선**이며 누락·중복 행 점검용, "순서 변경·이름 변경·발명·번역 금지" | 완 | 행·열 | 누락·중복·추가 | OCR 오류를 모델이 따라갈 수 있음 |
| D3 asis 시스템 | engine.py:539-544(`_read_chunk`) | 예방 | "컨텍스트·레이아웃으로 추출, 발명 금지, 없으면 null, **합계 필드는 인쇄된 합계 행/라벨 칸 값(항목 한 줄 값 금지)**, 스키마 필드 순서 유지, 래퍼 키 금지" | 완(합계 문구는 일반 표현) | 필드·값 | 추가·위치·계약 | 없음 |
| D4 TABLE_NOTE | engine.py:32-36 | 예방 | 표 필드가 있으면: "행은 근거, 기억이 아니다. 인쇄된 행만 인쇄 순서대로, 인쇄 안 된 행 추가 금지, 표준명이 아니어도 인쇄된 항목명 유지" | 완 | 행 | 추가·순서·변경(표준명으로 바꿈) | 없음 |
| D5 VISION_NOTE | engine.py:28-31 | 예방 | 이미지에서 표 구조(병합 칸·머리글)를 읽고 OCR 텍스트는 철자 보조로만 | 완 | 표·열·값 | 관계(병합·머리글) | 없음 |
| D6 청크 안내 | engine.py:557-561 | 예방 | "전체 중 n번째 부분, 이 쪽 범위에 없는 필드는 null/빈 값" | 완 | 필드·쪽 | 경계·추가 | 값이 쪽 경계에 걸리면 두 청크 모두 null 가능(B2는 첫 비null) |
| D7 필드 설명·형식 | doctypes.py:_MEDICAL_FIELDS 등, schema() | 예방 | 필드마다 라벨 동의어·형식(YYYYMMDD, 숫자만, 전화·FAX 제외, 한글 이름만)·"인쇄되지 않았으면 null(표 날짜로 채우지 않는다)" 지시 | 하(7개 서식·필드명) | 값·필드 | 정규화·추가·위치 | 설명이 길어지면 모델이 일부 무시 |
| D8 표 힌트 | doctypes.py:24-34, 92, 247(`HINTS`) | 예방 | `TABLE_HINT`(합계·머리글 행 제외), `DETAIL_HINT`(집계 행은 인쇄된 자리에 넣고 라벨은 항목 칸, 미인쇄 칸 계산 금지), `TOTAL_HINT`(합계 라벨이 인쇄된 칸만), `GROUND_HINT`(인쇄된 행만, 표준 목록에서 덧붙이기 금지, 금액 빈 행도 유지, 표준명으로 바꾸지 않기), `RECEIPT_HINT`(최종 합계 행만 '합계') | 하(유형별 문구: 진료비영수증·세부내역서만 GROUND_HINT) | 행·값 | 추가·누락·정규화 | 유형 간 정책 불일치(영수증은 합계 행 포함, 진단서계는 제외) |
| D9 스키마 제약 | doctypes.py:_property/schema | 예방 | 모든 필드 `["string","null"]`, 표는 `required` 전체 열, enum(+null) | 파(유형별 enum) | 값·열 | 계약·정규화 | 값 제약은 문자열 수준(형식은 후처리 정규화) |
| D10 항목명 규칙 | doctypes.py:_RECEIPT_ITEM["항목"] | 예방 | 특수문자 제거·입원료 인실 표기·투약/주사 하위 표기·'합계' 표기 | 하(진료비영수증) | 값 | 정규화 | 인쇄 원문과 달라짐(고객 염려 항목) |
| D11 JUDGE_PROMPT | verify.py:34-60 | 예방 | 필드 정의(`desc`)에 맞는 값만 고르라, `hint`는 참고(이미지 우선), `diff`로 어긋난 셀 먼저 재독, "표는 모든 행을 문서 순서로", AO 표기 유지, 발명 금지 | 하("Korean medical document", 정의는 유형 yaml) | 값·행 | 변경·추가·순서 | 두 읽기 모두 틀리면 코드로 못 막음(F·G 일부만) |
| D12 TABLE_REFINE_PROMPT | engine.py:147-152 | 예방(기본 꺼짐) | "셀 하나는 한 셀로(병합돼 보여도), 틀린 셀만 교정" | 완 | 값(셀) | 변경 | 위 A16 |
| D13 generate_schema 시스템 | engine.py:246-258 | 예방 | 스키마 생성 시 제목·설명 필수, 병합 머리글 반영, 열을 boolean 플래그로 바꾸지 말 것 | 완 | 필드·열 | 계약 | 생성 스키마는 `check_schema`만 통과하면 됨 |
| D14 호출 설정 | engine.py:_provider | 예방 | temperature 0, JSON mode/`json_schema`(vLLM 구조화 출력), reasoning 끔 | 완 | 값 | 계약 | json_schema 미지원 서버는 무시 |

## E. 출력 JSON 파싱·복구·재시도

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| E1 fence-strip | engine.py:_provider(137-138) | 보정 | 응답이 ```json 울타리면 벗김 | 완 | 문서(응답) | 정규화 | 없음 |
| E2 truncation-detect | _provider(129-131) | 탐지 | `finish_reason=length` → RuntimeError(잘린 JSON을 파싱 시도하지 않음) | 완 | 행·표 | 누락 | 실패(복구 없음). rowmajor는 C9로 대체 읽기 |
| E3 json-decode | _provider(139-143) | 탐지 | 파싱 실패 → 로그(꼬리 200자) 후 예외. **JSON 수리(괄호 보정 등)는 없음** | 완 | 문서 | 계약 | asis 비표 부분 실패는 문서 실패 |
| E4 http-retry | _provider(`HTTPTransport(retries=2)`) | 보정 | 연결 오류만 최대 2회 재시도(시한 지정 시 0회). 응답 내용 오류에 대한 **재시도 없음** | 완 | 문서 | (가용성) | 없음 |
| E5 dict-contract | _read_chunk/judge(`not isinstance(dict)`) | 탐지 | 객체가 아니면 RuntimeError | 완 | 문서 | 계약 | 실패 |
| E6 drop-null-optionals | engine.py:_drop_null_optionals | 보정 | 선택 필드에 모델이 채운 null을 스키마 기준으로 제거 | 완 | 필드 | 정규화 | null 허용 필드는 보존 |
| E7 rowmajor-position-map | engine.py:_read_rows(끝) | 보정 | 값 배열을 계획 열 이름에 대응, 계획에 없는 합집합 열은 `fill`(영수증 "0", 그 외 None) | 파(`fill`은 yaml layout) | 열 | 위치·누락 | 인쇄되지 않은 열을 "0"으로 채움(영수증) |
| E8 refine-reply-normalize | engine.py:refine_tables.correct | 보정 | `{"corrections":…}`와 맨 객체 둘 다 수용, 모르는 셀 번호 무시 | 완 | 값(셀) | 계약 | 없음 |
| E9 rule-json-fallbacks | verify.py:_decide, judge | 보정 | 판정이 없으면 AO 값 유지(`unknown`), `source`가 없는 값은 `rules.apply`로 정규화 후 AO/Docraft와 같으면 그쪽 원본 | 완 | 값·행 | 정규화·상태 | 판정 누락 필드는 미확인 상태로 통과 |

## F. 값·스키마 검증 (탐지)

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| F1 json-schema-validate | engine.py:validate | 탐지 | Draft2020-12 위반 + `confidence<0.7`(`low_confidence`) | 완 | 값·행 | 계약·상태 | 없음 |
| F2 assess-quality | engine.py:assess | 탐지/보류 | 값마다 상태(PASS/SUSPICIOUS/UNRESOLVED)·행동(ACCEPT/RECHECK/REVIEW)·이슈 코드(`required`,`minItems/maxItems`,`no_source`,`approximate_source`,`ambiguous_source`,`row_mismatch`,`row_conflict`,`invalid_geometry`,`distant_label`,`missing_value`,`invalid_typed_proof`) | 완(코드 이름은 일반, `missing_value`는 `LABELS` 별칭 사용 안 함) | 값·필드·행 | 계약·상태·위치·추가 | 값은 바꾸지 않음(표시만) |
| F3 grounding-tree | engine.py:ground/_grounding_tree/_hits/_agreed_row/_band/_line_leaf/_leaf | 탐지 | 값을 OCR 표 행·줄에서 찾아 근거(page·bbox·source_text·match: exact/contained/approximate/ambiguous/none, confidence 1.0/0.5/0) 부여. 배열 항목의 값이 합의 행 밖이면 0.5, 줄 상자로 확인되면 복원. `row_mismatch`(괘선 표)/`row_conflict` | 완(별칭은 `rules.LABELS` 참조) | 값·행 | 추가(근거 없음)·위치(행)·상태 | OCR이 이미지 진실이 아님(위치 증명이지 판독 증명 아님, 코드 주석) |
| F4 typed-evidence | typed_evidence.py:scalar/amount_candidates/_table_proofs/_field_blank/blank_candidate/_scalar_total/valid/augment | 탐지(증명) | 날짜 라벨·체크 표시·금액 라벨·표 셀(고유 행·고유 잎 머리글)·**빈 칸(null 증명)** 을 OCR 셀 증거에 묶어 `match=typed/blank` 증명, 결정론적 후보 제안 | 하(날짜·bool 라벨 `_labels`, `납부한금액_` 접두 특수 처리, `_RANGES`, 7개 유형의 `DOC_TYPES`만 augment) | 값·필드 | 상태(선택표시·빈 칸)·추가·계약(근거) | 유일하지 않으면 증명 안 함(보수적) |
| F5 derived-proof | typed_evidence.py:_derived, schema_alias_candidate, inference.py:sum_group/_aligned_amounts | 탐지+보정 | 구성 필드 합이 합계와 맞고 각 항이 증명될 때만 합계 제안, 날짜 별칭(사고발생일자=진료시작일) | 하(`FIELD_SUMS`, `SCHEMA_ALIASES`) | 필드 | 관계(합계식)·추가 | 회전 재읽기(`rotate_*`) 단계에서만 합계 그룹 사용 |
| F6 inferred-checkbox | typed_evidence.py:inferred_checkbox_candidate, doctypes.EXCLUSIVE_CHECKBOX_GROUPS | 보정(제안) | 두 선택지 중 하나만 체크되면 다른 쪽은 N | 하(진단서계 임상적추정/최종진단) | 필드 | 상태(선택표시)·관계 | 둘 다 안 읽히거나 체크가 2개면 안 함 |
| F7 geometry-validate | engine.py:assess(`invalid_geometry`), reprocess._positioned, verify._exposed_grounding | 탐지 | bbox가 page_size 안인지, 숫자·길이, 증명 구조가 유효한지 | 완 | 값 | 계약(근거) | 무효 근거는 응답에서 제외 |
| F8 expose-grounding | verify.py:_read_groundings/_exposed_grounding/_merge_recovered_groundings | 탐지/예방 | 최종 값이 **추출 값에서 후처리로 바뀌지 않은 경우만** 좌표를 유지(`rules._value`와 비교), 행은 정규화된 전체 행 서명이 유일할 때만 대응 | 완 | 값·행 | 위치·계약(근거) | 바뀐 값은 근거 없음으로 비움 |
| F9 approve-gate | main.py:approve/review/run_extract | 탐지 | 검증 이슈(+partial)가 있으면 승인 거부(422), 수정은 `set_pointer`+`mark_corrected`, 상태 `needs_review`/`completed` | 완 | 문서 | 계약·상태 | `low_confidence`는 승인에서 제외 |
| F10 request-validation | verify.py:resolve_doc_type/resolve_keys/resolve_row_filter, main.py read_document | 탐지 | 유형·key·row_filter 검증, 정의 밖 key 무시(경고) | 완 | 문서·표 | 계약 | 정의 밖 key만 있으면 빈 응답 |
| F11 schema-check | main.py:persist_schema, generate | 탐지 | 스키마가 유효 JSON Schema인지(`check_schema`), 생성 실패 502 | 완 | 문서(스키마) | 계약 | 없음 |

## G. 룰 기반 값 정규화·후처리 (`rules.apply`, R·V 경로)

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| G1 normalize-kinds | rules.py:normalize(`_date/_amount/_number/_idnum/_phone/_code/_edi/_bool/_enum_text/_text`) | 보정 | 날짜(O/I/l→0/1, 2자리 연도, 달력 검증, 다양한 구분자)·금액(천 단위, 소수 ≤2, 음수 △)·번호·주민번호(마스크 `*`)·전화(FAX 제거)·KCD 코드(앞 0→D, 1→I)·EDI(O/I/L→숫자, S/B는 마스터 확인 시만) | 파(kind별, 필드 kind는 doctypes) · 한국어 서식 | 문자·값 | 정규화·변경(OCR 혼동)·상태(빈 값) | `_number`는 "2x3"→6 곱셈 처리, 소수 세 자리는 천 단위로 해석 |
| G2 label-junk-filter | rules.py:_junk/_LABEL_WORDS | 보정 | 값 자리에 서식 라벨·표 마크업·선택지가 흘러든 것이면 null(표 칸은 제외) | 파(`LABELS`+doctypes 키+`_FORM_WORDS`) | 값 | 추가(라벨 유입)·위치 | 실제 값이 라벨 낱말로만 구성되면 지움 |
| G3 enum-canon | rules.py:_enum | 보정 | 동의어→정규값, 동률·불일치는 버림(사각형 두 선택지가 동시에 걸리면 None) | 파(ENUMS) | 값 | 정규화·상태(선택표시) | 정규 목록 밖은 null |
| G4 field-rules | rules.py:FIELD_RULES(`_serial/_name/_hospital/_address`, DRG, 병실) | 보정 | 등록번호(한글·날짜 시작이면 버림)·이름(2~5자 한글, 성별·진료과 거름, 중복 반복 제거)·병원명('의과의원'→'외과의원', 끝 '병'→'병원')·주소(전화·날짜 제거)·병실(진료과 이름 버림) | 하(필드명 지정, 한국어 규칙, 병원명 치환 하드코딩) | 값 | 정규화·위치·변경 | '의과의원→외과의원' 같은 치환이 실제 원문을 바꿈 |
| G5 hollow-rows | rules.py:_hollow | 보정 | 값이 없거나 라벨뿐인 행 삭제(진료비영수증 제외) | 하(`doc_type != "진료비영수증"`) | 행 | 추가(흘러든 머리글 행) | 영수증은 라벨꼴 항목명이 흔해 미적용 |
| G6 serial-swap | rules.py:_serials | 보정 | 환자 등록번호 값이 차트번호 칸의 값이면 이동 | 하(`환자 등록번호`·`차트번호`) | 필드 | 위치 | 없음 |
| G7 label-fill | rules.py:_fill/_candidates/_section/`EXCLUSIVE`/`FIELD_SECTION`/`EXPLICIT` | 보정 | 빠진 스칼라를 라벨 동의어(표 셀 오른쪽·`라벨: 값`)로 보충. 환자/기관 영역 밖 후보·같은 무리 다른 필드가 쓰는 값·근거 등급 동률 후보는 불채택 | 파(`LABELS`·`field_section`, 한국어) | 필드 | 누락·위치 | "잘못 채우는 쪽이 비우는 쪽보다 나쁘다"는 보수적 기본값 |
| G8 notes-to-rows | rules.py:_notes/NOTES/MARKS | 보정 | 소견 문장·비고 `날짜 (검사)` 표시로 수술·검사·치료내역 행 생성(앞 표에 담긴 내용 제외) | 하(진단서계 3표) | 행·표 | **추가**(근거 문장에서 만든 행)·누락 | 행이 문서에 표로 인쇄되지 않았어도 생김(AO 관례 맞춤) |
| G9 split-cells | rules.py:_split_cells | 보정 | 병명 칸의 코드→병명코드, 수술명 칸의 날짜→수술일자 | 하(병명내역·수술내역) | 값·열 | 위치·경계 | 없음 |
| G10 receipt-table-reconcile | rules.py:_receipt_table/_receipt_rows/_receipt_column/_receipt_header_column/_receipt_item/_moves/_column_moves/_realign/_insert_at | 보정 | 파서 표 머리글(병합 칸)·항목행을 뼈대로 모델 행을 인쇄 순서에 맞추고 빠진 항목을 채우고 이웃 열로 밀린 금액을 되돌림(여러 행에서 같은 방향이면 합계 행도) | 하(진료비영수증 항목내역) | 행·열·표 | 누락·위치(행·열)·순서·추가(보충 행) | 복원 부실하면 빠진 항목만 보충(예전 방식) |
| G11 unprinted-total-null | rules.py:_ungrounded/_copied + `UNPRINTED_NULL`/`FIELD_SUMS` | 보정 | 합계 행 없이 채워진 급여 합계가 문서 글자에 없거나 한 항목 행을 베낀 것·구성 합과 어긋나면 null | 하(세부내역서 급여 4개 합계) | 필드 | 추가(계산·베낀 값) | 인쇄된 합계도 서식상 다르면 지울 수 있음 |
| G12 totals-fill | rules.py:_totals/total_label/is_total/`_TOTAL_NAMES`/`KEEP_TOTALS` | 보정 | 합계·소계 행 인식(라벨 변형 정규화), 합계 필드 비었으면 합계 행으로 채움·합계 행 근거가 있으면 교체, 소계는 합계 필드 안 채움, 영수증 항목명을 '합계'로 | 하(진료비영수증·세부내역서) | 행·필드 | 관계(합계)·정규화·추가 | 합계 행 라벨이 사전에 없으면 집계 행으로 안 봄 |
| G13 header-driven-blank | rules.py:_header_columns/_headers/_inferred/_has_header/_grouped | 보정 | 머리글 근거로 서식에 없는 금액 열(묶음 제목 급여·비급여, 독립 열 없음) 값 삭제, 코드 열 하나일 때 EDI코드로 모으기, 소계 열 옮김 | 하(두 유형 금액 열, yaml `header_columns`·`grouped`) | 열·행 | 추가(미인쇄 열에 채운 값)·위치 | 머리글을 일부만 읽으면 오삭제 방지 위해 보수적(`≥3열` 조건 등) |
| G14 column-swap-fix | rules.py:_swaps/_swap/_detail_swaps/_printed_under/_column_sums | 보정 | 합계 행에 맞춰 통째로 맞바뀐 금액 열 쌍 교환, 세부내역서 원내코드↔EDI코드·본인↔공단 교환(값 꼴·인쇄 자리·득표 근거). 근거 약하면 표시만 | 하(두 유형) | 열·표 | 위치(열) | 한 열이 두 쌍에 걸리면 안 바꿈 |
| G15 group-date-inherit | rules.py:_group_dates/_title_lines/_row_lines | 보정 | 날짜 열이 없는 표에서 바로 위 무리 날짜 줄을 행의 시작일자로 | 하(세부내역서 시작일자) | 행 | 관계(문맥 상속) | OCR 줄 순서 가정 |
| G16 period-fill | rules.py:_period | 보정 | 날짜 없는 표에 인쇄된 진료기간으로 행 채움, 종료일 미인쇄면 비움, **반대 방향(표 → 진료기간)은 안 함** | 하(세부내역서) | 필드·행 | 관계 | 2026-10-03 정책: 계산·옮김 채움 금지 |
| G17 derive | rules.py:derive/_from_idnum/_earliest | 보정 | 주민번호로 성별·생년월일, 사고발생일자(스키마 정의대로), 영수증 항목명 정규화, 세부내역서 코드 열 | 하(필드 이름) | 필드 | 관계·정규화 | 마스크된 뒷자리면 성별 못 구함 |
| G18 item-name-norm | rules.py:item/_alias/_misread/_one_off/ITEM_ALIASES(shared yaml) | 보정 | 항목명 별칭(입원료 1인실→입원료_1인실), 표준명과 자모 하나 다르면 오독으로 교정 | 파(shared/receipt_items.yaml) | 값 | 정규화·변경(오독) | 짧은 이름은 자모 1개까지만 |
| G19 master-name | rules.py:_master_names → master.py:correct_name | 보정 | **코드가 마스터에 있고 같은 길이에서 1글자만 다른** 명칭만 그 글자 교정 | 하(병명내역·항목내역, `MASTER_NAMES`) | 문자 | 변경(오독) | 마스터 통째 대체 안 함(고객 염려). 코드 오류는 못 잡음 |
| G20 section-carry | rules.py:_section_items/_carry/_title_lines | 보정 | 섹션 제목('01.진찰료')을 항목으로, 무리 첫 행에만 인쇄된 값(항목·시작일·종료일)을 같은 무리 빈 칸에 상속 | 하(세부내역서 항목·날짜 열) | 행 | 관계(문맥 상속) | 매 행 반복 서식은 상속 안 함 |
| G21 row-pairing | rules.py:pair_rows/_prefix_same/_likeness | 보정(비교 인프라) | 행 키 열(`ROW_KEYS`)로 두 표 행 대응 | 파(row_keys yaml) | 행 | 순서·위치 | 키가 같은 중복 행은 나머지 칸 유사도 |
| G22 chunk-edge | engine.py:_normalized/_needles/_rank | 탐지 도우미 | 쉼표·공백·`\n`·`원`·`%`·날짜 구분자·1.0↔1·사업자번호 하이픈 변형을 같게 비교 | 완(일부 한국어) | 문자·값 | 정규화 | 느슨 비교로 근거 오인 가능 |

## H. AO↔Docraft 교차검증 룰·Judge (V 경로, `rules.run`)

`rules.RULES`(rules.py:1788-1812) 24개. 동일 룰이 reprocess에서는 `rules.check(doc_type, values, values, evidence)`(자기 대 자기)로 호출되므로 AO와 비교가 필요한 룰(ROW_MISSING·ROW_EXTRA·COLUMN_SHIFT·ROW_SHIFT·ITEM_NAME 일부)은 R·J 경로에서 사실상 발동하지 않는다.

| id | 위치 | 종류 | 보는 것 → 바꾸는 것(교정=`fix`, 없으면 탐지·Judge로) | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| H1 MASTER.CODE_UNKNOWN | rules.py:_master_checks | 탐지 | KCD 마스터에 없는 병명코드 표시(EDI는 신호가 약해 안 봄, 정밀도 근거 docstring) | 하(병명내역) | 값 | 계약·변경 | 교정 없음 |
| H2 DATE.ORDER | _date_checks | 탐지 | 날짜 앞뒤·발급일 뒤·1900 이전(필드·표 열 쌍) | 파(`date_order`·`issued`·`later_ok`) | 값·행 | 관계·변경 | 교정 없음(Judge 힌트) |
| H3 ID.MISMATCH | _id_checks | 탐지 | 성별·생년월일이 주민번호와 어긋남 | 하(성별·생년월일) | 필드 | 관계 | 없음 |
| H4 SUM.FIELD / SUM.TABLE | _field_sums/_sum_checks/_relations | 탐지+보정(`SUM.FIELD`만 합계 쪽 null) | 합계 필드=구성 필드 합, 영수증 합계 행·열별 합(십의 자리 절사 허용) | 파(`field_sums`·`total_fields`) · 영수증 표는 하 | 필드·표 | 관계(합계)·변경 | 합계 필드를 비우는 방향 |
| H5 DETAIL.ROW_ARITH | _row_arith | 탐지 | 단가×투여량×횟수×일수=총액, 본인+공단(+전액)=총액, 종별 가산 비율 허용 | 하(세부내역서) | 행 | 관계·변경·위치 | 교정 없음 |
| H6 DETAIL.LOW_QUALITY | _low_quality | 탐지(ESCALATE) | 행 금액 25% 초과 불일치+과반 불일치/EDI 과반 마스터 밖이면 표 전체 이미지 재확인 | 하 | 표 | 상태 | 사람 검토로 에스컬레이션 |
| H7 DETAIL.ITEM_CLASS | _class_checks | 보정 | 급여구분이 정규값 아니면 금액 열로 급여/비급여 정하고, 근거 없으면 비움 | 하 | 값 | 정규화·위치 | 둘 다 금액이면 Judge |
| H8 DETAIL.SECTION_ITEM / EMPTY_CELL / WARD | _section_checks/_empty_cells/_ward_checks | 보정 | 섹션 제목을 항목으로, AO가 비운 단가·투여량 칸을 Docraft 값으로, 병실 칸의 진료과 이름 비움 | 하 | 값 | 누락·위치 | 두 읽기가 함께 틀리면 못 잡음 |
| H9 DETAIL.EMPTY_COLUMN | _empty_columns | 탐지 | 머리글에 있는 단가·투여량 열이 전 행 비었음 | 파(`header_columns`) | 열 | 누락 | 재추출 권고 |
| H10 DETAIL.COLUMN_SWAP | _detail_swap_checks | 탐지(ESCALATE) | 근거 약한 열 교환 의심 | 하 | 열 | 위치 | 사람 검토 |
| H11 GROUND.UNPRINTED | _unprinted | 보정(null) | 인쇄되지 않은 합계 | 하 | 필드 | 추가 | G11과 동일 |
| H12 RECEIPT.* (MULTI_AMOUNT·NO_COLUMN·ROW_COPY·ROW_MISSING·ROW_EXTRA·COLUMN_SHIFT·ITEM_NAME·ROW_SHIFT·COLUMN_SWAP) | _multi_amounts/_no_columns/_row_copy/_row_missing/_row_extra/_shift_checks/_item_names/_row_shifts/_swap_checks | 탐지+일부 보정 | 한 칸 금액 둘·없는 열 값·합계 베끼기·행 누락(오독 후보 제외)·행 과잉·열 밀림/교환·항목명·세로 밀림 | 하(진료비영수증 항목내역) | 행·열 | 중복·누락·추가·위치·정규화 | 보정은 `_fix_*`(행 삽입·열 이동·이름 교체) |
| H13 MISSING.REQUIRED | _missing, `required`/`required_items`/`required_items_exempt` | 탐지(ESCALATE) | 필수 필드·표(조건 열)·필수 항목 행(영수증) 누락 | 파(rules.yaml·shared yaml) | 필드·표 | 누락·계약 | 한방 등 예외 정규식 필요 |
| H14 run-loop | rules.py:run/_correct/_where | 보정 | 확실한 이상만 룰 교정을 최대 3회전 반복, 같은 상태 반복 시 중단, 트레이스 기록 | 완 | 문서 | (제어) | 무한 반복 방지 |
| H15 judge | verify.py:judge/_decide/_row_diff | 보정 | 어긋난 값만 이미지 1장과 1회 LLM 호출로 판정, 표는 키 열로 대응해 어긋난 셀·행만 전달 | 하(프롬프트·유형) | 값·행 | 변경·누락·추가 | 판정 응답이 빠지면 AO 유지(`unknown`) |
| H16 judge-guards | verify.py:_agreed/_with_totals/_with_ao_names/_balance | 보정 | Judge가 고친 표에서 두 읽기가 같은 칸은 원값, 집계 행 원위치 복원, 항목명은 AO, 합계식을 더 어기면 AO/Docraft 값으로 되돌림(비우는 방향은 안 함) | 하(합계식·이름 열) | 값·행 | 변경·순서·관계 | 합계식 없는 필드는 미적용 |
| H17 blank-ao | verify.py:run(blank) | 보정 | AO가 전부 비면 Judge 없이 Docraft 값 사용 | 완 | 문서 | 누락 | 재분류 재추출 경로 |
| H18 review-mark | verify.py:mark_review/_annotate/quality 병합 | 보류(표시) | 두 읽기가 다른 칸·남은 CALC/STRUCT 이상 행·열에 `review`/`recheck` 표시, 최종 품질(`field_quality`)에 룰 이슈 합침 | 완 | 값·행·표 | 상태 | 값은 바꾸지 않음 |

## I. 재처리 (`reprocess.run`, R·J 경로, 증거로 승인)

| id | 위치 | 종류 | 보는 것 → 바꾸는 것 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| I1 targets-select | reprocess.py:run/_rule_targets/_positioned/priority | 탐지 | 품질이 PASS/CORRECTED가 아닌 잎을 우선순위(결정론 후보→위치 확인된 근거+룰 관련→…)로 재처리 대상 선정 | 완 | 값·행 | 상태 | 시도·모델 호출 예산(`max_attempts` 4, `max_model_calls` 2, 시한) |
| I2 deterministic-candidates | reprocess.py(deterministic)+typed_evidence | 보정 | 날짜 별칭·체크 N 추론·빈 칸 null 증명이 있으면 증거 첨부 후 채택 | 하(`DOC_TYPES`·스칼라 필드만) | 필드 | 상태·추가·관계 | 증명 안 되면 후보 없음 |
| I3 rules-stage | reprocess.py:stage "rules" | 보정 | `rules.apply`(정규화) 재적용, 변화 없으면 시도 환불 | 완(룰 내용은 G절 한정) | 값 | 정규화 | 없음 |
| I4 rotate-stages | reprocess.py:_vertical_ocr/_rotated(`rotate_ccw/cw`) + inference.sum_group | 보정 | 세로 글줄이 75% 이상인데 방향 정보가 없으면 ±90도로 재 OCR해 **합계 그룹**만 검증 후 채택 | 하(`FIELD_SUMS` 대상 필드, 이미지 파일만(PDF 제외)) | 쪽·필드 | 상태(방향)·관계 | OCR 2회 추가 |
| I5 roi-parse | reprocess.py:_crop/_remap/stage "roi_parse" | 보정 | 값 근처를 크롭(×2)해 OCR 재실행 후 기존 증거와 합쳐 같은 필드 후보 평가 | 완 | 값·행(셀) | 변경 | 좌표 되돌림 오류 가능(unturn/_remap 검증) |
| I6 roi-vlm / wide-vlm | stage "roi_vlm","wide_vlm" | 보정 | 크롭 또는 전체 이미지로 필드 한 개만 VLM 재추출(텍스트 필드는 blind). 긴 텍스트는 `roi`+`wide` 두 읽기가 같아야 채택 | 완 | 값 | 변경 | 모델 호출 2회 한도 |
| I7 adoption-gate | reprocess.py(`proven and improved and not regression`, cycle, `roi_parse_supports_original`) | 탐지(게이트) | 후보는 정확 일치 근거+라벨 확인(`_label_seen`)+새 룰 이슈 없음+타 필드 품질 악화 없음+순환 아님일 때만 채택. ROI OCR이 원값을 그대로 읽었으면 VLM 단독 제안으로 덮지 않음 | 완 | 값 | 계약·상태 | 보수적이라 해결률은 낮음 |
| I8 cell-path-safety | reprocess.py:_candidate_path | 예방 | 표 칸은 "변하지 않는 유일한 행 정체성"으로만 대응, 행 번호만으로 안 함 | 완 | 행·값 | 위치 | 행이 변하면 후보 폐기 |
| I9 reprocess-budget | reprocess.py:settings/deadline_for/finished | 탐지(운영) | 시한·시도·모델 호출 한도, 취소 | 완 | 문서 | (제어) | 시한 도달 시 현 상태로 종료 |

## J. 근거(bbox)·신뢰도 처리 요약 (F절 참조)

| id | 위치 | 종류 | 설명 | 일반성 | 단위 | 연산 |
|---|---|---|---|---|---|---|
| J1 line-level-bbox | engine.py:_pick/_labelled/_ranked_lines | 예방 | 값의 bbox를 블록이 아니라 라벨 옆·아래 줄(1~2줄 높이 이내), 형제 값의 세로 띠에 가장 가까운 줄로 | 완(라벨 별칭은 `rules.LABELS`) | 값 | 위치(근거) |
| J2 rotation-aware-bbox | parsers.py:unturn, typed_evidence(`rotation_degrees`,`polygon`) | 예방 | 돌려 읽은 쪽·기울어진 셀도 원본 프레임 좌표·다각형 보존 | 완 | 값·쪽 | 위치 |
| J3 confidence-model | engine.py:_leaf/_line_leaf | 상태 | 1.0(확정)/0.5(범위 밖·모호)/0(없음) 3단계 이산 값, 임계 0.7 | 완 | 값 | 상태 |

## K. 작업 큐·운영 (문서 단위 일관성)

| id | 위치 | 종류 | 설명 | 일반성 | 단위 | 연산 |
|---|---|---|---|---|---|---|
| K1 claim-generation | main.py:claim/check_cancel/heartbeat/recover, jobs.py | 예방 | 세대(generation)·소유자 조건부 갱신으로 중복 처리·낡은 결과 덮어쓰기 차단, 죽은 작업 복구 | 완 | 문서 | 중복·상태·계약 |
| K2 deadline-cancel | latency.py:remaining/capped, main.py cancel-all | 예방 | 요청 시한·취소가 단계 경계에서 작동(진행 중 호출은 끝까지) | 완 | 문서 | (제어) |
| K3 ocr-slot | latency.py:ocr_slot | 예방 | GPU 레이아웃 동시 2건 상한 | 완 | 문서 | (운영) |

---

## (1) 메커니즘이 하나도 없는(또는 사실상 없는) 단위×연산 조합

범용 경로(R·J)에서 실제로 동작하는 것만 센 기준이다. "룰 한정"은 두 서식의 항목내역·진단서계 일부에만 있다는 뜻이다.

| 단위 | 연산 | 현황 |
|---|---|---|
| 문자 | 누락, 중복, 순서, 관계, 상태 | 문자 단위 탐지는 `_edit`(기본 꺼진 A16)·`_name`의 이름 반복 제거·마스터 1글자 교정뿐. 글자 누락·글자 중복·글자 순서 오류는 없음 |
| 값 | 순서 | 날짜 목록(통원일) 같은 값 내 순서 점검 없음 |
| 필드 | 순서 | 필드 간 순서는 의미 없음(해당 없음). 필드 경계(두 필드 값이 한 값으로 합쳐짐)는 G9 병명/수술명만 |
| 행 | 중복(일반) | 경계 1건 중복(B2)과 영수증 합계 베끼기(H12 ROW_COPY, V 경로)뿐. 같은 행이 반복되는 일반 중복은 C3 상한·프롬프트 지시만, 사후 탐지 없음 |
| 행 | 누락·추가(일반) | 행 누락은 영수증 복원(G10)·AO 대비(H12, V 경로)·쪽 실패 표시(B6)만. 진단서계·약제비 표의 행 누락/추가는 셀 단위 `no_source`(F3)로만 간접 탐지, 행 단위 집계 없음 |
| 행 | 경계(합침/분리) | 괘선 표(A13)와 영수증 행 복원(G10)뿐. 괘선 없는 표의 한 행이 두 행으로 갈라지거나 두 행이 합쳐지는 오류는 탐지 없음 |
| 열 | 중복(옆 열 복제) | 영수증 소계 옮김(G13)·세부내역서 코드 합침 외 일반 탐지 없음 |
| 열 | 상태·계약(값 제약) | 열 값의 종류 제약은 `table_misses`(세부내역서)만. 다른 표는 kind 정규화로 null 처리 후 끝 |
| 표 | 중복, 순서, 상태 | 같은 표가 두 번 인식되는 경우, 쪽 순서가 바뀐 경우, 표 판독불가 상태 표시 없음(쪽 실패는 B6만) |
| 표 | 추가(표 전체) | 인쇄되지 않은 표 생성은 G8(근거 문장에서 만든 행)이 오히려 만들어 냄. 탐지 없음 |
| 쪽 | 중복, 순서 | 쪽 순서는 입력 블록 순서(`groupby`)를 가정, 같은 쪽 반복은 탐지 없음 |
| 쪽 | 추가(머리글·바닥글·쪽 번호 유입) | `TOTAL_HINT` 문구(쪽 번호 값 금지)뿐, 코드 탐지 없음. LABEL_TYPES의 `marginalia`는 블록 유형만 표시하고 후속 처리 없음 |
| 쪽 | 상태(확대·잘림·흐림) | 해상도 손실·4장 초과 이미지 생략(A12)을 표시하는 메트릭 없음(경고 로그만) |
| 쪽 | 타일 분할/병합 | **없음.** 큰 쪽은 한 장으로 축소(최대 2000px), 타일 분할·병합 로직 없음 |
| 문서 | 중복, 순서, 경계(여러 문서가 한 파일), 위치 | 다중 프레임은 422로 거부(A18). 한 쪽에 여러 서류가 있는 경우 분리 없음 |
| 문서 | 상태(유형 오분류) | 유형은 호출자가 지정(`doc_type` 입력). Docraft 안에 유형 판별·불일치 탐지 없음(재분류는 하네스) |
| 묶음 | 모든 연산 | 문서 묶음 간 일관성(동일 환자·기관), 필수 서류 세트, 중복 문서, 서류 간 합계 대조는 Docraft에 없음 |
| 전 단위 | 추가(생성값)의 사전 억제 | 프롬프트(D1·D3·D4·D8)와 사후 근거 확인(F3)에만 의존. 모델이 값을 만들어 내도 근거가 느슨하게 맞으면 통과(근거는 OCR 위치 증명이지 이미지 판독 증명이 아님) |
| 전 단위 | JSON 복구 | 깨진 JSON 수리·내용 오류 재시도 없음(E3·E4). 대체 읽기는 rowmajor→asis 한 가지뿐 |

## (2) 하드코딩되어 새 서식·필드에는 동작하지 않을 메커니즘

데이터 표(yaml)로 분리되어 있어도 "대상 유형·필드 이름 열거"이므로 새 서식에는 항목 추가가 필요하면 포함했다.

| 메커니즘 | 하드코딩 대상 | 새 서식·필드에서의 동작 |
|---|---|---|
| C4~C8 열 배치(table_layout.py + table_layouts.yaml) | `tables`: 진료비영수증·세부내역서의 `항목내역` 둘뿐. `layout.forms` 1~5(영수증 양식), `header.words/keys/pairs/optional/single`(세부내역서 열 낱말) | 다른 유형·표는 `plan=None` → 합집합 열 순서로 읽음(열 밀림 방어 없음) |
| G10~G16, G20(rules.py `_receipt_table`,`_header_columns`,`_detail_swaps`,`_group_dates`,`_period`,`_section_items`,`_carry`,`_totals`,`_swaps`) | `ITEM_TABLE="항목내역"`, `doc_type == "진료비영수증"/"세부내역서"` 분기, 열 이름(본인부담금·공단부담금·전액본인부담·EDI코드·원내코드·시작일자 등) | 새 서식·새 표에는 발동하지 않음 |
| H5~H12 룰(`DETAIL`·`RECEIPT` 대상 튜플) | 위 두 유형의 항목내역 | 위와 동일 |
| C10 `table_misses` 게이트 | 세부내역서 행 산술(단가×횟수×일수 등) | 산술 관계가 없는 표에는 0을 반환해 asis 재읽기가 안 걸림 |
| G4 `FIELD_RULES`·`_name`·`_hospital`·`_address`·`_serial` | 필드 이름 목록(이름·의사명·환자성명·병원명·주소·등록번호 등), `의과의원→외과의원` 치환, 이름 2~5자 한글 | 새 필드는 정규화만(kind) 적용, 필드별 정제 없음 |
| G7 라벨 보충 + `LABELS`·`EXCLUSIVE`·`SECTIONS`·`FIELD_SECTION`·`EXPLICIT` | 필드 이름별 라벨 동의어 표(약 60개 필드) | 라벨 표에 없는 필드는 보충 안 됨 |
| G8 `NOTES`·`MARKS` | 수술·검사·치료내역 표, '(검사)·(수술)·(치료)' 표시 | 해당 표가 없는 유형에는 미적용 |
| G11~G13 `UNPRINTED_NULL`·`TOTALS`·`FIELD_SUMS`·`KEEP_TOTALS`·`total_fields` | 급여_*총액, 진료비총액, 납부한금액_* 등 필드명 | 새 합계 필드는 등록 전까지 검증·교정 안 됨 |
| H2 날짜 순서 `DATE_ORDER`·`ISSUED`·`LATER_OK` | 입원/퇴원·진단/발급 등 필드 쌍 | 새 날짜 쌍은 등록 필요 |
| H13/`required` | 유형별 필수 필드·표·항목 목록(`REQUIRED_ITEMS`, 예외 정규식) | 새 유형은 필수 점검 없음 |
| G19 master | `master_names`: 병명내역(KCD)·항목내역(EDI)만, 마스터 원본이 KCD/EDI뿐 | 다른 코드계는 교정 없음 |
| F4~F6 typed_evidence·inference | `DOC_TYPES`에 있는 7개 유형만 `augment`, `납부한금액_` 접두 처리, `_RANGES`(진료기간 등) 라벨, `SCHEMA_ALIASES`, `EXCLUSIVE_CHECKBOX_GROUPS`(진단서계), `FIELD_SUMS` | 일반 스키마·새 유형은 "기존 근거만" (코드 docstring: generic schemas keep their existing grounding) |
| I2·I4 reprocess의 결정론 후보·회전 합계 | 위와 같은 필드 목록(`doctypes.spec`, `rules.FIELD_SUMS`) | 일반 스키마는 ROI/VLM 단계만 동작 |
| D1 ROWS_SYSTEM 마지막 항목, D7~D10 필드·표 힌트, D11 JUDGE_PROMPT | 소계·합계·계·끝수처리금액, 진료비영수증 항목명 규칙, "Korean medical document" | 새 서식은 프롬프트 지시 갱신 필요(다만 문구는 모델 해석에 따라 일부 일반화) |
| G1 normalize 중 `_phone`·`_idnum`·`_code`·`_date`(년월일, 2자리 연도 규칙) | 한국 서식 포맷 | 다른 국가 서식은 별도 정규화 필요 |

### 완전 일반(참고)
rowmajor 기본 메커니즘(C1~C3·C9)·청크·쪽 묶음·병합(B1~B6), 방향 판별·재읽기(A8~A10), 괘선 격자 재구성(A13~A15), JSON 파싱·절단 탐지(E1~E5), 스키마 검증·assess·grounding(F1~F3·F7~F9), 작업 큐(K1~K3)는 문서유형·필드명에 의존하지 않는다. 다만 `ground`의 라벨 근접 판정은 `rules.LABELS` 별칭에 의존하며 별칭이 없으면 필드 키·제목만 쓴다.
