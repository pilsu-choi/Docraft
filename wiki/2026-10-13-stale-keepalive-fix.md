---
okf_version: "0.2"
type: change
title: 공용 HTTP 클라이언트의 끊긴 keep-alive 연결 재사용 오류 수정
description: 10/13 속도 개선으로 넣은 공용 HTTP 클라이언트가 서버가 막 닫은 keep-alive 연결을 다시 써 "Server disconnected without sending a response"가 났다. 유휴 연결 유지 시간을 2초로 줄이고, 응답 전 끊김은 전송 계층에서 1회 재전송한다(Docraft·harness 공통).
tags: [docraft, harness, httpx, keep-alive, regression, reliability]
status: active
---

날짜: 2026-10-13
브랜치: Docraft `fix/stale-keepalive`(16f9cd5 → dev 3d407d4), harness-v2 `fix/stale-keepalive`(65c0dfb → dev ad26222)
워크트리: 각 저장소 `.worktrees/stale-conn`(병합 후 삭제)
관련: [속도 개선과 L40S 동시 처리 상향](2026-10-13-speed-opt-gpu-concurrency.md), [27B·32B 1장 실측](2026-10-13-qwen27b-vs-32b-1gpu-measure.md)

# 끊긴 keep-alive 연결 재사용 오류 수정

## 증상

- c0 27B 측정(Docraft 5f0bd90, 인터넷 경유 vLLM, 60건·12건 동시)에서 세부내역서 1건이 22초 만에 `httpx.RemoteProtocolError: Server disconnected without sending a response.`(engine.py `_provider` stream, 시한 있는 호출이라 재시도 0회)로 실패. 근거: `exp/e2e_call_test/out/meas1013/c27dp2-full/detail/read_manifest.csv`.

## 근본 원인

- 공용 클라이언트(Docraft 5ceb60f `latency.http_client`, harness `http.shared_client`)가 연결을 재사용한다. httpx 0.28.1 기본 `keepalive_expiry=5.0`, uvicorn(vLLM·Docraft·harness) 기본 `timeout_keep_alive=5` — 같아서 유휴 5초 무렵 재사용 순간 서버가 닫는 경합이 생긴다.
- `HTTPTransport(retries=)`는 연결 실패만 재시도해 이 경우를 막지 못한다.

## 문제 유형과 범위

- "풀링된 HTTP 클라이언트가 서버가 이미 닫은 keep-alive 연결을 재사용". 두 저장소의 장수명 클라이언트는 위 두 개뿐(호출처 Docraft `engine._provider`·`parsers` OCR, harness 임베딩·재분류·재판독·어댑터·parser_fill)이라 둘 다 고쳤다.

## 수정

- `Limits(keepalive_expiry=2.0)` — 서버 keep-alive(5초)보다 짧게.
- `_RetryStaleTransport(httpx.HTTPTransport)`: `handle_request`가 `RemoteProtocolError`·`ReadError`(응답 헤더 전)로 실패하면 1회 재전송. 헤더 이후 끊김·`ReadTimeout`은 재시도하지 않는다. 전송 계층이라 `.post()`·`.stream()`·시한 있는 호출 모두 적용. 추론 요청은 부작용이 없어 재전송해도 안전하다.

## 검증

- 새 테스트 저장소당 8건(Docraft `tests/test_stale_keepalive.py`, harness `tests/unit/test_http.py`): 첫 시도 실패 후 성공(일반·stream), 연속 실패 전파, 헤더 이후 끊김 미재시도, ReadTimeout 미재시도, `keepalive_expiry < 5`.
- 전체 회귀: Docraft 4100 통과·3 xfail, harness 2543 통과·21 실패(기존 NFC·NFD 표본 문제).
- 같은 조건 재측정은 c0에 요청. installer 고정 커밋은 c0가 c1c6af4 위에서 올린다.
