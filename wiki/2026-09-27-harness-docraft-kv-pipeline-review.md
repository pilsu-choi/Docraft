---
type: Analysis
title: "Harness와 Docraft의 key-value 추출 흐름 점검"
description: "사람의 문서 판독 단계에 대응해 두 저장소의 구현, 운영 경로, 평가 근거와 한계를 정리한 정적 점검"
tags: [harness, docraft, extraction, grounding, review]
status: stable
---

# Harness와 Docraft의 key-value 추출 흐름 점검

- 날짜: 2026-09-27
- 브랜치: `docs/kv-pipeline-review`
- 워크트리: `Docraft/.worktrees/kv-pipeline-review`
- 범위: Docraft `dev`(`c98d059`), harness-v2 로컬 `main`(원격 `dev` 추적)의 코드·README·기존 평가 기록을 읽은 정적 점검. 이번 작업에서 새 문서 이미지나 서비스 실측은 수행하지 않았다.

## 판단

의료 문서 key-value 자동화의 핵심 단계는 구현돼 있다. Docraft는 파싱·스키마 추출·근거 좌표·일반 프로젝트의 검토 작업을 맡고, Harness는 상위 Agentic OCR 결과에 규칙·마스터·선택적 Docraft 판독을 결합해 최종 등급과 값을 정한다. 다만 두 경로를 합친 운영 흐름이 모든 문서를 원문에서 자동 분류·추출·근거 표시·사람 승인까지 일관되게 처리한다고 보기는 어렵다.

| 사람의 단계 | 구현 근거 | 현재 경계 |
|---|---|---|
| 문서 읽기·배치 파악 | [Docraft 파서](../backend/parsers.py), [추출 엔진](../backend/engine.py)에서 OCR 블록·표·줄 좌표와 페이지 이미지를 사용 | 스캔 문서는 Paddle 서비스 설정에 의존 |
| 문서 유형·key 결정 | [7종 스키마](../backend/doctypes.py), [Harness 처리 흐름](../../harness-v2/src/mlife_harness/pipeline/runner.py) | Docraft `/api/read`는 `doc_type`을 입력받고, 상위 AO 분류 또는 Harness 재분류가 필요 |
| 값 선택·정규화 | [Docraft 추출](../backend/engine.py), [의료 규칙](../backend/rules.py), [Harness 정규화](../../harness-v2/src/mlife_harness/normalizer/value_fix.py) | 일반 프로젝트와 의료 AO 검증 경로의 규칙 깊이가 다름 |
| 검증·최종 채택 | [Harness 규칙·증거 수집](../../harness-v2/src/mlife_harness/pipeline/runner.py), [Docraft 교차검증](../backend/verify.py) | Harness 운영 경로는 Docraft `/api/verify`의 Judge를 호출하지 않고 `/api/read`를 필요할 때만 사용 |
| 원문 근거·사람 검토 | [Docraft 근거 연결](../backend/engine.py), [수정·승인 API](../backend/main.py) | `/api/read` 응답은 값만 반환하므로 Harness 판정에 Docraft 근거 좌표가 전달되지 않음 |

## 평가 근거와 해석

- [Harness 2026-09-27 평가](../../harness-v2/wiki/2026-09-27-교정값-value-반영-Docraft-AO규칙-이식.md)의 AWS 21건은 AO 84.4%에서 최종 88.7%로 올랐다. 표본과 평가 방식이 제한돼 있으며, 205건 전체 이미지 경로 평가는 아직 기록되지 않았다.
- [Docraft 자동 검토 평가](2026-09-24-auto-review.md)의 57건은 영수증·세부내역서 `/api/verify` 단독 경로 실측이다. 자동 통과 칸 정확도 99.11%·99.71%는 Harness 통합 운영 경로의 정확도로 옮겨 읽으면 안 된다.
- [엣지 카탈로그 점검](2026-09-25-ocr-edge-catalog-audit.md)은 102개 중 지원 1, 부분 52, 미지원 49로 판정했다. 이 수치는 특정 예외 처리 흐름의 구현 범위이지 전체 OCR 정확도가 아니다.
- Docraft 근거 신뢰도는 [문자열·행·위치 대조](../backend/engine.py)에 기반한 휴리스틱이다. 원문에 같은 글자가 있다는 사실만으로 key와 value의 의미상 연결이 맞음을 보장하지 않는다.

## 개선 우선순위

1. Harness가 쓰는 `/api/read`에 값별 페이지·bbox·원문 텍스트를 전달해 최종 판정까지 근거를 이어 붙인다.
2. Harness의 `unresolved`·`ambiguous` 등급을 사람이 실제로 검토·수정·승인하는 경로와 연결하고, 반영 결과를 추적한다.
3. 의료 7종 전체를 대상으로 동일 문서 집합의 AO→Harness→Docraft 통합 정확도, 자동 확정 오답률, 검토량, 처리 시간을 측정한다. 특히 공통 오독과 행 짝짓기 실패를 별도 집계한다.
