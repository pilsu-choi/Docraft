---
okf_version: "0.2"
type: change
title: 릴리스 전 리뷰 수정 (ephemeral requests·failed 폴더명·비동기 저장·stage 오염·VLM 응답 보존)
description: 고객 패치 전 리뷰에서 나온 5건을 유형 단위로 고쳤다. ephemeral-storage requests 축소와 합계 예산 테스트, failed/ 폴더명 충돌·점 이름, 루프 안 동기 디스크 I/O, 복구된 예외의 stage 오염, VLM 응답 앞 20개만 보존.
tags: [docraft, helm, ephemeral-storage, failures, latency, review]
status: active
---

날짜: 2026-10-15
브랜치: `fix/review-fixes`(GitLab dev ac5ef58 기준)
워크트리: `Docraft/.worktrees/review-fixes`

- **ephemeral-storage requests**: requests 는 스케줄링 예약일 뿐이라 합이 노드 allocatable(고객사 ~38GB)을 넘으면 Pending 이 된다. vLLM·vlm-server 1Gi, vl-api·lines·backend·worker 256Mi 로 줄이고 limits 는 그대로 둔다. 3장 replicas 프로파일 합 6Gi 이하를 `tests/test_failures.py` 가 점검한다(파드 유효 request = max(init, 컨테이너 합) x replicas).
- **failed/ 폴더명**: `<rid 정리본 또는 norid>-<HHMMSS>-<uuid6>`. `.`·`..` 등 점뿐인 이름은 norid. 하네스 rid 는 페이지·재시도마다 같아 덮어쓰기가 나던 문제도 uuid 로 해소.
- **동기 디스크 I/O**: `Call.fail` 은 저장을 단일 워커 스레드(`failures._saver`)에 맡기고 바로 돌아온다(입력 바이트는 snapshot 때 이미 메모리). `snapshot` 은 `asyncio.to_thread`. prune 은 프로세스당 60초에 한 번.
- **stage 오염**: `latency.timed` 가 stage 를 요청 집계(`_stage`)가 아니라 예외 객체(`docraft_stage`)에 붙이고, 실패 한 줄은 원인 사슬에서 읽는다. 안쪽에서 복구된 예외는 나중의 진짜 실패에 영향을 주지 않는다.
- **keep()**: 마지막 20개만 남긴다(링 버퍼) — 긴 요청에서 실패한 호출의 응답이 남는다.
- 검증: `pytest -n 4 -m ''` 4234 passed, 3 xfailed; `helm lint` 통과.
