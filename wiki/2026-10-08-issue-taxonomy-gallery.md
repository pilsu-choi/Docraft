---
okf_version: "0.2"
type: reference
title: "Parse·Extract 이슈 도감 (노드별 시각 예시)"
description: "이슈 유형 트리 v4의 Depth 4 노드 111개와 보조 원인 10개마다 원문(정답)과 출력을 나란히 그린 예시 페이지. 관측 사례를 우선 쓰고, 없으면 합성 생성기 메커니즘이나 추정 예시로 채웠다."
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

## 예시 출처

| 구분 | 건수 | 뜻 |
|---|---:|---|
| 관측 | 74 | 관측 기록(`evidence/2026-10-04-issue-taxonomy-v4/map-obs-*`, 의료비 적용 프로파일)의 실제 현상을 재현 |
| 합성 | 38 | 관측은 없고 `synthetics/generator/edge_cases.yaml` 메커니즘이 그 노드를 태깅함 |
| 추정 | 9 | 관측·합성 모두 없음. 예상 예시 |
| 합계 | 121 | Depth 4 노드 111 + 보조 원인 10 |

이름·주민번호·기관명·환자번호는 가상값으로 바꿨다. 금액·항목명 같은 서식 값은 관측 그대로 둔 것이 있다. 각 카드의 `근거`에 사례 ID와 출처 문서를 적었다.

## 검증

- 트리의 Depth 4 ID 111개와 예시 ID를 대조해 빠짐·중복·여분 0건.
- 주민번호 형식 문자열 0건.
- 400px 폭 렌더링에서 스크립트 오류 0, 가로 넘침 없음(Playwright 1회).

## 한계

- 예시는 서브에이전트가 근거 문서를 읽고 만든 것이다. 노드 귀속이 애매한 관측 사례(AMBIG)를 고른 카드가 있을 수 있다. 분류 경계 규칙과 다르게 보이면 데이터 JSON을 고치고 페이지를 다시 만든다.
- `E.OVR.SCOPE.3`는 합성 메커니즘 태그를 따랐다. 일반의약품 합산 예시라 `E.OVR.GEN.2`와 경계가 가깝다.
