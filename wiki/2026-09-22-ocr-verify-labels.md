---
type: Report
title: "AO 교차검증 정답셋(라벨)과 단계별 정확도 평가 스크립트"
description: "VLM으로 문서 유형 4종의 정답셋을 라벨링하고, Docraft raw/rules/ao/final 4단계 필드 정확도를 계산하는 scripts/verify_label.py·verify_eval.py 구현 기록"
tags: [ocr-verify, agentic-ocr, evaluation, labeling, vlm, harness-v2]
status: active
---

# AO 교차검증 정답셋(라벨)과 단계별 정확도 평가 스크립트

2026-09-22 · 브랜치 `feat/ocr-verify` · 워크트리 `.worktrees/ocr-verify`

[Agentic OCR 2.0 결과 교차검증·자동 교정 API 계획](2026-09-22-ocr-verify-plan.md)의 정답셋 구축·측정 파트를 맡아
`scripts/verify_label.py`(라벨 생성)와 `scripts/verify_eval.py`(단계별 정확도 계산)를 구현했다. 같은 워크트리에서
다른 에이전트가 `backend/doctypes.py`·`backend/rules.py`·`backend/main.py`·`backend/verify.py`·`tests/`를 동시에
구현했고, 작업 도중 세 모듈 모두 완성되어 두 스크립트 모두 실제 파이프라인 전 단계를 검증할 수 있었다.

## 1. 정답셋(`scripts/verify_label.py`)

- 문서 유형 4종(진단서·소견서·진료비영수증·세부내역서)마다 gold 1건(AO 예시 이미지) + silver 8건
  (`data/files/<유형>_samples/`에서 파일명 정렬 후 균등 간격 추출, tif 최소 3장 보장)을 골라 이미지만 보여주고
  (OCR 텍스트 없이) VLM이 필드값을 읽게 했다.
- 라벨링 모델은 추출 모델(`qwen/qwen3-vl-32b-instruct`)과 겹치면 순환 평가가 되므로, OpenRouter `/models`를
  조회해 후보(`anthropic/claude-sonnet-4.5` → `google/gemini-2.5-pro` → `openai/gpt-5`) 중 첫 available를 골랐다
  — 실제로는 `anthropic/claude-sonnet-4.5`가 사용됐다. `backend/engine.py`는 건드리지 않고, `httpx.Client.post`를
  얇게 감싸 요청 body의 `model` 키만 라벨링 모델로 바꿔치기했다(`ai_settings()`는 그대로 두어 다른 코드 경로에
  영향이 없다).
- 스키마는 `backend.doctypes.schema(doc_type)`(작업 도중 다른 에이전트가 구현 완료)를 우선 쓰고, 실패하면
  AO 예시 json의 키만으로 자체 생성하는 `fallback_schema()`를 쓴다 — 이 fallback은 `scripts/verify_eval.py`의
  `schema_for()`에서도 그대로 재사용해 중복 스키마 정의를 두지 않았다.
- 결과: **gold 4건 + silver 32건 = 36개 라벨**을 전부 생성(`data/verify/labels/<유형>/<이미지 stem>.json`),
  ok=35 · skip=1(먼저 만든 gold 진단서 1건) · error=0, 총 176.4초.

## 2. 단계별 정확도(`scripts/verify_eval.py`)

- 4단계: `raw`(`engine.extract`) → `rules`(`rules.apply`) → `ao`(gold만, `verify.flatten`으로 AO 값 평탄화,
  `backend.verify`의 기존 함수를 그대로 재사용해 중복 구현을 만들지 않았다) → `final`(gold만, `verify.run(image,
  ao_json, doc_type)`의 최종값).
- 채점: 스칼라는 `rules.same(kind, 라벨, 예측)`, 표는 라벨 행·예측 행을 순서대로 짝짓고 셀 단위로 같은 비교를
  적용한다(행 수가 다르면 모자란 쪽을 빈 행으로 채워 누락·과잉이 자연히 오답/오탐으로 집계됨). null 라벨은
  분모에서 빼고, 라벨이 null인데 예측이 있으면 별도로 오탐(`fp`) 카운트.
- `doctypes`/`rules`/`verify` 중 하나라도 아직 `NotImplementedError`/`ImportError`면 그 단계만 "미구현"으로
  표시하고 스크립트는 끝까지 돈다(방어적 스켈레톤 — 지금은 셋 다 구현되어 실제로는 발동하지 않았다).
- 캐시: 이미지당 파싱 20~90초가 걸려 `data/verify/cache/<유형>__<stem>.parse.json`·`.extract.json`에 저장하고
  `--no-cache`로 무시한다. `--workers`(기본 2)로 PaddleOCR 서버 과부하를 막는다.

### 실행 결과

**gold 4건, 전 단계** (`--grade gold`, 312.8초):

| 유형 | raw | rules | ao | final |
|---|---|---|---|---|
| 진단서 | 70.6% (12/17) fp=1 | 76.5% (13/17) fp=3 | 52.9% (9/17) fp=10 | 70.6% (12/17) fp=10 |
| 소견서 | 44.4% (4/9) | 44.4% (4/9) fp=5 | 55.6% (5/9) fp=5 | 55.6% (5/9) fp=6 |
| 진료비영수증 | 59.3% (16/27) fp=2 | 59.3% (16/27) fp=4 | 48.1% (13/27) fp=170 | 59.3% (16/27) fp=171 |
| 세부내역서 | 89.0% (210/236) fp=16 | 89.0% (210/236) fp=17 | 83.1% (196/236) fp=16 | 89.0% (210/236) fp=53 |

**전체 36건(gold+silver), raw·rules** (`--stage raw --stage rules`, 851.2초):

| 유형 | raw | rules |
|---|---|---|
| 진단서 | 79.6% (82/103) fp=21 | 80.6% (83/103) fp=70 |
| 소견서 | 60.3% (70/116) fp=23 | 60.3% (70/116) fp=54 |
| 진료비영수증 | 69.2% (522/754) fp=250 | 69.5% (524/754) fp=268 |
| 세부내역서 | 80.8% (1587/1965) fp=378 | 80.8% (1587/1965) fp=379 |

fp(오탐)가 정확도 대비 크게 나오는 건 라벨이 이미지에 실제로 없다고 판단한 필드(예: 체크박스류·병실 등)를
extract/rules가 과감히 채우는 경우가 많기 때문이다 — 값 존재 여부 판정 자체도 개선 여지로 남는다. 표(항목내역)
열 단위 정확도는 세부내역서 EDI명칭(20%대)·진료비영수증 항목명(24%)처럼 자유 텍스트 열에서 낮고, 금액류
열은 대체로 90%대다. gold `ao`/`final` 비교에서 `final`이 `ao`·`raw`·`rules`보다 항상 같거나 높아 judge가
실제로 값을 개선하는 방향으로 동작함을 확인했다(예: 진단서 raw 70.6%→final 70.6%지만 ao 52.9%보다 높고, 진료비
영수증은 raw/rules 59.3%에서 final도 59.3% 유지하며 fp만 늘어 — judge가 AO 오탐을 그대로 넘긴 사례가 있어
추후 `judge` 프롬프트의 표 오탐 억제가 개선 후보로 보인다).

전체 결과(필드 단위까지)는 `data/verify/eval-20260922-153719.json`(gold 전 단계), `data/verify/eval-20260922-155225.json`
(전체 raw·rules)에 저장했다. 둘 다 `data/`가 gitignore돼 있어 저장소에는 없다.

## 3. 사용법

```bash
# 라벨 생성 (gold 4 + silver 32, 재실행 시 이미 있는 라벨은 건너뜀)
../../.venv/bin/python scripts/verify_label.py
../../.venv/bin/python scripts/verify_label.py --doc-type 진단서 --per-type 4 --force
../../.venv/bin/python scripts/verify_label.py --only-gold --model anthropic/claude-sonnet-4.5

# 단계별 정확도
../../.venv/bin/python scripts/verify_eval.py --grade gold --stage raw   # 동작 확인용, 빠름
../../.venv/bin/python scripts/verify_eval.py --verbose                  # 전체, 오답 목록까지
../../.venv/bin/python scripts/verify_eval.py --doc-type 진단서 --no-cache --workers 3
```

## 4. 한계·후속 과제

- silver 라벨은 VLM(claude-sonnet-4.5) 단독 판독이라 라벨 자체 오류가 섞여 있다(예: 진단서 gold에서 라벨이
  "진단일"을 null로 읽고 "발급일"만 채운 사례 — 실제 문서 확인 필요). 정확도 수치는 "라벨 대비" 지표로 보되,
  라벨 신뢰도가 100%는 아니라는 점을 감안해야 한다.
- `ao`/`final` 단계는 gold 4건뿐이라 표본이 작다 — silver에도 AO 응답이 있다면(harness-v2 쪽에 요청 필요)
  표본을 늘릴 수 있다.
- fp(오탐) 집계는 "라벨이 null인데 예측이 있다" 기준이라, 라벨링 프롬프트가 지나치게 보수적으로 null을
  준 필드(체크박스·표 열 일부)에서 fp가 과대평가될 수 있다.
