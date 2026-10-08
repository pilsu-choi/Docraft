# 이슈 예시 데이터 형식 (JSON)

파일 하나 = JSON 배열. 원소 하나 = Depth 4 노드 하나(AUX 는 보조 유형 하나).

```json
{
  "id": "E.WRG.ASSIGN.2",
  "name": "다른 행·열에 배정",
  "status": "observed",            // observed(관측) | synthetic(합성 생성기 메커니즘으로 재현) | assumed(추정 예시)
  "doc": "진료비세부내역서",          // 예시 문서 유형
  "source": "G3-b · 2026-10-02-golden26-misextraction-analysis.md",  // observed: 사례ID·출처 파일 / synthetic: edge_cases.yaml 메커니즘명 / assumed: ""
  "caption": "공단부담금 값이 본인부담금 열에 들어갔다",   // 한 문장, 쉬운 말, 40자 내외
  "truth":  Panel,                 // 원문(정답)
  "output": Panel                  // 실제 출력(오류)
}
```

## Panel (4종 중 하나)

- 표: `{"kind":"table","cols":["항목","본인부담금","공단부담금"],"rows":[[Cell,Cell,Cell], ...]}`
- 필드(Extract JSON 출력에 주로): `{"kind":"fields","items":[["진료일",Cell],["발행일",Cell]]}`
- 글(Parse 텍스트, 서술문): `{"kind":"text","lines":[[Seg,Seg], [Seg]]}`  — 한 줄 = Seg 배열
- 쪽·문서(페이지·문서 단위 이슈): `{"kind":"pages","items":[{"t":"1쪽","sub":"영수증","m":"miss"}, ...]}`

## Cell / Seg

문자열 `"12,000"` 또는 객체 `{"t":"12,800","m":"wrong","cs":2,"note":"8→3"}`
- `m`(표시): `wrong`(틀림) `miss`(빠짐) `extra`(더해짐) `move`(자리 바뀜) `struct`(합침·나눔·연결·순서 등 구조) `hold`(보류·판독불가 표시)
  - 정답 패널: 출력에서 잘못될 원문 부분에 같은 m 을 단다(빠질 것은 miss 등). 출력 패널: 오류 부분에 m.
- `cs`: colspan(병합 셀), 생략 가능. `note`: 짧은 주석(선택).
- 빈칸은 `""`. 비문자 표시는 기호로(`✓`, `■`, `[도장]`, `~~취소선~~` 대신 `{"t":"12,000","note":"취소선"}`).

## 작성 규칙

1. 노드 하나에 예시 하나. 정답·출력은 최소 크기(표 2~4행, 필드 2~4개)로, 차이만 한눈에 보이게.
2. Parse 노드(P.*)의 output 은 OCR·parse 결과 모양(text/table), Extract 노드(E.*)의 output 은 스키마 출력 모양(fields/table).
3. 관측 사례가 있으면 그 현상을 그대로 재현하되 **이름·주민번호·병원명·환자번호 등 개인·기관 식별값은 가상값**(김가온, 가나의원, 12345 등)으로 바꾼다. 금액·항목명 같은 서식 값은 그대로 써도 된다.
4. 관측 사례가 없으면 synthetics/generator/edge_cases.yaml 메커니즘이 그 노드를 태깅하면 synthetic, 아니면 assumed 로 의료비 문서 예시를 만든다.
5. caption 은 내부 용어 없이 쉬운 말.
6. 결과는 python3 -c "import json;json.load(open(F))" 로 검증.
