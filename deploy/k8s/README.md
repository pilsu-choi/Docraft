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

## 알려진 불확실성 (우산 차트에서 확인 필요)

- `paddleocrVl.gpuMemoryUtilization` 기본 0.25: L40S 48GB 실측값이 아니라 추정치다.
- `vllmVlm.modelDir` 기본 `Qwen3-VL-32B-Instruct-FP8`: 실제 배포할 FP8 체크포인트의 정확한 HF 리포·서빙
  이름이 아직 확정되지 않았다 — 반입 번들이 값을 덮어써야 한다.
- `paddleocr-vl-api`가 `vlm-server`를 찾는 주소(`http://paddleocr-vlm-server:8080/v1`)는 PaddleOCR-VL
  이미지의 `pipeline_config_vllm.yaml` 기본값에 고정돼 있어(PaddlePaddle/PaddleOCR 저장소
  `deploy/paddleocr_vl_docker/pipeline_config_vllm.yaml`), `paddleocr-vlm-server` Service 이름을 릴리스
  접두사 없이 고정했다 — 우산 차트에서 같은 네임스페이스에 이 차트를 두 번 이상 설치하면 충돌한다(현재는
  단일 설치만 지원).
