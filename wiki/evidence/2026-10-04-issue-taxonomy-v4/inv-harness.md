# harness-v2 dev(15b172a) 추출 오류 탐지·보정 메커니즘 목록

조사 범위: `/home/pilsu/projects/mirae-assets/harness-v2/src/mlife_harness` (읽기 전용). 경로는 이 디렉터리 기준.
약어 — 종류: 탐=탐지만, 보=보정, 탐+보=탐지+보정, 보류=검토 표시. 일반성: H=서식·필드명 하드코딩, R=규칙 데이터(yaml/표)로 파라미터화, G=완전 일반.
단위: 문자/값/필드/행/열/표/쪽/문서/묶음. 연산: 누락/오독/정규화/추가(근거 없는 추가)/중복/위치(행·열·필드 오배정)/경계(합침·분리)/순서/관계(머리글·병합·라벨-값·문맥)/상태(선택표시·확실성·버전·판독불가)/계약(스키마·값제약·근거·완결성).

## A. 접수·구조 (ingest/, normalizer/flatten.py, normalizer/doc_code.py, reclassify/)

| id | 위치 | 종류 | 입력 신호 → 변경 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| ING-CONTRACT | ingest/contract.py:validate_input | 탐(거부) | JSON 파싱·transaction_id·documents·document_id·이미지 존재/열람/50MB·쌍 → `rejected`(처리 안 함) | G | 묶음/문서 | 계약 | 입력 형식이 약간 다른 정상 건 거부 |
| ING-PAIR | ingest/pairing.py (find_pair_image) | 보(이름 정규화) | 확장자·`_merged`·`.classification.<uuid>` 표식 제거, NFC → 이미지-JSON 짝 | G(표식 패턴은 코드 상수) | 묶음 | 관계/경계 | 다른 문서에 잘못 짝 지을 수 있음 |
| ING-IDEMP | ingest/hashing.py, pipeline/document_unit.py:_transition | 탐(건너뜀) | (batch, document_name, 파일 해시) 같으면 재처리 안 함 | G | 묶음/문서 | 중복 | 내용 바뀐 재제출은 해시로만 구분 |
| FLAT-ANOMALY | normalizer/flatten.py (AnomalyKind 7종) | 탐(로그만)+보(중복키는 첫 값만 채택) | headers 없음/셀 키 과·부족/중복 셀·필드 키/비 dict 노드/UI label≠key → `StructAnomaly` | G | 표/행/필드 | 계약/중복/위치 | 판정(등급)에 반영되지 않음(runner 로그만). 중복 키의 뒤 값은 조용히 버려짐 |
| DOC-CODE | normalizer/doc_code.py:resolve_document_code | 보+보류 | AO 한글 `doc_type` → 문서코드(매핑 데이터). 미지 서식→`undetermined`, 세부내역서 입·통원 구분이 비면 `review_required` → 문서 `unresolved`(arbitrator:_apply_document_code_signal) | R(매핑 표) + H(세부내역서 `환자정보(입통원구분)`, 0710/0720) | 문서 | 상태/관계 | 미지 서식은 필드가 모두 통과해도 문서가 unresolved |
| RECLASS | reclassify/reclassifier.py + title.py | 탐+보 | 첫 쪽 상단 25% 줄 OCR 제목 → 서식. 같은 스키마 계열이면 `doc_type`만 교체, 다른 계열이면 Docraft 전체 재추출. 제목급 글자 크기가 아니면 바꾸지 않음(`detected`) | H(제목 정규식 7종·스키마 계열 표) | 문서/쪽(첫 쪽) | 상태/관계 | 단일 쪽 문서만 재추출, 제목 오인식 시 정상 AO 분류를 뒤집음(제목급 조건으로 완화) |

## B. 정규화 — 확정 가능한 표기·위치 오류 보정 (normalizer/value_fix.py, 분기 10-n으로 채택)

공통: 교정은 사본에 단계 순서로 적용(`normalize_document`, `_STAGES`), 원본은 증거에 보존. `confirm=True`인 것은 재판독이 같게 읽어야 확정(아니면 교정값을 unresolved로). 채택 후 그 칸에 규칙 fail·마스터 불일치가 남으면 채택 안 함.

| id | 위치(value_fix.py:함수) | 종류 | 입력 신호 → 변경 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| N-DATE | `_dates` | 보 | 키 이름이 날짜(`infer_kind` 정규식: 일자·일$·날짜·진단일…)이고 단일 날짜로 읽히면 → YYYYMMDD(부분 날짜 허용). 기간·YYMMDD·Null은 그대로 | H(키 정규식 domain/normalize.py `_DATE_KEY_RE`) | 값 | 정규화 | 일/월 순서 모호 표기(2021.6.3 류), 키 이름 오판 |
| N-SECTION | `_section_items`+coverage.drop_section_rows | 보 | 세부내역서 `항목`이 `EDI명칭`을 베낌 → 바로 위 섹션 제목 행(`01.진찰료`꼴) 제목, 없으면 빈 값. 제목 행 삭제·행 번호 재매김 | H(세부내역서 `항목`/`EDI명칭`, 제목 정규식) | 필드/행 | 위치/관계(문맥 상속)/중복 | 정답이 베낀 항목을 그대로 둔 서식 |
| N-WARD | `_ward` | 보 | `환자정보(병실)`에 진료과 이름 → 빈 값 | H(`환자정보(병실)`, 진료과 정규식) | 필드 | 위치 | 병동명에 `과`가 든 경우 |
| N-DECIMAL | `_decimal_points` | 보(confirm) | `계`·끝수 행 금액에서 빠진 소수점(142,680.75→14268075) — 열마다 계+끝수=합계, 계 행 부담합=총액이 한 해석으로 맞을 때만 복원 | H(세부내역서 요약 행) | 문자/값 | 오독(누락 문자) | 합계가 우연히 맞는 다른 스케일 |
| N-SUMSHIFT | `_summary_shift` | 보(confirm) | 요약 행 금액이 단가·횟수·일수로 왼쪽 밀림 → 제자리(행 사이 식이 한 배치로 모일 때) | H(세부내역서 열 이름) | 행/열 | 위치 | 식이 우연히 성립 |
| N-ADJROW | `_adjustment` | 보(confirm) | 끝수 행 = 합계 − 계로 칸 계산 | H | 행 | 추가(계산값)/위치 | 인쇄값 대신 식 값(재판독 일치 필요) |
| N-SUBGAP | `_subtotal_gap` | 보(confirm) | `계` 행의 빠진 부담 칸(0 칸 차이/한 칸 밀림)을 식으로 채움 | H | 행/열 | 누락/위치 | 〃 |
| N-UNPRTOT | `_unprinted_totals` | 보 | 모든 쪽 AO parse 글자에 합계 라벨이 없고 표에도 합계·계 행이 없으면 `합계` 그룹 금액 → 0(AO가 항목 합으로 채운 값) | H(`합계` 그룹 키) | 필드/그룹 | 추가(근거 없는 값 제거) | parse 글자 누락 시 인쇄된 합계를 0으로 지움(parse 없으면 미적용) |
| N-TOTUNC | `_total_uncovered` | 보 | `합계.비급여총액` 0·공란인데 항목 비급여 합>0이고 다른 총액 3개가 항목 합과 일치 → 항목 합으로 채움 | H | 필드 | 누락/추가 | 비급여 합계가 실제로 0인 문서 |
| N-UNPRBEN | `_unprinted_benefit`+`_benefit_printed` | 보 | `급여` 열이 인쇄되지 않은 서식(parse 머리글 기준)의 `급여` 칸 → 빈 값 | H(세부내역서 `급여` 열) | 열 | 추가(제거) | parse 머리글 오인식 |
| N-SUMCNT | `_summary_counts` | 보 | 요약 행 투여량·단가·횟수·일수 `0` → 빈 값(parse에 0이 인쇄된 열은 둠) | H | 행/열 | 추가(제거) | 〃 |
| N-DOSE | `_blank_doses` | 보 | 투여량 열이 인쇄된 서식의 빈 투여량 — 단가×횟수×일수=총액이면 `1` | H | 필드 | 추가(기본값) | 총액이 우연히 맞는 경우 |
| N-WRAPCODE | `_wrapped_codes` | 보 | EDI코드가 영숫자 1자 + 원내코드가 원장 형태 아님 → 둘을 이어 EDI코드, 원내코드 비움(셀 줄바꿈 분리) | H(EDI코드/원내코드) | 필드 | 경계(합침) | 실제 1자 코드 |
| N-COPYCODE | `_copied_codes` | 보 | 원내코드가 모든 행에서 EDI코드와 같음 → 원내코드 비움(코드 열 1개 서식의 복제) | H | 열 | 중복 | 실제로 같은 서식 |
| N-LETTERO | `_letter_o_codes` | 보 | 원내코드 숫자 구간 `O`→`0`(FDOO1→FD001) | H(원내코드) | 문자 | 오독 | 영문 O가 정상인 코드 |
| N-CNTPRICE | `_count_in_price` | 보 | 금액이 모두 빈 행에서 횟수가 단가 숫자의 앞부분이고 단가가 마스터 단가 컬럼 어디와도 다르면 단가→횟수로 이동(마스터 있을 때) | H(세부내역서 원외 처방 행) | 필드 | 위치 | 마스터 단가 개정 |
| N-PRTBEN | value_fix:`printed_benefit` ← runner `_printed_benefit` | 보 | Docraft가 읽은 급여구분 인쇄 원문이 숫자 표기(80/100 등)이고 급여로 해석되면 급여구분=급여·전액본인부담 금액→급여 칸(금액 열 1개 서식만) | H | 행/열 | 위치/상태 | Docraft 행 대응 오류 |
| N-CLASS | `class_item_fixes` ← runner `_docraft_classes` | 보 | ④' 후에도 빈 `항목`을 Docraft 분류 열로 채움 | H | 필드 | 누락/추가 | Docraft 분류 오독 |
| N-DXLABEL | `_diagnosis_labels` | 보 | 병명 앞 서식 표지 `(주 질병·부상)`·`(부상병)`·`주-` 제거(병명 없이 표지만이면 그대로) | H(`병명내역.병명`, 표지 정규식) | 필드/문자 | 정규화/경계 | 병명 일부가 표지와 같은 모양 |
| N-DXNAMES | `_diagnosis_names` | 보 | 코드만 있는 행 k개가 이어지면 코드별 원장 명칭으로 원문 전체를 설명하는 유일한 k+1 조각을 찾아 차례로 싣기; 앞 행 끝 NOS를 뒤 행으로 이동(마스터 필요) | H(`병명코드`/`병명`) + 마스터 | 행 | 경계(분리)/위치 | 조각이 유일하지 않으면 미적용(보수적) |
| N-CHECKS | `_paired_checks`+coverage.add_missing_checks | 보(default) | `최종진단`·`임상적추정` 빈 값 → `N`, 키 자체가 없는 구스키마는 빈 칸을 붙임 | H(진단서 4종 두 키) | 필드 | 추가(기본값)/상태 | 문서에 표시가 있는데 AO가 놓친 경우(재판독이 다른 값을 읽으면 채택 안 함) |
| N-ACCIDENT | `_accident_date` (= 규칙 R-CERT-ACCIDENT와 같은 함수) | 보 | 사고발생일자를 진단일·검사일·수술일자·치료일로 산출해 AO 값과 다르면 교체(없으면 `Null`) | H(진단서 4종, 키 이름 5개) | 필드 | 관계/값 | 산출 입력이 틀렸으면 틀린 값을 확정 |
| N-ITEMNAME | `_item_names`+`standard_item`/`_misread` | 보 | 영수증 `항목`을 shared yaml `item_aliases` 정규식으로 표준명, 표준명과 한 글자(자모) 차이인 후보가 하나뿐이면 교정 | R(shared/receipt_items.yaml `item_aliases`·`receipt_item_names`) + H(영수증 `항목`) | 값/문자 | 정규화/오독 | 비정형 항목명은 그대로 보존. 유사 표준명 오교정 |
| N-DEPT | `_department` | 보 | 진료과가 표준 진료과목 사전(`departments`)에 없고 신뢰도<0.9이며 자모 하나 차이 후보 하나뿐 → 교정(글자 빠진 이름 제외) | R(yaml 사전)+H(`환자정보-진료과`, 임계 0.9 상수) | 값/문자 | 오독/상태(확실성) | 실제 다른 과 |
| N-SWAP | `_column_swaps` | 보 | 영수증 금액 열 두 개가 통째 맞바뀜(yaml `swaps` 쌍) — 맞바꾸면 두 열의 항목 합이 모두 합계 행과 맞을 때만. 행 2개 이상이면 항목 행, 1개면 합계 행 두 칸 | R(`swaps`)+H(영수증 열 이름) | 열 | 위치 | 합계 행 자체가 오독이면 합이 안 맞아 미적용 |
| N-COLSHIFT | `_column_shift` | 보(confirm) | 합계와 어긋나는 열이 X(+d)·Y(−d) 둘뿐이고 6칸 이하 조합이 하나뿐일 때 칸 일부를 옮김 | H(영수증 금액 열) | 열/행 | 위치 | 조합 유일성 가정 |
| N-MOVEPUB | `_moved_public` | 보 | 공단부담금 열 전체가 다른 금액 열에 실림 — 합계=진료비총액−환자부담총액이고 행별 부담률 같을 때 | H | 열 | 위치 | 부담률 편차 0.05 상수 |
| N-BEN2UNC | `_uncovered_benefit` | 보 | ①②③이 표 전체에서 0·공란이고 공단부담총액 0인데 `급여`에 금액 → 비급여 열로(환자부담총액이 합계 행 비급여와 맞을 때) | H | 열 | 위치 | 〃 |
| N-UNCCOL | `_uncovered_columns` | 보 | `비급여`↔`선택진료료외` 칸 이동. 서식 (A)④비급여 1칸/(B)④선택진료료·⑤외는 parse 머리글 글자(없으면 페이지 이미지 줄 OCR)로 판별 | H(영수증 두 열) | 열/행 | 위치/상태(서식 버전) | 서식 판별 실패 시 선택진료료외 값 유무로 추정 |
| N-DRG | `_drg` | 보 | 질병군(DRG) 번호가 `영문1자+숫자`가 아니면 → 빈 값(자리 수만 다른 값은 두고 규칙이 검토) | H(`환자정보-질병군(DRG)번호`) | 필드 | 위치/계약 | 실제 DRG 형식이 다른 병원 |
| N-INST | `_institution_type`+domain/normalize.standard_institution_type | 보 | 요양기관종류 표기(공백·가운뎃점·체크 기호) → 표준 4종. 선택지 여럿 읽힌 값은 그대로 | H(`의료기관정보-요양기관종류` 키·표준 4종 표) | 값 | 정규화/상태(선택표시) | 노이즈 글자 제거 후 우연 일치 |

## C. parse 표 보충·행 복구·추출 누락 검증 (parser_fill.py, coverage.py, shared yaml)

| id | 위치 | 종류 | 입력 신호 → 변경 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| PARSE-FILL | parser_fill.py:parser_fixes (룰 3·4; runner `_parser_recheck`/`_row_checked`) | 탐+보 | AO 값이 빈(0 포함) 금액 칸과 금액 밖 열(투여량·횟수·일수·EDI코드·EDI명칭·항목)을 AO parse 표(HTML) 값으로 보충. 거름: (a) 한 칸 숫자 2개 이상, (b) 큰 값 3개 뺀 평균의 30배 초과(`parser_outlier_ratio`), (c) 같은 행 다른 부담 칸에 이미 같은 금액, (d) 같은 코드 행 2개, (e) 윗·아랫 행에 같은 금액이고 parse가 비운 칸은 행 밀림으로 보고 비움(`_shifted`), 합계 행은 열 합 일치로만. parse 추가 행은 규칙 새 fail 없을 때만 유지 | R(30배·trim 3은 yaml)+H(영수증 `항목` 표준명/세부내역서 코드 행 열쇠, 열 이름) | 필드/행/열 | 누락/추가/중복/위치/관계(머리글 병합 격자) | parse 오류가 이상치 거름을 통과, 행 대응 오류 시 다른 행 값을 채움 |
| ROW-RECOVER | coverage.py:recover_rows (②' parse 인쇄 순서, ④' Docraft 표) | 보 | 인쇄 증거의 표준 항목명(영수증)이 AO 표에 없으면 빈 행을 만들어 붙임(금액 없는 선별급여·65세이상등정액·정액수가 등) | H(영수증 `항목내역`, 표준 항목명) | 행 | 누락/추가 | 같은 이름 중복 행 판단 |
| PARSE-PRINTED | parser_fill.py:printed_columns·detail_printed·uncovered_form·code_columns | 탐 | parse 머리글에서 인쇄된 열·서식 종류 파악 → N-UNPRBEN/N-SUMCNT/N-UNCCOL/COV-R5의 입력 | H(영수증·세부내역서) | 표/열 | 관계(머리글)/상태(서식 버전) | 머리글 병합 해석 오류 |
| COV-R1 | coverage.py:coverage_review 룰1 + yaml `required_keys`·`min_extract_ratio` 0.97 | 보류 | 문서 종류별 늘 인쇄되는 키 중 채운 비율 <0.97 → 문서 `unresolved`, 빈 키 경로를 review_paths(표 키는 첫 칸=표 전체 재판독) | R(yaml 문서 종류별 키 목록) | 문서/필드/표 | 누락/계약(완결성) | 인쇄되지 않아 비는 키가 목록에 있으면 오탐. 합계 행 없는 서식 등 |
| COV-R2 | coverage.py:missing_items + yaml `required_items`·`required_items_exempt` | 보류 | 영수증 `항목내역`에 표준 항목(진찰료·CT진단료)이 없으면 문서 unresolved. 한방/한약/첩약 행이 있으면 CT진단료 제외 | R(yaml)+H(영수증) | 행/표 | 누락 | 항목이 실제로 없는 서식(예외 정규식에 없는 새 서식) |
| COV-R5 | coverage.py:expected_cells + yaml `required_cells` | 보류 | parse 머리글로 인쇄 열을 알 때만: (a) 인쇄 열이 항목 행 전체에서 빔, (b) 행 종류(항목·소계·합계·끝수)별 필수 열의 인쇄 열 칸이 빔 → review_paths(값은 안 만듦) | R(yaml 문서종류·행종류·열)+H(세부내역서·영수증만) | 열/행/필드 | 누락/관계 | 금액 칸이 모두 빈 행은 제외, 정답지 59건 기준 임계 |

## D. 규칙 엔진·규칙셋 (rules/, rulesets/*.yaml) — 값은 바꾸지 않고 pass/warn/fail/not_applicable 증거만 낸다

엔진 공통(rules/engine.py·expr.py·spec.py·tolerance.py): 결측 전파→`on_missing`(기본 not_applicable); 규칙 하나 예외는 not_applicable로 격리; `regions`가 잘림(crop_detected)이면 not_applicable; yaml 스키마 위반·허용 목록 밖 함수·`rule_set_version` unpinned는 **기동 실패**; 금액 대조는 백원 단위 절사 비교(양쪽 절사값 같거나 차이<100원이면 pass, warn 없음); 증거는 규칙이 읽은 모든 필드에 붙음.

| id | 위치 | 종류 | 무엇을 보는가 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| ENG-CORE | rules/engine.py·spec.py·expr.py | 탐 | 위 공통 사항 | G | 문서/필드 | 계약 | not_applicable이 "검사 정상"과 하류에서 구분 안 됨(readiness가 마스터 미적재는 막음) |
| ENG-TOL | rules/tolerance.py | 탐 | floor(100원)·absolute·relative 허용오차 | R(yaml `tolerance`) | 값 | 오독(경계 허용) | 100원 미만 오독은 검출 못 함(요건에 명시) |
| ENG-ROWKIND | rules/builtins.py:excluded_row_reason·total_row_index·summary_label·adjustment_row_label·_is_lump_row | 탐 | 행 라벨(합계·총계·소계·계·합계(조정후)·끝수/끝전/절사…)로 합계·조정·포괄수가 행을 열 합·행 검사에서 제외 | H(한글 라벨 상수, `LUMP_ITEMS`, 첫 열·`항목`/`EDI명칭`) | 행 | 관계(행 종류) | 새 라벨 표기는 합계로 인식 못 해 항목에 합산 |
| ENG-SPLIT | builtins.py:uses_split_columns·_lumped·grouped_amount·split_amount·header_total·split_total | 탐 | 영수증 `급여`·`비급여`가 값 칸인지 그룹 머리글인지(하위 칸에 0 아닌 값 유무) 판별해 읽을 칸 선택 | H(영수증 열 이름) | 표 | 관계(머리글)/상태(서식 버전) | 판별 틀리면 오탐/미탐 |
| STRAT-CROP | rules/strategies.py:resolve_ac029_strategy+domain/bbox.py | 탐 | UI response 좌표: 합계 영역 외접 사각형이 이미지 가장자리에 닿으면 `crop_detected` → 그 영역 규칙 not_applicable(우측/하단 기준 전환). API 입력은 좌표 없어 판정 불가(None) | H(영수증 right_summary/bottom_table) | 쪽/표 | 누락(잘림)/계약 | 좌표 없는 입력은 잘림 미탐 |
| FMT_KCD_01·02 | medical_cert.yaml + builtins:kcd_normalizable·kcd_format_ok | 탐 | 병명코드 정규화 가능·영문 시작 3~6자리(복수 코드는 조각별) | R(규칙 yaml, 문서코드 0120·1333·0130·1250)+H(`병명내역.병명코드`) | 값/문자 | 계약(값제약) | `-` 허용 등 체계 가정 |
| MASTER_KCD_03 | 〃 + lookup.check_kcd_parts | 탐 | 코드가 KCD 마스터에 존재. 없으면 접미 영문자/`-숫자` 제거 기저 코드+병명 완전 일치일 때만 warn으로 낮춤 | R+H | 값 | 오독/계약 | 마스터 개정 지연 시 신규 코드 fail |
| MASTER_KCD_04 | 〃 + master/kcd_name.py | 탐 | 코드↔병명: 후보 명칭 집합 일치→3단(토큰 겹침·부분문자열·bigram Dice 0.5)→임베딩 4단(0.75, 설정 시). 동의어 사전 kcd_synonyms.yaml | R(임계·사전)+H(병명) | 필드/행 | 오독/관계 | 병원 표기가 원장과 멀면 fail(값은 안 바꿈, 분기 11 unresolved) |
| ENRICH_KCD_05 | 〃 + 분기 10-a/b | 보(채움) | 코드만 있고 병명 빈 칸 → 마스터 명칭(복수면 쉼표로 전부) 제시, 판정 inferred | R+H | 필드 | 누락/추가 | 원문에 없는 값을 적재(원문과 달라지는 보정 금지 방침과 충돌 가능) |
| SORT_KCD_06 | 〃 + engine:_sorted_codes | 탐 | 복수 코드 정렬 대조, **중복 코드만** warn | R | 열/표 | 중복/순서 | 순서 자체는 오류로 보지 않음 |
| R-KCD-REVERSE | 〃 + master/reverse.py:scored_reverse_lookup (분기 10-c/10-d) | 탐+보(조건부 채움) | 코드 빈 행에서 병명으로 원장 역조회: 점수=max(토큰 Dice, bigram Dice)+부위 보너스 ≥1.0 단독 1위(또는 같은 3단위 계열 동점)이면 inferred 코드, ≥0.5면 후보만(ambiguous) | R+H | 행/필드 | 누락/추가 | 병명 같은 다른 코드 채택 |
| R-KCD-AXIS | 〃 + master/kcd_axis.py:check_axis | 탐 | 5·6째 자리 축(근골격 부위·척추·편측성·개방/폐쇄, 귀 H60–H95 예외)과 병명 꼬리표/키워드 모순. 원장 없이 | H(KCD-8 보조세분류 표 4종 상수, 코드군 범위) | 값/행 | 관계/오독 | 정상 행 오탐을 피하려 보수적(꼬리표 우선) |
| R-KCD-PAIRING | 〃 + master/kcd_pairing.py (분기 10-g swap) | 탐+보 | 병명 배열을 기준축으로 병명코드를 각 명칭에 맞게 재배치(총점 최대 배정: n≤7 전수, 이상 헝가리). 현재 총점보다 1e-6 이상 클 때·새 짝 점수≥0.5·모든 코드 원장 존재일 때만 | R(0.5 상수)+H(병명코드/병명) | 행/표 | 위치/순서 | 정상 문서 재배치 방지 장치(0.5) 있으나 점수는 편집거리 비율 |
| MS-KCDREPAIR | domain/normalize.py:kcd_repair_candidate+lookup.resolve_kcd_repair (분기 10-e) | 보 | KCD 6자리 초과 절단(N4)→선두 숫자 치환(0→O,1→I,5→S,8→B,2→Z,6→G, N5), 후보가 원장에 있고 병명 모순 없을 때 repaired | H(`KCD_HEAD_FIX` 표, KCD 길이 6) | 문자 | 오독 | 3·4·7·9 시작은 후보 없음. 한 칸 복수 코드의 조각은 교정하지 않음 |
| MS-KCDFALLBACK | master/kcd_fallback.py:resolve_kcd_fallback | 탐(값 불변) | 접미 제거→N4·N5→절단 재조회(축 값)→`-` 빠진 세분 끝자리(R50992→R5099)는 **후보만**(검토 사유) | H(KCD 체계) | 값 | 오독/상태(버전 접미) | 4번은 확정 안 함 |
| MS-KCDMERGE | master/lookup.py:kcd_merged_names·kcd_name_via_document; kcd_name.merged_leftover/is_dx_row_path | 탐(후보) | 병명 합침 의심(남은 말이 다른 계열 후보) / 다른 명칭 항목(수술명·치료명·검사명)·다른 행 병명을 붙여 재판정 | H(진단서 계열 명칭 항목) | 필드/행 | 경계(합침)/위치 | 후보만 |
| MS-KCDSPLIT | domain/normalize.py:split_kcd_codes | 보(조회용 분리) | 한 칸에 붙은 복수 KCD 코드를 조각으로 나눠 조회·형식 검사(값은 그대로) | H(KCD) | 값/필드 | 경계(분리) | |
| MASTER_0710_08 | detail_0710.yaml + lookup.resolve_edi_code·resolve_edi_row | 탐 | EDI코드 원장 조회: 공백·대문자(E1)·이중 코드 첫 번째(E2)·정확(E3)·뒤에서 한 자씩 절단 최소 5자(E4)·원내코드 2순위. 미적중은 오류 아님(not_applicable + out_of_scope 분류) | R+H(`EDI코드`/`원내코드`/`EDI명칭`, 세부내역서 0710·0720) | 값/행 | 오독/위치(코드 열 뒤바뀜)/경계(이중 코드) | E4 절단 적중이 다른 코드일 수 있음 |
| OOS-CLASS | master/code_class.py:out_of_scope_on_miss+분기 10-f | 보류 아님(분모 제외) | 미적중 코드의 분류(약품코드 9자리·치료재료·비급여·코드 형식 아님·원내코드·원장 미적중·명칭 미적중) → tier out_of_scope(롤업·정확도에서 제외) | H(분류 규칙, 치료재료 사례 품목명) | 값 | 상태/관계 | 원장 개정으로 못 찾은 정상 코드가 "범위 밖"으로 숨음 |
| BENEFIT-TYPE | code_class.py:interpret_benefit_type | 탐(해석) | 급여구분: 비급→비급여, 100%·100/100→전액본인부담, 나머지 급여(열추출 자리표시도 급여) | H(세부내역서 `급여구분`) | 값/필드 | 상태(속성)/정규화 | 부분 부담률(80/100)이 급여로 분류(N-PRTBEN이 보완) |
| MASTER_0710_09 | detail_0710.yaml + lookup.check_edi_name·master/similarity.py·embedding.py | 탐(+후보) | 원장 코드의 원장 명칭 ↔ EDI명칭: bge-m3 코사인 **≤0.2** 또는 임베딩 미설정 시 IDF 가중 문자 2-gram 포함도 ≤0.2 → fail(코드 오독 의심) + 명칭 역유추 후보 코드. 값은 안 바꿈(분기 11 unresolved) | R(임계 설정)+H(EDI) | 필드/행 | 오독/관계 | 약어·병원 표기 차로 오탐 가능 |
| MASTER_0710_10 | 〃 + master/reverse.py:edi_reverse_lookup | 탐(후보) | 코드 없을 때 명칭 IDF 2-gram 포함도>0.2 후보(명칭·체계별 최단 코드). **자동 채택 안 함**(ambiguous) | R+H | 행 | 누락 | |
| MASTER_0710_11 | 〃 + engine:_check_unit_price | 탐 | 행 단가 ↔ 수가 마스터 단가 컬럼(요양기관종류→컬럼 매핑 yaml). 불일치 warn, 금액 칸 모두 빈 행은 fail | R(매핑)+H(`단가`·`의료기관정보-요양기관종류`) | 필드 | 오독/관계 | 고시 개정 단가 차(warn) |
| R-0710-ROWSUM | detail_0710.yaml + engine:_rowsum_multi | 탐 | (본인부담+공단부담+전액본인부담+비급여[선택진료료+외 합 우선])×(일수\|횟수) = 총액, 세 해석 중 하나라도 맞으면 pass. 합계·끝수 행 제외, 부담 칸 모두 빈 소계 제외 | R(params)+H(세부내역서 열 이름) | 행 | 오독/위치(열 간)/관계 | 문서 자체 불일치 행(부담합 18·총액 0)은 100원 절사로 pass |
| R-0710-PARTITION | 〃 + engine:_column_partition | 탐 | 항목 행 열 합 ↔ 합계 그룹 총액(본인·공단·전액·선택진료료·외·비급여). 상쇄 짝은 `offset_with`로 기록. 합계 칸 공란이면 n/a. 합계 0 서식에서 0 아닌 합계는 fail(추출기가 채운 값). 증거는 합계 필드에만 | R+H | 열/표/그룹 | 오독/위치/누락 | 100원 미만 오독 미검출 |
| R-0710-UNITMUL | 〃 | 탐 | 단가×횟수×일수(+투여량) = 총액, 해석 기록. 묶음 산정 행은 문서 자체 불일치(severity medium) | R+H | 행 | 오독 | 정상 문서 오탐 |
| CALC_0710_17·18 | 〃 | 탐 | 합계 그룹 내부 항등식(급여총액=본인+공단+전액, 비급여총액=선택진료료총액+외). 비급여는 두 총액 합 0이면 n/a | R+H | 그룹/필드 | 관계/오독 | |
| STRUCT_0710_16 / STRUCT_AC029_13 | 〃, ac029.yaml + builtins:column_alignment·table_aligned | 탐 | 열마다 값 배열 길이=행 수, 헤더 밖 칸 없음. short/extra/misaligned_rows를 context·로그에 | R | 표/열/행 | 계약/위치 | 재검증 1회 후에도 불일치 시 review라 했으나 코드는 규칙 fail 증거만 |
| CALC_AC029_01·02·CROSS_05·10·11·12 | ac029.yaml + builtins | 탐 | 진료비총액=급여+비급여, 환자부담총액=①+③+비급여, 우측↔하단 상호 대조, 합계 행 열 합, 합계 행 급여·비급여 항등식(서식 판별 `uses_split_columns` 통해 n/a 처리) | R+H(AC029 열·그룹 이름) | 문서/표/열/행 | 오독/위치/관계 | ⑥ 상한액초과금은 02에 미반영 |
| R-AC029-PAYABLE·PAID·BURDEN | ac029.yaml | 탐 | 납부할 금액 식(감면·가산 항 or_zero), 납부한 금액 합계, 진료비총액=환자부담+공단부담+상한액초과금(상호 갈릴 수 있음) | R+H | 필드/그룹 | 오독/관계 | 식에 없는 감면 항은 n/a |
| FMT_AC029_DRG | ac029.yaml + builtins:drg_format_ok | 탐 | DRG 번호 영문1+숫자4~5, 아니면 fail(N-DRG가 먼저 비움) | R+H | 필드 | 계약/위치 | |
| FMT_AC029_INSTITUTION | 〃 + builtins:institution_type_ok | 탐(→④' 재판독) | 명칭에 `병원`인데 의원급, 또는 명칭이 `의원`으로 끝나는데 병원급 이상, 또는 1차 신뢰도<0.7 → fail(warn은 확정을 안 막아 재판독 대상이 못 되므로 fail) | R+H(명칭 문자열 규칙, 0.7 상수) | 필드 | 상태(선택표시·확실성)/관계 | 명칭에 `병원`이 든 의원 오탐 |
| R-CERT-ACCIDENT | medical_cert.yaml + builtins:accident_date | 탐 | 사고발생일자=산출값 대조(attach_target_only: 입력 칸 안 끌어감) | R+H | 필드 | 관계 | |
| FMT_CERT_STATUS | 〃 | 탐 | 최종진단·임상적추정 ∈ {Y,N}(둘 다 Y/N 가능) | R+H(key_pattern) | 필드 | 상태(선택표시)/계약 | |
| R-CERT-SEX·BIRTH | 〃 + builtins:rrn_sex·rrn_birth | 탐(warn) | 성별/생년월일 ↔ 주민번호 뒷자리 첫 숫자·세기. 서식 칸이 우선이라 warn | R+H(`환자 주민번호`/`성별`/`생년월일`) | 필드 | 관계 | 외국인 번호(5~8)·세기 가정 |
| (규칙 없음) | rulesets/ — 0730 약제영수증 | — | 규칙 yaml 자체가 없음. 마스터 대조 쌍(EDI:약국_급여)과 COV-R1 required_keys만 작동 | — | — | — | 검증 공백 |

## E. 판정(Arbitration)·상태 (arbitration/, domain/tier.py)

| id | 위치 | 종류 | 입력 신호 → 변경 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| ARB-TABLE | arbitration/rules_table.py:RULE_TABLE/decide (우선순위 = 튜플 순서) | 보/보류 | 칸마다 증거(규칙·재판독·마스터·자가교정·정규화)로 tier 결정. 값 변경권은 여기뿐. 분기: 7-i(검증된 Docraft 교정) · 7-a/7-b(자가교정) · 10-n(정규화 채택) · 10-a/b/c/d(마스터 채움·후보) · 10-f(범위 밖) · 1/2(값 부재) · 10-g(swap)·10-e(N4·N5)·11(명칭 불일치: 값 유지+후보, unresolved)·10(코드 없음) · 3~6(재판독 없음/일치×규칙) · 7(재판독 불일치+1차 fail+재판독 pass→재판독 값 repaired) · 8(1차 pass+재판독 fail→1차 유지) · 9(근거 없음 unresolved) · 12(기본 unresolved) | G(필드명 무관, 서식 무관) | 필드 | 상태/값/계약 | 7: 재판독이 규칙을 우연히 통과시키면 틀린 값 채택. 10-n: 기본값 교정이 문서 표시와 다를 수 있음 |
| ARB-WARN | rules_table.py:rules_all_pass·_mark_warn_tolerated + config arbitration_warn_blocks_confirmation=False | 상태 | warn은 확정을 막지 않고 판정 번호에 `w` 접미 | G | 필드 | 상태(확실성) | warn 처리 기준 고객 협의 대상 |
| ARB-Q | arbitrator.py:decide_field | 보류 | ①' Docraft 전체 재추출 값의 근거(quality_accepted)가 불충분하면 값은 보존하고 unresolved(분기 번호 Q) | G | 필드 | 상태/근거 | |
| ARB-ROLLUP | domain/tier.py:rollup·arbitrator.summarize·table_tier | 상태 | 표→문서→트랜잭션 최악값. 검증한 칸만 집계(미검증 pass 제외), out_of_scope 건너뜀, 빈 입력은 None | G | 표/문서/묶음 | 상태 | 검증 필드 0건이면 등급 None |
| ARB-DOCSIG | arbitrator.py:_apply_document_code_signal | 보류 | 미지 서식·입통원 미확정 → 문서 unresolved(+근거 경로 review_paths) | G | 문서 | 상태/관계 | |
| ARB-APPLY | emit/assembler.py:_apply_final·build_field_harness (`apply_tiers`: repaired·swap·inferred) | 보 | 해당 tier의 final_value를 출력 `value`로 반영, 원값은 `harness.ao_value`. 나머지는 `value` 불변 | G | 필드 | 값 | 하류가 `value`를 적재하므로 교정이 원장에 닿음 |
| OUT-CONTRACT | emit/schema.py:validate_output·assert_input_preserved | 탐 | 출력 JSON 스키마 + 입력 구조 보존(추가는 `harness`뿐) 증명 | G | 문서/묶음 | 계약 | |
| REVIEW-PATHS | arbitrator.summarize·domain/tier.py:REVIEW_TIERS(ambiguous·unresolved) | 보류 | review_paths·review_reasons를 문서 채널에 | G | 필드/문서 | 상태 | |
| JOB-STATUS | domain/tier.py:JobStatus·pipeline/document_unit.py | 상태 | rejected(입력 계약 위반)/failed/completed 전이, 재시도 정책 | G | 문서/묶음 | 상태/계약 | |

## F. 재판독·Docraft·자가교정 (reread/, selfcorrect/, pipeline/runner.py)

| id | 위치 | 종류 | 입력 신호 → 변경 | 일반성 | 단위 | 연산 | 부작용 위험 |
|---|---|---|---|---|---|---|---|
| RR-SELECT | reread/selection.py:select_targets (config reread_mode, `reread_confidence_threshold` 0.90) | 탐(대상 선정) | selective: 규칙 fail/warn·신뢰도<0.90 또는 없음·규칙 severity high·값 종류 금액/코드/날짜. 비대상은 `skipped`(일치로 안 침). 기본 `RE_READ_ADAPTER=docraft`면 ③은 off, ④'만 호출 | R(설정)+H(값 종류 집합, 명칭 키 정규식) | 필드 | 상태(확실성) | 신뢰도 없는 필드는 전부 대상 |
| RR-COMPARE | reread/compare.py:compare_field·compare_document+domain/normalize.values_equal | 탐 | 정규화 후 동치 → matched/mismatched, 어댑터 불가·미대상·재판독에 값 없음 → unavailable/skipped(반대 증거로 안 침). 명칭은 유사도 | G(값 종류별 정규화) | 필드/행 | 오독 | |
| RR-ALIGN | reread/align.py:align_table·resolve_key_columns | 보(정합) | 표 행을 키 열((EDI코드,시작일자) 세부내역서·(항목) 영수증·병명코드, 설정 override)로 맞춤, 느슨한 2차 정합. 한쪽에만 있는 행 → mismatched(비 Docraft) 또는 unavailable+`row_alignment` 기록(Docraft). 표 단위 review로 올린다고 문서에 적혀 있으나 코드는 증거·건수 기록까지 | R(override)+H(문서코드별 키 열) | 행/표 | 위치/누락/순서 | 같은 키의 중복 행 정합 모호 |
| RR-DOCRAFT | reread/docraft.py:DocraftClient·read_targets·split_specs·merge_results | 보(재판독) | ④' 검토 등급 문서의 검토 필드(+합계 관계 경로+검토 행 전체+열 밀림 열)를 Docraft `/api/read`로 재판독, 필드·표 요청 분리 | H(Docraft 키 이름, `INFERRED_SUMS`·`SCHEMA_DATE_ALIASES`·`EXCLUSIVE_CHECKBOX_GROUPS` 서식별 표) | 필드/표/행 | 누락/오독/위치 | 다중 페이지·미지원 서식은 호출 안 함. 지연 20~180초 |
| RR-QUALITY | reread/quality.py:quality_accepted | 탐(근거 검증) | Docraft 근거: bbox·page·원문(source_text)·typed proof(date_equivalent·checkbox_mark·table_blank·labelled_amount·derived_sum·aligned_amount·schema_alias…)와 provenance 일치, issue_codes 없음, 값↔정규화값 일치. 요양기관종류 체크박스 예외 | H(proof 종류 표, 요양기관종류) | 값/필드 | 계약(근거)/상태 | 근거가 불완전한 Docraft 값은 7-i에서 배제 |
| RR-DROPSHARED | docraft.py:_drop_shared_evidence | 탐/보 | 서로 다른 칸이 같은 값 줄(IoU≥0.9)에서 같은 값/원문을 읽었으면 근거 폐기(한 값이 두 칸 근거일 수 없음) | G | 필드 | 중복/위치 | |
| RR-7I | runner:_verified_docraft_corrections·_rearbitrate → 분기 7-i | 보 | Docraft 교정(CORRECTED) 중 ① 등록 합계 묶음(derived_sum, INFERRED_SUMS 5종: 영수증 진료비총액·납부한금액_합계, 세부내역서 급여총액, 약제비영수증 2종)이 근거·합 일치하고 문서 규칙 새 fail 없음 ② 표 빈칸(table_blank) 0→빈 값, 두 경우만 채택 | H(INFERRED_SUMS 서식·필드 표) | 필드/행 | 오독/누락/추가 | 등록 밖 필드는 해당 없음 |
| RR-JOINT | runner:_joint_row_rules·_revalidator | 탐(재검증) | 행 공동 재검증: 재판독이 다르게 읽은 행 칸 전부를 바꿔 규칙 재실행, 새 fail 없고 바꾼 칸의 규칙 하나 이상이 pass로 바뀔 때만 인정 | G | 행 | 위치(열 밀림) | |
| RR-COLCONF | runner:_shifted_columns·_shifted_reads (column_confirmed) | 탐+보 | 열 밀림 교정(`confirm`) 칸의 열 전체를 Docraft로 읽어 열 공동 재검증 → 7-i | H(영수증 열 밀림) | 열 | 위치 | |
| RR-MATCHCONF | runner:_rearbitrate | 상태 | 재판독이 같은 값이면 1차 신뢰도는 확인된 것 — 신뢰도를 비운 사본의 규칙에 fail 없으면 그 증거로 판정(분기 5) | G | 필드 | 상태(확실성) | 같은 모델 계통의 같은 오독 |
| SC-LOOP | selfcorrect/loop.py·region.py·reread/region_reader.py (분기 7-a/7-b) | 탐+보 | CALC_* fail만 트리거: 금액 영역 crop 재추출 ≤3회(문서당 호출 10), 합계 일치 시 7-a repaired, 아니면 7-b unresolved. **재판독이 Docraft이거나 재추출기·이미지 없으면 안 돎**(사유를 증거에) | R(설정)+H(CALC 규칙 id 접두) | 필드/표 | 오독 | 좌표 없는 API 응답은 페이지 전체 재추출(체계적 오독 재현) |
| RR-MISSROWS | runner:_missing_rows_filter | 탐 | 빠진 필수 행(COV-R2)만 이유면 Docraft에 그 항목 행만 요청 | H(영수증 `항목내역`) | 행 | 누락 | |

## G. 임계값·상수 요약

| 값 | 위치 | 용도 |
|---|---|---|
| 0.90 | config.reread_confidence_threshold | 재판독 대상(저신뢰) |
| 0.9 | value_fix `_DEPARTMENT_CONFIDENCE` | 진료과 오독 교정 허용 신뢰도 상한 |
| 0.7 | builtins `_INSTITUTION_LOW_CONFIDENCE` | 요양기관종류 의심 |
| 0.97 | shared yaml min_extract_ratio | 추출 누락(룰 1) |
| 30배·상위 3개 | shared yaml parser_outlier_ratio·parser_trim_top | parse 오류 거름 |
| 100원 | rules/tolerance floor, builtins AMOUNT_TOLERANCE | 금액 대조 |
| 0.85 / 0.2 / 0.75 / 0.2 | config master_name_similarity_threshold / master_edi_name_similarity_threshold / master_kcd_name_embedding_threshold / master_edi_name_embedding_threshold | KCD·EDI 명칭 판정 |
| 0.5 / 1e-6 | kcd_pairing MIN_PAIR_SCORE / MIN_GAIN | 재배치 |
| ≥1.0 / ≥0.5 | R-KCD-REVERSE | 코드 추정 / 후보 |
| 3회 / 10호출 | config self_correction_max_rounds/calls | 자가교정 |
| 0.05 | value_fix `_RATIO_SPREAD` | 공단부담금 열 이동 부담률 편차 |
| 6칸·20후보 | value_fix `_SHIFT_CELLS`·`_SHIFT_CANDIDATES` | 칸 일부 밀림 조합 상한 |

---

## 결론 1. 메커니즘이 하나도 없는 단위 × 연산 조합

(표시 기준: 서식·필드 일반 메커니즘이 없고, 있어도 위 표의 특정 서식·열 한정 보정 1~2개뿐인 조합은 "사실상 없음"에 따로 적음)

**완전 없음**
- 문자 × 중복(OCR 반복 문자), 문자 × 순서(숫자 전치·자릿수 바뀜), 문자 × 경계(공백으로 갈린 한 글자·숫자) — 합계식 fail로만 간접 탐지, 문자 단위 보정 없음(예외: N-LETTERO·KCD N5·소수점 복원은 특정 필드 한정).
- 값 × 근거 없는 추가(AO가 만든 환각 값이 쪽 위에 없음): AO 값이 이미지에 인쇄돼 있는지 확인하는 일반 메커니즘 없음(N-UNPRTOT·N-UNPRBEN·N-SUMCNT 특정 항목 한정, Docraft 값만 근거 검증).
- 필드 × 순서(날짜 선후: 입원≤퇴원, 진단≤발급, 시작≤종료): 규칙 없음.
- 필드 × 계약(값제약) 일반: 날짜 유효성(실재하지 않는 날짜 플래그), 금액 숫자성(`is_number` 내장은 있으나 동봉 규칙 yaml이 부르지 않음), 사업자등록번호·주민번호·전화·면허번호 형식/체크섬, 음수 금액 — 없음. 형식 검사는 KCD·DRG·Y/N뿐.
- 필드 × 중복(같은 값이 다른 필드에도 복제: 환자명=병원명 등): 없음(parse 금액 중복·Docraft 근거 공유만).
- 행 × 중복(같은 EDI·시작일자·금액의 중복 행, 영수증 같은 항목 두 번): 보정·탐지 없음(KCD 중복 코드 warn만 병명 표 한정, parse 보충은 중복 코드 행을 "채우지 않음"으로 회피).
- 행 × 순서(세부내역서 시작일자·섹션 순서, 행 뒤섞임): 없음(KCD pairing은 병명 표 코드↔명칭 짝 한정).
- 열 × 순서, 열 × 중복(세부내역서 일반 열 복제는 원내코드 한 가지), 열 × 근거 없는 추가/경계(열 합침·분리)·머리글 오인식(AO headers 자체 검증): 없음(headers_absent는 로그만).
- 표 × 중복(같은 표 두 번 추출), 표 × 경계(쪽을 넘는 표의 합침·분리), 표 × 위치(표↔필드 오배정, 표가 다른 표 키로), 표 × 순서: 없음. 표 × 누락은 COV-R1 첫 칸 한정(표 키 존재 여부).
- 쪽 × 전 연산(누락 쪽·중복 쪽·쪽 순서·쪽 경계·회전·쪽별 일관성): 하네스 메커니즘 없음. 존재하는 것은 잘림(crop_detected, UI 입력의 합계 영역 한정)·다중 페이지 Docraft 호출 생략·parse 전 쪽 글자 조회(N-UNPRTOT) 뿐.
- 문서 × 중복(한 트랜잭션 안 같은 문서 2번), 문서 × 경계(한 파일에 문서 2개·한 문서가 2파일), 문서 × 순서: 없음(해시 멱등은 배치 재접수 한정).
- 묶음 × 관계(문서 간 일관성: 영수증↔세부내역서 총액·기간, 진단서↔영수증 병원·환자·진단일), 묶음 × 누락(짝 서식 부재), 묶음 × 중복·경계·순서·값 교차 검증: 없음.
- 상태(판독불가·가림·마스킹: `masked_value`/`redact_applied` 활용), 상태(서식 구버전/신버전)의 일반 탐지: 판독불가 전용 메커니즘 없음. 서식 버전은 영수증 `급여/비급여` 두 형태 판별(ENG-SPLIT·N-UNCCOL)과 세부내역서 열 인쇄 여부 한정.
- 값 × 순서, 값 × 경계 일반(한 칸에 두 값 합침)은 병명 코드(MS-KCDSPLIT)·병명(N-DXNAMES)·EDI 이중 코드(E2)·원내/EDI 코드 줄바꿈(N-WRAPCODE) 한정. 주소·연락처·기관명 합침/분리 없음.

**사실상 없음(특정 서식·필드 하드코딩 1개뿐)**
- 열 × 위치 오배정: 영수증 금액 열(N-SWAP·N-COLSHIFT·N-MOVEPUB·N-BEN2UNC·N-UNCCOL)과 세부내역서 요약 행 밀림 한정. 세부내역서 항목 행 열 맞바꿈은 R-0710-PARTITION이 탐지만(`offset_with`), 보정 없음.
- 필드 × 위치 오배정: 병실↔진료과, DRG, 요양기관종류, 진료과 한정.
- 행 × 누락: 영수증 표준 항목 행(ROW-RECOVER·COV-R2)과 병명 표(N-DXNAMES) 한정. 세부내역서 행 누락은 PARTITION 합계 불일치로만 탐지.
- 문서 × 관계(문맥 상속·머리글): 진단서 사고발생일자 산출, 주민번호↔성별·생년월일 한정.
- 값 × 순서/관계: 날짜·기간 상호 관계는 사고발생일자 산출뿐.

## 결론 2. 하드코딩되어 새 서식·필드에는 동작하지 않을 메커니즘

서식명·필드명·열 이름·라벨 문자열·서식별 표가 코드 상수이거나 규칙 yaml이 문서코드에 묶여 있어, 새 서식(또는 이름이 바뀐 필드)에는 자동으로 적용되지 않는 것.

1. 정규화 단계 전체(value_fix.py `_STAGES`): 유형 키가 `세부내역서·진료비세부산정내역서`, `진단서·소견서·입원확인서·입퇴원확인서·수술확인서`, `진료비영수증` 셋뿐이고 각 함수가 열·키 이름(`항목`·`EDI명칭`·`원내코드`·`환자정보(병실)`·`환자정보-질병군(DRG)번호`·`환자정보-진료과`·`합계`·`급여_본인부담총액`·`병명`·`병명코드`·`최종진단`·`임상적추정`·`사고발생일자`·`본인부담금`·`공단부담금`·`선택진료료외`·`비급여`·`급여` 등)을 직접 쓴다. 약제영수증(0730)·신규 서식에는 `_dates` 외 정규화 없음. 해당 항목: N-SECTION, N-WARD, N-DECIMAL, N-SUMSHIFT, N-ADJROW, N-SUBGAP, N-UNPRTOT, N-TOTUNC, N-UNPRBEN, N-SUMCNT, N-DOSE, N-WRAPCODE, N-COPYCODE, N-LETTERO, N-CNTPRICE, N-PRTBEN, N-CLASS, N-DXLABEL, N-DXNAMES, N-CHECKS, N-ACCIDENT, N-ITEMNAME(항목명 데이터는 yaml이나 키 `항목` 고정), N-DEPT, N-SWAP(쌍은 yaml, 열 목록은 `ITEM_COLUMNS` 상수), N-COLSHIFT, N-MOVEPUB, N-BEN2UNC, N-UNCCOL, N-DRG, N-INST.
2. 날짜 판별: domain/normalize.py `_DATE_KEY_RE` 등 키 이름 정규식(일자·일$·날짜·초진일…)에 맞는 키만 N-DATE 대상. 금액·코드·횟수 종류 추정(`_MONEY_KEY_RE` 등)도 같은 방식 — 재판독 대상 선정(HIGH_IMPORTANCE_KINDS)과 비교 정규화가 이 추정에 의존.
3. 규칙 yaml(rulesets/*.yaml): `document_codes`로 서식에 묶임(진단서 4종·AC029·0710/0720). 규칙식이 열·그룹·필드 이름을 직접 참조(`tables[항목내역]`, `groups[금액산정]`, `급여_본인부담총액`…). 약제영수증(0730)은 규칙 파일 없음 → 합계·논리 검증 전무. 새 서식은 yaml 추가가 필요(엔진은 일반이나 규칙 데이터가 서식별).
4. 마스터 대조 쌍(pipeline/master_evidence.py `DEFAULT_PAIRS`): 문서코드 0710·0720·0730·0120·1333·0130·1250에 대해 (표 키, 코드 열, 명칭 열)을 코드 상수로 선언. 이 밖의 서식·열은 마스터 증거 없음.
5. 영수증 합계 구조 판별(builtins uses_split_columns·grouped_amount·split_amount·header_total·split_total, strategies resolve_ac029_strategy): 영수증의 `급여`/`비급여`/`선택진료료`/`선택진료료외` 열 이름, right_summary/bottom_table 영역 정의에 고정.
6. 행 종류 라벨(builtins TOTAL_ROW_LABELS·SUBTOTAL_ROW_LABELS·ADJUSTMENT_ROW_MARKERS·LUMP_ITEMS·`_ROW_LABEL_HEADERS`·summary_label): 한글 라벨 상수. 새 표기·언어 변형은 합계 행으로 인식되지 않음.
7. 추출 누락 검증(coverage.py+shared yaml): `required_keys`·`required_items`·`required_cells`는 yaml이라 데이터 파라미터화이지만 문서 종류 키(진단서·소견서·입원확인서·수술확인서·진료비영수증·세부내역서·약제영수증)만 존재. `required_items`는 영수증만. recover_rows·drop_section_rows·expected_cells의 행 종류 판별은 영수증/세부내역서 한정. 새 서식은 yaml에 항목을 추가해야 하고 recover/expected 로직은 영수증·세부내역서 가정.
8. parse 보충(parser_fill.py `_SPECS`·`_CODE_HEADERS`·`_detail_alias`·`_PREFIX`): 영수증(표준 항목명 열쇠)·세부내역서(코드 열쇠)와 열 이름 별칭 표가 하드코딩. 진단서·약제영수증 표는 대상 아님.
9. KCD 관련: R-KCD-AXIS(KCD-8 보조세분류 4종 코드군 표 상수), MS-KCDREPAIR(`KCD_HEAD_FIX` 숫자→영문 표, 최대 길이 6), 접미 규칙, 동의어 사전(kcd_synonyms.yaml은 데이터), N-DXNAMES — KCD 체계·병명내역 표 한정.
10. EDI 관련: code_class(코드 형태 `EDI_CODE_SHAPES`, 9자리 약품코드, 치료재료 사례 품목명, 급여구분 해석 표기), MASTER_0710_11 요양기관종류→단가 컬럼 매핑(yaml이나 문서 필드 `의료기관정보-요양기관종류`·표 `단가` 고정).
11. 서식 재분류(reclassify/title.py): 제목 정규식 7종·스키마 계열 표·별칭 표가 코드 상수 → 새 서식 제목은 분류 못 함(미인식 시 AO 분류 유지).
12. 문서코드 매핑(doc_code.py DEFAULT_DOC_TYPE_MAPPINGS): 데이터이지만 초기 시드는 코드 상수(운영은 DB 주입 설계), 세부내역서 입·통원 파생은 `환자정보(입통원구분)` 필드 고정.
13. Docraft 연동(reread/docraft.py): `INFERRED_SUMS`·`SCHEMA_DATE_ALIASES`·`EXCLUSIVE_CHECKBOX_GROUPS`·`INFERENCE_LABELS` 서식·필드별 표, `config.docraft_doc_types` 서식 목록; quality.py `_TYPED` proof 종류 표; reread/align.py 문서코드별 키 열; 요양기관종류 예외(`_institution_checkbox`). 등록 밖 서식·필드는 7-i·합계 근거 채택 대상이 아님.
14. 요양기관종류 일관성(FMT_AC029_INSTITUTION·builtins:institution_type_ok): 영수증 `의료기관정보-명칭`·`요양기관종류` 필드와 명칭 문자열(`병원`/`의원` 접미)에 고정.
15. 자가교정 트리거(selfcorrect/loop.py:is_self_correction_trigger): 규칙 id 접두 `CALC`·카테고리 CALC에만 반응 — CALC 규칙이 없는 서식은 트리거 없음(그리고 Docraft 재판독 구성이면 아예 비활성).

**완전 일반(서식 무관)인 것**: ARB-TABLE·ARB-ROLLUP·ARB-APPLY(필드명 무관), 규칙 엔진·식 평가기·허용오차·스키마 기동 검증(ENG-CORE), 재판독 비교·정합 일반부(RR-COMPARE·RR-JOINT·RR-DROPSHARED), 접수 계약·해시 멱등, 출력 계약 검증. 단 이들이 소비하는 증거(규칙·정규화·마스터)가 서식 한정이므로 실효 범위는 위 하드코딩에 종속된다.
