---
okf_version: "0.2"
type: implementation
title: 작업 세대·부분 추출·스프레드시트 내보내기 무결성 보강
description: 구조 검토 D1·D3·D5의 공유 상태 소유권, 추출 완전성, 실행 문맥 문제를 일반화해 수정한 결과와 회귀 근거
tags: [docraft, integrity, jobs, partial-extraction, export, regression]
status: active
---

날짜: 2026-10-03  
브랜치: `fix/review-integrity` (`dev`의 `120feef` 기반)  
워크트리: `Docraft/.worktrees/review-integrity`

## 근본 원인과 문제 유형

| 검토 | 근본 원인 | 문제 유형·적용 범위 |
|---|---|---|
| D1 | claim은 실행 상태만 검사하고 완료·실패·heartbeat는 문서 ID로만 썼다. 재추출 대기 중에도 이전 result 승인·수정이 가능했다. | 공유 문서 상태를 작업 세대·소유권 없이 갱신. 업로드·재분석·단건/일괄 재추출·복구·리스 인계·취소·수정·승인 전체 수명주기. |
| D3 | CSV/XLSX에 외부 문자열을 그대로 넣어 값과 열 이름이 수식으로 해석됐다. | 문서 문자열을 스프레드시트 실행 문맥에 삽입. 단건/프로젝트 내보내기의 공통 표 응답 계층. |
| D5 | 실패 페이지 그룹을 제외한 행을 병합하면서 실패 횟수만 계측했다. 문서·화면·내보내기·승인이 그 부분성을 알지 못했다. | 부분 성공 결과의 완전성 계약 누락. 여러 페이지 표의 asis/rowmajor·fallback과 후속 검토/내보내기. |

## 변경

- 접수된 큐 메시지에는 `job_generation`을 함께 전달한다. 재분석·재추출은 새 세대를 만들고 기존 결과·승인·취소 표시를 초기화한다. 빈 세대는 기존 첫 작업 메시지 호환을 위한 기본값이며, 새 세대를 접수한 뒤에는 오래된 빈 세대 메시지도 claim하지 못한다.
- 실제 claim마다 `job_owner`를 새로 만든다. 같은 세대에서 죽은 워커의 리스를 인계받아도 이전 워커는 쓰지 못한다. heartbeat와 완료·실패 쓰기는 소유권을 조건으로 하고 단계 경계에서 행 잠금을 잡는다. 취소는 현재 잠근 세대에만 적용한다.
- 검토·승인은 `FOR UPDATE`로 문서 행을 잠근 뒤 `needs_review`/`completed`에서만 허용한다. 단건 추출은 행 잠금, 일괄 추출은 현재 상태 조건부 UPDATE로 중복·경쟁 접수를 거부한다. 세대/소유권은 DB가 권위이며 메모리 Celery revoke는 최선 노력이다.
- `engine.extract(..., completeness=...)`가 전체·표별 성공/실패 페이지를 모은다. provider 오류 외에도 누락·null·비목록·객체가 아닌 표 행 응답을 실패로 분류하고, 유효한 빈 행 목록은 성공으로 구분한다. 모두 실패하면 기존처럼 작업이 실패한다. 부분 성공이면 성공 행을 보존하며 결과에는 명시적으로 `partial=true`를 기록한다.
- 일반 문서는 `completeness`를 DB에 저장하고 문서·목록 응답에 공개한다. 부분 결과는 `partial_extraction` 검증 이슈를 가지며 자동 `completed`와 승인 모두 금지한다. 사람이 다른 필드를 수정해도 부분 이슈는 남는다. 페이지 누락은 leaf 재처리만으로 복구했다고 간주하지 않는다.
- 화면은 실패 페이지 경고, 결과 표의 부분 결과 표시, 승인 버튼 비활성화를 제공한다. `/api/read` diagnostics에도 `table_pages_failed`와 `extraction_completeness`를 남긴다. `table_pages_failed`의 기존 단위는 실패 **묶음 수**다.
- CSV는 수식 시작 문자 `= + - @`, 앞선 공백/제어 문자와 탭·CR·LF 변형 문자열에 작은따옴표를 붙인다. 헤더와 값에 동일 적용한다. XLSX의 모든 문자열 셀은 `s`로 저장하며 숫자 타입의 음수는 숫자로 유지한다. XML에서 금지한 제어 문자는 표시 가능한 `�`로 바꾼다.

## 소비자 계약

```json
{
  "partial": true,
  "pages": [1, 2, 3],
  "successful_pages": [1, 3],
  "failed_pages": [2],
  "tables": {"items": {"successful_pages": [1, 3], "failed_pages": [2]}}
}
```

부분 결과의 단건 JSON 다운로드는 `{result, completeness}`로 감싼다. 완전한 결과의 단건 JSON 다운로드는 기존 결과 객체를 유지한다. 프로젝트 JSON은 문서별 completeness를 추가한다. 부분 CSV/XLSX의 각 행은 `_docraft.partial`과 `_docraft.completeness`를 포함한다. 이 표시를 무시한 무인 적재는 완전성을 보장하지 않는다.

`pages`는 파싱 블록이 포함한 추출 대상 페이지이며, 선택하지 않은 PDF 페이지나 OCR 누락·내용 정확도를 보증하지 않는다. 이전 저장 결과의 기본 `{}`는 미확인이다. 과거 페이지 실패 정보를 새 필드로 복원할 수 없으므로 필요한 문서는 재추출한다. 마이그레이션은 추가 컬럼을 멱등 생성하며 데이터 삭제는 없다. API/워커는 함께 같은 버전으로 배포해야 한다. 이전 코드 워커가 남아 있으면 그 워커의 무조건 UPDATE까지 새 코드가 막을 수 없다.

## 회귀 검증

- 최종 전체 로컬 회귀: **879 passed, 7 warnings, 12.87초** (`../../.venv/bin/python -m pytest tests -q --tb=short`). 실제 PostgreSQL의 테스트 전용 스키마를 사용했다.
- 기존 기대값은 변경하지 않았고 `tests/test_api.py`·`test_projects.py`의 추출 대역 함수에 새 옵션을 받을 인자만 추가했다.
- 신규 `tests/test_integrity.py` 24건: 재분석/리스 인계 후 오래된 파싱 성공·실패(4), 추출/검증 뒤 재분석 성공·실패(4), 오래된 전달/heartbeat(1), 단건/일괄 queued 승인·수정(2), 취소 표시 초기화(1), 수식 문자열/헤더·공백·탭·CR·LF·제어문자·숫자 음수(11), 부분 결과 저장·수정 유지·승인 차단·단건/프로젝트 JSON/CSV/XLSX(1).
- `tests/test_pagewise.py`: 기존 한 페이지 실패 회귀에 정확한 완전성/diagnostics 검증을 추가했다. 신규 여러 페이지 묶음 실패 asis/rowmajor(2), 누락/null/비목록/비객체 행 계약 변형(4), 정상 빈 표(1)를 추가했다.
- frontend TypeScript+Vite 빌드 성공: 동일 소스를 `/tmp`로 복사하고 기존 node_modules를 참조했다. 기존 500kB chunk 경고는 남는다.
- 브라우저 회귀 `tests/ui_integrity.py`: 합성 API 응답으로 실패 페이지 경고·표 부분 표시·부분/queued 승인 차단·완전 결과 승인 활성화를 확인한다. `UI_INTEGRITY_OK`를 확인했다. Chromium 1246의 합성 응답 회귀이며 증거 스크린샷은 `/tmp/docraft-integrity-ui.png`다.
- AWS 배포·실물 모델 호출·새 추론 비용은 발생시키지 않았다. 로컬 대역 테스트는 문서 판독 정확도 측정이 아니다.

## 관련 근거

상위 wiki의 `2026-10-03-harness-docraft-architecture-quality-review.md` D1·D3·D5. 제품 경로는 `backend/main.py`, `backend/db.py`, `backend/engine.py`, `frontend/src/main.tsx`, `frontend/src/ResultsTable.tsx`다. 관련 소비자 설명은 [README](../README.md)에 반영했다.
