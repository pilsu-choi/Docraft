---
okf_version: "0.2"
type: Analysis
title: "key-value 추출 정확도 개선 지점 검토"
description: "76건 rules 단계 오류 분포와 코드 검토를 대조해 정확도 개선 우선순위를 정리한다. 구현은 포함하지 않는다. harness-v2의 마스터·규칙·오류 사례 재사용 지점을 포함한다."
tags: [verify, rules, extraction, accuracy, evaluation, harness-v2]
status: draft
---

# key-value 추출 정확도 개선 지점 검토

2026-09-22 · 브랜치 `docs/kv-accuracy-review` · 워크트리 `.worktrees/kv-accuracy-review`

## 근거
기준 main `729f495`. `data/verify/eval-20260922-183140.json`(76건 rules 단계)의 필드별 오류와 `backend/engine.py`·`rules.py`·`verify.py` 코드 검토를 Sonnet 서브에이전트로 병렬 수행해 대조했다. 모델·OCR 재실행 없음.

## 오류 질량 (rules 단계, wrong/fp)
| 유형 | 필드 | 건수 | 주 원인 |
|---|---|---:|---|
| 진료비영수증 | 항목내역.항목 | 159 (125/34) | 행 매칭 실패, 라벨의 세분 항목명(입원료_1인실)과 룰의 단순화(입원료) 불일치 |
| 진료비영수증 | 급여·공단부담금·본인부담금 | 75 | 위 항목 오매칭의 연쇄 |
| 세부내역서 | EDI명칭 | 129 (128/1) | 1~2글자 OCR 오인식(모티리톤/모티리론) |
| 세부내역서 | 단가 | 79 (40/39) | 라벨이 비어 있는데 룰 파생으로 채움(fp) |
| 세부내역서 | 투여량 | 69 (44/25) | 열 밀림(단가·총액 값 유입) |
| 세부내역서 | 시작일자·횟수 | 50+ | 행 순서 뒤바뀜, raw→rules 회귀 4건 포함 |
| 진단서·소견서 | 병명 | 33 | 대부분 OCR 글자 오류, 일부 라벨 오류 |
| 진단서·소견서 | 주소·병원주소·진단일·의사명 | ~35 (대부분 fp) | `_fill` 라벨 오매핑, raw→rules 회귀 22건 중 18건이 이 유형 |

세부내역서는 기존 9건 98.0%가 신규 10건 74.9%로 떨어져 일반화 격차가 가장 크다. 영수증은 관용 비교 91.6% 대 strict 76.7%로 `rules.same`의 부분 포함·빈값=0 관용이 점수를 크게 부풀린다.

## 코드 검토에서 확인한 결함
1. `verify.judge`가 항상 1페이지 이미지만 첨부(`verify.py:145`). 다페이지 세부내역서의 2페이지 이후 분쟁은 근거 없이 판정.
2. 진료시작일·종료일이 같은 라벨 "진료기간"을 쓰고 `_date`가 첫 날짜만 취해 둘 다 시작일로 채워짐(`rules.py:64-79,170`).
3. `rules.same` 텍스트 부분 포함(4자 이상)이 AO·Docraft 합의 판정(`verify.py:244`)에 쓰여, 다른 값이 일치로 확정되고 Judge를 건너뜀.
4. `verify._rows_same`은 행 순서·개수 완전 일치 요구. 한 행만 어긋나도 표 전체를 Judge가 재작성.
5. `LABELS` 동의어 "성명"이 의사명·환자성명 등 4필드에 중복, `DISTINCT`는 주소·연락처만 방어(`rules.py:32-93`). `_fill`은 문서 전체에서 첫 후보 채택.
6. `_totals`가 소계 행을 무조건 제거하고, 모델이 채운 틀린 합계를 합계행 값으로 덮어쓰지 않음(`rules.py:410-424`).
7. `engine._page_chunks`가 표 블록 중간에서 청크를 나눌 수 있고, 청크 병합 중복 제거가 dict 완전 일치에만 의존(`engine.py:263-334`).
8. `VISION_MAX_IMAGES=4` 초과 페이지는 이미지 없이 "이미지를 보고 읽어라" 지침만 받음.
9. 청크 단위 재시도 없음. 한 청크 실패가 전체 무추출로 이어짐.
10. 급여/비급여 열, 환자 주소/병원 주소의 스키마 설명이 조건부 문장만 있고 위치·예시 힌트 없음(`doctypes.py`).

## 개선 우선순위
| 순서 | 변경 | 대상 오류 |
|---|---|---|
| 1 | 표 행 정렬을 키 열(항목명+EDI코드, 시작일자) 기준으로 바꾸고, 항목명 정규화 시 세분 항목(입원료_1인실 등)을 보존. `verify._rows_same`과 `verify_eval.pair_rows` 공통화 | 영수증 항목 159 + 연쇄 75, 세부내역서 행 뒤바뀜 |
| 2 | `_fill` 오탐 억제: 환자정보/의료기관 영역 제약, 이름류 상호배제, 동률·모호 후보는 미채움, 라벨 근거 없는 단가 파생 중단, 소견서 진단일 보충 제한 | fp ~75, 회귀 18건 |
| 3 | 코드 사전 교정: EDI코드→표준명칭, 상병코드→KCD 상병명 대조로 1~2글자 OCR 오류 교정. 코드 자체가 일치할 때만 적용 | EDI명칭 128, 병명 다수 |
| 4 | 비교·Judge 정밀화: `same` 부분 포함을 자유서술 필드로 한정, Judge에 분쟁 필드가 속한 페이지 이미지와 셀 크롭 전달, 표 블록은 청크 분리 금지 | agree_wrong, 다페이지 판정 |
| 5 | 진료기간 시작/종료 첫 날짜 버그, 소계 행 보존, 청크 재시도 등 확정 결함 수정 | 국소 오답 |
| 6 | 라벨 품질: 신규 40건 silver 중 판독 불가 문구·전화번호가 병명·명칭에 들어간 사례를 원문 검수. 라벨 관례(세분 항목명 유지 여부) 고정 | 측정 신뢰도 |

## harness-v2 참고 자산

형제 프로젝트 `harness-v2`(M-Life 후처리 검증 하네스, 규칙셋 2026.09.6, 33규칙)를 Sonnet 서브에이전트 둘로 조사했다. 저장소 전체에 Docraft 언급은 없어 두 프로젝트는 현재 독립적이며, 연동 인터페이스는 별도 설계가 필요하다.

### 개선 우선순위와의 대응
| 우선순위 | harness-v2 자산 | 활용 |
|---|---|---|
| 1 표 행 정렬 | `reread/align.py`: 세부내역서 `(EDI코드, 시작일자)`, 영수증 `(항목)` 키 열로 행 매칭 | 같은 키 정의를 `verify._rows_same`·`verify_eval.pair_rows`에 채택 |
| 2 오탐 억제 | Arbitration 원칙 "잘못된 자동 교정이 미검출보다 나쁘다". `repaired` 판정은 21분기 중 3개뿐 | `rules.correct`·`_fill` 자동 채움을 같은 보수 기준으로 제한 |
| 3 코드 사전 교정 | 마스터 4종(`docs/requirements/latest/`): KCD CSV 고유코드 21,299, 수가코드 xlsx 399,157행, 치료재료 48,099행, 약가 22,484행. `master/kcd_synonyms.yaml` 동의어 52쌍. 매칭 모듈 `master/kcd_name.py`(5단 판정), `master/kcd_fallback.py`(N4/N5·절단 폴백), `master/lookup.resolve_edi_code`(E1~E5), `master/similarity.py`(NameIdf, rapidfuzz) | 데이터는 그대로, 모듈은 Postgres 조회를 걷어내고 인메모리 적재로 이식. harness는 flag만 하므로 Docraft가 교정까지 할 때는 코드 정확 일치 + 명칭 유사도 조건을 둔다 |
| 4 산식 검사 확장 | `rulesets/detail_0710.yaml` ROWSUM(3후보 병행)·UNITMUL(단가×횟수×일수)·PARTITION(열 소계), `ac029.yaml` 10규칙, 금액은 백원 절사 비교 | `rules.check`를 세부내역서로 확장해 투여량·단가 열 밀림(148건)을 산식 위반으로 검출. 단가는 파생 채움 대신 마스터 단가 대조(`MASTER_0710_11`) |
| 영수증 급여/비급여 | `ac029.yaml` 머리글 주석과 `wiki/2026-09-18-영수증-급여-두-서식.md`: 급여·비급여가 값 칸인 서식과 하위 칸을 묶는 그룹 머리글인 서식 두 종류 | `rules._grouped`의 startswith 휴리스틱을 이 판별 규칙으로 정리 |

### 고객 보고 오류 사례 3건 (`docs/requirements/[진료비영수증]*`, 2026-09-21, 미해결)
| 사례 | 내용 | Docraft 관련 |
|---|---|---|
| 비급여_급여_오추출됨 | 급여 칸이 없는 서식에서 비급여 9,010,000이 급여로 들어감. 합계 행도 따라감 | 위 두 서식 판별과 직결 |
| 파싱_에러 | 진찰료 셀에 두 행 금액이 병합, 주사료~영상진단료 5항목이 한 셀 | Docraft `multi_amount` 검출 대상. 파싱 결과로 회귀 확인 |
| 항목명_누락 | 금액이 전부 빈 CT·PET·초음파·보철교정 항목명 누락 | 이번 영수증 빈 행 보존 룰의 검증 케이스 |
이미지·AO 프롬프트·추출 JSON이 동봉되어 있어 `data/verify` 회귀 사례로 추가할 수 있다.

### 스키마 정합 확인 사항
- 진단서·소견서에 `사고발생일자`가 없다. harness 스키마B(`docs/requirements/진단서_4종_키_추가/latest/`)는 진단일·검사일·수술일 최솟값으로 파생한다(`R-CERT-ACCIDENT`).
- `원내코드`: Docraft 설명은 EDI코드와 같으면 null, 고객 답변(질문사항_2차)은 수가코드를 원내코드에 넣어도 무해. 대조 필요.
- 영수증 `급여` 필드는 고객이 존치 요청. 0과 null은 하네스가 동일 취급.
- 수술확인서·입퇴원확인서·약제비영수증은 Docraft에 미정의.

### 데이터 한계
harness-v2 golden(`docs/golden/baseline.json`)의 사람 정답 `truth`는 7건 모두 비어 있고, AO 응답은 유형당 1건(총 7건)이다. 새 정답셋은 얻을 수 없으며, 오히려 Docraft의 76건 라벨이 더 큰 자산이다. 재판독·자가교정은 VLM 미선정(`RE_READ_ADAPTER=unavailable`)으로 실측 없이 설계만 있다. harness §15 tier 분포는 정확도 지표가 아니다.

## 판단 기준
strict 정확도와 fp를 함께 보고한다. 점수를 올리려고 `same`을 느슨하게 바꾸지 않는다. 기존 36건은 개발용, 신규 40건은 검증용으로 유지한다.

## 관련 자료
- [룰 검증 성능 개선 우선순위](2026-09-22-rule-performance-review.md)
- [76건 평가 확장](2026-09-22-accuracy-eval-expansion.md)
- [룰 1차 전환 계획](2026-09-22-verify-rule-first-plan.md)
- harness-v2: `/home/pilsu/projects/mirae-assets/harness-v2` README §6·§7·§9, `src/mlife_harness/master/`, `src/mlife_harness/rulesets/`, `docs/requirements/`
