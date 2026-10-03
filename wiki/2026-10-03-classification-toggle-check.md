---
type: guide
title: harness·Docraft 서식 자동분류 끄기 확인
description: 제목 OCR 재분류의 기존 설정과 Docraft 수동 서식 지정 경로 확인
tags: [harness, docraft, classification, configuration]
status: active
---

날짜: 2026-10-03
브랜치: docs/classification-toggle-check (각 저장소 dev 기준)
워크트리: harness-v2/.worktrees/classification-toggle-check, Docraft/.worktrees/classification-toggle-check

## 확인 결과

- harness 제목 OCR 재분류 OFF: `TITLE_OCR_URL=`. ON: 제목 OCR 서버 주소를 다시 지정한다. 설정 적용에는 API·worker 프로세스/컨테이너 재생성이 필요하다.
- 이 설정은 이미지가 있는 비동기 처리의 제목 OCR 확인·서식 재추출을 제어한다. 입력 Agentic OCR이 이미 결정한 `doc_type`은 유지하며, 외부 Agentic OCR 자체 분류를 끄는 설정은 아니다.
- Docraft `/api/read`는 `doc_type`을 필수로 받는다. `/api/verify`는 명시한 서식 또는 AO 결과의 서식을 사용한다. 독립적인 서식 자동분류 토글은 없다.
- Docraft `auto_reprocess=false`는 추출값 복구를 위한 ROI 재읽기를 끄는 옵션이며, 서식 분류 옵션과 다르다.
- 워크스페이스의 AWS 환경 파일에는 `TITLE_OCR_URL=http://paddleocr-lines-api:8080`이 설정되어 있다. 이는 로컬 배포 설정 확인이며 실제 AWS 실행 상태를 조회한 결과가 아니다.

## 근거와 검증

- harness: `src/mlife_harness/config.py`의 `title_ocr_url`, `src/mlife_harness/cli/run_batch.py`의 `build_pipeline`에서 빈 주소일 때 `reclassifier=None` 유지.
- harness: `deploy/local/docker-compose.app.yml`이 TITLE_OCR_URL을 컨테이너에 전달하며 AWS 오버레이도 이 공통 설정을 사용.
- Docraft: `backend/main.py`의 `/api/read`, `/api/verify`; `backend/verify.py`의 서식 선택과 자동 재처리 분기.
- 두 저장소 dev 소스 확인 완료. 코드 변경·외부 모델 호출·AWS 배포·실행 중 설정 변경은 하지 않았다. 테스트 대상 확인 후 해당 환경에 적용한다.
