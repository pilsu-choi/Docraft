# 백엔드 로깅과 Docker 전체 스택

## 2026-09-21

[[extract-json-parse-failure]]를 조사할 때 서버 로그가 uvicorn access log뿐이어서, 추출이 왜 실패했는지와 VLM이 무엇을 돌려줬는지 확인할 수 없었다.

### 로깅
- `config.setup_logging()`이 `backend` logger 하나만 설정한다. 각 모듈은 `logging.getLogger(__name__)`을 쓴다. `propagate=False`로 두어 uvicorn/root logger와 중복 출력되지 않게 했고, httpx·httpcore·fitz 로그는 WARNING 이상만 남긴다.
- `LOG_LEVEL`은 기본 `DEBUG`다. `LOG_FILE`의 기본값은 저장소 루트의 `docraft.log`(RotatingFileHandler, 10MB × 3개)이고, 빈 값이면 stderr에만 출력한다. `*.log`는 gitignore에 추가했다.
- 레벨별 기록 내용:
  - INFO: 업로드 저장, 분석·추출·스키마 생성의 시작과 종료(소요 시간, 블록 수, 결과 상태), 검토·승인 상태 전환
  - ERROR: 분석·추출·스키마 생성 실패(traceback 포함), provider HTTP 오류와 응답 형식 오류, PaddleOCR 요청 실패, **VLM 응답 JSON 파싱 실패(원본 앞뒤 2000자)**
  - DEBUG: provider 요청 크기와 모델, 응답 원문(앞뒤 2000자), PaddleOCR 요청·응답 크기, DB 접속 host, audit
- API key, Authorization header, DB 비밀번호는 로그에 남기지 않는다.

### Docker
- `backend/Dockerfile`: python:3.12-slim. PyMuPDF·psycopg는 wheel로 설치돼 추가 시스템 라이브러리가 필요 없었다.
- `frontend/Dockerfile`: node:20에서 빌드한 결과를 nginx:1.27로 서빙한다. `frontend/nginx.conf`는 SPA fallback, `/api/` → `backend:8000` 프록시, `client_max_body_size 30m`, `proxy_read_timeout 300s`로 구성했다.
- `compose.yaml`의 `app` profile에 backend와 frontend를 추가했다. `docker compose up -d`는 그대로 postgres만 띄운다. backend는 `.env`(없어도 됨)를 읽은 뒤 DB·데이터 경로·PaddleOCR 주소를 컨테이너 네트워크 값으로 덮어쓰고, `LOG_FILE=""`로 stdout에만 로그를 쓴다.
- 서브에이전트 검증 중 root 컨테이너가 `./data/files`를 root 소유로 만들어 로컬 사용자가 지울 수 없었다. 그래서 backend를 `DOCKER_UID:DOCKER_GID`(기본 1000:1000)로 실행하도록 바꿨다.

## 검증
- 백엔드 테스트 28개 통과. 테스트 중 `docraft.log`에 INFO 흐름, parse 실패 ERROR, JSON decode 실패 ERROR가 기록되는 것을 확인했다.
- `LOG_FILE=`(빈 값)이면 로그 파일이 생기지 않는 것을 확인했다.
- `docker compose config --services`: 기본은 postgres, `--profile app`은 postgres·backend·frontend, `app`+`ocr`은 5개 서비스.
- 개발 스택과 겹치지 않도록 별도 프로젝트(`-p docraft-dockertest`, 포트 5434/8001/3001)로 띄웠다. backend healthy, `/` 200, nginx 경유 `/api/health` 정상을 확인한 뒤 해당 프로젝트만 `down -v`로 정리했다. 테스트 이미지 `docraft-dockertest-{backend,frontend}`는 캐시에 남아 있다.
