---
type: implementation
title: KCD·EDI 마스터 원본 소스를 harness DB·docraft DB로 재사용
description: data/master(dockerignore 대상)에 갇혀 있던 KCD·EDI 마스터 조회를 harness-v2 Postgres 재사용 → docraft DB 재사용 → 원본 신규 적재 순으로 재구성해 컨테이너·k8s에서도 동작하게 한 구현
tags: [master, kcd, edi, postgres, k8s, helm, deploy]
status: active
---

2026-09-23, 브랜치 `feat/master-source`, 워크트리 `.worktrees/master-source`.

## 배경

`backend/master.py`는 `scripts/build_master.py`가 만든 `data/master/*.csv`를 지연 적재했는데, 그 스크립트는
`/home/pilsu/projects/mirae-assets/harness-v2/docs/requirements/latest`라는 로컬 절대경로 하나만 원본으로
받았고 `data/`는 `.dockerignore`·`.gitignore` 대상이라 컨테이너·k8s에서는 파일이 아예 없어 명칭 교정이
조용히 꺼진 채로 배포되고 있었다. harness-v2는 이미 같은 원본을 Postgres(`code_entry`/`code_system`,
[schema.sql](/home/pilsu/projects/mirae-assets/harness-v2/src/mlife_harness/master/schema.sql))에 적재해
두므로, 같은 인프라(harness-installer 우산 차트, 같은 EC2)에 묶여 배포될 때는 그걸 그대로 읽는 편이
원본을 다시 내려받아 파싱하는 것보다 낫다.

## 소스 해석 순서

`backend/master.py`의 `_rows()`가 프로세스당 한 번(`functools.lru_cache`가 걸린 `_tables()` 안에서) 아래
순서로 처음 성공하는 소스를 쓴다. 공개 API(`code`·`names`·`correct_name`·`ready`)와 `MAX_EDITS`·`EDI_MIN`·
`DRUG_LEN` 상수는 그대로 두어 `backend/rules.py`가 바뀌지 않는다.

1. **harness DB 재사용** — `HARNESS_DATABASE_URL`이 있으면 `SELECT DISTINCT s.family, e.code, e.name FROM
   code_entry e JOIN code_system s USING (system_id) WHERE s.enabled AND s.family IN ('KCD','EDI')`을
   읽기전용으로 실행한다. 연결 실패나 0행이면 경고를 남기고 다음 소스로 넘어간다.
2. **docraft DB 재사용** — Docraft 자체 Postgres의 `master_code(family, code, name)` 테이블(인덱스
   `(family, code)`, `backend/db.py`의 `init_db()`가 다른 테이블과 함께 만든다)에 행이 있으면 그대로 쓴다.
3. **원본 신규 적재** — `MASTER_SOURCE_DIR`이 harness 원본 디렉터리(`KCD_CODE_*.csv`, `수가코드_*.xlsx`,
   `약가_*.tar.gz`, `치료재료_전체_*.tar.gz` — harness `mlife-harness-master` 이미지의 `/opt/master`와 같은
   구성, 파일명은 최신 것을 glob으로 고른다)를 가리키면 `scripts/build_master.py`에 있던 파싱 로직을
   가져와(단가는 버리고 code·name만) 파싱하고, `pg_advisory_xact_lock(hashtext('docraft.master_load'))`로
   감싼 트랜잭션 안에서 비어 있음을 다시 확인한 뒤 `psycopg` `cursor.copy`로 `master_code`에 적재한다(API·
   worker가 동시에 기동해도 한 번만 적재).
4. 셋 다 없으면 빈 테이블 그대로 `ready()`가 `False` — 종전과 같은 조용한 비활성.

`FAMILY`(harness) → Docraft `system` 매핑은 접두사 기준이다: `KCD`로 시작하면 `kcd`, `EDI`로 시작하면
`edi`(수가 7시트·`EDI:약가`·`EDI:치료재료` 등 harness의 EDI 하위 family를 모두 포함). harness DB 질의는
`family IN ('KCD','EDI')`만으로 이미 하위 체계를 다 묶으므로 그대로 두었다.

## 강제 재적재

새 고시 원장이 오면 `python -m backend.master --source <원본 디렉터리>`로 `master_code`를 통째로 다시
채운다(비어 있는지 확인하지 않고 무조건 교체). API·worker 프로세스의 `lru_cache`는 재기동해야 새 내용을
본다.

## 캐시 워밍

첫 요청이 느려지지 않도록 `backend/main.py`의 FastAPI `lifespan`에서 `init_db()` 뒤
`await asyncio.to_thread(master.ready)`로 이벤트 루프 밖에서 미리 채우고, `backend/worker.py`는 Celery
앱을 만들기 전에 동기로 `master.ready()`를 호출한다.

## 설정

| 변수 | 기본값 | 용도 |
|---|---|---|
| `HARNESS_DATABASE_URL` | 빈 값 | harness-v2 Postgres 읽기전용 재사용 |
| `MASTER_SOURCE_DIR` | 빈 값 | harness 마스터 원본 디렉터리(위 둘 다 없을 때만) |

compose(`compose.yaml`)는 `backend`·`worker` 공통 볼륨 앵커 `&master-volumes`에
`${MASTER_SOURCE_HOST_DIR:-./data/master-source}:/master:ro`를 추가했다 — `MASTER_SOURCE_DIR=/master`를
`.env`에 지정하면 그 안의 원본을 읽는다. `HARNESS_DATABASE_URL`은 이미 있는 `env_file: .env` 경로로
그대로 흘러간다(compose `environment:` 블록에 별도로 얹지 않았다). `deploy/aws/.env.aws.example`에도 같은
두 변수의 안내를 추가했다 — harness-v2가 같은 EC2에 떠 있으면 그 Postgres를 바로 가리킬 수 있다.

## Helm

`deploy/k8s/helm/docraft`에 값 두 개를 추가했다.

- `master.harnessDatabaseUrl` — 기존 `auth.existingSecret`/자동 생성 Secret 메커니즘에 `HARNESS_DATABASE_URL`
  키로 들어간다(`DATABASE_URL`·`AI_API_KEY`와 같은 패턴, `dft.appEnv`에 `optional: true` secretKeyRef 추가).
- `master.sourceImage.{repository,tag}` — harness `mlife-harness-master` 같은 이미지를 가리키면 backend·worker
  Deployment 양쪽에 `initContainer`(`cp -r /opt/master/. /master/`)와 `emptyDir` 볼륨 `master-source`가 붙고,
  ConfigMap의 `MASTER_SOURCE_DIR`이 `/master`로 채워진다(비어 있으면 initContainer도, env도 없다). initContainer는
  emptyDir에 쓰기 위해 `containerSecurity(readOnly=false)`를 쓰고, 메인 컨테이너는 그 볼륨을 읽기전용으로 붙인다
  — restricted PSS(`dft.podSecurity`) 안에서도 동작한다.

`dft.image` 헬퍼를 `(dict "ctx" $ "img" <이미지 dict>)` 형태도 받도록 넓혔다(기존
`(dict "ctx" $ "name" "backend")`는 그대로 동작). `helm lint`·`helm template`(GPU 컴포넌트·worker·frontend·
master 소스 이미지 전부 켠 조합 포함)을 통과했다.

## 만든 것

| 파일 | 역할 |
|---|---|
| `backend/master.py` | `_rows()`가 harness DB → docraft DB → `MASTER_SOURCE_DIR` 원본 순으로 해석. `_parse_source`/`_kcd_rows`/`_edi_rows`/`_tar_rows`가 `scripts/build_master.py`의 파싱 로직을 흡수(단가 제외). `reload_from`·`python -m backend.master --source` 강제 재적재 |
| `backend/db.py` | `init_db()`에 `master_code(family, code, name)` + `(family, code)` 인덱스 추가 |
| `backend/config.py` | `master_dir()`/`MASTER_DIR` 삭제 |
| `backend/main.py`, `backend/worker.py` | 기동 시 `master.ready()`로 캐시 워밍 |
| `scripts/build_master.py` | 삭제 — 로직은 `backend/master.py`로 이동 |
| `tests/test_master.py` | `_rows()`를 monkeypatch해 DB 없이 조회·교정·경계 테스트, 원본 파서(csv cp949·xlsx·tar.gz) 단위 테스트 추가; `tests/master_fixture/*.csv` 삭제 |
| `compose.yaml`, `.env.example`, `deploy/aws/.env.aws.example` | `HARNESS_DATABASE_URL`·`MASTER_SOURCE_DIR` 안내, `MASTER_SOURCE_HOST_DIR` 볼륨 마운트 |
| `deploy/k8s/helm/docraft` | `master.harnessDatabaseUrl`(Secret)·`master.sourceImage`(initContainer) values, `_helpers.tpl`의 `dft.image` 확장 |
| `README.md` | 마스터 절을 새 소스 해석 순서로 재작성 |

## 검증

- `python -m pytest tests -q` — 381 passed(실제 Postgres, `DATABASE_URL=postgresql://docraft:docraft@127.0.0.1:5433/docraft`).
- `_load_source`→`master_code` COPY 적재, 두 번째 실행 시 docraft DB 재사용, `HARNESS_DATABASE_URL`이 닿지
  않을 때 다음 소스로 넘어가는 폴백, `python -m backend.master --source`를 실제 Postgres에 대고 수동으로
  확인했다(임시 fixture 파일, 확인 후 `master_code` 원복).
- `helm lint`·`helm template`(기본값, master 값 켠 조합, GPU+worker+frontend 전부 켠 조합) 전부 통과.

## 남은 가정

- harness DB 질의는 `WHERE s.enabled AND s.family IN ('KCD','EDI')`만 걸었다 — 활성 `code_system` 행 전체를
  읽으므로 harness 쪽에서 family 값이 이 둘 밖으로 벗어나면(예: 오탈자) 조용히 빠진다.
- `master_code`에는 unit_price를 두지 않는다(`backend/master.py`가 원래도 명칭 교정에만 쓴다) — 단가가
  필요해지면 이 테이블을 확장하거나 별도 테이블을 둬야 한다.
- k8s에서 `master.sourceImage`를 켜면 매 파드 기동마다 initContainer가 원본을 emptyDir로 복사하고,
  첫 파드가 `MASTER_SOURCE_DIR`에서 파싱해 `master_code`에 COPY한다 — harness의 `master-load` Job처럼
  변경분만 골라 싣는 멱등 재적재는 아니다(비어 있을 때만 적재, 강제 재적재는 CLI로 수동).

## 관련 자료
- [KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md) — 이 문서가 대체한 `scripts/build_master.py` 기반 흐름의 원 구현 기록(교정 규칙 자체는 그대로다)
- [Docraft Helm 차트](2026-09-23-k8s-helm-chart.md) — `deploy/k8s/helm/docraft`의 기존 관례(existingSecret 패턴, restricted PSS)
- harness-v2: `src/mlife_harness/master/schema.sql`, `deploy/k8s/helm/mlife-harness/templates/master-load.yaml`
