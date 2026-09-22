---
type: Plan
title: "verify 룰 1차 추출 전환 계획 (지연 시간 최소화)"
description: "POST /api/verify에서 모델 추출을 빼고 파싱 블록 룰 추출 + AO 비교 + Judge 1회로 재구성해 지연 시간을 줄이면서 정확도를 유지하는 작업 지시서. 현재 구조 요약, 실측 시간, 부작용, 단계별 작업, 완료 기준"
tags: [plan, verify, rule-base, latency, agentic-ocr, llm-judge]
status: draft
---

# verify 룰 1차 추출 전환 계획

2026-09-22 · 브랜치 `docs/rule-first-plan` · 워크트리 `.worktrees/rule-first-plan`

[ocr-verify](2026-09-22-ocr-verify.md)로 구현한 `POST /api/verify`의 후속 작업 지시서다. 사용자 목표는 **지연 시간 최소화와 어느 정도의 성능 보장**이고, 현재 구조는 모델 추출이 1차라 이 목표와 맞지 않는다. 구현은 별도 브랜치(`feat/verify-rule-first` 등)에서 진행한다.

## 1. 현재 상황 (main `8050dd7` 기준)

### 파이프라인과 시간

`backend/verify.py`의 `run()` 순서와 gold 4건 실측(로컬 RTX 4070 PaddleOCR + OpenRouter Qwen3-VL-32B):

| 단계 | 코드 | 소요 | 비고 |
|---|---|---|---|
| ① 파싱 | `parsers.parse(image, provider="paddle")` | 20~90초 | PaddleOCR-VL 레이아웃 + `TABLE_REFINE`(VLM 셀 교정 4~13초) + 줄 OCR(`PADDLEOCR_LINES_URL`, 근거 좌표용). 표가 클수록 길다 |
| ② 모델 추출 | `engine.extract(doctypes.schema(doc_type), blocks, source=image)` | 10~30초 | LLM 1회. **룰 1차 전환으로 없앨 대상** |
| ③ 룰 후처리 | `rules.apply(doc_type, result, blocks)` | 0초 | 정규화·빈 스칼라 라벨 보충·파생·합계행 |
| ④ 이상 검사·교정 | `rules.check` / `rules.correct` | 0초 | 진료비영수증 항목내역 전용 |
| ⑤ 비교 | `rules.same` | 0초 | 일치 필드는 확정 |
| ⑥ Judge | `verify.judge` | 10~60초 | 불일치·누락·이상 필드만 이미지와 함께 LLM 1회 |

문서당 합계: 진단서·소견서 30~40초, 진료비영수증 90~140초, 세부내역서 약 180초.

### 룰의 현재 역할

- `rules.apply`는 모델 결과를 받아 **정규화와 보충**만 한다. 표(`항목내역`·`병명내역` 등)는 룰이 만들지 않고 모델 결과를 검사·교정만 한다.
- 그래서 모델이 금액이 빈 항목 행을 버리면(진료비영수증 `항목내역.항목` 실패 240건, 36건 평가의 최대 실패) 룰이 되살릴 수 없다.
- 이미 있는 자산: 라벨 동의어 테이블 `rules.LABELS`(57필드), 라벨 셀 오른쪽·`라벨: 값`·OCR 줄 탐색 `rules._fill`, 항목명 정규화 `rules.item`, 머리글 판별 `rules._headers`, 합계행 `rules._totals`, 파생 `rules.derive`, 정답셋 36건과 평가 스크립트 `scripts/verify_eval.py`(raw/rules/ao/final 단계).

### 평가 기준선 (36건, [ocr-verify](2026-09-22-ocr-verify.md) 6절)

| 유형 | raw(모델) | rules(모델+룰) | gold final |
|---|---|---|---|
| 진단서 | 82.0% | 88.0% | 100% |
| 소견서 | 80.7% | 81.4% | 90% |
| 진료비영수증 | 84.2% | 84.4% | 98% |
| 세부내역서 | 91.4% | 98.0% | 98.8% |
| 전체 | 88.4% | 92.9% | - |

## 2. 목표 구조

```
① 파싱(경량 옵션)
② 룰 추출        파싱 블록에서 직접: 표는 rows → 열 매핑 → 행, 스칼라는 라벨 규칙   ← 모델 호출 없음
③ AO와 비교      일치 → 확정(agree)
④ Judge 1회      불일치·누락·검출 이상만 이미지와 함께. Judge가 필요한 필드를 이미지에서 직접 읽어 모델 추출을 대체
⑤ (선택) 모델 추출 폴백   룰 커버리지가 낮은 유형·문서에서만
```

지연: 파싱 + Judge 1회로 내려간다(모델 추출 10~30초 제거, 룰·AO 일치 필드가 늘수록 Judge 입력도 감소). 성능: AO와 룰이라는 독립된 두 결과가 일치하면 확정하고, 다르면 이미지를 보는 Judge가 판정하므로 유지된다.

## 3. 예상 부작용과 대응

| 부작용 | 대응 |
|---|---|
| 라벨 변형·OCR 오탈자에 약함(twin reader는 `진단명` 오탈자 라벨 159종, 우리는 대표 동의어만) | 못 찾은 필드는 AO와 불일치로 Judge에 가므로 "누락"이지 "오답"이 아니다. 실패 목록에서 자주 나오는 라벨을 `LABELS`에 추가 |
| 같은 라벨 혼동(환자 `주소`/병원 `주소`, 환자 `전화번호`/병원 `Tel`) | 블록 순서·페이지 상단/하단 위치 규칙을 둔다(환자정보 블록은 병명 위, 의료기관 블록은 하단). 기존 짝 유입 차단은 유지 |
| 파싱 오류를 그대로 물려받음(셀 하나에 금액 여러 개, 행 병합) | `multi_amount` 검출을 Docraft 표에도 적용해 Judge로 보낸다 |
| 의미 해석 필드는 룰 커버리지가 낮음(비고의 검사일, 소견 문장 → 치료내역, 주/부상병 분리, 체크박스 상태) | 기존 `rules._fill`의 치료·검사내역 보충 규칙을 유지하고, 나머지는 AO 값이 있으면 그대로, 없으면 Judge |
| 룰은 신뢰도 신호가 없어 AO와 같은 오답이면 그대로 확정 | 두 OCR 엔진이 달라 상관은 낮다. 정답셋 평가에서 `agree`인데 라벨과 다른 건수를 별도 지표(`agree_wrong`)로 센다 |
| 파싱이 지연의 바닥으로 남음 | verify 경로에서 줄 OCR을 끄고(근거 좌표 불필요), `TABLE_REFINE`은 표 유형에만 켜는 옵션을 두고 시간·정확도 전후 비교 |

## 4. 세부 작업

### A. 룰 추출기 (`backend/rules.py`)

- `extract(doc_type, blocks) -> dict`(정규 표현)를 추가한다. 새 함수 하나에 기존 `_fill`(스칼라)·`_headers`·`item`·`_totals`(표)를 합쳐 쓰고, `apply`는 그 위에 정규화·파생만 하도록 정리한다. 비슷한 기능이 둘이 되지 않게 `_fill`은 `extract` 안으로 옮긴다.
- 표: 파싱 표 블록의 `rows`(괘선 격자 복원 포함, `spans` 보존)에서 머리글 행을 찾아 doctypes 열 키로 매핑(동의어: 본인부담금/본인부담, 전액본인부담금, 선택진료료외/이외 등 AO 프롬프트 규칙을 데이터로), 항목명 정규화 후 행을 만든다. 금액이 빈 행도 남긴다. 합계·소계 행은 `_totals` 규칙대로 처리(진료비영수증은 최종 합계 행 유지).
- 스칼라: 라벨 규칙 우선순위(표 라벨 셀 오른쪽 → 아래 → 텍스트 `라벨: 값` → OCR 줄)와 블록 위치 규칙(환자/병원 짝)을 둔다.
- 체크박스: 블록 텍스트의 `[√]`·`☑`·`■` 등 기호를 `_TRUE`로 판정, 기호가 없으면 None(Judge 대상).

### B. 파이프라인 (`backend/verify.py`, `backend/config.py`)

- `run()`에서 `engine.extract` 호출을 `rules.extract`로 바꾸고, `EXTRACT_FALLBACK`(기본 `false`) 설정으로 모델 추출을 선택 호출한다. 폴백 조건은 "룰이 채운 스칼라가 doctypes 정의의 N% 미만"처럼 단순하게 두고 상수로 뺀다.
- Judge 프롬프트에 "docraft 값이 null이면 이미지에서 직접 읽어 `corrected`로 답하라"를 명시한다(지금은 두 후보 중 선택 위주).
- 파싱 옵션: verify 경로에서 `lines_url`을 쓰지 않도록 `parse()` options에 `lines: false`(또는 동등한 플래그)를 추가하고, `TABLE_REFINE`은 `doctypes`에 표가 있는 유형에만 적용한다. `parsers.parse`의 기존 호출자(문서 업로드 경로)는 동작이 바뀌지 않아야 한다.

### C. 평가 (`scripts/verify_eval.py`)

- 단계에 `rule`(룰 추출만)을 추가하고 기존 `raw`·`rules`는 남긴다. `final` 시간을 문서별로 기록해 유형별 평균·최대를 표로 낸다.
- `agree_wrong` 지표를 추가한다.
- 전환 전후 비교표: 정확도(유형별 rule/rules/final)와 시간(파싱·Judge·합계)을 같은 36건으로 낸다.

### D. 문서

- 결과를 `wiki/2026-09-22-verify-rule-first.md`(구현 기록)에 남기고 `wiki/index.md`·`wiki/log.md`·README verify 절을 갱신한다. 이 계획 문서는 구현 후 `status: stable`로 바꾸고 결정 사항을 적는다.

## 5. 완료 기준

- [ ] `EXTRACT_FALLBACK=false`에서 gold 4건 + 오류 케이스 3건이 모델 추출 없이 교정 JSON을 반환한다.
- [ ] 36건 평가에서 `final` 정확도가 기준선(진단서 100·소견서 90·진료비영수증 98·세부내역서 98.8%) 대비 유형별 2pp 이내로 유지된다.
- [ ] 문서당 시간이 유형별로 기준선(30~40 / 90~140 / 약 180초) 대비 30% 이상 줄어든 전후 비교표가 있다.
- [ ] 진료비영수증 `항목내역.항목` 실패(240)가 룰 추출로 크게 줄었다.
- [ ] `tests/test_rules.py`에 표·스칼라 룰 추출 테스트, `tests/test_verify.py`에 폴백 분기 테스트가 있고 전체 통과한다.

## 6. 작업 규칙과 환경

- AGENTS.md대로 워크트리 `.worktrees/verify-rule-first`, 브랜치 `feat/verify-rule-first`, 한국어 접두사 커밋, main에는 `--no-ff` 병합.
- 워크트리에는 `data`·`.env`·`refs/postprocess_schema_example`이 없으므로 심볼릭 링크로 연결한다(`ln -s ../../data data` 등). 정답셋은 `data/verify/labels/`, 파싱 캐시는 `data/verify/cache/`(파싱 옵션을 바꾸면 `--no-cache`로 다시 만든다).
- 로컬 서비스: `docker compose --profile ocr` 컨테이너(PaddleOCR-VL 8080, 줄 OCR 8081, PostgreSQL 5433), `.env`의 OpenRouter 설정. 오케스트레이션은 메인 세션, 탐색·구현은 Sonnet/Opus 서브에이전트로 나누고 파일 소유를 분리해 병렬로 진행한다.
- 참고: [ocr-verify](2026-09-22-ocr-verify.md), [ocr-verify-labels](2026-09-22-ocr-verify-labels.md), [ocr-verify-plan](2026-09-22-ocr-verify-plan.md), harness-v2 오류 케이스 `harness-v2/docs/requirements/[진료비영수증]*`.
