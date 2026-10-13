---
okf_version: "0.2"
type: note
title: harness·Docraft 속도 개선과 L40S 동시 처리 상향
description: GPU가 덜 쓰이는 원인은 앞단 동시 처리 한도(Docraft VLM 8·OCR 2·표 띠 4, vLLM 16)였다. l40s-4·l40s-3 프로파일 한도를 올리고, Docraft 청크 병렬 읽기·HTTP 연결 재사용·위치 찾기 선행 기본 켬, harness HTTP 연결 재사용·③ 판독과 AO 표 내려받기 겹치기를 dev에 반영했다. 실측 전.
tags: [speed, latency, throughput, gpu, l40s, vllm, docraft, harness, installer]
status: active
---

날짜: 2026-10-13
브랜치: Docraft `feat/speed-opt`(dev 4eecef6), harness-v2 `feat/speed-opt`(dev 86fe9d0), harness-installer `feat/concurrency-tuning`(dev 5950313)
워크트리: 각 저장소 `.worktrees/speed-opt`, harness-installer `.worktrees/concurrency`

# harness·Docraft 속도 개선과 L40S 동시 처리 상향

## 원인

- 문서 시간의 대부분은 Qwen 답 생성(디코드)이다. 하네스 자체 계산은 문서당 5~90ms다.
- l40s-4 기준 Qwen TP2의 KV는 약 16.8만 토큰(실제 요청 4~6천 토큰)인데, 앞단 한도가 낮았다: vLLM `--max-num-seqs=16`, Docraft `VLM_CONCURRENCY=8`, `OCR_CONCURRENCY=2`, `TABLE_PAGE_CONCURRENCY=4`.
- 번들의 `docraft-0.1.0.tgz`가 9/28 이후 다시 만들어지지 않아 프로파일의 `vlmConcurrency`가 렌더되지 않았다(`charts/mlife-ocr/charts/`는 gitignore, `build-bundle.sh`의 `helm dependency update`가 다시 만든다).
- 10/12 [Docraft 속도 분석](../../wiki/2026-10-12-docraft-speed-opt.md)의 CPU 낭비(항목명 정규화 캐시, `_plain` 패턴, 줄 OCR 동시 실행, 재처리 기본 끔)는 이미 dev에 반영돼 있었다.

## 변경

| 저장소 | 커밋 | 내용 |
|---|---|---|
| Docraft | df58b33, 5ceb60f → dev 4eecef6 | `_read_chunks` 청크 병렬(`latency.parallel`, 슬롯이 동시 수 제한), 공용 `latency.http_client`, PNG `compress_level=1`, JSON 스키마 검사기 캐시, `BAND_PRELOCATE`·`BAND_SPECULATE` 기본 켬, helm `backend.ocrConcurrency`·`tablePageConcurrency`·`bandPrelocate`·`bandSpeculate` 키 |
| harness-v2 | ce883fe 외 → dev 86fe9d0 | 공용 `http.shared_client()`(프로세스별), ③ 판독과 `_parse_tables`(AO 표 내려받기) 동시 실행. ④'가 ③과 같은 키를 다시 요청하지 않는 것은 이미 구현돼 있어 변경 없음 |
| harness-installer | 0c5113e, a36bd21, 4bb8686, 이후 harness 고정 커밋 → dev 5950313 | l40s-4·l40s-3: vLLM `--max-num-seqs=32`, Docraft VLM 32·OCR 6(api 3개 × 2)·표 띠 8·위치 찾기 선행 켬. Docraft 4eecef6·harness 86fe9d0 고정 |

## 검증

- Docraft 전체 회귀 `pytest -n 8 -m ''`: 4087 통과, 3 xfail.
- harness-v2 전체 회귀: 2506 통과, 21 실패. 실패 21건은 변경 전 dev(453d38e)도 같다. 원인: `docs/agentic-ocr-2.0.1-results/수술확인서`·`입퇴원확인서`에 같은 파일이 NFC·NFD 두 이름으로 함께 커밋돼 있어 1:1 쌍 검사가 깨진다(범위 밖, 남김).
- harness-installer `pytest tests/` 89 통과. `helm template` 두 프로파일 모두 `--max-num-seqs=32`, `VLM_CONCURRENCY=32`, `OCR_CONCURRENCY=6`, `TABLE_PAGE_CONCURRENCY=8`, `BAND_PRELOCATE/SPECULATE=true` 렌더.
- 처리 시간·정확도 실측은 아직 없다.

## 남은 일

- AWS 재배포 후 같은 8건으로 처리 시간·정확도 비교(배포 담당 세션에 요청).
- Docraft 차트: OCR api 파드를 레이아웃 서버와 다른 카드에 둘 수 있게(`paddleocrVl.apiDeviceIds`). l40s-4 GPU1 약 38GB가 비어 있다.
- Qwen 3장 구성: TP3은 헤드 수(64·KV 8) 때문에 불가. 카드 1장 × 데이터 병렬 3(`--data-parallel-size=3`, 서비스 주소 그대로)은 Nebius L40S×4 실측 후 결정.
- 보류: 세부내역서 띠 호출 앞부분 고정(프롬프트 순서 변경), `COMPACT_REPLY`(정확도 회귀 필요), 쪽 렌더 캐시.
