# unprinted-total-computed
브랜치 fix/unprinted-total-computed, 커밋 81693c8 (워크트리 Docraft/.worktrees/unprinted-total-computed)
- 근본 원인: apply가 글자에 없는 급여_* 합계를 계산 여부와 무관하게 비움(AO 관례 정책).
- 유형: 인쇄되지 않은 합계에 대해 "계산으로 설명되는가"를 구분하지 않음.
- 변경: rules.py `_column_sum`(추출)·`_computed`(신규: _fits True 또는 대응 항목 열 합과 같음) 추가, `_ungrounded`는 베낀 값(_copied)이거나 글자에도 없고 계산으로도 설명 안 되는 값만 반환. apply·check(GROUND.UNPRINTED)·_fix_total이 같은 함수를 써서 일관. 필드명 신규 하드코딩 없음(TOTALS·FIELD_SUMS 재사용). 빈 칸 신규 계산 채움 없음. 주석·yaml에 2026-10-05 정책 반영.
- 이름 변경: unprinted_null -> unprinted_totals (rules.yaml은 하네스 바이트 일치 사본 아님; 공유는 shared/receipt_items.yaml뿐). 하네스에 unprinted_null 참조 없음 확인.
- 기존 FIELD_SUMS 불일치 시 None 처리(급여총액에 비급여 포함)는 그대로 유지(인쇄 여부 무관 기존 동작).
- 테스트: 전체 908 통과. 기대값 수정 1건: test_unprinted_detail_totals_are_dropped의 사유 문구(동작 불변). 추가: test_unprinted_totals_are_kept_only_when_computation_explains_them(7변형: 구성합·열합 2종 유지 / 한 행 베낌·소계·열합 아닌 값·합계식 불일치 None), test_printed_total_stays_even_if_unexplained.
- 정답지 영향: r9-final inputs에 *.docraft.json 없음(aiocr.adapted/harness/answer/grade만) -> 재적용 불가, 미수행.
- 참고: 급여_* 4개 필드는 doctypes상 세부내역서 소속(진료비영수증엔 없음). 메커니즘은 유형 무관.
- 위험: 열합 일치 판정은 항목 행이 2개 미만이어도 통과(행 1개 열합과 같으면 계산값으로 인정). 합계 행이 있는 서식은 기존대로(_ungrounded 조기 반환).
