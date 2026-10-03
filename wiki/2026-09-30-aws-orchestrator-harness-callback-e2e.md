---
type: experiment
title: AWS 에서 오케스트레이터 ↔ 하네스 비동기 콜백 검증
description: 고객 개발계 투입 전, EC2 에 오케스트레이터·Oracle 을 docker compose 로 띄워 step-callback → 하네스 /v2/jobs(비동기) → harness-callback → 원장 호출까지 실제 코드로 돌린 결과와 발견한 문제(AO 서식 코드 doc_type 미인식)
tags: [orchestrator, harness, callback, aws, docker, e2e]
status: active
---

날짜: 2026-09-30  
브랜치: past-data-aiocr-orchestrator `feat/aws-callback-e2e` (origin/dev `f542821` 기준, push 전)  
워크트리: `past-data-aiocr-orchestrator/.worktrees/aws-callback-e2e`

## 구성

| 항목 | 내용 |
|---|---|
| 위치 | EC2 개발 서버 `/mnt/data/aiocr-e2e`, compose 프로젝트 `aiocr-e2e` (`/opt` 는 ec2-user 쓰기 권한 없음) |
| Oracle | `gvenzl/oracle-xe:11-slim`, 초기화 SQL 은 배포 때 batch 저장소 origin/dev `deploy/local/init` 에서 가져옴 |
| 오케스트레이터 | `Dockerfile`(멀티스테이지) 이미지를 로컬 빌드 → tar 반입. dev 프로파일, `HARNESS_ENGINE_MODE=async` |
| 네트워크 | 하네스 네트워크 `mlife-harness_default` 에 붙음. 제출 `http://mlife-harness-api:9010/v2/jobs`, 콜백 `http://aiocr-orchestrator:8092/ocr/harness-callback/{AIOCR_TRSID}` |
| AO | 실제 demo-ao 콘솔. 계정은 `e2e/bulk_aiocr/aiocr-test.conf` 값 사용 |
| 원장 API | 대신 오케스트레이터 `/ocr/echo-callback` (그래서 8018 은 `030` 으로 남음) |
| 입력 | 2026-09-24 표본 7종의 기존 AO transaction_id — 8018 행을 `020` 으로 넣고 step-callback 호출 |

사용법: `deploy/aws-e2e/README.md` (`deploy.sh` → `run.sh all`).

## 결과

- 7건 모두 JOB `70` 까지 진행. 하네스 대상 6건은 제출 202 → 약 0.2초 뒤 콜백 수신 → 55→60→원장 호출→70.
- 약제비영수증(`Y000707300`, `HRNS_YN=N`)은 하네스를 건너뜀 — 정상.
- **통신·콜백 계약(경로, 본문, 상태 전이)은 문제없음.**

## 발견한 문제 — 하네스가 문서 종류를 못 알아봄

6건 모두 `harness.tier=unresolved`, `fields_verified=0`, `rule_results` 0건, `document_code_source=unknown` → 오케스트레이터 `VLD_SCD=20`(검토필요).

원인:

- 오케스트레이터는 AO 병합 결과를 그대로 보낸다. `result.doc_type` 이 서식 코드(`Y000701200` 등)다.
- 하네스 `normalizer/doc_code.py` `resolve_document_code` 는 한글 유형명(진단서, 진료비영수증 …)으로만 찾는다. 코드 별칭이 없고, AWS 의 `doc_type_mapping` 테이블도 0행이다.
- 9/24 e2e 가 잘 된 것은 `e2e/adapt_aiocr.py` 가 제출 전에 코드를 한글명으로 바꿨기 때문이다. 실제 연동 경로에는 이 변환이 없다.

코드 ↔ 유형명 (`adapt_aiocr.py` 기준):

| 서식 코드 | 하네스 유형명 |
|---|---|
| AC02922011 | 진료비영수증 |
| Y000707100 | 세부내역서 |
| Y000707300 | 약제영수증 |
| Y000701200 | 진단서 |
| Y000701300 | 입원확인서 |
| Y000701333 | 소견서 |
| Y00071250 | 수술확인서 |

**수정(harness-v2 dev `fa68ece`)**: 입력 단계에서 서식 코드를 한글 유형명으로 변환(산출 JSON 은 원본 코드 유지). Docraft 에는 참고용 스키마 예시(`refs/postprocess_schema_example/.../항목리스트.json`)만 있고 실행 매핑은 없었다.

재실행 결과(AWS, 오케스트레이터 경유 6건): 진단서·입원확인서 `repaired`, 수술확인서 `pass`, 소견서·세부내역서·진료비영수증 `unresolved`. 문서 유형 인식·parse 보충 정상.

## 부수 확인

- 하네스 parse 보충 호출이 콘솔 `run_id` 로 AO 를 불러 404 → 영수증·세부내역서 빈 금액 보충(룰 3·4)이 실경로에서 늘 꺼져 있었다. 같은 커밋에서 `aiocr_trsid` 로 부르도록 고침.
- 오케스트레이터는 `tier=pass` 만 `VLD_SCD=00`, 나머지(`repaired` 포함)는 전부 `20`(W-20 어휘 미확정). 결정 필요.
- 오케스트레이터는 하네스에 `X-API-Key` 를 보내지 않는다. 고객 환경에서 하네스 인증(`API_AUTH_MODE=api_key`)을 켜면 제출이 막힌다.
- 콜백 수신 쪽 인증 없음, 하네스는 `callback_url` 을 그대로 신뢰.
