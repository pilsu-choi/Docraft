# 잠재 케이스 270건 v3+v4 대응 검증

날짜: 2026-10-04 · 입력: `potential-cases.md`(270건), 기준: `2026-10-03-parse-extract-issue-taxonomy.md`(v3) + `taxonomy-v4-draft.md`(v4 추가 노드·K1~K10)

## 판정 요약

| 판정 | 건수 | 비고 |
|---|---:|---|
| OK | 241 | 정의·경계 규칙대로 명확히 들어감(AUX.* 원인 포함) |
| AMBIG | 20 | 노드는 있으나 두 노드 사이 경계 규칙이 없어 귀속이 갈림 |
| NEW | 6 | 맞는 노드 없음 — 모두 "보류해야 할 것을 확정·정상으로 출력"(과보류의 반대) |
| NA | 3 | 오류 유형이 아니라 기록 축(재현성·회귀) |

판정 기준: 노드 이름을 넓혀 읽지 않고, 정의·경계 규칙으로 하나가 정해질 때만 OK. 결과 형태가 두 개(예: "누락 또는 중복")로 적힌 케이스는 각 형태가 모두 명확한 노드를 가지면 OK로 두고 비고에 둘 다 적었다.

## 4(a) v4에 필요한 최소 추가

### 노드 추가 1건 (NEW 6건: 100, 123, 172, 200, 209, 237)

공통 원인: 원문이 읽기 어렵거나 가려졌거나 불완전한데, 시스템이 그 상태를 출력하지 않고 확정값·정상 상태로 낸다. v3에는 반대 방향인 과보류(`E.MIS.ABST`, `P.WRG.STATE.3`)만 있고, K8 "판독 가능 상태"의 이 방향을 받는 노드가 없다. `E.OVR.GEN.1`(빈칸을 값으로)은 원문에 값이 없는 경우라 "원문에 값은 있으나 읽을 수 없음"과 다르고, 완결성 표시 누락(100·200)은 값 자체가 맞아도 생긴다.

- **E.MIS.ABST의 짝으로 `E.WRG.HOLD` 보류 누락(과확신)**
  - `E.WRG.HOLD.1` 판독 불가·가림·훼손 구간을 추측해 확정값으로 출력 (123, 172, 209, 237; 17의 "추측값" 갈래)
  - `E.WRG.HOLD.2` 원문이 드러내는 결락·불완전(쪽 결번, 일부 쪽 없음)을 정상·완전으로 표시 (100, 200)
- 경계 규칙 추가: "보류가 필요한 원문을 확정값으로 내면 HOLD.1, 원문에 값 자체가 없는데 채우면 GEN.1. 파이프라인이 일부를 처리하지 못했는데 완료로 표시하면 `E.CON.DONE.4`, 원문 자체가 불완전한데 완전으로 표시하면 HOLD.2."
- Parse 쪽 대칭 노드(`P.WRG.STATE.4` 판독 불가를 문자로 추측)는 추가하지 않는다. 관측·잠재 케이스 모두 추측은 모델이 이미지를 보는 Extract 단계에서 생겼고, Parse의 추측은 `P.OVR.GEN.1`로 이미 표현된다.

### 경계 규칙 추가 (AMBIG 20건, 노드 추가 없음)

| 규칙 | 해당 | 내용 |
|---|---|---|
| B2 원문 문자 표현 보존 | 30, 31, 36, 37, 39 | 원문(텍스트층·인쇄)에 있는 전각·NFD·제로폭·하이픈 변종·합성 문자를 그대로 옮긴 것은 Parse 오류가 아니다. Parse가 다른 코드로 바꿨을 때만 `P.WRG.READ.5`. 이후 숫자 해석 실패는 `E.WRG.NORM.2`, 사전·마스터 비교 실패는 `AUX.REF`(조회 실패), 분할 실패는 `E.STR.COMPOSE.1` |
| B3 괄호·기호는 문자 | 42 | v4 `P.MIS.MARK.4` 예시에서 "괄호 표기·괄호 음수"를 뺀다. 괄호·△·▲는 문자이므로 빠지면 `P.MIS.CHAR.2`, 남았는데 부호로 해석 못 하면 `E.WRG.NORM.2`. MARK.4는 색·굵기·음영·밑줄처럼 문자 코드에 없는 서식만 |
| B4 표시 존재와 표기 관례 | 81 | 표시의 유무·위치를 잘못 보면 `P.WRG.STATE.1`/`E.WRG.READ.3`, 표시는 맞게 봤으나 관례(X=해당 없음, V=선택)를 잘못 해석하면 `E.WRG.NORM.1` |
| B5 위치·구조 노드는 비문자 표시에도 적용 | 82, 260 | `P.WRG.POS.1`의 "글자"를 "글자·표시"로 읽는다(체크가 옆 칸에 배정) |
| B6 허용된 계산 필드의 계산 오류 | 119, 265 | 계약이 계산을 허용한 필드(나이·일수)의 계산이 틀리면 정의된 변환 규칙의 결과 오류로 보고 `E.WRG.NORM.2`. 계약이 허용하지 않은 계산값을 낸 것은 기존대로 `E.OVR.GEN.2` |
| B7 문서 내 지시로 바뀐 값 | 124 | `E.WRG.READ.2`의 "의도치 않게"를 "원문과 다르게"로 읽고 `문서 내 지시 혼입` 원인 태그를 붙인다(값 변조). 없는 값을 만들면 `E.OVR.GEN.1` |
| B8 후처리 변환 오류 | 148 (55 일부) | `AUX.POST.NORM`을 "정규화·변환 오류(과정규화 포함)"로 정의를 넓힌다. 과정규화가 아닌 반올림·절사 순서 오류가 후처리에서 생기면 넣을 곳이 없다 |
| B9 레코드 종류 판정 | 67, 195, 202 | 레코드 종류(항목·소계·합계·쪽 합계·머리글) 판정 오류는 `E.STR.GROUP.1`. 계약이 그 종류를 제외하면 `E.OVR.SCOPE.1`, 계약이 포함하는데 빠지면 `E.MIS.TARGET.2`. 현재 ASSIGN.1·GROUP.1·SCOPE.1 중 어디인지 규칙이 없다 |
| B10 진술 출처 | 239 | 질문·인용·전언 등 진술 출처 차이는 `E.WRG.ATTR.1`(확실성)으로 본다. 질문 문장 영역 자체가 추출 범위 밖이면 `E.OVR.SCOPE.2` |
| B11 논리 쪽 순서 | 98 | 입력 쪽 순서가 뒤바뀐 것을 복원하지 못하면 `P.WRG.ORDER.1`의 "블록"에 쪽을 포함한다. 파이프라인이 순서를 바꾼 것은 `AUX.RUN` |
| B12 표 축 전치 | 63, 199 | 노드를 늘리지 않고 원인 `AUX.INPUT`(방향 처리 실패) + 결과 `E.WRG.ASSIGN.2`에 `오류 패턴` 축 값 "전치(행↔열)"를 추가한다 |

### 비판적 메모

- v4 `P.WRG.READ.5`는 "원문이 그 코드였음"과 "Parse가 그 코드로 바꿈"을 구분하지 않아 B2 없이는 Parse로 과귀속된다(위 5건).
- v4 `P.MIS.MARK.4`의 괄호 예시는 v3 `P.MIS.CHAR.2`(부호 누락)와 중복이다(B3).
- v4 `AUX.REF`는 유효했다: 28·30·39·151~154·197·249·269 원인이 여기로 명확히 갔다.
- v4 `E.CON.RANGE.4`는 탐지 사실만 다루므로, 200·267의 "경고 없이"는 `자동 탐지 여부` 축 미탐지로 기록해야 한다. 노드를 더 만들 필요 없음.
- `E.CON.PRIV.1`은 출력 안 노출만 덮는다. 121의 로그·OCR 원문 누출은 출력 밖이므로 이 분류 범위가 아니다(보안 사안으로 별도 처리).

## 4(b) K1~K10 × 단위 빈칸 점검

단위: 문자 / 표시 / 값 / 필드 / 레코드 / 열 / 표 / 페이지 / 문서 / 묶음. 아래는 v3+v4에 노드가 없는 칸만 적는다.

| 칸 | 비어도 되는가 | 이유 |
|---|---|---|
| K1·K2 × 열 (Extract) | 비어도 됨 | 열 전체 누락·추가는 셀 단위 `E.MIS.FIELD.2`·`E.WRG.ASSIGN.2`의 반복이며 `오류 패턴`(일괄)으로 표시한다 |
| K1 × 문서 | 비어도 됨 | 문서 누락은 항상 `P.MIS.AREA.1`(모든 쪽) 또는 `AUX.INPUT`(열기 실패)로 나타난다 |
| K2 × 표시 | 비어도 됨 | 없는 체크를 있다고 보는 것은 상태 반전 `P.WRG.STATE.1`(K8)로 같은 사건이다 |
| K2 × 페이지 | 비어도 됨 | 표지·빈 쪽 포함은 `AUX.SCHEMA`/`AUX.INPUT` 원인 + `E.OVR.SCOPE.2`·`E.OVR.GEN.1` 결과로 표현된다 |
| K3 × 필드·레코드·열·표·페이지 | 비어도 됨 | 내용은 값·문자에서만 바뀐다. 상위 단위의 내용 차이는 하위 단위 차이의 집계다. 문서 단위 "유형 바뀜"은 `AUX.SCHEMA` |
| K3·K4·K5 × 표시 | 규칙 필요(B5) | 표시는 위치·경계 노드를 가지지 않는다. 노드를 새로 만들기보다 POS·SPLIT의 대상에 표시를 포함한다 |
| K4 × 페이지·문서 | 비어도 됨 | 쪽이 다른 문서로 가면 `P.STR.DOC.*`, 문서가 다른 청구건으로 가면 `AUX.RUN`(다른 요청 결과 혼입) 또는 `E.WRG.CTX.4` |
| K5 × 묶음, K6·K7 × 묶음 | 비어도 됨 | 묶음은 최상위 단위라 경계·순서가 없다. 묶음 안 문서 간 관계는 `E.WRG.CTX.4`·`E.CON.RANGE.4` |
| K6 × 문자·필드·열·표·문서 | 비어도 됨 | 문자 순서 뒤바뀜은 `P.WRG.READ.1`/`P.WRG.ORDER.2`로 나타나고, 필드·열·문서 순서는 통상 계약상 의미가 없다. 계약이 순서를 정하면 `E.STR.ORDER.1`을 그 단위에 적용 |
| K6 × 페이지 | 규칙 필요(B11) | 입력 쪽 순서 복원 실패를 받을 노드가 명시되지 않음 |
| K8 × 값·문서 (과확신 방향) | **노드 필요** | 과보류(ABST)만 있고 반대 방향이 없다 → `E.WRG.HOLD.1/2` |
| K9 × Parse 전체 | 비어도 됨 | Parse는 후보를 고르지 않는다. 텍스트층·이미지 중 하나를 고르는 것은 `AUX.INPUT`(텍스트층·이미지 불일치) |
| K9 × 문서 | 비어도 됨 | 원본·정정본 중 선택은 `E.WRG.CTX.5`(관계) 또는 `E.WRG.PICK.1`로 이미 들어간다 |
| K10 × 표시 | 비어도 됨 | 표시는 출력 직렬화 시 값이 되므로 값 단위 K10으로 기록 |

## 4(c) K1~K10 완결성 반례 탐색

"정답 출력과 실제 출력의 차이"를 기준으로 K에 들어가지 않는 차이를 찾았다.

| 후보 반례 | 결론 |
|---|---|
| 같은 입력의 실행마다 다른 결과(141·142) | 반례 아님. 실행마다 차이는 K1~K10 중 하나이고, 흔들림은 `재현성` 축 |
| 결과 값은 같고 "원문/계산/참조" 출처 표시만 다름(224, 계산 허용 계약) | **약한 반례.** K8 목록(선택·확실성·시점·주체·판독 상태)에 "출처"가 없다. K8 정의에 "값의 출처(원문·계산·참조)"를 추가하면 해소되고, 노드는 기존 `E.OVR.GEN.2`로 충분 |
| 문서 완결성·처리 상태 플래그만 다름(100·200) | 반례 아님(K8 "판독 가능 상태"를 "처리 상태"로 넓혀 읽으면 들어감). 다만 노드가 없음 → HOLD |
| 동치 표기 차이(쉼표·날짜 형식, 156) | 반례 아님. 차이를 세기 전에 평가 계약이 동치류를 정해야 하는 선행 조건(`AUX.EVAL`) |
| 출력 밖 누출(로그·근거 원문, 121 일부) | 틀 밖. "출력"의 차이가 아니므로 K로 덮을 대상이 아님 |
| 응답 지연·콜백 순서 | 틀 밖(내용 차이 아님) |
| 정밀도 과장("약 6주"→6주) | 반례 아님. 한정어 소실은 K8 확실성 또는 K3 일부 손실 |
| 레코드 수만 다름 | 반례 아님. K1·K2·K5 중 하나로 분해됨 |

결론: K1~K10은 차이 "종류"로는 빠짐이 없다. 남은 빈틈은 K8 정의의 "출처" 누락(정의 문구 보강)과, K8 과확신 방향 노드 부재(HOLD 추가)다.

## 전 행 대응표

| 번호 | 원인ID | 후속ID | K | 단위 | 판정 | 비고 |
|---|---|---|---|---|---|---|
| 1 | AUX.INPUT | P.WRG.READ.1 | K3 | 값 | OK | 텍스트층·이미지 불일치(v4). 결과는 값 바뀜 형태 |
| 2 | P.WRG.READ.5 | E.MIS.FIELD.2 | K3 | 문자 | OK | 글꼴 대응 깨짐(v4) |
| 3 | AUX.INPUT | P.MIS.AREA.2 | K1 | 표 | OK | 텍스트층·이미지 혼합 페이지 일부 미처리(v4) |
| 4 | AUX.INPUT | P.MIS.AREA.1, P.CON.DONE.1 | K1, K10 | 문서 | OK | 디코딩 실패를 성공 처리(v4) |
| 5 | AUX.INPUT | P.MIS.AREA.1 | K1 | 페이지 | OK | 프레임 선택 누락 |
| 6 | AUX.INPUT | P.CON.DONE.1 | K10 | 문서 | OK | 열기 실패를 성공 처리(v4) |
| 7 | AUX.INPUT | P.MIS.AREA.1 | K1 | 문서 | OK | |
| 8 | AUX.INPUT | E.OVR.GEN.1 | K2 | 문서 | OK | |
| 9 | AUX.INPUT | P.MIS.CHAR.1 | K1 | 페이지 | OK | 방향 처리 실패 |
| 10 | P.WRG.READ.1 | — | K3 | 문자 | OK | 발생 조건: 저해상도 |
| 11 | P.MIS.CHAR.2 | E.WRG.NORM.2 | K3 | 값 | OK | 발생 조건: 압축 |
| 12 | P.WRG.POS.1 | E.WRG.ASSIGN.2 | K4 | 레코드 | OK | |
| 13 | P.MIS.UNIT.2 | E.WRG.ASSIGN.2 | K1→K4 | 열 | OK | 오류 패턴: 일괄 밀림 |
| 14 | P.WRG.TYPE.1 | E.OVR.SCOPE.2 | K2 | 값 | OK | |
| 15 | P.MIS.CHAR.1 | — | K1 | 값 | OK | "-" 인식 갈래는 P.OVR.FALSE.1 |
| 16 | P.STR.LINK.1 | E.WRG.ASSIGN.2 | K5 | 페이지 | OK | |
| 17 | AUX.INPUT | P.MIS.CHAR.1 | K1 | 값 | OK | 리사이즈 문자 소실. 추측값 갈래는 E.WRG.HOLD.1(신규) |
| 18 | AUX.INPUT | P.MIS.AREA.1 | K1 | 페이지 | OK | |
| 19 | AUX.INPUT | P.WRG.READ.1 | K3 | 페이지 | OK | |
| 20 | E.OVR.GEN.1 | — | K2 | 페이지 | OK | |
| 21 | E.OVR.GEN.1 | — | K2 | 문서 | OK | 스키마 예시값 유출 |
| 22 | P.OVR.FALSE.2 | — | K2 | 문자 | OK | 뒷면 비침(v4) |
| 23 | P.OVR.FALSE.1 | — | K2 | 문자 | OK | |
| 24 | AUX.INPUT | P.WRG.TYPE.2 | K3 | 표 | OK | 기울기 보정 실패 |
| 25 | AUX.INPUT | P.MIS.CHAR.1, E.MIS.FIELD.1 | K1 | 페이지 | OK | |
| 26 | P.WRG.READ.1 | — | K3 | 문자 | OK | |
| 27 | P.WRG.READ.1 | — | K3 | 문자 | OK | |
| 28 | P.WRG.READ.4 | AUX.REF→E.WRG.NORM.1 | K3 | 값 | OK | 공백 삽입(v4) |
| 29 | E.STR.SPLIT.2 | — | K5 | 필드 | OK | |
| 30 | P.WRG.READ.5 / AUX.REF | E.MIS.FIELD.2 | K3 | 문자 | AMBIG | B2: 원문이 NFD면 Parse 오류 아님 |
| 31 | P.WRG.READ.5 / E.WRG.NORM.2 | E.MIS.FIELD.2 | K3 | 값 | AMBIG | B2 |
| 32 | P.MIS.CHAR.1 | — | K1 | 값 | OK | 오독 갈래는 P.WRG.READ.1 |
| 33 | E.WRG.NORM.4 | — | K3 | 값 | OK | |
| 34 | P.WRG.READ.2 | — | K3 | 값 | OK | 위첨자 기호 오인식 |
| 35 | P.WRG.READ.2 | — | K3 | 값 | OK | |
| 36 | P.WRG.READ.5 / E.WRG.NORM.2 | E.STR.COMPOSE.1, E.WRG.NORM.3 | K3 | 문자 | AMBIG | B2 |
| 37 | P.WRG.READ.5 / AUX.REF | — | K3 | 문자 | AMBIG | B2 |
| 38 | P.WRG.POS.1 | E.MIS.PART.1 | K4 | 값 | OK | |
| 39 | P.WRG.READ.5 / AUX.REF | E.MIS.FIELD.2 | K3 | 문자 | AMBIG | B2 |
| 40 | P.OVR.FALSE.1 | — | K2 | 문자 | OK | 괘선을 문자로 |
| 41 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 42 | P.MIS.MARK.4 / P.MIS.CHAR.2 / E.WRG.NORM.2 | — | K3 | 값 | AMBIG | B3: v4 MARK.4 괄호 예시가 CHAR.2와 중복 |
| 43 | P.MIS.MARK.4 | E.WRG.NORM.2 | K1→K3 | 값 | OK | 빨간 글씨(v4). △▲는 B3 |
| 44 | E.WRG.NORM.3 | — | K3 | 값 | OK | |
| 45 | E.WRG.CTX.1 | E.WRG.NORM.2 | K7→K3 | 열 | OK | |
| 46 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 47 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 48 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 49 | P.WRG.READ.1 | E.CON.RANGE.2 | K3, K10 | 값 | OK | 자동 이월 갈래는 E.WRG.NORM.2 |
| 50 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 51 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 52 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 53 | E.CON.RANGE.2 | — | K10 | 값 | OK | |
| 54 | E.WRG.NORM.4 | — | K3 | 값 | OK | 정보 감소 변환 |
| 55 | E.WRG.NORM.2 | — | K3 | 값 | OK | 후처리에서 생기면 B8 |
| 56 | E.WRG.NORM.2 | — | K3 | 열 | OK | |
| 57 | E.OVR.GEN.2 | — | K2 | 값 | OK | |
| 58 | E.WRG.NORM.2 | E.CON.SCHEMA.2 | K3, K10 | 값 | OK | |
| 59 | P.WRG.POS.1 | E.WRG.ASSIGN.2 | K4 | 열 | OK | |
| 60 | P.STR.REL.1 | E.MIS.FIELD.2 | K7→K1 | 레코드 | OK | 상속 여부는 평가 계약 |
| 61 | P.STR.REL.1 | E.MIS.FIELD.2, E.OVR.DUP.2 | K7 | 열 | OK | |
| 62 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7→K4 | 열 | OK | |
| 63 | AUX.INPUT | E.WRG.ASSIGN.2 | K4 | 표 | AMBIG | B12: 전치 패턴 축 값 없음 |
| 64 | P.STR.SPLIT.2 | E.STR.SPLIT.2 | K5 | 레코드 | OK | |
| 65 | P.STR.LINK.2 | E.STR.SPLIT.2 | K5 | 레코드 | OK | |
| 66 | E.OVR.SCOPE.1 | — | K2 | 레코드 | OK | |
| 67 | E.STR.GROUP.1 / E.WRG.ASSIGN.1 | E.MIS.TARGET.2 | K4 | 레코드 | AMBIG | B9 |
| 68 | P.MIS.UNIT.2 | E.WRG.ASSIGN.2 | K1→K4 | 레코드 | OK | 오류 패턴: 일괄 밀림 |
| 69 | P.STR.HIER.3 | — | K7 | 표 | OK | 중첩 표(v4) |
| 70 | P.WRG.ORDER.3 | E.STR.SPLIT.1 | K6 | 표 | OK | |
| 71 | P.STR.LINK.2 | E.WRG.CTX.3 | K7 | 표 | OK | |
| 72 | P.STR.SPLIT.1 | E.STR.SPLIT.1 | K5 | 레코드 | OK | |
| 73 | P.STR.SPLIT.1 | — | K5 | 표 | OK | |
| 74 | P.STR.LINK.1 | E.STR.GROUP.1 | K5 | 표 | OK | |
| 75 | P.STR.REL.3 | E.WRG.ASSIGN.1 | K7→K4 | 필드 | OK | |
| 76 | P.STR.REL.3 | E.WRG.ASSIGN.1 | K7→K4 | 필드 | OK | 라벨 문자열을 값 필드에 |
| 77 | E.WRG.PICK.1 | — | K9 | 필드 | OK | 재현성: 간헐 |
| 78 | E.WRG.CTX.1 | E.MIS.FIELD.2 | K7→K1 | 필드 | OK | |
| 79 | E.MIS.FIELD.2 | — | K1 | 필드 | OK | 다른 필드 귀속 갈래는 E.WRG.ASSIGN.1 |
| 80 | P.STR.REL.3 | E.WRG.ASSIGN.1 | K7→K4 | 필드 | OK | |
| 81 | E.WRG.READ.3 / E.WRG.NORM.1 | — | K8 | 필드 | AMBIG | B4 |
| 82 | P.WRG.POS.1? | E.WRG.READ.3 | K4 | 필드 | AMBIG | B5: POS 정의가 글자 한정 |
| 83 | P.WRG.TYPE.2 | E.OVR.SCOPE.1 | K2 | 필드 | OK | 선택됨 갈래는 P.WRG.STATE.1 |
| 84 | P.WRG.READ.1 | — | K3 | 값 | OK | 일부 누락 갈래 P.MIS.CHAR.1 |
| 85 | E.OVR.SCOPE.2 | — | K2 | 필드 | OK | |
| 86 | P.WRG.READ.1 | — | K3 | 값 | OK | 발생 조건: 손글씨 |
| 87 | P.MIS.MARK.2 | E.WRG.CTX.5 | K1→K7 | 값 | OK | 두 값 연결 갈래는 E.STR.COMPOSE.2 |
| 88 | P.MIS.MARK.2 | P.WRG.READ.1 | K1→K3 | 값 | OK | |
| 89 | P.MIS.MARK.2 | E.OVR.SCOPE.3 | K1→K2 | 레코드 | OK | |
| 90 | P.MIS.MARK.4 | E.OVR.GEN.1 | K1→K2 | 필드 | OK | 음영(v4) |
| 91 | P.MIS.MARK.4 | E.WRG.PICK.1 | K1→K9 | 필드 | OK | 굵기(v4) |
| 92 | P.WRG.ORDER.3 | — | K6 | 페이지 | OK | |
| 93 | P.WRG.ORDER.2 | E.OVR.SCOPE.2 | K2 | 값 | OK | |
| 94 | P.WRG.ORDER.2 | — | K3 | 값 | OK | |
| 95 | P.STR.DOC.1 | E.WRG.CTX.4 | K5→K7 | 묶음 | OK | |
| 96 | E.OVR.DUP.3 | — | K2 | 묶음 | OK | |
| 97 | E.WRG.CTX.5 | E.OVR.SCOPE.3 | K7 | 묶음 | OK | |
| 98 | P.WRG.ORDER.1? | P.STR.LINK.2, E.STR.ORDER.1 | K6 | 묶음 | AMBIG | B11: 입력 쪽 순서 복원 노드 불명 |
| 99 | E.WRG.CTX.4 | E.STR.SPLIT.3 | K7 | 묶음 | OK | |
| 100 | (원문 결락) | E.WRG.HOLD.2(신규) | K8 | 문서 | NEW | 완결성 상태 미표시, CON.DONE.4는 파이프라인 미처리만 |
| 101 | AUX.SCHEMA | E.OVR.SCOPE.2 | K2 | 페이지 | OK | |
| 102 | AUX.SCHEMA | E.MIS.FIELD.2 | K1 | 문서 | OK | |
| 103 | E.OVR.DUP.3 | — | K2 | 페이지 | OK | |
| 104 | P.STR.DOC.1 | E.WRG.CTX.4 | K5 | 페이지 | OK | |
| 105 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 106 | E.WRG.ASSIGN.1 | — | K4 | 필드 | OK | |
| 107 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 108 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 109 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 110 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 111 | E.WRG.ATTR.1 | — | K8 | 값 | OK | |
| 112 | E.WRG.ATTR.1 | — | K8 | 레코드 | OK | |
| 113 | E.WRG.ATTR.2 | — | K8 | 레코드 | OK | |
| 114 | E.WRG.PICK.1 | — | K9 | 값 | OK | |
| 115 | E.WRG.NORM.3 | — | K3 | 값 | OK | |
| 116 | E.WRG.CTX.2 | — | K7 | 값 | OK | 참조 문구 = 상속 연결 |
| 117 | E.OVR.GEN.2 | — | K2 | 값 | OK | |
| 118 | E.OVR.GEN.2 | — | K2 | 값 | OK | 후처리면 AUX.POST.ALTER 원인 |
| 119 | E.WRG.NORM.2? | — | K3 | 값 | AMBIG | B6: 허용 계산 필드 오류 노드 불명 |
| 120 | E.OVR.GEN.1 | — | K2 | 값 | OK | |
| 121 | E.CON.PRIV.1 | — | K10 | 필드 | OK | 로그 누출은 범위 밖 |
| 122 | P.MIS.UNIT.2 | E.WRG.ASSIGN.2 | K1→K4 | 열 | OK | |
| 123 | E.WRG.HOLD.1(신규) | — | K8 | 값 | NEW | 가림 영역 추측 확정 |
| 124 | E.WRG.READ.2? | — | K3 | 문서 | AMBIG | B7: 지시 혼입 태그 |
| 125 | AUX.SCHEMA | E.WRG.PICK.1 | K9 | 문서 | OK | 지시 혼입 태그 |
| 126 | E.CON.DONE.3 | E.MIS.FIELD.1 | K10→K1 | 표 | OK | |
| 127 | E.CON.DONE.1 | E.CON.DONE.4 | K10 | 문서 | OK | |
| 128 | E.CON.SCHEMA.1 | E.MIS.FIELD.2 | K10 | 필드 | OK | |
| 129 | E.CON.SCHEMA.2 | — | K10 | 값 | OK | |
| 130 | E.CON.SCHEMA.3 | — | K10 | 표 | OK | |
| 131 | E.CON.DONE.4 | E.MIS.FIELD.1 | K10→K1 | 문서 | OK | |
| 132 | AUX.RUN | E.OVR.DUP.3 | K2 | 문서 | OK | 덮어쓰기 갈래 E.MIS.FIELD.1 |
| 133 | P.WRG.READ.5 | — | K3 | 문자 | OK | 인코딩(v4) |
| 134 | E.CON.DONE.1 | — | K10 | 문서 | OK | |
| 135 | E.CON.EVID.3 | — | K10 | 값 | OK | |
| 136 | AUX.INPUT | E.CON.EVID.3 | K10 | 페이지 | OK | 좌표 역변환 |
| 137 | AUX.INPUT | E.CON.EVID.3 | K10 | 페이지 | OK | |
| 138 | E.CON.EVID.3 | — | K10 | 값 | OK | |
| 139 | E.CON.EVID.1 | — | K10 | 값 | OK | |
| 140 | E.CON.EVID.3 | — | K10 | 페이지 | OK | |
| 141 | — | — | — | 문서 | NA | 재현성 축 |
| 142 | — | — | — | 문서 | NA | 재현성 축 |
| 143 | — | — | — | 묶음 | NA | 회귀(결과는 개별 유형) |
| 144 | AUX.POST.PICK | E.WRG.ASSIGN.1 | K9→K4 | 값 | OK | |
| 145 | AUX.POST.NORM | E.WRG.NORM.4 | K3 | 값 | OK | |
| 146 | AUX.POST.ALTER | E.MIS.FIELD.1 | K1 | 레코드 | OK | |
| 147 | AUX.POST.VALID | E.OVR.GEN.2 | K2 | 값 | OK | |
| 148 | AUX.POST.? | E.WRG.NORM.2 | K3 | 값 | AMBIG | B8: 후처리 일반 변환 오류 없음 |
| 149 | AUX.POST.ALTER | E.MIS.FIELD.2 | K1 | 값 | OK | |
| 150 | AUX.POST.ALTER | E.MIS.FIELD.1 | K1 | 레코드 | OK | |
| 151 | AUX.REF | E.MIS.FIELD.2 | K1 | 값 | OK | 참조 버전 |
| 152 | AUX.REF | E.WRG.NORM.1 | K3 | 필드 | OK | 잘못된 항목 매칭 |
| 153 | AUX.REF | AUX.POST.ALTER→E.MIS.FIELD.2 | K1 | 값 | OK | |
| 154 | AUX.REF | E.MIS.FIELD.2 | K1 | 필드 | OK | 조회 실패 |
| 155 | AUX.EVAL | — | — | 값 | OK | 출력 정상 |
| 156 | AUX.EVAL | — | — | 값 | OK | |
| 157 | AUX.EVAL | — | — | 표 | OK | |
| 158 | AUX.EVAL | — | — | 필드 | OK | |
| 159 | AUX.EVAL | — | — | 값 | OK | |
| 160 | AUX.SCHEMA | E.WRG.ASSIGN.2 | K4 | 표 | OK | 구서식 규칙 적용 |
| 161 | AUX.SCHEMA | E.MIS.FIELD.2 | K1 | 문서 | OK | |
| 162 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 163 | E.OVR.DUP.1 | — | K2 | 문서 | OK | 번역 채택 갈래 E.WRG.PICK.1 |
| 164 | E.CON.DONE.4 | E.MIS.FIELD.1 | K10→K1 | 문서 | OK | 발생 조건: 긴 입력 |
| 165 | AUX.RUN | E.OVR.DUP.1, E.MIS.FIELD.1 | K2/K1 | 레코드 | OK | 입력 분할 경계 |
| 166 | P.WRG.TYPE.1 | E.OVR.SCOPE.2 | K2 | 문서 | OK | |
| 167 | E.WRG.PICK.2 | — | K9 | 필드 | OK | |
| 168 | AUX.INPUT | P.OVR.FALSE.2 | K2 | 문서 | OK | 숨은 시트 = 보이지 않는 층 |
| 169 | P.WRG.READ.3 | E.OVR.SCOPE.2 | K2 | 값 | OK | |
| 170 | P.WRG.TYPE.2 | E.OVR.SCOPE.2 | K2 | 필드 | OK | |
| 171 | AUX.INPUT | P.MIS.MARK.4 | K1 | 값 | OK | 제출 자체가 흑백이면 정답 정의는 평가 계약 |
| 172 | E.WRG.HOLD.1(신규) | — | K8 | 값 | NEW | 판독 불가를 문맥 보정해 확정 |
| 173 | E.CON.EVID.3 | — | K10 | 값 | OK | |
| 174 | P.STR.HIER.2 | E.WRG.NORM.1 | K7 | 레코드 | OK | |
| 175 | P.STR.REL.2 | E.WRG.ASSIGN.2 | K7→K4 | 열 | OK | |
| 176 | AUX.SCHEMA | E.OVR.GEN.2, E.MIS.FIELD.2 | K2/K1 | 열 | OK | |
| 177 | E.OVR.GEN.2 | — | K2 | 필드 | OK | 합산 = 계산값 |
| 178 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 179 | P.WRG.STATE.1 | E.WRG.READ.3 | K8 | 필드 | OK | |
| 180 | E.WRG.ASSIGN.3 | — | K4 | 값 | OK | |
| 181 | E.STR.SPLIT.1 | E.MIS.TARGET.2 | K5 | 레코드 | OK | |
| 182 | E.MIS.FIELD.1 | E.OVR.GEN.1 | K1/K2 | 레코드 | OK | |
| 183 | E.OVR.GEN.2 | — | K2 | 필드 | OK | 다른 금액 갈래 E.WRG.PICK.1 |
| 184 | E.WRG.ASSIGN.1 | — | K4 | 필드 | OK | |
| 185 | P.STR.DOC.1 | E.STR.SPLIT.1 | K5 | 문서 | OK | |
| 186 | E.WRG.NORM.2 | — | K3 | 값 | OK | |
| 187 | E.OVR.SCOPE.2 | — | K2 | 필드 | OK | |
| 188 | AUX.SCHEMA | E.MIS.FIELD.2 | K1 | 문서 | OK | |
| 189 | P.MIS.MARK.1 | E.MIS.FIELD.2 | K1 | 필드 | OK | 자보→건보 갈래 E.WRG.READ.3 |
| 190 | E.CON.DONE.4 | E.MIS.FIELD.1, E.OVR.DUP.1 | K10/K1/K2 | 표 | OK | |
| 191 | E.WRG.CTX.2 | E.MIS.FIELD.2 | K7 | 열 | OK | |
| 192 | P.STR.SPLIT.2 | E.STR.COMPOSE.1 | K5 | 레코드 | OK | |
| 193 | E.WRG.CTX.1 | E.WRG.ASSIGN.2 | K7→K4 | 열 | OK | |
| 194 | P.MIS.CHAR.2 | — | K3 | 값 | OK | 반올림 갈래 E.WRG.NORM.4 |
| 195 | E.STR.GROUP.1 / E.WRG.ASSIGN.1 | — | K4 | 레코드 | AMBIG | B9 |
| 196 | E.WRG.NORM.1 | — | K3 | 열 | OK | |
| 197 | AUX.REF | E.MIS.FIELD.2 | K1 | 값 | OK | 잘린 원문 보존은 정상 |
| 198 | P.MIS.CHAR.2 | E.WRG.NORM.2 | K3 | 레코드 | OK | |
| 199 | AUX.INPUT | E.WRG.ASSIGN.2 | K4 | 표 | AMBIG | B12 |
| 200 | (원문 결락) | E.WRG.HOLD.2(신규) | K8 | 묶음 | NEW | RANGE.4 미탐지는 축 |
| 201 | AUX.POST.ALTER | E.MIS.FIELD.1 | K1 | 레코드 | OK | |
| 202 | E.STR.GROUP.1 / E.WRG.ASSIGN.1 | — | K4 | 레코드 | AMBIG | B9 |
| 203 | P.STR.LINK.2 | E.WRG.CTX.3 | K7 | 표 | OK | |
| 204 | P.STR.LINK.1 | E.WRG.ASSIGN.2 | K5 | 표 | OK | |
| 205 | E.WRG.ASSIGN.2 | — | K4 | 열 | OK | |
| 206 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 207 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 208 | E.WRG.ASSIGN.3 | — | K4 | 값 | OK | |
| 209 | E.WRG.HOLD.1(신규) | — | K8 | 값 | NEW | 퇴색 구간 추측 |
| 210 | AUX.INPUT | P.MIS.CHAR.1, E.OVR.DUP.1 | K1/K2 | 문서 | OK | |
| 211 | E.STR.SPLIT.3 | E.WRG.CTX.4 | K5 | 레코드 | OK | |
| 212 | E.OVR.SCOPE.3 | — | K2 | 레코드 | OK | |
| 213 | E.WRG.CTX.4 | E.MIS.TARGET.1 | K7/K1 | 표 | OK | |
| 214 | E.WRG.ASSIGN.1 | — | K4 | 필드 | OK | |
| 215 | E.MIS.FIELD.2 | E.OVR.GEN.2 | K1/K2 | 값 | OK | |
| 216 | E.OVR.SCOPE.2 | E.WRG.ASSIGN.1 | K2 | 필드 | OK | |
| 217 | E.OVR.GEN.2 | — | K2 | 값 | OK | |
| 218 | E.STR.ORDER.1 | — | K6 | 레코드 | OK | v4 |
| 219 | E.WRG.ATTR.1 | — | K8 | 필드 | OK | |
| 220 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 221 | E.MIS.PART.2 | — | K3 | 값 | OK | 6일 갈래 E.WRG.NORM.2 |
| 222 | E.WRG.ASSIGN.1 | — | K4 | 필드 | OK | |
| 223 | P.WRG.READ.1 | — | K3 | 값 | OK | |
| 224 | E.OVR.GEN.2 | — | K2 | 값 | OK | 출처 표시 차이는 K8 정의 보강 |
| 225 | E.WRG.NORM.4 | — | K3 | 값 | OK | |
| 226 | E.WRG.ASSIGN.1 | — | K4 | 레코드 | OK | |
| 227 | E.WRG.ASSIGN.1 | — | K4 | 필드 | OK | |
| 228 | E.WRG.NORM.4 | — | K3 | 값 | OK | |
| 229 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 230 | P.MIS.CHAR.2 | E.STR.ARRAY.1 | K3/K6 | 레코드 | OK | |
| 231 | E.WRG.ATTR.2 | — | K8 | 레코드 | OK | |
| 232 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 233 | E.WRG.ATTR.1 | — | K8 | 값 | OK | |
| 234 | E.WRG.ASSIGN.1 | — | K4 | 값 | OK | |
| 235 | E.WRG.ATTR.2 | — | K8 | 값 | OK | |
| 236 | E.WRG.ATTR.2 | — | K8 | 필드 | OK | 예정일 필드가 있으면 ASSIGN.3 |
| 237 | E.WRG.HOLD.1(신규) | — | K8 | 값 | NEW | 판독 불가 구간 문맥 생성 |
| 238 | P.STR.LINK.2 | E.MIS.FIELD.2, E.WRG.CTX.3 | K5 | 페이지 | OK | |
| 239 | E.WRG.ATTR.1? / E.OVR.SCOPE.2 | — | K8 | 필드 | AMBIG | B10 |
| 240 | E.WRG.ATTR.1 | — | K8 | 값 | OK | 전언 = 확실성 |
| 241 | P.MIS.CHAR.1 | E.MIS.FIELD.2 | K1 | 값 | OK | 오역 갈래 E.WRG.NORM.4 |
| 242 | E.WRG.NORM.1 | — | K3 | 값 | OK | 소실 갈래 E.MIS.PART.1 |
| 243 | E.STR.ARRAY.1 | — | K6 | 레코드 | OK | |
| 244 | P.MIS.MARK.1 | E.MIS.FIELD.2 | K1 | 필드 | OK | 첫 항목 갈래 E.OVR.GEN.1 |
| 245 | E.MIS.FIELD.1 | — | K1 | 레코드 | OK | 주·부 소실 갈래 E.MIS.FIELD.2 |
| 246 | E.WRG.NORM.4 | — | K3 | 값 | OK | |
| 247 | E.WRG.NORM.1 | — | K3 | 필드 | OK | |
| 248 | E.STR.SPLIT.3 | E.MIS.FIELD.2 | K5 | 레코드 | OK | |
| 249 | E.WRG.NORM.1 | AUX.REF 조회 결과 오매칭 | K3 | 값 | OK | |
| 250 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 251 | E.WRG.ASSIGN.1 | — | K4 | 필드 | OK | |
| 252 | AUX.SCHEMA | E.MIS.FIELD.2, E.WRG.ATTR.2 | K1/K8 | 문서 | OK | |
| 253 | E.WRG.ATTR.2 | — | K8 | 문서 | OK | |
| 254 | E.WRG.ASSIGN.3 | E.WRG.NORM.2 | K4/K3 | 값 | OK | |
| 255 | E.OVR.GEN.2 | — | K2 | 값 | OK | |
| 256 | E.OVR.GEN.1 | — | K2 | 값 | OK | |
| 257 | E.STR.ARRAY.1 | — | K6 | 레코드 | OK | |
| 258 | E.STR.SPLIT.3 | — | K5 | 레코드 | OK | |
| 259 | E.WRG.NORM.1 | — | K3 | 문서 | OK | |
| 260 | P.WRG.POS.1? | E.MIS.PART.1 | K4 | 레코드 | AMBIG | B5 |
| 261 | E.WRG.NORM.1 | — | K3 | 필드 | OK | |
| 262 | E.STR.COMPOSE.2 | — | K5 | 값 | OK | v4 혼입 |
| 263 | E.WRG.PICK.1 | — | K9 | 필드 | OK | |
| 264 | E.MIS.FIELD.2 | E.WRG.NORM.1 | K1/K3 | 필드 | OK | |
| 265 | E.WRG.NORM.2? | — | K3 | 값 | AMBIG | B6 |
| 266 | E.WRG.ASSIGN.3 | — | K4 | 필드 | OK | |
| 267 | E.CON.RANGE.4 | E.WRG.CTX.4 | K10 | 묶음 | OK | v4. 경고 없음은 탐지 축 |
| 268 | E.WRG.CTX.4 | E.CON.RANGE.4 | K7 | 묶음 | OK | |
| 269 | AUX.REF | E.MIS.ABST.2 | K8 | 값 | OK | 보정까지 하면 AUX.POST.ALTER |
| 270 | AUX.SCHEMA | P.STR.DOC.2 | K5 | 문서 | OK | |
