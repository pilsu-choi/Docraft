---
type: Implementation Log
title: "프로젝트 작업공간 백엔드 변경 기록"
description: "PostgreSQL 전환, 프로젝트·스키마 CRUD, SQLite 이관 도구 기록"
tags: [backend, postgresql]
status: stable
---

# 프로젝트 작업공간 백엔드 변경 기록

- 데이터베이스를 PostgreSQL로 전환했다. `docker compose up -d postgres`로 로컬 DB를 시작하고 `DATABASE_URL`로 연결한다. 업로드 원본은 기존 `DOCRAFT_DATA_DIR/files`에 둔다.
- 프로젝트 조회·생성에 더해 수정과 삭제를 추가했다. 프로젝트 삭제는 DB의 문서·스키마를 연쇄 삭제하지만 업로드 원본 파일은 임의로 지우지 않는다.
- 스키마 조회·생성·수정·삭제를 지원한다. 수정은 새 스키마 버전을 만들어 기존 문서 결과의 참조 스키마를 보존한다. 문서가 참조하는 버전 삭제는 409로 거부한다.
- 스키마 자동 생성은 파싱/OCR이 성공해 텍스트가 있는 참조 문서 1개 이상을 요구한다. `document_id`와 `document_ids`를 지원하며 프롬프트는 선택 사항이다. 파싱 실패나 대기 중인 원본 이미지에 대한 우회 VLM 호출은 하지 않는다.
- 기존 SQLite 파일은 자동으로 옮기거나 삭제하지 않는다. 이전 데이터가 필요하면 **업무 테이블이 비어 있는 PostgreSQL DB에 한해** `python -m scripts.migrate_sqlite_to_postgres 기존/data/docraft.db`를 명시적으로 실행한다. 기존 감사 로그는 보존하고 SQLite 로그를 추가한다. 원본 업로드 파일은 이전 절대 경로에 그대로 보존하고 `DOCRAFT_DATA_DIR`도 기존 data 디렉터리를 가리키게 해야 파일 조회가 유지된다.
- SQLite 텍스트에 포함된 NUL 바이트는 PostgreSQL이 저장할 수 없어 이관 시 해당 문자만 제거한다. 원본 SQLite는 수정하지 않는다.
- 2026-09-21 기존 `/tmp/docraft-preview-data/docraft.db`의 프로젝트 3건, 문서 4건, 스키마 3건, 감사 로그 17건을 PostgreSQL로 이관했다. 기존 PostgreSQL 감사 로그 5건도 유지되어 총 22건이며, 문서 원본 4개 모두 이전 위치에 존재함을 확인했다.
- 이관된 문서 원본 4개를 저장소의 `data/files`에 복사하고 SHA-256 해시를 검증한 뒤 PostgreSQL의 파일 경로를 갱신했다. 기존 `/tmp` 원본은 보존했다. 무시되는 루트 `.env`의 `DOCRAFT_DATA_DIR`만 절대 경로로 변경해 worktree와 메인 checkout에서 같은 저장소를 사용한다.
