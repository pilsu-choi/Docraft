# audit-P (변경 카드)

| id | status 이전→이후 | 판정 | 이유 | 근거 사례ID |
|---|---|---|---|---|
| P.MIS.AREA.1 | observed→observed | 예시교체 | 사례 현상(실패 그룹 제외 병합으로 일부 쪽만 복원)과 예시 일치시킴 | AR-1(D5) |
| P.MIS.AREA.2 | synthetic→observed | status변경 | 관측(RP-04, 합계 인쇄값이 파싱 텍스트에서 빠짐)이 있어 synthetic→observed | RP-04 |
| P.MIS.CHAR.1 | observed→observed | 예시교체 | PF-2는 판독 차이 복합이라 문자열 일부 누락(칸 잘림)이 명확한 PF-5로 교체 | PF-5 |
| P.WRG.READ.4 | observed→observed | 예시교체 | 지어낸 단어 대신 실제 관측 문자열(진찰료→진 찰 로)로 교체 | LG-1 |
| P.WRG.READ.5 | synthetic→observed | status변경 | 관측(PE-6 [UNK] 문자 손실)이 READ.5 후속으로 대응돼 synthetic→observed | PE-6 |
| P.WRG.POS.1 | observed→observed | 예시수정 | 사례 현상(진찰료 3,342 7,798 0 이 한 줄로 나와 셀 경계에 걸침)대로 수정 | TR-5 |
| P.WRG.ORDER.1 | observed→observed | 예시교체 | WO-05는 지시서 예시라 관측 아님; 실제 관측 RK-3(행 밀림)으로 교체 | RK-3 |
| P.WRG.ORDER.3 | observed→observed | 예시수정 | 지어낸 역방향 예시를 실제 관측(기본항목→기본 환자 항목)으로 수정 | TF-6 |
| P.WRG.TYPE.1 | observed→synthetic | status변경 | 근거 문서 "G3 보조"가 실재 사례로 대응되지 않음; 관측 없고 distractor_values 메커니즘이 태깅 | - |
| P.WRG.STATE.2 | observed→synthetic | status변경 | TP-1은 설계상 위험 기록(typed proof)·TP-2는 잠재라 관측 아님; occlusion 메커니즘이 태깅 | TP-1 |
| P.STR.SPLIT.1 | observed→observed | 예시교체 | 실제 관측(한 셀에 두 행 금액 병합)에 맞춰 진료비영수증 예시로 교체 | TR-7 |
| P.STR.SPLIT.2 | synthetic→observed | status변경 | 관측(RT-3 병합 셀 분리)이 SPLIT.2에 대응돼 synthetic→observed | RT-3 |
| P.STR.REL.1 | observed→observed | 예시교체 | TE-02는 의미 연결 불명이라 병합 범위(colspan 누락) 관측인 VX-2로 교체 | VX-2 |
| P.STR.REL.3 | observed→synthetic | status변경 | G1-a는 READ.1(먼 0 오독)로 대응돼 REL.3 관측 없음; cell_displacement 메커니즘이 태깅 | G1-a |
| P.STR.REL.4 | synthetic→observed | status변경 | 관측(RP-01 체크표시→Y/N 연결 누락)이 REL.4 후속으로 대응돼 synthetic→observed | RP-01 |
| P.STR.HIER.2 | assumed→synthetic | status변경 | edge_cases.yaml non_data_rows 메커니즘이 P.STR.HIER.2를 태깅(관측은 없음) | - |
| P.STR.LINK.2 | observed→observed | 예시수정 | 사례 현상(병합 없음·조각 식별 키 없음)에 맞게 캡션·문구 수정 | RC-5#1 |
