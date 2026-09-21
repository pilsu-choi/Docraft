# Docraft

문서를 업로드하고 원하는 스키마로 구조화된 JSON을 만드는 MVP입니다. 현재 범위는 `Upload → Parse → Schema → Extract → Validate/Review → Export/API`입니다.

## 시작하기

Python 3.11 이상과 pip가 필요합니다.

```bash
docker compose up -d
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

프론트엔드는 Node.js 18 이상이 필요합니다. 별도 터미널에서 작업 디렉터리를 연 뒤 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

화면은 `http://localhost:5173`, API 서버는 `http://127.0.0.1:8000`, OpenAPI 문서는 API 서버의 `/docs`에서 확인합니다. `docker compose up -d`는 기본적으로 캐시된 PostgreSQL 16 호환 `pgvector/pgvector:0.8.6-pg16` 이미지를 사용합니다(벡터 확장은 현재 사용하지 않습니다). 다른 이미지는 `POSTGRES_IMAGE`로 지정할 수 있습니다. 테스트는 실제 PostgreSQL의 임시 schema에서 `pytest -q`로 실행하며, 프론트 빌드는 `frontend/`에서 `npm run build`로 실행합니다.

### 로그

백엔드는 `backend` logger로 업로드, 분석·추출 시작과 종료(소요 시간 포함), 상태 전환을 INFO로 남깁니다. 실패는 traceback과 함께 ERROR로 남기고, AI provider 원본 응답(앞뒤 2000자)과 요청 크기는 DEBUG로 남깁니다. 로컬 실행 시 기본값은 `LOG_LEVEL=DEBUG`이고, 콘솔과 저장소 루트의 `docraft.log`(10MB × 3개 회전, git 제외)에 함께 기록합니다. 파일 위치는 `LOG_FILE`로 바꿀 수 있고, 빈 값으로 두면 파일에 쓰지 않습니다. API key와 DB 비밀번호는 기록하지 않습니다.

```bash
tail -f docraft.log
```

### Docker로 전체 스택 실행

```bash
docker compose --profile app up -d --build                 # postgres + backend + frontend
docker compose --profile app --profile ocr up -d --build   # PaddleOCR-VL(GPU) 포함
docker compose logs -f backend
```

화면은 `http://localhost:3000`, API는 `http://127.0.0.1:8000`입니다. frontend의 nginx가 `/api`를 backend로 넘깁니다. backend는 `.env`를 읽되 `DATABASE_URL`, `DOCRAFT_DATA_DIR=/data`(`./data` bind mount), `PADDLEOCR_BASE_URL=http://paddleocr-vl-api:8080`은 컨테이너용 값으로 덮어씁니다. 로그는 파일 없이 stdout으로만 나갑니다. 공유하는 `./data`가 root 소유가 되지 않도록 backend는 `DOCKER_UID`/`DOCKER_GID`(기본 1000) 사용자로 실행됩니다. 호스트 포트는 `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`로 바꿀 수 있습니다. 로컬 개발 서버와 포트 8000이 겹치므로 둘 중 하나만 띄우세요.

`DOCRAFT_API_KEY`를 설정했다면 화면 왼쪽 아래의 `API 키 설정`에 같은 API 키를 입력합니다. 이 키는 브라우저 세션에 저장되고 원문 조회와 다운로드에도 적용됩니다. provider의 `AI_API_KEY`는 서버 전용이며 UI에 입력하지 않습니다.

## OCR 변환 샘플

`samples/agentic-ocr-2.0.1-results/pdf/`에는 UI에서 바로 업로드해 볼 수 있는 의료 문서 PNG 5개의 검색 가능 PDF가 있습니다. 같은 이미지 원본은 `samples/agentic-ocr-2.0.1-results/images/`에 문서 종류별로 보관합니다. PDF는 macOS Vision이 만든 보이지 않는 텍스트 레이어를 포함하므로 현재 `PARSE_PROVIDER=library` 설정에서도 파싱됩니다. 샘플 바이너리는 개인정보 보호를 위해 Git에서 제외됩니다. 생성 방식과 검증 결과는 [wiki/fixture-conversion.md](wiki/fixture-conversion.md)에서 확인할 수 있습니다.

## 화면에서 전체 흐름 실행

1. 홈에서 새 프로젝트를 만들거나 프로젝트 목록에서 기존 프로젝트를 열고, 상세 화면의 문서·스키마 탭에서 작업합니다. 프로젝트 이름은 바꾸거나 삭제할 수 있습니다.
2. TXT/PDF/Office/스프레드시트/이미지 파일을 업로드합니다. 파싱(OCR 포함)이 `parsed`가 된 문서를 하나 이상 선택한 뒤 `스키마` 탭에서 추출할 필드를 설명하고 `AI 스키마 생성`을 누릅니다. 프롬프트는 비워도 되지만 파싱 완료 참조 문서는 필수입니다.
3. 저장된 스키마를 선택하고 `이 스키마로 추출 실행`을 누릅니다. `review` 탭에서 결과·신뢰도·원문 근거를 확인합니다.
   - 문서 분석 결과와 추출 결과는 `Markdown | JSON`, `필드 | JSON` 토글로 전환해 봅니다.
   - 스키마 편집기에서 필드마다 설명을 수정할 수 있고, AI 스키마 생성은 한국어 제목·설명을 우선 생성합니다.
   - 추출 필드에 마우스를 올리면 원문에서 해당 근거 상자가 강조되고, 원문의 근거 상자에 올리면 해당 필드가 강조됩니다.
4. 필요한 값을 수정하고 승인한 뒤 JSON 또는 CSV 내보내기 링크를 사용합니다.
5. `API` 탭에서는 선택한 문서와 스키마에 해당하는 curl 요청 예시를 확인할 수 있습니다.

## API 흐름

1. `POST /api/projects`로 프로젝트를 만들고 `PATCH`/`DELETE /api/projects/{project_id}`로 관리합니다.
2. `POST /api/projects/{project_id}/documents`에 `multipart/form-data`의 `files` 필드로 업로드합니다.
3. `POST /api/projects/{project_id}/schemas`에 JSON Schema를 등록합니다. `PATCH /api/schemas/{schema_id}`는 새 id/버전을 만들며, 문서가 사용한 버전은 삭제할 수 없습니다.
4. `POST /api/documents/{document_id}/extract`에 schema id를 전달해 추출합니다.
5. 결과의 근거와 검증 상태를 확인한 뒤 correction endpoint로 값을 수정합니다.
6. `GET /api/documents/{document_id}/export?format=json|csv`로 JSON 또는 CSV를 내려받습니다.

정확한 요청/응답 모델은 실행 중인 `/docs`를 기준으로 하며, API 키가 필요한 배포에서는 `X-API-Key` 헤더를 사용합니다.

## 처리 모델과 현재 한계

`AI_MODE=local`이면 외부 AI 키 없이 로컬 heuristic 추출을 사용합니다. 기본값은 `provider`이며 이 모드에서는 provider 설정이 없거나 응답이 잘못된 경우 로컬 결과로 조용히 대체하지 않고 오류를 표시합니다. MVP의 로컬 parser는 agentic AI 추론이나 완전한 OCR을 보장하지 않습니다. Office 문서, 복잡한 표, 손글씨 및 비정형 이미지 품질은 배포 전 별도 provider와 평가가 필요합니다.

문서 상태는 queued/parsing/parsed/extracting/validating/completed/failed 계열로 저장되며 업로드와 추출은 BackgroundTasks 기반 비동기로 실행됩니다. `DOCRAFT_API_KEY`를 설정하면 `X-API-Key` 인증이 활성화됩니다. RBAC, webhook, batch API, feedback learning, workflow builder는 후속 범위입니다.

## 설정

`.env.example`의 `DATABASE_URL`, `DOCRAFT_DATA_DIR`, `MAX_UPLOAD_BYTES`, `DOCRAFT_API_KEY`, `CORS_ORIGINS`를 복사해 환경에 맞게 수정합니다. 앱은 `.env`를 자동 로드하며 우선순위는 `DOCRAFT_ENV_FILE` → 현재 작업 디렉터리의 `.env` → 저장소 `.env` → worktree의 원본 checkout `.env`입니다. 처음 발견한 파일 하나만 읽고, 이미 프로세스에 설정된 환경변수는 덮어쓰지 않습니다. 비밀값은 `.env`에만 두고 커밋하지 마세요. 기본 DB는 compose의 PostgreSQL이고 업로드 파일은 `DOCRAFT_DATA_DIR/files/`에 보관됩니다. 기존 SQLite metadata는 원본과 파일을 건드리지 않는 명시적 일회성 도구 `python scripts/migrate_sqlite_to_postgres.py <기존 docraft.db>`로 옮길 수 있습니다.

### OpenRouter provider 설정

OpenRouter의 OpenAI 호환 endpoint를 사용하려면 서버 실행 전에 `.env`에 다음을 설정합니다. 모델은 vision 입력과 구조화된 응답을 지원해야 합니다.

```dotenv
AI_MODE=provider
AI_BASE_URL=https://openrouter.ai/api/v1
AI_API_KEY=<OpenRouter API key>
AI_VLM_MODEL=qwen/qwen3-vl-32b-instruct
```

`AI_VLM_MODEL`이 우선하며 기존 `AI_MODEL`도 호환 alias로 지원합니다. OpenRouter quickstart와 OpenAI structured outputs 안내를 함께 참고하세요: [OpenRouter Quickstart](https://openrouter.ai/docs/quickstart), [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

### 원격 PaddleOCR

기본 `PARSE_PROVIDER=library`는 pypdf/docx/openpyxl 등 기존 라이브러리로 텍스트 문서를 처리하며 이미지 OCR은 비활성화합니다. 선택적으로 로컬 모델 설치 없이 PaddleOCR-VL 전체 layout pipeline을 운영하는 별도 on-prem 서버를 연결할 수 있습니다.

```dotenv
PADDLEOCR_BASE_URL=https://your-paddle-service.example
PARSE_PROVIDER=paddle
PADDLEOCR_ACCESS_TOKEN=<optional bearer token>
PADDLEOCR_MODEL=PaddleOCR-VL-1.6-0.9B
```

#### 로컬 GPU에서 Docker로 호스팅

NVIDIA GPU(Compute Capability 8.0 이상, CUDA 12.6 이상을 지원하는 드라이버)와 NVIDIA Container Toolkit이 있으면 공식 PaddleOCR-VL 이미지를 compose `ocr` profile로 띄울 수 있습니다. 첫 실행 때는 이미지(수십 GB)를 받고 VLM을 올리는 데 몇 분이 걸립니다.

```bash
docker compose --profile ocr up -d
curl http://127.0.0.1:8080/health   # paddleocr-vl-api가 healthy가 되면 사용 가능
```

`.env`에는 `PARSE_PROVIDER=paddle`, `PADDLEOCR_BASE_URL=http://127.0.0.1:8080`을 설정합니다. `paddleocr-vlm-server`(vLLM, PaddleOCR-VL-1.6-0.9B)와 `paddleocr-vl-api`(PP-DocLayoutV3 layout + `/layout-parsing`) 두 컨테이너가 같은 GPU를 씁니다. 12GB GPU 기준으로 `deploy/paddleocr/vllm_config.yaml`의 `gpu-memory-utilization`을 0.5로 낮춰 두었습니다. GPU 번호와 호스트 포트는 `PADDLEOCR_GPU`, `PADDLEOCR_PORT`로 바꿀 수 있습니다. 서빙 모델은 `.env`의 `PADDLEOCR_MODEL` 하나로 정해집니다. compose가 같은 `.env`를 읽어 vLLM `--model_name`과 pipeline의 VL 모델명에 넣고, 앱 상태 표시도 이 값을 씁니다. 바꾼 뒤에는 `docker compose --profile ocr up -d --force-recreate`로 다시 띄웁니다. 응답의 영역별 `block_bbox`는 원문 미리보기의 근거 상자로 표시됩니다.

서비스는 `POST /layout-parsing` 계약을 지원해야 합니다. 설정하지 않은 상태에서 이미지 또는 스캔 PDF를 업로드하면 명시적인 설정 오류가 표시됩니다. 자세한 계약과 근거는 [wiki/paddleocr-compatibility.md](wiki/paddleocr-compatibility.md)를 참고하세요.

## 프로젝트 문서

구현 요구사항과 검증 근거는 [wiki/implementation.md](wiki/implementation.md)에 기록합니다.

검증 결과: 실제 PostgreSQL의 격리된 테스트 schema에서 백엔드 테스트 28개가 통과했고 프론트엔드 빌드도 통과했습니다. 합성 PDF 기반 Chrome E2E는 프로젝트 CRUD, 파싱 후 빈 프롬프트 스키마 생성, 빨간 원문 근거 박스, 패널 접기·펼치기를 검증합니다. 이미지·스캔 OCR은 `ocr` profile의 로컬 PaddleOCR-VL 컨테이너로 합성 영수증 PNG·스캔 PDF 업로드부터 영역 bbox 저장까지 확인했습니다.

원문 미리보기의 너비 맞춤·확대·근거 상자는 오프라인 Chrome 회귀 테스트로 확인할 수 있습니다. `frontend`에서 `npm run dev -- --host 127.0.0.1 --port 5175`를 실행한 뒤 저장소 루트에서 `python tests/ui_preview_layout.py`를 실행하세요. API 응답은 합성 PDF·이미지로 전부 모킹하며 프로젝트 데이터나 AI provider를 사용하지 않습니다. 다른 포트는 `DOCRAFT_UI_URL`로 지정할 수 있습니다.
