---
okf_version: "0.2"
type: change
title: 표 rowmajor 추출 이식 (TABLE_EXTRACT)
description: exp-extract-table에서 검증한 조건부 rowmajor 표 추출(영수증 양식별 열, 세부내역서 머리글 열 순서, 행 산술 게이트)을 Docraft 첫 추출에 이식하고 기본값으로 켰다. 원내코드 후퇴를 고쳤고 정답지 59건 오프라인 재현으로 확인했다
tags: [docraft, extract, table-extraction, rowmajor, latency, golden-set]
status: active
---

- 날짜: 2026-10-02
- 브랜치: feat/rowmajor-table (dev 49b0baa에서 분기, 병합·push 안 함)
- 워크트리: .worktrees/rowmajor-table
- 실험 원본: exp-extract-table `feat/rowmajor-conditional`, 상위 wiki `2026-10-02-table-rowmajor-conditional.md`

## 1. 무엇을 바꿨나

| 파일 | 내용 |
|---|---|
| `backend/config.py` | `TABLE_EXTRACT`(기본 `rowmajor`, `asis`), `TABLE_RECHECK_RATIO`(기본 0.3) |
| `backend/engine.py` | `extract(..., table_extract="asis")`. rowmajor면 표 필드마다 `_read_rows` 호출(행 = 값 배열, `response_format: json_schema`로 열 수 고정)과 나머지 필드의 JSON 객체 호출 하나를 병렬로 한다. 값은 합집합 열 키로 되돌린다. `_provider(json_schema=...)` |
| `backend/table_layout.py` | 열 배치 판별: 진료비영수증 양식 1~5(표 셀 낱말), 세부내역서 머리글 열 순서(OCR 줄 x 위치). 못 정하면 None → 스키마 열 순서 |
| `backend/rulesets/table_layouts.yaml` | 유형·표별 방법, 머리글 낱말 표, 영수증 양식별 표·열 설명(harness-v2 `진료비영수증_양식별_스키마/latest/추출_[1-5]_*.json`에서 옮김) |
| `backend/rules.py` | `arith_misses`: 세부내역서 항목내역의 행 산술(`_row_arith`) 실패 행 비율(행당 한 번) |
| `backend/verify.py` | `read`: 설정값으로 첫 추출, rowmajor이고 실패 비율 ≥ `TABLE_RECHECK_RATIO`면 항목내역만 asis로 다시 읽는다(호출 수는 `initial_extract_model_calls`에 들어간다) |
| README, `.env.example`, `deploy/aws/.env.aws.example`, helm `values.yaml`·`config.yaml` | 새 설정 |

적용 범위는 `/api/read`·`/api/verify`의 첫 추출뿐이다. 재처리(`reprocess`)와 프로젝트 일반 추출(`/api/.../extract`)은 `engine.extract` 기본값 asis 그대로다.

rowmajor를 쓰지 않고 asis로 읽는 경우: 문서가 `EXTRACT_CHUNK_CHARS` 한 조각을 넘을 때, 페이지 이미지가 없을 때(`AI_VISION=false`·텍스트 문서), 응답 행이 0개이거나 열 수가 맞지 않을 때(그 표만 asis로 다시 읽는다).

## 2. 고객사 vLLM

`AI_MODE=local`은 LLM 없는 정규식 추출(개발·테스트용)이라 rowmajor와 관계없다. 고객사 vLLM은 `AI_MODE=provider` + `AI_BASE_URL=<vllm>`으로 OpenRouter와 같은 `_provider`를 쓴다. rowmajor 호출은 OpenAI 호환 `response_format: {"type":"json_schema"}`를 보낸다. vLLM(helm 0.29.0)은 structured outputs로 이 스키마를 강제하고, OpenRouter에는 `provider.require_parameters: true`를 같이 보내 스키마를 지키는 provider로만 보낸다. 이 경우 `reasoning` 파라미터는 보내지 않는다(같이 보내면 받는 provider가 없어 404). vLLM은 모르는 `provider` 필드를 무시한다. vLLM 실기 확인은 아직 못 했다(AWS 호출 금지). 배포 담당 세션에서 확인해야 한다.

## 3. 원내코드 후퇴 수정

- 증상: 실험 header 방식에서 원내코드가 93.4% → 89.0%(21칸, 문서 2건)로 떨어졌다.
- 근본 원인: 머리글에서 못 읽은 열을 "서식에 없는 열"로 보고 뺐다. 그런데 코드 낱말을 하나도 못 읽은 문서(`20230104`: '처방코드'를 '서발코드'로 읽음)와 낱말 표에 없는 머리글('품목코드', 'EDI 코드')은 코드 열 수를 센 적이 없다.
- 문제 유형: 열을 못 읽은 것을 열이 없다는 근거로 썼다.
- 일반화한 규칙
  1. 열을 뺄지는 그 개념의 머리글 낱말을 읽어 열 수를 셌을 때만 정한다. 한 개념(코드 = 원내코드·EDI코드, 일자 = 시작·종료일자)의 낱말을 하나도 못 읽었으면 짝 열을 모두 남긴다. 코드 열이 하나뿐인 서식은 `rules._header_columns`가 원내코드를 EDI코드로 모은다.
  2. 끝말 규칙: '…코드'로 끝나는 머리글은 앞말을 못 읽었어도 코드 열로 본다.
  3. 낱말 표에 `실시일자`·`품목코드`·`원내코드`·`EDI코드`를 넣었다.
- 효과(59건): 원내코드 89.0% → **94.5%**(asis 93.4%). 다른 열은 실험과 같은 수준이다.

## 4. 오프라인 검증 (정답지 59건, OpenRouter qwen3-vl-32b, AWS 호출 없음)

저장해 둔 OCR 블록·이미지로 `verify.read`를 실제 코드 그대로 돌렸다. 바꾼 것은 `parse` 대체(저장본), `only` = 표, `auto_reprocess=False`뿐이다. 스크립트는 세션 scratchpad의 `port_run.py`이고, 결과는 `e2e/out/ab-rowmajor-1002/docraft-port/<유형>/`, 채점은 `docraft-port/grade/summary.md`에 있다.

| | asis | 실험 header+게이트 | **Docraft 이식** |
|---|---|---|---|
| 정확도 | 89.67% | 90.27% | **90.29%** |
| 세부내역서 / 영수증 | 80.90 / 99.62 | 82.01 / 99.61 | 81.98 / 99.71 |
| 원내코드 | 93.4 | 89.0 | **94.5** |
| 지연 합계 | 2303초 | 1001초 | 1134초(−50.8%) |
| p50/p90/max | 36.6/61.4/97.4 | 14.3/27.7/66.5 | 16.4/29.5/62.2 |
| LLM 호출 | 59 | 61 | 61(게이트 2건: 코드2개_급여액, SA…4193 — 실험과 같다) |

차이와 원인
- 지연이 실험보다 13% 길다. 같은 열 배치에서도 호출마다 차이가 있고(OpenRouter 측 편차), 원내코드·종료일자 열이 늘어난 문서는 출력 토큰이 조금 늘었다(평균 939 → 978).
- 같은 열 배치인데 결과가 달라진 문서
  - `3022033115105207-1`: 단가 15칸 누락
  - `급여액_2303314628`: 합집합 순서로 읽은 문서, 선택진료료외에 날짜 18칸이 오검출됨

  두 문서 모두 열 배치는 실험과 같으므로 모델 출력이 호출마다 달라진 것이다(temperature 0이어도 결정적이지 않음).

## 5. 테스트

`tests/test_rowmajor.py` 35건을 추가했고, 전체 696 passed다.
- 영수증 양식 판별: 1·2·4·5 판별, OCR 오독('이의')과 칸이 갈린 '이외', 신청란의 '선택진료', 판별하지 못하는 경우(None)
- 세부내역서 머리글
  - x 순서, 오독('충액'), 붙여 쓴 낱말과 띄어 쓴 낱말, 묶음 제목 '급여'
  - 회전·머리글 없음 → None
  - 못 읽은 필수 열은 제자리에 두고 선택 열은 뺀다
  - 코드 열 수 판단 4가지(하나, 끝말·오독, 떨어진 'EDI 코드', 못 읽음)
- engine
  - 위치 배열 스키마·순서와 합집합 키 되돌리기
  - 스칼라 필드는 따로 호출
  - 영수증 0 채움
  - 행 0개·열 수가 틀린 응답 → asis
  - 이미지 없음·여러 조각 → asis
  - asis는 기존과 같은 한 번 호출
  - json_schema 요청 본문(`require_parameters`, `reasoning` 없음)
- verify.read 게이트: 비율 0.3에서 다시 읽음, 0.2·0이면 그대로, `TABLE_EXTRACT=asis`면 다시 읽지 않음
- `arith_misses`: 행당 한 번 세기, 다른 유형은 0
- 기존 `test_verify` 가짜 `extract` 두 곳은 새 키워드 인자를 받도록 시그니처만 넓혔다.

## 6. 남은 일

- 고객사·AWS vLLM에서 json_schema(행 배열 `minItems`·`maxItems`) 강제를 실기로 확인해야 한다(배포 담당 세션).
- 영수증 양식 3은 판별 규칙상 나오지 않는다(선택진료료만 보이면 None). 양식 3·5 표본이 없다.
- 회전 스캔 세부내역서 3건은 합집합 순서로 읽는다.
- 게이트 오탐(SA…4193)은 실험과 같다.
- harness-installer `apps/docraft`는 Docraft 사본이다. 다음 동기화 때 코드 기본값(rowmajor)이 함께 들어가고, env를 따로 바꿀 필요는 없다.
