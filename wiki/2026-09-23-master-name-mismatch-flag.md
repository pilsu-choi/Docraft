---
okf_version: "0.2"
type: Analysis
title: "마스터 명칭 유사도 검토 필요 플래그 — 임계값 스윕 결과와 보류 결정"
description: "코드는 마스터에 있는데 인쇄 명칭이 후보 명칭들과 크게 다른 행을 검토 필요로 표시하는 안을 difflib 유사도로 구현·측정했다. 76건 평가에서 어떤 임계값도 정밀도 70%를 넘지 못해 검사는 비활성으로 남기고 조회 함수만 남겼다."
tags: [rules, master, kcd, edi, evaluation, accuracy, decision]
status: active
---

# 마스터 명칭 유사도 검토 필요 플래그 — 임계값 스윕 결과와 보류 결정

2026-09-23 · 브랜치 `feat/master-name-flag` · 워크트리 `.worktrees/master-name-flag`

## 목표

[KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md)은 코드가 마스터에 있고 명칭이 마스터 명칭과 정확히 1글자만 다를 때만 그 글자를 고친다. 이번 작업은 값을 바꾸지 않고 **"코드는 마스터에 있는데 인쇄 명칭이 그 코드의 후보 명칭 전부와 크게 다르다"**는 신호만 `검토 필요`(`name_mismatch`)로 얹는 안을 검토했다. 코드나 명칭을 서로 바꾸지 않는다(값 변경 없음, 명칭에서 코드 역추론 없음 — harness-v2 Arbitration 원칙 유지, 사용자 결정).

## 만든 것

- `backend/master.py::similarity(system, value, name)` — 코드의 마스터 후보 명칭들과 `name`의 최대 유사도(0~1). `difflib.SequenceMatcher`로 `_letters()`(공백·괄호·하이픈 등 표기 차이 제거) 정규화 문자열을 비교한다. 코드가 마스터에 없거나 명칭이 비면 `None`. 외부 라이브러리 없이 표준 라이브러리만 쓴다.
- `tests/test_master.py`에 조회 경계 테스트 6개(정확 일치, 표기 차이 무시, 후보 없음/명칭 없음, 마스터 비활성, 낮은 유사도).
- `backend/rules.py::_master_checks` 독스트링에 이번 측정 결과와 판단을 기록. **검사는 추가하지 않았다** — 이유는 아래.

## 측정 방법

`data/verify/accuracy-20260922/pipeline-cache`(76건 rules 단계 캐시)와 `data/verify/labels`를 이용해, 진단서·소견서·진료비영수증·세부내역서 76건의 `병명내역`(kcd)·`항목내역`(edi) 행을 `rules.pair_rows`로 라벨 행과 짝지었다. 코드가 마스터에 있는 행만 모아(각 79/210셀 중 실제로 코드 적중·라벨 존재까지 갖춘 행), 예측 명칭과 마스터 후보 전체의 `similarity()` 최댓값을 계산했다. "참"은 그 행의 코드 또는 명칭이 라벨과 실제로 다른 경우(`rules.same`), "거짓"은 유사도는 낮지만 이미 라벨과 같은(정답인) 경우다. 스크립트는 일회성이라 커밋하지 않았다(`/tmp` 스크래치패드에서 실행).

## 결과

| 계통 | 대상 행 | 임계값(미만이면 발동) | 발동 | 참(true) | 거짓(false) | 정밀도 |
|---|---:|---|---:|---:|---:|---:|
| 병명(kcd) | 35 | <0.20 | 3 | 0 | 3 | 0% |
| 병명(kcd) | 35 | <0.35 | 6 | 1 | 5 | 17% |
| 병명(kcd) | 35 | <0.65 | 7 | 2 | 5 | **29%(최고)** |
| 병명(kcd) | 35 | <0.90 | 12 | 2 | 10 | 17% |
| EDI | 120 | <0.30 | 8 | 0 | 8 | 0% |
| EDI | 120 | <0.45 | 28 | 4 | 24 | 14% |
| EDI | 120 | <0.55 | 43 | 9 | 34 | **21%(최고)** |
| EDI | 120 | <0.90 | 91 | 10 | 81 | 11% |

임계값을 0.05~0.90까지 0.05 간격으로 훑었지만(전체 표는 재현 절 참고) 어느 계통·어느 임계값도 정밀도 70%를 넘지 못했다. 최고점은 병명 29%(발동 7건 중 2건만 실제 오류), EDI 21%다.

거짓 발동 사례:

```
0.0 False | kcd J20  R509 'Fever, unspecified'                     | label: 동일  # 진단명이 영문으로 인쇄되면 마스터 한글 명칭과 유사도가 항상 0에 가깝다
0.32 False | edi AU232 '[외래]의료질평가지원금(의료질/환자안전)'   | label: '...환자안전/' # 괄호·구두점 표기 차이
0.51 False | edi V2202 '[KTAS 1-3]응급진료전문의 진찰료(타과)'     | label: '[KTAS 1~3]응급진료 전문의 진찰료(타과)-' # 물결·공백·꼬리 하이픈
```

`병명`은 진단서·소견서에서 영문으로 인쇄되는 경우가 있는데 KCD 마스터 명칭은 전부 한글이라, 이미 정답인 영문 명칭도 유사도가 항상 0에 가깝게 나온다(Hangul 유무로 걸러도 최고 정밀도가 50%까지만 오르고 표본이 4건뿐이라 신뢰할 수 없다). `EDI명칭`은 고시 표기(하이픈·붙임표)와 인쇄 표기(괄호·물결·공백)가 달라 진짜 오류와 표기 차이가 유사도 구간에서 겹친다 — [명칭 교정 문서](2026-09-22-master-name-correction.md)가 이미 지적한 문제(rapidfuzz ratio 임계값 실험이 순손실 -13이었던 것)와 같은 원인이다.

## 판단

**검사를 추가하지 않는다.** 정밀도 70% 목표에 크게 못 미치고(최고 29%), Judge 참고용 신호치고 오탐이 압도적으로 많아 오히려 신뢰를 깎는다. `similarity()` 함수 자체는 남겨 둔다 — 나중에 임계값을 스크립트 조회나 수동 검수 도구에 쓸 수 있고, 마스터에 영문 명칭이 보강되거나 고시·인쇄 표기 정규화가 더 정교해지면 재평가할 수 있다.

기존 `code_unknown`(마스터에 없는 병명코드)만 유지한다 — 발동 1/79건 중 실제 오류 0건으로 오탐이 거의 없어 채택된 것과 대조적이다([명칭 교정 문서](2026-09-22-master-name-correction.md) "check 단계 이상 보고" 표 참고).

## 재현

```bash
export MASTER_SOURCE_DIR=/home/pilsu/projects/mirae-assets/harness-v2/docs/requirements/latest  # 로컬 전용 경로, 코드에 넣지 않는다
export DATABASE_URL=postgresql://docraft:docraft@127.0.0.1:5433/docraft
.venv/bin/python -m pytest tests -q  # 386 passed
```

스윕 스크립트는 `data/verify/accuracy-20260922/pipeline-cache`의 `<doc_type>__<stem>.{extract,parse}.json`과 `data/verify/labels/<doc_type>/<stem>.json`을 읽어 `rules.apply` 결과와 라벨을 `rules.pair_rows`로 짝짓고, 코드가 마스터에 있는 행마다 `master.similarity()`와 `rules.same()`(참/거짓 판정)을 계산해 임계값별로 집계한다.

## 관련 자료

- [KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md) — 1글자 교정 규칙과 rapidfuzz 통째 대체 실험이 순손실이었던 이유
- [KCD·EDI 마스터 원본 소스를 harness DB·docraft DB로 재사용](2026-09-23-master-source-reuse.md) — `MASTER_SOURCE_DIR` 등 마스터 로딩 구조
- `backend/master.py::similarity`, `backend/rules.py::_master_checks`
