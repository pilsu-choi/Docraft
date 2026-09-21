# 구현 기록

## 범위

PRD P0의 Upload, Parse, Schema, Schema 기반 Extract, JSON 결과, grounding, correction, REST API를 검증 대상으로 삼는다. Validation/Export는 MVP 흐름에 포함하되 PRD의 후속 자동 validation agent와 feedback learning은 범위 밖으로 기록한다.

## 요구사항 매핑

| PRD 요구 | 검증 근거 |
| --- | --- |
| 프로젝트 단위 문서 격리 | 다른 프로젝트의 document/schema id 사용 시 404 또는 오류 응답 테스트 |
| 업로드 및 파일 검증 | 지원 확장자 업로드, 빈 파일/지원하지 않는 파일 차단 테스트 |
| Parse 결과 | 문서 상태와 markdown/blocks 응답 확인 |
| Schema 등록/불일치 방지 | 유효 schema 등록, 다른 project schema로 extract 차단 |
| Schema 기반 Extract | 등록 필드와 문서 텍스트에서 JSON 결과 생성 |
| Grounding | 결과 필드의 source text/page/bounding metadata 확인 |
| Human correction | 값 수정 후 history 또는 최신 결과 반영 확인 |
| Export | JSON/CSV 응답 형식 및 내용 확인 |
| 비동기 처리 | 처리 상태 endpoint와 unsupported/실패 상태 확인 |

## 테스트 원칙

테스트는 임시 SQLite와 임시 upload directory를 사용하여 실행 순서와 개발자 로컬 데이터에 의존하지 않는다. 각 시나리오는 project id를 통해 격리를 확인하고, 유효한 실제 PDF를 최소 fixture로 생성하거나 plain text fixture를 사용한다. API 계약이 확정되면 `tests/`의 integration fixture에서 app dependency를 재정의한다.

## 모델 배분

오케스트레이션은 astra가 담당하고, 저장소 파악·테스트 작성·코드 생성은 작업 성격에 맞춰 sol/terra/luna 계열 모델로 분배한다. 모델 이름은 제품 기능에 노출하지 않으며, 외부 provider 없이도 local parser로 개발 및 테스트가 가능해야 한다.

## 갱신 규칙

엔드포인트, 상태명, 환경변수 또는 테스트 결과가 바뀔 때 이 기록과 README의 API 흐름을 함께 갱신한다.

## 2026-09-21 검증 기록

`tests/test_api.py`에 P0 통합 시나리오 7개를 추가했다. 임시 `DOCRAFT_DATA_DIR`를 프로세스 시작 전에 설정하고, 실제 BackgroundTasks 처리 결과를 polling하여 비동기 상태도 검증한다. `pytest -q` 결과는 7 passed이며, `compileall`과 `git diff --check`도 통과했다. Starlette TestClient의 lifespan을 직접 사용하지 않는 환경에서도 테스트 DB가 초기화되도록 fixture에서 `init_db()`를 호출한다.

존재하지 않는 schema id와 잘못된 JSON Schema 입력에 대한 오류 응답은 통합 테스트를 통과했다.

초기 프론트 빌드에서 발견한 JSX 문법 오류와 Vite 플러그인 버전 충돌을 수정했다. 최종 TypeScript 검사와 프로덕션 빌드는 통과했다.

## 2026-09-21 프런트엔드 구현 기록

`frontend/`에 Node 18 호환 Vite 5 + React TypeScript 작업공간을 추가했다. 좌측 프로젝트 탐색, 다중 파일 드롭 업로드, 문서 상태 폴링, 원본 PDF/이미지와 Markdown·Blocks 보기, AI/JSON Schema 편집과 버전 선택, 추출, grounding 기반 split review, 수정·승인, JSON/CSV export, 실제 REST API 예제를 제공한다. 중첩 결과와 배열은 JSON 문자열로 렌더링·편집하여 객체 렌더링 오류가 나지 않게 했다.

프런트 API client는 `/api` same-origin proxy를 통해 backend의 projects, documents, schemas, parse, extract, review, approve, export contract를 사용한다. 업로드 선택 목록은 PDF, 이미지, DOCX, XLSX, CSV, TXT, Markdown이다. API example은 선택적 `X-API-Key`, multipart `files`, extract 요청, document polling 흐름을 명시한다. API 키는 브라우저 세션 저장소에만 보관하며, 원본 파일과 export도 인증 헤더를 포함한 fetch와 임시 Blob URL로 조회한다.

검증: 의존성은 `@vitejs/plugin-react` 4.x로 Vite 5와 정합화했고 React 타입 패키지를 추가했다. `npm run build`는 TypeScript 검사와 Vite production build를 통과했다(31 modules). 중복 API 패널을 제거하고 인증된 Blob 다운로드를 적용했다.

## 최종 통합 검증

- 백엔드 `pytest -q`: 7 passed, TestClient 의존성 폐기 예정 API 경고 1건.
- 프론트 `npm run build`: 통과.
- Chrome 일반 모드와 API 키 강제 모드: 신규 프로젝트 → 실제 TXT 업로드/파싱 → 스키마 생성/선택 → 추출 → 이름을 Janet Doe로 수정 → 승인 → JSON 다운로드 통과. 다운로드 내용을 파싱해 수정값을 확인했다.
- 재현 스크립트: `tests/ui_smoke.py`. 테스트용 서버는 종료했다.
- PDF/DOCX/XLSX 파싱, 중첩 표 배열 및 검증 실패 후 수정/승인 점검의 상세 근거는 `backend-implementation.md` 참조.
- 외부 AI 제공자 실호출과 Tesseract OCR은 환경에 키/실행 파일이 없어 검증하지 않았다. 로컬 추출은 휴리스틱이며 일반 문서에서 AI 추론 품질을 보장하지 않는다.
- RBAC, webhook, 고급 validation agent, feedback learning 등은 후속 범위로 남는다.
