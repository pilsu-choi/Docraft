# source-grounding 보고 (M1 원문 대조)

브랜치 `feat/source-grounding`, 워크트리 `harness-v2/.worktrees/source-grounding`, 커밋 `50b8688` (기반 dev `3d79d0e`). dev 병합·push·AWS 호출 없음.

## 근본 원인·문제 유형
- 근본 원인: AO 가 낸 값이 원문에 인쇄돼 있는지 확인하는 일반 장치가 없다. 합계 라벨·급여 열·건수처럼 서식 한정 장치(`_unprinted_totals` 등)만 있었다.
- 유형: "출력값과 근거 원문의 대조 부재" — 원문에 없는 값(E.OVR.GEN.1), 계산값(GEN.2), 추측 확정(E.WRG.HOLD.1), 다른 칸 복제(E.OVR.DUP.2).

## 설계
- `normalizer/grounding.py` `ground_document(doc, texts, low_confidence)` → `field_path → {status, value?, node?, cells?, reason?}`, `grounding_record` → `{counts, flags}`.
- 값 모양으로 비교: 수(쉼표·원·전각·소수, 인쇄된 `-`=0), 날짜(`2023-03-11`·`2023년 3월 11일`·`20230311`·연도 없는 `05.21`은 다른 날짜에 연도가 있을 때), 나머지는 공백·전각 제거 부분 문자열, 이름 조각(`입원료_1인실`), 배열은 원소별. 필드명·열 이름·서식 코드는 쓰지 않는다.
- 판정: grounded / absent(GEN.1·GEN.2·HOLD.1) / elsewhere(DUP.2, `cells`=같은 행의 짝) / unknown(parse 없음·한 글자·`zero`·`label`·`standard`).
- 읽는 선언: 표준 항목명(`receipt_items.yaml` `receipt_item_names`)과 입통원 구분 값(`INPATIENT_OUTPATIENT_DERIVATION`)은 추출기가 붙이는 어휘라 원문에 없어도 `unknown(standard)`.
- 연결: runner 에서 정규화 앞(AO 값 그대로)에 호출, 결과는 `harness.parser.documents[].grounding`(스키마 추가). parse 를 받는 비동기 경로에서만 동작한다. 값·판정 상태는 바꾸지 않는다. 판정 반영 플래그는 만들지 않음(원문 대조 정밀도가 오른 뒤 결정).
- 한계: parse 글자는 문서 단위 문단 목록이라 쪽·bbox 단위 대조는 못 한다(`AoParseClient.tables` 가 쪽 구분 없이 평탄화).

## 변경 파일
`src/mlife_harness/normalizer/grounding.py`(신규), `pipeline/runner.py`, `emit/schema.py`, `tests/unit/test_grounding.py`(신규 27건), `tests/unit/test_coverage_rules.py`(parser 기록 단언에 grounding 키 반영).

## 흡수 검토
- N-UNPRTOT(`_unprinted_totals`): r9 59건에서 이 장치가 합계 0 으로 바꾼 11칸 중 8칸을 `absent`(GEN.1·GEN.2·HOLD.1)로 잡았다. 놓친 3칸(비급여총액 80000·20000·10000)은 항목 행 금액이 원문에 있어 값 대조로는 '있음'이다 — 라벨 부재라는 문서 단위 근거는 값 대조로 대체되지 않는다. 일부 흡수 가능, 이번엔 기존 장치 유지(값 변경 동작 불변).
- N-UNPRBEN(`_unprinted_benefit`, 열 인쇄 여부)·N-SUMCNT(`_summary_counts`)는 열 머리글·요약 행 0 인쇄 근거라 값 대조(칸 단위)와 근거 종류가 달라 흡수 못 함. 값 `0`은 원문 부재가 정보가 없어 `unknown(zero)`로 둔다.
- `_copied_codes`(원내코드=EDI코드 열 복제)는 DUP.2 와 같은 현상이지만 표 단위 인쇄 열 근거 포함이라 유지. 이 장치의 `elsewhere`가 같은 쌍을 의심 표시한다.

## 테스트
- `tests/unit/test_grounding.py` 27건 통과: 표기 변형 11종(쉼표·전각·날짜 3형식·짧은 날짜·공백·대시 0·이름 조각·배열), 연도 없는 날짜, 없는 값 4종, HOLD.1, unknown(parse 없음·빈 텍스트·한 글자·영), 빈 값 미판정, 반복 라벨, GEN.2(열 합), 행 내 복제, 양쪽 인쇄된 같은 값은 복제 아님, 다른 행·표 밖 같은 값은 스키마 중복, 단가=총액 수량 1 정의상 같음(수량 2면 의심), 한 자리 수 제외, 기록 형식.
- `uv run pytest tests/unit -q`: 1942 통과, 17 실패(기존과 동일: 수술확인서·입퇴원확인서 샘플). 새 실패 없음.

## 로컬 측정 (r9 59건 캐시 재생, 외부 호출 0)
- 정확도: 97.405%(14191/14569) 기준선과 같음. 59건 전 칸 값 동일.
- 기준: 의심 칸이 채점상 AO 오답이면 정탐, AO 정답이면 오탐. 미탐은 AO 오답(비어 있지 않은 값 436칸)인데 표시 못 한 칸(전체 노드 합산이며 대부분 열 밀림·0/빈칸·오독이라 이 장치의 대상이 아님). 측정 스크립트 scratchpad `measure_grounding.py`.

| 노드 | 정탐 | 오탐 | 비고 |
|---|---|---|---|
| E.OVR.GEN.1 | 4 | 18 | 오탐은 대부분 parse 글자에 없는 OCR 누락(`E7660`·`AU401{W-IC-EVA}` 등 코드·명칭), 합계 `급여총액` |
| E.OVR.GEN.2 | 5 | 12 | 오탐은 정답이 계산값을 허용한 합계(`급여_급여총액`=부담 합) — 정책 사항이라 표시용 |
| E.WRG.HOLD.1 | 8 | 9 | 신뢰도 0.9 미만 원문 없음. 정탐은 표준명 오독·`합계` 0 처리 칸 |
| E.OVR.DUP.2 | 73 | 87 | 쌍 단위로는 거의 전부 정탐(복제된 칸 + 원본 칸이 함께 표시) |

- 개선 경과: 초기 GEN.1 오탐 638 → 표준 항목명·입통원·반복 라벨·0 표기 제외·이름 조각·짧은 날짜로 18. DUP.2 오탐 567 → 같은 행 안 복제만 보도록 제한해 87(필드·그룹·표 사이 같은 값은 스키마가 한 값을 여러 칸에 싣는 것). 정의상 같은 값(단가=총액 수량 1)은 곱 관계로 제외.
- DUP.2 오탐 87의 구성: 짝의 원본 칸 71(항목·EDI명칭 30, 시작·종료일자 24, EDI코드·원내코드 17 등 — 어느 쪽이 복사인지는 값만으로 못 정함), 정의상 같은 값 `총액`=`비급여` 10, `소계` 행 항목=EDI명칭 6.
- 정탐 사례: 종료일자=시작일자 복제 24, 원내코드=EDI코드 복제 17, 항목=EDI명칭 30, 인쇄되지 않은 합계 8.

## 부작용 위험
- 탐지만 하고 값·등급을 바꾸지 않아 산출 값 위험 없음. 산출 JSON 크기가 늘어난다(DUP.2 `cells` 목록이 긴 칸 있음 — 필요하면 상한).
- parse 글자가 OCR 오류로 값을 빠뜨리면 `absent`가 정답을 의심한다(GEN.1 오탐 원인 대부분). 판정 반영 시 이미지 재판독(Docraft) 증거와 같이 써야 한다.
- 수 값이 부분 문자열로 우연히 맞는 경우(`12290` ⊂ `112290`)는 `grounded`로 새어 미탐이 된다.

## 남은 일
1. DUP.2 짝에서 복사본 한 칸 고르기: parse 표의 열 머리글 위치와 AO 열 매핑(`printed_columns` 재사용)으로 값이 인쇄된 열을 알아내면 정밀도가 절반에서 올라간다.
2. 쪽 단위 대조(parse 쪽 구분 보존)와 bbox 주변 대조(AO 근거 bbox 가 입력에 있을 때).
3. 판정 반영 플래그(기본 꺼짐) — `absent`·`elsewhere`를 검토 대상으로 올릴지, Docraft 재판독 대상 선정에 쓸지 결정.
4. GEN.2 허용 여부 정책 결정(계산 합계 허용 시 GEN.2 는 정보용으로만).
5. 서식별 어휘(표준 요양기관종류 등) 선언을 yaml 한 곳으로 모으기.
