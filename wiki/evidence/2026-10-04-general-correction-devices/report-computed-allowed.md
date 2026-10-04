# computed-allowed 보고
- 브랜치 feat/computed-allowed, 커밋 6a89f17 (dev 5e5775e 기준, 병합·push 안 함). 워크트리 harness-v2/.worktrees/computed-allowed
## 근본 원인 / 유형
원문 대조(M1)가 "계산으로 채워도 되는 칸"이라는 서식 정책을 모른 채 GEN.2 를 모두 의심으로 표시. 유형: 정책이 선언 데이터에 없어 탐지 장치가 허용 칸과 비허용 칸을 구분하지 못함.
## 설계
- schema.yaml 필드 선언에 `computed: allowed` 추가(머리 주석 갱신). 로더(rules/schema.py `_field`)가 검증(allowed 외 값은 RuleSpecError), `FieldDecl.computed_allowed`.
- grounding.py: `schema_for(doc).fields[node.key]` 선언을 읽어, 분류가 GEN.2 이고 허용 선언이면 status `computed`(node GEN.2 유지, value 기록)로 두고 flags 에서 제외. GEN.1·HOLD.1·DUP.2 는 선언과 무관하게 기존대로. 코드에 필드명 없음.
- 선언: `세부내역서.fields.급여_급여총액: {kind: amount, computed: allowed}`.
- schema_checks.yaml 은 같은 개념이 필요 없어 변경 없음. 흡수한 기존 장치 없음.
## 주의: 사용자 지시와 실제 위치 차이
r9 의 GEN.2 오탐은 진료비영수증이 아니라 **세부내역서(진료비세부산정내역서)의 groups[합계]** 칸이다(영수증 30건에는 GEN.2 표시 0건). 그래서 선언은 `세부내역서` 아래에 뒀다. 영수증 합계 칸에도 허용을 적용하려면 같은 선언을 `진료비영수증.fields`에 추가하면 된다(영수증 쪽 키는 이번 r9에서 GEN.2 가 없어 확인 불가). 급여_본인부담총액·급여_공단부담총액·급여_전액본인부담총액은 합이 아니라 인쇄 부분값이라 선언하지 않았다(급여_전액본인부담총액이 GEN.2 로 한 건 잡혔으나 정탐, 정답 0).
## 변경 파일
normalizer/grounding.py, rules/schema.py, rulesets/shared/schema.yaml, tests/unit/test_grounding.py, tests/unit/test_schema_declarations.py
## 테스트
추가: 허용 칸 계산값→computed·flags 비움 / 같은 칸 설명 안 되는 값→GEN.1 absent / 같은 칸 인쇄된 값→grounded / 선언 없는 칸 계산값→GEN.2 absent / 로더 형식(allowed 성공, 기본 False, 잘못된 값 오류).
`pytest tests/unit -q`: 17 failed(기존과 동일), 2066 passed. 대상 두 파일 92 passed.
## r9 59건 재생(캐시, 외부 호출 0)
- 기준선: dev 5e5775e 를 같은 명령으로 재생(out/replay-r9-computed-base; 기존 replay-r9-dev 는 grounding 기록이 없어 쓸 수 없었음). 결과 out/replay-r9-computed-allowed, 채점 *-grade.
- 정확도 동일(셀 일치 13953/14580 양쪽, 전체 97.4%), 하네스 json 외 값 필드 차이 0건.
- GEN.2 정탐/오탐: 전 5/12 → 후 3/1. 의심 표시에서 빠진 것: 오탐 11건 + 정탐 2건(급여_급여총액 정답 0인데 계산값 출력한 2건: 20230104_123952.jpg 181447, 급여액_2303314628.jpg 209838). 그 둘은 미탐으로 바뀜(미탐 437→439). 허용 정책상 이 칸의 계산값 자체는 의심 대상이 아니라는 결정의 귀결.
- 다른 노드(GEN.1 4/18, DUP.2 73/87, HOLD.1 8/9)는 불변.
- 남은 GEN.2: 비급여총액(정탐), 항목내역 총액 오탐 1건, 항목내역 급여 정탐 1건, 급여_전액본인부담총액 정탐 1건.
## 위험
허용 칸에서 AO 가 계산값을 틀리게 낸 경우(정답 0 인 2건)는 더 이상 표시되지 않는다. 합계 불일치는 다른 규칙(detail_0710.yaml 항등식)이 본다. 선언 키는 칸 이름 기준이라 서식이 달라도 같은 이름이면 같은 서식 스키마 안에서만 적용(문서 종류별 선언).
