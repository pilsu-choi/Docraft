---
type: Implementation Log
title: "추출 페이지 단위 분할 호출"
description: "긴 문서에서 뒤쪽 페이지가 예산 초과로 조용히 버려지던 문제를 페이지 경계를 지키는 다중 provider 호출과 스키마 기반 병합으로 해결한 기록"
tags: [backend, extraction, ai-provider, chunking]
generated: {by: claude-code/claude-sonnet-5, at: 2026-09-22}
status: stable
---

# 추출 페이지 단위 분할 호출

2026-09-22 · 브랜치 `fix/extract-page-chunking` · 워크트리 `.worktrees/extract-page-chunking`

## 문제

`backend/engine.py`의 `extract(schema, blocks)`는 모든 블록 텍스트를 `_block_lines(blocks, budget=40000)`로 한 번에 이어 붙여 provider에 보냈다. 이 함수는 예산(기본 40000자)을 넘으면 그 지점부터 **블록을 통째로 버리고** `logger.warning`만 남겼다. 페이지가 많은 문서(표가 큰 진료비 내역서 등)는 뒤쪽 페이지가 provider 입력에서 아예 빠져 추출 결과에 나타나지 않는데도, 로그를 보지 않으면 알 수 없었다.

## 설계

### 1. 페이지 단위 분할 (`_page_chunks`)

블록을 `page` 키로 묶어 페이지 경계를 지키면서, 각 청크의 직렬화된 텍스트가 문자 예산 안에 들도록 나눈다.

- 문서가 예산 안에 들면(일반적인 경우) 청크는 하나뿐이고 동작은 예전과 같다.
- 페이지를 하나씩 채우다가 다음 페이지를 더하면 예산을 넘길 때 새 청크를 시작한다. 즉 한 페이지가 중간에 잘리는 일은 없다.
- 페이지 하나만으로 예산을 넘으면 그 페이지 안에서 블록 경계로 다시 나눈다.
- 블록 하나가 그 자체로 예산을 넘으면(표 하나가 거대한 HTML 블록인 경우 등) 그 블록만 단독 청크가 되고, 직렬화 단계(`_chunk_text`)에서 예산 길이로 잘리며 `logger.warning`을 남긴다. 이 경우만 잘림이 남는다.

예산은 `ai_settings()["chunk_chars"]`로 읽으며 기본값 40000, 환경변수 `EXTRACT_CHUNK_CHARS`로 조정한다(`backend/config.py`).

### 2. 청크별 provider 호출

청크마다 동일한 system prompt로 `_provider()`를 호출한다. 청크가 2개 이상이면 system prompt에 "This is part N of M of the document, covering page(s) X; return null/empty for fields not present in this part."를 덧붙여 모델이 빈 청크의 필드를 억지로 채우지 않게 한다. 청크가 하나면 이 문구는 붙지 않아(단일 호출 문서는 기존과 문자 그대로 동일한 요청) 회귀가 없다.

### 3. 스키마 기반 병합 (`_merge_chunk_results`)

청크별 결과를 스키마를 따라 재귀적으로 합친다.

- object: 각 property key를 스키마 순서대로 순회하며 재귀 병합.
- array: 청크 순서대로 이어 붙인다. 단, 앞 청크의 마지막 항목과 다음 청크의 첫 항목이 완전히 같으면(청크 경계에 걸친 표 행이 양쪽에 중복 포함된 경우) 한 번만 제거한다. 같은 청크 안에서 실제로 반복되는 값은 건드리지 않는다.
- scalar: 문서 순서상 처음 나오는 null이 아닌 값을 채택한다.

병합 뒤에 `_drop_null_optionals`를 한 번 적용하고, grounding은 전체 블록에 대해 **한 번만** `_grounding_tree(merged, [(block, _block_rows(block)) for block in blocks])`로 계산한다. grounding은 병합된 최종 결과와 원본 블록 전체를 대조하므로 청크 경계와 무관하게 정확하다.

## 한계

- 병합은 스키마의 `properties`에 있는 키만 채운다. provider가 스키마에 없는 키를 얹어 보내면 무시된다(원래도 스키마를 따르도록 지시하므로 실질적인 변화는 아니다).
- array 중복 제거는 "이전 청크의 마지막 항목 == 다음 청크의 첫 항목"일 때만 동작한다. 중간에 다른 항목이 끼거나 순서가 바뀐 중복은 잡지 못한다.
- 청크 수만큼 provider 호출이 늘어나므로 매우 긴 문서는 추출 시간이 길어진다.
- 블록 하나가 예산을 넘는 극단적인 경우만 텍스트가 잘리고 경고를 남긴다.

## 변경 파일

- `backend/config.py` — `ai_settings()`에 `chunk_chars`(환경변수 `EXTRACT_CHUNK_CHARS`, 기본 40000) 추가
- `backend/engine.py` — `_block_lines`를 삭제하고 `_page_chunks`(페이지 경계 분할)·`_chunk_text`(직렬화 및 단일 블록 잘림)·`_page_range`(로그·프롬프트용 페이지 범위 표기)·`_merge_chunk_results`(스키마 기반 병합) 추가. `extract()`가 청크마다 `_provider()`를 호출하고 병합한 뒤 `_drop_null_optionals`·`_grounding_tree`를 한 번만 적용하도록 재구성
- `tests/test_ai_provider.py` — `FakeClient`에 청크별로 다른 응답을 순서대로 돌려주는 `responses` 목록 지원 추가(`install_responses`). 예전 "블록 통째로 버림" 테스트를 삭제하고, 단일 청크 문서가 여전히 호출 1회인지, 여러 페이지 문서가 페이지 경계에서 올바르게 나뉘는지, 배열 이어붙임(경계 중복 제거)·스칼라 first-non-null 병합이 맞는지, 한 페이지가 예산을 넘을 때 블록 경계로 나뉘는지, 블록 하나가 예산을 넘을 때만 잘리고 경고가 남는지 검증하는 테스트 5개로 교체
- `README.md` — "03 데이터 추출" 절에 긴 문서 분할·병합 규칙 한 줄 추가

## 테스트 결과

```
python -m pytest tests -q --ignore=tests/ui_smoke.py --ignore=tests/ui_preview_layout.py --ignore=tests/ui_project_workspace.py
61 passed
```
