---
okf_version: "0.2"
type: reference
title: "Parse·Extract 이슈 도감 (노드별 시각 예시)"
description: "이슈 유형 트리 v4의 Depth 4 노드 111개와 보조 원인 10개마다 원문(정답)과 출력을 나란히 그린 예시 페이지. 관측 사례를 우선 쓰고, 없으면 합성 생성기 메커니즘이나 추정 예시로 채웠다. 51개 노드에 합성 이미지를 붙였고, 개인정보 보호를 위해 실제 고객 문서 대신 합성 데이터만 썼다."
tags: [taxonomy, parse, extract, example, visualization]
status: active
---

날짜: 2026-10-08 (Asia/Seoul)

브랜치: harness-v2·Docraft `docs/issue-taxonomy-gallery` (각 `dev` 기준)

워크트리: 각 저장소 `.worktrees/issue-taxonomy-gallery`

기준 원본: 상위 `mirae-assets/wiki`

## 내용

[Parse와 Extract 이슈 유형 계층 분류](2026-10-03-parse-extract-issue-taxonomy.md)의 노드를 글 대신 예시로 확인하기 위한 페이지다. 노드마다 원문(정답)과 출력을 나란히 놓고, 틀어진 칸을 색으로 표시한다(틀림·빠짐·더해짐·자리 바뀜·구조·보류).

- 페이지: https://claude.ai/artifact/J2bQnURQJm3wApYDJyasKj (비공개, 소유자만 열람)
- 같은 페이지 파일: [evidence/2026-10-08-issue-taxonomy-gallery/issue-taxonomy-gallery.html](evidence/2026-10-08-issue-taxonomy-gallery/issue-taxonomy-gallery.html)
- 예시 데이터: [issue-examples.json](evidence/2026-10-08-issue-taxonomy-gallery/issue-examples.json), 형식: [schema.md](evidence/2026-10-08-issue-taxonomy-gallery/schema.md)

## 예시 출처 (검수 후)

| 구분 | 건수 | 뜻 |
|---|---:|---|
| 관측 | 82 | 관측 기록(`evidence/2026-10-04-issue-taxonomy-v4/map-obs-*`, 10/05~08 wiki)의 실제 현상을 가상값으로 재현 |
| 합성 | 35 | 관측은 없고 `synthetics/generator/edge_cases.yaml` 메커니즘이 그 노드를 태깅함 |
| 추정 | 4 | 관측·합성 모두 없음. 예상 예시 |
| 합계 | 121 | Depth 4 노드 111 + 보조 원인 10 |

**개인정보:** 이미지는 모두 합성 생성기로 만든 가상 문서이며 실제 고객 문서는 쓰지 않았다. 표의 이름·주민번호·기관명·환자번호도 가상값이다. 페이지 머리에 같은 내용을 명시했다.

## 합성 이미지

- 51개 노드에 이슈 이미지, 그중 47개에 같은 문서의 이슈 없는 기준 이미지를 붙였다(98장, 5.7MB, 가로 720px 이하).
- 출처는 사용자 눈 검수를 통과한 eye-review 런(`synthetics/runs/20261005-eye-review-v1`~`20261006-eye-review-v8-fold`)을 우선했다. 노드별 런·메커니즘·설명은 [img-index.json](evidence/2026-10-08-issue-taxonomy-gallery/img-index.json).
- 70개 노드는 이미지가 없다. 27개는 합성 메커니즘이 없고(계약 오류·보조 원인 등), 43개는 태그는 있으나 이슈가 눈에 보이지 않아 뺐다.
- 대부분 전체 쪽 이미지라 휴대폰에서는 확대해서 봐야 한다.

## 표시 검수

처음 만든 카드에서 근거가 설계 메모인데 관측으로 표시한 경우, 관측이 있는데 합성으로 표시한 경우가 확인돼 121건 전부 근거 문서와 다시 대조했다. 판정 기준: 관측 = map-obs 대응 사례 중 실데이터·정답지·AWS 결과(EC·WO·WB 설계 시나리오와 결정대기 메모 제외), 합성 = 관측 없고 생성기 메커니즘 태그 있음, 추정 = 둘 다 없음.

| 결과 | 건수 |
|---|---:|
| 그대로 | 69 |
| 관측·합성·추정 표시 변경 | 17 |
| 예시 교체(다른 실제 사례로) | 13 |
| 예시 수정(사례 현상에 맞춤) | 22 |

변경 내역: [audit-P.md](evidence/2026-10-08-issue-taxonomy-gallery/audit-P.md), [audit-E.md](evidence/2026-10-08-issue-taxonomy-gallery/audit-E.md). 페이지 재생성: `python3 build.py`(out-P·out-E·img-index를 합침, 근거 폴더의 build.py·template.html).

## 검증

- 트리의 Depth 4 ID 111개와 예시 ID를 대조해 빠짐·중복·여분 0건.
- 주민번호 형식 문자열 0건.
- 400px 폭 렌더링에서 스크립트 오류 0, 가로 넘침 없음(Playwright 1회).

## 한계

- 예시는 서브에이전트가 근거 문서를 읽고 만든 것이다. 노드 귀속이 애매한 관측 사례(AMBIG)를 고른 카드가 있을 수 있다. 분류 경계 규칙과 다르게 보이면 데이터 JSON을 고치고 페이지를 다시 만든다.
- 검수도 서브에이전트가 했다. 카드가 근거와 다르게 보이면 `issue-examples.json`을 고치고 다시 만든다.

## 수정 이력 (2026-10-08)

- `E.CON.SCHEMA.1`: 지어낸 소견서 예시(근거 RC-6은 설계 메모)를 실제 사례로 교체했다. Docraft가 오타 키 `상환액초과금`을 내보내 하네스 요청 `상한액초과금`이 무시된 사례다(AWS 10/07 로그, Docraft `64679a4`). 필드 키에 색 표시가 있으면 `[object Object]`로 깨지던 렌더링도 고쳤다.
- **당장 대상 아님 19건**(사용자 판단): `P.MIS.MARK.4`, `P.WRG.READ.3`·`.4`·`.5`, `P.WRG.TYPE.2`, `P.STR.HIER.1`, `P.STR.DOC.1`·`.2`, `E.MIS.TARGET.1`, `E.WRG.READ.2`, `E.WRG.CTX.3`, `E.WRG.PICK.2`, `E.WRG.HOLD.2`, `E.OVR.DUP.3`, `E.OVR.SCOPE.1`, `E.CON.SCHEMA.2`, `E.CON.RANGE.1`, `E.CON.DONE.4`, `AUX.EVAL`. 분류에서는 지우지 않는다(미발견 사례도 들어갈 칸 유지). 페이지에서 흐리게 표시하고 숨기기 버튼을 둔다.
- 관측·합성 표시 오류를 확인해 121건 검수를 진행했다(위 "표시 검수"). 합성 이미지 51개 노드를 붙였다.
