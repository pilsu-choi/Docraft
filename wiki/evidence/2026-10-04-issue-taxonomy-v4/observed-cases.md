# 관측된 문서 추출 이슈 사례 모음 (읽기 전용 수집, 2026-10-04)

주의: 5개 수집 그룹(A~E) 결과를 합침. 완전 동일 행(ID+현상)만 제거했고, 같은 현상의 문서 간 의미 중복 병합은 미완(ID 접두어: 그룹별 임의 약어 포함). EC·WO·WB 행의 [예상]/[지시서 예시]는 실제 관측이 아닌 설계용 시나리오.

총 880건. 문서유형별: 세부내역서 336, 영수증 183, 공통 178, 진단서 66, 진료비영수증 59, 약제비영수증 15, 소견서 15, 입퇴원확인서 10, 영수증/세부내역서 4, 진단서/소견서 3, 세부내역서/영수증 2, 진단서/영수증/세부내역서 2, 횟수 1, 진단서/세부내역서 1, 진단서/소견서/약제비 1, 진단서/영수증/약제비 1, 소견서/입퇴원확인서/영수증 1, 한방 영수증 1, 세부내역서/진단서 1

## 1. 사례 표

| 사례ID | 문서유형 | 현상 | 원인단계 | 분류ID | 상태 | 출처파일 |
|---|---|---|---|---|---|---|
| G1-a (20250102091737a3 합계 비급여총액) | 영수증 | 비급여총액 201,100→0 (회전 팩스에서 Docraft가 먼 `0` 읽고 하네스가 식 일치로 채택) | 후처리 | G1-a | 미해결(일부 반영: 0뿐인 열 소계 채택 차단, 일반 차단은 남음) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G1-b (3022030712433802-1 유령 행) | 세부내역서 | 표 끝에 `항목=진찰료`만 있는 행이 추가됨 (recover_rows가 문서유형 무관 호출) | 후처리 | G1-b | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G1-c (공란다수_…43183 납부할금액) | 영수증 | 납부할금액 0→236,700 (Docraft가 환자부담총액 칸 베낌, 식 통과로 채택) | extract | G1-c | 해결(1bd2c3c, AWS 확인 대기) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G1-d (SA2019123157847_…390b 공단부담금) | 영수증 | 공단부담금 열 전체가 선택진료료외(비급여)로 밀림 (`_uncovered_columns`가 열 통째 밀림 미감지) | 후처리 | G1-d | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G1-e (43806·390i·400b 항목명) | 영수증 | `전혈및혈액성분제재료`(인쇄 원문 유지)→`…제제료`, 요양급여 서식 `계`→`합계` (표준명 치환) | 후처리 | G1-e | 결정대기→결정1: 표준명 유지·채점 동치 처리(하네스 변경 안 함) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G2-a (103201·103300·103302·103101·103200, 375500, 2303314855) | 세부내역서 | 요약 행(소계·계·합계) 단가·횟수·일수·투여량 빈칸→`0` | extract | G2-a | 해결(1bd2c3c, 결정2: 미인쇄 0은 빈칸) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G2-b (103101 16380/820/15560, 103200 16430 등 9칸) | 세부내역서 | 요약 행 총액·본인·공단이 단가·횟수·일수 칸으로 왼쪽 몰림 | extract | G2-b | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G2-c (103001·103101·103201·103300·103302 끝수 조정 행) | 세부내역서 | 끝수 조정 행 값 밀림·누락 (예: 103201 공단 14 누락) | extract | G2-c | 해결(1bd2c3c). 단 103001 끝수 행 전액본인부담(AO 빈칸·정답 0) 1칸 잔존 | 2026-10-02-golden-harness-misextraction-analysis.md |
| G2-d (…84292_215001 계 행) | 세부내역서 | 전액본인부담 255,390이 비급여 칸으로, 506,080 누락(칸 하나 빠져 한 칸 밀림) | extract | G2-d | 미해결(합계 행도 전액본인부담을 비급여에 묶어 근거 불확정→검토로 감) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G2-e (20250102091737a3 계·끝수 행) | 세부내역서 | 142,680.75→14268075 (소수점 소실) | extract | G2-e | 해결(복원 f1c8f1e; 이후 10/03 소수 인쇄값 유지로 정답지도 소수로 수정) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G2-f (비급표현-KJM02605 9·13행) | 세부내역서 | 급여 열 미인쇄 서식인데 소계 행 급여 칸에 총액 복사 | extract | G2-f | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G3 (급여액_2303314628) | 세부내역서 | 합계 7칸 정답 0(인쇄 없음)→AO가 항목합으로 계산해 값 채움 | extract | G3 | 해결(일부: 26a14c8 검토대상화, 1bd2c3c parse 근거 0 정규화). parse 없을 때 OCR 경로 미해결 | 2026-10-02-golden-harness-misextraction-analysis.md |
| G3 (20230104_123952) | 세부내역서 | 합계 정답 0→AO 계산값 채움 | extract | G3 | 해결(일부, 위와 같음) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G3 (비급표현-KJM02605) | 세부내역서 | 합계(비급여총액 1806500 등) 정답 0→값 있음 | extract | G3 | 해결(일부: 합계 행 없는 서식 41151a5, AWS 1002 확인 unresolved) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-aws-redeploy-golden59-rerun.md |
| G3 (2303315388) | 세부내역서 | 합계 비급여총액 10000 등 정답 0→값 있음 | extract | G3 | 해결(일부, 위와 같음) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-aws-redeploy-golden59-rerun.md |
| G4-a (103101·103200) | 세부내역서 | 코드 열 하나뿐인 서식에서 원내코드 비움→EDI코드와 동일하게 복제 | extract | G4-a | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G4-b (20230104_123952) | 세부내역서 | 원내코드 `FD001`·`YT001A`→`FDOO1`·`YTO01A` (O↔0 혼동) | extract | G4-b | 해결(1bd2c3c). 형제 코드·Docraft 근거 일반화는 남음 | 2026-10-02-golden-harness-misextraction-analysis.md |
| G5-a (SA2020010683384 103001 +2행, 103100 +3행) | 세부내역서 | 섹션 제목만 있는 행(`01.진찰료`)이 출력에 남아 행 수 증가→뷰어 행 맞춤 어긋나 정확도 48.9% | 후처리 | G5-a | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G5-b (2303314855 5·6행) | 세부내역서 | `항목`=`19. 비급여CT,MRI` 병합칸 분류명이 아래 행에 안 내려와 베낀 값/빈칸 | extract | G5-b | 해결(0~4행 비움 12be3da, 분류명 채움 1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G5-c (3022030712433802-1) | 세부내역서 | 분류 열(진찰료·투약·검사) 대신 AO가 EDI명칭을 항목에 복사 (12행 항목 비움은 dev 해결) | extract | G5-c | 해결(1bd2c3c) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G6 (45314) | 영수증 | 요양기관종류 병원급→의원급(체크 미판독, 첫 선택지) | extract | G6 | 해결(r8 병원급, 335acb3). 표 408 시한초과는 r9에서 해소 | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (39576) | 영수증 | 요양기관종류 정답→의원급 오답(명칭 없음·신뢰도 0.91이라 의심 미탐, Docraft 미호출) | extract | G6 | 미해결 | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (390b) | 영수증 | 요양기관종류 체크 미판독→의원급 | extract | G6 | 해결(r3 Docraft 채택) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (400b) | 영수증 | 요양기관종류 체크 미판독→의원급; r3에서 Docraft가 `V`만 반환(회귀) | extract | G6 | 해결(Docraft f668ac9, r4 병원급) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (390i) | 영수증 | 요양기관종류 체크 미판독; r3에서 Docraft `V`만 반환(회귀) | extract | G6 | 해결(Docraft f668ac9, r4 병원급) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (1624239c / 202501021624239c) | 영수증 | 요양기관종류 종합병원→의원급 | extract | G6 | 해결(r3 채택; r8 31401fa 복구) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (43806) | 영수증 | 요양기관종류 체크 미판독; r3 Docraft SUSPICIOUS(no_source)로 오답 | extract | G6 | 해결(r4 Docraft 병원급 PASS) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6 (번들 전체) | 영수증 | 정답이 병원급 이상인 9건 중 7건 AO가 첫 선택지(의원급) 출력, 신뢰도 0.91~0.95라 신뢰도로 거를 수 없음 | extract | G6 | 해결(최종 28/29, 남은 건 39576) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G6-4 (정답지 표기 혼재) | 영수증 | `의원급·보건기관`/`의원급・보건기관`/`의원급,보건기관`/`의원`/`병원`이 섞임→표준 4값 | 평가 | G6 | 해결(결정3 표준 4값, 9cf9835·정답지 수정) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G7-a (202501021624239c) | 영수증 | 주사 약품비 121,956이 두 행 위 투약 약품비로 밀림 | extract | G7-a | 해결(c2ff3bb) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G7-b (45314) | 영수증 | 선별급여·끝수처리조정금액 행 누락→아래 행 이름 밀림 | extract | G7-b | 해결(1bd2c3c; r9에서 선별급여 r15·끝수처리 r17 복원) | 2026-10-02-golden-harness-misextraction-analysis.md; 2026-10-02-institution-type-r3-followup.md |
| G7-b (요양급여_…023627730) | 영수증 | `100/100미만50/80/30/90%` 행 4개 누락처럼 보이나 틀린 금액 없음, `계`→`합계` 이름 때문에 채점 행 어긋남 | 평가 | G7-b / G1-e | 결정대기→결정1로 채점 동치 처리 | 2026-10-02-golden-harness-misextraction-analysis.md |
| G8 진료과 (45314) | 영수증 | 진료과 `침구과`→`친구과`(신뢰도 0.475) | extract | G8 | 해결(1bd2c3c, 진료과 사전) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G8 병원명 (43183) | 영수증 | 병원명 `가톨릭…`→`기간릭…` | extract | G8 | 미해결(기관 마스터 필요, 검토 표시만) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G9 (3022…-1 12행) | 세부내역서 | 급여구분 `80/100` 선별급여: 38,560이 급여 칸→AO가 전액본인부담 칸에 넣음 | extract | G9 | 해결(1bd2c3c·Docraft 79a11bd; AWS 확인 대기) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G10 (코드2종포함_2303315044) | 세부내역서 | 단가 빈칸·횟수 21→단가 21·횟수 2(잘림), MASTER warn인데 pass 확정 | extract | G10 | 해결(1bd2c3c, 낮은 우선) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G-정답지 (43806) | 영수증 | 정답지 `혈장`→`혈액`, `일원료`→`입원료` 오류 | 평가 | - | 해결(정답지 수정) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G-정답지 (20230104_123952 0행 원내코드) | 세부내역서 | 정답지 `D658881`→`D65881` | 평가 | - | 해결(정답지 수정) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G-정답지 (SA2020010683384_…103201 AAL020 투여량) | 세부내역서 | 정답지 투여량 빈칸→`1` | 평가 | - | 해결(정답지 수정) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G-정답지 (2020010684177·157794·157840·47809·40064·2965 2건 요양기관종류) | 영수증 | 정답지 요양기관종류 `의원`·`병원`·`,`/`・`변형→표준 4값 (8칸) | 평가 | - | 해결(정답지 수정) | 2026-10-02-golden-harness-misextraction-analysis.md |
| G-정답지 요약 행 0 (2303314662·2303314712·2303315286 계·끝수·합계 단가, 2303314855 합계 투여량·단가·횟수·일수) | 세부내역서 | 정답지 요약 행 `0`(원본은 빈칸)→정답지 수정 필요(13칸) | 평가 | G2-a | 결정2로 정답지 수정 방침 | 2026-10-02-golden-harness-misextraction-analysis.md |
| VIEW-1 (SA2020010683384 103001·103100) | 세부내역서 | 정확도 48.9%가 뷰어 `_align` 행 맞춤 오류(제목 행 때문)에서 비롯, 실제 금액 오류는 끝수 행 하나 | 평가 | G5-a | 해결(제목 행 삭제로) / 뷰어 `_row_sig` 보정은 별도 | 2026-10-02-golden-harness-misextraction-analysis.md |
| EVAL-로컬재실행 깨진 14칸 | 세부내역서 | 정답지 요약 행 `0` 13칸 + 103001 끝수 행 전액본인부담 1칸 악화 | 평가 | - | 미해결(정답지 수정 반영 대기 / 1칸 잔존) | 2026-10-02-golden-harness-misextraction-analysis.md |
| BM-1 (급여구분 열추출 334칸) | 세부내역서 | 급여구분 AO `열추출`(정답지 열추출 유지)→하네스가 빈값으로 비움 | 후처리 | - | 해결(정책 결정 열추출 유지 553156a; 정답지 66칸 열추출로 통일) | 2026-09-30-golden-set-59-aws-harness-benchmark.md; 2026-10-02-golden-benefit-col-extract-unify.md |
| BM-2 (시작·종료일자 52칸) | 세부내역서 | 헤더 진료기간 채운 시작·종료일자(정답)→하네스 `_period_copies`가 빈값으로 비움 | 후처리 | - | 해결(b1925dd `_period_copies` 삭제, 악화 52→0) | 2026-09-30-golden-set-59-aws-harness-benchmark.md; 2026-10-02-aws-redeploy-golden59-rerun.md |
| BM-3 (표 비급여·선택진료료외 3, 항목 하이픈 제거 1, Docraft 교정 2) | 세부내역서 | 기타 악화 6칸(비급여·선택진료료외 금액 채움, 항목 하이픈 제거, Docraft 교정 악화) | 후처리 | - | 미해결(건별 확인 필요) | 2026-09-30-golden-set-59-aws-harness-benchmark.md |
| BM-4 (SA2019123157847_201912311546380f.tif) | 공통 | 문서분류 정답 약제비영수증→AO `Y000701200`(서식코드) 그대로, 하네스 doc_type도 미변환→채점 0칸 | 입력 | - | 해결(서식 코드 변환 fa68ece 반영 확인 필요 → 이후 재분류 작업) | 2026-09-30-golden-set-59-aws-harness-benchmark.md |
| RD-1 (SA2019123043735_2019123013232302 요양기관종류) | 영수증 | 일치→불일치: Docraft가 `[V]의원급·보건기관`(체크 표시 포함) 읽은 값을 repaired 채택 | extract | G6 | 해결(Docraft 40f5afe·harness d8a4a62, r3 복구) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| RD-2 (항목 EDI명칭 복사 19칸) | 세부내역서 | `항목`에 EDI명칭 베낀 틀린 값→빈값으로 바뀜(정확도 변화 없음) | extract | G5-b/G5-c | 해결(비움 12be3da, 채움은 G5) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| RD-3 (20250102091737a3 항목내역 rows[3]·[4]) | 세부내역서 | 정답 142680·333001 / -80·78 (소수 버림)→출력 142680.75 / 333001.75 / -80.75 / 78.25 | 평가 | G2-e | 해결(10/03 소수 인쇄값 유지, 정답지를 소수로 수정) | 2026-10-02-aws-redeploy-golden59-rerun.md; 2026-10-03-golden-benefit-printed-only.md |
| RD-4 (보고 버전 2026.09.8 고정) | 공통 | 규칙셋 신버전 배포했으나 보고 버전이 `.env.aws` RULE_SET_VERSION 고정값으로 표시 | 입력 | - | 해결(.env.aws 수정, 규칙 갱신 시 함께 올림) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| IT-1 (r3 45314) | 영수증 | Docraft `[✓]병원급`을 하네스 `_drop_shared_evidence`가 버려 오답 | 후처리 | G6 | 해결(335acb3 모호 출처 수용) | 2026-10-02-institution-type-r3-followup.md |
| IT-2 (r4·r5 45314 표 408) | 영수증 | Docraft /api/read HTTP 408 시한 초과로 재판독·끝수처리 행 누락 | extract | G7-b | 해결(r9 Docraft 298570b 표 요청 성공) | 2026-10-02-institution-type-r3-followup.md |
| IT-3 (unresolved 칸 value가 AO 원값 `의원급`) | 영수증 | 45314 unresolved의 value가 표준값 `의원급·보건기관`이어야 하나 AO 원값 `의원급` | 후처리 | G6 | 해결(9016c9f, r5 확인) | 2026-10-02-institution-type-r3-followup.md |
| BEN-1 (급여 열 미인쇄 문서) | 세부내역서 | 급여 열이 인쇄 안 된 문서의 정답 급여 칸 값 있음→빈칸 (5491 359칸, 2965 1121칸) | 평가 | - | 해결(정답지 정책: 인쇄된 문서만 유지, 3건 유지) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-2 (급여액_2303314628) | 세부내역서 | 머리글 없는 3/4쪽, 급여 열 인쇄 여부 불명확→미인쇄로 추정해 빈칸 | 평가 | - | 미확정(추정) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-3 (선택진료료·선택진료료외·본인·공단·전액본인부담·비급여·총액 미인쇄 열 복사/0) | 세부내역서 | 미인쇄 열을 단가=총액 복사, 급여액 총액 복사, 급/비 표시로 비급여 이동, 선택진료 0 채움 (980칸 값 0, 36칸 0 아닌 값 → 빈칸) | extract | - | 해결(정답지 1,027칸 수정, 인쇄된 값만 규칙) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-4 (20250102091737a3 계·끝수 6칸) | 세부내역서 | 정답지 소수 버림 676782 등→인쇄값 676782.5·142680.75·333001.75·-2.5·-80.75·78.25 | 평가 | G2-e | 해결(정답지 수정) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-5 (3022033115105207 총액 954.5, 단가 18, 비급여 8) | 세부내역서 | 정답 총액 954.5(소수)·'금액' 자리를 단가로 둔 정답지→총액으로 통일, 비급여 8칸 미인쇄 | 평가 | - | 해결(10/03 결정: 인쇄된 금액=총액, 단가 빈칸) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-6 (코드2개 소계 급여액 786·69080) | 세부내역서 | 소계 급여액이 총액 자리에 있음→인쇄된 급여액 자리로 이동; Docraft가 급여액 2칸 누락 | extract | - | 해결(정답지 수정) / Docraft 누락 급여 2칸 미해결 | 2026-10-03-golden-benefit-printed-only.md |
| BEN-7 (Docraft 급/비 표시 → 비급여 11칸) | 세부내역서 | '급/비' 표시를 보고 금액을 비급여로 옮겨 적음(비급여 99.7→98.8) | extract | - | 해결(Docraft 규칙 제거 6015f0c) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-8 (단일 날짜 열 종료일자, 5491 24건 221칸·2965 17건 185칸) | 세부내역서 | 날짜 열 하나뿐인 서식 종료일자 빈칸→시작일자 베낀 값 | extract | - | 해결(정답지 빈칸 정책 + Docraft 복사 제거); AO 복사분은 고객 질문 1 대기 | 2026-10-03-golden-benefit-printed-only.md; 2026-10-04-issue-classifier-golden59-ranking.md |
| BEN-9 (SA2020010683931 5~8행 종료일자) | 세부내역서 | 정답 종료일자=인쇄된 실시일자 20191227·20191226×3→정답지에 처방일자 복사(오류) | 평가 | - | 해결(정답지 4칸 수정) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-10 (진료종료일 152칸·진료시작일 5칸) | 공통 | 진료종료일(문서 단위) 미인쇄인데 값 있음 (외래 시작일 복사, 표 날짜 min/max로 진료기간 계산) | extract | - | 해결(Docraft 8781af3·harness 6b7b01c 룰1 필수키 제외); 고객 질문 1·2 대기 | 2026-10-03-golden-benefit-printed-only.md |
| BEN-11 (결정 필요: 종료일자=시작일자 복사 관례) | 세부내역서 | 종료일자 복사 관례 유지 여부 | 미확정 | - | 결정대기(고객 확인 질문 1) | 2026-10-03-golden-benefit-printed-only.md |
| BEN-12 (20230228094825256178 수량) | 세부내역서 | 수량을 횟수 자리로 둘지 투여량 자리로 둘지 | 미확정 | - | 결정대기 | 2026-10-03-golden-benefit-printed-only.md |
| BEN-13 (진료기간 미인쇄 쪽) | 공통 | 머리글 없는 이어지는 쪽·일자별 계산서에서 진료시작일·종료일 빈칸 허용 여부 | 미확정 | - | 결정대기(고객 확인 질문 2) | 2026-10-03-golden-benefit-printed-only.md |
| FD-1 (SA2020010683384_* 9건, 20230104_123952, 코드2개_…) | 세부내역서 | 항목: 섹션 제목(`05.검사료`) 값 →모델이 제목 행을 머리글로 보고 버리고 EDI명칭·코드 적음 | extract | G5-a/G5-b | 해결(Docraft 규칙 `_section_items` 일반화, 오프라인 항목 40.1→66.8%) | 2026-10-02-detail-filldown-group-values.md |
| FD-2 (2303315388) | 세부내역서 | 항목: 분류가 무리 첫 행에만 인쇄되고 아래 빈칸→빈칸 그대로 | extract | G5-b | 해결(`_carry` 계획, 오프라인 평가) | 2026-10-02-detail-filldown-group-values.md |
| FD-3 (20230104·비급표현-KJM02605·코드2개 시작·종료일자) | 세부내역서 | 표에 날짜 열 없음, 진료기간(입원기간) 날짜가 행으로 안 퍼짐 (`_period` 한 방향, 라벨에 '입원기간' 빠짐) | extract | - | 해결(오프라인 시작일자 85.7→95.6%). 이후 10/03 인쇄값만 정책으로 재정의(진료기간 미인쇄 시 빈칸) | 2026-10-02-detail-filldown-group-values.md; 2026-10-03-golden-benefit-printed-only.md |
| FD-4 (정답 소계·계·합계·끝수 행 96칸 항목 불일치) | 세부내역서 | Docraft `TABLE_HINT`가 요약 행을 표에서 제외→정답 요약 행 항목 불일치 | extract | G2 | 결정대기(정책 결정 대상) | 2026-10-02-detail-filldown-group-values.md |
| FD-5 (OCR 오인식 `19. 비급여CT,MR`, 정답 오타 `80.`←`B0.`, 행 순서 오류 20250102091737a0·a2) | 세부내역서 | 항목 OCR 오인식·정답지 오타·행 순서 오류 | parse | - | 미해결(범위 밖) | 2026-10-02-detail-filldown-group-values.md |
| FD-6 (소계 행에 항목 행 붙어 채점된 날짜 4칸) | 세부내역서 | 출력에 소계 행이 없어 행 맞춤 어긋남 | 평가 | - | 미해결(기존 문제) | 2026-10-02-detail-filldown-group-values.md |
| HDR-1 (금액 | 횟수 | 일수 | 총액 서식, 표본 대부분) | 세부내역서 | `금액` 머리글을 총액 있어도 열로 보지 않아 단가 열 인쇄 인식 누락 | parse |
| HDR-2 (SA2020010683384·2303315388·202501010931310b) | 세부내역서 | `금액`→단가 별칭 없음→인쇄 단가 "미인쇄"로 오판해 지움 | parse | - | 해결 | 2026-10-04-detail-header-recognition.md; 2026-10-04-unprinted-column-copy.md |
| HDR-3 (합쳐진 머리글 칸 `금액 횟수`·`횟수일수`·`횟수 일수`·`명칭 층투 횟수`·`일수 금액`·`횟수(총투)일수`) | 세부내역서 | OCR이 이웃 머리글을 한 칸으로 읽어 두 열 다 인쇄 인식 누락 | parse | - | 해결(`_names`·`_segment`) | 2026-10-04-detail-header-recognition.md |
| HDR-4 (2303314662·2303314712 쌓인 칸) | 세부내역서 | AO가 열 전체를 한 칸(`성형외과<br>금액<br>15,810<br>…`, `급여<br>공단부담금<br>0…`)으로 내 머리글 행 못 찾음 | parse | - | 해결 | 2026-10-04-detail-header-recognition.md |
| HDR-5 (2303314855·SA2020010684292 묶음 `급여` 윗단) | 세부내역서 | 묶음 머리글 `급여`만 있는 윗단이 머리글 행으로 뽑혀 급여만 인쇄로 판정 | parse | - | 해결(`_header` 인쇄 열 최다 행) | 2026-10-04-detail-header-recognition.md |
| HDR-6 (동의어 `전액본인`·`선택진료`·`투약`·`용량`·`총투`) | 세부내역서 | 서식 다른 이름이 사전에 없어 열 인식 누락 | parse | - | 해결 | 2026-10-04-detail-header-recognition.md |
| HDR-7 (같은 열 이름 칸 둘) | 세부내역서 | `_columns`가 같은 AO 열 가리키는 칸 둘을 제외해 인쇄 열 놓침 | parse | - | 해결(인쇄와 값 칸 맞추기 분리) | 2026-10-04-detail-header-recognition.md |
| HDR-8 (급여액_2303314628) | 세부내역서 | AO parse 표에 머리글 행 자체 없음(문단 89개 어디에도 머리글 글자 없음) | parse | - | 미해결(모름 None 처리) | 2026-10-04-detail-header-recognition.md |
| HDR-9 (3022033115105207-1 투여량 머리글 `층투`) | 세부내역서 | 머리글 `총투`를 `층투`로 오독→투여량 열 미인식 | parse | - | 미해결(OCR 오타 동의어 안 넣음) | 2026-10-04-detail-header-recognition.md |
| HDR-10 (`투약일수` 머리글) | 세부내역서 | `투약` 동의어 때문에 `투약`+`일수`로 잘못 갈릴 수 있음(표본엔 없음) | parse | - | 미해결(잠재) | 2026-10-04-detail-header-recognition.md |
| UC-1 (3022033115105207 단가 18·비급여 8) | 세부내역서 | 미인쇄 열 단가=총액 복사, 비급여=단가·총액 복사 | extract | - | 해결(`_unprinted_columns`, 머리글 인식 위 개선 42칸·악화 0) | 2026-10-04-unprinted-column-copy.md |
| UC-2 (2303314855 투여량 7, 코드2개_급여액 총액 5, 비급표현-KJM02605 비급여 2·전액본인부담 1, 3022030712433802 전액본인부담 1) | 세부내역서 | 미인쇄 열에 같은 행 칸 복사 | extract | - | 해결(같은 원인 42칸 개선) | 2026-10-04-unprinted-column-copy.md |
| UC-3 (첫 구현 악화 125칸: 단가 105·투여량 10·횟수 9·일수 9) | 세부내역서 | 머리글 인식이 단가 놓쳐 수량 1 행의 정상 단가(=총액)를 복사로 오판해 지움(97.4→96.6%) | 후처리 | - | 해결(폐기 후 머리글 인식 선행·합 근거 제거로 재구현) | 2026-10-04-unprinted-column-copy.md |
| UC-4 (3022033115105207-1 실데이터 재생) | 세부내역서 | 저장된 입력에 parse HTML 없어 오프라인 재생 불가 | 입력 | - | 미확정(AWS 전체 실행 확인 대기) | 2026-10-04-unprinted-column-copy.md |
| UC-5 (영수증 표 미인쇄 열) | 영수증 | 같은 원인 확인 안 돼 미적용 | 미확정 | - | 미해결(범위 밖) | 2026-10-04-unprinted-column-copy.md |
| UC-6 (종료일자 날짜 복사) | 세부내역서 | 미인쇄 종료일자에 시작일자 복사 | extract | - | 결정대기(고객 확인) | 2026-10-04-unprinted-column-copy.md |
| CLS-1 (E.OVR.DUP.2 종료일자 220칸) | 세부내역서 | 종료일자 빈칸→AO가 같은 행 시작일자 복사 | extract | E.OVR.DUP.2 | 결정대기(고객 확인 질문 1) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-2 (E.OVR.DUP.2 금액 복사 67칸: 급여 34·단가 18·비급여 10·총액 5) | 세부내역서 | 미인쇄 금액 열에 같은 행 다른 금액 열 복사 | extract | E.OVR.DUP.2 | 해결(unprinted-column-copy-v2; r9는 구버전이라 재채점 필요) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-3 (AUX.EVAL 상한액초과금 29칸) | 영수증 | 키 `상한액초과금`(정답지)↔`상환액초과금`(AO·하네스) 불일치로 채점기가 칸 못 찾음(값은 맞음, 약 0.2%p) | 평가 | AUX.EVAL | 결정대기(고객 스키마 정식 키 확인) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-4 (E.MIS.FIELD.2 투여량 19칸, 진료시작일 등 9칸) | 세부내역서 | 인쇄된 투여량 `1`→AO가 놓침(3022033115105207 등); `_blank_doses` 규칙이 단가 복사로 검산 실패 | extract | E.MIS.FIELD.2 | 미해결(금액 복사 수정 후 재확인) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-5 (E.WRG.NORM.3 13칸) | 세부내역서 | 투여량·날짜 칸 빈칸↔0 | extract | E.WRG.NORM.3 | 미해결 | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-6 (E.MIS.PART.2 10칸) | 세부내역서 | 금액 소수점·자릿수 소실 | extract | E.MIS.PART.2 | 해결(일부: 10/03 소수 유지; 재확인 필요) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-7 (UNCLASSIFIED 7칸: 종료일자 4칸·사고발생일자 1·급여 786→0 1·요양기관종류 1) | 공통 | 정답 종료일자는 행마다 같은데 출력은 행마다 다른 날짜 4칸 등 | 미확정 | UNCLASSIFIED | 미해결(사람 판정) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-8 (E.WRG.READ.1 5칸) | 영수증 | 진료과·병원명 오독 | extract | E.WRG.READ.1 | 미해결(G8 병원명과 같은 유형) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-9 (AUX.POST.VALID 3칸·AUX.POST.PICK 1칸) | 공통 | 후처리가 산식·재판독으로 틀린 값 채택(악화 3·1) | 후처리 | AUX.POST.VALID / AUX.POST.PICK | 미해결 | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-10 (GEN.1 2, GEN.2 2, PART.1 1, ASSIGN.2 1) | 공통 | 그 밖 분류 7칸 | extract | E.OVR.GEN.1/2 · E.MIS.PART.1 · E.WRG.ASSIGN.2 | 미해결 | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-11 (비교 기준 이원화) | 공통 | 같은 r9가 뷰어 85.4%(오답 2,144칸) vs 공식 97.32%(391칸): 금액 빈칸↔0, null 정답 제외, 개인정보 마스킹 정책 상이 | 평가 | AUX.EVAL | 미해결(범위 밖, 채점기 버전관리 선행) | 2026-10-04-issue-classifier-golden59-ranking.md |
| CLS-12 (분류기 오판: E.CON.SCHEMA.1 49칸) | 공통 | 채점기가 못 찾음/null을 모두 None으로 적는데 키 누락으로 오분류 | 평가 | E.CON.SCHEMA.1 | 해결(505c5b1, 실제 키 누락 0칸) | 2026-10-04-issue-classifier-golden59-ranking.md |
| EC-P01 | 공통 | [예상] 저해상도·흔들림·압축 이미지: 소수점·음수·획 → 소실 | 입력 | 화질 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P02 | 공통 | [예상] 회전·기울기·원근·접힘: 줄·열 경계와 읽기 순서 → 왜곡 | 입력 | 촬영 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P03 | 공통 | [예상] 반사광·그림자·손가락·도장·가장자리 잘림: 이름·금액 → 일부 누락 | 입력 | 가림·잘림 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P04 | 공통 | [예상] 과한 이진화·노이즈 제거·리사이즈: 연한 글씨·체크·소수점 → 삭제 | 입력 | 전처리 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P05 | 공통 | [예상] 0/O, 1/I/l, 5/S, 한글 유사 글자: 코드·식별자·숫자 → 오인 | parse | 문자 혼동 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P06 | 공통 | [예상] 손글씨·취소선·덧쓰기·수정값: 최종값 → 폐기된 값 채택 또는 두 값 합침 | parse | 필기·수정 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P07 | 공통 | [예상] 다단·측면 메모·세로쓰기·각주: 필드 연결 → 서로 다른 문단과 연결 | parse | 읽기 순서 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P08 | 공통 | [예상] 병합 셀·무테 표·줄바꿈 셀·빈 셀: 금액 → 옆 열로 이동, 한 행이 두 행으로 분리 | parse | 표 구조 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P09 | 공통 | [예상] 다음 페이지로 이어진 표·반복 헤더: 정상 이어붙임 → 중복·누락 행, 잘못된 연결 | parse | 표 연속성 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P10 | 공통 | [예상] 체크박스·동그라미·화살표·음영·도장: 선택 여부 → 소실 | parse | 비문자 표시 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P11 | 공통 | [예상] 한 사진에 영수증 두 장·앞뒷면·빈 페이지·중복 스캔: 문서 분리 → 혼합, 페이지 누락·중복 | 입력 | 문서 경계 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P12 | 영수증 | [예상] 긴 영수증·초고해상도: 글자 보존 → 축소로 소실, 타일 경계 누락·중복 | 입력 | 큰 입력 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P13 | 공통 | [예상] EXIF 회전·투명 배경·다중 프레임 TIFF·손상 파일: 정상 디코딩 → 거꾸로 읽기·검은 배경·첫 프레임만 처리 | 입력 | 이미지 디코딩 | 해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-P14 | 공통 | [예상] 긴 출력 중단·일부 영역만 인식: 완결 결과 → 문법은 유효하나 내용 불완전 | parse | 출력 완결성 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E01 | 공통 | [예상] 환자·보호자·계약자·의사 이름 공존: 환자 이름 → 다른 사람에게 연결 | extract | 대상 귀속 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E02 | 공통 | [예상] 진료일·입원일·퇴원일·발행일·결제일 공존: 해당 역할 날짜 → 형식만 맞는 다른 날짜 채택 | extract | 날짜 역할 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E03 | 영수증 | [예상] 총액·본인부담·공단부담·수납·미수·환불 공존: 요청 금액 → 잘 보이는 합계 선택 | extract | 금액 역할 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E04 | 진단서 | [예상] 없음·의심·배제·과거력·가족력: 확정 사실만 → 언급된 질환·수술을 확정으로 추출 | extract | 부정·불확실성 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E05 | 공통 | [예상] 빈칸·미기재·판독불가·해당 없음·0·대시: 구분 → 모두 null 또는 0으로 축약 | extract | 결측 의미 | 결정대기 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E06 | 공통 | [예상] 여러 진단·수술·방문·후보 날짜: 배열 전체 → 첫 항목만 추출 또는 임의 선택 | extract | 복수 값 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E07 | 세부내역서 | [예상] 항목·수량·단가·금액 줄바꿈·병합: 항목 단위 연결 → 다른 행 값으로 한 항목 생성 | extract | 행 관계 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E08 | 영수증 | [예상] 정정본·취소 영수증·재발행: 유효 문서 → 구버전 채택 또는 이중 집계 | extract | 정정·재발행 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E09 | 공통 | [예상] 원/천원·mg/g·괄호 음수·불완전 날짜: 정규값 → 배수·부호 오류, 없는 연도 생성 | extract | 단위·형식 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E10 | 공통 | [예상] 선행 0·하이픈·마스킹 번호: 문자열 보존 → 0 소실, 가린 부분 추정 | extract | 식별자 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E11 | 공통 | [예상] 본문과 표의 날짜·금액 불일치, 코드와 병명 불일치: 충돌 노출 → 그럴듯한 값으로 임의 교정 | extract | 상충 근거 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E12 | 공통 | [예상] 다른 서식 적용·필드 없는 문서·필수값 강제: 결측 유지 → 존재하지 않는 값 생성 | extract | 스키마 불일치 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E13 | 공통 | [예상] 다음 페이지 헤더 생략·다른 환자 문서 묶음: 문서 경계별 전파 → 앞 페이지 대상·단위 잘못 전파 | extract | 페이지 통합 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E14 | 공통 | [예상] 이미지에 명령문·답안 예시 포함: 데이터로 취급 → 문서 문장을 추출 지시로 따름 | extract | 모델 지시 혼입 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E15 | 공통 | [예상] 값은 맞으나 근거 위치·페이지가 다른 항목을 가리킴: 올바른 근거 → 검토자가 잘못된 근거로 승인 | 후처리 | 근거 불일치 | 해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| EC-E16 | 공통 | [예상] 잘린 JSON·타입 오류·중복 키·배열 일부 누락: 완결 직렬화 → API 실패 또는 조용한 데이터 손실 | 후처리 | 직렬화 | 미해결 | 2026-09-27-image-parse-extract-edge-cases.md |
| PQ-01 | 공통 | `.TIF` 확장자인 실제 GIF 이미지: OCR 정상 처리 → OCR 422 실패 (디코딩·EXIF 반영 RGB PNG 정규화로 수정 e03330a) | 입력 | - | 해결 | 2026-09-27-parse-extract-quality.md |
| PQ-02 | 영수증 | 여러 층 머리글 병합 시 상위 `전액 본인부담`이 하위 `공단부담금`보다 우선: 금액 → 다른 열로 이동 (신규 영수증 정답 920→948, 수정 67bb81e) | parse | - | 해결 | 2026-09-27-parse-extract-quality.md |
| PQ-03 | 진단서/세부내역서 | 비급여 포함 총진료비를 급여총액으로 넣은 라벨 오류 → 별도 급여합계 근거 없는 값을 null로 수정 | 평가 | - | 해결 | 2026-09-27-parse-extract-quality.md |
| PQ-04 | 세부내역서/영수증 | 묶음 머리글 `급여`·`비급여` 열: schema 0 vs 기존 rules·회귀 테스트 null (strict 82.54→83.81% 하락 요인) | 평가 | - | 결정대기 | 2026-09-27-parse-extract-quality.md |
| PQ-05 | 진단서/소견서 | 주민번호→성별·생년월일 파생값 FP 6건 (파생값 허용 정책과 라벨 범위 미분리) | 평가 | - | 결정대기 | 2026-09-27-parse-extract-quality.md |
| PQ-06 | 진단서/소견서 | 원문 라벨 보충 FP 3건 (차트번호 2, 주소 1): 원문에 텍스트 있음 ≠ 필드 의미 일치 | 평가 | - | 결정대기 | 2026-09-27-parse-extract-quality.md |
| PQ-07 | 진단서/소견서 | 서술→치료명 FP 4건 | 평가 | - | 결정대기 | 2026-09-27-parse-extract-quality.md |
| PQ-08 | 공통 | bench.py가 누락 필드를 unmatched로 제외: 전체 필드 분모 → 분모에서 빠짐 (누락 포함 지표로 수정 28caa52 등) | 평가 | - | 해결 | 2026-09-27-parse-extract-quality.md |
| PQ-09 | 진단서/소견서/약제비 | 신규 15건 정확도 하락 (raw 양성값 170/199=85.43%, 기존 76건 94.19%): 라벨 범위·정규화·규칙 변화 원인 별도 조사 | 미확정 | - | 미해결 | 2026-09-27-parse-extract-quality.md |
| PQ-10 | 공통 | 전체 필드 97% 목표 → 신규 35건 loose 2,063/2,217=93.05%, strict 83.81% (미달성) | 미확정 | - | 미해결 | 2026-09-27-parse-extract-quality.md |
| PQ-11 | 공통 | 인쇄된 빈칸: null → 값 생성 108/741 (raw 115/733) | extract | - | 미해결 | 2026-09-27-parse-extract-quality.md |
| PQ-12 | 진단서/영수증/세부내역서 | 이미지 변형 gold 4건: 원본 strict 410 → 회전 303·흐림 311·가림 302 (loose는 485~488로 유지) | 입력 | - | 미해결 | 2026-09-27-parse-extract-quality.md |
| PQ-13 | 영수증 | 기존 규칙 평가 loose 4,263/4,479(95.2%) vs strict 2,929/4,479(65.4%): 채점 계약 차이 | 평가 | - | 결정대기 | 2026-09-27-parse-extract-quality.md |
| PQ-14 | 공통 | 출처 `source_text`가 실제 OCR 원문 대신 추출값으로 채워지는 경로 → 원문 출처 보강 (Docraft 1d6d2e7) | 후처리 | - | 해결 | 2026-09-27-parse-extract-quality.md |
| RP-01 | 진단서 | 임상적추정·최종진단 체크형 항목: 체크표시→Y/N 근거 연결 → no_source (항목은 존재) | extract | - | 해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-02 | 진단서 | 입원일: 추출 YYYYMMDD vs OCR 한국어 년·월·일 표기를 `engine._needles`가 동등 원문으로 못 찾음 → no_source | 후처리 | - | 해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-03 | 공통 | 35건 캐시 블록에 OCR 줄 좌표(`lines[].bbox`) 없음 → no_geometry (line OCR 꺼진 상태 생성) | parse | - | 해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-04 | 영수증 | 외래/입원·공단부담총액·발행일: 추출값은 silver와 일치하나 OCR 원문 근거 미연결 (합계 인쇄값이 파싱 텍스트에서 빠짐, 발행일은 라벨 없이 병원 하단 인쇄, 줄 좌표 0) | parse | - | 미해결 | 2026-09-27-reprocess-priority.md |
| RP-05 | 영수증 | 상한액초과금(`상환액초과금`): 원본 공란 → 비공란 값 추출 (null 후보에 근거 없어 재처리 미채택) | extract | - | 미해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-06 | 세부내역서 | `진료기간` 아래 날짜 범위 → 시작일·종료일 두 필드 연결 근거 규칙 없음 | extract | - | 해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-07 | 세부내역서 | 사고발생일자: 별도 라벨 없음, 스키마가 진료시작일과 같은 의미로 정의 → 직접 인쇄 근거와 별칭 근거 구분 필요 | 입력 | - | 해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-08 | 세부내역서 | 급여 본인부담총액: `본인부담액` 아래 `급여` 하위열과 총계 행 동일값 → 매칭 모호 (병합 머리글·총계 행 판별 필요) | parse | - | 미해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-09 | 영수증 | grounding `_labels`가 `rules.LABELS` 별칭(공단부담금·상한액초과금)을 쓰지 않아 4필드 라벨 앵커 미확보 | 후처리 | - | 해결 | 2026-09-27-reprocess-priority.md; 2026-09-27-typed-evidence.md |
| RP-10 | 공통 | 앞쪽 no_source·no_geometry 필드가 공용 시도 예산 소진 → 뒤쪽 필드 시도 못 받음 (우선순위 개선 b26af80; 교정 채택 0건) | 후처리 | - | 해결 | 2026-09-27-auto-reprocess-loop.md; 2026-09-27-reprocess-priority.md |
| RP-11 | 진단서/영수증/세부내역서 | 예산 확대(90초·8단계·VLM 4회) 자연 3건: 값 교정 채택 0건 (원문·라벨 연결 실패·모호 근거 지속) | 후처리 | - | 해결 | 2026-09-27-reprocess-priority.md |
| AR-01 | 진단서 | 진단일 의도적 오독 시험: 복구 → 모든 후보 `unverified_candidate` 거절 (`distant_label`·exact 근거 부재) | 후처리 | - | 해결 | 2026-09-27-auto-reprocess-loop.md; 2026-09-27-typed-evidence.md |
| AR-02 | 공통 | 3단계 중첩 객체를 표 셀로 오인해 필드 라벨 검증 생략 → 실제 배열 셀 판별로 제한 | 후처리 | - | 해결 | 2026-09-27-auto-reprocess-loop.md |
| AR-03 | 공통 | 기존/후보 규칙 비교 시 행·열 식별 정보 누락 → 같은 코드의 새 위반 놓침 | 후처리 | - | 해결 | 2026-09-27-auto-reprocess-loop.md |
| AR-04 | 공통 | 여러 필드 순차 교정 시 앞선 `CORRECTED` 상태 소실 | 후처리 | - | 해결 | 2026-09-27-auto-reprocess-loop.md |
| AR-05 | 공통 | 재추출 재대기열 시 이전 `reprocess` 이력 → 미초기화 | 후처리 | - | 해결 | 2026-09-27-auto-reprocess-loop.md |
| AR-06 | 공통 | Harness 작업 취소: 실행 중 동기 HTTP 즉시 중단 → 불가 (호출 전후 검사만) | 후처리 | - | 미해결 | 2026-09-27-auto-reprocess-loop.md |
| AR-07 | 공통 | 주소 필드 의도적 오독 시험: 정답 복구 → 초기 판독값으로만 되돌아옴 (초기값·후보 모두 silver와 불일치) | extract | - | 미해결 | 2026-09-27-auto-reprocess-loop.md |
| TE-01 | 영수증 | 상한액초과금 영역(index 20): 라벨 OCR 오류·인쇄 번호 ⑤·불완전 경계·약 1.4도 기울기 → 공란 확정 불가 | parse | - | 미해결 | 2026-09-27-typed-evidence.md |
| TE-02 | 세부내역서 | index 25: 머리글 오독·병합 구조의 의미 연결 불명, 빈칸 1개는 병합 셀 (null 교정 사례 아님) | parse | - | 미해결 | 2026-09-27-typed-evidence.md |
| TE-03 | 영수증 | 영수증 표 VLM 교정 약 52초 소요 (근거 재사용 불가) → 선택 기능 기본 꺼짐 | 후처리 | - | 해결 | 2026-09-27-typed-evidence.md; 2026-09-30-harness-weekly-briefing.md |
| NC-01 | 약제비영수증 | 회전된 약제비영수증: 가변 인쇄 내용이 서식 항목명보다 한 행 위로 밀려 금액 3필드 오연결 → 인쇄 오프셋·유일 금액·합계식 추론으로 3필드 교정 | parse | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-02 | 공통 | 주소 재판독 첫 수정안에서 잘못된 교정 채택 1건 → 후보값·동일 OCR 없는 전체 이미지 재판독 일치 요구로 거절 | 후처리 | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-03 | 공통 | 날짜 칸 비었으나 본문에 두 입원 기간 존재: 칸 공백만으로 날짜 전체 미기재 확정 금지 | extract | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-04 | 영수증 | 명시적 빈칸(금액): null → 0 또는 비공란 값 오추출 2건 (빈 칸 닫힌 물리 셀 영상 근거로 교정) | extract | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-05 | 공통 | 확대 예산에서 짧은 성명 오교정 1건: 전체 이미지 재판독에 OCR 문자열을 함께 줘 같은 오독 반복 → wide_vlm에 OCR 미전달로 변경 | 후처리 | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-06 | 진료비영수증 | AO 표본 22 카드 칸: 정답(빈칸/null) → AO 비0 금액 유지 (Docraft 재판독 null이나 grounding·quality 없어 unavailable, 분기 9 unresolved) | extract | - | 미해결 | 2026-09-28-natural-corrections.md |
| NC-07 | 진료비영수증 | AO 표본 24 초과금: 정답 null → AO 0 유지 (직접 근거 없음, 분기 9 unresolved) | extract | - | 미해결 | 2026-09-28-natural-corrections.md |
| NC-08 | 약제비영수증 | AO 표본 33 금액 3칸(총액·공단부담액·급여본인부담): 정답 → AO 오답 (현재 코드 live에서 7-i repaired로 정답 교정) | extract | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-09 | 약제비영수증 | AO UI가 `진료비내역`을 단일 행 표로 반환 vs 하네스 합계가 스칼라 이름(`진료비내역-총액`) 사용 → 구조 불일치 (단일 행 매핑 750cd2c) | 후처리 | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-10 | 공통 | 임시 실행기가 editable install 경로로 구 하네스(main@09e7a76) import → 22·24·33 결과를 최신 성과로 오인 (제외·재검증) | 평가 | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-11 | 진단서/영수증/약제비 | 예산 확대(180초·8단계·VLM 4회): 올바른 교정 5 → 5 (호출 3.14배, 시간 2.09배), 4문서 0 → 0 | 후처리 | - | 해결 | 2026-09-28-natural-corrections.md |
| NC-12 | 공통 | 중단 후 재시작 프로세스 중복으로 `guarded-default` 시간·호출 결과 오염 → 최종 비교에서 제외 | 평가 | - | 해결 | 2026-09-28-natural-corrections.md |
| CR-01 | 소견서/입퇴원확인서/영수증 | 룰1: 필수 키 채움 비율 <0.97 → 205건 중 7건 해당 (소견서 2, 입퇴원 2, 영수증 3) | extract | 룰 1 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-02 | 영수증 | 룰2: 항목내역에 진찰료·CT진단료 행 누락 → 30건 중 2건 (한방 오탐 1건은 예외 처리) | extract | 룰 2 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-03 | 영수증 | 룰3: AO 금액 칸 빈칸·0인데 parse 표에 값 있음 → 9칸 보충 (`20220307_120439.jpg` 5칸 정답지 일치) | extract | 룰 3 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-04 | 세부내역서 | 룰3: AO 금액 칸 빈칸·0인데 parse 표에 값 있음 → 20건 중 7칸 보충 (7칸 모두 정답지 일치) | extract | 룰 3 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-05 | 영수증 | 룰4: 재검증(Docraft) 후에도 급여·비급여 칸 빔 → parse 콤마 형식 값을 후보로 사용 | 후처리 | 룰 4 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-06 | 영수증/세부내역서 | AO가 빈 금액 칸을 `"0"`으로 출력 → 0도 빈칸으로 간주 (같은 행에 같은 금액 있으면 보충 안 함) | extract | 룰 3 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-07 | 영수증/세부내역서 | parse 오류 칸 (한 칸에 숫자 둘 이상, 절삭평균 30배 초과) → 보충 제외 | parse | 룰 3 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-08 | 세부내역서 | 정상 고액 항목(최대 708배)이 30배 기준에 걸려 보충 안 됨 (잘못 채우지는 않음, 30배 유지 결정 9/28) | 후처리 | 룰 3 | 해결 | 2026-09-28-extract-coverage-rules.md |
| CR-09 | 영수증/세부내역서 | 고객사 AO API 키(`workflow:result`) 미발급·네트워크 미확인 → 룰 3·4 동작 불가 (번들 재빌드·NAS 미반영) | 입력 | 룰 3·4 | 미해결 | 2026-09-28-extract-coverage-rules.md |
| WO-01 | 진단서 | [지시서 예시] 질병코드 `C16.9` → `C1G.9` (Parse 오독을 Extract가 그대로 선택) | parse | Parse 글자 오독 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-02 | 영수증 | [지시서 예시] 금액 `123,500` → `123,50` | parse | Parse 글자 오독 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-03 | 공통 | [지시서 예시] 글자 혼동 0↔O, 1↔I↔l, 6↔G, 8↔B, 띄어쓰기·글자 분리·합침 | parse | Parse 글자 오독 | 해결 | parse-extract-보강-작업지시서.md |
| WO-04 | 공통 | [지시서 예시] bbox 위치 오류: 옆 셀 포함, 한 글자가 여러 bbox, 여러 글자가 한 bbox | parse | Parse 위치 오류 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-05 | 세부내역서 | [지시서 예시] 행 관계: `09/01 AA123 10,000` → `09/01 BB456 10,000` 식 읽기 순서·연결 틀림 | parse | Parse 읽는 순서 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-06 | 공통 | [지시서 예시] 표 이해 오류: 행·열 합쳐짐/나뉨, 값이 옆 열로 밀림, 병합 셀, 표 미탐지, 다른 표 합침, 이어진 표 연결 오류 | parse | Parse 표 이해 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-07 | 공통 | [지시서 예시] 회전·기울기·흐림·저해상도·밝기·그림자·잘림·도장/서명 겹침·손글씨·수정 흔적 | 입력 | Parse 이미지 상태 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-08 | 공통 | [지시서 예시] 페이지 누락·중복·순서 변경·서로 다른 문서 혼합 | 입력 | Parse 페이지 문제 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-09 | 진단서 | [지시서 예시] Key 표현 차이 `진단명` ↔ `상병명`·`병명`·`주상병`·`진 단 명` 미처리 | extract | Extract Key 오탐 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-10 | 진단서 | [지시서 예시] `진단명 = 위암`이어야 하나 `위절제술`(수술명) 추출 | extract | Extract Value 오탐 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-11 | 공통 | [지시서 예시] 바로 아래 행·옆 열·다른 셀·다른 표·다른 Section 값을 가져옴 | extract | Extract 위치 관계 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-12 | 공통 | [지시서 예시] 같은 Key `성명`이 환자정보·의사정보에 중복: 환자 성명 → 의사 성명 선택 | extract | Extract 중복 Key | 미해결 | parse-extract-보강-작업지시서.md |
| WO-13 | 진단서 | [지시서 예시] 주상병·부상병 다중값: 하나만 추출·순서 바뀜·다른 행 섞임·배열 개수 상이 | extract | Extract 다중값 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-14 | 공통 | [지시서 예시] 유사 필드 혼동: 진단일↔발병일↔입원일, 진단명↔수술명, 총액↔본인부담금↔공단부담금, 주상병↔부상병 | extract | Extract 유사 필드 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-15 | 공통 | [지시서 예시] 형식 이상: 날짜 칸 문자열, 금액 칸 코드, 코드 형식 오류, 소수점·음수·단위, 앞자리 0 소실 | extract | Extract 형식 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-16 | 공통 | [지시서 예시] 원본에 없는 값을 LLM/VLM이 추측해 생성 (가장 위험) | extract | Extract 값 생성 | 미해결 | parse-extract-보강-작업지시서.md |
| WO-17 | 공통 | [실제 발생] `AA254`가 일자로 잘못 매핑 (회귀 테스트로 남길 것) | extract | - | 미해결 | parse-extract-보강-작업지시서.md |
| TD-01 | 영수증 | `202501020959270c` 행위료 4,120,000 중복 (parse 보충 뒤 위·아래 행 같은 열 값 행 밀림) → 비움 | 후처리 | P1-1 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-02 | 영수증 | `SA2019123157847_201912311546390i`(`390i`) 8,889가 선택진료료외인데 통과 (parse 없을 때 비급여 서식 판별 불가) | 후처리 | P1-2 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-03 | 세부내역서 | `2303314662` 계 행 비급여 3,000 누락 (`2303314855`도 190,000 채움, 정답지 계 행 없어 검증 불가) | 후처리 | P1-3 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-04 | 영수증 | `0959270c` parse로 채운 금액이 `4,120,000` 콤마 표기로 입력 | 후처리 | P1-5 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-05 | 영수증 | `390b` 공단부담총액 45,642: Docraft가 원문 근거와 함께 읽었으나 `distant_label` 거절 (9/28에는 채택) | 후처리 | P1-4 (#4) | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-06 | 영수증 | `0959270c` 합계 비급여 9,010,000: Docraft가 읽었으나 분기 9 불채택, parse 보충도 합계 행 제외 | 후처리 | P1-5 (#5) | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-07 | 영수증 | `0959270c` 4행, `1345559a` 5행 빠진 행 (복구가 필수 항목 진찰료·CT진단료만) → 32행·28행 정답 일치, `39576` +4행 | extract | P2 #6 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-08 | 영수증 | `202501021624239c` 공단부담금 120 / 3,212 / 121,956 → 선택진료료외로 일부 칸만 옆 열 밀림 | parse | P2 #7 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-09 | 진단서 | 병원 세분 코드 `G563-1`·`S3250-2`·`R5099-2`·`M8936/3`·`K6358`: KCD 기저 코드만 있어 판정 불가 (원본 그대로/기저 코드 고객사 합의 필요) | 후처리 | P2 #8 | 결정대기 | 2026-09-30-harness-issue-todo.md |
| TD-10 | 진단서 | KCD 명칭 판정 오탐 `M7920`·`M513`·`K760`·`K529` (추출은 맞음, 임베딩 켜도 0.585<0.75) → 동의어·분할 비교로 통과 | 후처리 | P2 #9 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-11 | 진단서 | `S82820` KCD 명칭 판정: 병명·코드가 한 줄 밀린 문서라 의도대로 fail | 입력 | P2 #9 | 미해결 | 2026-09-30-harness-issue-todo.md |
| TD-12 | 영수증 | 항목명 표기 `보철교정료`↔`보철·교정료`, `입원료_2-3인실`↔`입원료_2·3인실` (정답지와 표기 상이, 0↔빈칸 동일 취급) | 후처리 | P2 #16 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-13 | 영수증 | `45515` 예약진찰료·처치및수술료·재활및물리치료료·응급의학관리료 5~7행, `39576` 포괄수가진료비 누락 (`[UNK]` 세 글자 처리·표준 목록 누락·이름 규칙) | extract | P2 #17 | 해결 | 2026-09-30-harness-issue-todo.md |
| TD-14 | 영수증 | `45515` CT진단료 행: 첫 실행에서 Docraft가 빈 항목내역 반환 (재실행에서 복구, 실행마다 상이) | extract | P3 관찰 | 미해결 | 2026-09-30-harness-issue-todo.md |
| TD-15 | 약제비영수증 | 금액 규칙 0개 (총액·환자부담총액·수납금액 관계식, 약품 표 대상 여부 고객사 확인 필요) | 미확정 | P3 #10 | 결정대기 | 2026-09-30-harness-issue-todo.md |
| TD-16 | 공통 | 형식은 정상인 날짜 오류: 원본 위치와 1차 판독값 직접 대조 부재 | extract | P3 #11 | 미해결 | 2026-09-30-harness-issue-todo.md |
| TD-17 | 영수증 | `2020010684177` 등급 하락 (필수 칸 `진료시작일` 빈칸): 원본 인쇄 시 AO 누락 → 정상 동작 여부 확인 | 미확정 | P3 #12 | 미해결 | 2026-09-30-harness-issue-todo.md |
| TD-18 | 공통 | 보고서 오기: 3,000 누락 문서명 `20230104_123952`→`2303314662`, `PDZ090007O`는 정답지 기준 재현 안 됨 | 평가 | P3 #13 | 결정대기 | 2026-09-30-harness-issue-todo.md |
| TD-19 | 공통 | 정답지 사람 검수 전: 정확도 재측정 불가 | 평가 | P3 #14 | 미해결 | 2026-09-30-harness-issue-todo.md |
| TD-20 | 공통 | Docraft 다시 읽기 처리 시간: AWS L4 1장 56~230초 (7건 85~302초) | 후처리 | P3 #15 | 미해결 | 2026-09-30-harness-issue-todo.md |
| TD-21 | 한방 영수증 | 스키마 키 `한약(첩약)` vs 하네스 표준명 `한약첩약` (기존부터 다름) | 후처리 | - | 결정대기 | 2026-09-30-harness-issue-todo.md |
| TD-22 | 영수증 | 항목명 출력: 표준명(`전혈및혈액성분제제료`·`합계`·`보철교정료`) vs 서식 원문(`제재료`·`계`·`보철·교정료`) 중 어느 쪽으로 낼지 | 후처리 | 항목명 출력 표기 | 결정대기 | 2026-09-30-harness-issue-todo.md |
| FB-01 | 진단서 | 1차 판독 서류 종류 오분류(영수증→진단서 등): 제목 OCR 재확인 (210장 정답 199·오답 0·판단 불가 11) | 입력 | ①' | 해결 | 2026-09-29-harness-flow-briefing.md; 2026-09-30-harness-weekly-briefing.md |
| FB-02 | 공통 | 인쇄되지 않은 값을 기준 DB로 추정해 채우는 기능: 정답지 채점 악화 → 제거 | 후처리 | - | 해결 | 2026-09-29-harness-flow-briefing.md |
| FB-03 | 공통 | 여러 페이지 서류·동기(이미지 없음) 요청은 Docraft 다시 읽기 불가 → 하네스 판정으로 종료 | 입력 | - | 미해결 | 2026-09-29-harness-flow-briefing.md; 2026-09-30-harness-weekly-briefing.md |
| FB-04 | 세부내역서 | 단가 4,500·횟수 2·일수 빈칸·금액 9,000 → 횟수 1·일수 2로 표 재읽기 후 규칙 통과 (예시) | extract | - | 해결 | 2026-09-29-harness-flow-briefing.md |
| FB-05 | 영수증 | 병원명 비어 필수 칸 검사에 걸림 → `keys:["병원명"]`만 재읽기 (예시) | extract | - | 해결 | 2026-09-29-harness-flow-briefing.md |
| WB-01 | 진단서 | [가상 예시] 병명 코드 `I10` → `110` (영문 I를 숫자 1로, 첫 글자) → 기준표+병명 일치로 고침 (10-e) | parse | 정리보정 17-질병코드 첫 글자 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-02 | 진단서 | [가상 예시] 병명 `본태성 고혈압` → `(주상병)본태성 고혈압` (서식 표지 포함) → 표지 제거 (10-n) | parse | 정리보정 13 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-03 | 진단서 | [가상 예시] 코드 `M54.5` → `M54.S` (숫자 5를 영문 S, 중간 글자) → 기준표에 없어 unresolved 후 Docraft 재읽기로 고침 (분기 7) | parse | MASTER_KCD_03 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-04 | 진단서 | [가상 예시] 최종진단 Y / 임상적추정 `N` → 빈칸 → 체크박스 짝 채움 | extract | 정리보정 15 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-05 | 진단서 | [가상 예시] 진단일 `2026-08-16` → `2026-08-15` (형식 정상·모순 없는 값 오류) 통과로 미검출 | extract | 한계 | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-06 | 소견서 | 표본: 코드 `I678B` → `I6788` (B를 8로 읽음) → 기준표에 없어 unresolved, 중간 글자는 자동 치환 안 함 | parse | MASTER_KCD_03 | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-07 | 진단서 | Docraft OCR 표본: 코드 `I671` → `1671`, `증명서` → `중명서` | parse | - | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-08 | 영수증 | 이미지 잘림: 합계 영역이 이미지 끝에 닿아 잘림 → 해당 영역 규칙 해당 없음 처리 | 입력 | - | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-09 | 영수증 | 질병군(DRG) 번호 칸에 사업자번호·병실번호 (예: `212-82-07728`) → 비움 | extract | FMT_AC029_DRG / 정리보정 12 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-10 | 세부내역서 | 급여구분이 자리표시 `열추출` → 빈칸으로 비움 | 후처리 | 정리보정 2 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-11 | 세부내역서 | 항목이 자기 EDI 명칭을 베낌 ("초진진찰료" → `01.진찰료` 섹션 제목) | extract | 정리보정 3 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-12 | 세부내역서 | 병실 칸에 진료과 ("내과혈액종양") → 비움 | extract | 정리보정 4 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-13 | 세부내역서 | 3행 이상 동일 복사된 진료기간 (모두 20210601~20210610) → 비움 | extract | 정리보정 5 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-14 | 세부내역서 | 합계 비급여총액 0인데 항목 비급여 합 >0 (0 → 3,000) → 채움 | extract | 정리보정 6 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-15 | 세부내역서 | 갈라진 코드: EDI 칸 `PDZ090007` + 원내코드 칸 `O` → `PDZ090007O` 합침 | parse | 정리보정 7 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-16 | 영수증 | 항목명 오독 "진칠료"·"식데" → 진찰료·식대 표준화 | parse | 정리보정 8 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-17 | 영수증 | 금액 열 뒤바뀜 (본인 100,000 ↔ 공단 500,000) → 두 열 합계 모두 맞을 때만 맞바꿈 | parse | 정리보정 9 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-18 | 영수증 | 급여 칸에 들어간 비급여 금액 (급여 279,683 → 비급여) → 공단부담 전부 0·합계 맞을 때 이동 | extract | 정리보정 10 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-19 | 영수증 | 비급여 ↔ 선택진료료외 칸 오배치 (선택진료료외 50,000 → 비급여) → 서식 머리글로 판별 후 이동 | parse | 정리보정 11 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-20 | 진단서 | 병명이 한 칸에 합쳐짐 ("허리, 손목 등의 염좌") → 코드별 공식 병명 일치·방법 하나뿐일 때 분할 | extract | 정리보정 14 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-21 | 진단서 | 사고발생일자 20210310 → 진단일·가장 이른 검사일 중 빠른 날 20210305로 재계산 | 후처리 | R-CERT-ACCIDENT / 정리보정 16 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-22 | 공통 | 날짜 표기 차이 (`2021.6.3`·`2021년 6월 3일`) → `20210603` 통일 | 후처리 | 정리보정 1 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-23 | 진단서 | 질병코드 첫 글자 숫자 오인 (0→O, 1→I, 5→S, 8→B, 2→Z, 6→G; 예 `0990`→`O990`) | parse | FMT_KCD_02 / 정리보정 17 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-24 | 진단서 | 코드–병명 짝 엇갈림 (코드 [B,A]·병명 [A병,B병]) → 짝 다시 놓기 (swap) | extract | R-KCD-PAIRING | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-25 | 영수증/세부내역서 | 합계 불일치·표 모양 오류(열 값 개수≠행 수): 합계 규칙·표 모양 규칙 → 열 뒤바뀜만 맞바꿈, 표 모양은 검출만 | parse | CALC_AC029_10 / STRUCT_AC029_13 | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-26 | 세부내역서/진단서 | 코드–이름 불일치 (주사료 코드에 "식대" 항목명 등): 검출만, 후보만 첨부 | extract | MASTER_0710_09 / MASTER_KCD_04 | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-27 | 진단서 | 성별↔주민번호, 생년월일↔주민번호 모순: 경고만 | extract | R-CERT-SEX / R-CERT-BIRTH | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-28 | 세부내역서 | 수가코드 비어있음·다른 행 값 가져옴·단가 대조: 후보(애매)·기록만, 행 계산 규칙은 표 재읽기 | extract | MASTER_0710_10 / R-0710-ROWSUM | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-29 | 약제비영수증 | 금액 계산 오류: 규칙 0개로 검출 불가 ("판정 재료 없음") | 미확정 | - | 결정대기 | 2026-09-30-harness-weekly-briefing.md |
| WB-30 | 공통 | 앞 칸에서 시도 횟수를 다 쓰면 뒤 칸 재읽기 불가 (서류당 60초·4시도·VLM 2회) | 후처리 | - | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-31 | 세부내역서/영수증 | 세부내역서 행 단위 오류 분석, 영수증 합계 행 열 밀림 (남은 과제) | 미확정 | - | 미해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-32 | 공통 | 하네스 자체 재판독 루프(최대 3회): 개발 서버 측정 해결 건수 0 → Docraft 구성에서 미사용 | 후처리 | 7-a/7-b | 해결 | 2026-09-30-harness-weekly-briefing.md |
| WB-33 | 공통 | 정확도 93.0% (정답지 사람 검수 전) vs 목표 97~99%: 거리 존재 | 평가 | - | 미해결 | 2026-09-30-harness-weekly-briefing.md; 2026-09-29-harness-flow-briefing.md |
| RM-1 코드2개_급여액_3022033115393304-1 | 세부내역서 | 열 정렬 정상→rowmajor가 투여량을 비우고 뒤 값을 한 칸씩 당겨 표 전체 열 밀림(단가 자리에 111960 등, 93칸) | extract | 열 밀림 | 해결 | 2026-10-02-table-rowmajor-ab-experiment, -conditional, -report |
| RM-2 열 뒤바뀜(공단→본인) | 세부내역서 | 본인부담/공단부담 정위치→서로 바뀜(공통 순서의 '급여' 자리가 묶음 제목 '급여'와 겹침, 33칸) | extract | 열 뒤바뀜 | 해결 | 2026-10-02-table-rowmajor-report |
| RM-3 투여량·횟수·일수 순서 | 세부내역서 | 인쇄 순서(일수 뒤 투여량)→공통 순서(단가 앞)로 읽어 값 위치 틀림(23칸) | extract | 열 뒤바뀜 | 해결 | 2026-10-02-table-rowmajor-report |
| RM-4 전액본인부담↔비급여·회전 스캔 | 세부내역서 | 정위치→열 뒤바뀜·회전 스캔 머리글 위치 못 읽어 공통 순서 사용(12칸) | parse | 열 뒤바뀜 | 미해결 | 2026-10-02-table-rowmajor-report |
| RM-5 원내코드 후퇴 | 세부내역서 | 원내코드 열 채움→머리글에서 코드 열을 하나만 읽은 서식에서 원내코드 열 제외(93.4→89.0%, 21칸) | 후처리 | 원내코드 후퇴 | 해결 | 2026-10-02-table-rowmajor-report, extra-detail-validation |
| RM-6 SA2020010684193 | 세부내역서 | 산식 정상→불일치 행 비율 0.333, 79.5%(asis 재추출로 87.7%) | extract | 열 밀림 | 해결 | 2026-10-02-table-rowmajor-conditional |
| RM-7 선택진료료외만_금액표기 | 영수증 | 선택진료료외 값→3칸 빔(오류 2→5칸), 원인 못 찾음 | 미확정 | - | 미해결 | 2026-10-02-table-rowmajor-conditional, -report |
| RM-8 소계포함 영수증 | 영수증 | 소계 열 처리→양식 스펙에 없는 소계 열 때문에 개선 안 됨 | extract | - | 미해결 | 2026-10-02-table-rowmajor-conditional |
| RM-9 영수증 열 뒤바뀜 | 영수증 | 정위치→통합 8열 스키마에서 2칸 뒤바뀜(양식별 열 배치로 0칸) | extract | 열 뒤바뀜 | 해결 | 2026-10-02-table-rowmajor-conditional, -report |
| RM-10 양식 판별 실패 1건(OCR이 '이외' 놓침) | 영수증 | 양식 4 판별→미판별, 8열 통합 스키마로 읽음 | parse | - | 미해결 | 2026-10-02-table-rowmajor-conditional |
| RM-11 asis 초과·누락 행 | 세부내역서 | 정답 행 수→asis 누락 114·초과 31(rowmajor 누락 115·초과 10) | extract | 행 누락/초과 | 미해결 | 2026-10-02-table-rowmajor-ab-experiment |
| EX-1 회전 문서 a0·a2·a3 | 세부내역서 | 정상 방향 판독→회전 정답지 정확도 49.6/49.8/77.2%(rowmajor 0행 포함) | parse | 회전 | 해결(a0·a2 92.6/87.6%, a3 79.8%) | 2026-10-02-extra-detail-validation |
| EX-2 a3 6행 중 3행 누락 | 세부내역서 | 6행→3행(두 방식 모두), 방향 문제 아님 | 미확정 | - | 미해결 | 2026-10-02-extra-detail-validation |
| EX-3 image_17.tif | 세부내역서 | 옆으로 누운 합계 전용 쪽 방향 정규화→놓침 | parse | 회전 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-4 기간 한 칸 '일자' 열 | 세부내역서 | 시작·종료일자 분리→시작일이 종료일에 복사(일자 차이 167칸 중 135칸) | extract | 시작일→종료일 복사 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-5 붙은 머리글 '본인부담금공단부담금' | 세부내역서 | 공단부담 열 값→열 통째로 빔 | parse | 못 읽은 열을 없는 열로 처리 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-6 수가코드·청구코드 서식 | 세부내역서 | 청구코드(EDI) 값→버림(원내코드 후퇴와 같은 유형) | 후처리 | 못 읽은 열을 없는 열로 처리 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-7 게이트 빈틈 | 세부내역서 | 금액 통째 빈 응답·무너진 표 검출→arith_misses가 총액 있는 행만 세어 실패율 0 통과 | 후처리 | 게이트 빈틈 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-8 asis 2단 머리글 | 세부내역서 | 공단부담→본인부담 칸에 값 넣음 | extract | 열 뒤바뀜 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-9 asis 공단→본인 순서 서식 | 세부내역서 | 두 열 정위치→서로 뒤바꿈 | extract | 열 뒤바뀜 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-10 asis 명칭/코드 칸 혼동 | 세부내역서 | 코드·항목 정위치→명칭을 코드 칸에, 항목 칸에 명칭 복사 | extract | - | 미해결 | 2026-10-02-extra-detail-validation |
| EX-11 asis 긴 표 중단 | 세부내역서 | 49행→6행 누락(중간에 끊김) | extract | 행 누락 | 미해결 | 2026-10-02-extra-detail-validation |
| EX-12 게이트 오발동 | 세부내역서 | 가산 문서 정상 통과→8건 중 5건 오발동 | 후처리 | 게이트 오발동 | 결정대기(우선순위 낮음) | 2026-10-02-extra-detail-validation |
| EX-13 일자 차이 판정(실행일자 정책) | 세부내역서 | rowmajor/asis 일자 차이 2건 asis 맞음, 1건 보류 | 평가 | 정책 | 결정대기 | 2026-10-02-extra-detail-validation |
| PX-1 급여구분 '열추출' 빈칸화(분기 10-n) | 세부내역서 | 정답 '열추출' 유지→하네스가 빈칸으로 바꿈(오류 268칸, 하네스가 망친 272칸 중 268) | 후처리 | 분기 10-n | 해결(정책 열추출 유지, harness 553156a) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-2 상한액초과금 누락 | 영수증 | 상한액초과금 값→누락 29칸(키 상한액/상환액 차이로 추정) | 후처리 | - | 결정대기(AO가 키 수정 예정, ac029.yaml:268은 상환액초과금만 참조) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-3 3022033115105207-1·3022030712433802-1·2303314855 | 세부내역서 | 정답 값→52칸 누락(Docraft 표 요청 408·502, 병합칸 분류명) | extract | G5-b | 해결(408 해소, 1002i 이후) | 2026-10-02-extraction-accuracy-paper-experiments, docraft-read-latency-analysis |
| PX-4 투여량 열 통째 누락 | 세부내역서 | 투여량 값→한 서식에서 열 전체 빔(20칸, 칸 단위 채움률로 못 잡음) | extract | 열 통째 누락 | 미해결(룰 5a로 검토 전환만) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-5 병합칸 분류명 '항목' 누락 | 세부내역서 | 항목(분류명) 값→빈칸 | extract | G5-b | 미해결(룰 5로 검토 표시) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-6 자동적재 칸 누락 | 공통 | 자동 적재 오류 81칸 중 56칸이 누락, 하네스 누락 52칸 중 90% 이상 검토 표시 없이 출력 | 후처리 | 누락 | 해결(룰 5 배포, 목록 205건 재보정 남음) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-7 AO 빈칸에 Docraft '1' 채움 | 세부내역서 | 투여량 빈칸 유지→Docraft가 '1' 채움(위험 27~29칸) | extract | - | 해결(채택 안 함, 보류) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-8 보철교정료 vs 보철·교정료 | 영수증 | 정답 '보철·교정료'→Docraft 채택값 '보철교정료'(표기 차이 오답 1) | extract | 표기 차이 | 미해결(보류) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-9 영수증 진료시작일 | 영수증 | AO 빈칸에 Docraft 채택 이득 3칸(진료시작일, 같은 원인 1유형) | extract | - | 결정대기(채택 보류) | 2026-10-02-extraction-accuracy-paper-experiments |
| PX-10 가산·할증 행 항등식 불성립 | 세부내역서 | 행 산식 성립→정답지 자체의 항등식 만족 비율 79~83% | 평가 | - | 미해결 | 2026-10-02-extraction-accuracy-paper-experiments |
| IT-1 SA2019123043735 요양기관종류 `[V]` | 영수증 | 표준값→체크 표시 `[V]` 그대로(9/30 대비 새 오류) | extract | 체크박스 | 해결(Docraft 체크박스 지침 40f5afe) | 2026-10-02-aws-integrated-feature-test, deploy-r3 |
| IT-2 390i·400b 요양기관종류 'V' | 영수증 | 병원급→Docraft가 V만 반환(SUSPICIOUS), 분기 9로 AO값 '의원급' 유지 | extract | 체크박스, 분기 9 | 해결(f668ac9, 1002c) | 2026-10-02-aws-integrated-deploy-r3, deploy-1002c |
| IT-3 요양기관종류 원문 vs 표준 4종 (2020010684177·SA2019123157794) | 영수증 | 정답 '의원'/'병원'→출력 표준값 '의원급·보건기관'/'병원급' | 평가 | 정책 | 해결(정답지 표준 4종 통일) | 2026-10-02-aws-integrated-deploy-r3, feature-test |
| IT-4 요양기관종류 SA2019123039576 | 영수증 | 정답 병원급→출력 '의원급·보건기관'(판독 오답, 28/29 일치 유지) | extract | - | 미해결 | 2026-10-02-aws-integrated-feature-test, deploy-1002c·1002h·1002i |
| IT-5 390i·소계포함_45314 정규화 누락 | 영수증 | 표준값→하네스 출력 '의원급' | 후처리 | 정규화 누락 | 해결(9016c9f 1002d, 390i 확인) | 2026-10-02-aws-integrated-feature-test, deploy-1002d |
| IT-6 39576·43806·400b 판독 오답 | 영수증 | 병원급→'의원급·보건기관' | extract | - | 해결(43806·400b), 39576 미해결 | 2026-10-02-aws-integrated-feature-test, deploy-1002c·1002h |
| IT-7 2303314855 10행 투여량·횟수·일수 | 세부내역서 | 정답 0→빈 값 | 후처리 | - | 미해결 | 2026-10-02-aws-integrated-deploy-r3 |
| IT-8 소계포함_SA2019123045314 선별급여·끝수처리 행 누락 | 영수증 | 선별급여 행(r15)·끝수처리조정금액 행(r17) 존재→누락(9칸, 표 요청 408) | extract | 408 | 해결(1002i 표 요청 성공) | 2026-10-02-aws-integrated-deploy-1002c·1002d·1002f·1002h·1002i |
| IT-9 3022030712433802-1 항목(분류명) | 세부내역서 | '진찰료'·'투약'·'검사' 채움→빈 값, 13행 급여구분 '전액본인부담'(정답 급여)·급여 0(정답 38560) | extract | G5-b, 408·502 | 해결(1002h 22/22 일치) | 2026-10-02-aws-integrated-deploy-1002d·1002f·1002g·1002h |
| IT-10 분류명 채택이 빈 표를 받음(하네스 버그) | 세부내역서 | 분류명 채택→_docraft_classes가 빈 표를 읽어 미채택(키 경로 fields 아래로 변경) | 후처리 | - | 해결(f9d417f) | 2026-10-02-aws-integrated-deploy-1002g·1002h |
| IT-11 202501021624239c·SA2019123157847_400b 요양기관종류 악화 | 영수증 | 종합병원/병원급→'의원급·보건기관'(Docraft PASS인데 분기 9로 unresolved) | 후처리 | 분기 9 | 해결(31401fa 1002h) | 2026-10-02-aws-integrated-deploy-1002g·1002h |
| IT-12 급여구분 66칸 악화(2303315388 등 6건) | 세부내역서 | 정답 빈칸→하네스 '열추출' 유지 | 평가 | 정책 | 해결(정답지 열추출 통일) | 2026-10-02-aws-integrated-deploy-1002h |
| IT-13 SA2019123157847_400b 납부할금액 | 영수증 | 정답 0→11000(전액 수납 PAYABLE 규칙 의미) | 후처리 | R-AC029-PAYABLE | 해결(cd1461a, r10 11000→0) | 2026-10-02-docraft-read-latency-analysis, aws-integrated-deploy-1002i·1002j |
| IT-14 EDI명칭 셀 master_reference 0행 | 세부내역서 | EDI명칭 셀에 원장 보조표시→168행 중 0행(검증 대상 아니라 harness 블록 없음) | 후처리 | 10.1-4 | 해결(뷰어 같은 행 코드 기준 표시) | 2026-10-02-aws-integrated-deploy-1002d·1002e |
| IT-15 3022030712433802-1 502 | 세부내역서 | 표 응답 수신→Docraft 502(116초), 항목 r2~12·r17~20 빈 값 | extract | 408·502 | 해결 | 2026-10-02-aws-integrated-deploy-1002f |
| IT-16 SA2019123045314 요양기관종류 분기 9 | 영수증 | 병원급→Docraft 병원급이지만 분기 9 mismatched로 '의원급·보건기관' | 후처리 | 분기 9 | 해결(1002g 분기 7) | 2026-10-02-aws-integrated-deploy-1002f·1002g |
| IT-17 Docraft 표 요청 실패 6건 | 세부내역서 | 표 행 값→408/ReadTimeout/502로 표 응답 없음(r6 6, r8 3, r9 0) | extract | 408 | 해결(298570b) | 2026-10-02-aws-integrated-deploy-1002f·1002h·1002i |
| IT-18 정답지 59건 급여구분 정책 차이 | 세부내역서 | 정답 대비 열추출 315칸·소계/합계 95행 정책 차이로 정확도 82% | 평가 | 정책 | 해결(열추출 유지·정답지 통일) | 2026-10-02-table-rowmajor-report |
| DT-1 draft 급여총액 계산값 | 세부내역서 | 서식에 없는 급여_급여총액→본인+공단 합 계산 기재(2건 null 복원, 나머지 notes에 남음) | 입력 | - | 미해결(검수 때 확인) | 2026-10-02-detail-testset200 |
| DT-2 종별행위가산액 행 | 세부내역서 | 명세 행 포함 관례→일부 초안은 제외 | 입력 | - | 결정대기(검수) | 2026-10-02-detail-testset200 |
| DT-3 환자정보(입통원구분) 추정 | 세부내역서 | 표기 값→표기 없이 병실·명칭으로 추정 | 입력 | - | 결정대기(검수) | 2026-10-02-detail-testset200 |
| ST-1 영수증 잘린 칸 합계 계산 채움 | 영수증 | 인쇄값 ""→합계에서 계산해 채움(4-8.tif, 홈페이지4.tif) | 입력 | 계산 채움 금지 | 결정대기(검수) | 2026-10-02-six-type-testsets |
| ST-2 영수증 합계 1,000원 이상 차이 10건 | 영수증 | 항목 합≈합계→중복 행 2·합계 오독 1·누락 행 1 수정, 나머지 인쇄값 uncertain | 입력 | - | 해결 | 2026-10-02-six-type-testsets |
| ST-3 진단서 날짜 형식 위반 | 진단서 | 형식 준수→201811, 미상(2건 보정), 입원 여러 번 쉼표 나열 1건 | 입력 | - | 해결(2건)/결정대기(1건 검수) | 2026-10-02-six-type-testsets |
| ST-4 진단서 계열 체크칸 없는 서식 | 진단서 | 최종진단·임상적추정→null/N 처리, 소견 본문 입원·수술 날짜 미반영 | 입력 | - | 결정대기(검수) | 2026-10-02-six-type-testsets |
| ST-5 약제비영수증·진단서4종 스키마 불일치 | 약제비영수증 | 요구 필수키→현행 AO 키와 달라 골든 미반영 | 입력 | - | 결정대기 | 2026-10-02-six-type-testsets |
| RK-1 룰 추출 라벨 오채움 | 공통 | 정답 182건→잘못 채운 값 45·틀린 값 119(환자/의료기관 공용 라벨 '주소'·'성명', 체크박스 선택지 줄, 항목 번호) | extract | 라벨 오매칭 | 미해결(룰 주추출 비추천) | 2026-10-02-rule-based-kv-extract-review |
| RK-2 신규 세부내역서 서식 정확도 하락 | 세부내역서 | 기존 9건 98.0%→신규 10건 74.9% | extract | - | 미해결 | 2026-10-02-rule-based-kv-extract-review |
| RK-3 PaddleOCR-VL 0.9B 표 구조 오류 | 공통 | 표 구조·병합셀 정확 판독→행 밀림·셀 합쳐짐, 읽는 순서·글자 신뢰도 없음 | parse | - | 미해결 | 2026-10-02-rule-based-kv-extract-review |
| PE-1 급여 3열→2열·전액본인부담 열 누락·합계 칸 합쳐짐 | 영수증 | 급여 3열·전액본인부담→2열·열 누락, 합계 여러 칸이 한 셀 | parse | - | 해결(괘선 격자 보강) | 2026-10-03-parse-extract-cause-review |
| PE-2 요약 행 미출력 | 세부내역서 | 소계·합계 행 출력→추출 지시가 제외해 미출력 | extract | 요약 행 | 해결(keep_totals 반영) | 2026-10-03-parse-extract-cause-review, summary-rows-policy-integration |
| PE-3 돌아간 팩스 OCR 좌표·열 판별 실패 | 세부내역서 | 정상 판독→회전 팩스에서 좌표·열 판별 실패 | parse | 회전 | 해결(방향 정규화) | 2026-10-03-parse-extract-cause-review |
| PE-4 AO 세부내역서 26건 오답 322칸 | 세부내역서 | 정답→약 182칸은 짝 맞는 parse 행에 정답 있었음(상한 추정 56.5%) | extract | G1~G10 | 미해결(후속 활용 여지) | 2026-10-03-parse-extract-cause-review |
| PE-5 202501020959270c 약품비 | 세부내역서 | 약품비 4,120,000 약품비 칸→행위료에 배정(parse는 옳은 행) | extract | 오배정 | 미해결 | 2026-10-03-parse-extract-cause-review |
| PE-6 45515 투약 및·조제료/약품비 병합 연결 실패·[UNK] | 세부내역서 | 병합 머리글·문자 정상→연결 실패·[UNK] 손실, 남은 누락 행은 parse에 증거 있음 | parse | - | 미해결 | 2026-10-03-parse-extract-cause-review |
| PE-7 붙은 머리글·뭉친 행·한 셀 복수 숫자·명칭 오독 | 세부내역서 | 정상 구조→parse에서 구조·문자 오류(보충 시 모호 칸 제외) | parse | - | 미해결 | 2026-10-03-parse-extract-cause-review |
| KC-1 T2422/K296 병명 합침 | 진단서 | 병명 2개 각 행→OCR이 첫 코드 행에 합치고 다음 행 비움(명칭 4개로 보완 중단) | parse | KCD 경계 | 해결(원장 명칭 경계 복원·전체 명칭 폴백) | 2026-10-03-kcd-name-boundaries-fallback |
| KC-2 M4806/M511, M8786/M171 및 세 행 결합 | 진단서 | 병명 각 행→합쳐진 병명 | parse | KCD 경계 | 해결 | 2026-10-03-kcd-name-boundaries-fallback |
| SR-1 요약 행 일자·급여 | 세부내역서 | 인쇄값만→집계 행에 일자 채움, 급여=총액이면 지움, 미인쇄 급여 0/총액 복사 | 후처리 | 요약 행 | 해결(Docraft 120feef, harness 5ddf433, 93.14→96.24%) | 2026-10-03-summary-rows-policy-integration |
| SR-2 코드2개_급여액 서식 급여액 열 | 세부내역서 | 인쇄된 급여액 열→열 배치에서 빠짐 | extract | 열 배치 | 미해결 | 2026-10-03-summary-rows-policy-integration |
| SR-3 방문별 합계 행 날짜 | 세부내역서 | 합계 행 빈 날짜→모델이 날짜 기재 | extract | 요약 행 | 결정대기 | 2026-10-03-summary-rows-policy-integration |
| SR-4 20250102091737a3 계 행 소수 값 | 세부내역서 | 정답지 값→소수 값 대조 필요 | 평가 | - | 결정대기 | 2026-10-03-summary-rows-policy-integration |
| SR-5 합계 필드 '계' vs '합계' 행 | 세부내역서 | 합계 필드 채울 행 정의→미정 | 평가 | 정책 | 결정대기 | 2026-10-03-summary-rows-policy-integration |
| SR-6 표 행 번호(#) 검사 | 세부내역서 | 번호 정상 기재→14건 중 13건 번호 검사 걸려 asis 대체(번호 자리에 URL 등) | extract | - | 미해결(dev 미반영, 재설계 제안) | 2026-10-03-summary-rows-policy-integration |
| AR-1 부분 페이지 결과 완전성 미표시(D5) | 공통 | 전체 페이지 추출→실패 그룹 제외 병합(청담 4/6쪽·건국대 1/3쪽만 복원) 표시 없음 | extract | D5 | 해결(partial 표시·승인 제한, review-integrity) | 2026-10-03-harness-docraft-architecture-quality-review, review-integrity-remediation |
| AR-2 CSV/XLSX 수식 삽입(D3) | 공통 | 문자열 '=1+1'→CSV 그대로·XLSX 수식 셀 | 후처리 | D3 | 해결 | 2026-10-03-harness-docraft-architecture-quality-review, review-integrity-remediation |
| AR-3 빈 JSON {} 입력 검증(H4) | 공통 | 거부→동기 200/비동기 completed(tier null) | 입력 | H4 | 미해결 | 2026-10-03-harness-docraft-architecture-quality-review |
| AR-4 재분석 완료 쓰기 덮어쓰기(D1) | 공통 | 새 parse 결과→늦은 구 parser가 OLD로 덮음 | 후처리 | D1 | 해결(작업 세대 소유권) | 2026-10-03-harness-docraft-architecture-quality-review, review-integrity-remediation |
| AR-5 완료 상태 저장 후 payload 실패(H1) | 공통 | 완료+결과 저장→completed/result=null | 후처리 | H1 | 해결(원자 저장) | 2026-10-03-harness-docraft-architecture-quality-review, review-integrity-remediation |
| AR-6 정답지 재채점 기준 불일치 | 공통 | 일관 점수→r9 99.40%/99.16%/97.32%(정답 정책 변경 후 재채점)로 기준 혼재 | 평가 | - | 해결(평가 스냅샷·별도 run) | 2026-10-03-harness-docraft-architecture-quality-review, review-integrity-remediation |
| MF-1 단일 페이지 70~100행 JSON 실패 | 세부내역서 | JSON 정상→finish_reason=stop인데 JSON 실패 | extract | - | 미해결(행 묶음 분할 제안) | 2026-10-03-model-fixed-table-algorithms |
| MF-2 같은 금액 다른 열·행 전체 누락·교정 오망침 | 공통 | 회귀 사례 유형(제안 문서, 실측 아님) | 미확정 | - | 미해결 | 2026-10-03-model-fixed-table-algorithms |
| DB-1 Docraft 장애 중 재판독 연결 실패 | 공통 | 재판독 값→23시간 Docraft 연결 실패로 ④'·①' 단계 건너뛰어 검토(unresolved) 비율 상승 | extract | 인프라 연계 | 해결(Postgres 접속 예산) | 2026-10-03-docraft-backend-too-many-clients |
| XD-1 | 세부내역서 | 기간을 한 칸에 찍은 '일자' 열: 시작·종료일자 각각→시작일자만 보고 종료일자에 시작일 복사(일자 차이 167칸 중 135칸) | extract | - | 미해결(권고 1, 수정 전) | 2026-10-02-extra-detail-validation.md |
| XD-2 | 세부내역서 | OCR이 '본인부담금공단부담금'을 한 줄로 붙임: 공단부담 값→공단부담 열 통째로 빈칸(열 배치 판별이 못 읽은 열을 없는 열로 간주) | extract | - | 미해결(권고 2) | 2026-10-02-extra-detail-validation.md |
| XD-3 | 세부내역서 | '수가코드·청구코드' 서식: 청구코드(EDI) 보존→버려짐(원내코드 후퇴와 같은 유형) | extract | - | 미해결(권고 2) | 2026-10-02-extra-detail-validation.md |
| XD-4 | 세부내역서 | 금액을 통째로 비운 응답·무너진 표: 게이트 검출→총액 있는 행만 세어 실패율 0으로 통과(게이트 빈틈) | 후처리 | - | 미해결(권고 3) | 2026-10-02-extra-detail-validation.md |
| XD-5 | 세부내역서 | 90·270° 회전 문서에서 rowmajor 머리글 열 판별 실패, 180°는 거꾸로 판별(원본 돌아간 좌표 사용) | 입력 | - | 해결(50cad6d, engine._turns·unturn) | 2026-10-02-extra-detail-validation.md |
| XD-6 | 세부내역서 | 표 교정(refine) 크롭을 원본 방향 그대로 전송→바로 선 방향 크롭 필요 | 입력 | - | 해결(c85e9c1) | 2026-10-02-extra-detail-validation.md |
| XD-7 | 세부내역서 | 회전 정답지 3건(a0·a2·a3): 정확도 49.6/49.8/77.2%→방향 정규화 후 92.6/87.6/79.8% | 입력 | - | 해결(a3은 별건 잔존) | 2026-10-02-extra-detail-validation.md |
| XD-8 | 세부내역서 | a3: 6행 중 3행을 asis·rowmajor 모두 누락(방향 문제 아닌 별도 원인) | 미확정 | - | 미해결 | 2026-10-02-extra-detail-validation.md |
| XD-9 | 세부내역서 | 옆으로 누운 합계 전용 쪽(image_17.tif): 방향 정규화 적용→놓침 1건 | 입력 | - | 미해결 | 2026-10-02-extra-detail-validation.md |
| XD-10 | 세부내역서 | asis: 2단 머리글에서 공단부담 값→본인부담 칸에 입력 | extract | - | 미해결(asis 경로) | 2026-10-02-extra-detail-validation.md |
| XD-11 | 세부내역서 | asis: 공단부담→본인부담 순서 서식에서 두 열 뒤바뀜 | extract | - | 미해결(asis 경로) | 2026-10-02-extra-detail-validation.md |
| XD-12 | 세부내역서 | asis: 명칭→코드 칸, 항목 칸에 명칭 복사 | extract | - | 미해결(asis 경로) | 2026-10-02-extra-detail-validation.md |
| XD-13 | 세부내역서 | asis: 긴 표를 중간에 끊음(49행 중 6행 누락) | extract | - | 미해결(asis 경로) | 2026-10-02-extra-detail-validation.md |
| XD-14 | 세부내역서 | 가산 문서에서 게이트 오발동(호출 1회 추가, 오발동 5건·해로움 1건) | 후처리 | - | 미해결(우선순위 낮음) | 2026-10-02-extra-detail-validation.md |
| XD-15 | 세부내역서 | 머리글 열 순서 판별 실패 15/98: 한 줄 4열 미만 6, 머리글 낱말 없음 5, 표 줄 상자 없음 4 | parse | - | 미해결 | 2026-10-02-extra-detail-validation.md |
| XD-16 | 세부내역서 | 일자 열 2건: 정답 일자→rowmajor 오답(asis 정답), 실행일자 정책 1건 보류 | extract | - | 결정대기(실행일자 정책) | 2026-10-02-extra-detail-validation.md |
| XD-17 | 세부내역서 | 여러 쪽 PDF 3건 length 오류(rowmajor·asis 모두 오류) | 입력 | - | 해결(후속 PDF 5건 행 복원: 아주대 0→330 등, log.md 10-03) | 2026-10-02-extra-detail-validation.md |
| IT-1 | 영수증 | 요양기관종류 `병원급` 등 기대→Docraft가 `V`만 반환(설명에 기호 목록을 늘어놓은 탓, 390i·400b) | extract | - | 해결(Docraft f668ac9, ENUMS 표준 4종) | 2026-10-02-institution-type-r3-followup.md |
| IT-2 | 영수증 | 45314 요양기관종류: Docraft `[✓]병원급`→하네스 `_drop_shared_evidence`가 근거 중복으로 기각 | 후처리 | - | 해결(335acb3 모호 출처 수용, 28/29) | 2026-10-02-institution-type-r3-followup.md |
| IT-3 | 영수증 | 43806 요양기관종류: Docraft 품질 SUSPICIOUS(no_source)로 미채택→병원급 | extract | - | 해결(r4 PASS) | 2026-10-02-institution-type-r3-followup.md |
| IT-4 | 영수증 | SA2019123039576 요양기관종류 병원급→의원급·보건기관(명칭 없음·신뢰도 0.91이라 의심 조건 미탐, Docraft 미호출) | 후처리 | - | 미해결(의심 문서만 Docraft 호출 결정의 한계) | 2026-10-02-institution-type-r3-followup.md |
| IT-5 | 영수증 | SA2019123045515 `고상급종합병원`→`상급종합병원` 표기 변형 | 후처리 | - | 해결(하네스 d 정규화) | 2026-10-02-institution-type-r3-followup.md |
| IT-6 | 영수증 | SA2019123043735 체크 표시 `[V]의원급·보건기관` 포함 값을 repaired 채택→일치→불일치 | extract | - | 해결(체크 표시 정규화·40f5afe·d8a4a62) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| LT-1 | 세부내역서 | 45314 표 요청 HTTP 408(184~278초)로 선별급여·끝수처리 행 누락(9칸 악화), 3022030712433802-1 분류명·급여구분 교정 불가 | 입력 | - | 해결(Docraft 298570b: 결과 공유·표 교정 병렬·OCR 동시성·시한, r9 실패 0) | 2026-10-02-docraft-read-latency-analysis.md |
| LT-2 | 세부내역서 | 3022030712433802-1 Docraft 분류명 채택 안 됨(22/22 기대): `_docraft_classes`가 `record["response"]`에서 빈 표를 받음(키 경로 변경) | 후처리 | - | 해결(r8 22/22) | 2026-10-02-aws-integrated-deploy-1002g.md |
| LT-3 | 영수증 | 202501021624239c(종합병원)·400b(병원급): Docraft 정답 PASS인데 판정 분기 9(mismatched)로 unresolved→의원급·보건기관 | 후처리 | - | 해결(31401fa) | 2026-10-02-aws-integrated-deploy-1002g.md |
| LT-4 | 영수증 | 400b 납부할금액 0→11000: 전액 수납 시 빈칸(0)을 규칙이 비정상 판정(PAYABLE 의미 문제) | 후처리 | - | 해결(cd1461a, 규칙셋 2026.09.20, 유사 5건 회귀 없음) | 2026-10-02-aws-integrated-deploy-1002j.md |
| LT-5 | 세부내역서 | 2303xxxx 서식 급여구분 66칸: 정답지 빈칸 vs 하네스 `열추출`(AO도 동일) | 평가 | - | 해결(정답지를 `열추출`로 통일, 이후 인쇄값만 정책으로 재정정) | 2026-10-02-aws-integrated-deploy-1002h.md |
| LT-6 | 세부내역서 | `항목`에 EDI명칭을 베낀 값(불일치)→비움(누락으로 판정 변경) | 후처리 | - | 해결(12be3da) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| LT-7 | 세부내역서 | 20250102091737a3 소수점 142680.75 등: 정답지가 소수점을 버린 값이라 하네스 출력과 불일치 | 평가 | - | 해결(후속 정책 소수 유지·정답지 정정, golden-benefit-printed-only) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| LT-8 | 영수증 | 합계 행 없는 서식(2303315388 비급여총액·비급표현-KJM02605): 합계 값 부재→unresolved(분기 9) | extract | - | 해결(R-0710-PARTITION, dev 41151a5) | 2026-10-02-aws-redeploy-golden59-rerun.md |
| LT-9 | 세부내역서 | 103201·103300 투여량 빈칸→열 추출로 보완(개선 10칸), 43183 납부할금액 0 유지 | extract | - | 해결 | 2026-10-02-aws-integrated-deploy-1002d.md |
| LT-10 | 세부내역서 | EDI명칭 셀 0행에 검증 표식(harness 블록) 미부착(검증 대상 아닌 셀) | 후처리 | - | 결정대기(수정 방식 사용자 확인) | 2026-10-02-aws-integrated-deploy-1002d.md |
| RC-1 | 공통 | 합성 촬영 파라미터: 실측 분포→관측 근거 없이 수작업 범위 선택(원본 6,281건 계측), 기울기 목표를 추가 변환으로 해석해 원래 기울기 잔존 | 평가 | - | 해결(feat/capture-calibration, 보정 모드) | 2026-10-04-real-capture-distribution-calibration.md |
| SR-1 | 공통 | 실문서 엣지 22건 시각 선정: 원근·90도 회전·저대비·접힘·손가락 가림·직인/필기가 값 위에 겹침·약 50행 밀집 표·여러 쪽 일부 쪽(생성기 구현 여부와 별개) | 입력 | - | 미해결(생성기 반영 일부) | 2026-10-03-synthetic-reference-samples.md |
| SR-2 | 공통 | 엣지 기준 목록(회전·잘림·표 쪽 넘김·행 분할·0과 빈칸 혼재·소수·음수·날짜 형식 혼재·직인·주민번호 가림·병명 10개 이상 등): 사례별 최소 3장 | 입력 | edge_cases.yaml 메커니즘(`orientation`·`region_loss`·`numeric_format` 등) | 미해결(레지스트리 단계 구현 중) | 2026-10-03-synthetic-dataset-codex-작업지시서.md |
| RT-1 | 공통 | 실문서 합성 검수: 팩스 합계 불일치, 날짜/가림 자릿수 오류, 실문서 DPI (0,0) 메타로 보고서 중단 | 입력 | - | 해결(내부 검수 탈락 후 보강) | 2026-10-03-synthetic-pipeline-review21.md |
| TR-1 | 공통 | 하네스 작업 조회: DB 장애인데 404로 보임, Docraft 작업 로그에서 rid 소실, 오류를 경고 한 줄로 삼킴 | 후처리 | - | 해결(503·rid 전파·exc_info, 6efbd1d·81d98a8) | 2026-09-29-request-trace-logging.md |
| AG-1 | 공통 | 보강 지시서가 든 실제 오류: `AA254`가 일자로 잘못 매핑 | extract | - | 미확정(회귀 테스트 요구) | parse-extract-보강-작업지시서.md |
| RE-열밀림 | 영수증 | 비급여 값이 이웃 key 선택진료료로 들어감(열 밀림, 머리글 온전 3건은 파서 머리글이 병합 셀로 뭉개짐) → 파서 격자 열 되돌림은 머리글 온전할 때만 동작, 아니면 합계 대조 | parse | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-맞바뀜 | 영수증 | 이웃 금액 열 통째 맞바뀜(본인↔공단, 선택진료료↔선택진료료외) → 합계 행과 맞을 때만 되돌림 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-세부급여복사 | 세부내역서 | 급여구분=급여 행의 급여 칸은 null이어야 하나 총액이 복사됨(오탐 240건) → 복사값 비움 | 후처리 | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-단가투여량열 | 세부내역서 | 머리글에 없는 단가·투여량 열 값이 채워짐(fp 36) → 비움 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-EDI밀림 | 세부내역서 | 명칭이 EDI코드 열로 밀림 → 원내코드 자리 코드를 EDI코드로 이동 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-외래종료일 | 영수증 | 외래 진료종료일 빈칸 → 진료시작일로 채움(당시 라벨 17건 중 16건 동일) | 후처리 | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-급여합계 | 세부내역서 | 인쇄되지 않은 급여 합계를 행을 더해 계산해 채우거나 비급여 포함 총액을 급여총액에 옮김 → 비움 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-공단총액오독 | 영수증 | 공단부담총액 오독 → 합계 행이 행 합과 맞으면 합계 행 값으로 교체 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-산술불일치 | 세부내역서 | 단가×투여량×횟수×일수 ≠ 총액, 본인+공단 ≠ 총액 → row_arith 경고(Docraft 8건 모두 실제 오류) | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-합계불일치 | 영수증 | 납부금액 합·진료비총액=환자+공단 불일치 → sum_mismatch 경고(Docraft 14건 중 실제 오류 8건) | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-날짜역전 | 공통 | 입원>퇴원, 시작>종료, 진단·초진>발급 날짜 선후 역전 → bad_date 경고 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-주민번호불일치 | 소견서 | 주민번호와 성별·생년월일 불일치(Docraft 3건 중 2건 실제 오류) → id_mismatch 경고 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-등록번호형식 | 공통 | 등록번호에 한글·날짜 시작, DRG번호에 영문 없음 → 비움 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-의사명조각 | 진단서 | 의사명에 진료과·서식 문구 조각(치과, 또는인) → 비움 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-머리글행 | 세부내역서 | 머리글 행·빈 행이 데이터 행으로 들어옴 → 삭제(영수증은 0원 인쇄 행이 있어 제외) | parse | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-항목명접두 | 영수증 | 항목명에 분류 칸 이름이 붙음(필주사료_약품비, 선택항목_CT진단료) → 뗀 결과가 표준명일 때만 제거 | parse | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-치료내역중복 | 진단서 | 치료내역이 수술·검사내역 문장과 중복 → 만들지 않음 | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-저품질스캔 | 세부내역서 | 코드 대부분이 마스터에 없고 산술도 깨진 저품질 스캔(표가 추출마다 흔들림, 한 장에서 전액본인부담 오탐 18건) → low_quality 경고 | 입력 | - | 미해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-독립급여열오탐 | 세부내역서 | 머리글상 독립 급여 열이 있는 두 문서에서 총액으로 급여를 채워 오탐 36건(라벨은 급여 값 0건) → 총액 계산 채움 제거 | 후처리 | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-항목명오류57 | 영수증 | 항목명 오류 57건 중 이름 규칙으로 고친 것은 8건, 행 누락 22·연쇄 밀림 20·파서 오복원 2·한두 글자 오독 5(오독은 별칭 위험으로 미반영) | 미확정 | - | 미해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-행누락 | 영수증 | 항목 행 누락 22건과 연쇄 밀림 20건은 룰 범위 밖 | extract | - | 미해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-급여프롬프트 | 세부내역서 | 모델이 급여구분=급여 행에 총액을 채움(raw 급여 오탐 240→93) → 프롬프트 변경(총액 계산 금지, 묶음 머리글이면 null) | extract | - | 해결 | Docraft/2026-09-23-rules-edge-cases.md |
| RE-진단일버린룰 | 소견서 | 진단일 근거 없으면 비움 룰은 fp 5건 제거하나 맞는 값 3건 손실 → 폐기 | 후처리 | - | 결정대기 | Docraft/2026-09-23-rules-edge-cases.md |
| PR-출력그룹위치 | 영수증 | 자동 통과 오류 18칸이 출력 그룹 위치 오류(AO가 빈 필드의 그룹 위치를 잘못 둠) | extract | - | 미해결 | Docraft/2026-09-25-edge-speed-accuracy-priorities.md |
| PR-항목명오독 | 영수증 | 두 판독이 같은 항목명을 같이 오독한 오류 8칸(한 글자 누락, 유일 표준명이면 보정 제안) | extract | RCP-003 | 미해결 | Docraft/2026-09-25-edge-speed-accuracy-priorities.md |
| PR-헤더미검출 | 세부내역서 | 파서 머리글을 못 찾아 DETAIL.EMPTY_CELL 미작동 → 투여량이 비워지지 않는 사례 남음 | parse | - | 미해결 | Docraft/2026-09-25-edge-speed-accuracy-priorities.md |
| PR-괄호음수 | 영수증 | 금액 (3,000) → -3000 기대, 현재 양수로 읽음(앞의 - 와 △ 만 음수) | 후처리 | NRM-006 | 미해결 | Docraft/2026-09-25-edge-speed-accuracy-priorities.md |
| PR-납부금액검산 | 영수증 | 납부할금액 = 환자부담총액 − 이미납부금액 검산식 없음 | 후처리 | RCP-004 | 미해결 | Docraft/2026-09-25-edge-speed-accuracy-priorities.md |
| PR-발병일 | 진단서 | 발병일·기재 입원일수 필드가 스키마에 없어 날짜 순서·입원일수 검산 불가 | 후처리 | ADM-004 | 미해결 | Docraft/2026-09-25-edge-speed-accuracy-priorities.md |
| LV-분류오류 | 세부내역서 | 세부내역서→진료비영수증 AO 오분류 6건(환자성명과 환자정보-성명이 같은 값으로 두 줄), 소견서→진단서 2건 → Harness 제목 OCR 재분류로 8건 중 7건 탐지, 놓침 1·오탐 1 | 입력 | - | 해결 | label_veiwer/2026-09-29-doc-type-mismatch.md |
| LV-분류놓침 | 공통 | Harness 재분류가 제목을 못 읽은 오분류(kept)는 검수자가 문서 종류를 고쳐야 드러남 | 입력 | - | 미해결 | label_veiwer/2026-09-29-doc-type-mismatch.md |
| LV-진단소견분류 | 소견서 | 진단서·입퇴원확인서·소견서는 정답지 스키마가 같아 템플릿 교체로 오분류가 안 바뀜 → 분류 채점으로만 드러남 | 평가 | - | 해결 | label_veiwer/2026-09-29-doc-type-mismatch.md |
| LV-JSON보기비어있음 | 공통 | 편집 탭 JSON 보기 textarea 내용이 비어 있음 → el()이 value를 setAttribute로 넣던 것 수정 | 평가 | - | 해결 | label_veiwer/2026-09-29-edit-tab-usability.md |
| LV-표머리글가림 | 세부내역서 | 19열 표 머리글이 보이지 않음(열 36px로 눌림) → 열 폭 72~220px | 평가 | - | 해결 | label_veiwer/2026-09-29-edit-tab-usability.md |
| LV-불일치개수 | 공통 | 사이드바 불일치 27과 탭 비교 14로 기준 불일치 → util.isMismatch() 하나로 통일 | 평가 | - | 해결 | label_veiwer/2026-09-29-edit-tab-usability.md |
| E2E-1.1 | 세부내역서 | 비급 구분 열 서식: 정답지가 비급·빈칸·100% 그대로 → 비급여/급여/급여 로 13칸 수정(100% 전액본인부담 정보는 별도 필드 필요) | 평가 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.2 | 세부내역서 | 실시일 열에 입원기간이 인쇄된 서식: 시작일자·종료일자 20221229·20230103 기대, 정답지 초안이 빈칸으로 28칸 오류 → 정답지 수정 | 평가 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.3 | 세부내역서 | 병실 칸이 비면 옆 진료과(외과, 내과혈액종양)를 병실로 읽음 → 진료과 패턴이면 비움(DETAIL.WARD) | extract | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.3b | 세부내역서 | Docraft가 빈 병실에 외래를 채우나 다른 문서는 병실 칸에 외래가 실제 인쇄돼 룰로 구분 불가 | extract | - | 결정대기 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.4 | 세부내역서 | 섹션 제목 행(01.진찰료) 아래 데이터 행 항목이 EDI명칭 복사로 채워짐 → 제목으로 교체(DETAIL.SECTION_ITEM), 항목 열이 병합 셀인 문서는 대상 제외 | extract | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.5 | 세부내역서 | 총투·수량 머리글은 횟수 열이 따로 있을 때만 투여량. 투여량 오류 46→38칸 감소에 그침(Docraft가 1을 읽었으나 머리글 셀에서 투여량 낱말을 못 찾아 EMPTY_CELL 미작동, 한 문서는 추출에 투여량 값 없음) | parse | - | 미해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.6 | 세부내역서 | EDI코드 칸에 인쇄된 - 때문에 채점기가 같은 행을 정답에만/결과에만 있는 행으로 갈라 셈 → 정답지의 - 를 빈칸으로 처리 | 평가 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-1.7 | 세부내역서 | 원내코드 B1020B·NPIS0003·MX122s1의 S·B를 5·8로 바꿔 코드가 망가짐 → 마스터로 확인될 때만 변환 | 후처리 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-2.1 | 세부내역서 | 급여구분 열이 없는 서식에서 AO가 자리표시 값 열추출을 모든 행에 넣음 → 급여 금액 열이면 급여, 금액 없는 행은 비움(DETAIL.ITEM_CLASS) | extract | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-3.1 | 세부내역서 | Judge가 표를 다시 쓰며 AO와 Docraft가 모두 비운 칸에 42, 18 같은 금액을 지어냄 → 두 읽기가 같은 칸은 그 값으로 복원(verify._agreed) | 후처리 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-3.2 | 세부내역서 | AO가 투여량 열을 비우고 Docraft가 읽으면 Judge가 비우는 쪽 선택 → 파서 머리글로 열이 확인될 때만 Docraft 값을 채움 | 후처리 | - | 미해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-4.1 | 세부내역서 | 사고발생일자: 정답지는 인쇄된 조회기간 시작일 20190331, Docraft는 첫 명세 날짜 20220303 | extract | - | 결정대기 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-4.2 | 세부내역서 | 항목의 섹션 번호 포함 여부가 문서마다 섞여 정답지 기준과 불일치 → 채점기가 번호를 떼고 비교 | 평가 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-5.흐린사진 | 세부내역서 | 흐린 사진에서 원내코드 FD001이 FDOO1로 읽히고 제증명료 첫 행이 소계 행과 섞임 | 입력 | - | 미해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| E2E-5.OCR422 | 공통 | 서버 재부팅 직후 PaddleOCR VLM 기동 전 /api/verify가 422 PaddleOCR 원격 처리 실패(HTTP 500) → 몇 분 뒤 재전송 | 입력 | - | 해결 | Docraft/2026-09-24-e2e-edge-cases.md |
| RI-D1 | 공통 | 재추출 대기 중에도 이전 result 승인·수정이 가능하고 죽은 워커가 완료·실패를 덮어씀 → 작업 세대·소유권 도입 | 후처리 | D1 | 해결 | Docraft/2026-10-03-review-integrity.md |
| RI-D3 | 공통 | CSV/XLSX 내보내기에서 값·열 이름이 수식으로 해석됨 → 수식 시작 문자에 작은따옴표, XLSX 문자열 셀 강제 | 후처리 | D3 | 해결 | Docraft/2026-10-03-review-integrity.md |
| RI-D5 | 공통 | 실패 페이지 그룹을 제외하고 병합하나 부분 성공 사실을 문서·화면·내보내기·승인이 모름 → partial 플래그와 승인 금지 | extract | D5 | 해결 | Docraft/2026-10-03-review-integrity.md |
| KV-1영수증항목 | 영수증 | 항목내역.항목 오류 159건(행 매칭 실패, 세분 항목명 입원료_1인실 vs 단순화 입원료)과 연쇄 75건 → 실제 원인은 _receipt_table이 파서 복원 행을 모델 행과 짝짓지 않고 뒤에 끼워 넣어 위치가 밀림 | 후처리 | - | 해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-2EDI명칭 | 세부내역서 | EDI명칭 오류 129건(모티리톤/모티리론 같은 1~2글자 OCR 오인식) → 코드 사전 교정 제안 | parse | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-3단가 | 세부내역서 | 단가 오류 79건(모델 추출 오탐, raw에서도 fp 39) | extract | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-4투여량 | 세부내역서 | 투여량 오류 69건(열 밀림으로 단가·총액 값 유입) → 산식 위반으로 검출 제안 | extract | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-5시작일횟수 | 세부내역서 | 시작일자·횟수 50건 이상 오류(행 순서 뒤바뀜, raw→rules 회귀 4건) | extract | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-6병명 | 진단서 | 병명 오류 33건(대부분 OCR 글자 오류, 일부 라벨 오류) | parse | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-7fill오매핑 | 소견서 | 주소·병원주소·진단일·의사명 fp 약 35건(_fill 라벨 오매핑, raw→rules 회귀 22건 중 18건) | 후처리 | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-8진료기간 | 영수증 | 진료시작일·종료일이 같은 라벨 진료기간을 쓰고 _date가 첫 날짜만 취해 둘 다 시작일로 채워짐 | 후처리 | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-9다페이지판정 | 세부내역서 | Judge가 1페이지 이미지만 첨부해 2페이지 이후 분쟁이 근거 없이 판정됨 | 후처리 | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-10부분포함 | 공통 | rules.same의 4자 이상 부분 포함이 AO·Docraft 합의로 쓰여 다른 값이 일치로 확정되고 Judge를 건너뜀 | 평가 | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-11성명동의어 | 공통 | LABELS 동의어 성명이 의사명·환자성명 등 4필드에 중복되고 _fill이 첫 후보를 채택 | 후처리 | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-12소계제거 | 영수증 | _totals가 소계 행을 무조건 제거하고 모델이 채운 틀린 합계를 합계 행 값으로 덮지 않음 | 후처리 | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-13청크분할 | 세부내역서 | _page_chunks가 표 블록 중간에서 청크를 나누고 병합 중복 제거가 완전 일치에만 의존, 청크 재시도 없음, VISION_MAX_IMAGES=4 초과 페이지는 이미지 없음 | extract | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-고객비급여급여 | 영수증 | 고객 보고 비급여_급여_오추출됨: 급여 칸 없는 서식에서 비급여 9,010,000이 급여로 들어가고 합계 행도 따라감 | extract | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-고객파싱에러 | 영수증 | 고객 보고 파싱_에러: 진찰료 셀에 두 행 금액 병합, 주사료~영상진단료 5항목이 한 셀 | parse | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-고객항목명누락 | 영수증 | 고객 보고 항목명_누락: 금액이 전부 빈 CT·PET·초음파·보철교정 항목명 누락 | extract | - | 미해결 | Docraft/2026-09-22-kv-accuracy-review.md |
| KV-사고발생일자 | 진단서 | 진단서·소견서에 사고발생일자 필드가 없음(harness는 진단일·검사일·수술일 최솟값 파생) | 미확정 | - | 결정대기 | Docraft/2026-09-22-kv-accuracy-review.md |
| PQ-TIF-GIF | 공통 | 확장자 .TIF인 실제 GIF 이미지가 OCR 422로 실패 → 이미지 디코딩 후 EXIF 방향 반영 RGB PNG로 정규화(e03330a) | 입력 | - | 해결 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-머리글우선 | 영수증 | 병합 영수증 표에서 상위 제목 전액 본인부담이 하위 공단부담금 열보다 우선돼 금액이 다른 열로 이동(영수증 920→948/1026) → 하위 구체 열명 우선 | parse | - | 해결 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-급여0null | 영수증 | 묶음 제목 급여 57·비급여 82의 139셀을 schema는 0, 기존 rules는 null로 처리해 strict 점수 하락 | 평가 | - | 결정대기 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-FP13 | 소견서 | 신규 15건 fp 증가 13건: 주민번호→성별·생년월일 파생 6, 원문 라벨 보충 차트번호 2·주소 1, 서술→치료명 4 | 후처리 | - | 결정대기 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-비급여포함총액 | 진단서 | 비급여 포함 총진료비를 급여총액으로 넣은 라벨 오류(진단서 2·세부내역서 2 교차 검수) → 별도 급여합계 근거 없으면 null | 평가 | - | 해결 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-OCR역할 | 공통 | 값이 OCR에 존재하나 다른 날짜·금액 역할을 고른 오류가 PASS로 남음, OCR이 놓친 올바른 값은 RECHECK | extract | - | 미해결 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-변형 | 공통 | 회전·흐림·중앙 가림 변형에서 strict 일치 410→303·311·302로 하락(rules 일치값은 485~488로 유지) | 입력 | - | 미해결 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-페이지수 | 공통 | PaddleOCR가 요청과 다른 페이지 수를 반환해도 일부 성공으로 숨겨짐 → ParseError | parse | - | 해결 | Docraft/2026-09-27-parse-extract-quality.md |
| PQ-97 | 공통 | 전체 필드 정확도 97% 목표 미달(35건 silver loose 93.05%·strict 83.81%) | 평가 | - | 미해결 | Docraft/2026-09-27-parse-extract-quality.md |
| TE-사고발생일 | 진단서 | 사고발생일이 인쇄되지 않았는데 진료 시작일에서 파생한 값을 직접 근거로 표시 → 직접 확인으로 표시하지 않음, 파생 근거 계약 필요 | 후처리 | - | 결정대기 | Docraft/2026-09-27-typed-evidence.md |
| TE-빈칸교정 | 영수증 | 오독값을 null로 고치는 빈 셀 교정이 합성 회귀에서만 검증, 자연 표본 3건은 검증된 빈 셀 0개 | parse | - | 미해결 | Docraft/2026-09-27-typed-evidence.md |
| TE-병합머리글 | 영수증 | 기존 OCR·격자 파서가 좌표를 안 주거나 병합 머리글을 오독하면 typed 근거 미생성, 영수증 2필드가 별칭 라벨 거리 검사로 검토 상태 | parse | - | 미해결 | Docraft/2026-09-27-typed-evidence.md |
| NC-열밀림 | 영수증 | 가변 인쇄값 전체가 인쇄 라벨·격자보다 한 행 위에 놓여 금액 열이 한 행씩 밀려도 exact 근거로 보임 → 두 날짜 라벨의 공통 오프셋으로 확인 후 합계식으로 교정 | parse | - | 해결 | Docraft/2026-09-28-natural-corrections.md |
| NC-금액오독 | 영수증 | 금액 오독 3개와 명시적 빈칸의 0 오추출 2개(3문서 5필드) → 독립 원문 판독과 일치하게 교정 | extract | - | 해결 | Docraft/2026-09-28-natural-corrections.md |
| NC-성명오교정 | 공통 | 확대 예산 재처리에서 성명을 오교정 1건(OCR 오독을 모델이 반복) → 전체 이미지 재판독에서 OCR 입력 제거, 재실행 오교정 0 | extract | - | 해결 | Docraft/2026-09-28-natural-corrections.md |
| NC-미교정 | 영수증 | 두 날짜 anchor 오프셋이 다르거나 라벨·숫자 대응이 복수이거나 총액식이 미등록인 문서는 자동 교정 불가 | extract | - | 미해결 | Docraft/2026-09-28-natural-corrections.md |
| CORR-01 | 진료비영수증 | 오독 항목명 `진칠료`/`식데` -> 표준명 `진찰료`/`식대` 기대, AO 값이 그대로 원장에 적재됨(교정이 value에 닿지 않음) | 후처리 | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-02 | 진료비영수증 | 금액 열 두 개가 통째로 바뀐 표: 맞바꿈 기대 -> AO 값 유지(합계 행과 불일치) | extract | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-03 | 세부내역서 | 항목이 EDI명칭을 베낀 행: 섹션 제목(`01.진찰료`) 기대 -> EDI명칭 복사값 | extract | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-04 | 세부내역서 | 환자정보(병실)에 진료과 이름 유입: 빈 값 기대 -> 진료과명 | extract | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-05 | 세부내역서 | 서식에 없는 급여구분을 추정 채움: 빈칸 기대 -> `급여` 오검출 15칸(정확도 70.4%로 하락, 이식 제외) | 후처리 | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-06 | 세부내역서 | 표준명이 아닌 항목명에서도 기호 제거: `처치및수술료_검사료` 유지 기대 -> `처치및수술료검사료`(EDI명칭 17칸 오분류) | 후처리 | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-07 | 세부내역서 | Docraft 재판독과 AO 행 짝짓기 실패: 짝 기대 -> 24행 vs 20행 중 짝 0(시작일자 공란, 코드가 EDI코드/원내코드로 갈림) | extract | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-08 | 세부내역서 | AO 열 밀림: 일수 값이 횟수 칸에 들어가고 일수 빈칸 -> 칸 하나씩 재검증하면 규칙이 또 실패해 교정 불가 | extract | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-09 | 진단서 | 사고발생일자 규칙(R-CERT-ACCIDENT)이 입력 칸(진단일/수술일자)을 붙잡음: AO 맞은 칸 43개가 unresolved | 후처리 | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-10 | 세부내역서 | 행 규칙(ROWSUM/UNITMUL)이 맞는 칸까지 같은 행 전체 미해결로 묶음(미해결 중 실제 AO 오류 약 14%) | 후처리 | - | 미해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-11 | 세부내역서 | 약품비 총액 0 행의 UNITMUL 오판 2행 | 후처리 | - | 미해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-12 | 진료비영수증 | 합계 행 CALC 오판 6행 | 후처리 | - | 미해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| CORR-13 | 공통 | Docraft null/짝 없는 행을 반대 증거로 사용: 멀쩡한 값이 미해결(영수증 161칸 중 97칸 불일치) | 후처리 | - | 해결 | harness-v2/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md |
| UI-01 | 공통 | 08(UI response) 입력 시 평탄화가 extracted_*만 읽어 문서 0건 -> verdict undetermined | 입력 | - | 해결 | harness-v2/2026-09-14-UI-response-입력과-bbox-잘림판정.md |
| UI-02 | 공통 | 표 잘림(crop) 판정을 필드 부재가 아닌 bbox 가장자리 접촉으로 하도록 변경(잘린 실물 없어 임계 EDGE_MARGIN 1% 보정 전) | 입력 | - | 결정대기 | harness-v2/2026-09-14-UI-response-입력과-bbox-잘림판정.md |
| UI-03 | 공통 | 08 샘플: 빈 값은 token_bbox null이라 좌표 없음(세부내역서 표 114칸 중 66칸만 좌표) | 입력 | - | 미해결 | harness-v2/2026-09-14-UI-response-입력과-bbox-잘림판정.md |
| UI-04 | 공통 | `not_extracted`/`unverified`/`confirmed_by_operator` 플래그를 판정에 사용하지 않음 | 후처리 | - | 미해결 | harness-v2/2026-09-14-UI-response-입력과-bbox-잘림판정.md |
| BENCH-01 | 세부내역서 | EDI 패밀리 조회 수정 후 p95 128ms -> 501ms(미발견 코드마다 시트별 커넥션 7회 fan-out) | 후처리 | - | 해결 | harness-v2/2026-09-09-규칙검증-정확도속도-측정.md |
| BENCH-02 | 공통 | 마스터 미적재 상태 측정이 운영 성능 대변 불가(4.9ms vs 적재 92ms, 규칙 조용히 not_applicable) | 평가 | - | 해결 | harness-v2/2026-09-09-규칙검증-정확도속도-측정.md |
| MST-01 | 세부내역서 | EDI 코드 `AA254`/`AA254030`이 마스터에 있는데 MASTER_0710_08 fail(룰셋 system_id `EDI`가 적재명 `EDI:의치과_급여`와 불일치) | 후처리 | - | 해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-02 | 약제비영수증 | 룰셋 마스터명 `EDI_약국_급여_전체`가 존재하지 않는 이름 -> 조회 0건 | 후처리 | - | 해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-03 | 세부내역서 | 9자리 원내(약품)코드 13건이 마스터 미존재로 fail + 역유추 전수 스캔으로 문서당 최대 10.9초 -> 검증 범위 밖 not_applicable | 후처리 | - | 해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-04 | 세부내역서 | 문서 명칭 `재진진찰료-의원,보건의료원 내 의과` vs 마스터 `재진진찰료-의원` 유사도 0.64로 MASTER_0710_09 fail 4건(정상 표기 오탐 의심) | 후처리 | - | 결정대기 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-05 | 세부내역서 | 코드 `MCR301` 전 시트 미존재 fail | 미확정 | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-06 | 소견서 | KCD `I6788` 미존재(유사 `I678*` 존재, OCR 오독 의심) | parse | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-07 | 입퇴원확인서 | KCD `S0600B` 미존재(유사 `S060*` 존재, OCR 오독 의심) | parse | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-08 | 입퇴원확인서 | `S300`/`골반의 타박상` 코드-명칭 조합 불일치(MASTER_KCD_04) | extract | - | 해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-09 | 진단서 | 불완전 코드 `K58` 단독 기재(하위 세분 코드 필요, MASTER_KCD_09 warn) | extract | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-10 | 진료비영수증 | 전액본인부담 열이 공단부담금 열의 복제(진찰료/처치및수술료/수액/합계 4행, CALC_AC029_11 16건, 총액 등식 9건) | extract | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-11 | 진료비영수증 | 합계 행 선택진료료외 미판독(0인데 수액 40,000 존재, CALC_AC029_12 3건) | extract | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| MST-12 | 세부내역서 | 12행 총액 미판독(0인데 부담합 18, 단가x횟수x일수 135, ROWSUM/CALC_0710_02 11건) | extract | - | 미해결 | harness-v2/2026-09-09-마스터-적재-스모크-검증.md |
| KCD-01 | 진단서 | 선두 숫자 KCD `0990`/`0339`/`0828` -> `O990`/`O339`/`O828` 기대, 원장 미존재로 not_found(N5 치환) | parse | - | 해결 | harness-v2/2026-09-14-KCD-정규화-N4N5와-동의어-사전.md |
| KCD-02 | 진단서 | 선두 `0` 치환이 `D`/`Q` 오독일 수 있어 병명과 모순되면 교정 보류(합의에 없는 조건, 확인 필요) | 후처리 | - | 결정대기 | harness-v2/2026-09-14-KCD-정규화-N4N5와-동의어-사전.md |
| KCD-03 | 진단서 | 병명 `좌측 슬관절 퇴행성 관절염`(M171) 원장 명칭과 불일치(mismatch 0.29) -> 3단 판정으로 통과 | extract | - | 해결 | harness-v2/2026-09-14-KCD-정규화-N4N5와-동의어-사전.md |
| KCD-04 | 진단서 | 한 칸에 복수 코드(SPLIT) 미처리 | extract | - | 미해결 | harness-v2/2026-09-14-KCD-정규화-N4N5와-동의어-사전.md |
| KCD-05 | 진단서 | `E785 고시질혈증`/`N390 요로감염` 명칭 mismatch(사전만으로 미해결, 후속 3단 판정으로 해결) | extract | - | 해결 | harness-v2/2026-09-14-KCD-정규화-N4N5와-동의어-사전.md |
| KCD-06 | 입퇴원확인서 | `S300 골반의 타박상` 명칭 축약 기재: warn -> 3단 판정 pass(고객 확정 전, 축약 기재 §19-19) | extract | - | 결정대기 | harness-v2/2026-09-14-KCD-동의어사전-제거와-명칭-3단판정-역방향조회.md |
| KCD-07 | 진단서 | `R634 (주상병)이상체중감소`/`J157` 규칙은 pass인데 마스터 증거는 name_mismatch((주상병) 접두 미제거) | 후처리 | - | 해결 | harness-v2/2026-09-14-KCD-동의어사전-제거와-명칭-3단판정-역방향조회.md |
| KCD-08 | 진단서 | 코드 없이 병명만 있는 경우 역방향 조회: `좌측 고관절 골관절염`->M169 inferred, `좌측유방암` ambiguous(후보 117건), `보행장애` unresolved | extract | - | 해결 | harness-v2/2026-09-14-KCD-동의어사전-제거와-명칭-3단판정-역방향조회.md |
| KCD-09 | 진단서 | 의료 동의어 부재: `보행장애`<->`걷기장애`(R262) 류는 unresolved | extract | - | 미해결 | harness-v2/2026-09-14-KCD-동의어사전-제거와-명칭-3단판정-역방향조회.md |
| KCD-10 | 진단서 | 검토 ④ 느슨함: 병명이 틀리고 수술 부위 토큰만 같아도 pass 가능 | 후처리 | - | 미해결 | harness-v2/2026-09-14-KCD-동의어사전-제거와-명칭-3단판정-역방향조회.md |
| KCD-11 | 진단서 | KCD-8 PDF 파싱 결함: 3단위 머리 누락 2,044건, 한글/영문 경계 소실, 대표명 영문 꼬리 오염 1,074건(사전은 이후 제거) | 입력 | - | 해결 | harness-v2/2026-09-14-KCD-정규화-N4N5와-동의어-사전.md |
| V59-01 | 세부내역서 | 인쇄된 소계/계/합계/끝수처리조정금액 행이 최종 결과에서 삭제(221곳, KEEP_TOTALS가 영수증만 보존) | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-02 | 세부내역서 | 같은 이름 행(`이학요법료` 날짜 블록별 3행)의 금액 뒤섞임 32곳 + 출력 셀 자리번호 정렬로 뒤쪽 행이 다른 행 셀 승계 | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-03 | 세부내역서 | `원내코드`가 이웃 행으로 밀림(`SA2020010683384_...200`) | extract | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-04 | 세부내역서 | 약품명 교정 오류 `코대원포르테시럽`->`코데핀포르테시럽`, `Level 8`->`Level B`, EDI코드 구분자 표기, 분수 `3/8`->`3/4`, EDI코드 글자 오독 | extract | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-05 | 세부내역서 | 급여구분 `열추출`(339회)->`급여`/`비급여` 기대: AO 자리표시 값, 금액 열로 정하고 불가하면 경고(190행 일치, 30행은 열추출 유지) | extract | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-06 | 세부내역서 | 금액 소수점 소실 `954.5`->`9545`, `19160.0`->`191600` | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-07 | 세부내역서 | 원내코드/EDI코드 관례 충돌: AO는 코드 열 하나인 서식에서 EDI코드에만, 둘이면 양쪽에 같은 코드(Judge 교정 표만 원내코드 비움) -> AO처럼 유지 결정 | 평가 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-08 | 세부내역서 | 다쪽 문서에서 요약 합계가 제공된 쪽에 없어 unclear 15곳 | 입력 | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-09 | 세부내역서 | `끝수처리 조정금액`을 `공수처리 조정금액`으로 오독해 급여구분 비어 있음(1행) | parse | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-10 | 진료비영수증 | 합계 보조가 합계식만 맞는 Docraft 표 선택: 합계 값이 `예약진찰료` 행, `제증명/기타` 값이 `선별급여` 행에 들어감(`202501021624239c`) -> 출력 셀 정렬 버그 착시로 판명 | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-11 | 진료비영수증 | 금액산정 상자 행 밀림: `납부할금액`/`이미납부한금액`/`납부한금액_현금`에 이웃 칸 값(Judge가 채택) | extract | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-12 | 진료비영수증 | 인쇄상 빈 `납부할금액` 칸에 다른 합계로 계산한 값(예: 11,000) 채움 | extract | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-13 | 진료비영수증 | 항목명 `전혈및혈액성분제재료`(인쇄 그대로)를 오독 교정이 `제제료`로 변경 | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-14 | 진료비영수증 | 항목명 오독 `한약접약`/`치료재대`/`보수처리조정금액`/`재활및물리치료`/`정맥수가원화외료`/`제층료`/`65세이상등경감`(일부 교정, 두 글자 이상 오독은 미교정) | parse | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-15 | 진료비영수증 | 한방 문서 `-6` 부호 누락, 음수 `-42,360` 부호 삭제 | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-16 | 진료비영수증 | 누락 행 보충이 오독 이름 `치료제료다`를 끼워 `치료재료대`와 중복 행(`재중명`/`진단시및제중명료`/`타` 3건 방지) | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-17 | 진료비영수증 | 한방 선택항목 행을 Docraft 추출이 아예 뽑지 않음(이름 교정을 실문서로 확인 못함) | extract | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-18 | 진료비영수증 | `SA2019123157847_...390b` 공단부담총액 0->45,642(R-AC029-BURDEN fail) 해소, `202501020959270c` 비급여->급여 8곳 교정 | extract | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-19 | 공통 | AO가 문서유형을 코드값(`Y000701200`)으로 내고 필드 0개 추출(1건) -> doc_type 지정 필요 | 입력 | - | 미해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-20 | 공통 | /api/verify 동기 호출이 이벤트 루프 전체 차단, 긴 문서 nginx 300초 504 | 후처리 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| V59-21 | 세부내역서 | 정답 라벨에 집계 행 없어 집계 행 삭제가 평가에 드러나지 않음 | 평가 | - | 해결 | Docraft/2026-09-23-verify-test-0922.md |
| VER-01 | 공통 | Judge가 `R63.4`/`2022/05/17` 같은 형식 차이만 있는 값을 corrected로 냄 -> rules.apply 재정규화로 재분류 | 후처리 | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-02 | 진단서 | 주민번호 없을 때 성별이 항상 `남`이 되던 버그(성별 9->0) | 후처리 | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-03 | 세부내역서 | Judge가 환자정보(입통원구분)에 환자구분 `건강보험` 입력 | extract | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-04 | 진료비영수증 | 추출 모델이 금액 빈 행을 통째로 버림(24~29행 중 3~18행만 추출, 항목내역.항목 실패 240) | extract | - | 미해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-05 | 진료비영수증 | AO가 비급여를 급여로 오추출(정액수가/합계 행 9,010,000): no_column 2행/row_copy/sum_mismatch 검출 후 교정 | extract | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-06 | 진료비영수증 | 셀 병합 파싱 에러: 납부 금액 스칼라 4건 교정 | parse | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-07 | 진료비영수증 | AO에 tables 비어 항목내역 누락(항목명 누락 케이스), 케이스 JSON(논현정형외과)과 이미지(순천중앙병원)가 서로 다른 문서 | 입력 | - | 결정대기 | Docraft/2026-09-22-ocr-verify.md |
| VER-08 | 세부내역서 | AO가 `항목` 열에 EDI명칭을 넣는 관례 차이 16셀 | extract | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-09 | 진료비영수증 | OCR 오타 `전험및혈액성분제제료` (final 유일 오답) | parse | - | 미해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-10 | 공통 | Docraft 추출이 빈 칸 라벨(`병실`/`질병군(DRG)번호`/`성별`/`:`)을 값으로 냄 | extract | - | 해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-11 | 진단서 | 진단 연월일 칸이 비었는데 AO가 발급일을 진단일로 넣음, Judge도 AO 채택 | extract | - | 미해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-12 | 진료비영수증 | 정액수가 한 행이 곧 합계인 요양병원 문서에서 row_copy 오탐 | 후처리 | - | 미해결 | Docraft/2026-09-22-ocr-verify.md |
| VER-13 | 공통 | 다중 페이지 TIF/PDF 422 거절(범위 밖) | 입력 | - | 미해결 | Docraft/2026-09-22-ocr-verify.md |
| LBL-01 | 세부내역서 | VLM 라벨 EDI명칭 환각(한 파일 16개 중 15개), 면허번호를 본인부담총액에 기입, 열 밀림(단가 열 누락) | 평가 | - | 해결 | Docraft/2026-09-22-ocr-verify-labels.md |
| LBL-02 | 진료비영수증 | VLM 라벨 행 대량 누락(3~18행, 실제 24~29행)과 행 오귀속, 직접 계산한 합계, 환자 전화번호를 병원연락처에 기입 | 평가 | - | 해결 | Docraft/2026-09-22-ocr-verify-labels.md |
| LBL-03 | 세부내역서 | 다쪽 문서 한 쪽만 있어 총합계 행 없음(소계를 총액으로 볼지 기준 필요) | 입력 | - | 결정대기 | Docraft/2026-09-22-ocr-verify-labels.md |
| LBL-04 | 진료비영수증 | `공단부담총액` 칸이 서식에 없는 5건: 합계행 사용 여부 관례 확인 필요 | 평가 | - | 결정대기 | Docraft/2026-09-22-ocr-verify-labels.md |
| LBL-05 | 진료비영수증 | 빈 금액 칸 0 vs null 정책 불일치(RECEIPT_HINT `0` vs 라벨 null) -> `"0"` 확정 | 평가 | - | 해결 | Docraft/2026-09-22-ocr-verify-labels.md |
| LBL-06 | 세부내역서 | 치료재료 코드 `B102010Z` 1/I 구분 불가, EDI명칭 셀 폭 잘림 처리 기준 없음, 진료비영수증 26번째 행 항목명 미인쇄 null | 입력 | - | 미해결 | Docraft/2026-09-22-ocr-verify-labels.md |
| LBL-07 | 소견서 | 소견서 이름 오탐(9)과 진단서 성별 오탐(8): 주민번호 유도 정책 | 후처리 | - | 해결 | Docraft/2026-09-22-ocr-verify-labels.md |
| NSEAL-01 | 진단서 | 이름 `홍길동 (인)` -> `홍길동` 기대, 도장 표시 `인`이 남아 `홍길동인`(이름 속 `인` 보존 필요) | 후처리 | - | 해결 | Docraft/2026-09-23-rules-flow-example.md |
| PQ-01 | 공통 | `.TIF` 확장자의 실제 GIF 이미지가 OCR 422 실패(디코딩 후 EXIF 방향 반영 RGB PNG 정규화로 수정) | 입력 | - | 해결 | harness-v2/2026-09-27-parse-extract-quality.md |
| PQ-02 | 진료비영수증 | 여러 층 머리글 합칠 때 상위 `전액 본인부담`이 하위 `공단부담금`보다 우선해 금액이 다른 열로 이동(영수증 정답 920->948 회복) | parse | - | 해결 | harness-v2/2026-09-27-parse-extract-quality.md |
| PQ-03 | 진료비영수증 | 묶음 머리글 열(`급여`/`비급여`) 0 vs null 계약 차이로 strict 점수 하락 | 평가 | - | 결정대기 | harness-v2/2026-09-27-parse-extract-quality.md |
| PQ-04 | 진단서 | 신규 35건 rules FP 증가: 주민번호->성별/생년월일 파생 6건, 원문 라벨 보충 3건, 서술->치료명 4건 | 후처리 | - | 결정대기 | harness-v2/2026-09-27-parse-extract-quality.md |
| PQ-05 | 세부내역서 | 비급여 포함 총진료비를 급여총액으로 넣은 라벨 오류(별도 인쇄 근거 없는 값은 null로 수정) | 평가 | - | 해결 | harness-v2/2026-09-27-parse-extract-quality.md |
| PQ-06 | 공통 | bench 라벨 필드 누락 시 unmatched 제외로 전체 정확도 분모 부적절 -> 누락 포함 지표 | 평가 | - | 해결 | harness-v2/2026-09-27-parse-extract-quality.md |
| PQ-07 | 공통 | 회전/흐림/중앙 가림 변형 이미지에서 strict 일치 하락(원본 410 -> 회전 303, 흐림 311, 가림 302) | parse | - | 미해결 | harness-v2/2026-09-27-parse-extract-quality.md |
| INF-01 | 약제비영수증 | AO UI 33번 진료비내역 단일행 표의 금액 세 칸이 라벨과 불일치(0 등) -> 합계 원자 판정 7-i로 교정, 문서 등급은 unresolved | extract | - | 해결 | harness-v2/2026-09-28-Docraft-추론proof-소비자검증.md |
| INF-02 | 약제비영수증 | 24번 대상 빈칸 미교정(Docraft 응답 재생에서 교정 근거 없음) | extract | - | 미해결 | harness-v2/2026-09-28-Docraft-추론proof-소비자검증.md |
| INF-03 | 공통 | AO 원값이 규칙을 통과하면 Docraft 교정 근거가 있어도 최종 unresolved(등록 합계 관계/숫자 0 빈칸에 한정 분기 7-i 추가) | 후처리 | - | 해결 | harness-v2/2026-09-28-Docraft-추론proof-소비자검증.md |
| COV5-01 | 세부내역서 | 정답지 59건 표 칸 48개 누락 중 90% 이상이 검토 표시 없이 통과(투여량 열 통째 빈 20칸) -> 룰5 기대 칸 검사 | extract | - | 해결 | harness-v2/2026-10-02-추출-누락-검증-룰5-기대-칸.md |
| COV5-02 | 세부내역서 | 항목 행 `항목`(분류명, 채움률 97.8%)이 required_cells 목록에 없어 미검출 | extract | - | 결정대기 | harness-v2/2026-10-02-추출-누락-검증-룰5-기대-칸.md |
| COV5-03 | 진료비영수증 | AO가 빈 금액 칸을 `"0"`으로 내 금액 열 5b는 칸을 아예 비운 경우만 검출 | extract | - | 미해결 | harness-v2/2026-10-02-추출-누락-검증-룰5-기대-칸.md |
| AR-1 | 영수증 | SA2019123157847 AO가 필드를 못 뽑음: Docraft 보충값이 서식 그룹이 아닌 최상위 extracted_fields로 나가 채점기가 못 읽음(자동 통과 오류 18칸) | 후처리 | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-2 | 영수증 | SA2019123157794 재활및물리치료료→재활및물리치료(끝 료 누락), AO·Docraft 동일 오독이라 review 못 잡고 행 짝 실패 8칸 | extract | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-3 | 영수증 | 입원료_2-3인실 표준형 2-3 vs 정답지 2·3 / 2,3 혼용(12칸) | 평가 | - | 해결 | Docraft/2026-09-24-auto-review.md |
| AR-4 | 영수증 | 정액수가(요양병원)·(완화의료) 괄호 유지→rules.item()이 괄호를 떼 정액수가요양병원으로 바꿈 | 후처리 | - | 해결 | Docraft/2026-09-24-auto-review.md |
| AR-5 | 영수증 | 한 글자 오독(0000021605→21805, 503568→503588, 발행일 20190315→18)과 사업자번호 오검출 5칸 | extract | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-6 | 세부내역서 | 흐린 사진 20230104_123952.jpg 코드 오독을 AO·Docraft가 똑같이 해서 review 안 걸림(4칸) | 입력 | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-7 | 세부내역서 | 3022033115105207 사고발생일자: 인쇄된 조회기간 시작일(20190331)→결과는 첫 명세일(20220303) 관례 차이 | extract | - | 결정대기 | Docraft/2026-09-24-auto-review.md |
| AR-8 | 세부내역서 | 성명 F/61 표기, EDI명칭 중괄호, EDI코드 sleep2.→SLEEP2 각 1칸 소규모 오류 | extract | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-9 | 세부내역서 | 3022033115105207-1.png 인쇄된 투여량 열이 통째로 비었는데 AO·Docraft 모두 놓쳐 두 값이 같아 review 안 걸림(18칸) → DETAIL.EMPTY_COLUMN 룰로 검출 | parse | - | 해결 | Docraft/2026-09-24-auto-review.md |
| AR-10 | 세부내역서 | 비급표현-KJM02605.tif·20250102091737a3.tif 머리글 횟수(총투) 한 칸인데 빈 열 검사가 총투+횟수 두 낱말로 오검출 | 후처리 | - | 해결 | Docraft/2026-09-24-auto-review.md |
| AR-11 | 세부내역서 | 빈 병실 칸에 제목 (외래)를 보고 Docraft가 외래를 채움(2303315286은 실제 인쇄돼 룰로 못 가름) | extract | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-12 | 세부내역서 | 저품질 팩스·흐린 사진의 EDI명칭·코드 자모 오독 약 30칸, 두 결과가 같게 틀리면 못 잡음 | 입력 | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-13 | 세부내역서 | SA…3100·SA…3201·코드2개 서식에서 파서 머리글이 투여량 열을 못 찾아 DETAIL.EMPTY_CELL이 못 채움 | parse | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| AR-14 | 공통 | e2e 정답지 자체 오류(날짜 28칸, 급여구분 13칸 등 4건)가 99% 수준 수치를 좌우, 사람 검수 여부 불명 | 평가 | - | 미해결 | Docraft/2026-09-24-auto-review.md |
| E2E-1 | 영수증 | AO가 항목 행 통째 누락(SA2019123157847, SA2019123045515)→Docraft가 채움, 항목 77칸 개선 | extract | - | 해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-2 | 영수증 | 금액 열 밀림(선택진료료외 9, 비급여 5, 본인부담금 5)과 공단부담총액 3칸 오류를 Docraft가 교정 | extract | - | 해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-3 | 영수증 | Docraft 악화 25칸: 인쇄 안 된 행(제중명료)·DRG S8 추가, 1820→1825 숫자 오독 | extract | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-4 | 세부내역서 | 20230104_123952.jpg 흐린 사진 행 짝 어긋나 원내코드·횟수 비고 빈 종료일자에 입원종료일 채움 11칸(실시일 칸에 입원기간 인쇄 → 정답지 수정) | 입력 | - | 해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-5 | 세부내역서 | 코드2종포함_2303315044.jpg 정답이 빈 행에 금액(본인부담 18, 총액 42)을 채움 8칸 | extract | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-6 | 세부내역서 | 병실 칸에 진료과를 넣는 AO 오류(창원경상대 서식)를 못 고치고 2칸 더 늘림(남은 오류 13칸) | extract | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-7 | 세부내역서 | 인쇄된 투여량 열 전체 누락 46칸 | parse | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-8 | 세부내역서 | 항목에 섹션명 대신 명칭(22칸), EDI명칭 저해상도 팩스 오독 25, EDI코드 17, 원내코드 10 | extract | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-9 | 영수증 | 남은 오류 항목 16, 공단부담금 8, 요양기관종류 8, 본인부담금 6, 납부할금액 4 | extract | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-10 | 공통 | AO가 끝나지 않은 3건(3022030712433802-1.png, SA2020010683384_…3002.tif, 공란다수_SA2019123043183) 평가 제외 | 입력 | - | 미해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-11 | 세부내역서 | 비급표현-KJM02605.tif 급여구분 인쇄칸이 빈 행·100% 행을 Docraft가 급여로 채움 8칸(관례 미정), 정답지 비급→비급여 5칸 수정 | extract | - | 결정대기 | Docraft/2026-09-24-e2e-ao-verify.md |
| E2E-12 | 공통 | 서버 재부팅 직후 PaddleOCR HTTP 500으로 5건 실패 후 재실행 성공 | parse | - | 해결 | Docraft/2026-09-24-e2e-ao-verify.md |
| REQ-1 | 영수증 | 납부할금액 필수인데 예전 요양급여 서식엔 칸이 없어 환자부담총액을 베껴 넣거나 비워 review(걸린 3건 중 2건), 필수 제외 권고 | extract | - | 결정대기 | Docraft/2026-09-23-required-fields.md |
| REQ-2 | 영수증 | 사업자등록번호 칸이 비었는데 전화번호를 넣음(룰이 막지 못함) | extract | - | 미해결 | Docraft/2026-09-23-required-fields.md |
| REQ-3 | 영수증 | AO 출력이 통째로 비어 필수 필드 8개 모두 누락 flag | 입력 | - | 미해결 | Docraft/2026-09-23-required-fields.md |
| REQ-4 | 공통 | 플러그인·doctypes 필드명 불일치(진료기간(진료시작일)↔환자정보(진료시작일), 납부한금액-카드↔_카드, 상한액초과금↔상환액초과금, 선택진료↔선택진료료) | 미확정 | - | 미해결 | Docraft/2026-09-23-required-fields.md |
| REQ-5 | 영수증 | 한방 진료비영수증엔 CT진단료 칸이 없어 필수 항목 행 누락 오탐 → 한방·한약·첩약 예외 | 후처리 | - | 해결 | Docraft/2026-09-23-required-fields.md |
| REQ-6 | 영수증 | AO가 인쇄 안 된 CT진단료를 금액 0으로 찍는 경우, 행 존재만 보도록 처리 | extract | - | 해결 | Docraft/2026-09-23-required-fields.md |
| REQ-7 | 세부내역서 | 등록번호·환자구분·진료기간이 머리글 없는 이어지는 쪽에서 비어 필수 목록에서 제외(각 1/9) | 입력 | - | 해결 | Docraft/2026-09-23-required-fields.md |
| RP-1 | 영수증 | 외래/입원·공단부담총액·발행일 값은 정답과 같으나 OCR 줄 좌표가 없어 근거 연결 실패(공단총액·발행일이 파싱 텍스트에 빠짐) | parse | - | 미해결 | Docraft/2026-09-27-reprocess-priority.md |
| RP-2 | 영수증 | 상한액초과금(상환액초과금) 원본 칸 공란인데 비공란 값 추출 | extract | - | 미해결 | Docraft/2026-09-27-reprocess-priority.md |
| RP-3 | 세부내역서 | 진료기간 아래 날짜 범위를 시작일·종료일 두 값에 연결하는 근거 규칙 없음 | 후처리 | - | 미해결 | Docraft/2026-09-27-reprocess-priority.md |
| RP-4 | 세부내역서 | 사고발생일 별도 라벨 없고 스키마가 진료 시작일과 같게 정의, 직접 인쇄 근거와 파생·별칭 근거 구별 불가 | 후처리 | - | 결정대기 | Docraft/2026-09-27-reprocess-priority.md |
| RP-5 | 세부내역서 | 급여 본인부담총액이 본인부담액 아래 급여 하위열과 총계 행에서 같은 값이 겹쳐 매칭 모호(병합 머리글·총계 행 판별 필요) | parse | - | 미해결 | Docraft/2026-09-27-reprocess-priority.md |
| RP-6 | 영수증 | grounding _labels가 공단부담금·상한액초과금 별칭을 안 써서 네 필드 모두 인쇄 라벨 앵커를 못 잡음 | 후처리 | - | 미해결 | Docraft/2026-09-27-reprocess-priority.md |
| CP-1 | 세부내역서 | 2303314855 인쇄된 항목 칸 앞 5행이 빈데 AO가 7행 모두 EDI명칭을 항목에 베낌→빈 값으로 교정 | extract | - | 해결 | harness-v2/2026-09-30-세부내역서-베낀항목-비움.md |
| CP-2 | 세부내역서 | 섹션명이 인쇄돼 있는데 AO가 못 읽어 베낀 행을 빈칸으로 둠(2303314855 SONO 2행, 3022030712433802-1 17행, 2303314528 16행), 재판독 미착수 | extract | - | 미해결 | harness-v2/2026-09-30-세부내역서-베낀항목-비움.md |
| CP-3 | 세부내역서 | MASTER_0710_10 코드 없는 행 역조회가 항목(섹션명 칸)을 입력으로 써 항목이 비면 역조회 소실→EDI명칭 사용 | 후처리 | - | 해결 | harness-v2/2026-09-30-세부내역서-베낀항목-비움.md |
| KCD-1 | 입퇴원확인서 | 병명 3개(M754 S434 M501)인데 2행으로 추출, S434 행에 두 병명 합침·M501 누락이 MASTER_KCD_04 pass로 조용히 통과→확인 필요 | extract | - | 해결 | harness-v2/2026-09-18-KCD-병명합침-확인필요.md |
| KCD-2 | 입퇴원확인서 | 남은 병명이 한 코드로 안 정해지거나(경추간판장애 M50 계열 동점)·같은 3단위 계열 병합·조사 차이면 합침을 못 잡음 | 후처리 | - | 미해결 | harness-v2/2026-09-18-KCD-병명합침-확인필요.md |
| RR-1 | 소견서 | 병명코드 I678→I6788 자릿수 오독(1333), 병명 뇌허혈(만성)과 불일치로 review_required | extract | - | 미해결 | harness-v2/2026-09-10-review_required-3종-원인-분석.md |
| RR-2 | 세부내역서 | 0720 row12 페니라민정 단가15×횟수3인데 총액0·급여18·본인부담0 행 내부 모순, 원인 셀 특정 불가 | 미확정 | - | 미해결 | harness-v2/2026-09-10-review_required-3종-원인-분석.md |
| RR-3 | 영수증 | AC029 전액본인부담 열이 이웃 열 값을 복제(행0 10717, 행8 6504, 행21 40000)해 fail 9건 파생 | extract | - | 미해결 | harness-v2/2026-09-10-review_required-3종-원인-분석.md |
| RR-4 | 영수증 | AC029 합계행 선택진료료외 40000→0으로 읽힘(CALC_AC029_12·10 fail) | extract | - | 미해결 | harness-v2/2026-09-10-review_required-3종-원인-분석.md |
| RR-5 | 영수증 | 공단부담금 열합계 17221 vs 합계행 17300 원단위 절사 차이, 실제 영수증 관행이라 warn 흡수 | 후처리 | - | 해결 | harness-v2/2026-09-10-review_required-3종-원인-분석.md |
| TERM-1 | 영수증 | 진료기간에 날짜 하나만 인쇄된 외래 영수증은 진료종료일이 빈칸인데 필수 키 검사가 늘 검토·재판독으로 보냄(채움률 약 50%) | 후처리 | - | 해결 | harness-v2/2026-10-03-진료종료일-필수키-제외.md |
| TERM-2 | 영수증 | AO가 외래 영수증 진료종료일을 시작일로 베낌, 하네스가 그대로 통과(새 정답지 채점 시 영수증 93.1→69.0%) | extract | - | 결정대기 | harness-v2/2026-10-03-진료종료일-필수키-제외.md |
| SUM-1 | 세부내역서 | G2-b 요약 행 금액이 투여량·단가·횟수·일수 칸으로 왼쪽 밀림(83384 계열 7건) | extract | G2-b | 해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-2 | 세부내역서 | G2-c 끝수처리 조정 행 값이 합계−계와 다름 | extract | G2-c | 해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-3 | 세부내역서 | G2-d 계 행 칸 누락(총액−부담 합 차이 100원 이상) | extract | G2-d | 해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-4 | 세부내역서 | G2-e 금액 칸 소수(676782.5, 142680.75)→0 방향 버림(20250102091737a3 6칸) | extract | G2-e | 해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-5 | 세부내역서 | G2-f 요약 행 급여를 총액으로 복사 | extract | G2-f | 해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-6 | 세부내역서 | G2-a 요약 행 투여량·단가·횟수·일수에 인쇄 안 된 0 → 빈 값(2303314855 8칸) | extract | G2-a | 해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-7 | 세부내역서 | SA2020010684292_2020010611215001 계 행 전액본인 255,390이 비급여로 밀림, 합계 그룹이 전액본인부담을 비급여에 묶어 근거 불확정 | extract | G2-d | 미해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-8 | 세부내역서 | 정답지 요약 행에 0이 있으나 원본 칸은 빈 칸(2303314662·2303314712·2303315286 단가, 2303314855 투여량 등 13칸) | 평가 | - | 미해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| SUM-9 | 세부내역서 | 103001 +11 끝수 행 공단부담 20: AO에 정답지보다 행이 2개 많아 행 정렬로 매칭 불일치 | 평가 | - | 미해결 | harness-v2/2026-10-02-세부내역서-요약행-칸-배정.md |
| RC-1 | 영수증 | 08 영수증 하단 잘림 시 공단부담총액을 우측 영역으로 묶어 우측·하단 모두 잘림(basis none)→하단 좌표로 이동 | 후처리 | - | 해결 | harness-v2/2026-09-14-영수증-조정후합계-납부금액-단가곱-구조검증.md |
| RC-2 | 영수증 | 합계(조정후) 행 실물 없음(라벨 0건), 표 행인지 그룹 필드인지 불명 | 미확정 | - | 결정대기 | harness-v2/2026-09-14-영수증-조정후합계-납부금액-단가곱-구조검증.md |
| RC-3 | 세부내역서 | 페니라민정 15×3.0×3=135인데 총액 0으로 인쇄된 묶음 산정 행이 UNITMUL fail | 입력 | - | 결정대기 | harness-v2/2026-09-14-영수증-조정후합계-납부금액-단가곱-구조검증.md |
| RC-4 | 영수증 | 헤더 칸이 빠지고 헤더 밖 칸이 생긴 행(행/열 개수 불일치)을 정상으로 보던 판정→STRUCT_AC029_13·짧은 열 기록 | 후처리 | - | 해결 | harness-v2/2026-09-14-영수증-조정후합계-납부금액-단가곱-구조검증.md |
| RC-5 | 영수증 | 여러 페이지·배치 표 병합 후 행·열 검증 미구현(하네스에 병합 없음, 조각 식별 키 없음) | 입력 | - | 미해결 | harness-v2/2026-09-14-영수증-조정후합계-납부금액-단가곱-구조검증.md |
| RC-6 | 영수증 | 영수증 ⑩~⑫(지원단체부담금 등) 추출 키 이름을 스키마와 대조 못 하고 ⑥ 상한액초과금에서 R-AC029-BURDEN과 CALC_AC029_02가 갈림 | 미확정 | - | 결정대기 | harness-v2/2026-09-14-영수증-조정후합계-납부금액-단가곱-구조검증.md |
| Q-2 | 세부내역서 | AU211 등 명칭 병기(기관표기{약칭})·칸 폭 잘림 때문에 OCR 정확한데 하네스 오탐 fail 12행(33→9건) | 후처리 | - | 해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-4 | 세부내역서 | EDI 코드 두 개 병기 AU211{AIAU211}를 통째로 조회해 미존재 fail | 후처리 | - | 해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-5 | 영수증 | 합계행 급여·비급여 칸 공란이면 col_sum이 0을 돌려 CALC_AC029_01·CROSS_AC029_05 오탐 fail(진료비총액 103,910 건) | 후처리 | - | 해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-6 | 세부내역서 | 문서 명칭이 마스터 명칭을 접두로 포함해도 fuzz.ratio 0.27로 불일치 | 후처리 | - | 해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-7 | 영수증 | 질병군포괄수가 행 체크: 규칙 1회 결과가 col_sum이 읽은 열 전체 셀에 부착 | 후처리 | - | 해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-8 | 영수증 | image13 비급여 한 칸 서식에서 v1.11 수정이 비급여를 그룹 머리글로 가정해 CALC_AC029_01·02 fail(회귀) | 후처리 | - | 해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-9 | 세부내역서 | 진료일 2021-08 문서 vs 마스터 2025판: MASTER_0710_08 not_found 8건·MASTER_0710_11 warn 12건이 판본 차이, AQ120800은 원문 AO120800 실제 오독 | 입력 | - | 결정대기 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| Q-10 | 세부내역서 | 파이프라인이 code_reread_agrees_by_path를 안 넘겨 분기 11이 명칭 셀 자신의 재판독으로 판단되고, MASTER_0710_10 detail과 판정 분기가 서로 모순 | 후처리 | - | 미해결 | harness-v2/2026-09-11-질문사항-1차-답변-분석.md |
| TD-1 | 세부내역서 | 절사 식 floor(값/100)*100을 문자 그대로 쓰면 요건 예시(2,694,904 vs 2,694,870)·999 vs 1,000 실패, 100원 미만 구현 시 18원 차이 검출 소실 | 평가 | - | 결정대기 | harness-v2/2026-09-14-TODO-260914-요건-반영-확인필요사항.md |
| TD-2 | 입퇴원확인서 | KCD N5 선두 0→D·Q 치환 시 병명과 어긋나면 교정 안 함(합의에 없는 조건) | 후처리 | - | 결정대기 | harness-v2/2026-09-14-TODO-260914-요건-반영-확인필요사항.md |
| TD-3 | 영수증 | 끝수처리 행 라벨 실물 없음(JSON 27건 0건)과 잘림 문서 실물 없음(합성 문서로만 검증) | 입력 | - | 미해결 | harness-v2/2026-09-14-TODO-260914-요건-반영-확인필요사항.md |
| TD-4 | 세부내역서 | EDI 헤더 매핑 3.0.3~3.0.6(보험부담액·선택진료·병원가산·선별급여·제목 행 없음) 고객 확인 대기 | parse | - | 결정대기 | harness-v2/2026-09-14-TODO-260914-요건-반영-확인필요사항.md |
| TD-5 | 입퇴원확인서 | KCD ④ 문서 내 수술명이 부위 토큰 하나만 겹쳐도 통과(병명 틀려도 pass 가능), 축약 기재 S300 골반의 타박상 warn→pass, 짝 재배치 안전장치로 표기 차이 시 재배치 실패 가능 | 후처리 | - | 결정대기 | harness-v2/2026-09-14-TODO-260914-요건-반영-확인필요사항.md |
| TD-6 | 세부내역서 | EDI E4 절단 재조회로 8·9자 코드 뒤 오독 검출 소실(원장 5자 접두 363,954개), 투여량 곱 표본 전부 공란 | 후처리 | - | 결정대기 | harness-v2/2026-09-14-TODO-260914-요건-반영-확인필요사항.md |
| LV-1 | 공통 | 원본+Golden만 올린 번들에서 결과 없는데 빈 결과와 비교해 정확도 34%·불일치 85 표시 | 평가 | - | 해결 | label_veiwer/2026-10-02-score-without-result.md |
| PF-1 | 세부내역서 | 투여량·횟수·일수·EDI코드·EDI명칭 칸 정답 있음→AO가 빈 문자열로 누락(오답 322칸 중 약 182칸은 parse 행에 정답 존재) | extract | - | 해결 | harness-v2/2026-09-29-세부내역서-parse-보충-열-확대.md |
| PF-2 | 세부내역서 | EDI명칭 정답→parse 보충값 판독 차이(쉼표 누락 병원 정신병원, 각막곡률→각막곡율, IQ→10, 칸 잘림 위치 차이) 7칸 불일치 | parse | - | 미해결 | harness-v2/2026-09-29-세부내역서-parse-보충-열-확대.md |
| PF-3 | 세부내역서 | 횟수(총투)일수 또는 횟수 일수로 붙은 머리글+빈 칸에서 일수 열을 하나로 못 정해 보충 못 함(1220210624…, 3022033115393304-1.png) | parse | - | 미해결 | harness-v2/2026-09-29-세부내역서-parse-보충-열-확대.md |
| PF-4 | 세부내역서 | 수량 1.0000→parse가 1,000으로 오파싱(20230228…), 쉼표 값이라 보충에서 거름 | parse | - | 해결 | harness-v2/2026-09-29-세부내역서-parse-보충-열-확대.md |
| PF-5 | 세부내역서 | EDI명칭 외래환자의약품관리료(방문당)→parse 칸 잘림으로 앞 5자만 비교 열쇠로 사용 | parse | - | 해결 | harness-v2/2026-09-29-세부내역서-parse-보충-열-확대.md |
| PF-6 | 세부내역서 | 1220220321… 표본 EDI명칭 빈칸 Docraft 값 우선 시 순이득 +1칸뿐(parse만 틀림 3·Docraft만 틀림 2·둘 다 틀림 1)이라 Docraft 우선 미도입 | 후처리 | - | 결정대기 | harness-v2/2026-09-29-세부내역서-parse-보충-열-확대.md |
| PX-1 | 공통 | 근거 좌표 없거나 품질 PASS 아닌 Docraft 재판독값→자동 교정되던 것 검토 상태로 보류(출처 불명확 값 채택) | 후처리 | - | 해결 | harness-v2/2026-09-27-Parse-Extract-전체분모평가와-Docraft-근거게이트.md |
| PX-2 | 공통 | 정답 라벨 중 결과 필드·판정 누락분이 분모에서 빠져 정확도 과대평가(unresolved에 맞는 값 구분 불가) | 평가 | - | 해결 | harness-v2/2026-09-27-Parse-Extract-전체분모평가와-Docraft-근거게이트.md |
| PX-3 | 진료비영수증 | 병합된 영수증 표 머리글에서 공단부담금 대신 위쪽 전액본인부담 선택→정상 금액이 다른 열로 이동(수정 후 rules 정답 28칸 증가) | parse | - | 해결 | harness-v2/2026-09-27-Parse-Extract-전체분모평가와-Docraft-근거게이트.md |
| PX-4 | 진료비영수증 | 묶음 제목 열 인쇄 안 됨(null 기대)→스키마 0 지시와 규칙 null 표현 차이로 strict 불일치 | extract | - | 미해결 | harness-v2/2026-09-27-Parse-Extract-전체분모평가와-Docraft-근거게이트.md |
| PX-5 | 공통 | 회전·흐림 이미지에서 근거 게이트 경고 증가(원본 213→회전 269/흐림 237), 탐지 recall 라벨 없음 | 입력 | - | 미확정 | harness-v2/2026-09-27-Parse-Extract-전체분모평가와-Docraft-근거게이트.md |
| PX-6 | 공통 | 35건 독립 표본 인쇄된 빈칸 오탐 raw 115/733·rules 108/741, strict 일치 rules 83.81% | extract | - | 미해결 | harness-v2/2026-09-27-Parse-Extract-전체분모평가와-Docraft-근거게이트.md |
| S7-1 | 세부내역서 | 세부내역서→AO가 진료비영수증 스키마로 분류해 EDI코드·단가 열 통째 누락(AO 오류 칸의 42%, 9장) | extract | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-2 | 공통 | 5건 AO extract model_output_invalid(재시도해도 실패) | extract | - | 미해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-3 | 공통 | doc_type 한글명 기대→7종 워크플로우가 코드(Y000701200 등)로 출력해 하네스 문서코드 unknown | 입력 | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-4 | 세부내역서 | 항목내역.급여구분 빈 값 기대→AO가 열추출 자리표시 출력 | extract | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-5 | 진단서 | 병명 기대(주 질병·부상 접두 없음)→AO가 (주 질병·부상)·(부상병)·주상병: 접두를 병명에 포함 | extract | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-6 | 진단서 | 최종진단·임상적추정 한쪽 Y면 다른 쪽 N 기대→빈 값 | extract | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-7 | 진료비영수증 | 신서식 선택진료료외 칸 기대→AO가 비급여 칸에 금액 기재 | extract | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-8 | 진료비영수증 | 질병군(DRG) 번호 영문1자+숫자4~5자리 기대(G10600)→AO가 사업자번호·병실을 넣음(14칸 검토로만 잡힘, Docraft도 동일 오독) | extract | - | 미해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-9 | 진료비영수증 | DRG 값에 올 수 없는 문자(- / 호)가 섞임→빈 값 정규화 후보 14칸 | extract | - | 미해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-10 | 진료비영수증 | 합계 행도 선택진료료 비어 있으면 열 이동 대상, 20220321_112233 투약 약품비 2,159 옮긴 결과가 정답지와 다름 | 후처리 | - | 미해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-11 | 세부내역서 | 행 누락·과잉, EDI명칭 잘림(하네스 88%, 칸 규칙으로 안 잡힘) | extract | - | 미해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-12 | 진료비영수증 | Docraft 문서 전체 검증이 항목명을 바꾸는 교정으로 영수증 -5.3%p | 후처리 | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-13 | 공통 | 서식 제목 OCR이 큰 제목을 진료비/내역서(입원)처럼 조각내고 EXIF 미적용해 로컬 OCR 규칙이 서버 OCR에서 오분류 | 입력 | - | 해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-14 | 공통 | 회전·상단 잘림·복약안내만 찍힌 약제비 13~15장 제목 미인식→AO 분류 유지 | 입력 | - | 미해결 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| S7-15 | 공통 | 외국인등록번호(뒷자리 5~8) 성별 대조가 요건 260918(스키마 1~4만)과 충돌해 규칙 미도입 | 후처리 | - | 결정대기 | harness-v2/2026-09-24-표본-7종-e2e-서식재분류-정규화.md |
| EN-1 | 세부내역서 | 재진진찰료-의원(마스터)→문서 재진진찰료-의원,보건의료원 내 의과 등 기관 범위 덧붙임으로 EDI명칭 유사도 fail(AA254·AA254030 4건) | 후처리 | - | 해결 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-2 | 세부내역서 | 한 자리 코드 오독이 형제 항목(거의 같은 명칭)에 맞아 명칭 대조로 못 잡음(856건 중 약 1/3, 혈전제거술 동맥-경부 vs 동맥-흉부) | 후처리 | - | 미해결 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-3 | 세부내역서 | 병원 라벨이 원장 명칭보다 길면(재진진찰료-의원,보건의료원 내 의과) 형제 AA253이 AA254보다 앞서 역유추 후보 오배치 | 후처리 | - | 미해결 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-4 | 세부내역서 | 치료재료 코드 명칭이 영문 제품명이라 한글 병원 라벨과 대조 시 확인 필요만 쏟아짐 | 후처리 | D3 | 해결 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-5 | 세부내역서 | 치료재료 deleted=Y 코드 9건 삭제 표시 코드를 현행으로 단정 못 함→warn | 후처리 | D4 | 해결 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-6 | 세부내역서 | 진찰료 코드 형식이 영문2+숫자3 아닌 경우 명칭으로 코드 재유추(요건 §2, 결정 C5) 미구현 | 후처리 | C5 | 결정대기 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-7 | 세부내역서 | EDI명칭 칸 빈 값→원장 명칭 보완 후보 제시(결정 C4) 미구현 | 후처리 | C4 | 결정대기 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-8 | 세부내역서 | 치료재료·수가 45개 정확 코드 충돌·667개 5자 접두 충돌 조정 없이 통보만 | 후처리 | - | 결정대기 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| EN-9 | 세부내역서 | 명칭 유사도 기준값 0.2가 합성 데이터와 요건 예시 4건으로만 검증(실제 병원 라벨 긍정 샘플 없음) | 평가 | - | 미해결 | harness-v2/2026-09-15-EDI-명칭검증-TFIDF-포함도.md |
| V7-1 | 입퇴원확인서 | 병명코드 S0600B(서식에 그대로 인쇄, 신뢰도 0.96)→KCD 마스터에 접미 영문 코드 0개라 fail 오탐 | 후처리 | §19-18 | 해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-2 | 입퇴원확인서 | S300 골반의 타박상(서식 인쇄 그대로)→마스터 아래등 및 골반의 타박상과 유사도 0.75<0.85로 fail 오탐 2건 | 후처리 | §19-19 | 해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-3 | 세부내역서 | MCR301 영양수액비급여처방료(60000) 비급여→단일 코드 열 서식인데 마스터 조회 0건으로 fail 오탐 | 후처리 | §19-20 | 해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-4 | 소견서 | 서식 I678B→상위 OCR이 B를 8로 오독(I6788), 하네스가 정확히 검출 | extract | - | 해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-5 | 세부내역서 | 단가 AA254 의원단가 13,160(마스터 2025판)→문서 12,380(2023 진료일), 판본 차이로 2023~2024년 급여 행 상시 warn | 후처리 | §19-21 | 미해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-6 | 약제비영수증 | 규칙 0건 문서가 검증 0건인데 confirmed 판정(미검증 필드 공허참) | 후처리 | - | 해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-7 | 세부내역서 | MASTER_0710_10 규칙은 항목 열 명칭 pass인데 채택 경로는 EDI명칭 열을 봐 값 버려지고 undetermined | 후처리 | - | 미해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-8 | 진료비영수증 | 하단 잘림 시 우측 기준 검증 규칙 0건, 공단부담총액 어떤 규칙도 검증 안 함 | 후처리 | §19-22 | 미해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-9 | 진료비영수증 | 전액본인부담 열이 공단부담금 열의 복제로 읽힘, 선택진료료외 합계 0으로 미판독(r21 수액 40000) | extract | - | 미해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| V7-10 | 세부내역서 | 12행 총액 0 미판독(페니라민정 행, 서식에 인쇄된 값) | extract | - | 미해결 | harness-v2/2026-09-10-실측-7종-전수-재검증.md |
| CO-1 | 진료비영수증 | 전액본인부담 열이 공단부담금 열 복제(진찰료 10717·처치및수술료 6504·합계 17300)→CALC_AC029_01/02/10이 검출 | extract | - | 미해결 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| CO-2 | 진단서 | 통원일 JSON 배열 기대→실제는 파이썬 repr 문자열 (['20210819', ...]) | 입력 | - | 해결 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| CO-3 | 공통 | 파일명 NFC 기대→디스크 한글 파일명 NFD라 7건 중 2건 정당한 입력이 거부 | 입력 | - | 해결 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| CO-4 | 공통 | normalize_date가 2023년 3월 11일 같은 비패딩 월·일을 None 반환 | 후처리 | - | 해결 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| CO-5 | 소견서 | 문자열 null을 빈 값으로 못 잡음(FieldNode.is_empty와 normalize.is_empty 불일치) | 후처리 | - | 해결 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| CO-6 | 공통 | 상위 OCR이 좌표(bbox) 미제공→자가교정 영역 crop이 페이지 전체 재추출로 퇴화 | 입력 | §19-7 | 미해결 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| CO-7 | 진료비영수증 | 2,694,904→2,694,870(-34) 차이가 절사로 설명 안 되고 warn으로만 흡수 | 후처리 | §19-5 | 결정대기 | harness-v2/2026-09-09-하네스-v2-코어-구현.md |
| FL-1 | 약제비영수증 | 약제비영수증 표기 기대→실측 doc_type이 약제영수증으로 옴(매핑 불일치) | 입력 | - | 해결 | harness-v2/2026-09-09-하네스-v2-전체-flow-설명.md |
| FL-2 | 세부내역서 | 입원/통원 구분(0710/0720) 근거 필드가 비었거나 양쪽 매칭 시 추측 못 하고 문서 review_required만 표시 | 입력 | - | 해결 | harness-v2/2026-09-09-하네스-v2-전체-flow-설명.md |
| EQ-1 | 입퇴원확인서 | 문서 골반의 타박상→마스터 아래등 및 골반의 타박상으로 판독 누락이라 가정해 한 방향 완화 근거로 삼았으나 서식 실물에 그대로 인쇄(전제 오류, 정정됨) | 후처리 | §19-19 | 해결 | harness-v2/2026-09-09-EDI-명칭-수식표기-완화.md |
| EQ-2 | 세부내역서 | 마스터 명칭 접두+구분자 경계 수식 표기(AA254 계열 2코드 4건) 근거 4건뿐인 잠정 규칙, 고객 협의 필요 | 후처리 | R7 | 결정대기 | harness-v2/2026-09-09-EDI-명칭-수식표기-완화.md |
| AU-1 | 공통 | API_KEYS가 compose·env 예시에 없어 api_key 모드 켜면 전량 500 | 입력 | - | 해결 | harness-v2/2026-09-09-API-인증-켜기와-준비상태-정직화.md |
| AU-2 | 공통 | 비 ASCII 한글 헤더로 hmac.compare_digest TypeError 500 | 입력 | - | 해결 | harness-v2/2026-09-09-API-인증-켜기와-준비상태-정직화.md |
| AU-3 | 공통 | 마스터 미적재·부분 적재 시 readyz 200이고 MASTER·KCD 규칙 전부 not_applicable로 조용한 미검증 | 후처리 | - | 해결 | harness-v2/2026-09-09-API-인증-켜기와-준비상태-정직화.md |
| FR-B1 | 공통 | 실측 파일명(X.tif.classification.uuid.json·X.jpg_merged.json·X.png)→배치 CLI가 이미지 짝을 못 찾아 7건 0건 처리 | 입력 | B1 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-B2 | 공통 | 미지의 doc_type·입통원구분 없음 시 undetermined·review_required 기대→confirmed로 출력 | 후처리 | B2 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-B3 | 공통 | 자가교정 루프가 파이프라인에 배선 안 돼 한 번도 안 돎(region_reader 미주입·re_verify 항상 False) | 후처리 | B3 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R1 | 진료비영수증 | CALC_AC029_01 식이 비급여 이중 계상→비급여 있는 모든 영수증 fail(차이=비급여 40,000) | 후처리 | R1 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R2 | 진단서 | SORT_KCD_06이 주상병→부상병 임상 순서를 사전순 불일치로 warn→진단서·수술확인서·입퇴원확인서 3종이 review_required | 후처리 | R2 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R3 | 공통 | warn만 있는 필드가 무조건 review_required(분기 12)→공단부담 절사 잔여가 정상 서류에서 항상 검토 대상(세부내역서 16셀·영수증 5셀) | 후처리 | R3 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R4 | 세부내역서 | 횟수·일수 공란(관행상 1)→CALC_0710_02가 0으로 채워 계산 0≠12,380 fail | 후처리 | R4 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R5 | 진단서 | 통원일수=9가 FMT_DATE_01 key_pattern(통원일)에 걸려 날짜 형식 fail(입원일수·재원일수도 동일) | 후처리 | R5 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R6 | 세부내역서 | 9자리 숫자 EDI 약품코드(650902021 등)→수가 마스터에 없다고 MASTER_0710_08 fail 13행(약가 마스터 v2 범위 밖) | 후처리 | R6 | 해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R7 | 세부내역서 | EDI명칭 재진진찰료-의원,보건의료원 내 의과 vs 마스터 재진진찰료-의원 유사도 0.64<0.85 fail 4건 | 후처리 | R7 | 해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R8 | 약제비영수증 | 15필드 중 13 confirmed·빈 필드 2개인데 롤업에서 undetermined가 confirmed보다 위라 문서 undetermined | 후처리 | R8 | 결정대기 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-R9 | 진료비영수증 | 열 합계 규칙이 열 전체 셀에 증거를 붙여 review 65개 중 52개가 같은 경로(실제 오류는 합계 행 1칸+열 밀림 3칸) | 후처리 | R9 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-A2 | 공통 | 규칙 11이 명칭 필드 재판독 matched를 코드 일치로 판정→코드 오독인데 마스터에 존재하면 명칭 오교정 위험 | 후처리 | A2 | 해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-A3 | 공통 | 재판독에만 있는 행이 생겨도 표 판정이 undetermined(table_review_required 미호출) | 후처리 | A3 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-A9 | 공통 | is_empty가 - none nan도 빈 값 취급→문서에 실제 찍힌 -가 값 없음 일치로 확정될 수 있음 | 후처리 | A9 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-M2 | 세부내역서 | 수가 마스터 명칭의 %(2,859건)·_(37,698건) LIKE 와일드카드 미이스케이프로 역유추 후보 오염 | 후처리 | M2 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-M4 | 공통 | MASTER_KCD_07 성별 폴백이 남자·M·1을 정규화 안 해 high fail 오탐 | 후처리 | M4 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-M6 | 공통 | KCD C20-9 하이픈 포함 코드→마스터에 - 코드 0건이라 형식 통과·마스터 fail | 후처리 | M6 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-M7 | 세부내역서 | master_evidence가 원본 코드를 증거에서 지우고 역유추 1단계면 조용히 다른 코드로 대체 | 후처리 | M7 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-O1 | 진단서 | 통원일 9원소 배열이 원소 단위 판정 없이 단일 판정(§4.2 위반) | 후처리 | - | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-D4 | 공통 | 감사 로그에 matched_name·candidates·evidence_values의 한글 성명이 원값 기록(키 이름 기반 마스킹만) | 후처리 | D4 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| FR-D1 | 공통 | 감사 로거 주입 시 self.audit.log 호출 AttributeError(AuditRun에는 emit만 있음), 감사 레코드 0건 | 후처리 | D1 | 미해결 | harness-v2/2026-09-09-금요일-납품-전-전수-검토.md |
| RR-1 | 진료비영수증 | 정액수가(요양병원)·합계 9,010,000 비급여 기대→급여에 들어감, 투약 약품비 4,120,000이 행위료 행에 들어감(세로 행 밀림) | extract | - | 해결 | Docraft/2026-09-23-receipt-issue-cases.md |
| RR-2 | 진료비영수증 | 주사료 행위료·약품비 값이 한 행 위로, 236·800,000·1,500,000·500,000이 한두 행 아래로 밀림(열 합 그대로라 합계 검사로 못 잡음) | extract | - | 해결 | Docraft/2026-09-23-receipt-issue-cases.md |
| RR-3 | 진료비영수증 | 머리글 선택진료료 이외→파서가 미외로 읽어 40,000·420,000·10,000·470,000이 선택진료료 열로 이동 | parse | - | 해결 | Docraft/2026-09-23-receipt-issue-cases.md |
| RR-4 | 진료비영수증 | 포괄수가 행이 위쪽 항목을 다시 담는 합계 행에 row_copy 헛경고 | 후처리 | - | 해결 | Docraft/2026-09-23-receipt-issue-cases.md |
| RR-5 | 진료비영수증 | 파싱 에러 건 증명료및기타 -42,360→Docraft 추출이 부호 손실(AO가 맞게 읽어 최종값은 정상) | extract | - | 미해결 | Docraft/2026-09-23-receipt-issue-cases.md |
| RR-6 | 진료비영수증 | 항목명 표기 보철교정료·정액수가요양병원(Docraft) vs 보철·교정료·정액수가(요양병원)(AO) 출력 표기 불일치 | extract | - | 미해결 | Docraft/2026-09-23-receipt-issue-cases.md |
| RR-7 | 진료비영수증 | 항목명 누락 이슈 폴더의 AO JSON이 이미지와 다른 문서(논현정형외과)라 AO 누락을 재현 불가 | 입력 | - | 결정대기 | Docraft/2026-09-23-receipt-issue-cases.md |
| RG-1 | 진료비영수증 | 2020010684177 1라운드에서 열 통째 맞바꿈과 합계 행 이동이 부딪쳐 검사료 비급여 50,000이 선택진료료외 열로 감(2라운드가 되돌림, 교정 순서 문제는 잔존) | 후처리 | - | 미해결 | Docraft/2026-09-23-rule-registry.md |
| RG-2 | 공통 | 음수 값 검사 룰 RANGE.NON_NEGATIVE 대상 오류가 AO에서 없어(음수 21칸은 정상 조정금액 행) 룰 미도입 | 후처리 | - | 해결 | Docraft/2026-09-23-rule-registry.md |
| RG-3 | 진료비영수증 | 원시 추출에서 잘못된 음수 2칸(영수증 1건) | extract | - | 미해결 | Docraft/2026-09-23-rule-registry.md |
| AL-1 | 세부내역서 | 라벨 null 기대→모델이 급여 열을 총액-비급여로 채움(fp 372→273으로 정리), 잔여 141건은 _grouped 판정 실패 문서 7건(머리글 행 미검출 5·머리글 병합 1·급여구분 값 혼입 1) | 후처리 | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-2 | 세부내역서 | SA2020010683384 항목내역 행이 한 칸씩 밀려 EDI코드 L2012 기대→L2011 등 연쇄 오답(qwen3.5-27b에서 380/382→225/382) | extract | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-3 | 진료비영수증 | 인쇄된 항목 행(진찰료·입원료_1인실·투약및조제료_약품비)을 통째 누락(155799374711284.jpg 오답 4→27, 1549843741259026.jpg 10→29) | extract | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-4 | 세부내역서 | 투여량 칸 라벨 null→모델이 1·2·3 또는 금액(12380·1837)을 채움(photo_1640582155063 +23, 2303314684 +19) | extract | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-5 | 세부내역서 | 문자 단위 오독 진찰료→진활료, EDI코드 AH500→A1500, 병실 82병동(829)→82(829), 시작일자 20210809→20210808(1120210831…tif 오답 11→32) | extract | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-6 | 진료비영수증 | 요약 금액 오선택 납부한금액_카드 19200→8400, 이미납부한금액 8400→0, 공단부담총액 null→12820, 환자구분 건보(임산부)→건강보험(155799374711284.jpg) | extract | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-7 | 진단서 | 수술내역.수술일자·수술명 +4~5셀, 차트번호 +3셀 오답 증가(소견서·진단서 새 모델) | extract | - | 미해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| AL-8 | 공통 | 관례 정렬로 채점 분모 8,527→9,525→9,238 변경, 09-23 이전 정확도와 직접 비교 불가 | 평가 | - | 해결 | Docraft/2026-09-23-label-alignment-and-model-compare.md |
| TR-1 | 진료비영수증 | 괘선 있는 표가 2~3도 기울어 세로 괘선이 100px 흘러 행 전체가 한 셀로 병합, 머리글 항목 미검출(라벨 28행 대 예측 7행) | parse | (a) | 해결 | Docraft/2026-09-22-table-restore.md |
| TR-2 | 공통 | _runs 팽창 창 정렬 버그로 마스크 1px 밀리고 길이가 짧아져 표 아래·오른쪽 행·열이 괘선 없음으로 읽힘 | parse | (a') | 해결 | Docraft/2026-09-22-table-restore.md |
| TR-3 | 진료비영수증 | 괘선이 한 행에서만 흐려도 병합으로 판단해 행 전체 합침(1546483864454246, SA2019101694203) | parse | (b) | 해결 | Docraft/2026-09-22-table-restore.md |
| TR-4 | 세부내역서 | 항목 열 병합으로 머리글이 함목 F'잘료 . 입원료 식대… 한 셀로 뭉치고 OCR 오탈자(항→함) 겹침(SA2020010683612, photo_1640582155063) | parse | (c) | 미해결 | Docraft/2026-09-22-table-restore.md |
| TR-5 | 진료비영수증 | PP-OCR이 진찰료 3,342 7,798 0 을 한 줄로 줘 셀 경계에 걸침(1546483864454246) | parse | (d) | 해결 | Docraft/2026-09-22-table-restore.md |
| TR-6 | 세부내역서 | 머리글 행이 표 블록 밖이거나 TIF 품질 불량으로 표가 글자 덩어리로만 잡힘(2303314684, 1120210906115301212, 세부내역서6, SA2019101165425) | parse | (e) | 미해결 | Docraft/2026-09-22-table-restore.md |
| TR-7 | 진료비영수증 | 고객 보고 파싱 에러: 한 셀에 두 행 금액 병합(다중 금액 셀 12→0) | parse | - | 해결 | Docraft/2026-09-22-table-restore.md |
| TR-8 | 세부내역서 | photo_1640582155063처럼 휘어 찍힌 사진은 각도 0도 판정이라 표 복원 실패(페이지 펴는 전처리 필요) | 입력 | - | 미해결 | Docraft/2026-09-22-table-restore.md |
| TF-1 | 진료비영수증 | PaddleOCR-VL 글자 오독 료→로, 670925→670825, 진 찰 로→진찰료, 양수증번호→영수증번호, 홍액→총액, 억삼동→역삼동(VLM 셀 교정으로 보정) | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-2 | 세부내역서 | 아세트아미노렌→아세트아미노펜, 영양수택→영양수액, 덕스판테놀→덱스판테놀 | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-3 | 진단서 | 이상체증강소→이상체증감소, 끝다공증→골다공증, 입 상 책 추 정→임상적 추정 | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-4 | 소견서 | 항원시→창원시 등 4셀 오독 | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-5 | 약제비영수증 | 아섹젝→아세정, 필름코딩쟁→필름코팅정 | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-6 | 진료비영수증 | 세로 글자 오독 기본항목→기본 환자 항목, 선택항목→개월 년수 | parse | - | 미해결 | Docraft/2026-09-22-table-refine.md |
| TF-7 | 공통 | VLM 셀 교정이 값 삭제(나동휘→빈칸)·약품명 창작(아섹젝→아세트아미노펜)·직인 셀에 없는 글자 채움·셀 사이 텍스트 이동(현금영수증→현금승인번호) | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-8 | 공통 | PaddleOCR 경로가 rows만 받아 spans 미저장→스캔 문서 미리보기에서 병합 셀이 합쳐지지 않음 | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| TF-9 | 공통 | PP-StructureV3 표 모듈 구조 무너짐(세부내역서 여러 품목이 한 행에 합쳐짐)과 표 방향 분류기가 crop을 180도 회전 | parse | - | 해결 | Docraft/2026-09-22-table-refine.md |
| RP-1 | 진료비영수증 | 항목내역.항목 오답 119건이 rules 단계 최다, 룰 적용 후 영수증 84.4%·소견서 81.4%·진단서 88.0%(96% 목표 미달) | extract | - | 미해결 | Docraft/2026-09-22-rule-performance-review.md |
| RP-2 | 세부내역서 | rules 단계 빈 정답에 값을 채운 오탐 56건 | 후처리 | - | 미해결 | Docraft/2026-09-22-rule-performance-review.md |
| RP-3 | 소견서 | 치료명 8건·검사명 4건·병명 3건 오답(의미 추출) | extract | - | 미해결 | Docraft/2026-09-22-rule-performance-review.md |
| RP-4 | 공통 | rules.same이 4글자 이상 부분 포함·금액 빈 값과 0을 일치 취급해 병명·주소 등 의미 달라지는 필드도 느슨 판정 | 평가 | - | 미해결 | Docraft/2026-09-22-rule-performance-review.md |
| KB-1 | 진단서 | T2422/K296 등 두 병명을 첫 코드 행에 합치고 다음 행 병명을 비움→K296 원장 후보 4개라 기존 보완 중단(M4806/M511, M8786/M171, 세 행 결합 동일 유형) | extract | - | 해결 | harness-v2/2026-10-03-kcd-name-boundaries-fallback.md |
| KB-2 | 진단서 | 기존 병명 분리기가 쉼표·및 경계만 탐색하고 유사도 판정을 써 공백 경계를 못 찾고 병명 내부 구분자에서 잘못 자른 후보가 통과 | 후처리 | - | 해결 | harness-v2/2026-10-03-kcd-name-boundaries-fallback.md |
| KB-3 | 진단서 | 병원 세분 코드 M87862의 해석은 기존 코드 정규화·보수적 폴백 유지(분리기는 정규화 코드가 직접 원장에 있는 경우만 대상) | 후처리 | - | 미해결 | harness-v2/2026-10-03-kcd-name-boundaries-fallback.md |
| KB-4 | 진단서 | 병명 키 자체가 누락된 JSON(코드 행에 병명 키 없음)과 호출자 입력 보존 | 입력 | - | 해결 | harness-v2/2026-10-03-kcd-name-boundaries-fallback.md |
| SR-1 | 세부내역서 | 요약 행(소계·계·끝수)은 인쇄값 확인 후 확정 → 하네스가 행 사이 식으로 계산해 인쇄 확인 없이 repaired 확정 | 후처리 | 유형 A(인쇄값 대신 만든 값) | 해결 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-2 | 세부내역서 | 급여 열 미인쇄 서식에서 급여 빈칸 → 요약 행 급여를 0으로 바꾸고 항목 행은 AO의 0·총액 복사값이 그대로 출력 | 후처리 | 유형 A(인쇄값 대신 만든 값) | 해결 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-3 | 세부내역서 | 요약 행은 같은 종류끼리 짝지어야 함 → 키 열이 빈 요약 행이 코드 없는 항목 행과 순서대로 엇갈려 짝지어짐 | 후처리 | 유형 B(요약 행 신원 혼동) | 해결 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-4 | 영수증 | 총합계·끝처리 조정금액 등이 한 번만 있어야 함 → 다른 표기로 이미 있는 요약 행을 누락 복구(recover_rows)가 중복 추가 | 후처리 | 유형 B(요약 행 신원 혼동) | 해결 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-5 | 세부내역서 | 요약 라벨은 분류가 아님 → 소계 등 요약 라벨이 분류명(class_item_fixes 증거)으로 쓰임 | 후처리 | 유형 B(요약 행 신원 혼동) | 해결 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-6 | 세부내역서 | 급여 열 정책 결정 필요 → INFERRED_SUMS 급여_급여총액=본인+공단+전액본인 를 Docraft가 계산해 냄(범위 밖) | 후처리 | - | 결정대기 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-7 | 영수증 | 영수증 급여 열 금액을 비급여로 옮기고 급여 0으로 두는 _uncovered_benefit 의 정책 적용 여부 미정(세부내역서 정책 대상 아님) | 후처리 | - | 결정대기 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| SR-8 | 세부내역서 | 요약 라벨이 EDI명칭 칸에만 있는 AO 행을 합계·소계로 인식 → 인식 못 함(라벨 열 가정, 실측 사례 없음) | 후처리 | - | 미해결 | harness-v2/2026-10-03-summary-rows-printed-benefit.md |
| PAY-1 | 영수증 | 전액 수납 영수증(SA2019123157847) 납부할금액 0(빈칸) → R-AC029-PAYABLE 이 식 값 11000 을 요구해 fail 처리하고 Docraft가 먼 칸 11000을 읽어 채택해 값이 망가짐 | 후처리 | - | 해결 | harness-v2/2026-10-02-납부할금액-전액수납-빈칸.md |
| PAY-2 | 영수증 | 정답 0 + 수납 합계==환자부담총액 6건 중 요양급여_SA2019123044081 의 납부할금액이 공란으로 읽힘(AO 값 5건 0, 1건 공란) | extract | - | 해결 | harness-v2/2026-10-02-납부할금액-전액수납-빈칸.md |
| TP-1 | 공통 | 표 셀 빈칸 → Docraft None 이 미판독인지 실제 빈칸인지 구분 불가, 0 과 빈칸 혼동 위험(typed proof 로 명시적 빈칸만 인정) | 후처리 | - | 해결 | harness-v2/2026-09-27-Docraft-typed-proof와-명시적-빈칸.md |
| TP-2 | 공통 | Docraft 가 실제 OCR 표 셀 빈칸을 image_cell_blank 로 제공하는지 end-to-end 미확인(잘린 셀·모호한 셀 역할·불완전한 표 좌표는 자동 채택 불가) | parse | - | 미해결 | harness-v2/2026-09-27-Docraft-typed-proof와-명시적-빈칸.md |
| RC-1 | 영수증 | 2020010684177_3020010611181902 비급여 한 칸 서식에서 검사료.비급여 50000 유지 → 열 전체 맞바뀜으로 오판해 선택진료료외로 이동 | 후처리 | - | 해결 | harness-v2/2026-09-29-영수증-열-교정-보완.md |
| RC-2 | 영수증 | SA2019123157847_201912311546400b 제증명료.급여 11000 은 비급여(①②③+④ 서식) → 급여 열에 남아 환자부담총액 unresolved | 후처리 | - | 해결 | harness-v2/2026-09-29-영수증-열-교정-보완.md |
| RC-3 | 영수증 | 202501020959270c 요양병원 정액수가 행 이중계상 제외 → 항목 합에 더해져 합계 행 3칸 fail | 후처리 | - | 해결 | harness-v2/2026-09-29-영수증-열-교정-보완.md |
| RC-4 | 영수증 | SA2019123157847_201912311546400b 납부할금액·이미납부한금액 0 → 납부한금액_합계 11000 과 R-AC029-PAYABLE 불일치로 환자부담총액 unresolved 잔존 | extract | - | 해결 | harness-v2/2026-09-29-영수증-열-교정-보완.md |
| RC-5 | 영수증 | bbox 열 위치 기반 비급여·선택진료료외 서식 판별 미착수 | 후처리 | - | 미해결 | harness-v2/2026-09-29-영수증-열-교정-보완.md |
| RF-1 | 영수증 | SA2019112214096_2019112215445100 급여 키 15310(문서값) → 하위 칸 합 4593+10717 을 OCR이 계산해 만든 값, 항목 행 대조가 자기 비교 | parse | - | 해결 | harness-v2/2026-09-10-진료비영수증-서식구조-재검토.md |
| RF-2 | 영수증 | 전액본인부담 열 빈칸 → 공단부담금 열 전체 복제(10717·6504·17300), 두 총액 규칙 차이가 정확히 17300 | extract | - | 미해결 | harness-v2/2026-09-10-진료비영수증-서식구조-재검토.md |
| RF-3 | 영수증 | 합계 행 선택진료료외 40000 → 0 으로 읽히고 40000 이 OCR이 만든 비급여 키에 들어감 | extract | - | 결정대기 | harness-v2/2026-09-10-진료비영수증-서식구조-재검토.md |
| RF-4 | 영수증 | 항목 행 단위 항등식 CALC_AC029_11 이 27행 전부 fail → 서식상 합계 행에서만 성립(row_filter total_row 신설) | 평가 | - | 해결 | harness-v2/2026-09-10-진료비영수증-서식구조-재검토.md |
| RF-5 | 영수증 | 환자부담총액 식에 상한액 초과금(⑥) 미반영 → ⑥ 이 인쇄된 영수증에서 정상 문서 오탐 가능 | 평가 | §19-15 | 결정대기 | harness-v2/2026-09-10-진료비영수증-서식구조-재검토.md |
| RF-6 | 영수증 | 합의 근거 없는 규칙 6종(CALC_AC029_03·04, LOGIC_AC029_06·07, DOMAIN_AC029_08, FMT_AC029_09) 처리, DOMAIN_AC029_08 은 실측값 02 의 외래·입원 의미 미확인 | 평가 | §19-16 | 결정대기 | harness-v2/2026-09-10-진료비영수증-서식구조-재검토.md |
| VH-1 | 공통 | Judge 가 key 를 빠뜨려 판정 없음 → source=ao 로 내보내 거짓 확인(unknown 으로 표시하도록 수정) | 후처리 | - | 해결 | Docraft/2026-09-23-verify-hint-paths.md |
| VH-2 | 공통 | hint_paths 로 좁힌 final 만 검사 → 힌트 밖 구성 필드가 빠져 sum_mismatch 누락(checks_after 를 전체 필드+판정 값으로 계산) | 평가 | - | 해결 | Docraft/2026-09-23-verify-hint-paths.md |
| ES-1 | 공통 | 정답·응답 폴더 안 grade.json 덮어쓰기 → 정답 수정 시 과거 채점·리포트가 무효화되지 않고 가변 입력과 산출물이 함께 보관됨 | 평가 | - | 해결 | harness-v2/2026-10-03-evaluation-snapshots.md |
| ES-2 | 공통 | make_report.py 독립 실행 경로는 입력 동결 대상 밖(범위 밖) | 평가 | - | 미해결 | harness-v2/2026-10-03-evaluation-snapshots.md |
| MAT-1 | 세부내역서 | 치료재료 코드 45개 정확 충돌 → 수가(EDI:의치과_급여)와 코드 겹침, 수가가 우선되어 치료재료 명칭 아닌 수가 명칭에 적중 | 후처리 | - | 해결 | harness-v2/2026-09-15-치료재료-원장-적재.md |
| MAT-2 | 세부내역서 | 치료재료 667개 코드의 5자 접두가 수가 원장에 적중 → OCR 오독 시 E4 절단이 수가 코드로 오분류할 위험(정상 8자 코드는 정확 일치로 먼저 잡혀 완화) | 후처리 | - | 결정대기 | harness-v2/2026-09-15-치료재료-원장-적재.md |
| MAT-3 | 세부내역서 | 폐지 코드(deleted=Y 9건) 규칙 동작 미구현 | 후처리 | - | 해결 | harness-v2/2026-09-15-치료재료-원장-적재.md |
| DRG-1 | 세부내역서 | 645102410 판비콤프주(급여 약 표본) 약가 원장 적중 → 10개 회차에 없어 not_applicable 약품코드 범위 밖, 비급여·이전 회차 여부 미확인 | 후처리 | - | 미해결 | harness-v2/2026-09-18-약가-치료재료전체판-원장-적재.md |
| DRG-2 | 세부내역서 | 약가 적중 코드의 MASTER_0710_09 명칭 대조 → 한글 약품명 표기 차이(제형·함량 병기)로 오탐 가능, 실측 미확인 | 후처리 | - | 미해결 | harness-v2/2026-09-18-약가-치료재료전체판-원장-적재.md |
| DRG-3 | 세부내역서 | 비급여 원내코드(MCR301류) 원장 조회 확인 불가 → 급여구분 휴리스틱에 의존 | 후처리 | §19-20 | 미해결 | harness-v2/2026-09-18-약가-치료재료전체판-원장-적재.md |
| LV-1 | 공통 | 16.소견서 3 진단 사고발생일자 비교 탭 EXTRA(Golden 값 없음) → 편집 탭에는 키 자체가 없어 채택 불가(ghost 행 추가) | 평가 | - | 해결 | label_veiwer/2026-09-29-editor-mismatch-viz.md |
| LV-2 | 소견서 | 16.소견서 5 병명내역 표 셀 강조 전체 칸 → 절반만 칠해짐 | 평가 | - | 해결 | label_veiwer/2026-09-29-editor-mismatch-viz.md |
| LV-3 | 공통 | Golden 없는 문서도 비교 결과·AO 점수 표시, 필터 칩 숫자 ≠ 표시 행 수(INP-001 27 vs 14), Golden 비어서 생긴 차이를 소스 오류 빨강으로 표시 | 평가 | - | 해결 | label_veiwer/2026-09-29-compare-tab-usability.md |
| B1 | 공통 | 실측 파일명(X.tif.classification.<uuid>.json) 이미지 짝 매칭 → 7건 전부 unpaired로 산출물 0건 | 입력 | B1 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| B2 | 공통 | 문서코드 미확정(미지 doc_type, null, 입통원구분 없음/모호) → confirmed가 아니어야 하나 confirmed로 나감 | 후처리 | B2 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R1 | 영수증 | CALC_AC029_01 비급여를 선택진료외+선택진료료 합으로 읽어 이중 계상 → 비급여 0 아닌 영수증마다 확정 fail | 후처리 | R1 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R2 | 진단서 | SORT_KCD_06 주상병 부상병 임상 순서가 사전순과 다르다고 warn | 후처리 | R2 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R4 | 세부내역서 | CALC_0710_02 공란 횟수·일수를 0으로 채워 계산값 0 → 총액 행마다 fail(잠복) | 후처리 | R4 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R5 | 공통 | FMT_DATE_01 key_pattern 통원일이 통원일수에 매칭 → 값 채워지면 날짜 검사 fail(잠복) | 후처리 | R5 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R6 | 세부내역서 | EDI코드 칸의 9자리 숫자 약품코드 13/16행을 마스터에 없는 코드로 fail → 대부분 행 검토 대상 | 후처리 | R6 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R3 | 세부내역서 | 절사 허용 warn만 있는 필드가 기본값 review_required로 떨어져 정상 서류 16셀이 자동 확정 불가 | 후처리 | R3 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| R8 | 약제비영수증 | 빈 선택 필드 하나 때문에 15필드 중 13 확정인 문서가 undetermined | 후처리 | R8 | 해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| FDV-59 | 영수증 | 진료비영수증 열 복제 오독 1건이 열 합계 규칙으로 번져 검토 필드 59개(실제 오류 4개 안팎) | 후처리 | - | 미해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| FDV-DET8 | 세부내역서 | 세부내역서 진짜 판독 오류로 검토 필드 8개 남음 | extract | - | 미해결 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| FDV-MEDMAT | 세부내역서 | 치료재료 코드는 판별 근거가 없어 마스터 미존재 판정 분류 미처리 | 후처리 | - | 결정대기 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| FDV-EDISIM | 세부내역서 | 문서가 마스터보다 상세한 정상 EDI 명칭 표기를 유사도 임계로 fail 처리 | 후처리 | R7 | 결정대기 | harness-v2/2026-09-09-금요일-납품-오탐수정.md |
| SR-1 | 세부내역서 | 소계·계·합계·끝수처리 조정금액 행 기대 유지 → TABLE_HINT·keep_totals 부재로 집계 행 삭제 | extract | - | 해결 | Docraft/2026-10-03-summary-rows-printed-benefit.md |
| SR-2 | 세부내역서 | 인쇄된 급여액 열(급여액=총액) 기대 값 유지 → 급여=총액이면 지우는 규칙으로 급여 칸 삭제 | 후처리 | - | 해결 | Docraft/2026-10-03-summary-rows-printed-benefit.md |
| SR-3 | 세부내역서 | 코드2개_급여액 서식 급여액 열 인쇄됐으나 열 배치에서 빠져 급여 칸 5칸 오류 | parse | - | 미해결 | Docraft/2026-10-03-summary-rows-printed-benefit.md |
| SR-4 | 세부내역서 | 3022033115105207 방문별 합계 행 날짜 빈칸 기대 → 모델이 날짜 기재 | extract | - | 미해결 | Docraft/2026-10-03-summary-rows-printed-benefit.md |
| SR-5 | 세부내역서 | 20250102091737a0 계·끝수 행 소수(676782.5) 인쇄 vs 정답지 정수 | 평가 | - | 결정대기 | Docraft/2026-10-03-summary-rows-printed-benefit.md |
| SR-6 | 세부내역서 | 합계 행이 끝수처리 뒤 값으로 계 행 먼저 채운 합계 필드를 덮지 못함 | 후처리 | - | 미해결 | Docraft/2026-10-03-summary-rows-printed-benefit.md |
| PP-1 | 영수증 | 외래 진료종료일 빈칸 기대 → 진료시작일을 복사해 채움 | 후처리 | - | 해결 | Docraft/2026-10-03-printed-period-fields.md |
| PP-2 | 영수증 | 진료기간 미인쇄 시 빈칸 기대 → 표 날짜 최소·최대로 계산해 채움 | 후처리 | - | 해결 | Docraft/2026-10-03-printed-period-fields.md |
| PP-3 | 영수증 | 시작·종료가 같은 날짜로 인쇄된 진료기간에서 종료일 라벨 채우기가 exclusive에 막힘 | 후처리 | - | 미해결 | Docraft/2026-10-03-printed-period-fields.md |
| PO-1 | 세부내역서 | 비급여 칸 빈칸 기대 → 급/비 비급 표시와 총액으로 비급여에 복사 | 후처리 | - | 해결 | Docraft/2026-10-03-printed-only-derive.md |
| PO-2 | 세부내역서 | 날짜 열 하나만 인쇄된 서식 종료일자 빈칸 기대 → 시작일자 복사 | 후처리 | - | 해결 | Docraft/2026-10-03-printed-only-derive.md |
| PO-3 | 세부내역서 | 비급표현-KJM02605 비급 표시 열을 비급여 열로 편집거리 매칭해 표시 열 옆 금액이 비급여에 기재 | parse | - | 해결 | Docraft/2026-10-03-printed-only-derive.md |
| PO-4 | 세부내역서 | 3022033115105207 합계 행 종료일자 4칸 모델이 집계 행에 날짜 기재 | extract | - | 미해결 | Docraft/2026-10-03-printed-only-derive.md |
| PO-5 | 세부내역서 | SA2020010683931 처방일자·실시일자 두 열에서 정답지가 처방일자를 베낌 vs 인쇄된 실시일자 4칸 | 평가 | - | 결정대기 | Docraft/2026-10-03-printed-only-derive.md |
| SO-1 | 세부내역서 | 20250102091737a0·a2·a3.tif 가로 서식이 90도 눕혀진 스캔 → OCR 좌표 세로, 열 순서 판별 실패, 누락 117셀(asis 49.6·49.8·77.2%) | 입력 | - | 해결 | Docraft/2026-10-02-scan-orientation.md |
| SO-2 | 세부내역서 | 판별 이후 누락 셀 회복 여부는 AWS 재OCR 필요 | 미확정 | - | 결정대기 | Docraft/2026-10-02-scan-orientation.md |
| SO-3 | 공통 | verify.judge·스키마 생성 VLM 이미지는 방향 정규화 미적용 | 입력 | - | 미해결 | Docraft/2026-10-02-scan-orientation.md |
| AR-1 | 공통 | 앞쪽 미확정 필드가 문서당 4회 시도를 소비해 뒤쪽 필드 재처리 기회 제한 | 후처리 | - | 미해결 | Docraft/2026-09-27-auto-reprocess.md |
| AR-2 | 진단서 | 진단일 의도적 오독 → ROI·넓은 VLM 후보 모두 distant_label·비정확 출처로 거절 | 후처리 | - | 미해결 | Docraft/2026-09-27-auto-reprocess.md |
| AR-3 | 공통 | 주소 오독 1건 CORRECTED됐으나 최초값·교정값 모두 미검수 silver 라벨과 불일치 | 평가 | - | 미해결 | Docraft/2026-09-27-auto-reprocess.md |
| VX-1 | 영수증 | 병합 셀 표를 OCR 텍스트만으로 추출 → 열 합계 7300/17300을 7381/17221로 지어냄, 빈칸 이미_납부한_금액에 47300 기재 | extract | - | 해결 | Docraft/2026-09-22-vision-extract.md |
| VX-2 | 영수증 | PaddleOCR-VL 표 colspan 누락·합계 행 한 셀 뭉침·한글 오독(진찰료→진 찰 로, 역삼동→억삼동) | parse | - | 해결 | Docraft/2026-09-22-vision-extract.md |
| VX-3 | 영수증 | AI 스키마 생성이 금액 열을 불리언 플래그로 바꿔 금액 자리 없음 | extract | - | 해결 | Docraft/2026-09-22-vision-extract.md |
| VX-4 | 영수증 | 전액 본인부담·선택진료료 열이 스키마 생성에서 항목별 필드로 안 나옴 | extract | - | 미해결 | Docraft/2026-09-22-vision-extract.md |
| RT-1 | 영수증 | 진료비영수증 스캔 VLM 표가 rowspan 16 오류·전액본인부담 열 누락·합계 행 한 셀 | parse | - | 해결 | Docraft/2026-09-22-ruled-table-grid.md |
| RT-2 | 약제비영수증 | 흐린 괘선 오른쪽 표가 26행에서 2x2로 뭉개짐 | parse | - | 해결 | Docraft/2026-09-22-ruled-table-grid.md |
| RT-3 | 영수증 | 두 줄짜리 병합 셀(⑦진료비 총액)에 스캐너 줄무늬가 겹쳐 셀이 둘로 분리 | parse | - | 미해결 | Docraft/2026-09-22-ruled-table-grid.md |
| RT-4 | 진단서 | 휨이 큰 스캔에서 SLACK 초과 괘선을 놓쳐 좌측 라벨 일부 병합 | parse | - | 미해결 | Docraft/2026-09-22-ruled-table-grid.md |
| RT-5 | 공통 | 줄 OCR 서비스가 큰 PDF 페이지(4096px) 받으면 컨테이너 재시작 → 표가 VLM 구조로 남음(세부내역서·소견서·약제비영수증 PDF) | parse | - | 미해결 | Docraft/2026-09-22-ruled-table-grid.md |
| KV-1 | 영수증 | 1546387085517921.jpg 라벨 24행인데 26행, 투약및조제료_행위료가 19번째에 덧붙음(세분 항목 표 끝에 추가) | 후처리 | - | 해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-2 | 영수증 | SA2019070400018 주사료 행 중복 | 후처리 | - | 해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-3 | 세부내역서 | 1120210831 tif 16·17행 EDI코드 한 글자 오인식(CN001/DN001)으로 시작일자·횟수 행 뒤바뀜 | 평가 | - | 해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-4 | 영수증 | holdout 영수증 서식 인쇄 항목(의학료·혈액진단료·내복불출치료료) 대신 모델이 표준 항목명 출력 | extract | - | 미해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-5 | 영수증 | 155799374711284.jpg 라벨 3행인데 26행을 지어냄 | extract | - | 미해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-6 | 세부내역서 | EDI명칭 128건 1~2글자 오인식(모티리톤/모티리론), 영수증 제증명→제중영 전화상담료→전화봉화료 | parse | - | 미해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-7 | 영수증 | SA2019101165425 두 건 TIF 품질 불량으로 항목 머리글 못 잡아 0행(라벨 28행 대 예측 7행) | parse | - | 미해결 | Docraft/2026-09-22-kv-row-align.md |
| KV-8 | 세부내역서 | 3022033117174302-1.png 정답지 시작일자 20020226 오류(20200226) | 평가 | - | 미해결 | Docraft/2026-09-22-kv-row-align.md |
| PC-1 | 영수증 | 긴 문서 예산(40000자) 초과 시 뒤쪽 페이지 블록이 조용히 버려져 추출 누락 | 입력 | - | 해결 | Docraft/2026-09-22-extract-page-chunking.md |
| PC-2 | 공통 | 블록 하나가 예산 초과(거대 표 HTML)면 그 블록만 잘림 | 입력 | - | 미해결 | Docraft/2026-09-22-extract-page-chunking.md |
| JP-1 | 세부내역서 | 2303314528.png 추출이 VLM 응답 JSON 파싱 오류(Expecting delimiter)로 실패 → strict json_schema 키 정렬·반복 루프(횟수 0 411개) | extract | - | 해결 | Docraft/2026-09-21-extract-json-parse-failure.md |
| JP-2 | 세부내역서 | 같은 행 안에서 필드가 한 칸씩 밀린 경우 행 단위 합의로 감지 못함 | extract | - | 미해결 | Docraft/2026-09-21-extract-json-parse-failure.md |
| LG-1 | 영수증 | VL이 진찰료를 진 찰 로로 오독해 행 매칭 실패 → grounding confidence 0.0 거짓 경고(줄 OCR은 정확) | parse | - | 해결 | Docraft/2026-09-22-ocr-line-grounding.md |
| LG-2 | 영수증 | 47,300 등 서로 다른 셀 4개 leaf가 같은 bbox로 근거 오판 | 후처리 | - | 해결 | Docraft/2026-09-22-ocr-line-grounding.md |
| LG-3 | 세부내역서 | 약품명 괄호·단위 한 글자 차이(아세트아미노렌/펜)로 줄 근거 매칭 실패 | parse | - | 해결 | Docraft/2026-09-22-ocr-line-grounding.md |
| LG-4 | 공통 | 불리언 leaf가 원문에 없어 confidence 0.0 low_confidence 오탐 | 후처리 | - | 해결 | Docraft/2026-09-22-ocr-line-grounding.md |
| AE-1 | 세부내역서 | 기존 9건 98.0% 대비 신규 10건 74.9%로 하락(표본 확대 발견) | extract | - | 미해결 | Docraft/2026-09-22-accuracy-eval-expansion.md |
| AE-2 | 소견서 | 소견서 76건 평가 정확도 73.4%, 치료·검사 소견 문장 vs 행위 분리 라벨 관례 모호 | 평가 | - | 결정대기 | Docraft/2026-09-22-accuracy-eval-expansion.md |
| AE-3 | 영수증 | 항목 머리글을 잃은 OCR 결과에서 표준 항목 행 복원 불가, 영수증 91.6% | parse | - | 미해결 | Docraft/2026-09-22-accuracy-eval-expansion.md |
| AE-4 | 진단서 | 진단서 정확도 85.0%(FP 42) 96% 목표 미달 | extract | - | 미해결 | Docraft/2026-09-22-accuracy-eval-expansion.md |
| E210-1 | 영수증 | AO 폴링 한도(300초) 초과로 공란다수_* 진료비영수증 8건 running 상태로 타임아웃 | 입력 | - | 미해결 | Docraft/2026-09-24-e2e-210-plan.md |
| E210-2 | 공통 | 같은 코드 재실행도 결과 변동(나빠짐 23·좋아짐 24) | 평가 | - | 미해결 | Docraft/2026-09-24-e2e-210-plan.md |
| VR-1 | 영수증 | verify 룰 1차 전환 시 모델이 금액 빈 항목 행을 버리면 룰이 복구 못 함(항목내역.항목 실패 240건) | extract | - | 미해결 | Docraft/2026-09-22-verify-rule-first-plan.md |

## 2. edge_cases.yaml 메커니즘

| id | layer | taxonomy | 설명 | evidence.refs |
|---|---|---|---|---|
| orientation | capture | AUX.INPUT | orientation (label_rule=visible_only) | IN-2, G1-a [observed] |
| region_loss | capture | P.MIS.AREA.2, AUX.INPUT | region loss (label_rule=visible_only) | partial_paper_crop [observed] |
| resolution_loss | capture | P.MIS.CHAR.1, P.MIS.CHAR.2, AUX.INPUT | resolution loss (label_rule=visible_only) | IN-5, IN-6 [observed] |
| photometric | capture | P.MIS.CHAR.1, P.WRG.READ.1 | photometric (label_rule=visible_only) | CMN-002 [observed] |
| document_boundary | composition | P.STR.DOC.1, P.STR.DOC.2 | document boundary (label_rule=printed_verbatim) |  [expected] |
| length_scale | composition | P.MIS.AREA.1, E.MIS.TARGET.1 | length scale (label_rule=semantic_position) | IN-3 [observed] |
| page_boundary_split | composition | P.STR.LINK.2, E.WRG.CTX.3 | page boundary split (label_rule=semantic_position) | IN-4 [observed] |
| cell_displacement | template | E.WRG.ASSIGN.1, E.WRG.ASSIGN.2, P.WRG.POS.1, P.STR.REL.3 | cell displacement (label_rule=semantic_position) | G1-d, G2-b, G2-c, G2-d, G7-a, LY-1 [observed] |
| structure_omission | template | E.MIS.FIELD.2, P.MIS.UNIT.2, P.OVR.GEN.1 | structure omission (label_rule=visible_only) | G7-b, G2-a [observed] |
| non_data_rows | template | E.OVR.SCOPE.1, E.OVR.SCOPE.2, P.WRG.TYPE.2, P.STR.HIER.2 | non data rows (label_rule=semantic_position) | G5-a, G2-c [observed] |
| span_hierarchy | template | E.WRG.CTX.2, P.STR.REL.1, P.STR.HIER.1, E.STR.GROUP.1 | span hierarchy (label_rule=semantic_position) | G5-b [observed] |
| header_variation | template | P.STR.REL.2, E.WRG.CTX.1 | header variation (label_rule=semantic_position) | RM-3, LY-1 [observed] |
| semantic_duplicate | template | E.OVR.DUP.2, P.OVR.DUP.2, E.STR.ARRAY.1 | semantic duplicate (label_rule=semantic_position) | G4-a, G5-c [observed] |
| distractor_values | template | E.WRG.ASSIGN.1, E.OVR.SCOPE.2, E.WRG.PICK.1, P.WRG.TYPE.1 | distractor values (label_rule=semantic_position) | G1-a, G1-c, G3, LY-5 [observed] |
| glyph_confusion | content | E.WRG.READ.1, P.WRG.READ.1 | glyph confusion (label_rule=printed_verbatim) | G4-b, G8, OC-3 [observed] |
| numeric_format | content | E.MIS.PART.2, E.WRG.NORM.2, E.WRG.NORM.3, P.WRG.READ.2 | numeric format (label_rule=printed_verbatim) | G2-e, NRM-006, NRM-008, NRM-011 [observed] |
| surface_form | content | AUX.POST.NORM, E.WRG.NORM.4, E.MIS.PART.1 | surface form (label_rule=printed_verbatim) | G1-e, MP-4, MP-5 [observed] |
| encoded_categorical | content | E.WRG.NORM.1, E.WRG.NORM.4 | encoded categorical (label_rule=printed_verbatim) | G9, LY-3 [observed] |
| partial_record | content | E.MIS.PART.1, E.MIS.FIELD.2, E.MIS.FIELD.1 | partial record (label_rule=visible_only) | G10 [observed] |
| multi_value_cell | content | E.MIS.PART.3, E.CON.SCHEMA.3, P.STR.SPLIT.1, E.STR.SPLIT.1 | multi value cell (label_rule=printed_verbatim) | RM-3, MP-5 [observed] |
| printed_inconsistency | content | AUX.POST.ALTER, AUX.POST.VALID, E.WRG.PICK.2, E.CON.RANGE.3 | printed inconsistency (label_rule=printed_verbatim) | RV-5, RV-6 [observed] |
| unprinted_derivable | content | E.OVR.GEN.2, E.OVR.GEN.1, P.OVR.GEN.1 | unprinted derivable (label_rule=visible_only) | G3 [observed] |
| fact_attributes | content | E.WRG.ATTR.1, E.WRG.ATTR.2, E.WRG.ATTR.3, E.WRG.ASSIGN.3 | fact attributes (label_rule=printed_verbatim) |  [expected] |
| selection_marks | overlay | E.WRG.READ.3, P.MIS.MARK.1, P.WRG.STATE.1 | selection marks (label_rule=semantic_position) | G6, OC-5 [observed] |
| occlusion | overlay | P.OVR.FALSE.1, P.MIS.AREA.2, P.WRG.STATE.2, P.WRG.STATE.3, E.MIS.ABST.1, E.MIS.ABST.2 | occlusion (label_rule=ink_visibility) | OC-6, stamp_overlap [observed] |
| handwriting | overlay | P.MIS.MARK.2, P.WRG.READ.3, P.STR.REL.4 | handwriting (label_rule=ink_visibility) | handwriting_margin [observed] |
