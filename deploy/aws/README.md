# deploy/aws — AWS 개발 서버

저장소의 `compose.yaml`을 그대로 쓰고, 서버와 다른 점만 `docker-compose.aws.override.yml`로 덮어 EC2에 올린다.
구성은 harness-v2의 `deploy/aws`를 따랐다.

## 서버

harness-v2 개발 서버와 **같은 EC2**를 쓴다.
- 사양: RHEL 9, NVIDIA L4 23GB, RAM 241GB, 64코어.
- 디스크: 루트가 8.8GB라 스택은 데이터 디스크의 `REMOTE_ROOT=/mnt/data/docraft`에 둔다. docker 저장소도 `/mnt/data/docker`에 있다.

harness와 겹치지 않게 다음을 지킨다.
- **포트**: harness가 9010·5433·8124·9001을 쓴다. Docraft는 호스트 포트를 frontend(3000) 하나만 연다. 기본은 루프백이고 SSH 터널로 접근한다.
- **GPU**: harness의 임베딩 vLLM이 약 3.5GB를 쓴다. PaddleOCR vLLM은 `vllm_config.aws.yaml`의 `gpu-memory-utilization: 0.35`(약 8GB)로 줄였다.
- **docker**: `provision.sh`는 아무것도 설치하지 않고 확인만 한다. 공유 서버의 docker를 재시작하면 harness도 같이 내려간다.

## 처음 한 번

```bash
cp deploy/aws/.env.aws.example deploy/aws/.env.aws   # AI_*·DOCRAFT_API_KEY 등을 채운다
deploy/aws/provision.sh                              # 도구 확인, 디렉터리 생성(멱등)
deploy/aws/deploy.sh                                 # 첫 배포는 PaddleOCR 이미지 pull로 오래 걸린다
```

## 평소

```bash
deploy/aws/deploy.sh          # 코드가 바뀌면 재배포(태그 = git 커밋)
deploy/aws/tunnel.sh --bg     # http://localhost:13000 (UI와 /api)
deploy/aws/smoke.sh           # 샘플 5종 파싱 왕복, 표마다 ruled/vlm과 행×열 출력
deploy/aws/logs.sh backend    # 로그
deploy/aws/down.sh            # 정지. GPU를 harness에 돌려줄 때도 이것으로 내린다
```

| 스크립트 | 하는 일 |
| --- | --- |
| `provision.sh` | docker·compose(2.24 이상)·NVIDIA 런타임을 확인하고 `REMOTE_ROOT`를 만든다 |
| `deploy.sh` | backend·frontend 이미지를 로컬에서 빌드해 tar로 반입한다. compose·설정을 전송하고 `--profile app --profile ocr`로 기동한다 |
| `tunnel.sh` | 로컬 `TUNNEL_PORT`(13000)를 서버 frontend로 연결한다(`--bg`/`--stop`) |
| `smoke.sh` | `aws-smoke` 프로젝트에 샘플을 올려 파싱 결과를 확인한다 |
| `logs.sh` / `down.sh` | 로그 / 정지(`--volumes`는 DB까지 삭제) |

## 외부 접근

`.env.aws`에서 바인드 주소를 고른다.

| `FRONTEND_BIND` | 접근 방법 | 비고 |
| --- | --- | --- |
| `127.0.0.1` (기본) | `tunnel.sh`의 SSH 터널 → `http://localhost:13000` | 보안그룹을 건드리지 않는다 |
| `0.0.0.0` | `http://<서버>:3000` 직접 | 보안그룹에서 3000을 열어야 한다. `DOCRAFT_API_KEY`가 비면 `deploy.sh`가 거부한다 |

외부에 열면 UI 왼쪽 아래 `API 키 설정`에 `DOCRAFT_API_KEY`를 넣어야 API가 동작한다. 정적 화면은 키 없이도 보인다.
아직 TLS가 없어 키와 업로드 문서가 평문으로 오간다. 보안그룹 소스 IP를 사내 대역으로 제한하고, 실데이터를 받기 전에 TLS(ALB+ACM 등)를 붙인다.

`AI_API_KEY`(OpenRouter)는 backend 컨테이너 환경변수에만 있다. `/api/health`·`/api/ai/status`는 provider 호스트명과 모델명만 돌려주고, 로그에도 키를 남기지 않는다.

## 주의

- `.env.aws`는 서버에 `.env`로 올라간다. compose 변수와 backend 환경변수를 겸하므로 `AI_API_KEY` 같은 비밀값이 서버에 저장된다. 이 파일은 커밋하지 않는다(`.gitignore`).
- postgres 계정은 `compose.yaml`의 `docraft/docraft` 그대로다. 호스트 포트를 열지 않아 컨테이너 네트워크 안에서만 접근할 수 있다.
- 업로드 파일은 `REMOTE_ROOT/data`에 쌓인다.
- PaddleOCR 모델은 `docraft_paddlex_models` 볼륨에 캐시된다.
