# 분류 대응 검증 chunk-01 (v3+v4)

입력 행 294건. 판정별: OK 241, AMBIG 16, NEW 9, NA 28

표기: UNATTR = 귀속 미확정(분류 경계 규칙 '단계 귀속'에 따라 후보 유지). 중복 사례ID는 `@L<원문 행번호>`를 붙임. 후속ID 칸의 쉼표는 복수 ID. K `-`는 정답지·정책 등 단위 차이로 표현되지 않는 항목.

## AMBIG 목록

| 묶음 | 사례ID | 내용 | 후보 | 부족한 규칙(제안) |
|---|---|---|---|---|
| AMB-1 | IT-1@L13, IT-2@L14, IT-1@L83, IT-6@L88 | 체크 기호('[V]')가 값에 섞이거나 'V'만 출력 | E.WRG.READ.2 / READ.3 / NORM.4 | 선택 표시 기호가 값 문자열에 혼입되면 READ.3(상태 판독)과 READ.2(옮기며 변경) 중 무엇인지 규칙 필요. 제안: 선택 결과가 맞으면 READ.2, 선택 자체가 틀리면 READ.3 |
| AMB-2 | PX-8, PR-항목명오독, AR-2@L289 | 기호·한 글자 탈락(보철·교정료→보철교정료, 끝 '료' 누락) | E.WRG.READ.1 / E.MIS.PART.1 / P.MIS.CHAR.1 / E.WRG.NORM.4 | 문자 탈락과 오인식, 변환 규칙 결과를 가르는 기준 필요. 제안: 규칙 정의가 있으면 NORM, 없으면 문자 수 감소는 PART/CHAR, 치환은 READ |
| AMB-3 | RK-1, KV-7fill오매핑, KV-11성명동의어 | 공용 라벨이 여러 필드(환자·의사·기관) 후보 | E.WRG.CTX.1 / CTX.4 / PICK.1 / ASSIGN.1 | 같은 라벨이 복수 필드에 걸릴 때 CTX와 PICK 구분 규칙 필요. 제안: 라벨→필드 매핑 오류는 CTX.1, 같은 필드 후보 선택은 PICK |
| AMB-4 | XD-11, RE-맞바뀜, CORR-02 | 이웃 열 통째 맞바뀜 | E.WRG.CTX.1 / E.WRG.ASSIGN.2 | 머리글 의미 오해(원인)와 열 오배정(결과)을 가르는 증거 기준 필요. 제안: 머리글 근거 있으면 CTX.1을 원인으로, 없으면 ASSIGN.2 + 일괄 밀림 패턴 |
| AMB-5 | E2E-1.3, CORR-04, VER-11 | 빈 필드를 원문 다른 위치의 값으로 채움 | E.WRG.ASSIGN.1/3 / E.OVR.GEN.1 | '빈칸을 값으로 채움=과추출' 규칙과 '다른 필드 배정' 규칙 충돌. 제안: 값이 원문 다른 칸에 실재하면 ASSIGN, 어디에도 없으면 GEN |

## NEW 목록

| 사례ID | 내용 | 칸(K×단위) | 제안 노드 |
|---|---|---|---|
| PX-3, IT-8, IT-9, IT-15, IT-17, LT-1 | Docraft 표 요청 408·502·ReadTimeout으로 표·행 미처리 | K1×표 | AUX.RUN 하위 `호출 실패·시간초과로 단위 미처리` (결과는 P.MIS.AREA.2 / E.MIS.FIELD.1에 연결) |
| SR-6 | 행 번호 검사 오탐으로 정상 결과 14건 중 13건을 폐기하고 asis로 대체 | K3×표 | AUX.POST.VALID.2 `검증 오탐으로 정상 값·결과 폐기/대체` (과보류 E.MIS.ABST.2는 값 단위 보류만 포함) |
| KV-13 | 청크가 표 중간에서 분할, 중복 제거 불완전, 초과 쪽 이미지 없음 | K5×표 | AUX.INPUT 하위 `입력 분할(청크) 경계 처리 오류` |
| CORR-01 | 교정 결과가 최종 value에 반영되지 않음(CORR-08도 부분) | K3×값 | AUX.POST.APPLY `검출·교정 결과 미반영` |

## 자주 쓴 ID 상위 15 (원인+후속 합산)

| 순위 | ID | 건수 |
|---|---|---|
| 1 | AUX.EVAL | 31 |
| 2 | E.MIS.FIELD.2 | 26 |
| 3 | E.WRG.ASSIGN.2 | 17 |
| 4 | E.OVR.GEN.2 | 16 |
| 5 | P.WRG.READ.1 | 16 |
| 6 | E.OVR.GEN.1 | 14 |
| 7 | AUX.INPUT | 13 |
| 8 | AUX.POST.ALTER | 11 |
| 9 | E.MIS.FIELD.1 | 11 |
| 10 | E.WRG.ASSIGN.1 | 11 |
| 11 | AUX.REF | 11 |
| 12 | E.WRG.READ.1 | 10 |
| 13 | P.STR.SPLIT.1 | 10 |
| 14 | E.OVR.DUP.2 | 10 |
| 15 | AUX.POST.PICK | 9 |

## 전체 표

| 사례ID | 원인ID | 후속ID | K | 단위 | 판정 | 비고 |
|---|---|---|---|---|---|---|
| PX-1 | AUX.POST.ALTER | E.MIS.FIELD.2 | K1 | 값 | OK | 후처리가 맞는 값을 빈칸으로 바꿈, 정책 결정으로 해결 |
| PX-2 | E.CON.SCHEMA.1 | E.MIS.FIELD.2 | K10 | 필드 | OK | 규칙 참조 키 이름 불일치(상한액/상환액)로 필드 비어 출력 |
| PX-3 | NEW:AUX.RUN.TIMEOUT | P.MIS.AREA.2 | K1 | 표 | NEW | AUX.RUN 칸: 표 요청 408·502 시간초과로 표 단위 미처리. 병합칸 분류명은 E.WRG.CTX.2 후보 |
| PX-4 | E.MIS.FIELD.2 | - | K1 | 열 | OK | 열 통째 누락(패턴 축 일괄), 칸 단위 채움률로 미탐 |
| PX-5 | E.WRG.CTX.2 | E.MIS.FIELD.2 | K7 | 값 | OK | 병합 분류명 상속 실패, 문서 분류 G5-b |
| PX-6 | E.MIS.FIELD.2 | - | K1 | 값 | OK | 누락 칸의 90% 이상 미탐지(자동 탐지 축) |
| PX-7 | E.OVR.GEN.1 | - | K2 | 값 | OK | 빈칸을 '1'로 채움(과추출) |
| PX-8 | E.WRG.READ.2 | E.WRG.NORM.4 | K3 | 값 | AMBIG | '보철·교정료'→'보철교정료'. 후보 READ.2 vs NORM.4, 부족한 규칙: 기호(가운뎃점) 소실을 변환 규칙 결과와 옮기다 생긴 변경으로 가르는 기준(AMB-2) |
| PX-9 | E.MIS.FIELD.2 | - | K1 | 필드 | OK | AO가 빈칸, Docraft가 채움(AO측 누락) |
| PX-10 | AUX.EVAL | - | - | 값 | OK | 정답지 항등식 만족률은 정답지 품질 지표 |
| IT-1@L13 | E.WRG.READ.2 | E.WRG.READ.3 | K3 | 값 | AMBIG | 체크 기호 '[V]'가 값에 남음. 후보 READ.2/READ.3/NORM.4, 부족한 규칙: 선택 표시 기호가 값 문자열에 섞인 경우(AMB-1) |
| IT-2@L14 | E.WRG.READ.3 | AUX.POST.PICK | K8 | 값 | AMBIG | Docraft가 'V'만 반환, 분기 9로 AO값 유지. AMB-1과 동일, 후속은 AUX.POST.PICK |
| IT-3@L15 | AUX.EVAL | - | K3 | 값 | OK | 정답 원문 '의원' vs 표준 4값, 정책 통일 |
| IT-4@L16 | E.WRG.READ.3 | - | K8 | 값 | OK | 병원급을 의원급으로 선택 오판 |
| IT-5@L17 | E.WRG.NORM.1 | E.CON.RANGE.1 | K3 | 값 | OK | 표준 4값으로 정규화 안 됨, 허용 목록 밖 값 |
| IT-6@L18 | E.WRG.READ.3 | - | K8 | 값 | OK | 선택 표시 오판(해결 2건, 미해결 1건) |
| IT-7 | E.WRG.NORM.3 | - | K3 | 값 | OK | 0을 빈 값으로 처리 |
| IT-8 | NEW:AUX.RUN.TIMEOUT | E.MIS.FIELD.1 | K1 | 행 | NEW | 표 요청 408로 선별급여·끝수처리 행 누락(AUX.RUN 칸) |
| IT-9 | NEW:AUX.RUN.TIMEOUT | E.MIS.FIELD.2 | K1 | 값 | NEW | 408·502로 분류명 교정 불가, 급여구분 오류 동반 |
| IT-10 | AUX.RUN | E.MIS.FIELD.2 | K1 | 값 | OK | 하네스가 Docraft 응답의 바뀐 키 경로를 못 읽음(결과 통합) |
| IT-11 | AUX.POST.PICK | E.WRG.PICK.1 | K9 | 값 | OK | Docraft 정답을 분기 9 판정으로 미채택 |
| IT-12 | AUX.EVAL | - | K3 | 값 | OK | 정답지 빈칸 vs 열추출 정책 불일치 |
| IT-13 | AUX.POST.ALTER | E.OVR.GEN.2 | K3 | 값 | OK | 규칙이 0을 비정상 판정해 다른 값으로 계산 교정 |
| IT-14 | - | - | - | 값 | NA | 검증 표식 부착 범위(뷰어 표시) 문제 |
| IT-15 | NEW:AUX.RUN.TIMEOUT | E.MIS.FIELD.2 | K1 | 값 | NEW | 표 응답 후 502로 항목 빈 값 |
| IT-16 | AUX.POST.PICK | E.WRG.PICK.1 | K9 | 값 | OK | 분기 9 판정이 맞는 Docraft값 미채택 |
| IT-17 | NEW:AUX.RUN.TIMEOUT | P.MIS.AREA.2 | K1 | 표 | NEW | 표 요청 408/ReadTimeout/502로 표 응답 없음. 대표 사례 |
| IT-18 | AUX.EVAL | - | K3 | 값 | OK | 열추출·소계 행 정책 차이 |
| DT-1 | AUX.EVAL | E.OVR.GEN.2 | K2 | 값 | OK | 정답지 초안에 계산값 기재(원문 값처럼) |
| DT-2 | AUX.EVAL | E.MIS.TARGET.2 | K1 | 행 | OK | 가산 행 포함 관례, 채점 범위 정책 |
| DT-3 | AUX.EVAL | E.OVR.GEN.2 | K2 | 값 | OK | 표기 없는 값을 병실·명칭으로 추정(초안) |
| ST-1 | E.OVR.GEN.2 | - | K2 | 값 | OK | 인쇄 빈칸을 합계로 계산해 채움 |
| ST-2 | E.OVR.DUP.1 | E.WRG.READ.1,E.MIS.FIELD.1 | K2 | 행 | OK | 복합(중복 행·합계 오독·누락 행), 합계식 불일치는 탐지 경로 |
| ST-3 | E.CON.RANGE.2 | E.CON.SCHEMA.3 | K10 | 값 | OK | 날짜 형식 위반, 쉼표 나열은 단일 값 규칙 위반 |
| ST-4 | E.WRG.NORM.3 | E.MIS.FIELD.2 | K3 | 필드 | OK | 체크칸 없는 서식에서 null/N 처리, 본문 날짜 미반영 |
| ST-5 | E.CON.SCHEMA.1 | - | K10 | 필드 | OK | 요구 키와 현행 키 불일치(AUX.SCHEMA 후보) |
| RK-1 | E.WRG.CTX.4 | E.OVR.GEN.1 | K7 | 값 | AMBIG | 공용 라벨('주소'·'성명')로 다른 개체 값 채움. 후보 CTX.1/CTX.4/PICK.1/ASSIGN.1, 부족한 규칙: 동일 라벨의 복수 필드 후보 구분(AMB-3) |
| RK-2 | UNATTR | - | - | 문서 | OK | 서식 변형 정확도 하락, 원인 미특정(단계 귀속 규칙) |
| RK-3 | P.STR.SPLIT.1 | P.WRG.ORDER.1 | K5 | 행 | OK | 행 밀림·셀 합쳐짐, 신뢰도 부재는 별도 |
| PE-1 | P.MIS.UNIT.1 | P.STR.SPLIT.1 | K1 | 열 | OK | 열 누락과 합계 칸 합쳐짐 복합 |
| PE-2 | E.MIS.TARGET.2 | - | K1 | 행 | OK | 추출 지시가 요약 행을 제외 |
| PE-3 | AUX.INPUT | P.WRG.POS.2 | K4 | 열 | OK | 회전 방향 처리 실패로 좌표·열 판별 실패 |
| PE-4 | UNATTR | E.WRG.ASSIGN.* | - | 표 | OK | 집계 사례(G1~G10), 하위 사례별 별도 분류 필요 |
| PE-5 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 약품비를 행위료 필드에 배정 |
| PE-6 | P.STR.REL.2 | P.WRG.READ.5 | K7 | 열 | OK | 병합 머리글 연결 실패, [UNK]는 문자 코드 표현 손실 |
| PE-7 | P.STR.SPLIT.1 | P.WRG.READ.1 | K5 | 행 | OK | 붙은 머리글·뭉친 행·한 셀 복수 숫자 복합 |
| KC-1 | P.STR.SPLIT.1 | E.MIS.FIELD.2 | K5 | 행 | OK | 병명 두 행을 한 행으로 합치고 다음 행 비움 |
| KC-2 | P.STR.SPLIT.1 | E.MIS.FIELD.2 | K5 | 행 | OK | 동일 유형 |
| SR-1@L51 | E.OVR.GEN.1 | AUX.POST.ALTER,E.OVR.GEN.2 | K2 | 값 | OK | 집계 행 일자·급여 채움과 지움 복합 |
| SR-2@L52 | E.MIS.FIELD.2 | - | K1 | 열 | OK | 급여액 열이 열 배치에서 빠짐 |
| SR-3 | E.OVR.GEN.1 | - | K2 | 값 | OK | 합계 행 빈 날짜를 모델이 채움 |
| SR-4 | AUX.EVAL | - | K3 | 값 | OK | 정답지 소수 표기 대조 |
| SR-5 | AUX.EVAL | - | - | 필드 | OK | 합계 필드 대상 행 정의 정책 |
| SR-6 | NEW:AUX.POST.VALID.2 | E.MIS.FIELD.2 | K3 | 표 | NEW | AUX.POST 칸: 번호 검사 오탐으로 정상 결과를 폐기하고 대체 경로 사용 |
| AR-1@L57 | E.CON.DONE.4 | P.MIS.AREA.1 | K10 | 문서 | OK | 부분 페이지 결과를 완료로 표시 |
| AR-2@L58 | - | - | - | 문서 | NA | 내보내기 수식 삽입(보안) |
| AR-3@L59 | - | - | - | 문서 | NA | API 입력 검증 |
| AR-4@L60 | AUX.RUN | - | K3 | 문서 | OK | 늦은 구 결과가 새 결과 덮음 |
| AR-5@L61 | AUX.RUN | - | K10 | 문서 | OK | 완료 상태와 결과 저장 비원자(E.CON.DONE.3 후보) |
| AR-6@L62 | AUX.EVAL | - | - | 묶음 | OK | 채점 기준 혼재 |
| MF-1 | E.CON.DONE.1 | - | K10 | 문서 | OK | 긴 행 JSON 문법 실패 |
| MF-2 | E.WRG.ASSIGN.2 | E.MIS.FIELD.1,AUX.POST.ALTER | K4 | 열 | OK | 예상 시나리오(제안 문서) |
| DB-1 | - | - | - | 문서 | NA | DB 접속 장애(운영) |
| XD-1 | E.STR.COMPOSE.1 | E.OVR.DUP.2 | K5 | 필드 | OK | 기간 한 칸을 시작·종료로 나눌 때 종료에 시작 복사 |
| XD-2 | P.STR.SPLIT.1 | E.MIS.FIELD.2 | K5 | 열 | OK | 머리글 붙임으로 열 통째 누락 |
| XD-3 | E.WRG.CTX.1 | E.MIS.FIELD.2 | K7 | 열 | OK | 결합 머리글(수가코드·청구코드)의 의미 연결 실패 |
| XD-4 | E.MIS.FIELD.2 | - | K1 | 표 | OK | 금액 통째 비움을 게이트가 미탐(자동 탐지 축) |
| XD-5 | AUX.INPUT | P.WRG.POS.2 | K4 | 열 | OK | 회전 문서 방향 처리와 좌표 역변환 |
| XD-6 | AUX.INPUT | P.WRG.READ.1 | K3 | 표 | OK | 교정 크롭 방향 미정규화 |
| XD-7 | AUX.INPUT | - | K3 | 문서 | OK | 회전 정답지 정확도 하락 |
| XD-8 | UNATTR | E.MIS.FIELD.1 | K1 | 행 | OK | 원인 미확정, 귀속 미확정 유지 |
| XD-9 | AUX.INPUT | E.MIS.TARGET.2 | K1 | 페이지 | OK | 누운 합계 쪽 방향 정규화 후 놓침 |
| XD-10 | E.WRG.CTX.1 | E.WRG.ASSIGN.2 | K7 | 열 | OK | 2단 머리글 해석 오류로 열 오배정 |
| XD-11 | E.WRG.ASSIGN.2 | E.WRG.CTX.1 | K4 | 열 | AMBIG | 두 열 맞바뀜. 후보 CTX.1 vs ASSIGN.2, 부족한 규칙: 머리글 의미 오해와 단순 열 오배정 구분(AMB-4) |
| XD-12 | E.WRG.ASSIGN.1 | E.OVR.DUP.2 | K4 | 값 | OK | 명칭이 코드 칸으로, 항목에 명칭 복사 |
| XD-13 | E.CON.DONE.3 | E.MIS.FIELD.1 | K1 | 행 | OK | 긴 표 중간에 끊김 |
| XD-14 | - | - | - | 문서 | NA | 게이트 오발동은 호출 비용 중심 |
| XD-15 | P.STR.REL.2 | P.MIS.UNIT.2 | K7 | 열 | OK | 머리글 열 순서 판별 실패(머리글 낱말 없음 포함) |
| XD-16 | E.WRG.ASSIGN.3 | AUX.EVAL | K4 | 값 | OK | 실행일자·시작일자 역할 정책 |
| XD-17 | AUX.INPUT | P.MIS.AREA.1 | K1 | 페이지 | OK | 여러 쪽 PDF 처리 실패 |
| IT-1@L83 | E.WRG.READ.3 | E.WRG.READ.2 | K8 | 값 | AMBIG | Docraft가 'V'만 반환. AMB-1 |
| IT-2@L84 | AUX.POST.PICK | E.WRG.PICK.1 | K9 | 값 | OK | 근거 중복 규칙이 맞는 Docraft값 기각 |
| IT-3@L85 | E.CON.EVID.1 | AUX.POST.PICK | K10 | 값 | OK | 출처 없음 판정으로 미채택 |
| IT-4@L86 | E.WRG.READ.3 | - | K8 | 값 | OK | 의심 조건 미탐으로 Docraft 미호출(미탐지 축) |
| IT-5@L87 | P.WRG.READ.1 | E.WRG.NORM.1 | K3 | 값 | OK | '고상급종합병원' 표기 변형 |
| IT-6@L88 | E.WRG.READ.3 | AUX.POST.PICK | K8 | 값 | AMBIG | 체크 기호 포함 값. AMB-1 |
| LT-1 | NEW:AUX.RUN.TIMEOUT | E.MIS.FIELD.1 | K1 | 행 | NEW | 표 요청 408로 행 누락과 교정 불가 |
| LT-2 | AUX.RUN | E.MIS.FIELD.2 | K1 | 값 | OK | IT-10과 동일 |
| LT-3 | AUX.POST.PICK | E.WRG.PICK.1 | K9 | 값 | OK | IT-11과 동일 |
| LT-4 | AUX.POST.ALTER | E.OVR.GEN.2 | K3 | 값 | OK | IT-13과 동일 |
| LT-5 | AUX.EVAL | - | K3 | 값 | OK | IT-12와 동일 |
| LT-6 | E.OVR.DUP.2 | - | K2 | 값 | OK | 항목에 EDI명칭 복제 |
| LT-7 | AUX.EVAL | - | K3 | 값 | OK | 정답지 소수 버림 |
| LT-8 | E.MIS.ABST.2 | - | K8 | 필드 | OK | 합계 행 없는 서식을 규칙이 미해결로 처리 |
| LT-9 | E.MIS.FIELD.2 | - | K1 | 열 | OK | 투여량 열 누락 보완 |
| LT-10 | - | - | - | 값 | NA | IT-14와 동일 |
| RC-1 | - | - | - | 문서 | NA | 합성 데이터 생성 설계 |
| SR-1@L100 | - | - | - | 문서 | NA | 합성 엣지 선정 |
| SR-2@L101 | - | - | - | 문서 | NA | 합성 엣지 목록 |
| RT-1 | - | - | - | 문서 | NA | 합성 검수 파이프라인 |
| TR-1 | - | - | - | 문서 | NA | 조회·로그(운영) |
| AG-1 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 코드 값이 일자로 매핑 |
| RE-열밀림 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7 | 열 | OK | 병합 머리글 뭉개져 열 밀림 |
| RE-맞바뀜 | E.WRG.ASSIGN.2 | E.WRG.CTX.1 | K4 | 열 | AMBIG | 이웃 금액 열 통째 맞바뀜. AMB-4 |
| RE-세부급여복사 | E.OVR.DUP.2 | - | K2 | 값 | OK | 총액을 급여 칸에 복사 |
| RE-단가투여량열 | E.OVR.GEN.1 | - | K2 | 열 | OK | 머리글 없는 열 값 채움 |
| RE-EDI밀림 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 명칭이 EDI코드 열로 |
| RE-외래종료일 | E.OVR.GEN.2 | - | K2 | 값 | OK | 빈 종료일을 시작일로 채움(후처리 규칙) |
| RE-급여합계 | E.OVR.GEN.2 | E.WRG.ASSIGN.1 | K2 | 값 | OK | 미인쇄 합계 계산 채움과 총액 이동 |
| RE-공단총액오독 | E.WRG.READ.1 | - | K3 | 값 | OK | 합계 행 값으로 교체 |
| RE-산술불일치 | E.CON.RANGE.3 | E.WRG.READ.1 | K10 | 행 | OK | 탐지 경로, 실제 오류는 판독 오류 |
| RE-합계불일치 | E.CON.RANGE.3 | E.WRG.READ.1 | K10 | 묶음 | OK | 동일 |
| RE-날짜역전 | E.CON.RANGE.3 | - | K10 | 필드 | OK | 날짜 선후 제약 |
| RE-주민번호불일치 | E.CON.RANGE.3 | - | K10 | 필드 | OK | 필드 간 제약 |
| RE-등록번호형식 | E.CON.RANGE.2 | - | K10 | 값 | OK | 형식 오류 비움 |
| RE-의사명조각 | E.OVR.SCOPE.2 | - | K2 | 값 | OK | 서식 문구 조각 포함 |
| RE-머리글행 | P.WRG.TYPE.2 | E.OVR.SCOPE.1 | K2 | 행 | OK | 머리글·빈 행을 데이터 행으로 |
| RE-항목명접두 | P.STR.SPLIT.1 | - | K5 | 값 | OK | 분류 칸 텍스트가 항목명에 붙음 |
| RE-치료내역중복 | E.OVR.DUP.2 | - | K2 | 필드 | OK | 다른 문장 내용 중복 |
| RE-저품질스캔 | UNATTR | - | - | 문서 | OK | 저품질 입력, 오탐 18건, 원인 미특정 |
| RE-독립급여열오탐 | E.OVR.GEN.2 | - | K2 | 값 | OK | 총액으로 급여 계산 채움 |
| RE-항목명오류57 | E.MIS.FIELD.1 | E.WRG.ASSIGN.2,P.WRG.READ.1 | K1 | 행 | OK | 복합 57건(행 누락 22·연쇄 밀림 20·오독 5·파서 2) |
| RE-행누락 | E.MIS.FIELD.1 | E.WRG.ASSIGN.2 | K1 | 행 | OK | 연쇄 밀림 동반 |
| RE-급여프롬프트 | E.OVR.DUP.2 | - | K2 | 값 | OK | RE-세부급여복사와 동일 |
| RE-진단일버린룰 | AUX.POST.ALTER | - | K1 | 값 | OK | 폐기된 규칙, 맞는 값 지움 |
| PR-출력그룹위치 | E.STR.GROUP.1 | - | K4 | 필드 | OK | 그룹 위치 오류 |
| PR-항목명오독 | E.WRG.READ.1 | E.MIS.PART.1 | K3 | 값 | AMBIG | 한 글자 누락. 후보 READ.1/PART.1/P.MIS.CHAR.1, 부족한 규칙: 문자 탈락과 오인식 구분(AMB-2) |
| PR-헤더미검출 | P.MIS.UNIT.2 | E.OVR.GEN.1 | K1 | 열 | OK | 머리글 못 찾아 빈 열 규칙 미작동 |
| PR-괄호음수 | E.WRG.NORM.2 | - | K3 | 값 | OK | 괄호 음수 변환 규칙 없음. parse가 괄호를 지우면 P.MIS.MARK.4 |
| PR-납부금액검산 | - | - | - | 필드 | NA | 검산 규칙 백로그(탐지 축) |
| PR-발병일 | - | - | - | 필드 | NA | 스키마 필드 부재(검산 불가) |
| LV-분류오류 | AUX.SCHEMA | - | K3 | 문서 | OK | 문서 유형 오분류 |
| LV-분류놓침 | AUX.SCHEMA | - | K3 | 문서 | OK | 재분류 미탐 |
| LV-진단소견분류 | AUX.SCHEMA | AUX.EVAL | K3 | 문서 | OK | 스키마 동일해 분류 채점으로만 노출 |
| LV-JSON보기비어있음 | - | - | - | 문서 | NA | 뷰어 UI 버그 |
| LV-표머리글가림 | - | - | - | 표 | NA | 뷰어 UI |
| LV-불일치개수 | - | - | - | 묶음 | NA | 뷰어 집계 기준 |
| E2E-1.1 | AUX.EVAL | - | K3 | 값 | OK | 정답지 표기 수정 |
| E2E-1.2 | AUX.EVAL | E.STR.COMPOSE.1 | K3 | 필드 | OK | 정답지 초안이 기간 칸을 빈칸 처리 |
| E2E-1.3 | E.WRG.ASSIGN.1 | E.OVR.GEN.1 | K4 | 값 | AMBIG | 빈 병실에 옆 진료과. 후보 ASSIGN.1 vs OVR.GEN.1, 부족한 규칙: 빈 필드를 다른 위치 값으로 채움(AMB-5) |
| E2E-1.3b | E.OVR.GEN.1 | - | K2 | 값 | OK | 빈 병실에 외래 채움 |
| E2E-1.4 | E.WRG.CTX.2 | E.OVR.DUP.2 | K7 | 값 | OK | 섹션 제목 상속 대신 EDI명칭 복사 |
| E2E-1.5 | P.MIS.UNIT.2 | E.OVR.GEN.1 | K1 | 열 | OK | 머리글 낱말 못 찾음 |
| E2E-1.6 | AUX.EVAL | - | K5 | 행 | OK | '-' 때문에 채점 행 분리 |
| E2E-1.7 | AUX.POST.ALTER | E.WRG.READ.2 | K3 | 값 | OK | 코드 글자를 5·8로 치환 |
| E2E-2.1 | E.WRG.NORM.1 | - | K3 | 열 | OK | 자리표시 값 정책 변동(PX-1) |
| E2E-3.1 | E.OVR.GEN.1 | - | K2 | 값 | OK | Judge가 빈 칸에 금액 생성 |
| E2E-3.2 | AUX.POST.PICK | E.MIS.FIELD.2 | K9 | 값 | OK | Judge가 비우는 쪽 선택 |
| E2E-4.1 | E.WRG.PICK.1 | - | K9 | 값 | OK | 사고발생일자 후보(조회기간 시작일 vs 첫 명세일) |
| E2E-4.2 | AUX.EVAL | - | K3 | 값 | OK | 섹션 번호 포함 정책 |
| E2E-5.흐린사진 | P.WRG.READ.1 | P.STR.SPLIT.1 | K3 | 값 | OK | 흐림, 문자 오독과 소계 행 섞임 |
| E2E-5.OCR422 | - | - | - | 문서 | NA | 서버 기동 순서(운영) |
| RI-D1 | AUX.RUN | - | K3 | 문서 | OK | AR-4와 동일 |
| RI-D3 | - | - | - | 문서 | NA | AR-2와 동일 |
| RI-D5 | E.CON.DONE.4 | P.MIS.AREA.1 | K10 | 문서 | OK | AR-1과 동일 |
| KV-1영수증항목 | AUX.POST.ALTER | E.STR.ORDER.1,E.WRG.ASSIGN.2 | K6 | 행 | OK | 복원 행을 뒤에 끼워 위치 밀림 |
| KV-2EDI명칭 | P.WRG.READ.1 | - | K3 | 값 | OK | 1~2글자 오인식 |
| KV-3단가 | E.OVR.GEN.1 | - | K2 | 값 | OK | 모델 오탐 |
| KV-4투여량 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 열 밀림(패턴 축) |
| KV-5시작일횟수 | E.STR.ORDER.1 | - | K6 | 행 | OK | 행 순서 뒤바뀜 |
| KV-6병명 | P.WRG.READ.1 | - | K3 | 값 | OK | OCR 글자 오류 |
| KV-7fill오매핑 | E.WRG.CTX.1 | - | K7 | 값 | AMBIG | 라벨 매칭으로 다른 필드 값 채움. AMB-3 |
| KV-8진료기간 | E.STR.COMPOSE.1 | - | K5 | 필드 | OK | 기간 라벨의 첫 날짜만 취해 둘 다 시작일 |
| KV-9다페이지판정 | AUX.INPUT | E.WRG.PICK.2 | K1 | 페이지 | OK | Judge에 1쪽 이미지만 전달 |
| KV-10부분포함 | AUX.POST.VALID | E.WRG.PICK.2 | K3 | 값 | OK | 부분 포함 합의를 일치 근거로 오인 |
| KV-11성명동의어 | E.WRG.CTX.4 | - | K7 | 값 | AMBIG | 성명 라벨이 4필드 후보. AMB-3 |
| KV-12소계제거 | E.MIS.TARGET.2 | - | K1 | 행 | OK | 소계 행 무조건 제거 |
| KV-13청크분할 | NEW:AUX.INPUT.CHUNK | E.STR.SPLIT.2,E.OVR.DUP.1 | K5 | 표 | NEW | AUX.INPUT 칸: 입력 분할 경계에서 표 중간 분할·중복·초과 쪽 이미지 없음 |
| KV-고객비급여급여 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 급여 칸 없는 서식에서 비급여가 급여로 |
| KV-고객파싱에러 | P.STR.SPLIT.1 | - | K5 | 값 | OK | 두 행 금액 병합 셀 |
| KV-고객항목명누락 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 금액 빈 행 누락 |
| KV-사고발생일자 | E.OVR.GEN.2 | - | K2 | 필드 | OK | 파생 값 정책 결정 대기(계약 허용 여부) |
| PQ-TIF-GIF | AUX.INPUT | - | K1 | 문서 | OK | 디코딩 실패 |
| PQ-머리글우선 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7 | 열 | OK | 상위 제목이 하위 열명보다 우선 |
| PQ-급여0null | AUX.EVAL | - | K3 | 값 | OK | 0 vs null 계약 |
| PQ-FP13 | E.OVR.GEN.2 | - | K2 | 필드 | OK | 주민번호 파생·라벨 보충·서술 추정 |
| PQ-비급여포함총액 | AUX.EVAL | - | K3 | 값 | OK | 정답지 라벨 오류 |
| PQ-OCR역할 | E.WRG.ASSIGN.3 | - | K4 | 값 | OK | OCR 존재 값 중 다른 역할 선택, 미탐 |
| PQ-변형 | UNATTR | - | - | 문서 | OK | 회전·흐림·가림 일괄 하락(발생 조건 축) |
| PQ-페이지수 | P.CON.DONE.1 | - | K10 | 문서 | OK | 페이지 수 불일치를 일부 성공으로 숨김 |
| PQ-97 | - | - | - | 묶음 | NA | 정확도 목표 미달 지표 |
| TE-사고발생일 | E.CON.EVID.3 | E.OVR.GEN.2 | K10 | 필드 | OK | 파생 값을 직접 근거로 표시 |
| TE-빈칸교정 | - | - | - | 값 | NA | 검증 범위 한계(탐지 축) |
| TE-병합머리글 | P.CON.EVID.1 | P.STR.REL.2 | K10 | 필드 | OK | 좌표 없음으로 근거 미생성 |
| NC-열밀림 | P.WRG.POS.1 | E.CON.EVID.3 | K4 | 열 | OK | 한 행 밀림을 exact 근거로 오인 |
| NC-금액오독 | E.WRG.READ.1 | E.WRG.NORM.3 | K3 | 값 | OK | 오독과 명시적 빈칸을 0으로 |
| NC-성명오교정 | E.WRG.READ.1 | - | K3 | 값 | OK | 모델이 OCR 오독을 반복 |
| NC-미교정 | P.WRG.POS.1 | - | K4 | 열 | OK | 자동 교정 불가 잔여(교정 범위 한계) |
| CORR-01 | NEW:AUX.POST.APPLY | P.WRG.READ.1 | K3 | 값 | NEW | AUX.POST 칸: 교정 결과가 최종 값에 미반영 |
| CORR-02 | E.WRG.ASSIGN.2 | E.WRG.CTX.1 | K4 | 열 | AMBIG | 금액 열 맞바꿈. AMB-4 |
| CORR-03 | E.WRG.CTX.2 | E.OVR.DUP.2 | K7 | 값 | OK | E2E-1.4와 동일 |
| CORR-04 | E.WRG.ASSIGN.1 | E.OVR.GEN.1 | K4 | 값 | AMBIG | 병실에 진료과. AMB-5 |
| CORR-05 | E.OVR.GEN.2 | - | K2 | 값 | OK | 급여구분 추정 채움 |
| CORR-06 | AUX.POST.NORM | - | K3 | 값 | OK | 비표준명 기호 제거(과정규화) |
| CORR-07 | E.STR.SPLIT.3 | - | K5 | 행 | OK | 재판독과 AO 행 동일성 판단 실패 |
| CORR-08 | E.WRG.ASSIGN.2 | - | K4 | 열 | OK | 열 밀림, 교정 반영 실패는 AUX.POST.APPLY 후보 |
| CORR-09 | E.MIS.ABST.2 | - | K8 | 필드 | OK | 규칙이 맞는 칸을 미해결로 |
| CORR-10 | E.MIS.ABST.2 | - | K8 | 행 | OK | 행 단위 미해결 확산 |
| CORR-11 | E.MIS.ABST.2 | - | K8 | 행 | OK | UNITMUL 오판 |
| CORR-12 | E.MIS.ABST.2 | - | K8 | 행 | OK | CALC 오판 |
| CORR-13 | E.MIS.ABST.2 | - | K8 | 필드 | OK | 반대 증거 오용 |
| UI-01 | AUX.INPUT | - | K1 | 문서 | OK | 입력 형식 읽기 실패로 문서 0건 |
| UI-02 | - | - | - | 표 | NA | 판정 로직 설계 |
| UI-03 | - | - | - | 값 | NA | 빈 값 좌표 부재(설계 한계) |
| UI-04 | - | - | - | 필드 | NA | 판정 로직 설계 |
| BENCH-01 | - | - | - | 문서 | NA | 성능 |
| BENCH-02 | - | - | - | 문서 | NA | 측정 환경 |
| MST-01 | AUX.REF | - | K10 | 필드 | OK | 룰셋 마스터 이름 불일치 |
| MST-02 | AUX.REF | - | K10 | 필드 | OK | 존재하지 않는 마스터 이름 |
| MST-03 | AUX.REF | - | K10 | 필드 | OK | 미존재 코드, 성능 문제 동반 |
| MST-04 | AUX.REF | E.MIS.ABST.2 | K8 | 값 | OK | 명칭 유사도 임계로 정상 표기 오탐 |
| MST-05 | UNATTR | - | - | 값 | OK | 마스터 공백 vs 오독 미확정 |
| MST-06 | P.WRG.READ.1 | - | K3 | 값 | OK | OCR 오독 의심 |
| MST-07 | P.WRG.READ.1 | - | K3 | 값 | OK | OCR 오독 의심 |
| MST-08 | AUX.REF | - | K3 | 값 | OK | 명칭 매칭 |
| MST-09 | - | - | - | 값 | NA | 원문 자체가 불완전 코드 |
| MST-10 | E.OVR.DUP.2 | - | K2 | 열 | OK | 열 복제 |
| MST-11 | E.MIS.FIELD.2 | - | K1 | 값 | OK | 합계 칸 미판독 |
| MST-12 | E.MIS.FIELD.2 | - | K1 | 값 | OK | 총액 미판독 |
| KCD-01 | P.WRG.READ.1 | - | K3 | 값 | OK | O와 0 혼동 |
| KCD-02 | AUX.POST.NORM | - | K3 | 값 | OK | 치환 보수성 결정 |
| KCD-03 | AUX.REF | - | K3 | 값 | OK | 명칭 mismatch |
| KCD-04 | E.STR.SPLIT.1 | - | K5 | 행 | OK | 한 칸 복수 코드 |
| KCD-05 | AUX.REF | - | K3 | 값 | OK | 명칭 mismatch |
| KCD-06 | AUX.REF | - | K3 | 값 | OK | 명칭 축약 기재 |
| KCD-07 | AUX.REF | - | K3 | 값 | OK | 접두 미제거 |
| KCD-08 | - | - | - | 필드 | NA | 역방향 조회 기능 설명 |
| KCD-09 | AUX.REF | - | K8 | 값 | OK | 동의어 부재 |
| KCD-10 | AUX.REF | - | K3 | 값 | OK | 느슨한 통과(미탐지 축) |
| KCD-11 | P.MIS.CHAR.1 | P.WRG.READ.4 | K1 | 문자 | OK | 마스터 구축 PDF의 머리 누락·경계 소실 |
| V59-01 | E.MIS.TARGET.2 | - | K1 | 행 | OK | KEEP_TOTALS 영수증만 적용 |
| V59-02 | E.STR.SPLIT.3 | E.WRG.ASSIGN.2 | K5 | 행 | OK | 같은 이름 행 뒤섞임, 출력 정렬 버그는 AUX.RUN |
| V59-03 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 이웃 행으로 밀림 |
| V59-04 | AUX.POST.ALTER | E.WRG.READ.1,P.WRG.READ.2 | K3 | 값 | OK | 약품명 교정 오류 등 복합 |
| V59-05 | E.WRG.NORM.1 | - | K3 | 열 | OK | 자리표시 값 |
| V59-06 | AUX.POST.NORM | E.MIS.PART.2 | K3 | 값 | OK | 소수점 소실 |
| V59-07 | AUX.EVAL | - | K3 | 필드 | OK | 코드 관례 충돌 |
| V59-08 | AUX.INPUT | - | K1 | 페이지 | OK | 제공 쪽에 합계 없음 |
| V59-09 | P.WRG.READ.1 | E.MIS.FIELD.2 | K3 | 값 | OK | '끝수'를 '공수'로 오독 |
| V59-10 | AUX.RUN | - | K4 | 행 | OK | 출력 셀 정렬 버그 착시 |
| V59-11 | E.WRG.ASSIGN.2 | - | K4 | 값 | OK | 금액산정 상자 행 밀림 |
| V59-12 | E.OVR.GEN.2 | - | K2 | 값 | OK | 빈 칸을 다른 합계로 계산 채움 |
| V59-13 | AUX.POST.ALTER | - | K3 | 값 | OK | 인쇄된 항목명 변경 |
| V59-14 | P.WRG.READ.1 | - | K3 | 값 | OK | 항목명 오독 |
| V59-15 | AUX.POST.NORM | E.MIS.PART.2 | K3 | 값 | OK | 부호 삭제 |
| V59-16 | AUX.POST.ALTER | E.OVR.DUP.1 | K2 | 행 | OK | 보충이 오독 이름 행 추가 |
| V59-17 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 선택항목 행 미추출 |
| V59-18 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 비급여를 급여로 |
| V59-19 | AUX.SCHEMA | - | K1 | 문서 | OK | 문서유형 코드값 |
| V59-20 | - | - | - | 문서 | NA | 동기 호출 차단(운영) |
| V59-21 | AUX.EVAL | - | K1 | 행 | OK | 정답 라벨에 집계 행 없음 |
| VER-01 | E.CON.RANGE.2 | - | K10 | 값 | OK | 형식 차이만 있는 값 |
| VER-02 | E.OVR.GEN.1 | - | K2 | 필드 | OK | 기본값 '남' |
| VER-03 | E.WRG.ASSIGN.1 | - | K4 | 필드 | OK | 환자구분을 입통원구분에 |
| VER-04 | E.MIS.FIELD.1 | - | K1 | 행 | OK | 금액 빈 행 누락 |
| VER-05 | E.WRG.ASSIGN.1 | - | K4 | 값 | OK | 비급여를 급여로 |
| VER-06 | P.STR.SPLIT.1 | - | K5 | 값 | OK | 셀 병합 |
| VER-07 | AUX.RUN | - | K3 | 문서 | OK | 케이스 JSON과 이미지가 다른 문서 |
| VER-08 | E.OVR.DUP.2 | - | K2 | 값 | OK | 항목에 EDI명칭(관례 차이) |
| VER-09 | P.WRG.READ.1 | - | K3 | 값 | OK | OCR 오타 |
| VER-10 | E.WRG.CTX.1 | - | K7 | 필드 | OK | 빈 칸의 라벨 글자를 값으로 |
| VER-11 | E.WRG.ASSIGN.3 | E.OVR.GEN.1 | K4 | 값 | AMBIG | 비어 있는 진단일에 발급일. AMB-5 |
| VER-12 | E.MIS.ABST.2 | - | K8 | 행 | OK | 합계 행 한 줄 서식에서 row_copy 오탐 |
| VER-13 | AUX.INPUT | - | K1 | 문서 | OK | 다중 페이지 거절 |
| LBL-01 | AUX.EVAL | - | K3 | 문서 | OK | 정답지 환각·오기 |
| LBL-02 | AUX.EVAL | - | K1 | 행 | OK | 정답지 행 누락·계산 합계 |
| LBL-03 | AUX.INPUT | - | K1 | 페이지 | OK | 입력 쪽이 불완전 |
| LBL-04 | AUX.EVAL | - | - | 필드 | OK | 합계 행 사용 관례 |
| LBL-05 | AUX.EVAL | - | K3 | 값 | OK | 0 vs null 정책 |
| LBL-06 | AUX.EVAL | P.WRG.READ.1 | - | 값 | OK | 처리 기준 없음, 1/I 판독 한계 |
| LBL-07 | E.OVR.GEN.2 | - | K2 | 필드 | OK | 주민번호 유도 정책 |
| NSEAL-01 | E.OVR.SCOPE.2 | - | K2 | 값 | OK | 도장 표시 '인' 포함 |
| PQ-01 | AUX.INPUT | - | K1 | 문서 | OK | PQ-TIF-GIF와 동일 |
| PQ-02 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7 | 열 | OK | PQ-머리글우선과 동일 |
| PQ-03 | AUX.EVAL | - | K3 | 값 | OK | PQ-급여0null과 동일 |
| PQ-04 | E.OVR.GEN.2 | - | K2 | 필드 | OK | PQ-FP13과 동일 |
| PQ-05 | AUX.EVAL | - | K3 | 값 | OK | PQ-비급여포함총액과 동일 |
| PQ-06 | AUX.EVAL | - | - | 묶음 | OK | 분모 설정 |
| PQ-07 | UNATTR | - | - | 문서 | OK | PQ-변형과 동일 |
| INF-01 | UNATTR | E.WRG.ASSIGN.2 | K4 | 값 | OK | 라벨과 불일치 금액, 원인 미특정 |
| INF-02 | E.MIS.FIELD.2 | - | K1 | 값 | OK | 빈칸 미교정 |
| INF-03 | AUX.POST.PICK | - | K9 | 값 | OK | AO 원값 우선으로 Docraft 근거 무시 |
| COV5-01 | E.MIS.FIELD.2 | - | K1 | 값 | OK | PX-6과 동일 |
| COV5-02 | E.MIS.FIELD.2 | - | K1 | 값 | OK | 검사 대상 목록 누락(탐지 축) |
| COV5-03 | E.WRG.NORM.3 | - | K3 | 값 | OK | 빈 칸 '0' 처리 |
| AR-1@L288 | E.STR.GROUP.1 | - | K4 | 필드 | OK | 보충값이 최상위로 |
| AR-2@L289 | E.WRG.READ.1 | E.MIS.PART.1 | K3 | 값 | AMBIG | 끝 글자 '료' 누락. AMB-2 |
| AR-3@L290 | AUX.EVAL | - | K3 | 값 | OK | 표기 혼용 |
| AR-4@L291 | AUX.POST.NORM | - | K3 | 값 | OK | 괄호 제거 |
| AR-5@L292 | E.WRG.READ.1 | E.WRG.CTX.4 | K3 | 값 | OK | 한 글자 오독, 사업자번호 오검출 동반 |
| AR-6@L293 | P.WRG.READ.1 | - | K3 | 값 | OK | 흐림, 동일 오독으로 미탐 |
| AR-7@L294 | E.WRG.PICK.1 | - | K9 | 값 | OK | E2E-4.1과 동일 |
| AR-8@L295 | E.WRG.READ.2 | - | K3 | 값 | OK | 복합 소규모(성명 혼입·중괄호·대문자화) |
| AR-9@L296 | P.MIS.UNIT.1 | - | K1 | 열 | OK | 투여량 열 통째 빔, 두 판독 동일해 미탐 |
