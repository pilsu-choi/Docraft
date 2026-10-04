# change-audit (M6 변경 감사) 보고

브랜치 feat/change-audit, 워크트리 harness-v2/.worktrees/change-audit, 커밋: 위 `git log` 1건 (dev 3d79d0e 기반). dev 병합·push·AWS 호출 없음.

## 근본 원인·문제 유형
값 변경이 정규화(NormalizationEvidence)·재판독(7·7-i)·마스터(10-a~e,g)·자가교정(7-a)으로 흩어져 있고, 출력에는 correction_basis(어느 장치)만 나간다. "근거가 문서 밖 독립 증거인가, 스스로 만든 값(산식·추론)뿐인가"가 기록되지도 막히지도 않는다. 유형: 근거 종류 없는 값 변경.

## 설계
- 값을 바꿀 권한은 Arbitration 한 곳뿐(ARB-TABLE)이고 정규화·parse 보충도 NormalizationEvidence -> 분기 10-n 으로 들어온다. 그래서 모든 변경 지점에 기록 호출을 흩지 않고 판정 결과에서 한 번에 뽑는다.
- 기존 구조 확장: NormalizationEvidence.basis, Decision.basis, FieldOutcome.basis(frozenset[BasisKind]), DocumentTrace.changes(list[ChangeRecord]). 새 enum 은 BasisKind 하나(출력 계약의 CorrectionBasis·EnrichmentBasis 는 "어느 장치", BasisKind 는 "근거 종류"라 축이 다름. 계약 enum 은 건드리지 않음).
- 공통 기록 함수: arbitration.change_records(DocumentOutcome) -> [ChangeRecord(field_path, stage, rule, before, after, basis, detail)]. stage=normalize/reread/selfcorrect/master, rule=판정 분기 번호, detail=정규화 사유·마스터 메모. runner 가 ④' 뒤에 trace.changes 로 채운다. 고객 출력 계약 불변(assembler 변경 없음).
- 근거 분류(BasisKind: PRINTED·FORMULA·REREAD·MASTER·INFERRED): value_fix 40곳 중 FORMULA(합계·열 합 배치) 10개 함수, INFERRED(_unprinted_totals, _accident_date), MASTER(진단명·단가 횟수·진료과·항목명 표준화), REREAD(Docraft 분류열·급여구분) 표시, 나머지는 기본 PRINTED(표기·parse 글자). 분기 쪽: 10-n=정규화 basis(+재판독 MATCHED면 REREAD 추가), 7=라벨 거리 경고로 원문 근거 거부 시 FORMULA 아니면 REREAD, 7-i·7-a=REREAD, 10-a·b·e·g=MASTER, 10-c=INFERRED(R-KCD-REVERSE 점수).
- 가드: Settings.change_audit_guard(env CHANGE_AUDIT_GUARD, 기본 False). decide() 끝의 _guard_weak_basis: basis ⊆ {FORMULA, INFERRED} 이고 값이 AO 원본과 달라지면 원래 값 + unresolved, 제안값은 candidates, 판정 번호에 g 접미(10-ng, 10-cg, 7g). merge_fixes 는 뒤 단계의 약한 근거가 앞 단계 PRINTED 에 가려지지 않게 병합(_merged_basis).
- 선언 데이터/하드코딩: 문서 유형·필드명·라벨 문자열을 코드에 넣지 않음. 근거 종류는 단계 함수 단위 표시.

## 위험 장치 점검 (실제 코드 확인)
- ENRICH_KCD_05(rules/engine.py 1791)+10-a/b: 코드만 있고 명칭이 빈 칸에 원장 명칭(복수면 쉼표로 전부)을 채운다. 원문에 없는 값 맞음. 근거는 코드 정확 조회라 MASTER(참조 마스터)로 분류 -> 가드가 막지 않음(독립 근거). 막으려면 별도 방침 결정 필요(inferred 등급으로 이미 표시됨).
- R-KCD-REVERSE(10-c): 병명 점수 ≥1.0 단독 1위면 코드를 채움. 병명 유사도뿐이라 INFERRED -> 가드가 막음(10-cg, 후보로만).
- N-UNPRTOT: parse 글자에 합계 라벨이 없고 표에도 합계 행이 없으면 합계 그룹을 0으로. parse 글자가 일부만 있어도 "전 쪽 글자"로 취급해 라벨 누락 시 인쇄된 합계를 지움(코드 확인). INFERRED(인쇄 부재 추론) -> 가드가 막음. 단 로컬 r9 에서 2칸 모두 0 이 정답이라 막으면 악화.
- 분기 7: 재판독 불일치+1차 fail+재판독 값으로 규칙 통과면 채택. Docraft 원문 근거가 인정된 값은 규칙 재검증을 거치고(reread_rules), 원문 근거가 라벨 거리로만 거부된 값은 합계 맞음 하나가 근거 -> FORMULA 로 표시해 가드 대상. 재판독 엔진이 docraft 가 아니면(내부 VLM) 근거 없이 규칙 통과만으로도 채택되는 경로가 있음(REREAD 로 분류, 가드 비대상).
- 10-f: 값 변경이 아니라 등급 분류(OOS). EDI 계열은 미적중이 전부 범위 밖이고 마지막 분류 `원장 미적중`(코드 모양은 맞는데 원장에 없음)이 오독 코드를 분모에서 숨길 수 있음. 공통 가드(값 변경 근거)와 축이 달라 이번 범위에서 구현하지 않음. 남은 일: `원장 미적중`·`명칭 미적중`을 별도 집계/표시(탐지)하는 항목.

## 변경 파일
domain/tier.py(BasisKind·*_ONLY·WEAK_BASIS), domain/models.py(NormalizationEvidence.basis, ChangeRecord, FieldOutcome.basis), normalizer/value_fix.py(basis 표시·_merged_basis), arbitration/rules_table.py(Decision.basis, DecisionCase.guard_weak_basis·original_value, same_value, _guard_weak_basis), arbitration/arbitrator.py(change_records, 가드 주입, original_value 공용화), arbitration/__init__.py, pipeline/runner.py(DocumentTrace.changes), config.py(change_audit_guard), tests/unit/test_change_audit.py.
흡수/대체한 기존 장치: 없음(Arbitrator 의 original_value 계산을 DecisionCase.original_value 로 공용화).

## 테스트
tests/unit/test_change_audit.py 12건 통과: 가드 켬/끔 비교(FORMULA·INFERRED 되돌림, 판정 번호 10-ng), 독립 근거 통과(PRINTED·MASTER·산식+재판독 MATCHED), 빈 값 채움 차단, 10-c 차단/10-a 통과, 분기 7 라벨 거리(7g) vs 원문 근거 인정(7), 값 불변 판정 무영향, merge 근거 병합, change_records 단계·before/after·basis(가드 켜면 되돌린 칸은 기록 안 됨). tests/unit 전체 17 실패(기존 동일) / 1927 통과, 새 실패 없음.

## 로컬 측정 (r9 재생, 캐시만, 외부 호출 0, 마스터 DB 미접속·Docraft 재판독 없음 경로)
- 가드 꺼짐: 14191/14569 = 97.405%, dev 15b172a 결과와 59건 셀 단위 완전 동일(차이 0). 정확도 불변 확인.
- 가드 켜짐: 14114/14569 = 96.877% (-77칸, -0.53pp). 개선 1칸 / 악화 78칸 (판정 번호 10-ng 만 발화, 7g·10-cg 은 이 경로에서 미발화). 상세 셀 목록: exp/e2e_call_test/out/audit_cells.json (악화/개선, answer·ao·꺼짐값·켜짐값), 비교 스크립트 scratchpad/audit_cmp.py. 결과 폴더 out/replay-r9-audit-{off,on}(-grade).
- 켜짐 시 되돌려진 칸을 단계별로 보면(총 79칸, 15파일) 끝수처리 조정 행 14, 소계·계·합계 행 칸 밀림 28, 빈 투여량 1 채움 10, 공단부담금 열 이동 13, 급여->비급여 4, 소수점 빠진 금액 4, 합계 행 두 칸 맞바뀜 2, 빠진 칸 2, N-UNPRTOT 2. 대부분이 합계로 검증된 다칸 교정이라 되돌리면 AO 오류로 복귀.
- 개선 1칸: 202501021624239c.tif 항목내역 7행 선택진료료외(공단부담금 열 이동 교정이 오히려 틀렸던 칸). 악화 최다 파일: SA2020010683384_2020010610103101(22), 103200(10), 103201(9), 390b(7).
- 정탐/오탐: 가드가 원문과 달라지는 변경으로 지목한 칸 중 정답 변경(오탐) 약 78, 오답 변경(정탐) 1. 이 데이터에선 산식 교정이 거의 항상 맞아 가드는 이득이 없다.

## 권고
기본 꺼짐 유지. FORMULA 전체를 막으면 -0.5pp 이고 개선은 1칸뿐. 좁히려면 INFERRED(10-c, 사고발생일 산출, N-UNPRTOT)만 가드하는 선택도 있으나 N-UNPRTOT 2칸이 정답이라 이 데이터에선 이득 없음. 10-c·ENRICH 는 마스터 DB 가 있는 환경(AWS 재생)에서 측정해야 한다.

## 부작용 위험·남은 일
- 켜면 값 대신 AO 원본이 나가므로 열 이동·합계 보정이 전부 검토 등급이 된다(정확도 -0.5pp).
- 재판독(7·7-i)·마스터(10-a~g) 경로는 로컬 재생에서 발화하지 않아 단위 테스트로만 검증. AWS 재생 때 가드 켜짐/꺼짐 비교 필요(요청 시 배포 담당 통해).
- 파서 보충 행 추가(recover_rows)와 10-f 등급 분류는 change_records 대상이 아님.
- exp/e2e_call_test/evaluation_run.py 심볼릭 링크가 깨져 있음(../harness-v2 -> ../../harness-v2). 채점 시 PYTHONPATH=<워크트리>/tools 로 우회.
