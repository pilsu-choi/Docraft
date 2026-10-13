---
okf_version: "0.2"
type: change
title: 응답 harness.timings — 구간별 소요 시간·Docraft 세부·병목
description: 콜백·결과 JSON의 harness 블록에 timings 키 하나를 추가해, 하네스 단계별 시간(비중·겹침 표시), 대기 시간, 가장 오래 걸린 단계, Docraft 호출별 세부 구간·대기·VLM 호출 수·토큰 합을 한곳에서 보게 했다. 기존 필드는 그대로다.
tags: [harness, docraft, observability, latency, callback, api]
status: active
---

날짜: 2026-10-13
브랜치: harness-v2 `feat/response-timings`(dev 5ef19a2), Docraft `feat/vlm-usage`(dev 3a3100c→977da2c), harness-installer dev 71046fc(고정 커밋); 초 단위 전환 `feat/timings-seconds`(harness dev 76f62a7, installer dev 13daab8)
워크트리: 각 저장소 `.worktrees/timings`·`.worktrees/vlm-usage`(병합 뒤 삭제)
관련: [속도 개선과 L40S 동시 처리 상향](2026-10-13-speed-opt-gpu-concurrency.md), [harness.elapsed_ms 추가](../../harness-v2/wiki/2026-09-28-response-elapsed.md)

# 응답 harness.timings

## 왜

- 요청 단위 시간은 로그(`stage()`·Docraft `read finished`)와 흩어진 필드(`elapsed_ms`, `docraft_reads[].elapsed_ms`)에만 있었다. Docraft 세부 구간은 하네스 결과로 넘어오지 않았고, 대기 시간을 계산해 보여 주는 곳이 없었다.
- 고객사 내부망에서 따로 모니터링 장비 없이 결과 JSON만으로 병목을 보게 한다.

## 모양

```json
"harness": {
  "elapsed_ms": 231400,
  "timings": {
    "total_s": 231.4,
    "queue_wait_s": 1.8,
    "bottleneck": "docraft_read",
    "stages": [
      {"key": "normalize", "name": "② 정규화", "sec": 0.04, "pct": 0.0},
      {"key": "docraft_read", "name": "Docraft 판독", "sec": 205.3, "pct": 88.7},
      {"key": "ao_parse", "name": "AO 표 내려받기", "sec": 2.1, "pct": 0.9, "parallel_with": "docraft_read"}
    ],
    "docraft": [
      {"document_id": "D1", "phase": "reread", "elapsed_s": 205.3,
       "stages_s": {"upload": 0.01, "queue": 0, "parse": 18.5, "extract": 78.0, "post": 0.3, "reprocess": 0, "finish": 0.1, "gap": 6.7},
       "wait_s": {"ocr": 2.5, "vlm": 14.3},
       "vlm": {"calls": 6, "prompt_tokens": 25200, "completion_tokens": 2250}}
    ]
  }
}
```

| 키 | 뜻 |
|---|---|
| `total_s` | `elapsed_ms`의 초 환산(소수 2자리). `timings` 안의 시간은 모두 초 |
| `queue_wait_s` | 비동기 작업: 접수→처리 시작. 동기 API는 `null` |
| `bottleneck` | `stages` 중 가장 오래 걸린 단계 |
| `stages[]` | 실행 순서. 시간은 `sec`. 단계: ①' 서식 재분류, ② 정규화, Docraft 판독(③), AO 표 내려받기, ③ 증거 수집, 규칙 검사, 마스터·임베딩 조회, 재판독 비교, ③' 자가교정, ④ 판정, ④' 대체 읽기, ⑤ 결과 생성. 돈 단계만 싣는다. `parallel_with`가 있으면 다른 단계와 겹쳐 돌았다(그래서 `pct` 합이 100을 넘을 수 있다) |
| `docraft[]` | Docraft 호출 한 건마다. `phase`는 reclassify·reread·fallback |
| `docraft[].stages_s` | Docraft 안 순차 구간. `gap`은 어느 구간에도 안 든 시간(크면 CPU 경합) |
| `docraft[].wait_s` | OCR·VLM 자리 대기. 크면 동시 처리 한도에 걸린 것 |
| `docraft[].vlm` | VLM 호출 수·프롬프트·출력 토큰 합(vLLM `usage`가 없으면 토큰 키는 빠진다) |

## 구현

- harness: `obs/timing.py`(요청 단위 수집기·키→이름 표·`build()`), `stage()`에 `key` 인자, Docraft 클라이언트가 응답 `diagnostics`를 수집기에 넘김. API 계층(`api/app.py`, `api/jobs.py`)에서 응답 직전에 붙인다. `process()` 산출은 그대로(CLI 배치 결과에는 없음). 스키마 선택 속성.
- Docraft: `_provider`가 호출마다 `vlm_calls`, 응답 `usage`의 `vlm_prompt_tokens`·`vlm_completion_tokens`를 더해 `diagnostics`와 `read finished` 로그에 싣는다.
- 결과 JSON이 DB에 저장되므로 지난 작업도 다시 집계할 수 있다.
- 콜백 전송 시간은 콜백 본문에 넣을 수 없어 로그에만 남는다.

## 검증

- harness 전체 회귀: 2510 통과, 21 실패(기존 NFC·NFD 중복 샘플, 변경 전과 같음). 새 테스트 `tests/unit/test_timing.py` 4건, `test_sync_api` 동기·비동기 모양 검사.
- Docraft 전체 회귀 4092 통과, 3 xfail. 새 테스트 `test_provider_counts_calls_and_tokens`(usage 있음·없음·일부).
- 한계: 실제 파이프라인으로 Docraft를 부르는 통합 테스트는 없다(Docraft 응답을 흉내 낸 클라이언트 단위만). AWS 배포 뒤 실제 응답으로 확인한다.

## 남은 일

- 보고서 스크립트(작업 결과의 `timings`를 모아 구간별 중앙값·p90·병목 순위, HTML 한 파일)와 측정 중 vLLM `/metrics`·`nvidia-smi` 수집.
