---
okf_version: "0.2"
type: Analysis
title: "마스터 명칭 유사도 검토 필요 플래그 — 임계값 스윕 결과와 보류 결정"
description: "코드는 마스터에 있는데 인쇄 명칭이 후보 명칭들과 크게 다른 행을 검토 필요로 표시하는 안을 difflib 유사도, 이어서 harness-v2가 쓰는 BAAI/bge-m3 임베딩 코사인 유사도로 구현·측정했다. 76건 평가에서 어느 방식·어떤 임계값도 정밀도 70%를 넘지 못해 검사를 추가하지 않기로 하고 두 조회 함수 모두 제거했다."
tags: [rules, master, kcd, edi, evaluation, accuracy, decision]
status: active
---

# 마스터 명칭 유사도 검토 필요 플래그 — 임계값 스윕 결과와 보류 결정

2026-09-23 · 브랜치 `feat/master-name-flag` · 워크트리 `.worktrees/master-name-flag`

## 목표

[KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md)은 코드가 마스터에 있고 명칭이 마스터 명칭과 정확히 1글자만 다를 때만 그 글자를 고친다. 이번 작업은 값을 바꾸지 않고 **"코드는 마스터에 있는데 인쇄 명칭이 그 코드의 후보 명칭 전부와 크게 다르다"**는 신호만 `검토 필요`(`name_mismatch`)로 얹는 안을 검토했다. 코드나 명칭을 서로 바꾸지 않는다(값 변경 없음, 명칭에서 코드 역추론 없음 — harness-v2 Arbitration 원칙 유지, 사용자 결정).

## 만든 것

1차(difflib, `4b6986f`): `backend/master.py::similarity(system, value, name)` — 코드의 마스터 후보 명칭들과 `name`의 최대 유사도(0~1). `difflib.SequenceMatcher`로 `_letters()`(공백·괄호·하이픈 등 표기 차이 제거) 정규화 문자열을 비교. `tests/test_master.py`에 조회 경계 테스트 6개.

2차(임베딩, 이번 갱신): harness-v2가 서빙하는 `BAAI/bge-m3`(vLLM, AWS 개발 EC2)로 같은 76건을 코사인 유사도로 재평가했다(`/tmp` 스크래치패드 일회성 스크립트, 커밋 안 함). harness의 전처리를 그대로 따랐다 — KCD는 원문 그대로(`kcd_name.py::judge` 4단 U4와 같게 전처리 없이 질의·후보 비교), EDI는 `similarity.py::edi_embedding_form`(NFKC, 괄호 토막만 제거, 기호·대소문자는 남김)으로 질의·후보 모두 변환. 결과도 70%를 넘지 못해(아래 표), **`similarity()`와 새 임베딩 조회 함수 둘 다 코드에 남기지 않았다** — 이유는 아래.

`backend/rules.py::_master_checks` 독스트링에 두 방식의 측정 결과와 판단을 기록. **검사는 추가하지 않았다.**

## 측정 방법

두 차례 다 같은 재현 절차를 썼다: `data/verify/accuracy-20260922/pipeline-cache`(76건 rules 단계 캐시)와 `data/verify/labels`를 이용해, 진단서·소견서·진료비영수증·세부내역서 76건의 `병명내역`(kcd)·`항목내역`(edi) 행을 `rules.pair_rows`로 라벨 행과 짝지었다. 코드가 마스터에 있는 행만 모아(각 79/210셀 중 실제로 코드 적중·라벨 존재까지 갖춘 행 — kcd 35행, edi 120행) "참"은 그 행의 코드 또는 명칭이 라벨과 실제로 다른 경우(`rules.same`), "거짓"은 유사도는 낮지만 이미 라벨과 같은(정답인) 경우로 셌다.

1차(difflib)는 예측 명칭과 마스터 후보 전체의 `similarity()`(`_letters()` 정규화) 최댓값을 썼다.

2차(임베딩)는 harness-v2가 운영하는 `BAAI/bge-m3` vLLM(`vllm-embedding`, AWS 개발 EC2, `deploy/aws/tunnel.sh`가 열지 않는 컨테이너 전용 포트라 `ssh -L 8201:<컨테이너IP>:8000`을 직접 열었다)에 `/v1/embeddings`로 물어 코사인 유사도 최댓값을 썼다. 질의·후보 전처리는 harness와 같게 맞췄다 — **KCD**는 `kcd_name.py::judge` 4단(U4)과 같게 원문 그대로(전처리 없이) 비교하고, **EDI**는 `similarity.py::edi_embedding_form`(NFKC 정규화, 괄호 토막만 제거, 기호·대소문자는 유지)으로 질의·후보 모두 변환했다. 두 방식 모두 문서당 배치 호출·명칭별 캐시를 썼다. 두 스크립트 다 일회성이라 커밋하지 않았다(`/tmp` 스크래치패드에서 실행).

## 결과

difflib(1차):

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

임베딩(2차, bge-m3 코사인, 미만이면 발동) — 재현율은 대상 행 중 참(true)인 것 중 잡아낸 비율:

| 계통 | 대상 행 | 임계값 | 발동 | 참(true) | 거짓(false) | 정밀도 | 재현율 |
|---|---:|---|---:|---:|---:|---:|---:|
| 병명(kcd) | 35(전체 참 3) | <0.60 | 1 | 1 | 0 | 100%(표본 1건, 신뢰 불가) | 33% |
| 병명(kcd) | 35 | <0.75 | 5 | 2 | 3 | **40%(신뢰 가능한 최고)** | 67% |
| 병명(kcd) | 35 | <0.90 | 10 | 2 | 8 | 20% | 67% |
| EDI | 120(전체 참 11) | <0.60 | 14 | 3 | 11 | **21%(최고)** | 27% |
| EDI | 120 | <0.75 | 53 | 7 | 46 | 13% | 64% |
| EDI | 120 | <0.90 | 85 | 10 | 75 | 12% | 91% |

결합 규칙(임베딩<t1 AND difflib<t2)도 시도했다 — kcd 최고는 t1<0.6·t2<0.4에서 정밀도 100%지만 발동 1건뿐이라(표본 부족) 의미가 없고, 다음으로 나은 조합은 t1<0.7에서 33%다. EDI 최고는 t1<0.6·t2<0.6에서 발동 11·참 3·정밀도 27%로 임베딩 단독(21%)보다 조금 낫지만 여전히 목표에 한참 못 미친다.

임계값을 0.05~0.95까지 0.05 간격으로 훑었지만(전체 표는 재현 절 참고) **difflib·임베딩·결합 규칙 어느 것도, 어느 계통·임계값에서도 정밀도 70%를 넘지 못했다.** kcd 35행은 전체 참이 3건뿐이라 어떤 조합도 표본이 작아 한 건만 더 맞거나 틀려도 정밀도가 수십%p 흔들린다는 점을 감안해야 한다.

거짓 발동 사례(difflib):

```
0.0 False | kcd J20  R509 'Fever, unspecified'                     | label: 동일  # 진단명이 영문으로 인쇄되면 마스터 한글 명칭과 유사도가 항상 0에 가깝다
0.32 False | edi AU232 '[외래]의료질평가지원금(의료질/환자안전)'   | label: '...환자안전/' # 괄호·구두점 표기 차이
0.51 False | edi V2202 '[KTAS 1-3]응급진료전문의 진찰료(타과)'     | label: '[KTAS 1~3]응급진료 전문의 진찰료(타과)-' # 물결·공백·꼬리 하이픈
```

거짓 발동 사례(임베딩) — difflib가 걸렀던 영문 병명 오탐은 줄었지만, EDI는 인쇄 명칭이 라벨과 **글자 그대로 같은데도** 낮은 점수가 나오는 새 유형이 나타났다(그 코드의 마스터 후보 명칭 중 어느 것도 인쇄 표기와 딱 맞지 않기 때문 — 원인은 difflib와 같다, 유사도 계산 방식만 바뀐 것):

```
0.5672 False | edi Z0030 '직영가산(1식당)' | label: '직영가산(1식당)'  # 인쇄 명칭이 라벨과 완전히 같은데도 마스터 후보 전부와 거리가 있다
0.5123 False | edi BM2600VT '뉴젠콜(NEWGENCOL)' | label: '뉴젠콜 (NEWGENCOL)'  # 괄호 앞 공백 하나 차이
```

`병명`은 진단서·소견서에서 영문으로 인쇄되는 경우가 있는데 KCD 마스터 명칭은 전부 한글이라, difflib에서는 이미 정답인 영문 명칭도 유사도가 항상 0에 가깝게 나온다 — 임베딩은 의미 기반이라 이 경우를 일부 구제해(kcd 최고 정밀도가 29%→40%로 개선) 가설(문서 서두 참고)이 부분적으로는 맞았다. 하지만 `EDI명칭`은 고시 표기(하이픈·붙임표)와 인쇄 표기(괄호·물결·공백)가 다른 문제가 임베딩에서도 그대로 남아(위 사례) 진짜 오류와 표기 차이가 유사도 구간에서 계속 겹친다 — [명칭 교정 문서](2026-09-22-master-name-correction.md)가 이미 지적한 문제(rapidfuzz ratio 임계값 실험이 순손실 -13이었던 것)와 같은 원인이다.

## 판단

**검사를 추가하지 않는다.** difflib든 임베딩이든 결합 규칙이든 정밀도 70% 목표에 크게 못 미치고(최고 kcd 40%·EDI 21%, 그나마 kcd는 표본이 작다), Judge 참고용 신호치고 오탐이 압도적으로 많아 오히려 신뢰를 깎는다.

**`similarity()`(difflib)와 임베딩 조회 함수 둘 다 코드에 남기지 않는다** — 1차 결정(`4b6986f`)에서는 "나중에 재평가할 수 있다"며 `similarity()`를 남겼지만, harness급 임베딩으로 재평가해도 같은 결론이 나왔으므로 쓰이지 않는 함수를 유지할 이유가 없다(AGENTS.md "비슷한 의미를 내포하는 기능은 없어야 한다"). 마스터에 영문 명칭이 보강되거나 고시·인쇄 표기 정규화가 더 정교해지면, 이 문서와 스윕 방법을 참고해 다시 만들면 된다.

기존 `code_unknown`(마스터에 없는 병명코드)만 유지한다 — 발동 1/79건 중 실제 오류 0건으로 오탐이 거의 없어 채택된 것과 대조적이다([명칭 교정 문서](2026-09-22-master-name-correction.md) "check 단계 이상 보고" 표 참고).

## 재현

```bash
export MASTER_SOURCE_DIR=/home/pilsu/projects/mirae-assets/harness-v2/docs/requirements/latest  # 로컬 전용 경로, 코드에 넣지 않는다
export DATABASE_URL=postgresql://docraft:docraft@127.0.0.1:5433/docraft
.venv/bin/python -m pytest tests -q
```

difflib 스윕 스크립트는 `data/verify/accuracy-20260922/pipeline-cache`의 `<doc_type>__<stem>.{extract,parse}.json`과 `data/verify/labels/<doc_type>/<stem>.json`을 읽어 `rules.apply` 결과와 라벨을 `rules.pair_rows`로 짝짓고, 코드가 마스터에 있는 행마다 difflib 유사도와 `rules.same()`(참/거짓 판정)을 계산해 임계값별로 집계했다(당시 `master.similarity()`를 직접 불렀다 — 지금은 제거됨).

임베딩 스윕 스크립트는 같은 방식으로 행을 모으되, `master.names()`로 얻은 후보 명칭과 예측 명칭을 harness 전처리로 변환해 `httpx`로 `MASTER_EMBEDDING_URL`(AWS 개발 EC2 `vllm-embedding` 컨테이너로의 SSH 터널)에 배치 임베딩을 요청하고 numpy 코사인으로 비교했다. 임베딩 서버 접근:

```bash
# 컨테이너가 호스트 포트를 게시하지 않으므로(deploy/aws/tunnel.sh는 API·PG·CH만 포워딩) 컨테이너 IP로 직접 연다
ssh -i <SSH_KEY> ec2-user@<SSH_HOST> "docker inspect mlife-harness-vllm-embedding --format '{{range \$k,\$v := .NetworkSettings.Networks}}{{\$v.IPAddress}}{{end}}'"
ssh -i <SSH_KEY> -N -L 8201:<컨테이너IP>:8000 ec2-user@<SSH_HOST> &
# API 키는 컨테이너 환경변수 VLLM_API_KEY(docker inspect로 확인) — .env.aws의 MASTER_EMBEDDING_API_KEY가 비어 있어도 실제로는 켜져 있었다
```

## 관련 자료

- [KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md) — 1글자 교정 규칙과 rapidfuzz 통째 대체 실험이 순손실이었던 이유
- [KCD·EDI 마스터 원본 소스를 harness DB·docraft DB로 재사용](2026-09-23-master-source-reuse.md) — `MASTER_SOURCE_DIR` 등 마스터 로딩 구조
- harness-v2 `src/mlife_harness/master/{embedding,similarity,kcd_name}.py` — bge-m3 임베딩 클라이언트·EDI 명칭 전처리·KCD 4단 판정(U4) 구현, 이번 재현이 따라 한 원본
- `backend/rules.py::_master_checks`
