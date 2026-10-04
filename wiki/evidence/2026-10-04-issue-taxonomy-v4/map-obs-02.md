---
title: 대응 검증 map-obs-02
---

# 대응 검증 결과 (obs-chunk-02 + edge_cases 메커니즘)

대상: 사례 298행 + edge_cases 메커니즘 26행 = 324행. 중복 사례ID는 `#n`(chunk 내 등장 순서)으로 구분.

## 판정별 건수

| 판정 | 건수 |
|---|---|
| OK | 223 |
| AMBIG | 13 |
| NEW | 0 |
| NA | 88 |
| 합계 | 324 |

## AMBIG 전체 목록

| 사례ID | 내용 | 제안 |
|---|---|---|
| AR-11 | 빈 병실 칸에 제목 (외래)를 보고 Docraft가 외래를 채움(2303315286은 실제 인쇄돼 룰로 못 가름) | 빈칸에 원문의 다른 위치 값(제목)을 채움. GEN.1(빈칸 채움=과추출) vs ASSIGN.1(원문 값 오배정) vs DUP.2. 부족한 규칙: 채운 값의 원문 출처 유무로 가르는 기준 |
| REQ-2 | 사업자등록번호 칸이 비었는데 전화번호를 넣음(룰이 막지 못함) | 빈 칸에 다른 종류 값(전화번호) 채움. ASSIGN.1 vs GEN.1. AR-11과 같은 규칙 부족 |
| RR-2#1 | 0720 row12 페니라민정 단가15×횟수3인데 총액0·급여18·본인부담0 행 내부 모순, 원인 셀 특정 불가 | 행 내부 산식 모순, 원인 셀 특정 불가. 후보 RANGE.3(탐지)/READ.1(오독)/원문 인쇄 불일치(오류 아님). 부족한 규칙: 원문 자체가 제약 위반일 때의 분류와 귀속 미확정 기본 노드 |
| RC-3#1 | 페니라민정 15×3.0×3=135인데 총액 0으로 인쇄된 묶음 산정 행이 UNITMUL fail | 원문에 총액 0으로 인쇄된 묶음 행이 단가곱 검증 fail. 원문 인쇄 불일치의 분류 기준 부재(RR-2와 동일) |
| EN-3 | 병원 라벨이 원장 명칭보다 길면(재진진찰료-의원,보건의료원 내 의과) 형제 AA253이 AA254보다 앞서 역유추 후보 오배치 | 참조 후보 오선택. AUX.REF(잘못된 항목 매칭) vs AUX.POST.PICK(복수 후보 오선택). 부족한 규칙: 참조 조회 후보 선택의 AUX 귀속 |
| FR-M7 | master_evidence가 원본 코드를 증거에서 지우고 역유추 1단계면 조용히 다른 코드로 대체 | 원본 코드를 지우고 역유추 코드로 대체. AUX.REF vs AUX.POST.ALTER vs AUX.POST.EVID. 부족한 규칙: 참조 조회 기반 교정의 AUX 귀속 |
| AL-4 | 투여량 칸 라벨 null→모델이 1·2·3 또는 금액(12380·1837)을 채움(photo_1640582155063 +23, | 빈 투여량 칸에 1·2·3 또는 금액(다른 열 값) 채움. GEN.1 vs ASSIGN.1. 같은 규칙 부족(AR-11) |
| TR-6 | 머리글 행이 표 블록 밖이거나 TIF 품질 불량으로 표가 글자 덩어리로만 잡힘(2303314684, 11202109061153 | 머리글 미검출로 표가 글자 덩어리. 후보 TYPE.2(표 오분류)/UNIT.2(머리글 누락)/AREA.2. 부족한 규칙: 표 전체 구조 복원 실패의 단위 결정 |
| RP-3#2 | 치료명 8건·검사명 4건·병명 3건 오답(의미 추출) | 서술형 필드의 의미 추출 오답(치료명·검사명·병명). 후보 COMPOSE.1(경계)/ATTR/SCOPE.2. 부족한 규칙: 자유 서술 값 단위 분리의 경계 오류 |
| MAT-1 | 치료재료 코드 45개 정확 충돌 → 수가(EDI:의치과_급여)와 코드 겹침, 수가가 우선되어 치료재료 명칭 아닌 수가 명칭에  | 코드 충돌에서 수가 우선 선택. AUX.REF vs AUX.POST.PICK(EN-3과 동일 규칙 부족) |
| SR-4#2 | 3022033115105207 방문별 합계 행 날짜 빈칸 기대 → 모델이 날짜 기재 | 집계 행 날짜 빈칸에 날짜 기재. GEN.1 vs DUP.2 vs ASSIGN.1. 같은 규칙 부족(AR-11) |
| PO-4 | 3022033115105207 합계 행 종료일자 4칸 모델이 집계 행에 날짜 기재 | 집계 행에 날짜 기재(SR-4와 동일 사건 유형) |
| edge:printed_inconsistency | edge_cases.yaml 메커니즘 | 태그는 적절하나 원문 자체가 제약 위반인 경우 RANGE.3이 오류인지 탐지 사실인지 규칙 부재(RR-2, RC-3과 동일) |

## NEW 전체 목록

없음. 신설이 필요한 칸은 아래 제안으로 AMBIG·비고에 흡수했다(해당 판정 NEW 0건).

## 제안 요약 (규칙·노드 보강)

1. 빈칸에 원문의 다른 위치 값을 채운 경우(AR-11, REQ-2, AL-4, SR-4#2, PO-4): 분류 경계 규칙에 `채운 값이 원문 다른 칸에 인쇄돼 있으면 같은 값 복사=E.OVR.DUP.2, 다른 의미 값=E.WRG.ASSIGN.1, 원문 어디에도 없음=E.OVR.GEN.1` 추가.
2. 원문 자체가 산식·제약을 어기게 인쇄된 경우(RR-2#1, RC-3#1, edge:printed_inconsistency): RANGE.3은 출력 위반만 센다는 문장과 귀속 미확정 기본 노드 필요.
3. 참조(마스터) 조회 후보 오선택(EN-3, FR-M7, MAT-1): AUX.REF vs AUX.POST.PICK/ALTER 귀속 경계 규칙 필요(제안: 조회 로직 결함은 AUX.REF, 후보 선택 정책은 AUX.POST.PICK).
4. 머리글을 못 잡아 표 전체 구조가 무너진 경우(TR-6): P.MIS.UNIT.2/P.WRG.TYPE.2/P.MIS.AREA.2 중 단위 결정 기준(제안: 머리글만 사라졌으면 UNIT.2, 표가 본문으로 보이면 TYPE.2).
5. 서술형 값 단위 분리(RP-3#2): E.STR.COMPOSE.1을 `한 서술에서 값 단위를 나눌 때의 경계 오류`로 일반화 검토.
6. 탐지·판정 계층 사례가 NA에 많이 몰림(검증식 오탐, 판정 롤업·미탐, 증거 과다 부착 등 약 48건): v3 기록 축 `자동 탐지 여부`만으로는 오탐(정상 원문 fail)·판정 상태 오표시를 담지 못함. 별도 `탐지 정밀도` 축(오탐·미탐·판정 상태)을 두거나 NA 범주로 명시 권고.
7. K표 보정: E.STR.ARRAY.1(행·열 개수 불일치)은 K6(순서)가 아니라 길이 대응이라 칸 재배치 필요(RC-4#1). AUX.* 노드에는 K를 `결과 차이 종류`로 적용했다(원인 칸 없음).
8. 실행 시간초과·외부 서비스 미완료(E2E-10, E210-1, RT-5)는 AUX.RUN에 노드가 없어 NA로 둠. 결과 누락이 생기면 AUX.RUN 하위 `처리 중단·시간초과` 추가 검토.
9. edge_cases 태그 수정 권고: cell_displacement(P.STR.REL.3→REL.2), structure_omission(P.OVR.GEN.1 제거·UNIT.1 추가), non_data_rows(P.STR.HIER.2→P.WRG.TYPE.1), semantic_duplicate(E.STR.ARRAY.1 제거), occlusion(P.MIS.AREA.2→P.MIS.CHAR.1), handwriting(P.WRG.TYPE.1 추가), multi_value_cell(E.STR.COMPOSE.1 추가), numeric_format(NORM.4 추가), length_scale(AUX.INPUT 추가).

## 자주 쓴 ID 상위 15 (원인ID+후속ID)

| 순위 | ID | 건수 |
|---|---|---|
| 1 | E.MIS.FIELD.2 | 19 |
| 2 | AUX.EVAL | 18 |
| 3 | AUX.REF | 18 |
| 4 | AUX.POST.ALTER | 18 |
| 5 | E.OVR.GEN.1 | 17 |
| 6 | P.WRG.READ.1 | 16 |
| 7 | E.WRG.READ.1 | 14 |
| 8 | E.OVR.DUP.2 | 14 |
| 9 | E.WRG.ASSIGN.2 | 13 |
| 10 | AUX.INPUT | 12 |
| 11 | P.STR.SPLIT.1 | 11 |
| 12 | E.OVR.GEN.2 | 10 |
| 13 | E.WRG.ASSIGN.1 | 8 |
| 14 | E.MIS.FIELD.1 | 7 |
| 15 | AUX.SCHEMA | 7 |

## 전체 표

| 사례ID | 원인ID | 후속ID | K | 단위 | 판정 | 비고 |
|---|---|---|---|---|---|---|
| AR-10 | - | - | - | - | NA | 검증 오탐(빈 열 검사가 머리글 한 칸을 낱말 둘로 오검출). 탐지 정밀도 계층 |
| AR-11 | E.OVR.GEN.1 | E.WRG.ASSIGN.1 | K2 | 필드 | AMBIG | 빈칸에 원문의 다른 위치 값(제목)을 채움. GEN.1(빈칸 채움=과추출) vs ASSIGN.1(원문 값 오배정) vs DUP.2. 부족한 규칙: 채운 값의 원문 출처 유무로 가르는 기준 |
| AR-12 | P.WRG.READ.1 | - | K3 | 문자·토큰 | OK | 발생조건 저해상도·팩스(AUX.INPUT). 두 결과가 같게 틀리면 미탐(탐지 축) |
| AR-13 | P.MIS.UNIT.2 | E.MIS.FIELD.2 | K1 | 열 | OK | 머리글이 열을 못 찾음. REL.2 후보이나 라벨 인식 실패라 UNIT.2 |
| AR-14 | AUX.EVAL | - | - | 필드 | OK | 정답지 오기(날짜·급여구분) |
| E2E-1 | E.MIS.FIELD.1 | - | K1 | 레코드(행) | OK | AO 행 누락을 Docraft가 보충 |
| E2E-2 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 금액 열 밀림, 오류 패턴=열 일괄 |
| E2E-3 | E.OVR.GEN.1 | E.WRG.READ.1 | K2 | 레코드(행) | OK | 인쇄 안 된 행 추가+숫자 오독(복합). 복합 사례 |
| E2E-4 | AUX.EVAL | - | - | 값 | OK | 정답지 수정으로 해결(실시일 칸에 입원기간 인쇄). 흐린 사진 행 짝 어긋남은 발생조건 |
| E2E-5 | AUX.EVAL | - | - | 값 | OK | 문서 문구상 정답지가 빈 행에 금액을 채운 것으로 읽음. 확인 필요: AO가 채운 것이면 GEN.1 |
| E2E-6 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 병실 칸에 진료과 |
| E2E-7 | P.MIS.UNIT.1 | E.MIS.FIELD.2 | K1 | 열 | OK | 인쇄 열 통째 누락 |
| E2E-8 | E.OVR.DUP.2 | P.WRG.READ.1 | K2 | 필드 | OK | 항목에 EDI명칭 복제+저해상도 오독 다수(복합) |
| E2E-9 | - | - | - | - | NA | 유형 미특정 잔여 오류 집계 |
| E2E-10 | - | - | - | 문서 | NA | AO 미완료 3건 평가 제외(운영·외부 서비스). 실행 시간초과 노드가 AUX.RUN에 없음 |
| E2E-11 | E.OVR.GEN.2 | - | K2 | 값 | OK | 인쇄 안 된 급여구분을 추론해 채움, 정책 결정대기. 정답지 5칸 수정은 AUX.EVAL |
| E2E-12 | - | - | - | - | NA | 인프라(서버 재부팅 직후 500) |
| REQ-1 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 칸 없는 서식에서 환자부담총액을 복사. 필수 제외 권고는 정책 |
| REQ-2 | E.WRG.ASSIGN.1 | E.OVR.GEN.1 | K4 | 필드 | AMBIG | 빈 칸에 다른 종류 값(전화번호) 채움. ASSIGN.1 vs GEN.1. AR-11과 같은 규칙 부족 |
| REQ-3 | E.MIS.TARGET.1 | - | K1 | 문서 | OK | AO 출력 통째 빈 값(문서 단위 전체 누락). 문서 단위 노드 부재로 TARGET.1에 근사 |
| REQ-4 | AUX.SCHEMA | E.CON.SCHEMA.1 | K10 | 필드 | OK | 필드명 정의 불일치(설정 계층) |
| REQ-5 | - | - | - | - | NA | 필수 키 검사 오탐(한방 서식 예외 정책) |
| REQ-6 | E.OVR.GEN.1 | - | K2 | 값 | OK | 인쇄 안 된 CT진단료를 0으로 |
| REQ-7 | - | - | - | - | NA | 원문에 없는 값이라 오류 아님(필수 목록 정책) |
| RP-1#1 | P.CON.EVID.1 | E.CON.EVID.1 | K10 | 필드 | OK | OCR 좌표 없어 근거 연결 실패. 파싱 텍스트에 값 누락 동반(P.MIS.CHAR.1 후보) |
| RP-2#1 | E.OVR.GEN.1 | - | K2 | 필드 | OK | 공란에 값 |
| RP-3#1 | E.CON.EVID.1 | E.STR.COMPOSE.1 | K10 | 필드 | OK | 기간→시작·종료 연결의 근거 규칙 부재. v4 COMPOSE.1 적용 |
| RP-4#1 | E.OVR.GEN.2 | - | K2 | 필드 | OK | 파생·별칭 값과 직접 인쇄 근거 구분 불가. 평가 계약(계산값 허용) 필요 |
| RP-5 | E.CON.EVID.3 | P.STR.REL.2 | K10 | 값 | OK | 같은 값이 두 곳에 겹쳐 근거 위치 모호 |
| RP-6 | E.CON.EVID.1 | - | K10 | 필드 | OK | 근거 앵커 라벨 별칭 규칙 누락 |
| CP-1 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 명칭을 항목에 복제 |
| CP-2 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 인쇄된 섹션명 못 읽음(재판독 미착수) |
| CP-3 | AUX.REF | E.WRG.READ.2 | K3 | 값 | OK | 역조회 입력을 빈 항목 칸으로 써 소실(조회 실패). v4 AUX.REF |
| KCD-1 | E.STR.SPLIT.1 | E.MIS.FIELD.2 | K5 | 레코드(행) | OK | 병명 합침+하나 누락. 조용히 통과=탐지 미표시 축 |
| KCD-2 | E.STR.SPLIT.1 | - | K5 | 레코드(행) | OK | 합침을 못 잡는 탐지 한계(후속 결과는 동일 유형) |
| RR-1#1 | E.WRG.READ.1 | - | K3 | 값 | OK | 코드 자릿수 오독(I678B→I6788) |
| RR-2#1 | E.CON.RANGE.3 | - | K10 | 레코드(행) | AMBIG | 행 내부 산식 모순, 원인 셀 특정 불가. 후보 RANGE.3(탐지)/READ.1(오독)/원문 인쇄 불일치(오류 아님). 부족한 규칙: 원문 자체가 제약 위반일 때의 분류와 귀속 미확정 기본 노드 |
| RR-3#1 | E.OVR.DUP.2 | - | K2 | 열 | OK | 열 복제 |
| RR-4#1 | E.WRG.READ.1 | - | K3 | 값 | OK | 40000→0(합계 행) |
| RR-5#1 | - | - | - | - | NA | 검증 허용오차(원 단위 절사 관행) |
| TERM-1 | - | - | - | - | NA | 필수 키 검사 정책(원문에 없는 값) |
| TERM-2 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 종료일에 시작일 복사, 하네스 미탐 |
| SUM-1 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 요약 행 열 왼쪽 밀림(G2-b) |
| SUM-2 | E.WRG.READ.2 | - | K3 | 값 | OK | 조정 행 값 불일치. 생성 경로(오독/계산 채움) 미확정, 귀속 미확정 유지 |
| SUM-3 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 계 행 칸 누락 |
| SUM-4 | E.WRG.NORM.4 | - | K3 | 값 | OK | 소수를 정수로 버림. PART.2 후보이나 정규화 규칙 결과라 NORM.4(원문 보존 정책) |
| SUM-5 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 급여를 총액으로 복사 |
| SUM-6 | E.WRG.NORM.3 | - | K3 | 값 | OK | 인쇄 안 된 0 vs 빈 값 혼동 |
| SUM-7 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 전액본인→비급여 |
| SUM-8 | AUX.EVAL | - | - | 값 | OK | 정답지 0 vs 원본 빈칸 |
| SUM-9 | AUX.EVAL | - | - | 레코드(행) | OK | 행 수 차이로 정렬 불일치 |
| RC-1#1 | E.CON.EVID.1 | - | K10 | 필드 | OK | 하단 잘림에서 근거 영역이 모두 잘림. 발생조건 AUX.INPUT region_loss |
| RC-2#1 | - | - | - | - | NA | 스키마·정책 결정(원문에 없는 행을 행/그룹 어디에 둘지) |
| RC-3#1 | E.CON.RANGE.3 | - | K10 | 레코드(행) | AMBIG | 원문에 총액 0으로 인쇄된 묶음 행이 단가곱 검증 fail. 원문 인쇄 불일치의 분류 기준 부재(RR-2와 동일) |
| RC-4#1 | E.STR.ARRAY.1 | - | K6 | 레코드(행) | OK | 행·열 개수 불일치를 정상 판정. ARRAY가 K6 칸이나 실제는 길이 대응(순서 아님): K표 재배치 필요 |
| RC-5#1 | P.STR.LINK.2 | - | K5 | 표·그룹·섹션 | OK | 쪽 걸친 표 병합 후 검증 미구현(기능 부재) |
| RC-6 | E.CON.SCHEMA.1 | - | K10 | 필드 | OK | 추출 키 이름 스키마 대조 |
| Q-2 | - | - | - | - | NA | 검증 오탐(명칭 병기·칸 폭 잘림). 원문이 정상 |
| Q-4 | AUX.REF | - | - | 값 | OK | 병기된 두 코드를 통째 조회(조회 입력 오류). 후속 E.STR.COMPOSE.1 후보 |
| Q-5 | - | - | - | - | NA | 검증식 오탐(합계 행 공란을 0으로) |
| Q-6 | - | - | - | - | NA | 검증 오탐(유사도 계산) |
| Q-7 | - | - | - | - | NA | 검증 증거 과다 부착(탐지 정밀도) |
| Q-8 | - | - | - | - | NA | 검증 규칙 회귀 오탐 |
| Q-9 | AUX.REF | E.WRG.READ.1 | K3 | 값 | OK | 참조 판본 차이가 주 원인, AQ120800은 실제 오독 |
| Q-10 | - | - | - | - | NA | 내부 판정 로직 인자 누락 버그 |
| TD-1 | - | - | - | - | NA | 검증 식 정의 결정(절사) |
| TD-2 | AUX.POST.ALTER | - | K3 | 값 | OK | 교정 적용 조건 결정(맞는 값 훼손 방지) |
| TD-3 | - | - | - | - | NA | 검증 표본 부족(실물 라벨 없음) |
| TD-4 | - | - | - | 열 | NA | 고객 확인 대기 열 의미 매핑(요건). 열 의미 해석 규칙은 E.WRG.CTX.1 후보 |
| TD-5 | - | - | - | - | NA | 검증기 미탐 위험(탐지 정밀도) |
| TD-6 | - | - | - | - | NA | 검증기 미탐 위험(절단 재조회) |
| LV-1#1 | AUX.EVAL | - | - | 문서 | OK | 결과 없는 번들의 채점 |
| PF-1 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 빈 문자열 누락, parse 행에 정답 존재 |
| PF-2 | P.WRG.READ.1 | P.MIS.CHAR.1 | K3 | 문자·토큰 | OK | 쉼표 누락·자모·칸 잘림 |
| PF-3 | P.STR.REL.2 | E.MIS.FIELD.2 | K7 | 열 | OK | 붙은 머리글 한 칸이 가리키는 열 못 정함 |
| PF-4 | P.WRG.READ.2 | - | K3 | 값 | OK | 1.0000→1,000 소수점 |
| PF-5 | P.MIS.CHAR.1 | - | K3 | 값 | OK | 칸 잘림으로 앞 5자만 |
| PF-6 | - | - | - | - | NA | 병합 우선순위 정책 |
| PX-1 | AUX.POST.EVID | - | K3 | 값 | OK | 근거 없는 재판독값 자동 채택 |
| PX-2 | AUX.EVAL | - | - | 묶음 | OK | 분모 누락 |
| PX-3 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7 | 열 | OK | 병합 머리글에서 열 선택 오류. REL.1(병합 범위) 후보 |
| PX-4 | E.WRG.NORM.3 | - | K3 | 값 | OK | null vs 0 표현. AUX.EVAL(표기 정책) 병기 |
| PX-5 | - | - | - | - | NA | 근거 게이트 경고 증가(탐지 지표, 유형 미특정). 발생조건 회전·흐림 |
| PX-6 | E.OVR.GEN.1 | - | K2 | 값 | OK | 인쇄된 빈칸 오탐 집계 |
| S7-1 | AUX.SCHEMA | E.MIS.FIELD.2 | K1 | 열 | OK | 문서 유형 오분류로 열 누락 |
| S7-2 | E.CON.DONE.1 | - | K10 | 문서 | OK | model_output_invalid(직렬화·형식) |
| S7-3 | E.CON.RANGE.1 | - | K10 | 값 | OK | doc_type 표기 코드 vs 한글명 |
| S7-4 | E.OVR.GEN.1 | - | K2 | 값 | OK | 자리표시 출력 |
| S7-5 | E.STR.COMPOSE.2 | - | K5 | 값 | OK | 라벨 접두가 값에 혼입 |
| S7-6 | E.WRG.NORM.3 | - | K3 | 값 | OK | 상호 배타 선택의 미선택=N vs 빈값. selection_marks 연관 |
| S7-7 | E.WRG.ASSIGN.2 | - | K4 | 열 | OK | 신서식 열 오배정 |
| S7-8 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | DRG 칸에 사업자번호 |
| S7-9 | E.WRG.ASSIGN.1 | E.CON.RANGE.2 | K4 | 값 | OK | DRG 값 형식 위반이 탐지 경로(S7-8과 같은 사건) |
| S7-10 | AUX.POST.ALTER | - | K4 | 값 | OK | 열 이동 교정 대상 범위 |
| S7-11 | E.MIS.FIELD.1 | E.OVR.GEN.1,E.MIS.PART.1 | K1 | 레코드(행) | OK | 복합(행 누락·과잉·명칭 잘림 합산) |
| S7-12 | AUX.POST.ALTER | - | K3 | 값 | OK | 교정이 맞는 항목명을 바꿈 |
| S7-13 | AUX.INPUT | AUX.SCHEMA | K3 | 문서 | OK | EXIF 미적용+제목 조각 |
| S7-14 | AUX.INPUT | AUX.SCHEMA | K3 | 문서 | OK | 회전·잘림으로 제목 미인식 |
| S7-15 | - | - | - | - | NA | 검증 규칙 도입 정책 충돌 |
| EN-1 | - | - | - | - | NA | 검증 유사도 오탐(마스터가 더 짧음) |
| EN-2 | E.WRG.READ.1 | - | K3 | 값 | OK | 한 자리 코드 오독, 형제 항목이라 미탐 |
| EN-3 | AUX.REF | AUX.POST.PICK | K3 | 값 | AMBIG | 참조 후보 오선택. AUX.REF(잘못된 항목 매칭) vs AUX.POST.PICK(복수 후보 오선택). 부족한 규칙: 참조 조회 후보 선택의 AUX 귀속 |
| EN-4 | - | - | - | - | NA | 검증 오탐(영문 제품명 대조) |
| EN-5 | - | - | - | - | NA | 참조 속성(deleted) 처리 정책 |
| EN-6 | - | - | - | - | NA | 요건 미구현 기능 |
| EN-7 | - | - | - | - | NA | 요건 미구현 기능(빈 값 보완 제안, 보완값은 GEN.2 위험) |
| EN-8 | AUX.REF | - | - | 값 | OK | 잠재 충돌. 관측 오류 없음 |
| EN-9 | - | - | - | - | NA | 임계값 근거 부족 |
| V7-1 | AUX.REF | - | - | 값 | OK | 마스터에 접미 영문 코드 없음(참조 범위). 검증 오탐 |
| V7-2 | - | - | - | - | NA | 검증 유사도 오탐(원문 정상 인쇄) |
| V7-3 | AUX.REF | - | - | 값 | OK | 단일 코드 열 서식 마스터 조회 0건(조회 범위). 검증 오탐 |
| V7-4 | E.WRG.READ.1 | - | K3 | 값 | OK | B→8, 하네스가 정확히 검출 |
| V7-5 | AUX.REF | - | - | 값 | OK | 참조 판본 차이(2025판 vs 2023 진료일) |
| V7-6 | - | - | - | - | NA | 판정 계층: 규칙 0건을 confirmed(미탐 지표). v3에 판정 상태 노드 없음 |
| V7-7 | - | - | - | - | NA | 규칙과 채택 경로의 열 불일치(내부 판정 로직) |
| V7-8 | - | - | - | - | NA | 검증 커버리지 부재 |
| V7-9 | E.OVR.DUP.2 | E.WRG.READ.1 | K2 | 열 | OK | 열 복제+합계 0 미판독 |
| V7-10 | E.MIS.FIELD.2 | - | K1 | 값 | OK | 인쇄된 0 미판독 |
| CO-1 | E.OVR.DUP.2 | - | K2 | 열 | OK | 열 복제 |
| CO-2 | E.CON.SCHEMA.2 | - | K10 | 필드 | OK | JSON 배열 vs 파이썬 repr 문자열 |
| CO-3 | - | - | - | - | NA | 파일시스템 유니코드 정규화(NFC/NFD) 입력 거부 |
| CO-4 | E.WRG.NORM.2 | - | K3 | 값 | OK | 비패딩 날짜 정규화 실패 |
| CO-5 | E.WRG.NORM.3 | - | K3 | 값 | OK | 문자열 null vs 빈 값 |
| CO-6 | P.CON.EVID.1 | - | K10 | 페이지 | OK | 상위 OCR bbox 미제공 |
| CO-7 | - | - | - | - | NA | 검증 허용오차 정책 결정 |
| FL-1 | E.CON.RANGE.1 | - | K10 | 값 | OK | doc_type 표기 매핑 |
| FL-2 | AUX.SCHEMA | - | K8 | 문서 | OK | 입원/통원 하위유형 근거 부족 시 보류 |
| EQ-1 | - | - | - | - | NA | 분석 가정 정정(검증 완화 근거) |
| EQ-2 | - | - | - | - | NA | 잠정 규칙 고객 협의 |
| AU-1 | - | - | - | - | NA | 운영 설정 |
| AU-2 | - | - | - | - | NA | 운영 인증 버그 |
| AU-3 | - | - | - | - | NA | 준비상태 판정(마스터 미적재 시 조용한 미검증, 탐지 계층) |
| FR-B1 | AUX.INPUT | - | K1 | 문서 | OK | 이미지 짝 못 찾아 0건 처리(빈 결과를 성공으로). v4 AUX.INPUT |
| FR-B2 | - | - | - | - | NA | 판정 상태 오표시(미지 doc_type을 confirmed). 판정 계층 |
| FR-B3 | - | - | - | - | NA | 자가교정 루프 미배선(기능) |
| FR-R1 | - | - | - | - | NA | 검증식 이중 계상 오탐 |
| FR-R2 | - | - | - | - | NA | 검증 순서 규칙 오탐 |
| FR-R3 | - | - | - | - | NA | 판정 롤업 정책 |
| FR-R4 | - | - | - | - | NA | 검증식 공란 처리 오탐 |
| FR-R5 | - | - | - | - | NA | 검증 키 패턴 오매칭 |
| FR-R6 | AUX.REF | - | - | 값 | OK | 약가 코드 마스터 범위 밖. 검증 오탐 |
| FR-R7 | - | - | - | - | NA | 검증 유사도 오탐 |
| FR-R8 | - | - | - | - | NA | 판정 롤업 정책 |
| FR-R9 | - | - | - | - | NA | 검증 증거 과다 부착(탐지 정밀도) |
| FR-A2 | AUX.POST.EVID | - | K3 | 값 | OK | 명칭 재판독을 코드 일치 근거로 채택(오교정 위험, 잠재) |
| FR-A3 | - | - | - | - | NA | 판정 로직 누락 |
| FR-A9 | E.WRG.NORM.3 | - | K3 | 값 | OK | 실제 인쇄된 - 를 빈 값으로 간주 |
| FR-M2 | AUX.REF | - | - | 값 | OK | LIKE 와일드카드로 후보 오염(잘못된 항목 매칭) |
| FR-M4 | - | - | - | - | NA | 검증기 범주값 정규화 부재로 오탐(NORM.1 유형이나 출력 값 오류 아님) |
| FR-M6 | AUX.REF | - | - | 값 | OK | 하이픈 코드 조회 실패. 검증 오탐 |
| FR-M7 | AUX.REF | AUX.POST.ALTER | K3 | 값 | AMBIG | 원본 코드를 지우고 역유추 코드로 대체. AUX.REF vs AUX.POST.ALTER vs AUX.POST.EVID. 부족한 규칙: 참조 조회 기반 교정의 AUX 귀속 |
| FR-O1 | - | - | - | - | NA | 판정 단위(배열 원소) 설계 |
| FR-D4 | E.CON.PRIV.1 | - | K10 | 값 | OK | 감사 로그에 한글 성명 원값. v4 PRIV.1 |
| FR-D1 | - | - | - | - | NA | 감사 로거 호출 버그 |
| RR-1#2 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 세로 행 밀림(약품비가 행위료 행에) |
| RR-2#2 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 세로 행 밀림, 합계 검사로 못 잡음(탐지 한계) |
| RR-3#2 | P.WRG.READ.1 | E.WRG.ASSIGN.2 | K3 | 문자·토큰 | OK | 머리글 오독(이외→미외)으로 열 이동 |
| RR-4#2 | - | - | - | - | NA | 검증 헛경고(row_copy) |
| RR-5#2 | E.MIS.PART.2 | - | K3 | 값 | OK | 부호 손실 |
| RR-6 | E.WRG.NORM.4 | - | K3 | 값 | OK | 항목명 표기 차이. 원문 보존 정책(평가 계약) 필요 |
| RR-7 | AUX.RUN | - | - | 문서 | OK | 입력 JSON이 다른 문서(다른 요청 결과 혼입) |
| RG-1 | AUX.POST.ALTER | - | K4 | 값 | OK | 교정 순서 충돌 |
| RG-2 | - | - | - | - | NA | 룰 도입 여부(오류 없음) |
| RG-3 | E.WRG.READ.1 | - | K3 | 값 | OK | 잘못된 음수(부호) |
| AL-1 | E.OVR.GEN.2 | - | K2 | 값 | OK | 급여 열을 총액-비급여로 계산해 채움 |
| AL-2 | E.WRG.ASSIGN.2 | - | K4 | 레코드(행) | OK | 행 한 칸씩 밀림, 연쇄 패턴 |
| AL-3 | E.MIS.FIELD.1 | - | K1 | 레코드(행) | OK | 인쇄 행 통째 누락 |
| AL-4 | E.OVR.GEN.1 | E.WRG.ASSIGN.1 | K2 | 값 | AMBIG | 빈 투여량 칸에 1·2·3 또는 금액(다른 열 값) 채움. GEN.1 vs ASSIGN.1. 같은 규칙 부족(AR-11) |
| AL-5 | E.WRG.READ.1 | E.MIS.PART.1 | K3 | 문자·토큰 | OK | 문자 오독+병실 괄호 잘림 |
| AL-6 | E.WRG.PICK.1 | E.WRG.NORM.4,E.OVR.GEN.1 | K9 | 값 | OK | 요약 금액 오선택+환자구분 표기 변경+null 값 생성(복합) |
| AL-7 | - | - | - | - | NA | 유형 미특정 오답 증가 |
| AL-8 | AUX.EVAL | - | - | - | OK | 분모 변경 |
| TR-1 | P.STR.SPLIT.1 | - | K5 | 레코드(행) | OK | 기울어진 괘선으로 행 병합. 발생조건 기울기 |
| TR-2 | P.MIS.UNIT.1 | - | K1 | 레코드(행) | OK | 괘선 마스크 밀림으로 표 아래·오른쪽 행·열 미인식(알고리즘 결함) |
| TR-3 | P.STR.SPLIT.1 | - | K5 | 레코드(행) | OK | 흐린 괘선을 병합으로 판단 |
| TR-4 | P.STR.SPLIT.1 | P.WRG.READ.1 | K5 | 열 | OK | 머리글 병합+오탈자 |
| TR-5 | P.WRG.POS.1 | - | K4 | 값 | OK | 한 줄 3값이 셀 경계에 걸침 |
| TR-6 | P.WRG.TYPE.2 | P.MIS.UNIT.2 | K2 | 표·그룹·섹션 | AMBIG | 머리글 미검출로 표가 글자 덩어리. 후보 TYPE.2(표 오분류)/UNIT.2(머리글 누락)/AREA.2. 부족한 규칙: 표 전체 구조 복원 실패의 단위 결정 |
| TR-7 | P.STR.SPLIT.1 | - | K5 | 값 | OK | 한 셀에 두 행 금액 |
| TR-8 | AUX.INPUT | P.STR.SPLIT.1 | K5 | 표·그룹·섹션 | OK | 휜 사진 방향·펴기 전처리 부재 |
| TF-1 | P.WRG.READ.1 | P.WRG.READ.4 | K3 | 문자·토큰 | OK | 오독+공백 삽입 |
| TF-2 | P.WRG.READ.1 | - | K3 | 문자·토큰 | OK | 약품명 오독 |
| TF-3 | P.WRG.READ.1 | P.WRG.READ.4 | K3 | 문자·토큰 | OK | 오독+공백 삽입 |
| TF-4 | P.WRG.READ.1 | - | K3 | 문자·토큰 | OK | 오독 |
| TF-5 | P.WRG.READ.1 | - | K3 | 문자·토큰 | OK | 오독 |
| TF-6 | P.WRG.ORDER.3 | - | K6 | 문자·토큰 | OK | 세로 글자 읽기 방향 |
| TF-7 | AUX.POST.ALTER | - | K3 | 문자·토큰 | OK | 교정이 값 삭제·창작·이동(정의 일치) |
| TF-8 | P.CON.FMT.2 | - | K10 | 표·그룹·섹션 | OK | 병합 정보(spans) 미저장 |
| TF-9 | P.STR.SPLIT.1 | AUX.INPUT | K5 | 레코드(행) | OK | 표 구조 붕괴+표 방향 180도 |
| RP-1#2 | - | - | - | - | NA | 집계(유형 미특정) |
| RP-2#2 | E.OVR.GEN.1 | - | K2 | 값 | OK | 빈 정답에 값 |
| RP-3#2 | E.STR.COMPOSE.1 | - | K5 | 값 | AMBIG | 서술형 필드의 의미 추출 오답(치료명·검사명·병명). 후보 COMPOSE.1(경계)/ATTR/SCOPE.2. 부족한 규칙: 자유 서술 값 단위 분리의 경계 오류 |
| RP-4#2 | AUX.EVAL | - | - | 값 | OK | 채점 느슨 판정(표기 정책) |
| KB-1 | E.STR.SPLIT.1 | E.MIS.FIELD.2 | K5 | 레코드(행) | OK | 병명 합침·다음 행 비움 |
| KB-2 | AUX.POST.ALTER | E.STR.COMPOSE.1 | K5 | 값 | OK | 후처리 분리기가 내부 구분자에서 자름 |
| KB-3 | - | - | - | - | NA | 범위 밖 유지 결정 |
| KB-4 | E.CON.SCHEMA.1 | - | K10 | 필드 | OK | 병명 키 누락 입력의 보존 |
| SR-1#1 | AUX.POST.ALTER | E.OVR.GEN.2 | K2 | 값 | OK | 인쇄 확인 없이 계산값 확정 |
| SR-2#1 | AUX.POST.ALTER | E.OVR.GEN.2 | K2 | 값 | OK | 0·총액 복사(생성) |
| SR-3#1 | E.STR.SPLIT.3 | - | K5 | 레코드(행) | OK | 요약 행 신원 혼동 |
| SR-4#1 | AUX.POST.ALTER | E.OVR.DUP.1 | K2 | 레코드(행) | OK | 이미 있는 요약 행 중복 추가 |
| SR-5#1 | E.WRG.ASSIGN.3 | - | K4 | 값 | OK | 요약 라벨을 분류명으로 |
| SR-6#1 | E.OVR.GEN.2 | - | K2 | 필드 | OK | 계산 급여 합(정책 결정대기) |
| SR-7 | - | - | - | - | NA | 서식 해석 정책 미정 |
| SR-8 | E.MIS.TARGET.2 | - | K1 | 레코드(행) | OK | 라벨 열 가정으로 요약 행 인식 못 함(실측 없음, 잠재) |
| PAY-1 | AUX.POST.VALID | - | K3 | 값 | OK | 식 값을 정답 근거로 오인 |
| PAY-2 | E.WRG.NORM.3 | - | K3 | 값 | OK | 0 vs 공란 |
| TP-1 | P.WRG.STATE.2 | - | K8 | 값 | OK | 미판독을 빈칸으로(0·빈칸 혼동) |
| TP-2 | P.WRG.STATE.2 | - | K8 | 값 | OK | 잠재(미확인) |
| RC-1#2 | AUX.POST.ALTER | - | K4 | 값 | OK | 열 맞바뀜 오판 교정 |
| RC-2#2 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 비급여 서식에서 급여 열 잔존 |
| RC-3#2 | - | - | - | - | NA | 검증 합산 규칙(이중 계상 제외) |
| RC-4#2 | - | - | - | - | NA | 검증 불일치 미해결(값 오류 확인 없음) |
| RC-5#2 | - | - | - | - | NA | 기능 미착수(bbox 열 위치 서식 판별) |
| RF-1 | P.OVR.GEN.1 | - | K2 | 값 | OK | OCR이 하위 칸 합을 계산해 만든 값. Parse 계산값 노드(P.OVR.GEN 하위) 신설 검토 |
| RF-2 | E.OVR.DUP.2 | - | K2 | 열 | OK | 열 복제 |
| RF-3 | E.WRG.ASSIGN.2 | E.WRG.READ.1 | K4 | 값 | OK | 합계 행 40000→0과 다른 키에 40000 |
| RF-4 | - | - | - | - | NA | 검증식 적용 범위 오탐 |
| RF-5 | - | - | - | - | NA | 검증식 정의 결정 |
| RF-6 | - | - | - | - | NA | 근거 없는 규칙 정리 |
| VH-1 | E.CON.SCHEMA.1 | AUX.POST.VALID | K10 | 필드 | OK | Judge가 key 누락, 판정 없음을 확인으로 처리 |
| VH-2 | - | - | - | - | NA | 검증 범위(hint_paths) 결함 |
| ES-1 | AUX.EVAL | - | - | - | OK | 채점 산출물 덮어쓰기 |
| ES-2 | AUX.EVAL | - | - | - | OK | 동결 대상 밖 |
| MAT-1 | AUX.REF | AUX.POST.PICK | K3 | 값 | AMBIG | 코드 충돌에서 수가 우선 선택. AUX.REF vs AUX.POST.PICK(EN-3과 동일 규칙 부족) |
| MAT-2 | AUX.REF | - | - | 값 | OK | 5자 접두 충돌 오분류 위험(잠재) |
| MAT-3 | - | - | - | - | NA | 기능 미구현(폐지 코드) |
| DRG-1 | AUX.REF | - | - | 값 | OK | 원장 미적중(조회 실패) |
| DRG-2 | - | - | - | - | NA | 검증 오탐 가능성(실측 미확인) |
| DRG-3 | AUX.REF | - | - | 값 | OK | 비급여 원내코드 조회 불가 |
| LV-1#2 | - | - | - | - | NA | 뷰어 UI 동작(편집 탭 키 없음) |
| LV-2 | - | - | - | - | NA | 뷰어 표시 버그 |
| LV-3 | AUX.EVAL | - | - | 문서 | OK | Golden 없는 문서 채점·표시 |
| B1 | AUX.INPUT | - | K1 | 문서 | OK | 이미지 짝 매칭 실패로 산출물 0건(FR-B1과 동일) |
| B2 | - | - | - | - | NA | 판정 상태 오표시(FR-B2와 동일) |
| R1 | - | - | - | - | NA | 검증식 이중 계상 오탐 |
| R2 | - | - | - | - | NA | 검증 순서 오탐 |
| R4 | - | - | - | - | NA | 검증식 공란 처리 오탐 |
| R5 | - | - | - | - | NA | 검증 키 패턴 오매칭 |
| R6 | AUX.REF | - | - | 값 | OK | 약가 코드 범위 밖. 검증 오탐 |
| R3 | - | - | - | - | NA | 판정 롤업 정책 |
| R8 | - | - | - | - | NA | 판정 롤업 정책 |
| FDV-59 | - | - | - | - | NA | 검증 증거 과다 부착(탐지 정밀도). 근본 사건은 E.OVR.DUP.2 |
| FDV-DET8 | E.WRG.READ.1 | - | K3 | 값 | OK | 판독 오류(유형 미세분) |
| FDV-MEDMAT | AUX.REF | - | - | 값 | OK | 치료재료 판별 근거 없음 |
| FDV-EDISIM | - | - | - | - | NA | 검증 유사도 오탐 |
| SR-1#2 | E.MIS.TARGET.2 | - | K1 | 레코드(행) | OK | 집계 행 삭제 |
| SR-2#2 | AUX.POST.ALTER | E.MIS.FIELD.2 | K1 | 값 | OK | 인쇄된 급여 칸을 지움 |
| SR-3#2 | P.MIS.UNIT.1 | E.MIS.FIELD.2 | K1 | 열 | OK | 인쇄된 열이 배치에서 빠짐 |
| SR-4#2 | E.OVR.GEN.1 | E.OVR.DUP.2 | K2 | 값 | AMBIG | 집계 행 날짜 빈칸에 날짜 기재. GEN.1 vs DUP.2 vs ASSIGN.1. 같은 규칙 부족(AR-11) |
| SR-5#2 | AUX.EVAL | - | - | 값 | OK | 소수 인쇄 vs 정수 정답 |
| SR-6#2 | AUX.POST.ALTER | - | K3 | 필드 | OK | 처리 순서로 합계 필드 미교정 |
| PP-1 | AUX.POST.ALTER | E.OVR.DUP.2 | K2 | 필드 | OK | 종료일에 시작일 복사 |
| PP-2 | AUX.POST.ALTER | E.OVR.GEN.2 | K2 | 필드 | OK | 표 날짜로 계산해 채움 |
| PP-3 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | 같은 날짜 인쇄 시 종료일 못 채움. COMPOSE.1 후보 |
| PO-1 | AUX.POST.ALTER | E.OVR.GEN.2 | K2 | 값 | OK | 표시와 총액으로 추론 |
| PO-2 | AUX.POST.ALTER | E.OVR.DUP.2 | K2 | 필드 | OK | 종료일에 시작일 복사 |
| PO-3 | E.WRG.CTX.1 | E.WRG.ASSIGN.2 | K7 | 열 | OK | 유사 머리글 매칭 오류. 문서 원인단계는 parse로 적힘 |
| PO-4 | E.OVR.GEN.1 | E.OVR.DUP.2 | K2 | 값 | AMBIG | 집계 행에 날짜 기재(SR-4와 동일 사건 유형) |
| PO-5 | AUX.EVAL | - | - | 값 | OK | 정답지가 처방일자 복사 |
| SO-1 | AUX.INPUT | E.MIS.FIELD.2 | K1 | 필드 | OK | 90도 눕힌 스캔, 열 순서 판별 실패. 후속 P.WRG.ORDER.1 후보 |
| SO-2 | - | - | - | - | NA | 검증 대기(미확정) |
| SO-3 | AUX.INPUT | - | K3 | 문서 | OK | VLM 입력 방향 미정규화(잠재) |
| AR-1 | - | - | - | - | NA | 재처리 예산 설계 |
| AR-2 | E.WRG.READ.1 | - | K3 | 값 | OK | 주입 오독을 교정 못 함 |
| AR-3 | AUX.EVAL | - | - | 값 | OK | 미검수 silver 라벨 |
| VX-1 | E.OVR.GEN.1 | E.OVR.GEN.2 | K2 | 값 | OK | 합계를 지어냄+빈칸에 값(OCR 텍스트만 사용) |
| VX-2 | P.STR.REL.1 | P.STR.SPLIT.1,P.WRG.READ.1 | K7 | 표·그룹·섹션 | OK | colspan 누락+합계 행 뭉침+오독(복합) |
| VX-3 | AUX.SCHEMA | E.MIS.FIELD.2 | K1 | 열 | OK | 스키마 생성 오류 |
| VX-4 | AUX.SCHEMA | E.MIS.FIELD.2 | K1 | 열 | OK | 스키마 생성에서 열이 필드로 안 나옴 |
| RT-1 | P.STR.REL.1 | P.MIS.UNIT.1,P.STR.SPLIT.1 | K7 | 표·그룹·섹션 | OK | rowspan 오류+열 누락+합계 행(복합) |
| RT-2 | P.STR.SPLIT.1 | - | K5 | 표·그룹·섹션 | OK | 흐린 괘선 표 뭉개짐 |
| RT-3 | P.STR.SPLIT.2 | - | K5 | 값 | OK | 줄무늬로 병합 셀 분리 |
| RT-4 | P.STR.SPLIT.1 | - | K5 | 값 | OK | 괘선 놓침으로 라벨 병합 |
| RT-5 | - | - | - | 페이지 | NA | 인프라(대형 페이지 시 컨테이너 재시작). 해상도 한계는 AUX.INPUT 후보 |
| KV-1 | E.OVR.GEN.1 | E.STR.ORDER.1 | K2 | 레코드(행) | OK | 라벨보다 많은 행, 행 끝에 덧붙음 |
| KV-2 | E.OVR.DUP.1 | - | K2 | 레코드(행) | OK | 행 중복 |
| KV-3 | AUX.EVAL | E.WRG.READ.1 | K6 | 레코드(행) | OK | 코드 오독으로 행 정렬 키 어긋남 |
| KV-4 | E.WRG.NORM.4 | - | K3 | 값 | OK | 인쇄 항목 대신 표준 항목명 |
| KV-5 | E.OVR.GEN.1 | - | K2 | 레코드(행) | OK | 26행 지어냄 |
| KV-6 | P.WRG.READ.1 | - | K3 | 문자·토큰 | OK | 1~2글자 오인식 |
| KV-7 | P.MIS.UNIT.2 | E.MIS.TARGET.1 | K1 | 표·그룹·섹션 | OK | 품질 불량으로 항목 머리글 못 잡아 0행 |
| KV-8 | AUX.EVAL | - | - | 값 | OK | 정답지 오기 |
| PC-1 | AUX.INPUT | E.MIS.TARGET.1 | K1 | 페이지 | OK | 긴 입력 예산 초과로 뒤쪽 페이지 버림. v4 일부 미처리 |
| PC-2 | AUX.INPUT | E.MIS.PART.1 | K3 | 표·그룹·섹션 | OK | 거대 블록 잘림 |
| JP-1 | E.CON.DONE.1 | E.CON.DONE.3 | K10 | 문서 | OK | JSON 파싱 오류+반복 루프 |
| JP-2 | E.WRG.ASSIGN.2 | - | K4 | 필드 | OK | 행 내 한 칸 밀림, 행 합의로 미탐 |
| LG-1 | P.WRG.READ.4 | E.CON.EVID.3 | K3 | 문자·토큰 | OK | 공백 삽입 오독으로 근거 매칭 실패(거짓 경고) |
| LG-2 | E.CON.EVID.3 | - | K10 | 값 | OK | 서로 다른 셀 4개가 같은 bbox |
| LG-3 | P.WRG.READ.1 | E.CON.EVID.3 | K3 | 문자·토큰 | OK | 한 글자 차이로 근거 매칭 실패 |
| LG-4 | - | - | - | - | NA | 근거 불가 필드(불리언)의 경고 오탐 |
| AE-1 | - | - | - | - | NA | 집계(유형 미특정) |
| AE-2 | AUX.EVAL | - | - | 필드 | OK | 서술형 라벨 관례 모호 |
| AE-3 | P.MIS.UNIT.2 | E.MIS.FIELD.1 | K1 | 표·그룹·섹션 | OK | 머리글 잃어 표준 항목 행 복원 불가 |
| AE-4 | - | - | - | - | NA | 집계(유형 미특정) |
| E210-1 | - | - | - | 문서 | NA | 운영(AO 폴링 시간초과) |
| E210-2 | - | - | - | - | NA | 재현성 축(간헐), 유형 아님 |
| VR-1 | E.MIS.FIELD.1 | - | K1 | 레코드(행) | OK | 금액 빈 항목 행을 모델이 버림 |
| edge:orientation | AUX.INPUT | P.WRG.ORDER.1,E.MIS.FIELD.2 | K6 | 페이지 | OK | 태그 적절. 결과 연결 ID(읽기 순서·필드 누락) 병기 권고 |
| edge:region_loss | P.MIS.AREA.2 | - | K1 | 페이지 | OK | 태그 적절(P.MIS.AREA.2, AUX.INPUT). RC-1류 근거 영역 잘림은 E.CON.EVID.1 추가 가능 |
| edge:resolution_loss | P.WRG.READ.1 | P.MIS.CHAR.1,P.MIS.CHAR.2 | K3 | 문자·토큰 | OK | 태그 적절하나 오독 결과 P.WRG.READ.1 추가 권고(AR-12, KV-6) |
| edge:photometric | P.MIS.CHAR.1 | P.WRG.READ.1 | K3 | 문자·토큰 | OK | 태그 적절. 이진화·대비 원인은 AUX.INPUT 병기 가능 |
| edge:document_boundary | P.STR.DOC.1 | P.STR.DOC.2 | K5 | 문서 | OK | 태그 적절. 경계가 맞는데 값 연결 오류면 E.WRG.CTX.4·E.STR.SPLIT.3 추가 |
| edge:length_scale | AUX.INPUT | P.MIS.AREA.1,E.MIS.TARGET.1 | K1 | 페이지 | OK | 태그 적절하나 원인은 AUX.INPUT(긴 입력 예산, PC-1) 병기 권고 |
| edge:page_boundary_split | P.STR.LINK.2 | E.WRG.CTX.3 | K5 | 표·그룹·섹션 | OK | 태그 적절 |
| edge:cell_displacement | E.WRG.ASSIGN.2 | P.WRG.POS.1 | K4 | 값 | OK | 태그 일부 부적절: P.STR.REL.3(라벨·값 짝)은 서식형 라벨용, 표 열 밀림은 P.STR.REL.2·PX-3 유형 |
| edge:structure_omission | P.MIS.UNIT.1 | E.MIS.FIELD.1,E.MIS.FIELD.2 | K1 | 열 | OK | 태그 일부 부적절: P.OVR.GEN.1은 누락이 아닌 생성. UNIT.1·E.MIS.FIELD.1 추가 권고 |
| edge:non_data_rows | E.OVR.SCOPE.1 | E.OVR.SCOPE.2,P.WRG.TYPE.1 | K2 | 레코드(행) | OK | 태그 일부 부적절: P.STR.HIER.2(각주·캡션 연결)는 맞지 않음. 요약 행 취급은 TARGET.2·정책 |
| edge:span_hierarchy | P.STR.REL.1 | E.WRG.CTX.2,P.STR.HIER.1,E.STR.GROUP.1 | K7 | 열 | OK | 태그 적절 |
| edge:header_variation | P.STR.REL.2 | E.WRG.CTX.1 | K7 | 열 | OK | 태그 적절 |
| edge:semantic_duplicate | E.OVR.DUP.2 | P.OVR.DUP.2 | K2 | 필드 | OK | 태그 일부 부적절: E.STR.ARRAY.1(배열 길이 대응)은 의미 중복과 무관, 제거 검토 |
| edge:distractor_values | E.WRG.ASSIGN.1 | E.OVR.SCOPE.2,E.WRG.PICK.1,P.WRG.TYPE.1 | K4 | 값 | OK | 태그 적절 |
| edge:glyph_confusion | P.WRG.READ.1 | E.WRG.READ.1 | K3 | 문자·토큰 | OK | 태그 적절 |
| edge:numeric_format | P.WRG.READ.2 | E.MIS.PART.2,E.WRG.NORM.2,E.WRG.NORM.3 | K3 | 값 | OK | 태그 적절. 소수 버림(SUM-4)은 E.WRG.NORM.4 추가 |
| edge:surface_form | E.WRG.NORM.4 | AUX.POST.NORM,E.MIS.PART.1 | K3 | 값 | OK | 태그 적절 |
| edge:encoded_categorical | E.WRG.NORM.1 | E.WRG.NORM.4 | K3 | 값 | OK | 태그 적절 |
| edge:partial_record | E.MIS.FIELD.1 | E.MIS.PART.1,E.MIS.FIELD.2 | K1 | 레코드(행) | OK | 태그 적절 |
| edge:multi_value_cell | E.MIS.PART.3 | E.CON.SCHEMA.3,P.STR.SPLIT.1,E.STR.SPLIT.1 | K1 | 값 | OK | 태그 적절. 한 값을 여러 필드로 나누는 경계는 E.STR.COMPOSE.1 추가 |
| edge:printed_inconsistency | AUX.POST.VALID | AUX.POST.ALTER,E.WRG.PICK.2,E.CON.RANGE.3 | K10 | 레코드(행) | AMBIG | 태그는 적절하나 원문 자체가 제약 위반인 경우 RANGE.3이 오류인지 탐지 사실인지 규칙 부재(RR-2, RC-3과 동일) |
| edge:unprinted_derivable | E.OVR.GEN.2 | E.OVR.GEN.1,P.OVR.GEN.1 | K2 | 값 | OK | 태그 적절 |
| edge:fact_attributes | E.WRG.ATTR.1 | E.WRG.ATTR.2,E.WRG.ATTR.3,E.WRG.ASSIGN.3 | K8 | 값 | OK | 태그 적절(예상 시나리오) |
| edge:selection_marks | P.WRG.STATE.1 | E.WRG.READ.3,P.MIS.MARK.1 | K8 | 비문자 표시 | OK | 태그 적절 |
| edge:occlusion | P.MIS.CHAR.1 | P.OVR.FALSE.1,P.WRG.STATE.2,E.MIS.ABST.1 | K1 | 문자·토큰 | OK | 태그 일부 부적절: P.MIS.AREA.2는 영역 단위 누락, 가림은 문자 누락(CHAR.1) 쪽. STATE.3·ABST.2는 가림 사례에 반대(과보류)라 정상 보류와 구분 필요 |
| edge:handwriting | P.WRG.READ.3 | P.MIS.MARK.2,P.STR.REL.4 | K3 | 문자·토큰 | OK | 태그 일부 부적절: P.MIS.MARK.2는 수정 표시용, 손글씨 메모 혼입은 P.WRG.TYPE.1 추가 |
