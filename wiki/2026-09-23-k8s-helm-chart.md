---
type: Implementation Log
title: "Docraft Helm 차트 (k8s, GPU 서빙 포함)"
description: "harness-installer 우산 차트의 서브차트로 쓸 Docraft Helm 차트를 harness-v2 mlife-harness 차트를 참고해 만든 기록 — backend/worker/frontend, 외부 Postgres·Redis 연결, PaddleOCR-VL·PP-OCRv5·Qwen3-VL vLLM의 deviceIds 기반 GPU 배치, helm lint/template 검증"
tags: [deploy, k8s, helm, gpu, vllm, paddleocr]
generated: {by: claude-code/claude-sonnet-5, at: 2026-09-23}
status: stable
---

# Docraft Helm 차트 (k8s, GPU 서빙 포함)

- 날짜: 2026-09-23
- 브랜치: `feat/k8s-chart`
- 워크트리: `.worktrees/k8s-chart`

## 배경

고객 폐쇄망 k8s 클러스터에 harness-v2와 함께 Docraft를 올리기 위해, harness-installer 우산 차트(별도 저장소)의
서브차트가 될 `deploy/k8s/helm/docraft`를 만들었다. 참고 기준은 harness-v2의
`deploy/k8s/helm/mlife-harness`(values.yaml 관례, `templates/models.yaml`의 hostPath 모델·`deviceIds` GPU
주입, 보안 컨텍스트, `image.registry` 치환, NOTES.txt, `tests/smoke.yaml`)와 `deploy/k8s/INSTALL.md` §11(GPU·
restricted 네임스페이스)이며, Docraft 쪽 소스는 `compose.yaml`·`deploy/paddleocr/*.yaml`·
`backend/Dockerfile`·`backend/config.py`·`.env.example`이다.

## 차트 구조

```
deploy/k8s/helm/docraft/
├── Chart.yaml
├── values.yaml
├── files/paddleocr/ocr_lines.yaml        # deploy/paddleocr/ocr_lines.yaml 사본(정적, values 무관)
└── templates/
    ├── _helpers.tpl        # dft.* 이름·라벨·이미지·GPU 스케줄링·appEnv 헬퍼
    ├── config.yaml          # ConfigMap(-env) + Secret(-secret, existingSecret 패턴)
    ├── backend.yaml          # PVC(-data) + backend Service/Deployment + worker Deployment(선택)
    ├── frontend.yaml         # nginx Service/Deployment(선택, 기본 꺼짐)
    ├── paddleocr-vl.yaml     # vlm-server + api 두 Deployment/Service
    ├── paddleocr-lines.yaml  # PP-OCRv5 줄 좌표 Deployment/Service + 모델 캐시 PVC/hostPath
    ├── vllm-vlm.yaml         # Qwen3-VL-32B-Instruct vLLM 서버
    ├── NOTES.txt
    └── tests/smoke.yaml      # helm test — /api/health(+켜진 GPU 컴포넌트 /health)
```

## 컴포넌트별 설계

**backend/worker** — compose와 같은 이미지(`backend/Dockerfile`), `/api/health` 하나만 있어(별도
`/readyz` 없음) startup·readiness·liveness 모두 그 경로를 쓴다. `/data`(업로드 원본)는 backend·worker가
PVC로 공유하며, `ReadWriteOnce`면 harness의 `mlh.dataAffinity`와 같은 방식으로 같은 노드에 모은다.
`queue.backend=inline`(기본)이면 worker Deployment 자체를 만들지 않는다.

**DB·큐는 외부 지정** — 이 차트는 Postgres·Redis를 띄우지 않는다(과제 요구사항). `externalDatabase.url`·
`externalRedis.url`을 우산 차트가 harness pgvector Postgres(전용 `docraft` DB)·harness redis(다른
`QUEUE_NAME`)로 채운다. Secret은 harness와 같은 `existingSecret` 패턴(`DATABASE_URL`,
`CELERY_BROKER_URL`, `DOCRAFT_API_KEY`, `AI_API_KEY` 네 키를 한 Secret에 담는다).

**frontend** — 이미지에 구운 `frontend/nginx.conf`가 backend를 `http://backend:8000`으로 고정 프록시한다
(compose 서비스 이름). 이미지를 다시 빌드하지 않고, 실제 backend Service 주소(`<fullname>-backend`)로
바꾼 `default.conf`를 ConfigMap으로 덮어써 릴리스 이름과 무관하게 동작하게 했다. 기본은 꺼짐(우산 차트나
별도 정적 호스팅으로 대체 가능).

**paddleocr-vl(GPU)** — compose의 `paddleocr-vlm-server`(vLLM 백엔드)와 `paddleocr-vl-api`(paddlex
serve)를 그대로 두 Deployment로 옮겼다. 핵심 이슈: `paddleocr-vl-api`가 쓰는 `pipeline_config_vllm.yaml`의
백엔드 주소 기본값이 이미지에 `http://paddleocr-vlm-server:8080/v1`로 박혀 있다(PaddlePaddle/PaddleOCR
저장소 `deploy/paddleocr_vl_docker/pipeline_config_vllm.yaml`, WebSearch로 확인) — compose가 그 이름의
서비스를 쓰는 것과 같은 이유다. 두 컨테이너를 한 Pod에 넣고 포트 충돌(둘 다 8080)을 `--port` 인자로 피하는
방법도 검토했으나, 이미지 밖에서 확정하기 어려운 CLI 인자 가정을 추가하는 대신 **`vlm-server`의 Service
이름을 릴리스 접두사 없이 `paddleocr-vlm-server`로 고정**해 이미지의 기본 설정을 그대로 쓰는 쪽을 택했다
— compose와 정확히 같은 토폴로지라 위험이 적다. `api`에는 compose의 `depends_on
condition:service_healthy`를 initContainer(`curl` 폴링)로 옮겼다.

**paddleocr-lines** — CPU 추론(`--device cpu` 기본)이지만 이미지가 paddlepaddle-gpu라 libcuda 로딩에
GPU 가시성이 필요하다(compose 주석과 같은 이유) — `deviceIds`로 카드를 드라이버만 주입한다. 모델 캐시
(`$HOME/.paddlex`)는 정상적으로는 허브에서 자동 다운로드되는데, 폐쇄망에서는 안 되므로
`persistence.paddlexModels.hostPath`(또는 빈 PVC를 임시로 채우는 절차)로 미리 채워야 한다고 README에
남겼다 — 이 부분은 반입 번들 설계 시점에 다시 확인이 필요하다.

**vllm-vlm(GPU)** — Qwen3-VL-32B-Instruct, harness와 같은 `vllm/vllm-openai:v0.29.0` 이미지를 쓴다.
hostPath 가중치(`models.volume.hostPath` 아래 `vllmVlm.modelDir` 서브디렉터리), `--api-key`는 환경변수
(`VLLM_API_KEY`, harness와 같은 패턴 — 인자로 주면 노드의 `ps`에 보인다)로 Secret의 `AI_API_KEY`를 그대로
쓴다. **`--tensor-parallel-size`는 `deviceIds`의 카드 개수로 자동 계산**해 별도 `gpuCount` 값을 두지
않았다(harness `models.embedding`이 지적한 "두 값을 따로 맞출 일을 없앤다" 원칙을 그대로 적용) — BF16 +
텐서 병렬로 바꿀 때 `deviceIds: "1,2"`, `modelDir`을 BF16 서브디렉터리로, `dtype: bfloat16`만 바꾸면 된다
(helm template으로 렌더링 확인, 아래 검증 절 참고).

**GPU 배치 기본값(L40S 2장)** — GPU0 = `paddleocrVl`(vlm-server+api) + harness `bge-m3`(이 차트 밖) +
`paddleocrLines`(드라이버만), GPU1 = `vllmVlm` 전용. `gpu.nodeSelector`·`gpu.tolerations`·
`gpu.runtimeClassName`을 세 컴포넌트가 공유하고, 컴포넌트별 `deviceIds`로 카드를 나눈다. harness와 달리
device plugin 병행 모드는 두지 않고 **deviceIds 우회 단일 모드**로 단순화했다(과제가 "컴포넌트별
deviceIds"를 명시했고, 코드 간결성 지침과도 맞다) — `gpu.nodeSelector`가 비어 있으면
`dft.requireGpuNode`가 `helm template` 단계에서 바로 멈춘다(harness의 같은 가드와 동일 원리).

## 보안 컨텍스트

backend·worker·smoke 테스트는 harness와 같은 `restricted` 수준(`runAsNonRoot`, uid 10001,
`capabilities: drop ALL`, `allowPrivilegeEscalation: false`)을 적용했다. frontend는 같은 수준이지만
uid 101이다 — 공식 `nginx:*-alpine`(root, 80번 포트)이 `capabilities: drop ALL`에서 CHOWN·SETUID·
SETGID·NET_BIND_SERVICE 없이 크래시루프하는 것을 코드 리뷰로 잡아, 베이스 이미지를
`nginxinc/nginx-unprivileged`(uid 101, 8080번 포트)로 바꾸고 `dft.podSecurity (uid 101 gid 101)`을
적용해 고쳤다(Service 외부 포트는 80 그대로, 컨테이너만 8080). PaddleOCR·vLLM 세 GPU
컴포넌트는 벤더 이미지가 root를 전제로 하므로(compose `user: root`, vLLM은 harness도 같은 전제) 강제하지
않고 `seccompProfile: RuntimeDefault`와 `allowPrivilegeEscalation: false`만 적용했다 — harness
`deploy/models/README.md`의 "비 root 전환은 GPU에서 검증하기 전" 결정을 그대로 따랐다.

## 검증

로컬에 helm 바이너리가 없어 `helm v3.21.0` linux-amd64를 받아 `~/.local/bin`에 설치했다.

- `helm lint --strict` — 통과(icon 권장 INFO 하나뿐).
- `helm template`(기본값) — 통과, `backend`·`ConfigMap`·`Secret`·PVC만 렌더링된다(선택 컴포넌트 전부 꺼짐).
- `helm template`(모든 컴포넌트 켬 + `gpu.nodeSelector` 없이) — `dft.requireGpuNode` fail 가드가 의도대로
  멈춘다.
- `helm template`(모든 컴포넌트 켬 + `gpu.nodeSelector` 지정) — 20개 리소스 렌더링, 이름 중복 없음(YAML
  멀티 문서 파싱으로 확인).
- BF16 + `deviceIds: "1,2"` 오버라이드 — `--tensor-parallel-size=2`·`--dtype=bfloat16`·
  `subPath: Qwen3-VL-32B-Instruct-BF16`로 정확히 반영됨을 확인.
- **버그 발견·수정**: `backend.maxUploadBytes: 26214400`(따옴표 없는 정수)를 `quote` 함수에 통과시키면
  helm의 값 YAML→JSON 왕복에서 float64로 바뀌어 `"2.62144e+07"`로 렌더링되는 문제를 발견했다 — values.yaml에서
  문자열(`"26214400"`)로 고정해 고쳤다. 다른 정수 값(600, 16384 등)은 자릿수가 작아 증상이 없었다.

## 불확실한 부분 (README `알려진 불확실성`에도 남김)

- `paddleocrVl.gpuMemoryUtilization` 기본 0.25(L40S 48GB): compose 0.6(L4 24GB 단독)에서 절대량을 맞추면
  0.3이지만, 같은 카드를 harness `bge-m3`·`paddleocrLines`와 나눠 쓰는 것을 감안해 여유를 더 둔
  추정치다 — 실측 없음.
- `vllmVlm.modelDir` 기본값 `Qwen3-VL-32B-Instruct-FP8`은 과제 지시의 모델명을 그대로 쓴 자리표시자이며,
  실제 배포할 FP8 체크포인트의 정확한 HF 리포·서빙 이름은 미확정이다.
- `paddleocr-lines`의 `.paddlex` 모델 캐시를 폐쇄망에서 사전에 채우는 구체적 절차(반입 번들 쪽 작업)는
  이 차트 범위 밖으로 남겨 뒀다.
- `paddleocr-vlm-server` Service를 접두사 없이 고정한 결정 때문에 같은 네임스페이스에 이 차트를 두 번
  이상 설치할 수 없다 — 우산 차트는 항상 단일 설치이므로 문제 없다고 보지만, 확인이 필요하다.

## 관련 자료

- [harness-v2 mlife-harness 차트](../../../harness-v2/deploy/k8s/helm/mlife-harness) (참고용, 이 저장소 밖)
- [deploy/k8s/README.md](../deploy/k8s/README.md) — 값·GPU 배치·hostPath 구조 요약
