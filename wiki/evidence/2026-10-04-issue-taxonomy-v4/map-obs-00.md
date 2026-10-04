# 분류 대응 검증 결과 map-obs-00

입력 obs-chunk-00.md 288행. 기준 v3+v4. 상태 열은 위 기준 문서 표기를 따름.

## 요약

판정별 건수: OK 239, AMBIG 16, NEW 1, NA 32 (합계 288)

### AMBIG·NEW 목록

- G2-a (103201·103300·103302·103101·103200, 37… [AMBIG] 요약 행(소계·계·합계) 단가·횟수·일수·투여량 빈칸→`0` -> 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: 미인쇄 빈칸→0 을 정규화(빈값·0 혼동)로 볼지 과추출(빈칸을 값으로 채움)로 볼지 미정
- BM-3 (표 비급여·선택진료료외 3, 항목 하이픈 제거 1, Docraft 교… [AMBIG] 기타 악화 6칸(비급여·선택진료료외 금액 채움, 항목 하이픈 제거, Docraft 교정 악화) -> 후보: AUX.POST.ALTER, E.OVR.GEN.2, E.WRG.NORM.4(하이픈 제거); 규칙: 건별 확인 전 귀속 미확정인 합산 행은 셀 단위로 분리해 기록
- RD-1 (SA2019123043735_2019123013232302 요양기관종… [AMBIG] 일치→불일치: Docraft가 `[V]의원급·보건기관`(체크 표시 포함) 읽은 값을 repaired 채택 -> 후보: E.WRG.READ.2, P.OVR.FALSE.1(비문자 선택 표시를 글자로 인식), E.WRG.READ.3; 규칙: 선택 표시 기호가 값 문자열에 섞였으나 선택 상태는 맞은 경우의 귀속
- IT-2 (r4·r5 45314 표 408) [NEW] Docraft /api/read HTTP 408 시한 초과로 재판독·끝수처리 행 누락 -> 칸: K1 x 행/표; AUX.RUN 하위 신규 '호출 실패·시한 초과로 하위 결과 소실' (현 AUX.RUN은 중복·순서·혼입·캐시만)
- CLS-3 (AUX.EVAL 상한액초과금 29칸) [AMBIG] 키 `상한액초과금`(정답지)↔`상환액초과금`(AO·하네스) 불일치로 채점기가 칸 못 찾음(값은 맞음, 약 0 -> 후보: AUX.EVAL, E.CON.SCHEMA.1; 규칙: 정식 키가 계약에 확정되지 않은 키 표기 불일치의 귀속(확정이면 SCHEMA.1, 미확정이면 AUX.EVAL)
- CLS-5 (E.WRG.NORM.3 13칸) [AMBIG] 투여량·날짜 칸 빈칸↔0 -> 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: 빈칸↔0 교환을 정규화로 볼지 과추출로 볼지 미정(v3 '빈칸을 값으로 채움=과추출'과 NORM.3 충돌)
- CLS-7 (UNCLASSIFIED 7칸: 종료일자 4칸·사고발생일자 1·급여 … [AMBIG] 정답 종료일자는 행마다 같은데 출력은 행마다 다른 날짜 4칸 등 -> 후보: E.WRG.CTX.2, E.WRG.PICK.1, E.WRG.ASSIGN.2; 규칙: 정보 부족(행마다 다른 날짜 출력의 원인 미확인), 7칸 이질적 묶음은 칸별 분리 필요
- EC-E01 [AMBIG] [예상] 환자·보호자·계약자·의사 이름 공존: 환자 이름 → 다른 사람에게 연결 -> 후보: E.WRG.ASSIGN.3, E.WRG.ATTR.3, E.WRG.CTX.4, E.WRG.PICK.1; 규칙: 같은 역할 필드(환자 성명)에 다른 당사자 값 선택 시 ASSIGN/ATTR/PICK 구분
- EC-E02 [AMBIG] [예상] 진료일·입원일·퇴원일·발행일·결제일 공존: 해당 역할 날짜 → 형식만 맞는 다른 날짜 채택 -> 후보: E.WRG.ASSIGN.3(시점 역할), E.WRG.PICK.1; 규칙: 역할별 라벨이 분리된 복수 날짜 중 틀린 날짜 채택이 후보 선택인지 역할 배정인지
- EC-E03 [AMBIG] [예상] 총액·본인부담·공단부담·수납·미수·환불 공존: 요청 금액 → 잘 보이는 합계 선택 -> 후보: E.WRG.ASSIGN.3, E.WRG.PICK.1; 규칙: 역할 구분 금액(총액·본인·공단 등) 중 틀린 것 선택, 위와 같음
- RP-07 [AMBIG] 사고발생일자: 별도 라벨 없음, 스키마가 진료시작일과 같은 의미로 정의 → 직접 인쇄 근거와 별칭 근거 구분 -> 후보: AUX.EVAL(스키마 중복 정의), E.CON.EVID.1; 규칙: 스키마가 같은 의미로 정의한 별칭 필드의 근거 종류(직접 인쇄 vs 별칭)
- NC-04 [AMBIG] 명시적 빈칸(금액): null → 0 또는 비공란 값 오추출 2건 (빈 칸 닫힌 물리 셀 영상 근거로 교정) -> 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: 빈칸→0·비공란 값 혼재 시 0은 정규화, 비0은 과추출로 나누는 규칙 부재
- NC-07 [AMBIG] AO 표본 24 초과금: 정답 null → AO 0 유지 (직접 근거 없음, 분기 9 unresolved) -> 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: null→0 (위와 같음)
- NC-08 [AMBIG] AO 표본 33 금액 3칸(총액·공단부담액·급여본인부담): 정답 → AO 오답 (현재 코드 live에서 7- -> 후보: E.WRG.READ.1, E.WRG.ASSIGN.1, E.MIS.FIELD.2; 규칙: 정보 부족(오답 유형 미기재)
- WO-12 [AMBIG] [지시서 예시] 같은 Key `성명`이 환자정보·의사정보에 중복: 환자 성명 → 의사 성명 선택 -> 후보: E.WRG.ASSIGN.3, E.WRG.CTX.4, E.WRG.PICK.1, E.WRG.ATTR.3; 규칙: 동일 라벨 복수 당사자 중 선택(EC-E01과 같음)
- TD-21 [AMBIG] 스키마 키 `한약(첩약)` vs 하네스 표준명 `한약첩약` (기존부터 다름) -> 후보: E.CON.SCHEMA.1, AUX.EVAL; 규칙: 정식 키 미확정 시 키 표기 차이(CLS-3과 같음)
- WB-10 [AMBIG] 급여구분이 자리표시 `열추출` → 빈칸으로 비움 -> 후보: E.OVR.GEN.1, E.CON.RANGE.1, AUX.EVAL; 규칙: AO 자리표시값(열추출)을 오류로 볼지 정책상 정답으로 볼지 미정(BM-1에서 정답 유지로 결정)

### 자주 쓴 ID 상위 15 (원인+후속 합산)

1. AUX.EVAL (39)
2. E.WRG.ASSIGN.2 (26)
3. E.MIS.FIELD.2 (26)
4. E.OVR.DUP.2 (18)
5. AUX.POST.ALTER (16)
6. E.OVR.GEN.2 (12)
7. E.OVR.GEN.1 (12)
8. P.WRG.READ.1 (12)
9. E.WRG.CTX.1 (12)
10. E.WRG.ASSIGN.1 (11)
11. E.WRG.READ.1 (10)
12. E.WRG.READ.3 (9)
13. E.CON.EVID.1 (9)
14. E.MIS.FIELD.1 (8)
15. AUX.INPUT (7)

### 메모
- 문서에 적힌 분류ID 중 G7-b(요양급여)는 평가 원인(계→합계 표준명 치환의 채점 어긋남)으로 보고 AUX.POST.NORM→AUX.EVAL로 바로잡음. BEN-7·G9는 급여구분 의미 오해(NORM.1)→배정(ASSIGN.1)으로 연결.
- 반복 AMBIG 축: (1) 빈칸↔0 은 NORM.3 vs GEN.1, (2) 같은 역할 후보 중 다른 당사자·날짜·금액 선택은 ASSIGN.3 vs PICK.1 vs ATTR.3 vs CTX.4, (3) 정식 키 미확정 키 표기 차이는 SCHEMA.1 vs AUX.EVAL, (4) 선택 표시 기호가 값 문자열에 섞임, (5) AO 자리표시값.
- NEW: AUX.RUN 하위 '호출 실패·시한 초과로 결과 소실' 하나. 나머지 OK 239건은 AUX.EVAL(정답지·정책)·E.OVR.DUP.2·E.WRG.ASSIGN.2 계열로 흡수됨.
- 헤더 인식 계열(HDR-*)은 E.WRG.CTX.1(머리글 의미 연결)+AUX.POST.ALTER(맞는 값 지움)로 처리. 별도 노드는 불필요하나 하네스 사전 동의어 부재는 AUX.REF 확장 후보.
- 우산·복합 행(CLS-7·CLS-10·BM-3·WO-06·WO-08·WO-13·WO-15)은 칸 단위로 분리해야 정확 분류 가능.

## 전체 표

| 사례ID | 원인ID | 후속ID | K | 단위 | 판정 | 비고 |
|---|---|---|---|---|---|---|
| G1-a (20250102091737a3 합계 비급여총액) | AUX.POST.VALID | E.WRG.READ.1 | K3 | 값 | OK | 회전 팩스 먼 0을 식 일치로 채택 |
| G1-b (3022030712433802-1 유령 행) | AUX.POST.ALTER | E.OVR.GEN.2 | K2 | 행 | OK | recover_rows가 유령 행 추가 |
| G1-c (공란다수_…43183 납부할금액) | E.WRG.ASSIGN.1 | AUX.POST.VALID | K4 | 필드 | OK | 다른 필드 값 복사, 식 통과로 채택 |
| G1-d (SA2019123157847_…390b 공단부담금) | E.WRG.ASSIGN.2 | - | K4 | 열 | OK | 열 통째 밀림(패턴 축), 미탐지는 자동 탐지 축 |
| G1-e (43806·390i·400b 항목명) | AUX.POST.NORM | AUX.EVAL | K3 | 값 | OK | 표준명 치환; 결정1로 채점 동치 처리 |
| G2-a (103201·103300·103302·103101·103200, 37… | E.WRG.NORM.3 | - | K3 | 값 | AMBIG | 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: 미인쇄 빈칸→0 을 정규화(빈값·0 혼동)로 볼지 과추출(빈칸을 값으로 채움)로 볼지 미정 |
| G2-b (103101 16380/820/15560, 103200 16430 등… | E.WRG.ASSIGN.2 | - | K4 | 행 | OK | 요약 행 값 왼쪽 칸 몰림(일괄 밀림) |
| G2-c (103001·103101·103201·103300·103302 끝수 … | E.WRG.ASSIGN.2 | E.MIS.FIELD.2 | K4 | 행 | OK | 끝수 행 값 밀림·누락 |
| G2-d (…84292_215001 계 행) | E.MIS.FIELD.2 | E.WRG.ASSIGN.2 | K1 | 필드 | OK | 칸 하나 빠져 한 칸 밀림 연쇄 |
| G2-e (20250102091737a3 계·끝수 행) | E.MIS.PART.2 | - | K3 | 값 | OK | 소수점 소실(원인 P.MIS.CHAR.2 가능) |
| G2-f (비급표현-KJM02605 9·13행) | E.OVR.DUP.2 | - | K2 | 필드 | OK | 미인쇄 급여 칸에 총액 복사 |
| G3 (급여액_2303314628) | E.OVR.GEN.2 | - | K2 | 필드 | OK | 인쇄 없는 합계를 항목합으로 계산 |
| G3 (20230104_123952) | E.OVR.GEN.2 | - | K2 | 필드 | OK | - |
| G3 (비급표현-KJM02605) | E.OVR.GEN.2 | - | K2 | 필드 | OK | - |
| G3 (2303315388) | E.OVR.GEN.2 | - | K2 | 필드 | OK | - |
| G4-a (103101·103200) | E.OVR.DUP.2 | - | K2 | 필드 | OK | 원내코드를 EDI코드와 동일하게 복제 |
| G4-b (20230104_123952) | E.WRG.READ.1 | - | K3 | 문자 | OK | O↔0 혼동 |
| G5-a (SA2020010683384 103001 +2행, 103100 +3행) | E.OVR.SCOPE.1 | AUX.EVAL | K2 | 행 | OK | 섹션 제목 행이 레코드로 출력, 뷰어 행 맞춤 어긋남 |
| G5-b (2303314855 5·6행) | E.WRG.CTX.2 | - | K7 | 필드 | OK | 병합칸 분류명이 아래 행에 상속 안 됨 |
| G5-c (3022030712433802-1) | E.OVR.DUP.2 | - | K2 | 필드 | OK | 분류 열 대신 EDI명칭 복사 |
| G6 (45314) | E.WRG.READ.3 | - | K8 | 표시 | OK | 체크 미판독→첫 선택지, 신뢰도로 거를 수 없음(미탐) |
| G6 (39576) | E.WRG.READ.3 | - | K8 | 표시 | OK | 의심 미탐 |
| G6 (390b) | E.WRG.READ.3 | - | K8 | 표시 | OK | - |
| G6 (400b) | E.WRG.READ.3 | - | K8 | 표시 | OK | r3 Docraft가 V만 반환(회귀) |
| G6 (390i) | E.WRG.READ.3 | - | K8 | 표시 | OK | r3 Docraft가 V만 반환(회귀) |
| G6 (1624239c / 202501021624239c) | E.WRG.READ.3 | - | K8 | 표시 | OK | - |
| G6 (43806) | E.WRG.READ.3 | - | K8 | 표시 | OK | Docraft SUSPICIOUS로 오답은 후속 AUX.POST.EVID 후보 |
| G6 (번들 전체) | E.WRG.READ.3 | - | K8 | 표시 | OK | 9건 중 7건 첫 선택지 출력(집계 사례) |
| G6-4 (정답지 표기 혼재) | AUX.EVAL | - | K3 | 값 | OK | 정답지 표기 혼재→표준 4값 |
| G7-a (202501021624239c) | E.WRG.ASSIGN.2 | - | K4 | 행 | OK | 값이 두 행 위로 밀림 |
| G7-b (45314) | E.MIS.FIELD.1 | E.WRG.ASSIGN.2 | K1 | 행 | OK | 행 누락 후 아래 행 이름 밀림 |
| G7-b (요양급여_…023627730) | AUX.POST.NORM | AUX.EVAL | K3 | 값 | OK | 행 누락처럼 보이나 계→합계 이름 때문에 채점 어긋남 |
| G8 진료과 (45314) | E.WRG.READ.1 | - | K3 | 값 | OK | 진료과 사전(AUX.REF)으로 보정 |
| G8 병원명 (43183) | E.WRG.READ.1 | - | K3 | 값 | OK | 기관 마스터 필요(AUX.REF) |
| G9 (3022…-1 12행) | E.WRG.ASSIGN.1 | E.WRG.NORM.1 | K4 | 필드 | OK | 급여구분(80/100) 의미 오해로 급여 금액을 전액본인부담에 배정 |
| G10 (코드2종포함_2303315044) | E.WRG.ASSIGN.2 | E.MIS.PART.2 | K4 | 행 | OK | 값이 단가 칸으로 이동하고 횟수 일부 잘림; MASTER warn 통과는 미탐 |
| G-정답지 (43806) | AUX.EVAL | - | K3 | 값 | OK | 정답지 오기 |
| G-정답지 (20230104_123952 0행 원내코드) | AUX.EVAL | - | K3 | 값 | OK | - |
| G-정답지 (SA2020010683384_…103201 AAL020 투여량) | AUX.EVAL | - | K3 | 값 | OK | - |
| G-정답지 (2020010684177·157794·157840·47809·400… | AUX.EVAL | - | K3 | 값 | OK | - |
| G-정답지 요약 행 0 (2303314662·2303314712·23033152… | AUX.EVAL | - | K3 | 값 | OK | 요약 행 0 정책(결정2) |
| VIEW-1 (SA2020010683384 103001·103100) | AUX.EVAL | - | - | 행 | OK | 뷰어 행 맞춤 오류; 문서 ID G5-a 연결은 후속 원인(E.OVR.SCOPE.1) |
| EVAL-로컬재실행 깨진 14칸 | AUX.EVAL | - | K3 | 값 | OK | 정답지 수정 반영 대기 |
| BM-1 (급여구분 열추출 334칸) | AUX.POST.ALTER | E.MIS.FIELD.2 | K3 | 필드 | OK | 열추출 정책 결정 후 정답지 열추출 유지 |
| BM-2 (시작·종료일자 52칸) | AUX.POST.ALTER | E.MIS.FIELD.2 | K3 | 필드 | OK | _period_copies가 맞는 값을 지움 |
| BM-3 (표 비급여·선택진료료외 3, 항목 하이픈 제거 1, Docraft 교… | AUX.POST.ALTER | E.OVR.GEN.2 | K3 | 값 | AMBIG | 후보: AUX.POST.ALTER, E.OVR.GEN.2, E.WRG.NORM.4(하이픈 제거); 규칙: 건별 확인 전 귀속 미확정인 합산 행은 셀 단위로 분리해 기록 |
| BM-4 (SA2019123157847_201912311546380f.tif) | AUX.REF | E.CON.RANGE.1 | K10 | 필드 | OK | 서식 코드→문서 유형명 변환(코드표) 조회 누락 |
| RD-1 (SA2019123043735_2019123013232302 요양기관종… | E.WRG.READ.2 | - | K3 | 값 | AMBIG | 후보: E.WRG.READ.2, P.OVR.FALSE.1(비문자 선택 표시를 글자로 인식), E.WRG.READ.3; 규칙: 선택 표시 기호가 값 문자열에 섞였으나 선택 상태는 맞은 경우의 귀속 |
| RD-2 (항목 EDI명칭 복사 19칸) | E.OVR.DUP.2 | - | K2 | 필드 | OK | EDI명칭 복사 값을 빈값으로 교정 |
| RD-3 (20250102091737a3 항목내역 rows[3]·[4]) | AUX.EVAL | - | K3 | 값 | OK | 정답지 소수 버림 |
| RD-4 (보고 버전 2026.09.8 고정) | - | - | - | - | NA | 보고 버전 표기(운영 설정) |
| IT-1 (r3 45314) | AUX.POST.ALTER | E.WRG.READ.3 | K3 | 값 | OK | 모호 출처를 버려 맞는 값 삭제(맞는 값을 지움) |
| IT-2 (r4·r5 45314 표 408) | AUX.RUN | E.MIS.FIELD.1 | K1 | 행 | NEW | 칸: K1 x 행/표; AUX.RUN 하위 신규 '호출 실패·시한 초과로 하위 결과 소실' (현 AUX.RUN은 중복·순서·혼입·캐시만) |
| IT-3 (unresolved 칸 value가 AO 원값 `의원급`) | E.CON.RANGE.1 | - | K10 | 값 | OK | 보류 칸 값이 표준 4값 밖(AO 원값) |
| BEN-1 (급여 열 미인쇄 문서) | AUX.EVAL | - | K3 | 필드 | OK | 정책: 미인쇄 열 정답 |
| BEN-2 (급여액_2303314628) | AUX.EVAL | - | - | 필드 | OK | 인쇄 여부 불명(정책 미확정) |
| BEN-3 (선택진료료·선택진료료외·본인·공단·전액본인부담·비급여·총액 미인쇄 … | E.OVR.DUP.2 | E.OVR.GEN.1 | K2 | 필드 | OK | 미인쇄 열 복사와 0 채움 복합 |
| BEN-4 (20250102091737a3 계·끝수 6칸) | AUX.EVAL | - | K3 | 값 | OK | 정답지 소수 반영 |
| BEN-5 (3022033115105207 총액 954.5, 단가 18, 비급여… | AUX.EVAL | - | K4 | 필드 | OK | 정답지 금액 자리 통일 |
| BEN-6 (코드2개 소계 급여액 786·69080) | AUX.EVAL | E.MIS.FIELD.2 | K4 | 필드 | OK | 정답지 자리 수정 후 Docraft 급여액 누락 2칸 잔존 |
| BEN-7 (Docraft 급/비 표시 → 비급여 11칸) | E.WRG.NORM.1 | E.WRG.ASSIGN.1 | K4 | 필드 | OK | 급/비 표시 의미 해석 후 금액을 비급여로 이동 |
| BEN-8 (단일 날짜 열 종료일자, 5491 24건 221칸·2965 17건 … | E.OVR.DUP.2 | - | K2 | 필드 | OK | 종료일자에 시작일자 복사 |
| BEN-9 (SA2020010683931 5~8행 종료일자) | AUX.EVAL | - | K3 | 값 | OK | 정답지 오기 |
| BEN-10 (진료종료일 152칸·진료시작일 5칸) | E.OVR.GEN.2 | E.OVR.DUP.2 | K2 | 필드 | OK | 미인쇄 문서 단위 날짜를 복사·계산(min/max) |
| BEN-11 (결정 필요: 종료일자=시작일자 복사 관례) | AUX.EVAL | - | K2 | 필드 | OK | 정책 결정대기(종료일자 복사 관례) |
| BEN-12 (20230228094825256178 수량) | AUX.EVAL | - | K4 | 필드 | OK | 수량 자리 정책(횟수 vs 투여량) 미정 |
| BEN-13 (진료기간 미인쇄 쪽) | AUX.EVAL | - | K1 | 필드 | OK | 진료기간 미인쇄 시 빈칸 허용 정책 |
| FD-1 (SA2020010683384_* 9건, 20230104_123952,… | E.WRG.CTX.2 | E.OVR.DUP.2 | K7 | 필드 | OK | 섹션 제목을 항목으로 상속하지 못함 |
| FD-2 (2303315388) | E.WRG.CTX.2 | - | K7 | 필드 | OK | 무리 첫 행에만 인쇄된 분류를 아래로 상속 안 함 |
| FD-3 (20230104·비급표현-KJM02605·코드2개 시작·종료일자) | E.WRG.CTX.2 | - | K7 | 필드 | OK | 진료기간 상속; 10/03 인쇄값만 정책으로 오류 정의 변경 |
| FD-4 (정답 소계·계·합계·끝수 행 96칸 항목 불일치) | E.MIS.TARGET.2 | - | K1 | 행 | OK | 요약 행 표 제외; 정책 결정대기 |
| FD-5 (OCR 오인식 `19. 비급여CT,MR`, 정답 오타 `80.`←`B… | P.WRG.READ.1 | AUX.EVAL | K3 | 문자 | OK | 복합 행: OCR 오인식·정답 오타(AUX.EVAL)·행 순서(P.WRG.ORDER.1) |
| FD-6 (소계 행에 항목 행 붙어 채점된 날짜 4칸) | E.MIS.TARGET.2 | AUX.EVAL | K1 | 행 | OK | 소계 행 부재로 행 맞춤 어긋남 |
| HDR-1 (금액 | E.WRG.CTX.1 | AUX.POST.ALTER | K7 | 열 | OK | 금액 머리글을 단가 열로 연결 못 함, 인쇄 단가를 지움 |
| HDR-2 (SA2020010683384·2303315388·2025010109… | E.WRG.CTX.1 | AUX.POST.ALTER | K7 | 열 | OK | 금액→단가 별칭 부재 |
| HDR-3 (합쳐진 머리글 칸 `금액 횟수`·`횟수일수`·`횟수 일수`·`명칭 … | P.STR.SPLIT.1 | E.WRG.CTX.1 | K5 | 셀 | OK | 이웃 머리글을 한 칸으로 읽음 |
| HDR-4 (2303314662·2303314712 쌓인 칸) | P.STR.SPLIT.1 | E.WRG.CTX.1 | K5 | 열 | OK | 열 전체가 한 칸에 쌓임 |
| HDR-5 (2303314855·SA2020010684292 묶음 `급여` 윗단) | P.STR.REL.2 | E.WRG.CTX.1 | K7 | 행 | OK | 묶음 머리글 윗단이 머리글 행으로 선택됨 |
| HDR-6 (동의어 `전액본인`·`선택진료`·`투약`·`용량`·`총투`) | E.WRG.CTX.1 | - | K7 | 열 | OK | 서식별 열 이름 동의어 사전 부재 |
| HDR-7 (같은 열 이름 칸 둘) | E.WRG.CTX.1 | - | K7 | 열 | OK | 같은 열을 가리키는 칸 둘 제외(하네스 로직) |
| HDR-8 (급여액_2303314628) | P.MIS.UNIT.2 | - | K1 | 행 | OK | 파싱 표에 머리글 행 없음 |
| HDR-9 (3022033115105207-1 투여량 머리글 `층투`) | P.WRG.READ.1 | E.WRG.CTX.1 | K3 | 문자 | OK | 총투→층투 오독 |
| HDR-10 (`투약일수` 머리글) | E.WRG.CTX.1 | - | K7 | 열 | OK | 잠재: 투약일수 분절 오류(단어 경계는 P.WRG.READ.4 후보) |
| UC-1 (3022033115105207 단가 18·비급여 8) | E.OVR.DUP.2 | - | K2 | 필드 | OK | 미인쇄 열에 같은 행 칸 복사 |
| UC-2 (2303314855 투여량 7, 코드2개_급여액 총액 5, 비급표현-… | E.OVR.DUP.2 | - | K2 | 필드 | OK | - |
| UC-3 (첫 구현 악화 125칸: 단가 105·투여량 10·횟수 9·일수 9) | AUX.POST.ALTER | E.MIS.FIELD.2 | K3 | 필드 | OK | 복사 판정 오류로 정상 단가를 지움 |
| UC-4 (3022033115105207-1 실데이터 재생) | - | - | - | - | NA | 검증 인프라(저장 입력 부족) |
| UC-5 (영수증 표 미인쇄 열) | - | - | - | - | NA | 원인 미확인 미적용 기록 |
| UC-6 (종료일자 날짜 복사) | E.OVR.DUP.2 | - | K2 | 필드 | OK | 종료일자 복사; 고객 확인 대기 |
| CLS-1 (E.OVR.DUP.2 종료일자 220칸) | E.OVR.DUP.2 | - | K2 | 필드 | OK | 문서 ID 그대로 |
| CLS-2 (E.OVR.DUP.2 금액 복사 67칸: 급여 34·단가 18·비급… | E.OVR.DUP.2 | - | K2 | 필드 | OK | 문서 ID 그대로 |
| CLS-3 (AUX.EVAL 상한액초과금 29칸) | AUX.EVAL | E.CON.SCHEMA.1 | K10 | 필드 | AMBIG | 후보: AUX.EVAL, E.CON.SCHEMA.1; 규칙: 정식 키가 계약에 확정되지 않은 키 표기 불일치의 귀속(확정이면 SCHEMA.1, 미확정이면 AUX.EVAL) |
| CLS-4 (E.MIS.FIELD.2 투여량 19칸, 진료시작일 등 9칸) | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 인쇄된 투여량 놓침 |
| CLS-5 (E.WRG.NORM.3 13칸) | E.WRG.NORM.3 | - | K3 | 값 | AMBIG | 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: 빈칸↔0 교환을 정규화로 볼지 과추출로 볼지 미정(v3 '빈칸을 값으로 채움=과추출'과 NORM.3 충돌) |
| CLS-6 (E.MIS.PART.2 10칸) | E.MIS.PART.2 | - | K3 | 값 | OK | 금액 소수점·자릿수 소실 |
| CLS-7 (UNCLASSIFIED 7칸: 종료일자 4칸·사고발생일자 1·급여 … | - | - | - | - | AMBIG | 후보: E.WRG.CTX.2, E.WRG.PICK.1, E.WRG.ASSIGN.2; 규칙: 정보 부족(행마다 다른 날짜 출력의 원인 미확인), 7칸 이질적 묶음은 칸별 분리 필요 |
| CLS-8 (E.WRG.READ.1 5칸) | E.WRG.READ.1 | - | K3 | 값 | OK | 진료과·병원명 오독 |
| CLS-9 (AUX.POST.VALID 3칸·AUX.POST.PICK 1칸) | AUX.POST.VALID | AUX.POST.PICK | K3 | 값 | OK | 악화 3·1칸 |
| CLS-10 (GEN.1 2, GEN.2 2, PART.1 1, ASSIGN.2… | E.OVR.GEN.1 | E.OVR.GEN.2,E.MIS.PART.1,E.WRG.ASSIGN.2 | K2 | 값 | OK | 7칸 묶음, 상세 부족(문서 ID 유지) |
| CLS-11 (비교 기준 이원화) | AUX.EVAL | - | - | 묶음 | OK | 채점기 버전·비교 기준 이원화 |
| CLS-12 (분류기 오판: E.CON.SCHEMA.1 49칸) | AUX.EVAL | - | - | 필드 | OK | 분류기 오판(채점기 None 표기) |
| EC-P01 | P.MIS.CHAR.2 | - | K3 | 문자 | OK | 예상: 저해상도(발생 조건)로 소수점·음수 소실 |
| EC-P02 | AUX.INPUT | P.WRG.POS.1,P.WRG.ORDER.1 | K4 | 페이지 | OK | 예상: 회전·기울기 방향 처리 실패, 결과 복수 |
| EC-P03 | P.MIS.CHAR.1 | - | K3 | 문자 | OK | 예상: 가림·잘림 일부 누락 |
| EC-P04 | AUX.INPUT | P.MIS.CHAR.2,P.MIS.MARK.1 | K3 | 문자 | OK | 예상: 이진화·리사이즈 소실 |
| EC-P05 | P.WRG.READ.1 | - | K3 | 문자 | OK | 예상: 0/O·1/I/l 혼동 |
| EC-P06 | P.MIS.MARK.2 | P.STR.REL.4 | K8 | 표시 | OK | 예상: 수정 표시 누락; 폐기값 채택은 E.WRG.CTX.5 후속 |
| EC-P07 | P.WRG.ORDER.3 | E.WRG.CTX.1 | K6 | 블록 | OK | 예상: 다단·측면 메모 |
| EC-P08 | P.STR.REL.1 | P.STR.SPLIT.2,E.WRG.ASSIGN.2 | K7 | 셀 | OK | 예상: 병합 셀·줄바꿈 |
| EC-P09 | P.STR.LINK.2 | P.OVR.DUP.1 | K5 | 표 | OK | 예상: 이어진 표·반복 헤더 |
| EC-P10 | P.MIS.MARK.1 | - | K1 | 표시 | OK | 예상: 체크박스·동그라미 소실 |
| EC-P11 | P.STR.DOC.1 | P.OVR.DUP.1 | K5 | 문서 | OK | 예상: 한 사진 두 장·중복 스캔·페이지 누락(AUX.INPUT) |
| EC-P12 | AUX.INPUT | P.MIS.CHAR.1,P.OVR.DUP.1 | K3 | 문자 | OK | 예상: 축소 소실·타일 경계 중복 |
| EC-P13 | AUX.INPUT | - | K1 | 페이지 | OK | 예상: 디코딩·프레임 선택 |
| EC-P14 | P.CON.DONE.1 | - | K10 | 페이지 | OK | 예상: 출력 중단 완료 오표시 |
| EC-E01 | E.WRG.ASSIGN.3 | E.WRG.ATTR.3 | K4 | 필드 | AMBIG | 후보: E.WRG.ASSIGN.3, E.WRG.ATTR.3, E.WRG.CTX.4, E.WRG.PICK.1; 규칙: 같은 역할 필드(환자 성명)에 다른 당사자 값 선택 시 ASSIGN/ATTR/PICK 구분 |
| EC-E02 | E.WRG.ASSIGN.3 | - | K4 | 필드 | AMBIG | 후보: E.WRG.ASSIGN.3(시점 역할), E.WRG.PICK.1; 규칙: 역할별 라벨이 분리된 복수 날짜 중 틀린 날짜 채택이 후보 선택인지 역할 배정인지 |
| EC-E03 | E.WRG.ASSIGN.3 | - | K4 | 필드 | AMBIG | 후보: E.WRG.ASSIGN.3, E.WRG.PICK.1; 규칙: 역할 구분 금액(총액·본인·공단 등) 중 틀린 것 선택, 위와 같음 |
| EC-E04 | E.WRG.ATTR.1 | - | K8 | 필드 | OK | 예상: 부정·의심·과거력을 확정으로 추출 |
| EC-E05 | E.WRG.NORM.3 | - | K3 | 값 | OK | 예상: 빈칸·판독불가·0·대시 구분 소실 |
| EC-E06 | E.MIS.PART.3 | E.WRG.PICK.1 | K3 | 필드 | OK | 예상: 복수 값 중 첫 항목만 |
| EC-E07 | E.STR.SPLIT.1 | P.STR.SPLIT.2 | K5 | 레코드 | OK | 예상: 다른 행 값을 합쳐 한 항목 생성(ASSIGN.2도 후보이나 레코드 합침이 우선) |
| EC-E08 | E.OVR.SCOPE.3 | E.OVR.DUP.3 | K2 | 문서 | OK | 예상: 정정본·취소본 구버전 채택·이중 집계 |
| EC-E09 | E.WRG.NORM.2 | P.MIS.MARK.4 | K3 | 값 | OK | 예상: 단위·괄호 음수·불완전 날짜 |
| EC-E10 | E.WRG.NORM.4 | E.OVR.GEN.1 | K3 | 값 | OK | 예상: 선행 0 소실, 마스킹 부분 추정 |
| EC-E11 | E.WRG.PICK.2 | - | K9 | 필드 | OK | 예상: 상충 근거를 임의 교정 |
| EC-E12 | AUX.SCHEMA | E.OVR.GEN.1 | K2 | 필드 | OK | 예상: 필드 없는 문서에 값 생성 |
| EC-E13 | E.WRG.CTX.3 | - | K7 | 필드 | OK | 예상: 앞 페이지 대상 전파 |
| EC-E14 | GEN.TAG | E.OVR.GEN.1 | K2 | 필드 | OK | 예상: 문서 내 지시 혼입(원인 태그), 결과 유형 연결 |
| EC-E15 | E.CON.EVID.3 | AUX.POST.EVID | K10 | 필드 | OK | 예상: 근거 위치 불일치 |
| EC-E16 | E.CON.DONE.1 | E.CON.DONE.2,E.CON.DONE.3 | K10 | 문서 | OK | 예상: 잘린 JSON·중복 키·일부 누락 |
| PQ-01 | AUX.INPUT | - | K1 | 문서 | OK | 확장자 불일치 이미지 디코딩 실패(422) |
| PQ-02 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7 | 열 | OK | 다층 머리글 우선순위 오적용 |
| PQ-03 | AUX.EVAL | - | K3 | 필드 | OK | 정답지 라벨 오류 |
| PQ-04 | AUX.EVAL | - | K3 | 필드 | OK | schema 0 vs null 정책 결정대기 |
| PQ-05 | AUX.EVAL | E.OVR.GEN.2 | K2 | 필드 | OK | 파생값 허용 정책 미분리 |
| PQ-06 | AUX.EVAL | E.WRG.CTX.1 | K2 | 필드 | OK | 라벨 범위 정책 |
| PQ-07 | AUX.EVAL | E.OVR.GEN.2 | K2 | 필드 | OK | 서술→치료명 라벨 범위 |
| PQ-08 | AUX.EVAL | - | K1 | 필드 | OK | 채점기가 누락 필드를 분모에서 제외 |
| PQ-09 | - | - | - | - | NA | 하락 원인 조사 과제(귀속 미확정) |
| PQ-10 | - | - | - | - | NA | 지표 목표 미달 기록 |
| PQ-11 | E.OVR.GEN.1 | - | K2 | 필드 | OK | 인쇄된 빈칸에 값 생성 |
| PQ-12 | - | - | - | - | NA | 이미지 변형 집계 지표(셀 단위 분류 필요) |
| PQ-13 | AUX.EVAL | - | - | 묶음 | OK | 채점 계약(loose/strict) 차이 |
| PQ-14 | E.CON.EVID.3 | - | K10 | 필드 | OK | source_text가 추출값으로 채워짐 |
| RP-01 | E.CON.EVID.1 | P.STR.REL.4 | K10 | 필드 | OK | 체크표시→Y/N 근거 연결 누락 |
| RP-02 | E.CON.EVID.1 | - | K10 | 필드 | OK | 근거 검증기가 표기 변형(YYYYMMDD vs 한국어)을 못 찾음 |
| RP-03 | P.CON.EVID.1 | - | K10 | 블록 | OK | 줄 좌표 없음 |
| RP-04 | P.MIS.AREA.2 | E.CON.EVID.1 | K1 | 블록 | OK | 합계 인쇄값이 파싱 텍스트에서 빠짐; 발행일은 라벨 없음(P.STR.REL.3 가능) |
| RP-05 | E.OVR.GEN.1 | - | K2 | 필드 | OK | 원본 공란에 값 추출 |
| RP-06 | E.CON.EVID.1 | E.STR.COMPOSE.1 | K10 | 필드 | OK | 기간→시작·종료 근거 규칙 부재 |
| RP-07 | AUX.EVAL | E.CON.EVID.1 | K10 | 필드 | AMBIG | 후보: AUX.EVAL(스키마 중복 정의), E.CON.EVID.1; 규칙: 스키마가 같은 의미로 정의한 별칭 필드의 근거 종류(직접 인쇄 vs 별칭) |
| RP-08 | P.STR.REL.2 | E.CON.EVID.1 | K7 | 열 | OK | 병합 머리글·총계 행 동일값 매칭 모호 |
| RP-09 | E.CON.EVID.1 | - | K10 | 필드 | OK | 근거 검증기 별칭 미사용 |
| RP-10 | - | - | - | - | NA | 재처리 예산 스케줄링 |
| RP-11 | - | - | - | - | NA | 재처리 예산 확대 실험 |
| AR-01 | E.WRG.READ.1 | - | K3 | 값 | NA | 의도적 오독 시험(거절은 정상 보류) |
| AR-02 | - | - | - | - | NA | 재처리 루프 구현 버그(출력 오류 시 AUX.POST.VALID) |
| AR-03 | - | - | - | - | NA | 재처리 루프 구현 버그 |
| AR-04 | - | - | - | - | NA | 재처리 루프 상태 소실(출력 오류 시 AUX.RUN) |
| AR-05 | - | - | - | - | NA | 재처리 이력 미초기화 |
| AR-06 | - | - | - | - | NA | 운영: 취소 처리 |
| AR-07 | E.WRG.READ.1 | - | K3 | 값 | OK | 오독 시험, 후보도 오답 |
| TE-01 | P.WRG.READ.1 | E.CON.EVID.1 | K3 | 문자 | OK | 라벨 오독·기울기로 공란 확정 불가 |
| TE-02 | P.STR.REL.1 | E.CON.EVID.1 | K7 | 셀 | OK | 머리글 오독·병합 의미 연결 불명 |
| TE-03 | - | - | - | - | NA | 운영: 처리 시간 |
| NC-01 | P.WRG.POS.1 | E.WRG.ASSIGN.1 | K4 | 필드 | OK | 회전으로 가변 인쇄가 항목명보다 한 행 위로 밀림 |
| NC-02 | AUX.POST.ALTER | - | K3 | 값 | OK | 잘못된 교정 채택 |
| NC-03 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 칸 공백만으로 미기재 확정 금지(교정 가드) |
| NC-04 | E.WRG.NORM.3 | E.OVR.GEN.1 | K3 | 값 | AMBIG | 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: 빈칸→0·비공란 값 혼재 시 0은 정규화, 비0은 과추출로 나누는 규칙 부재 |
| NC-05 | E.WRG.READ.1 | AUX.POST.ALTER | K3 | 값 | OK | OCR 문자열 앵커링으로 오독 반복 |
| NC-06 | E.OVR.GEN.1 | - | K2 | 필드 | OK | 정답 빈칸에 비0 금액 유지 |
| NC-07 | E.WRG.NORM.3 | E.OVR.GEN.1 | K3 | 값 | AMBIG | 후보: E.WRG.NORM.3, E.OVR.GEN.1; 규칙: null→0 (위와 같음) |
| NC-08 | - | - | - | 필드 | AMBIG | 후보: E.WRG.READ.1, E.WRG.ASSIGN.1, E.MIS.FIELD.2; 규칙: 정보 부족(오답 유형 미기재) |
| NC-09 | E.CON.SCHEMA.2 | - | K10 | 필드 | OK | 표 vs 스칼라 구조 불일치 |
| NC-10 | - | - | - | - | NA | 평가 환경(구버전 import) |
| NC-11 | - | - | - | - | NA | 예산 확대 실험 |
| NC-12 | - | - | - | - | NA | 실험 프로세스 오염 |
| CR-01 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 룰1 필수 키 채움 비율(탐지 룰) |
| CR-02 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 필수 항목 행 누락 |
| CR-03 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | parse 표에는 값이 있는데 빈칸·0 |
| CR-04 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | - |
| CR-05 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 재검증 후에도 빔 |
| CR-06 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 0 표기를 빈값으로 취급하는 보충 조건 |
| CR-07 | P.STR.SPLIT.1 | - | K5 | 셀 | OK | 한 칸에 숫자 둘 이상 |
| CR-08 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 보충 임계(30배)로 일부 미보충 |
| CR-09 | - | - | - | - | NA | 운영: API 키 미발급 |
| WO-01 | P.WRG.READ.1 | E.WRG.READ.2 | K3 | 문자 | OK | 오독을 Extract가 그대로 선택 |
| WO-02 | P.MIS.CHAR.2 | - | K3 | 문자 | OK | 123,500→123,50 |
| WO-03 | P.WRG.READ.1 | P.WRG.READ.4 | K3 | 문자 | OK | 혼동 문자 + 띄어쓰기·분리·합침 |
| WO-04 | P.WRG.POS.2 | P.STR.SPLIT.1,P.STR.SPLIT.2 | K4 | 문자 | OK | bbox 위치 오류 |
| WO-05 | P.WRG.ORDER.1 | E.WRG.CTX.4 | K6 | 행 | OK | 행 순서·연결 틀림 |
| WO-06 | P.STR.SPLIT.1 | P.STR.REL.1,P.STR.LINK.1,P.STR.LINK.2,P.MIS.AREA.2 | K5 | 표 | OK | 표 이해 오류 우산 행(복수 원인) |
| WO-07 | - | - | - | - | NA | 발생 조건 목록(기록 축) |
| WO-08 | P.MIS.AREA.1 | P.OVR.DUP.1,P.STR.DOC.1 | K1 | 페이지 | OK | 페이지 누락·중복·혼합 우산 행 |
| WO-09 | E.WRG.CTX.1 | E.MIS.FIELD.2 | K7 | 필드 | OK | Key 표현 차이(진단명↔상병명) |
| WO-10 | E.WRG.ASSIGN.1 | - | K4 | 필드 | OK | 진단명에 수술명 |
| WO-11 | E.WRG.ASSIGN.2 | E.WRG.CTX.3 | K4 | 필드 | OK | 바로 아래·옆 열·다른 표 값 |
| WO-12 | E.WRG.ASSIGN.3 | E.WRG.CTX.4 | K4 | 필드 | AMBIG | 후보: E.WRG.ASSIGN.3, E.WRG.CTX.4, E.WRG.PICK.1, E.WRG.ATTR.3; 규칙: 동일 라벨 복수 당사자 중 선택(EC-E01과 같음) |
| WO-13 | E.MIS.PART.3 | E.STR.ORDER.1,E.STR.ARRAY.1 | K3 | 필드 | OK | 다중값 우산 행 |
| WO-14 | E.WRG.ASSIGN.1 | E.WRG.ASSIGN.3 | K4 | 필드 | OK | 유사 필드 혼동(주상병↔부상병은 ASSIGN.3) |
| WO-15 | E.CON.RANGE.2 | E.WRG.NORM.2,E.WRG.NORM.4 | K10 | 값 | OK | 형식 이상 우산 행 |
| WO-16 | E.OVR.GEN.1 | - | K2 | 값 | OK | 원문에 없는 값 생성 |
| WO-17 | E.WRG.ASSIGN.1 | E.CON.RANGE.2 | K4 | 필드 | OK | AA254가 일자로 매핑 |
| TD-01 | E.OVR.DUP.2 | AUX.POST.ALTER | K2 | 필드 | OK | parse 보충이 행 밀림 값을 채움 |
| TD-02 | E.WRG.ASSIGN.2 | - | K4 | 필드 | OK | 서식 판별 불가로 통과(미탐) |
| TD-03 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 계 행 비급여 누락 |
| TD-04 | E.CON.RANGE.2 | - | K10 | 값 | OK | 콤마 표기 입력 |
| TD-05 | E.MIS.ABST.2 | - | K8 | 필드 | OK | 원문 근거 있는 값을 근거 거리 기준으로 거절 |
| TD-06 | E.MIS.ABST.2 | - | K8 | 필드 | OK | 분기 9 불채택 |
| TD-07 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 필수 항목 외 행 누락 |
| TD-08 | P.WRG.POS.1 | E.WRG.ASSIGN.2 | K4 | 필드 | OK | 일부 칸만 옆 열 밀림 |
| TD-09 | AUX.REF | - | K10 | 필드 | OK | KCD 세분 코드가 기준표에 없음(합의 필요) |
| TD-10 | - | - | - | - | NA | 검증 오탐(추출은 맞음) |
| TD-11 | P.WRG.POS.1 | - | K4 | 필드 | OK | 병명·코드 한 줄 밀림 |
| TD-12 | AUX.POST.NORM | AUX.EVAL | K3 | 값 | OK | 항목명 표기(·, _) 동치 |
| TD-13 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 표준 목록 누락·[UNK] 처리로 행 누락 |
| TD-14 | E.MIS.TARGET.1 | - | K1 | 표 | OK | 간헐적 빈 항목내역(재현성 간헐) |
| TD-15 | - | - | - | - | NA | 검증 룰 부재(고객 확인) |
| TD-16 | E.WRG.READ.1 | - | K3 | 값 | OK | 형식 정상 날짜 오류, 원본 대조 부재(미탐) |
| TD-17 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 인쇄 여부 확인 필요(정상일 수 있음) |
| TD-18 | - | - | - | - | NA | 보고서 오기 |
| TD-19 | - | - | - | - | NA | 검수 일정 |
| TD-20 | - | - | - | - | NA | 운영: 처리 시간 |
| TD-21 | E.CON.SCHEMA.1 | AUX.EVAL | K10 | 필드 | AMBIG | 후보: E.CON.SCHEMA.1, AUX.EVAL; 규칙: 정식 키 미확정 시 키 표기 차이(CLS-3과 같음) |
| TD-22 | AUX.POST.NORM | AUX.EVAL | K3 | 값 | OK | 표준명 vs 서식 원문 정책 |
| FB-01 | AUX.SCHEMA | - | K3 | 문서 | OK | 문서 종류 오분류 |
| FB-02 | AUX.POST.ALTER | AUX.REF | K2 | 값 | OK | 기준 DB 추정 채움(제거됨) |
| FB-03 | - | - | - | - | NA | 기능 제약(다중 페이지 동기 요청) |
| FB-04 | E.WRG.ASSIGN.2 | - | K4 | 행 | OK | 예시: 횟수·일수 칸 오배정 |
| FB-05 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 병원명 비어 필수 칸 검사 |
| WB-01 | P.WRG.READ.1 | - | K3 | 문자 | OK | I→1 |
| WB-02 | P.WRG.TYPE.2 | E.OVR.SCOPE.2 | K2 | 값 | OK | 서식 표지 (주상병) 포함 |
| WB-03 | P.WRG.READ.1 | - | K3 | 문자 | OK | - |
| WB-04 | E.MIS.FIELD.2 | P.MIS.MARK.1 | K1 | 필드 | OK | 체크박스 짝 값 빈칸 |
| WB-05 | E.WRG.READ.1 | - | K3 | 값 | OK | 형식 정상 날짜 오류(미탐) |
| WB-06 | P.WRG.READ.1 | - | K3 | 문자 | OK | B→8 |
| WB-07 | P.WRG.READ.1 | - | K3 | 문자 | OK | 1↔I, 증→중 |
| WB-08 | P.MIS.AREA.2 | - | K1 | 블록 | OK | 이미지 잘림 |
| WB-09 | E.WRG.ASSIGN.1 | - | K4 | 필드 | OK | DRG 칸에 사업자번호 |
| WB-10 | E.OVR.GEN.1 | AUX.EVAL | K2 | 값 | AMBIG | 후보: E.OVR.GEN.1, E.CON.RANGE.1, AUX.EVAL; 규칙: AO 자리표시값(열추출)을 오류로 볼지 정책상 정답으로 볼지 미정(BM-1에서 정답 유지로 결정) |
| WB-11 | E.OVR.DUP.2 | - | K2 | 필드 | OK | EDI명칭 복사 |
| WB-12 | E.WRG.ASSIGN.1 | - | K4 | 필드 | OK | 병실 칸에 진료과 |
| WB-13 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 3행 이상 동일 복사 |
| WB-14 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 합계 비급여 0(TD-03과 같음) |
| WB-15 | P.STR.SPLIT.2 | - | K5 | 셀 | OK | 갈라진 코드 합침 |
| WB-16 | P.WRG.READ.1 | - | K3 | 문자 | OK | 진칠료·식데 |
| WB-17 | P.WRG.POS.1 | E.WRG.ASSIGN.2 | K4 | 열 | OK | 금액 열 뒤바뀜 |
| WB-18 | E.WRG.ASSIGN.1 | - | K4 | 필드 | OK | 급여 칸에 비급여 금액 |
| WB-19 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K4 | 열 | OK | 비급여↔선택진료료외 오배치 |
| WB-20 | E.STR.SPLIT.1 | - | K5 | 필드 | OK | 한 칸에 복수 병명 합쳐짐 |
| WB-21 | E.OVR.GEN.2 | AUX.POST.ALTER | K2 | 필드 | OK | 사고일자 재계산, 계산값 허용 정책 확인 필요 |
| WB-22 | E.WRG.NORM.2 | - | K3 | 값 | OK | 날짜 표기 변환 |
| WB-23 | P.WRG.READ.1 | - | K3 | 문자 | OK | 코드 첫 글자 |
| WB-24 | E.STR.ARRAY.1 | - | K6 | 레코드 | OK | 코드–병명 짝 엇갈림 |
| WB-25 | E.CON.RANGE.3 | E.STR.ARRAY.1,E.WRG.ASSIGN.2 | K10 | 표 | OK | 합계·표 모양 검출 룰 |
| WB-26 | E.CON.RANGE.3 | AUX.REF | K10 | 필드 | OK | 코드–이름 불일치(마스터) |
| WB-27 | E.CON.RANGE.3 | - | K10 | 필드 | OK | 성별·생년월일↔주민번호 모순 |
| WB-28 | E.MIS.FIELD.2 | E.WRG.ASSIGN.2 | K1 | 필드 | OK | 코드 비어있음·다른 행 값 가져옴 |
| WB-29 | - | - | - | - | NA | 검증 룰 부재 |
| WB-30 | - | - | - | - | NA | 운영: 시도 예산 |
| WB-31 | - | - | - | - | NA | 남은 과제 기록 |
| WB-32 | - | - | - | - | NA | 운영: 재판독 루프 |
| WB-33 | - | - | - | - | NA | 지표 격차 기록 |
| RM-1 코드2개_급여액_3022033115393304-1 | E.MIS.FIELD.2 | E.WRG.ASSIGN.2 | K4 | 열 | OK | rowmajor가 투여량 비워 열 전체 연쇄 밀림 |
| RM-2 열 뒤바뀜(공단→본인) | E.WRG.ASSIGN.2 | P.STR.REL.2 | K4 | 열 | OK | 열 뒤바뀜(묶음 제목 겹침) |
| RM-3 투여량·횟수·일수 순서 | E.WRG.ASSIGN.2 | - | K4 | 열 | OK | 인쇄 열 순서 vs 공통 순서 |
| RM-4 전액본인부담↔비급여·회전 스캔 | P.MIS.UNIT.2 | E.WRG.ASSIGN.2 | K1 | 셀 | OK | 회전 스캔 머리글 위치 못 읽음 |
| RM-5 원내코드 후퇴 | AUX.POST.ALTER | E.MIS.FIELD.2 | K1 | 열 | OK | 못 읽은 열을 없는 열로 처리 |
| RM-6 SA2020010684193 | E.WRG.ASSIGN.2 | - | K4 | 열 | OK | 산식 불일치 열 밀림 |
| RM-7 선택진료료외만_금액표기 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 원인 미확정(3칸 빔) |
| RM-8 소계포함 영수증 | AUX.SCHEMA | - | K3 | 열 | OK | 양식 스펙에 없는 소계 열 |
| RM-9 영수증 열 뒤바뀜 | AUX.SCHEMA | E.WRG.ASSIGN.2 | K4 | 열 | OK | 통합 8열 스키마로 열 뒤바뀜 |
| RM-10 양식 판별 실패 1건(OCR이 '이외' 놓침) | P.MIS.CHAR.1 | AUX.SCHEMA | K3 | 문자 | OK | '이외' 놓쳐 양식 판별 실패 |
| RM-11 asis 초과·누락 행 | E.MIS.FIELD.1 | E.OVR.GEN.2 | K1 | 행 | OK | 행 누락 114·초과 31 |
| EX-1 회전 문서 a0·a2·a3 | AUX.INPUT | P.WRG.POS.1 | K4 | 페이지 | OK | 회전 문서 방향 처리 |
| EX-2 a3 6행 중 3행 누락 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 방향 문제 아님, 원인 미확정 |
| EX-3 image_17.tif | AUX.INPUT | P.MIS.AREA.1 | K1 | 페이지 | OK | 누운 쪽 방향 정규화 놓침 |
| EX-4 기간 한 칸 '일자' 열 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 한 칸 '일자'를 종료일에 복사 |
| EX-5 붙은 머리글 '본인부담금공단부담금' | P.STR.SPLIT.1 | AUX.POST.ALTER,E.MIS.FIELD.2 | K5 | 셀 | OK | 붙은 머리글로 열 통째 빔 |
| EX-6 수가코드·청구코드 서식 | AUX.POST.ALTER | E.MIS.FIELD.2 | K1 | 열 | OK | 못 읽은 열을 없는 열로 처리 |
| EX-7 게이트 빈틈 | E.MIS.TARGET.1 | - | K1 | 표 | OK | 금액 통째 빈 응답을 게이트가 통과(미탐) |
| EX-8 asis 2단 머리글 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K4 | 열 | OK | 2단 머리글 공단→본인 |
| EX-9 asis 공단→본인 순서 서식 | E.WRG.ASSIGN.2 | - | K4 | 열 | OK | 열 순서 서식에서 뒤바뀜 |
| EX-10 asis 명칭/코드 칸 혼동 | E.WRG.ASSIGN.1 | E.OVR.DUP.2 | K4 | 필드 | OK | 명칭을 코드 칸에 넣고 항목에 복사 |
| EX-11 asis 긴 표 중단 | E.CON.DONE.3 | E.MIS.FIELD.1 | K10 | 표 | OK | 긴 표 중간 중단(부분 처리) |
| EX-12 게이트 오발동 | - | - | - | - | NA | 게이트 오발동(탐지 오탐) |
| EX-13 일자 차이 판정(실행일자 정책) | AUX.EVAL | - | K3 | 값 | OK | 실행일자 정책 결정대기 |
