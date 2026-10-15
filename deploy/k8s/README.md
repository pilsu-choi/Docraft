# Docraft Helm 차트

`helm/docraft`는 harness-installer 우산 차트(별도 저장소)의 서브차트로 쓸 것을 전제로 만들었다. Postgres·Redis는
이 차트가 띄우지 않는다 — harness-v2의 pgvector Postgres(전용 `docraft` DB)와 redis(별도 `QUEUE_NAME`)를 그대로
가리킨다(`externalDatabase.url`, `externalRedis.url`).

## 컴포넌트

| 컴포넌트 | 기본값 | 비고 |
| --- | --- | --- |
| `backend` | 켜짐 | FastAPI, `/api/health`. `DOCRAFT_DATA_DIR=/data`(PVC) |
| `worker` | 꺼짐 | Celery. `queue.backend=celery`일 때만 의미 있다 |
| `frontend` | 꺼짐 | `nginxinc/nginx-unprivileged`(uid 101, 8080번 포트). 이미지에 구운 `backend:8000` 프록시 주소를 ConfigMap으로 실제 Service 주소로 덮는다. Service 외부 포트는 그대로 80 |
| `paddleocrVl` | 꺼짐(GPU) | PaddleOCR-VL 레이아웃 파서. `vlm-server`(vLLM 백엔드)+`api`(paddlex serve) 두 파드 |
| `paddleocrLines` | 꺼짐(GPU 드라이버만) | PP-OCRv5 줄 좌표. `--device cpu` 기본이지만 이미지가 paddlepaddle-gpu라 libcuda 로딩에 GPU 가시성이 필요하다 |
| `vllmVlm` | 꺼짐(GPU) | Qwen3-VL-32B-Instruct vLLM 서버. hostPath 가중치(반입 번들) |

## 값 확인 명령

```bash
helm lint deploy/k8s/helm/docraft
helm template docraft deploy/k8s/helm/docraft \
  --set externalDatabase.url=postgresql://docraft:<pw>@<host>:5432/docraft
```

GPU 컴포넌트는 기본(device plugin 모드, 아래 「GPU 배치」)으로는 `gpu.nodeSelector` 없이도 뜬다 —
`nvidia.com/gpu`를 요청해 스케줄러가 알아서 GPU 노드를 고른다:

```bash
helm template docraft deploy/k8s/helm/docraft \
  --set externalDatabase.url=postgresql://docraft:<pw>@<host>:5432/docraft \
  --set paddleocrVl.enabled=true --set paddleocrLines.enabled=true --set vllmVlm.enabled=true
```

카드 번호를 직접 지정하는 모드(`deviceIds`를 채움)로 바꾸면 `gpu.nodeSelector`가 필수다(비우면
렌더링이 멈춘다 — 아래 「GPU 배치」 이유):

```bash
helm template docraft deploy/k8s/helm/docraft \
  --set externalDatabase.url=postgresql://docraft:<pw>@<host>:5432/docraft \
  --set paddleocrVl.enabled=true --set paddleocrLines.enabled=true --set vllmVlm.enabled=true \
  --set paddleocrVl.deviceIds=0 --set paddleocrLines.deviceIds=0 --set vllmVlm.deviceIds=1 \
  --set gpu.nodeSelector.kubernetes\.io/hostname=<GPU노드>
```

## 외부 VLM(GPU 보류 중 테스트)

`vllmVlm.enabled=false`(기본)인 동안에도 `ai.baseUrl`/`ai.model`로 외부 OpenAI 호환 VLM(별도 호스팅
vLLM, OpenRouter 등)을 가리킬 수 있다. 키는 기존 `auth.aiApiKey`(Secret의 `AI_API_KEY`)를 그대로 쓴다 —
새 Secret 키를 만들지 않는다.

```bash
helm template docraft deploy/k8s/helm/docraft \
  --set externalDatabase.url=postgresql://docraft:<pw>@<host>:5432/docraft \
  --set ai.baseUrl=https://openrouter.ai/api/v1 \
  --set ai.model=qwen/qwen3-vl-32b-instruct \
  --set auth.aiApiKey=<key>
```

`AI_BASE_URL`/`AI_VLM_MODEL`은 `templates/_helpers.tpl`의 `dft.aiBaseUrl`/`dft.aiVlmModel` 한 곳에서만
정해진다(ConfigMap 키 중복 없음). 우선순위: `vllmVlm.enabled=true`면 in-cluster vLLM 주소가 무조건
이기고, 이때 `ai.baseUrl`이나 `ai.model`을 같이 채우면(둘 중 뭐가 실제로 쓰이는지 헷갈리는 대신)
렌더링이 멈춘다 — 외부 VLM을 쓰려면 `vllmVlm.enabled=false`로 두고, in-cluster로 돌아가려면
`ai.baseUrl`/`ai.model`을 비운다.

harness-installer 우산 차트(`charts/mlife-ocr`)의 `docraft.auth.aiApiKey`가 공유 Secret
`mlife-ocr-secret`의 `AI_API_KEY`를 채우는 계약은 그대로 유지된다 — 이 변경은 `auth.aiApiKey`가
아니라 `AI_BASE_URL`/`AI_VLM_MODEL`의 출처만 건드린다.

## GPU 배치 (기본값: L40S 2장)

`paddleocrVl`·`paddleocrLines`·`vllmVlm` 세 컴포넌트 모두 두 방식 중 하나로 GPU를 할당한다
(harness-v2 `mlife-harness` 차트의 `models.embedding.gpuCount`/`deviceIds`와 같은 패턴):

- **device plugin 모드(기본, `deviceIds` 비움)** — `nvidia.com/gpu`를 `gpuCount`장 요청한다.
  스케줄러가 유휴 카드를 골라 주므로 `gpu.nodeSelector`가 없어도 된다. 한 카드를 여러 파드가
  나눠 쓰려면(아래 기본 배치처럼 `paddleocrVl`과 `paddleocrLines`가 GPU0을 공유) device plugin
  time-slicing 설정이 있어야 한다 — GPU 메모리는 격리되지 않으므로 함께 쓰는 컴포넌트의
  `gpuMemoryUtilization` 비율 합이 카드 하나에 들어와야 한다.
- **카드 지정 모드(`deviceIds`를 채움)** — device plugin을 우회한다(harness-v2
  `deploy/k8s/INSTALL.md` §11과 같은 방식). 노드의 `nvidia-container-toolkit`이
  `accept-nvidia-visible-devices-envvar-when-unprivileged=true`여야 하고, `nvidia.com/gpu`를
  요청하지 않으므로 `gpu.nodeSelector`로 노드를 직접 지정해야 한다(비우면 렌더링이 멈춘다).

두 모드 모두 `gpu-check` init 컨테이너가 실제로 보이는 GPU 장수를 확인하고 다르면 멈춘다 — 카드
지정 모드는 toolkit 설정 문제를, device plugin 모드는 time-slicing으로 같은 카드의 복제본만 받은
경우를 짚어 준다(텐서 병렬에서 특히 중요하다).

### MIG로 나뉜 카드(예: 운영계 H200)

device plugin 모드에서 요청할 자원 이름은 컴포넌트마다 `gpuResource`(기본 `nvidia.com/gpu`)로
바꿀 수 있다. 카드가 MIG로 나뉘어 있으면 `nvidia.com/mig-4g.71gb`처럼 조각 이름을 넣어 컴포넌트마다
다른 크기의 조각을 요청한다 — 스케줄러가 카드 사용량을 알아야 여러 컴포넌트를 안전하게 배치한다:

```bash
--set vllmVlm.gpuResource=nvidia.com/mig-4g.71gb \
--set paddleocrVl.gpuResource=nvidia.com/mig-2g.35gb \
--set paddleocrVl.apiGpuResource=nvidia.com/mig-1g.18gb
```

`paddleocrVl`은 `vlm-server`(실제 VLM 추론)와 `api`(paddlex serve, 레이아웃 검출 등 자체 CV
모델도 GPU로 돈다 — CPU 전용 옵션 없음)가 서로 다른 파드라 필요한 조각 크기가 다를 수 있다 —
`apiGpuResource`를 비우면(기본) `gpuResource`를 그대로 따른다. `gpuResource`가
`nvidia.com/mig-`로 시작하면 `gpu-check`도 `nvidia-smi -L`의 GPU 카드 줄 대신 들여쓴 `MIG` 줄
개수를 센다.

기본 배치(카드 지정 모드로 예시):

| GPU | 컴포넌트 | 비고 |
| --- | --- | --- |
| 0 | `paddleocrVl`(vlm-server+api, `deviceIds: "0"`) | harness `bge-m3`(이 차트 밖)와 카드를 나눠 쓴다 |
| 0 | `paddleocrLines`(`deviceIds: "0"`) | 연산은 CPU, 드라이버 주입만 |
| 1 | `vllmVlm`(`deviceIds: "1"`) | Qwen3-VL-32B-Instruct 전용 |

`gpu-memory-utilization`은 값으로 뺐다. `paddleocrVl.gpuMemoryUtilization` 기본 0.25는 L40S 48GB에서 harness
`bge-m3`·`paddleocrLines`와 카드를 나눠 쓰는 것을 감안한 추정치다(compose 기본 0.6은 L4 24GB 단독 사용 기준) —
실측 후 조정 필요(미확정). `vllmVlm.gpuMemoryUtilization` 기본 0.90은 FP8 32B 가중치(약 32GB) + KV cache
여유를 감안한 값이다.

BF16 + 텐서 병렬로 바꾸려면 `vllmVlm.modelDir`을 BF16 가중치 서브디렉터리로, `gpuCount`를 2로(카드 지정
모드면 `deviceIds`를 `"1,2"`처럼 카드 두 장으로) 바꾼다 — `--tensor-parallel-size`는 이 값(또는 `deviceIds`
개수)으로 자동 정해진다(값을 따로 두지 않는다).

한 장에 들어가는 모델(예: Qwen3.8-27B FP8 — L40S 한 장)을 여러 장에 띄울 때는 `vllmVlm.parallel: data`로 카드마다 한 벌씩
띄운다(`--data-parallel-size`, 주소·Service 는 하나 그대로, vLLM 이 요청을 나눠 준다). 벌끼리 통신하지 않아 처리량이 장수에
비례한다. `--max-num-seqs`는 벌마다 적용된다. 기본 `tensor`는 한 벌을 장수로 나눈다(`--tensor-parallel-size`).

운영에서는 `vllmVlm.parallel: replicas`를 쓴다. 카드마다 vLLM 파드를 하나씩 띄우고(파드당 1장, `-vllm-vlm-<n>`), Envoy 라우터
(`-vllm-router`, `images.envoy`)가 처리 중 요청이 가장 적은 파드로 나눠 준다. backend 가 보는 주소(`-vllm-vlm` Service)는 그대로다.

- 한 벌이 멈추거나 재시작·교체돼도 나머지 벌은 계속 받는다(`data`는 파드 하나라 같이 내려간다).
- 라우터는 `/health` 검사로 떨어진 파드를 빼고, 연결 단계 실패만 다른 파드로 다시 보낸다(처리 중 요청은 다시 보내지 않는다).
  요청 기록은 `kubectl logs deploy/<릴리스>-docraft-vllm-router`(응답 코드·소요·보낸 파드), 파드별 집계는 라우터 `:9901/clusters`.
- 파드마다 API 서버가 하나라 vLLM 엔진 상태 로그(`Running`/`Waiting`/`GPU KV cache usage`)가 그대로 찍힌다.
- `resources`·`--max-num-seqs`는 파드마다 적용된다.

모든 방식에 멈춤 감지(`vllmVlm.stallSeconds`, 기본 180초)가 붙는다. 받은 요청이 있는데 처리한 토큰 수가 그 시간 동안 그대로면 liveness
가 실패해 그 파드를 재시작한다(`/health`만으로는 엔진 멈춤을 못 잡는다). 0 이면 `/health`만 본다.

## hostPath 모델 디렉터리 구조 (반입 번들이 채운다)

```
models.volume.hostPath (기본 /opt/docraft/models)/
└── Qwen3-VL-32B-Instruct-FP8/        # vllmVlm.modelDir
    ├── config.json
    ├── *.safetensors
    └── tokenizer*.json
```

`persistence.paddlexModels.hostPath`를 쓰면 PP-OCRv5 줄 좌표 모델 캐시(`$HOME/.paddlex`, 정상적으로는 허브에서
자동 다운로드)도 같은 방식으로 미리 채워야 한다(폐쇄망에서는 자동 다운로드가 안 된다) — 비워 두면 PVC를 새로
만들며, 이 경우 임시 파드를 붙여 `kubectl cp`로 채운 뒤 설치한다.

## 진단·디스크 (2026-10-15)

- **Envoy 접근 로그**(`parallel: replicas`): 한 줄에 `rid=`(backend가 보낸 `X-Request-ID`=`<rid>#<호출번호>`)·`in=`/`out=`(바이트)·`try=`(시도 횟수)·`upstream=`·`fail=`(전송 실패 사유). 응답 헤더 `x-upstream-host`(`%UPSTREAM_REMOTE_ADDRESS%`)로 backend 로그의 `upstream=`이 채워진다. 형식 변경은 `kubectl logs deploy/<릴리스>-docraft-vllm-router`로 확인한다.
- **실패 입력 보존**: `backend.failedKeepDays`(7, 0이면 끔)·`backend.failedMaxMb`(2048) → ConfigMap `FAILED_KEEP_DAYS`·`FAILED_MAX_MB`. 위치는 data PVC의 `/data/failed/`이므로 `persistence.data.size`(기본 10Gi)가 `failedMaxMb`보다 충분히 커야 한다. `backend.vlmSlowMs`는 느린 VLM 호출의 INFO 기준. 자세한 내용은 [루트 README 실패 진단과 재현](../../README.md).
- **디스크**: 모든 컨테이너에 `resources.requests/limits.ephemeral-storage`, 모든 `emptyDir`(shm 제외 메모리 볼륨 포함)에 `sizeLimit`(`ephemeral.tmp` 2Gi·`ephemeral.masterSource` 1Gi)을 둔다. vLLM·PaddleOCR 벤더 이미지는 컨테이너 쓰기층(`~/.cache` 컴파일 캐시·`/tmp`)과 로그가 ephemeral-storage로 잡히므로 한도를 크게(vLLM 30Gi, vlm-server 30Gi) 두었다 — 너무 줄이면 kubelet이 파드를 퇴거시킨다. 노드 `/`의 여유(고객사 L40S 노드 약 38GB)보다 `limits` 합이 크면 안 된다는 점만 지키면 되고, `requests` 합은 노드에서 실제로 예약되므로 0.5배 이하로 유지한다.
- **버전 확인**: `curl <backend>/api/health`의 `version`은 이미지 빌드 인자 `DOCRAFT_COMMIT`(미지정 시 `unknown`). 번들 빌드(`harness-installer/build-bundle.sh`의 `docker build ... backend/Dockerfile`)에서 `--build-arg DOCRAFT_COMMIT=<docraft 커밋>`을 넘겨야 채워진다.

## 알려진 불확실성 (우산 차트에서 확인 필요)

- `paddleocrVl.gpuMemoryUtilization` 기본 0.25: L40S 48GB 실측값이 아니라 추정치다.
- `vllmVlm.modelDir` 기본 `Qwen3-VL-32B-Instruct-FP8`: 실제 배포할 FP8 체크포인트의 정확한 HF 리포·서빙
  이름이 아직 확정되지 않았다 — 반입 번들이 값을 덮어써야 한다.
- `paddleocr-vl-api`가 `vlm-server`를 찾는 주소(`http://paddleocr-vlm-server:8080/v1`)는 PaddleOCR-VL
  이미지의 `pipeline_config_vllm.yaml` 기본값에 고정돼 있어(PaddlePaddle/PaddleOCR 저장소
  `deploy/paddleocr_vl_docker/pipeline_config_vllm.yaml`), `paddleocr-vlm-server` Service 이름을 릴리스
  접두사 없이 고정했다 — 우산 차트에서 같은 네임스페이스에 이 차트를 두 번 이상 설치하면 충돌한다(현재는
  단일 설치만 지원).

## backend·라우터 복제본 (고가용성)

`backend.replicas: 2`, `vllmVlm.router.replicas: 2` 로 한 파드가 죽어도(OOMKilled 등) 서비스가 이어진다(노드가 하나면 파드 수준 이중화). `RollingUpdate`(maxUnavailable 0, maxSurge 1).
`backend.vlmConcurrency`·`ocrConcurrency`·`tablePageConcurrency`·`queue.concurrency` 는 **전체 합계**이고 파드마다 `ceil(합계/replicas)` 가 들어간다. `resources` 는 파드마다다.
작업 선점은 DB 조건부 UPDATE 라 파드가 겹쳐도 한 번만 실행되고, `cancel-all`·`verify_inflight`·같은 페이지 결과 공유는 파드별이다. Postgres 접속은 요청마다 열고 닫으므로 `backend.replicas` × (스레드 40 + 큐 동시성) 만큼 접속 몫이 늘어난다.
