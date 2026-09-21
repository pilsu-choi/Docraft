# Docraft

문서를 업로드하고 원하는 스키마로 구조화된 JSON을 만드는 MVP입니다. 현재 범위는 `Upload → Parse → Schema → Extract → Validate/Review → Export/API`입니다.

## 시작하기

Python 3.11 이상과 pip가 필요합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
cp .env.example .env
set -a
source .env
set +a
uvicorn backend.main:app --reload
```

프론트엔드는 Node.js 18 이상이 필요합니다. 별도 터미널에서 작업 디렉터리를 연 뒤 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

화면은 `http://localhost:5173`, API 서버는 `http://127.0.0.1:8000`, OpenAPI 문서는 API 서버의 `/docs`에서 확인합니다. 테스트는 `pytest -q`, 프론트 빌드는 `frontend/`에서 `npm run build`로 실행합니다.

API 키를 설정했다면 화면 왼쪽 아래의 `API 키 설정`에서 입력합니다. 키는 브라우저 세션에 저장되고 원문 조회와 다운로드에도 적용됩니다.

## API 흐름

1. `POST /api/projects`로 프로젝트를 만듭니다.
2. `POST /api/projects/{project_id}/documents`에 `multipart/form-data`의 `files` 필드로 업로드합니다.
3. `POST /api/projects/{project_id}/schemas`에 JSON Schema를 등록합니다.
4. `POST /api/documents/{document_id}/extract`에 schema id를 전달해 추출합니다.
5. 결과의 근거와 검증 상태를 확인한 뒤 correction endpoint로 값을 수정합니다.
6. `GET /api/documents/{document_id}/export?format=json|csv`로 JSON 또는 CSV를 내려받습니다.

정확한 요청/응답 모델은 실행 중인 `/docs`를 기준으로 하며, API 키가 필요한 배포에서는 `X-API-Key` 헤더를 사용합니다.

## 처리 모델과 현재 한계

로컬 개발은 외부 AI 키 없이 동작하는 PDF/이미지/텍스트 기반 parser를 사용합니다. 선택적으로 provider 환경 변수를 설정할 수 있지만, MVP의 로컬 parser는 실제 agentic AI 추론이나 완전한 OCR을 보장하지 않습니다. Office 문서, 복잡한 표, 손글씨 및 비정형 이미지 품질은 배포 전 별도 provider와 평가가 필요합니다.

문서 상태는 queued/parsing/parsed/extracting/validating/completed/failed 계열로 저장되며 업로드와 추출은 BackgroundTasks 기반 비동기로 실행됩니다. `DOCRAFT_API_KEY`를 설정하면 `X-API-Key` 인증이 활성화됩니다. RBAC, webhook, batch API, feedback learning, workflow builder는 후속 범위입니다.

## 설정

`.env.example`의 `DOCRAFT_DATA_DIR`, `MAX_UPLOAD_BYTES`, `DOCRAFT_API_KEY`, `CORS_ORIGINS`를 복사해 환경에 맞게 수정합니다. 현재 앱은 `.env`를 자동 로드하지 않으므로 셸에서 `set -a; source .env; set +a`를 실행하거나 프로세스 실행 환경에 직접 주입해야 합니다. 기본 저장소는 지정한 디렉터리 아래 SQLite와 `files/`입니다. 운영 환경에서는 영속 파일 스토리지와 접근 제어를 별도로 구성합니다.

## 프로젝트 문서

구현 요구사항과 검증 근거는 [wiki/implementation.md](wiki/implementation.md)에 기록합니다.

검증 결과: 백엔드 통합 테스트 7개와 프론트 프로덕션 빌드가 통과했습니다. Chrome에서 신규 프로젝트, 실제 TXT 업로드, 스키마 생성, 추출, 수정, 승인, JSON 다운로드를 일반 모드와 API 키 강제 모드 모두 확인했습니다. 외부 AI 제공자는 실제 키로 검증하지 않았으며, 이미지·스캔 OCR에는 별도 Tesseract 설치가 필요합니다.
