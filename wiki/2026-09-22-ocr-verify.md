---
type: Implementation Log
title: "Agentic OCR 2.0 결과 교차검증·자동 교정 API 구현"
description: "이미지 1장과 AO 응답 JSON을 받아 Docraft가 독립 Parse→twin reader 이식 룰→Extract 한 결과와 필드별로 비교하고, 어긋난 값만 LLM-as-Judge로 판정해 교정 JSON을 돌려주는 POST /api/verify의 설계·구현·평가 기록"
tags: [backend, agentic-ocr, rule-base, llm-judge, api, verify, evaluation]
generated: {by: claude-code/claude-fable-5.1 (오케스트레이션) + claude-opus/sonnet (구현·탐색), at: 2026-09-22}
status: stable
---

# Agentic OCR 2.0 결과 교차검증·자동 교정 API 구현

2026-09-22 · 브랜치 `feat/ocr-verify` · 워크트리 `.worktrees/ocr-verify`

[계획 문서](2026-09-22-ocr-verify-plan.md)의 구현 기록이다. 계획의 미결 사항 3건은 다음과 같이 확정하고 진행했다.

| 미결 | 결정 |
|---|---|
| 정답셋 | 0917 채점표 xlsx는 ○/△/× 기호와 메모뿐이고 원본 이미지도 없어 정답값으로 쓸 수 없다. AO 예시 4건(gold)과 `data/files/*_samples` 유형별 8장(silver)을 VLM으로 라벨링한 뒤 이미지 대조로 검수해 정답셋으로 삼았다. [ocr-verify-labels](2026-09-22-ocr-verify-labels.md) 참고 |
| 범위 | 4종(진단서·소견서·진료비영수증·세부내역서) 우선. 수술확인서·입퇴원확인서·약제비영수증은 `doctypes`에 정의를 추가하면 같은 경로로 동작한다 |
| 입력 단위 | 이미지 1장(TIF 포함). 다중 페이지 TIF·PDF는 422로 거절한다 |

## 1. 파이프라인

```
POST /api/verify  (multipart: image, ao_result, [doc_type])
  ① verify.document(ao)      AO 응답에서 문서 하나 고르기 (API 형식 documents[0] / UI 형식 result 모두 수용)
  ② parsers.parse(paddle)    이미지 → 블록 (기존 경로 재사용, TIF 포함)
  ③ engine.extract(schema)   doctypes.schema(doc_type)로 LLM 추출 (기존 경로 재사용)
  ④ rules.apply              twin reader 이식 룰: 정규화·라벨 보충·파생·합계행 처리
  ⑤ rules.check / correct    진료비영수증 항목내역 이상 검출과 확실한 것만 룰 교정
  ⑥ 필드별 비교(rules.same)  일치 → agree (LLM 호출 없음)
  ⑦ verify.judge             불일치·이상 필드만 이미지 + 두 값 + 필드 정의(desc) + 힌트로 1회 LLM 호출
  ⑧ 응답 조립                입력 AO JSON 구조 그대로 + value 교정 + 판정 정보
```

### 모듈

| 파일 | 역할 | 줄 |
|---|---|---|
| `backend/doctypes.py` | 유형별 필드·표 정의(데이터 테이블). AO `key`를 그대로 쓰고 그룹은 최상위로 평탄화. `schema(doc_type)`는 `engine.extract`용 JSON Schema, `kind()`는 값 정규화·비교 방식 | 221 |
| `backend/rules.py` | twin reader 플러그인에서 이식한 정규화(`normalize`)·비교(`same`)·후처리(`apply`)와 진료비영수증 표 검사(`check`)·교정(`correct`) | 565 |
| `backend/verify.py` | AO 응답 평탄화(`flatten`), Judge 호출(`judge`), 파이프라인(`run`) | 282 |
| `backend/main.py` | `POST /api/verify` 라우트(인증·확장자 415·JSON 422·다중 페이지 422·실패 502) | +40 |
| `scripts/verify_label.py` | VLM 정답셋 라벨링(추출 모델과 다른 모델을 OpenRouter 목록에서 고름) | 319 |
| `scripts/verify_eval.py` | 라벨셋 기준 단계별(raw/rules/ao/final) 필드 정확도 평가 | 500 |
| `tests/test_rules.py`, `tests/test_verify.py` | 순수 함수·monkeypatch 기반 테스트 | 959 |

### 정규 표현(canonical dict)

스칼라는 AO `key` 그대로 최상위 키, 표는 표 key → 행 dict 목록이다. AO 응답과 Docraft 추출 결과, 라벨 파일이 모두 이 형태로 비교된다.

```json
{"진단일": "20230228", "이름": "홍길동", "병명내역": [{"병명코드": "R634", "병명": "(주상병) 이상체중감소"}]}
```

## 2. twin reader 룰 이식 (계획 A)

twin reader 플러그인(`refs/postprocess_schema_example/20260828_v1.1/plugin/미래에셋생명_고도화/`)을 분석한 결과, 진단서_5종 플러그인 5개는 공백·주석 차이만 있는 같은 코드이고 날짜 정규화·유틸도 세 폴더에 복제돼 있었다. 원본은 자체 OCR 셀 그래프(arrtcd, relativeLabelsInfo)에 묶여 있어 그대로 옮길 수 없으므로, 이식 가치가 있는 부분만 **유형별 룰 테이블(데이터) + 공통 엔진(코드)** 구조로 다시 썼다.

| 이식한 룰 | 구현 |
|---|---|
| 날짜 → `YYYYMMDD` | 4자리/2자리 연도·구분자·`\d{8}`·`\d{6}` 분기, 2자리 연도 ≥50→19xx, 실제 달력(윤일) 검증 |
| 복수 날짜(통원일) | 문자열 안의 날짜를 모두 모아 `", "`로 결합, 비교는 집합 |
| 금액 OCR 교정 | `I l | / →1, O o ㅇ 이→0, B→8, b→6`, 콤마·원 제거, 선행 0 제거 |
| 수량 | `,→.`, `N x M` 곱셈, 정수면 소수점 제거 |
| 주민번호·성별·생년월일 | 앞 6자리 뒤 하이픈, 마스킹 `*` 보존, 뒷자리 첫 숫자로 성별·세기 유도 |
| 전화 | FAX 이후 절단, 숫자·하이픈만 |
| 병명코드 | `[A-Z][0-9]{2,5}` 단위 분리, 앞자리 0→D·1→I 교정, 점 제거(AO 표기), 병명 텍스트에서 코드 잔재 제거 |
| 이름·의사명·병원명·주소 | 면허번호·직함어 제거, 좌우 대칭 중복 접기, `의과의원→외과의원`, `주소:` 뒤만 |
| 체크박스·외래/입원 | `[V]`·✓ → "Y", 입원→"01", 외래→"02"(원본 JS의 3항 체이닝 버그를 명시적 분기로 교정) |
| 합계행 | 항목이 합계/계/총계/끝수처리 행은 표에서 빼고 비어 있는 합계 필드를 채움. 진료비영수증은 AO 스키마가 합계 행을 표에 두므로 남김 |
| 사고발생일자 | 진료시작일 우선, 없으면 진단일·수술일·검사일·치료일 중 최소 |
| 라벨 보충 | 필드별 라벨 동의어 57개(twin reader `keywordInfo` + 서식 실물 라벨)로 표의 라벨 셀 오른쪽·텍스트의 `라벨: 값`·OCR 줄에서 빠진 값을 찾음 |

이식하지 않은 것: OCR 셀 그래프 방향 탐색(`AreaSearch`, `relativeLabelsInfo`), 소견문 구조화 LLM 호출(`llm/plugin_llm_*.js`, 진단서_5종만 사용), 엑셀 출력, 라벨 오탈자 사전 수백 종(대표 라벨만 채택), 합계 필드 "0" 강제 채움(AO는 빈 값 유지).

## 3. LLM-as-Judge (계획 C)

- 일치 필드는 LLM에 보내지 않는다. 불일치·한쪽 누락·이상 검출 필드만 모아 **문서당 1회** 호출한다(`engine._provider`·`_user`·`_page_images` 재사용, `json_object`).
- 프롬프트에는 각 필드의 `desc`(doctypes 정의)와 `hint`(룰 검사 결과)를 함께 싣는다. 실측에서 Judge가 세부내역서 `환자정보(입통원구분)`에 환자구분 값 "건강보험"을 넣는 오해가 있어 desc를 추가했다.
- Judge가 "AO 표기를 따르라"는 지시를 무시하고 `R63.4`·`2022/05/17`처럼 형식만 다른 값을 `corrected`로 내는 문제가 있었다. 판정값을 `rules.apply`에 통과시켜 정규화한 뒤 AO·Docraft 값과 다시 비교해 형식 차이는 `ao`/`docraft`로 재분류하고, Judge가 끼워 넣은 합계·끝수처리 행도 같은 경로로 제거한다.

## 4. AO 키·값 누락 대응

AO 응답에서 key·value가 빠지는 경우를 모두 다룬다.

| 누락 | 처리 |
|---|---|
| `value` 없음·null·빈 문자열·`not_extracted: true` | None으로 보고 Docraft 값과 비교(불일치면 Judge) |
| 원소 `key` 없음 | `display_label`로 대체, 그래도 없으면 `source: "unknown"`으로 표시하고 판정 제외 |
| 표 셀 `key` 없음 | `headers`의 같은 열 위치로 보충 |
| doctypes에 정의된 필드·표가 AO에 아예 없음 | Docraft 값으로 원소를 새로 만들어 추가(`added: true`), Docraft 값이 있으면 Judge 확인 |

응답의 `documents[0].verify.counts`에 `agree, ao, docraft, corrected, unknown, added`를 센다. UI 응답 형식(`result.fields/tables/groups`, `doc_type`이 null이면 `doc_type` 파라미터 필수)도 같은 코드로 받는다.

## 5. 진료비영수증 항목내역 오류 검출·자동 교정

harness-v2 요구사항의 오류 케이스 3건(`harness-v2/docs/requirements/[진료비영수증]*`)과 합계 검증 요건(`하네스_검증_요건정리.md` 1절)을 `rules.check`로 옮겼다.

| 코드 | 검출 | 교정 |
|---|---|---|
| `no_column` | Docraft 파싱 머리글에 독립 `급여`(또는 `비급여`) 열이 없는데 AO 값이 0이 아님 | Docraft의 같은 행 값과 맞으면 열을 옮김(급여→비급여), 아니면 Judge 힌트 |
| `multi_amount` | 셀 하나에 금액 둘 이상(행 병합) | Judge 힌트 |
| `row_copy` | 합계 행이 바로 위 항목 행을 통째로 베낌 | Judge 힌트 |
| `sum_mismatch` | 진료비총액·환자부담총액·공단부담총액 합계식과 합계행 vs 항목행 열별 합(십의 자리 절사 허용) | Judge 힌트 |
| `row_missing`/`row_extra` | 항목명 정규화(AO 프롬프트 규칙: 입원료 1인실→입원료_1인실 등) 후 한쪽에만 있는 행 | 금액이 전부 빈 누락 행은 Docraft에서 바로 추가, 나머지는 Judge |

케이스 실측 결과(이미지 1장당 108~142초):

| 케이스 | 결과 |
|---|---|
| 비급여→급여 오추출 | `no_column` 2행·`row_copy`·`sum_mismatch` 검출. 룰이 정액수가·합계 행의 급여 9,010,000을 비급여로 옮기고 Judge가 확인. 환자부담총액 불일치 해소 |
| 파싱 에러(셀 병합) | AO 최종 표가 합계식을 만족해 검출 없음. Judge가 이미지를 보고 표는 AO를 택하고 납부 금액 스칼라 4건을 교정 |
| 항목명 누락 | AO에 `tables`가 비어 있어 `항목내역`을 추가(`added: true`)하고 Docraft 25행으로 채움. 금액이 빈 CT·PET·초음파·보철교정료 행 포함. 단 이 케이스 폴더의 JSON(논현정형외과)과 이미지(순천중앙병원)가 서로 다른 문서라 원 작성자 확인 필요 |

## 6. 정답셋과 평가 (계획 B)

정답셋 구성과 검수 과정은 [ocr-verify-labels](2026-09-22-ocr-verify-labels.md)에 있다. 평가는 `scripts/verify_eval.py`로 단계별 필드 정확도를 계산한다.

- `raw`: `engine.extract` 결과, `rules`: `rules.apply` 적용 후, `ao`: AO 값(gold만), `final`: `verify.run` 최종값(gold만).
- 정확도 = 라벨이 값을 가진 필드 중 `rules.same`이 참인 수 / 라벨이 값을 가진 필드 수. 표는 식별 열(항목·EDI코드·병명코드·날짜)로 행을 짝지어 셀 단위로 센다.

### 룰 확장 전후 (gold 4 + silver 32, 필드 정확도·오탐)

| 유형 | raw | rules(확장 전) | rules(확장 후) |
|---|---|---|---|
| 진단서 | 82.0% (109/133) fp=6 | 83.5% (111/133) fp=55 | **88.0% (117/133) fp=14** |
| 소견서 | 80.7% (117/145) fp=8 | 82.8% (120/145) fp=39 | **81.4% (118/145) fp=12** |
| 진료비영수증 | 84.2% (875/1039) fp=47 | 85.7% (890/1039) fp=71 | **84.4% (877/1039) fp=51** |
| 세부내역서 | 91.4% (1982/2169) fp=178 | 94.5% (1844/1951) fp=298 | **98.0% (2126/2169) fp=56** |
| 전체 | 88.4% (3083/3486) fp=239 | 90.7% (2965/3268) fp=463 | **92.9% (3238/3486) fp=133** |

- "확장 전" 열은 라벨 관례 정합 이전 분모(3268)라 직접 비교는 raw↔확장 후로 본다. 세부내역서 분모가 1951→2169로 늘어난 것은 라벨의 급여·종료일자 칸이 AO 관례(급여구분×총액, 종료일자=시작일자)로 채워져 채점 대상이 됐기 때문이다.
- 소견서·진료비영수증 raw가 2pp 내려간 것은 텍스트 포함 판정 최소 길이를 2→4자로 올려 `주사료` vs `주사료_행위료`를 더는 같다고 보지 않아서다.
- 룰 확장에서 크게 잡힌 필드: 세부내역서 `급여`(실패 245→8), `원내코드`(260→rules 0), `EDI코드`(142→rules 1/149), 진단서 `성별`(9→0, 주민번호가 없을 때 성별이 항상 "남"이 되던 버그), 소견서 `이름`(9→0).
- 룰로 못 잡는 최대 실패: 진료비영수증 `항목내역.항목`(240) — 추출 모델이 금액이 빈 행을 통째로 버린다(24~29행 중 3~18행만 추출). Judge 단계에서 AO 행으로 보완된다.

### gold 4건 전 단계 (AO 응답이 있는 문서)

| 유형 | raw | rules | ao | final |
|---|---|---|---|---|
| 진단서 | 64.0% (16/25) | 88.0% (22/25) | 100% (25/25) fp=1 | **100% (25/25) fp=1** |
| 소견서 | 70.0% (7/10) | 70.0% (7/10) | 90.0% (9/10) | **90.0% (9/10)** |
| 진료비영수증 | 54.0% (27/50) | 54.0% (27/50) fp=1 | 98.0% (49/50) fp=6 | **98.0% (49/50) fp=3** |
| 세부내역서 | 91.6% (230/251) fp=16 | 98.0% (246/251) fp=0 | 92.4% (232/251) | **98.8% (248/251) fp=1** |

final은 모든 유형에서 AO 이상이고 오탐은 AO보다 적다. 세부내역서에서 AO가 틀린 16셀은 `항목` 열에 EDI명칭을 넣는 AO 관례 차이이며 Judge가 Docraft 값(인쇄된 구분명)을 택했다. 진료비영수증 final의 유일한 오답은 OCR 오타(`전험및혈액성분제제료`)다. 결과 JSON: `data/verify/eval-20260922-164129.json`(36건), `eval-20260922-164613.json`(gold 전 단계).

## 7. 실측 관찰과 남은 한계

- **TIF**: `data/files` 샘플의 TIF는 LZW RGB·Group3/4 이진·JPEG 압축·JPEG 데이터에 `.tif` 확장자만 붙은 파일이 섞여 있다. 모두 단일 페이지이며 PaddleOCR 경로에서 그대로 파싱됐다.
- **처리 시간**: 이미지 1장에 진단서·소견서 30~40초, 진료비영수증 90~140초, 세부내역서 약 180초. 표가 클수록 표 교정(`TABLE_REFINE`)과 Judge 응답이 길어진다.
- **Docraft 추출의 라벨 텍스트 값**: LLM 추출이 빈 칸의 라벨("병실", "질병군(DRG)번호", "성별", ":")을 값으로 내는 경우가 있어 룰에서 라벨 동의어와 같은 값은 None으로 지운다.
- **Judge 한계**: 문서에 `진단 연월일` 칸이 비어 있는데 AO가 발급일을 진단일로 넣은 경우 Judge도 AO 손을 들었다. 정답셋은 문서 그대로 null로 뒀다. `row_copy`는 요양병원처럼 정액수가 한 행이 곧 합계인 문서에서 오탐이 남는다.
- **text 비교**: `rules.same`은 텍스트의 접두·구두점 차이("(주상병)이상체중감소" vs "이상체중감소")를 포함 관계로 흡수한다. 짧은 값에서 과하게 관대해지지 않도록 최소 길이를 둔다.
- **범위 밖**: 다중 페이지 문서, 세부내역서 행별 총액 검증(요건 2절), harness-v2 연동(룰 검증 실패 건만 호출), 나머지 3종 유형.

## 8. 검증

- `pytest -q`: 245 passed (기존 94 + rules 111 + verify 40)
- 실제 provider(OpenRouter Qwen3-VL-32B)·로컬 PaddleOCR로 gold 4건과 오류 케이스 3건 end-to-end 실행.
