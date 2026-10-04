# 보고: schema-declarations (2026-10-04)

브랜치 `feat/schema-declarations`(dev 3d79d0e 기준), 워크트리 `harness-v2/.worktrees/schema-declarations`, 커밋 `01c37fe`. dev 병합·push·AWS 호출 없음.

## 근본 원인·문제 유형
- 판단 엔진(규칙 엔진·식 평가기)은 일반인데 판단 기준(필드 종류, 날짜 선후, 합계 관계, 출력 금지 형식)은 서식별 yaml 규칙 또는 코드 상수라, 규칙이 없는 서식(약제영수증 0730)은 검증이 전무하고 날짜 실재·번호 형식·음수 금액·가림 검사는 어떤 서식에도 없었다.
- 유형: "서식 지식이 코드·서식별 규칙에 흩어져 있어, 선언만으로 일반 검사를 돌릴 수 없음"(M5 계약 제약, M8 출력 금지 값).

## 설계
- 선언 `src/mlife_harness/rulesets/shared/schema.yaml`(로더 하나: `rules/schema.py::load_declarations`, 형식 오류는 RuleSpecError로 기동 실패). 문서 종류 키는 receipt_items.yaml 의 required_keys 와 같은 하네스 표기, `*`는 공통.
  - 항목: fields{kind(date/amount/int/code/text), pattern, check(bizno/rrn), values, non_negative, private(출력에 나와도 되는 가림 형식), required, synonyms}, date_order 쌍, sums{total, parts}.
  - 실제로 채운 것: 주민번호(`*`: rrn 체크섬 + private), 날짜 선후 쌍(정답지 654건에서 위반 0~8건인 것만), 영수증·약제 사업자번호(bizno), 약제영수증 날짜·금액(음수 금지)·합계 2개. required·synonyms 는 형식만 정의(로더가 받기만 함; 현재 필수 키는 required_keys).
  - receipt_items.yaml 확장 대신 shared/ 에 파일을 하나 둔 이유: 그 파일은 Docraft 와 바이트 동일(설치 번들이 cmp 확인)이라 확장하면 두 저장소·번들 동시 수정이 필요하다. Docraft 가 같은 선언을 읽게 될 때 같은 방식으로 복사하면 된다.
- 검사 `rulesets/schema_checks.yaml`(전 문서 공통 3규칙, builtin `schema_value`·`schema_relation`·`schema_private`, 위반은 warn). 기존 규칙 엔진·`RuleEvidence`(pass/warn/fail)·builtin 디스패치를 그대로 쓰고 증거 context 에 `node_id`·`paths`를 담는다.
  - E.CON.RANGE.2: 실재하지 않는 날짜(선언 없이도 키로 날짜로 추정한 칸, 쉼표 나열 포함, 연도 0000 은 날짜 없음), 코드 형식·체크섬(선언된 칸만, 가린 값·미인쇄 값은 제외), 음수 금액(선언된 칸만).
  - E.CON.SCHEMA.2: 선언된 date/amount/int 에 숫자·날짜가 아닌 값(`is_number` 활용 — 기존에 안 쓰이던 내장 술어).
  - E.CON.RANGE.1: 선언한 허용 목록 밖(로직만, 채운 선언 없음).
  - E.CON.RANGE.3: 날짜 선후(문서 전역 + 표 행마다, 표 행은 위반만), 선언된 합계. yaml 규칙이 이미 보는 합계(ac029·0710)는 선언하지 않아 중복 없음.
  - E.CON.PRIV.1·.2: private 형식이 아니면 노출(가림 표시 없음)·형식 위반(가림 표시 있으나 선언과 다름). 값은 증거 문구에 싣지 않고 값은 바꾸지 않는다.
- 선언 없을 때: 키 이름으로 날짜로 추정한 칸의 실재 여부만 본다(테스트로 고정).
- 탐지 전용: 증거는 기본적으로 칸에 붙이지 않고 문서 증거로만 남겨 판정·재판독 선정(warn/fail 칸 대상)에 영향이 없다. 설정 `SCHEMA_CHECKS_JUDGE=true`(`RuleEngine.schema_judges`)면 읽은 칸에 붙인다(README 설정표 추가). 위반 없는 칸은 증거를 만들지 않고(표 한 장에 수백 건 방지), 선후·합계만 pass 도 남긴다.
- 흡수한 기존 장치: 없음(기존 `FMT_AC029_DRG`·`R-CERT-SEX/BIRTH` 등은 건드리지 않음). 약제영수증 규칙은 별도 yaml 대신 선언 sums 로 둬서 새 규칙 파일·함수를 늘리지 않았다.

## 변경 파일
- 신규: `rules/schema.py`, `rulesets/schema_checks.yaml`, `rulesets/shared/schema.yaml`, `tests/unit/test_schema_declarations.py`
- 수정: `rules/engine.py`(builtin 3개 + `schema_judges`), `rules/spec.py`(builtin 이름), `config.py`·`cli/run_batch.py`(설정 전달), `README.md`(설정표), 규칙 개수를 세던 테스트 3개(`test_rules_spec`·`test_rules_engine`·`test_detail_empty_inout`: 공통 규칙셋 1개 추가 반영, 약제 "규칙 없음" 테스트를 "스키마 검사만 돎"으로 교체)

## 테스트
- 신규 60개(통과): 로더 거부 3, 날짜(실재·부분·빈값·비날짜 텍스트·키로 추정 못 하는 칸·선언된 date), 금액(쉼표·원·0·음수·비숫자, 음수 허용 칸), 사업자번호·주민번호 체크섬(맞음/틀림/자릿수/가림/외국인/선언 없음), 패턴·허용 목록, 공개 규칙(노출·가림·형식 위반·선언 없음), 엔진 통합(정상 약제 영수증 경고 없음, 위반 7종, 빈 칸 건너뜀, 기본 칸 미부착·값 불변, 선언 없는 서식, 진단서 노출, 세부내역서 표 행 위반만).
- `uv run pytest tests/unit -q`: 17 failed(기존과 동일한 샘플 JSON·수술확인서·입퇴원확인서 17건), 1975 passed. 새 실패 없음.

## 로컬 측정 (외부 호출 0건, AO 환경변수 없음, 캐시 재생)
1. r9 59건: 결과 `exp/e2e_call_test/out/replay-r9-schema-declarations`, 채점 `...-grade`. 정확도 97.405%(14191/14569) 그대로, 셀별 grade.json 59개 모두 dev 와 동일, 출력 값·등급·review_paths 동일. 새 warn/fail 0건, pass 증거만 54건(날짜 선후). 정탐 0·오탐 0. 미탐: 틀린 날짜·금액 칸 389(234 날짜류)는 빈칸 채택·공란 문제이고 형식 위반이 아니라 이 검사 대상이 아님.
2. 오탐 측정(정상 값): 정답지 654건(datasets/*/golden)에 적용 — 날짜 실재 위반 0, 약제 합계 위반 3건(2문서: 약제비영수증_1_0 은 총액이 비급여를 제외하고 인쇄, 병원정보_약제비총액은 12원 차이 인쇄 불일치), 사업자번호 체크섬 위반 6(진료비영수증), 주민번호 체크섬 위반 15(전부 합성 문서 "신한life_test" 수술확인서), 주민번호 노출 PRIV.1 78·형식 PRIV.2 3(정책 미정, 노출은 정답지가 원문 주민번호를 그대로 적는 문서).
3. 표본 205건(AO 원값 vs 정답지, 외부 호출 없음, 결과 `out/replay-sd-all`, 증거 `scratchpad/cap-all.jsonl`, 스크립트 `replay_capture.py`·`analyze.py`):
   - RANGE.3 합계: 정탐 3(AO 가 비급여 칸을 틀리게 읽은 2문서·3증거) / 오탐 2(위 12원 차이 문서의 두 합계; 정답지도 그 값).
   - RANGE.2 번호: 정탐 3(사업자번호 1, 주민번호 2: AO 오독) / 오탐 14(합성 문서 주민번호 13 + 1).
   - 날짜 실재(RANGE.2 날짜)·SCHEMA.2·RANGE.1: 이 데이터에서 발동 0 — 단위 테스트로만 확인됨.
   - PRIV: 노출 65·형식 위반 3 탐지(정답과 일치 여부는 의미 없음. 정책 결정 대상).
   - 번호류 틀린 칸 28 중 14 탐지, 14 미탐(가려진 값·자릿수 부족 등 체크섬을 못 보는 경우).

## 약제비영수증(0730)
- 정답지 38건(datasets/약제비영수증_테스트셋/golden)으로 확인: 총액 = 급여본인부담 + 공단부담액 + 비급여및전액본인부담금(36/38 일치), 환자부담총액 = 급여본인부담 + 비급여및전액본인부담금(전액본인부담이 찍힌 서류는 비급여및전액본인부담금에 포함되어 합계에서 제외). 불일치 2문서는 인쇄 자체가 불일치하므로 fail 이 아니라 warn 으로 둠(요구한 "정상 문서를 fail 시키지 않음" 충족). 소득공제대상액-수납금액 합계는 0 인 서류가 있어 선언하지 않음.

## 부작용 위험·남은 일
- 증거 건수가 늘어난다: 문서당 pass 1~3건(`rule_results_summary` pass/total 증가), 위반 시 warn. DB 기록에도 문서 증거로 들어간다. warn 은 `w` 판정 번호 표시에는 영향이 없다(칸에 안 붙음).
- `SCHEMA_CHECKS_JUDGE=true` 로 켜면 warn 칸이 재판독 대상이 된다(주민번호 PRIV·합성 문서 체크섬이 오탐으로 칸에 붙음). 켜기 전에 PRIV 정책·체크섬 대상 정리 필요.
- 주민번호 체크섬은 2020-10 이후 발급 번호가 무작위라 실문서에서 오탐 가능(정답지 실문서 진단서·입퇴원확인서는 전부 통과).
- 규칙 버전은 chart 일치 테스트 때문에 `2026.09.22`로 맞췄다(배포 시 RULE_SET_VERSION 과 함께 올릴 때 schema_checks.yaml 도 같이).
- 남은 일: Docraft 에 shared/schema.yaml 사본·같은 선언 읽기, required·synonyms 를 required_keys·동의어 표에서 이전, 날짜류 검사의 실발동 데이터 확보, 소견서·진단서 날짜 선후 쌍 보강, wiki(상위·하네스) 기록·README 규칙 개수 문구·docs/harness-sample-output 갱신(이 세션에서는 하지 않음).
