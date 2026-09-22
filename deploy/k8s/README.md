# Docraft Helm 차트

`helm/docraft`는 harness-installer 우산 차트(별도 저장소)의 서브차트로 쓸 것을 전제로 만들었다. Postgres·Redis는
이 차트가 띄우지 않는다 — harness-v2의 pgvector Postgres(전용 `docraft` DB)와 redis(별도 `QUEUE_NAME`)를 그대로
가리킨다(`externalDatabase.url`, `externalRedis.url`).

## 컴포넌트

| 컴포넌트 | 기본값 | 비고 |
| --- | --- | --- |
| `backend` | 켜짐 | FastAPI, `/api/health`. `DOCRAFT_DATA_DIR=/data`(PVC) |
| `worker` | 꺼짐 | Celery. `queue.backend=celery`일 때만 의미 있다 |
| `frontend` | 꺼짐 | nginx. 이미지에 구운 `backend:8000` 프록시 주소를 ConfigMap으로 실제 Service 주소로 덮는다 |
| `paddleocrVl` | 꺼짐(GPU) | PaddleOCR-VL 레이아웃 파서. `vlm-server`(vLLM 백엔드)+`api`(paddlex serve) 두 파드 |
| `paddleocrLines` | 꺼짐(GPU 드라이버만) | PP-OCRv5 줄 좌표. `--device cpu` 기본이지만 이미지가 paddlepaddle-gpu라 libcuda 로딩에 GPU 가시성이 필요하다 |
| `vllmVlm` | 꺼짐(GPU) | Qwen3-VL-32B-Instruct vLLM 서버. hostPath 가중치(반입 번들) |

## 값 확인 명령

```bash
helm lint deploy/k8s/helm/docraft
helm template docraft deploy/k8s/helm/docraft \
  --set externalDatabase.url=postgresql://docraft:<pw>@<host>:5432/docraft
```

GPU 컴포넌트를 켜려면 `gpu.nodeSelector`가 필수다(비우면 렌더링이 멈춘다 — 아래 이유):

```bash
helm template docraft deploy/k8s/helm/docraft \
  --set externalDatabase.url=postgresql://docraft:<pw>@<host>:5432/docraft \
  --set paddleocrVl.enabled=true --set paddleocrLines.enabled=true --set vllmVlm.enabled=true \
  --set gpu.nodeSelector.kubernetes\.io/hostname=<GPU노드>
```

## GPU 배치 (기본값: L40S 2장)

deviceIds로 device plugin을 우회한다(harness-v2 `deploy/k8s/INSTALL.md` §11과 같은 방식) — 노드의
`nvidia-container-toolkit`이 `accept-nvidia-visible-devices-envvar-when-unprivileged=true`여야 하고,
`nvidia.com/gpu`를 요청하지 않으므로 `gpu.nodeSelector`로 노드를 직접 지정해야 한다.

| GPU | 컴포넌트 | 비고 |
| --- | --- | --- |
| 0 | `paddleocrVl`(vlm-server+api, `deviceIds: "0"`) | harness `bge-m3`(이 차트 밖)와 카드를 나눠 쓴다 |
| 0 | `paddleocrLines`(`deviceIds: "0"`) | 연산은 CPU, 드라이버 주입만 |
| 1 | `vllmVlm`(`deviceIds: "1"`) | Qwen3-VL-32B-Instruct 전용 |

`gpu-memory-utilization`은 값으로 뺐다. `paddleocrVl.gpuMemoryUtilization` 기본 0.25는 L40S 48GB에서 harness
`bge-m3`·`paddleocrLines`와 카드를 나눠 쓰는 것을 감안한 추정치다(compose 기본 0.6은 L4 24GB 단독 사용 기준) —
실측 후 조정 필요(미확정). `vllmVlm.gpuMemoryUtilization` 기본 0.90은 FP8 32B 가중치(약 32GB) + KV cache
여유를 감안한 값이다.

BF16 + 텐서 병렬로 바꾸려면 `vllmVlm.modelDir`을 BF16 가중치 서브디렉터리로, `deviceIds`를 `"1,2"`처럼 카드
두 장으로 바꾼다 — `--tensor-parallel-size`는 `deviceIds` 개수로 자동 정해진다(값을 따로 두지 않는다).

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
