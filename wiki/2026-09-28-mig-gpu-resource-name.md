---
type: Implementation Log
title: "MIG 자원 이름 선택: 컴포넌트마다 다른 nvidia.com/mig-* 요청"
description: "helm/docraft 차트의 GPU 컴포넌트(paddleocrVl vlm-server·api, paddleocrLines, vllmVlm)가 device plugin 모드에서 요청하는 자원 이름을 nvidia.com/gpu 고정 대신 값으로 뺀 기록 — 운영계 H200이 MIG로 나뉠 때 컴포넌트마다 다른 조각을 요청하도록"
tags: [helm, k8s, gpu, mig, docraft, device-plugin]
status: stable
---

# MIG 자원 이름 선택: 컴포넌트마다 다른 nvidia.com/mig-* 요청

- 날짜: 2026-09-28
- 브랜치: `feat/gpu-resource`
- 워크트리: `.worktrees/gpu-resource`

## 배경

[GPU 할당 방식 이원화](2026-09-26-GPU-할당-방식.md)로 device plugin 모드가 `nvidia.com/gpu`를
`gpuCount`장 요청하도록 구현했지만, 자원 이름은 헬퍼(`dft.gpuResources`)에 `nvidia.com/gpu`로
고정돼 있었다. 고객 운영계 H200 한 장이 MIG로 나뉘면 스케줄러는 `nvidia.com/gpu`가 아니라
`nvidia.com/mig-4g.71gb`처럼 조각별 자원 이름으로 요청을 받는다 — 컴포넌트마다 다른 크기의 MIG
조각을 쓰게 하려면 이 이름을 컴포넌트별 값으로 뺄 필요가 있었다.

## api 파드 GPU 필요 여부 확인

작업 전에 `paddleocr-vl-api`(paddlex serve)가 실제로 GPU가 필요한지 먼저 확인했다. `paddleocr-lines`는
`--device cpu`를 명시적으로 주는데(연산은 CPU, `paddlepaddle-gpu` 이미지의 libcuda 로딩 때문에
GPU 가시성만 필요), `paddleocr-vl-api`의 실행 커맨드(`paddleocr-vl.yaml`)에는 그런 `--device` 지정이
없다. PaddleOCR 저장소의 `deploy/paddleocr_vl_docker/pipeline_config_vllm.yaml`(WebFetch로 확인)에도
device 설정이 없다 — VLM 인식만 `genai_config`로 `vlm-server`에 위임하고, 문서 방향 분류
(`DocOrientationClassify`)·왜곡 보정(`DocUnwarping`)·레이아웃 검출(`LayoutDetection`,
PP-DocLayoutV3)은 api 컨테이너 자신이 돌린다. 이 서브모듈들은 CV 모델이라 GPU가 보이면 기본으로
GPU를 쓴다. **결론: api 파드는 현재 CPU 전용 옵션이 없고, VLM 인식 외의 자체 CV 추론 때문에 실제로
GPU가 필요하다** — 다만 vlm-server보다 훨씬 가벼운 모델만 돌리므로 더 작은 MIG 조각으로 충분할 수
있다.

## 구현

`templates/_helpers.tpl`:

- `dft.gpuResources` — `nvidia.com/gpu` 고정 키 대신 `.gpu.gpuResource | default "nvidia.com/gpu"`로
  requests·limits 키를 계산한다.
- `dft.gpuCheck` — 자원 이름이 `nvidia.com/mig-`로 시작하면(`hasPrefix`) `nvidia-smi -L`에서
  `^GPU ` 줄이 아니라 `MIG ` 줄 개수를 센다(MIG 카드는 `GPU n: ...` 아래 들여쓴 `  MIG ...` 줄로
  조각을 나열한다). 최소 변경으로 `grep -c` 패턴만 조건부로 바꿨다.

`values.yaml`:

- `paddleocrVl.gpuResource`(기본 `nvidia.com/gpu`) — `vlm-server`·`api` 공통 기본값.
- `paddleocrVl.apiGpuResource`(기본 빈 문자열, 비우면 `gpuResource`를 따름) — api만 다른 조각을
  쓸 때. 중복 의미의 새 키(예: `vlmServerGpuResource`)는 만들지 않았다 — `gpuResource`가 이미
  vlm-server의 기본값 역할을 겸한다.
- `paddleocrLines.gpuResource`·`vllmVlm.gpuResource` — 각각 기본 `nvidia.com/gpu`.

`templates/paddleocr-vl.yaml`의 api Deployment에서만 로컬 변수
`$papi := merge (dict "gpuResource" (default $p.gpuResource $p.apiGpuResource)) $p`로 자원 이름을
덮어쓴 dict를 만들어 그 Deployment의 `gpuCheck`·`gpuEnv`·`gpuResources` 호출에 쓴다(`deviceIds`·
`gpuCount`는 `$p`와 동일하게 유지 — merge는 dst에 없는 키만 src에서 채우므로 `gpuResource`만
바뀌고 나머지는 그대로 상속된다). `paddleocr-lines.yaml`·`vllm-vlm.yaml`은 원래도 컴포넌트 dict
(`$l`/`$v`)를 그대로 헬퍼에 넘기므로, `values.yaml`에 `gpuResource`를 추가한 것만으로 자동 반영됐다
— 템플릿 수정이 필요 없었다.

`deploy/k8s/README.md`의 「GPU 배치」 절에 "MIG로 나뉜 카드" 소절을 추가해 세 값 조합 예시와
`api`/`vlm-server` 분리, `gpu-check`의 MIG 카운트 전환 조건을 설명했다.

## 검증

`helm`(v3.21.0)으로 `helm lint`와 `helm template` 3가지 케이스를 확인했다.

1. **기본값(GPU 끔)** — `externalDatabase.url`만 채우고 렌더링, GPU 관련 자원·env 없음(6개
   리소스만 렌더링).
2. **카드 지정 모드**(`deviceIds` `"0"`/`"0"`/`"1"` + `gpu.nodeSelector`) — `--set-string`으로
   줘야 Sprig `default`가 정수 `0`을 "빈 값"으로 오인하지 않는다(기존 GPU 할당 방식 문서에도 있는
   전제와 동일, 이번에 새로 생긴 문제는 아니다). `NVIDIA_VISIBLE_DEVICES`만 있고 `nvidia.com/gpu`
   자원 요청은 없음(허용 리스트인 tolerations의 `key: nvidia.com/gpu`만 등장).
3. **리소스 모드 + MIG**(`vllmVlm.gpuResource=nvidia.com/mig-4g.71gb`,
   `paddleocrVl.gpuResource=nvidia.com/mig-2g.35gb`,
   `paddleocrVl.apiGpuResource=nvidia.com/mig-1g.18gb`, `paddleocrLines` 꺼짐) — `vlm-server`는
   `mig-2g.35gb: 1`, `api`는 `mig-1g.18gb: 1`, `vllm-vlm`은 `mig-4g.71gb: 1`을 requests·limits에
   각각 올바로 요청했고, 세 `gpu-check` 모두 `grep -c 'MIG '`로 바뀌었다. `nvidia.com/gpu` 잔존 없음.

## 남은 참고

- MIG 조각 크기(`4g.71gb` 등)는 노드의 실제 MIG 프로파일 구성에 맞아야 한다 — 이 작업은 자원
  이름을 값으로 빼는 것까지만 하고, 실제 H200 MIG 분할 계획(몇 조각을 어떤 크기로 나눌지)은 범위
  밖이다.
- api 파드를 CPU 전용으로 돌리는 옵션(예: pipeline_config에 `--device cpu` 추가)은 이번에 만들지
  않았다 — 필요하면 별도 작업으로 pipeline_config 오버라이드 방식을 설계해야 한다.
