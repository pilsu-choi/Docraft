---
type: report
title: 표 추출 방식 A/B 실험 — Docraft 현행(asis) vs 위치 배열(rowmajor)
description: exp-extract-table의 rowmajor를 Docraft 표 추출에 녹일 가치가 있는지 정답지 59건·같은 OCR·같은 LLM으로 비교한 실험 보고서
tags: [docraft, harness, experiment, table-extraction, rowmajor, latency, golden-set]
status: active
---

날짜: 2026-10-02  
브랜치: exp-extract-table `feat/ab-docraft` (실험 코드 `ab/`), Docraft·harness 코드 변경 없음  
워크트리: `exp-extract-table/.worktrees/ab-docraft`  
결과: `e2e/out/ab-rowmajor-1002/` (`full/summary.md`·`summary.json`·`diff.csv`)

## 1. 요약

| | asis (현행) | rowmajor | 차이 |
|---|---|---|---|
| 표 칸 정확도 | 89.67% | 88.81% | −0.86%p (한 문서가 대부분, 4절) |
| 추출 호출 지연 p50 / p90 / max | 36.6 / 61.4 / 97.4초 | 18.7 / 29.1 / 36.6초 | **약 −50%** (59건 모두 빨라짐) |
| 출력 토큰 평균 | 2,283 | 1,129 | −51% |
| 오류·0행·잘림 | 0 / 0 / 0 | 0 / 0 / 0 | 같음 |

**결론: 속도 효과는 확실하지만, 표 전체가 한 열씩 밀리는 사고가 59건 중 1건 나왔다. 그래서 바로 기본값으로 바꾸지 않고, 열 밀림 검출과 asis 재추출을 붙인 조건부 도입을 2단계로 검증한다.**

## 2. 목적과 가설

- 목적: Docraft 표 추출이 느리다. 24행 표가 100~160초 걸려 HTTP 408이 났고, 표 교정이 처리 시간의 29%를 차지한다(`2026-10-02-docraft-read-latency-analysis.md`). 이 지연을 exp-extract-table의 rowmajor로 줄일 수 있는지 본다.
- 가설 H1: rowmajor는 행마다 필드 키를 다시 쓰지 않으므로 출력 토큰과 지연이 크게 준다.
- 가설 H2: Docraft는 OCR 표 텍스트를 참고로 주기 때문에, rowmajor의 알려진 약점(열 뒤바뀜)이 정확도를 떨어뜨리지 않는다.

## 3. 실험 설정

| 항목 | 내용 |
|---|---|
| 데이터 | 정답지 59건(세부내역서 29, 진료비영수증 30). 이미지·정답은 `e2e/out/golden1002-aws-r9` |
| OCR | AWS Docraft 컨테이너의 PaddleOCR-VL(표 교정 포함)로 59건을 한 번 파싱해 두 방식에 같은 blocks를 넣음. 실패 0 |
| LLM | OpenRouter `qwen/qwen3-vl-32b-instruct` (AWS Docraft와 같은 설정), temperature 0. 실제 처리 provider는 두 방식 모두 Alibaba 59/59 |
| A: asis | Docraft `engine.extract(표 key로 좁힌 스키마, blocks, 이미지)`, 응답 형식 `json_object`. 재처리 루프는 끔 |
| B: rowmajor | exp `extract_rowmajor`, 응답 형식 `json_schema`(OpenRouter `require_parameters`). 이미지는 Docraft `_page_images`(긴 변 2000px JPEG), 참고 텍스트는 Docraft `_chunk_text`로 A와 같음 |
| 같게 둔 것 | 이미지, OCR 텍스트, 모델, 표 스키마(열 순서·설명), 후처리 `rules.apply` |
| 진행 | 문서마다 A·B를 번갈아 호출(시간대 편향 제거), 동시 4건, 재시도 없음(원시 실패를 셈) |
| 채점 | `e2e/grade_samples.py`의 `align`·`verdict`를 써서 표 칸만 비교 |
| 호출 수 | OCR 59(AWS), LLM 118(OpenRouter) |

## 4. 결과

### 4.1 정확도

| 구분 | asis | rowmajor |
|---|---|---|
| 전체 | 89.67% (11,629/12,969) | 88.81% (11,527/12,980) |
| 세부내역서 | 80.90% | 79.53% |
| 진료비영수증 | 99.62% | 99.39% |
| 누락 행 / 초과 행 | 114 / 31 | 115 / **10** |
| 열 뒤바뀜 칸 | 31 | 39 |

- 이 수치는 Docraft 단독 첫 추출 기준이다. AO 결과, 하네스 중재, 재처리를 거치지 않았으므로 운영 정확도(59건 99.4%)와 직접 비교하지 않는다. `급여구분`(11.8%)은 열추출 정책 차이 때문에 두 방식 모두 낮다.
- 행 수 일치가 3/59로 나온 것은 채점 스크립트의 행 수 셈법 문제로 보인다(빈 행·합계 행 처리). 두 방식에 똑같이 적용되므로 비교에는 영향이 없다.

### 4.2 차이가 난 칸 분석

두 방식의 값이 다른 칸은 288개다. 정확도 차이 102칸 중 **93칸이 한 문서**(`코드2개_급여액_3022033115393304-1.png`)에서 나왔다.

- 이 문서에서 rowmajor는 `투여량`을 비우고 그 뒤 값을 한 칸씩 당겨 넣었다. 예를 들어 `단가` 자리에 `111960`, `선택진료료외` 자리에 `6711`이 들어갔다. 표 전체의 열이 한 칸씩 밀린 것이다. exp README 6절이 경고한 "위치 기반 출력의 구조적 약점"이 참고 텍스트가 있는데도 나타났다.
- 이 문서를 빼면 나머지 58건의 순차이는 약 10~17칸(0.1%p 수준)이다. 다만 문서 단위로 보면 asis가 나은 문서가 19건, rowmajor가 나은 문서가 9건이어서 작지만 asis 쪽으로 기운다.
- 열 뒤바뀜은 두 방식 모두 `공단부담→본인부담`이 대부분이다(asis 22, rowmajor 31). 위치 방식이 이름 비슷한 열에 조금 더 약하다.
- 반대로 rowmajor는 없는 행을 덜 만들었다(초과 행 31→10).

### 4.3 지연과 토큰

- 59건 **모두** rowmajor가 빨랐다. 문서별 지연 비율 중앙값은 0.49, 합계는 2,303초에서 1,122초로 줄었다.
- 최대 지연이 97초에서 37초로 줄었다. 현재 408의 원인인 긴 표 꼬리 지연을 직접 줄이는 효과다.
- 입력 토큰은 같고(약 6.9k), 출력 토큰만 절반이 됐다. 그래서 OpenRouter 비용도 출력 몫만큼 준다.

## 5. 가설 판정

| 가설 | 판정 | 근거 |
|---|---|---|
| H1 지연·토큰 감소 | **채택** | p50·p90·max 모두 약 절반, 59/59건 개선 |
| H2 정확도 유지 | **부분 기각** | 평소에는 거의 같지만(58건 순차이 0.1%p), 드물게 표 전체 열 밀림이 생기고 한 번 나면 그 표가 통째로 틀린다 |

## 6. 한계

- 59건, 1회 실행이다. temperature 0이어도 서버 배치에 따라 결과가 흔들릴 수 있어, 열 밀림 빈도(1/59)는 추정 오차가 크다.
- OCR 텍스트가 40,000자를 넘어 청크가 나뉘는 문서는 이번 표본에 없었다. rowmajor는 문서 전체를 한 번에 호출한다.
- `json_schema`를 provider가 실제로 강제했는지는 확인하지 못했다. 응답은 59건 모두 정상적으로 파싱됐다.
- Docraft 재처리 루프와 하네스 규칙이 열 밀림을 얼마나 잡아내는지는 이번 실험 범위 밖이다.

## 7. 결론과 다음 단계

rowmajor를 그대로 기본값으로 바꾸는 것은 권하지 않는다. 대신 **"rowmajor로 먼저 읽고, 열 밀림이 의심되면 asis로 다시 읽는" 조건부 도입**을 다음 실험으로 제안한다.

1. 열 밀림 검출: Docraft에 이미 있는 행 단위 산식(단가×횟수×일수=총액, 급여 분해 합)과 열 뒤바뀜 검사(`_swap_checks`)로 표 단위 불일치 비율을 계산한다. 이번 결과에서 그 문서가 검출되는지, 정상 58건은 오탐이 없는지 오프라인으로 확인한다.
2. 검출되면 그 표만 asis로 다시 읽는다. 예상 비용은 검출 비율만큼 늘어나는 호출이고, 지연 이득은 대부분 유지된다.
3. 위 조합으로 59건을 다시 돌려 "정확도 손실 0, 지연 −40% 이상"을 통과하면 Docraft에 설정값 하나로 넣는다. 그 뒤 AWS 확인은 배포 담당 세션을 통해 한다.

## 8. 재현

```bash
cd exp-extract-table/.worktrees/ab-docraft
export PYTHONPATH=<requests 설치 경로>        # Docraft venv에 requests가 없다
PY=../../../Docraft/.venv/bin/python
# OCR: ab/ocr_only.py를 Docraft backend 컨테이너 /tmp/ab에 넣고 실행 → ocr/ 가져오기
$PY ab/run_ab.py --arm both --workers 4 --out ../../../e2e/out/ab-rowmajor-1002/full
$PY ab/grade_ab.py --out ../../../e2e/out/ab-rowmajor-1002/full
```
