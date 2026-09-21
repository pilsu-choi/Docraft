# 프로젝트 작업공간 테스트 기록

## 목적

프로젝트 홈/상세 CRUD, PostgreSQL 전환, 스키마 버전 격리, 자동 스키마 생성의 파싱 완료 조건, PDF grounding 좌표를 실제 PostgreSQL 기반 통합 테스트로 검증한다. 테스트 입력은 합성 TXT와 런타임 생성 PDF만 사용하며 의료 원문이나 provider 비밀값을 기록·전송하지 않는다.

## 격리 방식

`tests/conftest.py`는 `DOCRAFT_TEST_DATABASE_URL`(미지정 시 로컬 compose URL)에 연결해 매 pytest 실행마다 무작위 PostgreSQL schema를 만든다. 앱의 `DATABASE_URL`에는 그 schema의 `search_path`를 넣고, 종료 시 `DROP SCHEMA ... CASCADE`로 정리한다. 따라서 SQLite 대체나 개발 데이터 공유 없이 foreign key cascade와 project/schema 범위를 검증한다.

## 검증 항목

- 프로젝트 이름/설명 수정과 삭제 시 documents·schemas의 PostgreSQL cascade
- 같은 스키마 이름의 프로젝트별 v1 및 PATCH에 의한 새 v2 생성
- 사용 중인 스키마 버전 삭제 차단
- 자동 생성은 참조 문서가 없으면 422, 다른 프로젝트 참조 또는 failed 문서면 409, parsed TXT 참조와 빈 프롬프트면 성공
- PyMuPDF가 만든 합성 PDF의 bbox가 비퇴화 사각형이며 페이지 크기 안에 있어 화면의 백분율 red overlay에 사용할 수 있음

## 실행

```bash
docker compose up -d
.venv/bin/python -m pytest -q
```

## 실행 결과 (2026-09-21)

`docker compose`의 PostgreSQL 16 컨테이너에 연결해 `.venv/bin/python -m pytest -q`를 실행했다. 결과는 **26 passed**다. 경고는 PyMuPDF/Starlette의 외부 의존성 deprecation 경고이며 테스트 실패는 없었다. `frontend/`에서 `npm run build`도 통과했다.

추가로 SQLite 이관 도구는 임시 schema에서 검증했다. audit log만 있는 대상은 보존한 채 이관되고, projects/documents/schemas/corrections 중 데이터가 있는 대상은 즉시 중단되어 중복 이관하지 않는다.

Chrome E2E는 `docraft_e2e` 임시 schema와 합성 PDF(`Vendor: Synthetic Co`, `Amount: 1200`)로 실행했다. 홈 생성 → 원문 패널 접기/재개방 폭 변화 → PDF 업로드/파싱 → 실제 PDF bbox의 빨간 overlay → Schema 탭의 미저장 prompt 유지 → 작업 패널 접기/재개방 → **빈 프롬프트와 파싱 완료 문서로 실제 OpenRouter 스키마 생성** → v2 저장 → 추출 → 결과 수정 → JSON 다운로드 → 다른 패널을 접을 때 한 패널은 열린 상태 유지 → 프로젝트 목록 rename/delete를 확인했다. 결과는 `UI_PROJECT_WORKSPACE_OK`이며 스크린샷은 `/tmp/docraft-project-workspace-e2e.png`에 남겼다. 실제 고객/의료 원문은 사용하지 않았다.

NUL 문자 포함 레거시 SQLite 텍스트도 PostgreSQL 이관 전에 NUL만 제거하고 나머지 문자열을 보존하는 회귀 테스트를 추가해 통과했다(`tests/test_sqlite_migration.py`: 3 passed).
