{{/* 이름 ─────────────────────────────────────────────────────────── */}}
{{- define "dft.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 50 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 50 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "dft.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* dft.selector (dict "ctx" $ "component" "backend") */}}
{{- define "dft.selector" -}}
app.kubernetes.io/name: {{ .ctx.Chart.Name }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* 설정(ConfigMap) 체크섬 — 값이 바뀌면 파드를 다시 띄운다. 버전 라벨은 뺀다: 차트 버전만
   바뀌어도 재기동하지 않게 한다(harness 와 같은 이유). */}}
{{- define "dft.configChecksum" -}}
{{- regexReplaceAll "(?m)^ *app\\.kubernetes\\.io/version: .*$" (include (print .Template.BasePath "/config.yaml") .) "" | sha256sum -}}
{{- end -}}

{{- define "dft.secretName" -}}
{{- default (printf "%s-secret" (include "dft.fullname" .)) .Values.auth.existingSecret -}}
{{- end -}}

{{/* 이미지 ────────────────────────────────────────────────────────────
   registry 가 있으면 "<registry>/<repository>:<tag>". 비우면 노드에 import 한 이미지를
   그대로 쓴다. dft.image (dict "ctx" $ "name" "backend") — 또는 .Values.images 조회 대신
   {repository,tag} 를 바로 줄 때 dft.image (dict "ctx" $ "img" .Values.master.sourceImage) */}}
{{- define "dft.image" -}}
{{- $img := .img -}}
{{- if not $img -}}
{{- $img = index .ctx.Values.images .name -}}
{{- end -}}
{{- if .ctx.Values.image.registry -}}
{{- printf "%s/%s:%s" (trimSuffix "/" .ctx.Values.image.registry) $img.repository $img.tag -}}
{{- else -}}
{{- printf "%s:%s" $img.repository $img.tag -}}
{{- end -}}
{{- end -}}

{{- define "dft.podCommon" -}}
{{- with .Values.image.pullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/* GPU 파드 공통 스케줄링(전역 nodeSelector·tolerations + gpu.* 병합). deviceIds 로 device
   plugin 을 우회하므로 nvidia.com/gpu 자원 요청이 없다 — 반드시 노드를 지정해야 한다
   (dft.requireGpuNode 가 먼저 막는다). */}}
{{- define "dft.gpuScheduling" -}}
{{- with merge (deepCopy (.Values.gpu.nodeSelector | default dict)) (.Values.nodeSelector | default dict) }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with concat (.Values.tolerations | default list) (.Values.gpu.tolerations | default list) }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.gpu.runtimeClassName }}
runtimeClassName: {{ . }}
{{- end }}
{{- end -}}

{{/* AI_BASE_URL/AI_VLM_MODEL 을 정하는 단 한 곳 — templates/config.yaml 이 이 둘만 쓴다.
   vllmVlm.enabled 면 in-cluster vLLM Service 가 이기고, ai.baseUrl/ai.model(외부 OpenAI 호환 VLM)을
   함께 채우면 둘 중 무엇이 실제로 쓰이는지 헷갈리는 대신 렌더링을 멈춘다. */}}
{{- define "dft.aiBaseUrl" -}}
{{- if .Values.vllmVlm.enabled -}}
{{- if or .Values.ai.baseUrl .Values.ai.model -}}
{{- fail "vllmVlm.enabled=true 와 ai.baseUrl/ai.model 을 함께 채울 수 없다 — in-cluster vLLM 을 쓰려면 ai.baseUrl/ai.model 을 비우고, 외부 VLM 을 쓰려면 vllmVlm.enabled=false 로 둔다." -}}
{{- end -}}
{{- printf "http://%s-vllm-vlm:8000/v1" (include "dft.fullname" .) -}}
{{- else -}}
{{- .Values.ai.baseUrl -}}
{{- end -}}
{{- end -}}

{{- define "dft.aiVlmModel" -}}
{{- if .Values.vllmVlm.enabled -}}
{{- .Values.vllmVlm.servedModelName -}}
{{- else -}}
{{- .Values.ai.model -}}
{{- end -}}
{{- end -}}

{{- define "dft.requireGpuNode" -}}
{{- if not (or .Values.gpu.nodeSelector .Values.nodeSelector) -}}
{{- fail "GPU 컴포넌트(paddleocrVl·paddleocrLines·vllmVlm)를 켜면 gpu.nodeSelector 로 노드를 지정해야 한다 — deviceIds 는 device plugin 을 우회해 nvidia.com/gpu 를 요청하지 않으므로 스케줄러가 GPU 노드를 알아서 고르지 못한다." -}}
{{- end -}}
{{- end -}}

{{/* deviceIds → NVIDIA_VISIBLE_DEVICES 환경변수. 노드의 nvidia-container-toolkit 이
   accept-nvidia-visible-devices-envvar-when-unprivileged=true 여야 동작한다.
   dft.gpuEnv "0" 또는 dft.gpuEnv "0,1" */}}
{{- define "dft.gpuEnv" -}}
- { name: NVIDIA_VISIBLE_DEVICES, value: {{ . | quote }} }
- { name: NVIDIA_DRIVER_CAPABILITIES, value: "compute,utility" }
{{- end -}}

{{/* 카드 지정이 실제로 먹혔는지 먼저 본다 — 전제가 안 맞으면 몇 분 뒤 알아보기 어려운 CUDA
   오류로 죽는 대신 여기서 원인을 한 줄로 남기고 멈춘다(harness models.yaml 과 같은 패턴).
   dft.gpuCheck (dict "ctx" . "image" "<image ref>" "deviceIds" "0" "count" 1) */}}
{{- define "dft.gpuCheck" -}}
- name: gpu-check
  image: {{ .image }}
  imagePullPolicy: {{ .ctx.Values.image.pullPolicy }}
  command: ["sh", "-c"]
  args:
    - |
      n="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || true)"
      if [ "${n:-0}" -ne {{ .count }} ]; then
        echo "카드 지정(deviceIds={{ .deviceIds }})이 먹히지 않았습니다 — 보이는 GPU ${n:-0}장, 필요 {{ .count }}장." >&2
        echo "노드에서 확인: grep accept-nvidia-visible-devices /etc/nvidia-container-runtime/config.toml (= true 여야 함, GPU Operator 기본은 false)" >&2
        nvidia-smi -L >&2 2>/dev/null || echo "  nvidia-smi 자체가 없습니다 — 드라이버가 주입되지 않았습니다." >&2
        exit 1
      fi
      echo "GPU {{ .count }}장 확인(deviceIds={{ .deviceIds }})"
      nvidia-smi -L
  env:
    - { name: NVIDIA_VISIBLE_DEVICES, value: {{ .deviceIds | quote }} }
    - { name: NVIDIA_DRIVER_CAPABILITIES, value: "compute,utility" }
  securityContext:
    allowPrivilegeEscalation: false
  resources:
    requests: { cpu: 50m, memory: 64Mi }
    limits:   { memory: 256Mi }
{{- end -}}

{{/* 보안 컨텍스트 — Pod Security "restricted". backend/worker/frontend 처럼 자체 이미지에만
   쓴다(PaddleOCR·vLLM 은 벤더 이미지가 root 를 전제해 적용하지 않는다 — 각 템플릿 주석 참고).
   dft.podSecurity (dict "uid" 10001 "gid" 10001) */}}
{{- define "dft.podSecurity" -}}
securityContext:
  runAsNonRoot: true
  runAsUser: {{ .uid }}
  runAsGroup: {{ .gid }}
  fsGroup: {{ .gid }}
  seccompProfile: { type: RuntimeDefault }
{{- end -}}

{{/* dft.containerSecurity (dict "readOnly" true) */}}
{{- define "dft.containerSecurity" -}}
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: {{ .readOnly }}
  capabilities: { drop: ["ALL"] }
{{- end -}}

{{/* backend·worker 공통 환경 */}}
{{- define "dft.appEnv" -}}
envFrom:
  - configMapRef: { name: {{ include "dft.fullname" . }}-env }
env:
  - name: DATABASE_URL
    valueFrom: { secretKeyRef: { name: {{ include "dft.secretName" . }}, key: DATABASE_URL } }
  - name: DOCRAFT_API_KEY
    valueFrom: { secretKeyRef: { name: {{ include "dft.secretName" . }}, key: DOCRAFT_API_KEY, optional: true } }
  - name: AI_API_KEY
    valueFrom: { secretKeyRef: { name: {{ include "dft.secretName" . }}, key: AI_API_KEY, optional: true } }
  - name: HARNESS_DATABASE_URL
    valueFrom: { secretKeyRef: { name: {{ include "dft.secretName" . }}, key: HARNESS_DATABASE_URL, optional: true } }
  {{- if eq .Values.queue.backend "celery" }}
  - name: CELERY_BROKER_URL
    valueFrom: { secretKeyRef: { name: {{ include "dft.secretName" . }}, key: CELERY_BROKER_URL } }
  {{- end }}
{{- end -}}

{{/* backend·worker 가 /data 를 함께 쓴다. RWO 면 한 노드에 모은다 — 다른 노드의 파드가 못
   붙어(Multi-Attach) 뒤에 뜬 파드가 ContainerCreating 에서 멈춘다(harness 와 같은 이유). */}}
{{- define "dft.dataAffinity" -}}
{{- if eq .Values.persistence.data.accessMode "ReadWriteOnce" }}
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - topologyKey: kubernetes.io/hostname
        labelSelector:
          matchLabels:
            app.kubernetes.io/instance: {{ .Release.Name }}
            docraft/data: shared
{{- end }}
{{- end -}}
