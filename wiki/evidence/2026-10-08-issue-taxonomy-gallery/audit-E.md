# audit-E (변경 카드)

| id | status 이전→이후 | audit | 이유 | 근거 사례ID |
|---|---|---|---|---|
| E.MIS.TARGET.1 | synthetic→observed | status변경 | 긴 문서의 뒤쪽 쪽이 입력 한도 초과로 버려진 관측 있음(합성 아님) | PC-1 |
| E.MIS.PART.1 | observed→observed | 예시교체 | 사례 AR-2(재활및물리치료료→끝 료 누락) 현상대로 교체; 이전 예시는 PX-8(가운뎃점 소실)을 섞은 것 | AR-2 |
| E.MIS.ABST.2 | observed→observed | 예시수정 | CORR-09 현상은 사고발생일자 규칙이 진단일·수술일자 칸을 붙잡아 맞은 값이 미확정이 된 것 | CORR-09 |
| E.WRG.READ.1 | observed→observed | 예시수정 | G4-b 방향 반대: 정답 FD001(숫자 0)을 FDOO1(알파벳 O)로 읽음 | G4-b |
| E.WRG.READ.2 | synthetic→observed | status변경 | 합성→관측 E2E-1.7(원내코드 S·B가 5·8로 바뀜); digit_sequence 예시 폐기 | E2E-1.7 |
| E.WRG.CTX.1 | observed→observed | 예시수정 | XD-10은 공단 값이 본인 칸에 들어간 것; 이전은 머리글 이름만 바꿔 표시 | XD-10 |
| E.WRG.NORM.1 | observed→observed | 예시수정 | IT-5 현상은 고상급종합병원 표기 변형을 정규화 못함; 이전 '상급종합'은 지어낸 값 | IT-5 |
| E.WRG.NORM.2 | observed→observed | 예시수정 | PR-괄호음수 원문은 금액 (3,000); 환급이라는 설명은 근거 없음 | PR-괄호음수 |
| E.WRG.NORM.4 | observed→observed | 예시교체 | G9는 ASSIGN.1/NORM.1 사례; NORM.4 대응 사례 RR-6(보철·교정료→보철교정료)로 교체 | RR-6 |
| E.WRG.PICK.2 | synthetic→observed | status변경 | 합성→관측 KV-10(4자 이상 부분 포함을 일치로 보고 확정); 예시 교체 | KV-10 |
| E.OVR.GEN.1 | observed→observed | 예시수정 | 출력 날짜가 같은 표의 다른 칸 값이면 DUP.2 경계; 원문에 없는 날짜로 변경 | SR-3 |
| E.OVR.DUP.1 | observed→observed | 예시수정 | KV-2는 영수증 주사료 행 중복 | KV-2 |
| E.OVR.DUP.2 | observed→observed | 예시수정 | LT-6은 항목칸 EDI명칭 복사; 카드 현상(원내코드 칸 복제)은 G4-a | G4-a |
| E.OVR.DUP.3 | synthetic→synthetic | 예시수정 | 합성 출처를 메커니즘 id로 표기, 문서 유형 정정 | document_copy |
| E.OVR.SCOPE.1 | observed→observed | 예시수정 | RE-머리글행 대신 '01.진찰료' 구분 제목 줄이 실제 나온 G5-a로 출처 교체 | G5-a |
| E.OVR.SCOPE.2 | observed→observed | 예시수정 | RE-의사명조각 현상은 의사명에 서식 문구 조각(또는인 등)이 섞임 | RE-의사명조각 |
| E.OVR.SCOPE.3 | synthetic→synthetic | 예시교체 | 경계 규칙상 GEN.2와 가까운 일반의약품 합산 대신 취소·구버전 행 포함 예시로 교체 | revision_candidates |
| E.STR.SPLIT.1 | observed→observed | 예시수정 | KCD-04는 진단서 한 칸의 복수 코드; 코드 누락 혼합 제거 | KCD-04 |
| E.STR.SPLIT.2 | synthetic→observed | status변경 | 합성→관측 KV-13(표 블록 중간에서 청크를 나눔) | KV-13 |
| E.STR.SPLIT.3 | observed→observed | 예시교체 | CORR-07은 재판독-행 짝짓기 실패; 같은 이름 행 금액 뒤섞임 V59-02로 교체 | V59-02 |
| E.STR.GROUP.1 | observed→observed | 예시교체 | PR-출력그룹위치 현상은 영수증 필드가 서식 그룹 대신 최상위에 놓임 | PR-출력그룹위치 |
| E.STR.ARRAY.1 | observed→observed | 예시교체 | RC-4#1은 머리글 칸 수와 행 칸 수 불일치; 수술명·수술일 예시는 근거 없음 | RC-4#1 |
| E.CON.SCHEMA.3 | observed→observed | 예시수정 | ST-3 단일값 위반은 진단서 입원 여러 번 쉼표 나열 | ST-3 |
| E.CON.RANGE.1 | observed→observed | 예시수정 | FL-1은 약제비영수증 기대인데 약제영수증으로 나옴 | FL-1 |
| E.CON.RANGE.2 | observed→observed | 예시수정 | RE-등록번호형식은 한글·날짜로 시작하는 등록번호 형식 위반 | RE-등록번호형식 |
| E.CON.RANGE.4 | observed→synthetic | status변경 | RE-합계불일치는 영수증 내부 합계식(RANGE.3)이라 문서 간 제약 관측 없음; 합성 bundle_source_mismatch | bundle_source_mismatch |
| AUX.INPUT | assumed→observed | status변경 | EC-P02(예상)는 관측 아님; 관측 XD-9(옆으로 누운 합계 쪽 방향 정규화 놓침)으로 교체, 결과 TARGET.2 | XD-9 |
| AUX.POST.ALTER | observed→observed | 예시수정 | 출처 경로 정정, caption 의 → 노드ID 제거 | BM-2 |
| AUX.POST.EVID | assumed→observed | status변경 | G6 는 근거 없는 카드 내용; 관측 PX-1(근거 좌표 없는 재판독값 자동 채택)로 교체. 후속 노드는 맵에 없어 READ.1 로 둠 | PX-1 |
| AUX.POST.NORM | observed→observed | 예시교체 | G1-e 는 AUX.EVAL 로 대응; AUX.POST.NORM→PART.2 대응 V59-15(음수 부호 삭제)로 교체 | V59-15 |
| AUX.POST.PICK | assumed→observed | status변경 | CLS-9 는 근거 없는 카드 내용; 관측 IT-11(맞은 Docraft 값을 버림)로 교체 | IT-11 |
| AUX.POST.VALID | observed→observed | 예시수정 | 출처 경로 정정, caption 의 → 노드ID 제거 | G1-a |
| AUX.REF | observed→observed | 예시수정 | BM-4 정답은 약제비영수증, 출력은 서식코드 Y000701200 | BM-4 |
| AUX.RUN | observed→observed | 예시수정 | IT-2 는 영수증, 끝수처리 행 누락 | IT-2 |
| AUX.SCHEMA | assumed→observed | status변경 | 추정 카드 대신 관측 RM-9(통합 8열 스키마에서 두 칸 뒤바뀜), 결과 ASSIGN.2 | RM-9 |

공통: 출처 경로 golden26-misextraction-analysis → golden-harness-misextraction-analysis 등 map-obs 표기를 원 출처 문서로 정정(내용 일치 카드는 audit ok).
