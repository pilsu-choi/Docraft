---
type: Implementation Log
title: "/api/verify 연결 끊김 중단과 AWS 배포 잠금·처리 중 검사"
description: "0922 재테스트에서 드러난 두 운영 문제를 고친 기록: 클라이언트가 끊겨도 LLM 호출을 계속하던 /api/verify를 단계 사이에서 멈추게 하고, 여러 세션이 공유 서버에 동시에 배포하던 문제를 잠금·배포 기록·처리 중 거부로 막았다. 필수 필드에서 납부할금액을 뺀 조정 포함"
tags: [backend, verify, deploy, aws, ops]
generated: {by: claude-code, at: 2026-09-23}
status: stable
---

# /api/verify 연결 끊김 중단과 AWS 배포 잠금

- 날짜: 2026-09-23
- 브랜치: `fix/verify-ops`(코드), `docs/verify-ops`(이 기록)
- 워크트리: `.worktrees/verify-ops`, `.worktrees/verify-ops-doc`

[required-fields](2026-09-23-required-fields.md)의 AWS 재테스트에서 나온 후속 작업이다.

## 필수 필드 조정 (`f0633cf`)

진료비영수증 `required`에서 `납부할금액`을 뺐다. 예전 요양급여 서식에는 그 칸이 없어서, 재테스트에서 이 필드가 걸린 3건 중 2건이 칸 없는 서식이었다. 그중 1건은 Judge가 환자부담총액을 베껴 넣었다.

## 클라이언트가 끊기면 `/api/verify`를 멈춘다 (`5269f07`)

- **문제:** 클라이언트(harness-v2, SSH 터널 너머의 테스트 스크립트)가 끊겨도 서버 스레드는 파싱 → 추출(VLM) → Judge(LLM)를 끝까지 돌았다. 재테스트 중 터널이 두 번 끊겼을 때 남은 요청이 서버를 수 분씩 붙잡았다.
- **라우트 쪽:** `verify.run`을 태스크로 돌리고, 1초마다 `request.is_disconnected()`를 확인한다. 끊겼으면 `threading.Event`를 세운다. 처리가 멈추면 `verify: cancelled (client disconnected)`를 로그에 남기고 499를 돌려준다.
- **`verify.run` 쪽:** 선택 인자 `cancel`을 받는다. 파싱 뒤 추출 전, 그리고 Judge 전에 확인해서 세워져 있으면 `verify.Cancelled`를 던진다. 인자가 선택이라 기존 호출자는 그대로 동작한다.
  - 파싱 중에 끊기면 추출·Judge 호출을 둘 다 아낀다.
  - 추출 중에 끊기면 Judge 호출을 아낀다.
  - 이미 진행 중인 호출은 끝까지 간다.
- **일반 추출 작업은 해당 없다.** `/api` 추출 작업은 큐와 worker로 돌아서, 요청 연결과 상관없이 이미 따로 처리된다.
- **서버 실측:** 클라이언트를 25초에 끊었다. 서버는 파싱(표 보정 65초 포함)이 끝난 89.9초에 `cancelled`를 남기고 멈췄고, 추출·Judge 호출은 일어나지 않았다.
  - 로그의 `doc_type=None`은 폼에서 유형을 주지 않았다는 뜻이다(AO 안의 유형을 쓰는 요청).

## 배포 잠금·배포 기록·처리 중 거부 (`5d38311`)

- **잠금:** 배포하는 ssh 세션이 서버의 `/mnt/data/docraft/deploy.lock`에 `flock -n`을 잡는다. 빌드 전부터 스크립트가 끝날 때까지 쥐고 있고, 잡은 쪽 정보를 파일에 적는다. 두 번째 배포는 누가 잡고 있는지 보여 주고 exit 3으로 멈춘다.
- **배포 기록:** `/mnt/data/docraft/DEPLOYED`에 `revision=… time=…Z by=user@host branch=…`을 남긴다. 배포를 시작하면 직전 기록부터 출력한다.
- **처리 중 거부:**
  - backend health에 `verify_inflight`(처리 중인 `/api/verify` 수)를 더했다.
  - `deploy.sh`는 빌드 전과 교체 직전에 이 값을 확인하고, 0보다 크면 배포를 거부한다. `DEPLOY_FORCE=1`이면 강제로 진행한다.
  - health에 닿지 못하거나, 필드가 없는 옛 backend면 0으로 본다.
- **`tunnel.sh`:** 전에는 명령줄 패턴(`pgrep -f`)으로 터널을 찾아 끊어서, 다른 세션의 터널까지 끊을 수 있었다. 이제 포트별 ssh 제어 소켓(`/tmp/docraft-tunnel-<port>.sock`)으로 자기 터널만 연다.
- **서버 실측:**
  - `bbd1aeb`를 배포해 `DEPLOYED` 기록이 남는 것을 확인했다.
  - 요청 1건을 처리하는 중에 `deploy.sh --no-build`를 실행했다. 직전 배포 기록을 출력하고 "처리 중 1건"으로 exit 3을 냈다.
  - 제어 소켓 터널은 서버에서 직접 확인하지 않았다(검증에는 서버 안에서 curl을 썼다).

## 테스트

- 438 passed.
- 새로 추가한 테스트:
  - 추출 중에 취소 신호를 세우면 Judge가 호출되지 않는다.
  - 라우트가 연결 끊김에 499를 돌려주고, 끝난 뒤 `verify_inflight`가 0으로 돌아온다.
- shellcheck는 설치할 수 없어서 `bash -n`만 돌렸다.

## 남은 한계

- 파싱(PaddleOCR, 표 보정)은 도중에 멈추지 못한다. 문서 한 장에 최대 90초쯤 GPU를 계속 쓴다.
- 잠금과 처리 중 검사는 이 저장소의 `deploy.sh`를 거쳐 배포할 때만 적용된다. 서버에서 compose를 직접 다루면 적용되지 않는다.
