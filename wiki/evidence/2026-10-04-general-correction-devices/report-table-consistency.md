# table-consistency 보고 (2026-10-04)

브랜치 `feat/table-consistency` (harness-v2 dev 3d79d0e 기준), 워크트리 `harness-v2/.worktrees/table-consistency`, 커밋 `0a4bf85`. dev 병합·push·AWS 호출 없음.

## 근본 원인과 문제 유형
- 근본 원인: 열 밀림·맞바뀜 보정(N-COLSHIFT·N-SWAP·N-MOVEPUB·N-BEN2UNC·N-UNCCOL)이 영수증 금액 열·세부내역서 요약 행의 열 이름에 묶여 있고, 구조 이상(StructAnomaly)은 로그만 남기며, 행 중복·행 종류 이상을 보는 장치가 없다. "표 안 값 모양이 열과 어긋나는지"를 서식과 무관하게 보는 층이 없었다.
- 문제 유형: 표의 열·행 규칙성(값 모양, 행 단위 경계)에서 벗어난 칸을 서식 지식 없이 찾는 탐지 부재(M3 구조 일관성, M7 행 단위 중복).

## 설계
- 새 모듈 `src/mlife_harness/normalizer/consistency.py`(260줄). 진입점 `table_consistency(doc, htmls, anomalies, blocks)` → `[(RuleEvidence, 붙일 칸 경로)]`.
- 읽는 선언: 칸이 이미 가진 `value_kind`(기존 `infer_kind`)뿐. 새 yaml·열 이름·라벨 문자열 없음. 선언이 없으면 값 모양 추정만 동작한다(열 이름이 평범하면 `column_swap`만 빠지고 나머지는 그대로).
- 값 모양 5종: date·num(정수·금액·소수)·code·text·blank. 열의 주된 모양은 값 있는 칸의 70% 이상, 칸이 4개 이상일 때만 정한다. 정의상 빈칸이 많은 열은 빈칸을 보지 않고 값 있는 칸만 본다. 코드·이름 열은 자유 서식이라 `_ACCEPTS`로 서로 섞여도 이상이 아니다(첫 측정에서 EDI코드 열 오탐 21건 → 0건으로 줄인 개선).
- 증거: 기존 `RuleEvidence`(category STRUCT, 기본 `warn`), 기존 증거 경로(`evidence_by_path`, 문서 단위는 `document_evidence`)에 합침. 분류 ID는 `detail` 앞 `[E.WRG.ASSIGN.2]`로 출력에 나가고(출력 스키마 불변) `context.node`에도 있다. `table_consistency_blocks_confirmation=True`면 `fail`로 판정에 반영(기본 꺼짐).
- 패턴 → 노드: `column_outlier`(한 칸)·`row_shift`(행 내 k칸 밀림, 어긋난 칸 둘 이상이 같은 방향·폭 이웃 열 모양과 60% 이상 맞음, `context.shift` 부호=값이 제 열의 왼쪽(+)/오른쪽(-))·`column_swap`(열 종류 선언과 열 전체 모양 불일치)·`transposed`(열 순도 낮고 행 순도 높음, 표 첫 칸) → E.WRG.ASSIGN.2. `row_kind`(값 있는 칸 3개 이상, 절반 이상이 열 모양과 다름) → E.STR.GROUP.1. `array_length`(StructAnomaly 행 칸 수 이상을 같은 증거로 올림, 정규화로 행이 바뀐 낡은 이상은 건너뜀) → E.STR.ARRAY.1. `row_duplicate`(모든 값 같은 행, 값 있는 칸 3개 이상, parse 표에 그 행이 인쇄된 횟수 이상이면 정상 반복으로 제외, parse 없으면 `printed=None`) → E.OVR.DUP.1. `parse_boundary_repeat`(parse 표 끝 행이 다음 표 맨 앞 두 행 중 하나와 같음, 맞는 추출 행 칸에 남김) → P.OVR.DUP.1.
- StructAnomaly: 행 칸 수 이상 2종만 새 탐지 경로로 올렸다. 나머지 5종(헤더 없음·중복 키·비 dict·라벨 불일치)은 표 칸 증거로 옮길 대상이 아니라 그대로 로그만 남는다(범위 밖).
- 변경 파일: `normalizer/consistency.py`(신규), `pipeline/runner.py`(`_add_consistency` 한 곳, ③ 증거 수집 직후), `config.py`(플래그 1개), `tests/unit/test_table_consistency.py`(신규).
- 흡수한 기존 장치: 없음(동작 불변 지시). 비슷한 class·enum 신설 없음(`_Finding`은 내부 dataclass 하나).

## 기존 보정의 파라미터화 설계안 (이번엔 동작 불변)
- 공통 구조: N-SWAP·N-COLSHIFT·N-MOVEPUB·N-BEN2UNC·N-UNCCOL은 모두 (후보 열·칸 집합) → (합계 제약으로 확인) → (값 이동)이다. 후보를 고르는 앞단이 서식 한정이고 확인·이동은 제약에 의존한다.
- 1단계: 후보 선정을 새 장치로 바꾼다. `ITEM_COLUMNS` 상수·yaml `swaps` 쌍 대신 `value_kind`가 금액(MONEY)인 열 집합을 후보로 쓴다. 합계 행·요약 행 구분은 `row_kind`로 대체 가능한지 `excluded_row_reason`과 일치율부터 재본다.
- 2단계: 이동은 두 근거(값 모양 이상 + 열 합계 제약 일치)가 모두 맞을 때만(원칙 2). 숫자끼리 바뀐 금액 열은 모양이 같아 새 장치가 못 잡으므로 합계 제약을 계속 쓴다. 새 장치는 후보를 줄이고 "모양 이상이 이미 있음"을 확인 근거로 더하는 역할이다.
- 3단계: yaml에는 "열 종류 선언"과 "합계 관계"만 남기고 열 이름 상수를 지운다. 전제: 열 종류 선언이 지금은 `infer_kind` 정규식이라 규칙 yaml의 `kind`로 옮겨야 열 이름이 달라진 서식에서도 동작한다.
- 위험: 합계 제약이 약한 서식(약제비영수증 0730, 합계 행이 없는 서식)에서는 후보 단계만 일반화하고 이동은 막아 둔다.

## 테스트
`tests/unit/test_table_consistency.py` 32건 통과. 변형: 값 모양 14종 경계(날짜 형식·13월·쉼표 금액·음수·소수·코드·빈칸 표기), 정상 표 무반응, 빈칸 많은 열·자유 서식 코드 열 무반응(장치가 건드리면 안 되는 정상), 행 4개 이하 무판단, 한 칸 이상, 행 밀림 k=±1·±2 방향·폭, 숫자끼리 맞바뀜 미주장, 행 종류, 열 맞바뀜(선언 있음/없음), 전치, 중복(parse 없음/두 번 인쇄=정상/한 번 인쇄=의심), 값 3칸 미만 중복 제외, 쪽 경계 반복, StructAnomaly 승격과 낡은 이상 건너뜀, fail 플래그, 파이프라인 통합(값 불변·증거 부착).
전체 `uv run pytest tests/unit -q`: 1947 통과, 17 실패(기존 17건과 동일, 새 실패 없음).

## 로컬 측정 (외부 호출 0건, parse 캐시 59건 전부 사용)
- 정확도: 97.405% (14191/14569) 로 dev `15b172a` 기준선과 동일. 칸 값·문서 tier 전부 같고, 판정번호만 1칸 `w` 접미(경고 증거가 붙은 통과 칸)가 달라졌다.
- r9 실제 결과(하네스 출력 표 칸 13.4천): 표시 1칸(E.WRG.ASSIGN.2 column_outlier) → 정탐 1·오탐 0. 오답 표 칸 332(누락 47·불일치 15·오검출 270) 중 미탐 331. AO 원본 입력 기준(AO 오답 531) 도 표시 1·정탐 1·미탐 530.
- 미탐이 많은 이유(원인 분해): 오검출 270은 정답이 빈칸인데 값이 있는 칸으로 223칸이 종료일자(정책·복사값)이고 모양 오류가 아니다. 누락 47은 값이 비어 모양이 없다. 불일치 15는 소수·숫자 열 맞바뀜 등 숫자끼리다. 즉 r9 59건에는 모양이 다른 구조 오류가 거의 없어 노드별 정탐·미탐을 실데이터만으로 잴 수 없다(E.STR.GROUP.1·E.STR.ARRAY.1·E.OVR.DUP.1·P.OVR.DUP.1·전치 표시 0건, 해당 오답도 0건).
- 오탐: 정답지 59건 표 칸 10,492개에 0.02%(2칸, column_outlier)만 표시. 요약 행(합계·소계)은 열 모양과 맞아 오탐이 없었다. 처음 설계(code와 num을 구분)는 EDI코드 열에서 오탐 21건이라 코드·이름 열 허용 규칙으로 고쳤다.
- 합성 변형 재현율(정답지 59건 표에 변형 주입, 시드 고정, 스크립트 scratchpad `synth_tc.py`): 칸 맞바뀜(모양 다른 두 칸) 98%(171/174), 행 1칸 밀림 오른쪽 100%·왼쪽 99%, 2칸 밀림 99~100%, 날짜↔금액 열 맞바뀜 96%(27/28), 행 중복(parse 미확인) 100%(116/116). 단 `row_shift`로 이름 붙인 비율은 1칸 밀림 49%, 2칸 밀림 34~44%로 절반 이하다. 나머지는 어긋난 칸이 하나뿐이거나 이웃 열이 희소해 `column_outlier`·`row_kind`로 표시된다(칸은 표시됨, 패턴 이름만 다름). 밀려도 모양이 같은 칸(숫자↔숫자)은 못 잡는다.
- 측정 스크립트(저장소 밖): scratchpad `run_tc.sh`, `measure_tc.py`, `measure_ao.py`, `synth_tc.py`, `dup_tc.py`. 결과: out/replay-r9-table-consistency, out/replay-r9-table-consistency-grade.

## 부작용 위험
- 경고 증거가 붙은 칸이 새로 "검증됨"(`is_verified`)이 되어 문서 요약의 검증 필드 수와 산출 채널 부착이 늘 수 있다. 등급은 pass가 가장 낮아 롤업은 나빠지지 않고, 통과 칸 판정번호에 `w`가 붙는다(r9에서 1칸). 필드 수 집계를 쓰는 하류가 있으면 확인 필요.
- 문서 요약 `rule_results_summary`의 warn·total 건수가 증거 수만큼 늘어난다.
- `row_duplicate`는 parse 표가 없으면(동기 경로) 정상 반복도 의심으로 올린다. parse 표 인쇄 횟수 대조는 값 문자열 포함 비교라 열 값이 아주 짧으면(0·1) 인쇄 횟수를 많이 세어 놓칠 수 있다(미탐 쪽 위험).
- `parse_boundary_repeat`는 parse에서 표 단위만 보므로 같은 쪽에 같은 표가 나뉘어 나와도 걸린다.
- `table_consistency_blocks_confirmation`을 켜기 전에 실제 오탐률(현재 0.02%)을 영수증·진단서 계열 등 더 큰 표본으로 재측정해야 한다.

## 남은 일
- 열 종류 선언을 규칙 yaml `kind`로 옮겨 `infer_kind` 정규식 의존을 없앤다(column_swap 일반성).
- 실제 구조 오류 표본 확보(label_viewer 205건·세부 200 골든)로 노드별 정탐·미탐 재측정. 특히 E.STR.GROUP.1·P.OVR.DUP.1은 실사례가 없다.
- 숫자 열끼리 맞바뀜은 열 합계 제약과 결합(위 설계안 2단계).
- 같은 행 두 칸 값 복사(종료일자=시작일자 등 E.OVR.DUP.2)는 M1·정책 영역이라 이번 범위 밖.
