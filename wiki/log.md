# Docraft wiki 변경 이력

## 2026-09-23 (9)
* **Update**: 코드 리뷰 지적(공식 `nginx:1.27-alpine`을 `capabilities: drop ALL`로 돌리면 80번 포트 바인딩·워커 프로세스 setuid/setgid에 CHOWN/SETUID/SETGID/NET_BIND_SERVICE가 필요해 frontend 파드가 크래시루프)을 반영했다. `frontend/Dockerfile`의 베이스를 `nginxinc/nginx-unprivileged:1.27-alpine`(uid 101, 8080번 포트 기본)로 바꾸고 `frontend/nginx.conf`의 `listen`을 8080으로 옮겼다(compose `frontend` 서비스의 포트 매핑도 `:8080`으로 맞춤, 호스트 쪽 `FRONTEND_PORT` 기본 3000은 그대로). `deploy/k8s/helm/docraft/templates/frontend.yaml`의 ConfigMap `listen`·containerPort를 8080으로 바꾸고 `dft.podSecurity (uid 101 gid 101)`를 적용해 `runAsNonRoot`+`capabilities drop ALL`을 특권 없이 만족시켰다 — Service 외부 포트는 호출자 호환을 위해 80 그대로 두고 이름 있는 포트(`targetPort: http`)로 8080에 연결했다. `helm lint --strict`·`helm template`(기본값, frontend 단독 렌더링) 재검증 통과. `deploy/k8s/README.md`의 frontend 행에 이미지·포트·uid를 반영했다.
* **Creation**: harness-installer 우산 차트의 서브차트로 쓸 Docraft Helm 차트를 [k8s-helm-chart](2026-09-23-k8s-helm-chart.md)에 기록했다(브랜치 `feat/k8s-chart`, 워크트리 `.worktrees/k8s-chart`). `deploy/k8s/helm/docraft`를 harness-v2 `mlife-harness` 차트 관례(values.yaml 구조·`deviceIds` GPU 우회·`image.registry` 치환·`existingSecret` 패턴·NOTES.txt·`tests/smoke.yaml`)를 따라 만들었다. backend(FastAPI `/api/health`)·worker(Celery, 선택)·frontend(nginx, 선택, 기본 꺼짐)와 PaddleOCR-VL(`vlm-server`+`api` 두 Deployment)·PP-OCRv5 줄 좌표(CPU 추론 + GPU 드라이버만 주입)·Qwen3-VL-32B-Instruct(vLLM, hostPath FP8 가중치) 세 GPU 컴포넌트를 구현했다. Postgres·Redis는 띄우지 않고 `externalDatabase.url`/`externalRedis.url`로 harness 쪽을 가리킨다. `paddleocr-vl-api`가 쓰는 이미지 내장 `pipeline_config_vllm.yaml`의 백엔드 주소가 `http://paddleocr-vlm-server:8080/v1`로 고정돼 있음을 WebSearch로 확인하고(PaddlePaddle/PaddleOCR 저장소), `vlm-server` Service 이름을 릴리스 접두사 없이 고정해 이미지 기본값을 그대로 쓰게 했다. `vllmVlm`의 `--tensor-parallel-size`는 `deviceIds` 카드 개수로 자동 계산해 별도 `gpuCount` 값을 없앴다(BF16+텐서 병렬 전환은 `deviceIds`·`modelDir`·`dtype`만 바꾸면 된다, helm template으로 확인). GPU 배치 기본값은 L40S 2장 — GPU0 = paddleocr-vl + harness bge-m3(차트 밖) + paddleocr-lines(드라이버만), GPU1 = vllm-vlm 전용. `~/.local/bin`에 helm v3.21.0을 설치해 `helm lint --strict` 통과, 기본값·전체 컴포넌트 켬(GPU 노드 미지정 시 fail 가드 확인 포함) 두 가지로 `helm template` 렌더링을 검증했고, 정수 값을 `quote`할 때 float64 왕복으로 `MAX_UPLOAD_BYTES`가 `"2.62144e+07"`로 깨지는 버그를 발견해 values.yaml에서 문자열 리터럴로 고쳤다. `deploy/k8s/README.md`(값·GPU 배치·hostPath 모델 구조·불확실성)를 새로 쓰고 [README](../README.md) 배포 절에 링크를 추가했다. [index](index.md)에 새 문서를 연결했다. 불확실한 점: `paddleocrVl.gpuMemoryUtilization` 0.25 실측 없음, `vllmVlm.modelDir`의 정확한 FP8 체크포인트 ID 미확정, paddleocr-lines `.paddlex` 캐시 폐쇄망 반입 절차는 범위 밖.

## 2026-09-23 (8)
* **Update**: 코드 리뷰 지적 2건을 [verify-hint-paths](2026-09-23-verify-hint-paths.md)의 "코드 리뷰 반영" 절에 기록하고 반영했다. (1) `hint_paths`가 전부 정의 밖 key여서 `only`가 빈 집합이 되면 속성 0개 스키마로 VLM 추출을 낭비하던 문제 — `verify.run`이 `only` 계산 직후, `parse()`(OCR)·`engine.extract`(VLM) 호출 전에 `ValueError`를 내도록 고쳤고, 라우트는 기존 `ValueError`→`422` 경로를 그대로 재사용해 검증 로직이 `run()` 한 곳에만 있다. (2) `checks_after = rules.check(doc_type, final, ...)`가 `hint_paths`로 좁힌 부분집합만 봐서 힌트 밖 구성 필드가 빠지는 `sum_mismatch` 등 필드 간 검사를 놓치던 문제 — `{**ao_flat, **final}`로 바꿔 힌트 밖 필드도 원래 AO 값으로 검사 대상에 넣었다. `tests/test_verify.py`의 `test_run_ignores_unknown_hint_paths_and_logs_once`를 "알려진/알 수 없는 key 혼합"과 "전부 알 수 없음(ValueError)" 두 테스트로 나누고, 라우트 422 테스트(`test_verify_route_rejects_hint_paths_with_no_key_defined_for_the_doc_type`)와 `checks_after` 회귀 테스트(`test_run_computes_checks_after_over_every_field_even_with_hint_paths`)를 추가했다. `pytest tests/test_verify.py` 54 passed, 전체 `pytest` 379 passed.

## 2026-09-23 (7)
* **Update**: [verify-hint-paths](2026-09-23-verify-hint-paths.md)에 "판정 없음은 `unknown`" 절을 추가했다. Judge 판정이 없는 key를 `source="ao"` 대신 `unknown`으로 내보내 harness 폴백이 거짓 확인으로 읽지 않게 했고, 룰 교정 key는 `corrected`를 유지한다. 전체 `pytest` 376 passed.

## 2026-09-23 (6)
* **Creation**: `POST /api/verify`에 선택 form 필드 `hint_paths`(JSON 배열 문자열, key는 `verify._name()`이 쓰는 필드·표 이름)를 추가한 작업을 [verify-hint-paths](2026-09-23-verify-hint-paths.md)에 기록했다(브랜치 `feat/verify-hint-paths`, 워크트리 `.worktrees/verify-hint-paths`). `backend/verify.py::run`에 `hint_paths=None` 인자를 더해, 주어지면 정의된 key만 남긴 `only` 집합으로 (a) `doctypes.schema()`의 `properties`/`required`를 좁혀(`verify._restrict`) 추출 비용을 줄이고, (b) `_add_missing`의 누락 필드 보충을 그 key만으로 제한하고, (c) 불일치 판정(`disputes`)·Judge 호출을 그 key만으로 제한하고, (d) 최종 값 반영 루프에서 `only` 밖 key는 건너뛰어 AO 입력 값 그대로 남기고 `value`·`source`·`reason`·`ao_value`·`docraft_value`를 붙이지 않는다(판정 여부를 `"source" in field`로 가릴 수 있음). `verify.counts`는 판정된 key만 집계한다. 정의에 없는 key는 무시하고 로거에 경고를 한 번 남긴다. JSON이 아니거나 배열이 아니면(원소가 문자열이 아니어도) 라우트가 422를 낸다. `backend/main.py`의 `verify_result`에 `hint_paths: str | None = Form(None)` 파싱·검증을 추가했다. `tests/test_verify.py`에 `hinted_stub()` 헬퍼와 8개 테스트(disputes·counts 제한, 스키마 축소, 힌트 없음/빈 배열 시 기존 동작, 알 수 없는 key 무시+경고, 라우트 전달·422 2건)를 추가하고 기존 두 라우트 테스트의 `verify.run` monkeypatch 시그니처를 맞췄다. `pytest tests/test_verify.py` 51 passed, 전체 `pytest` 376 passed.
* **Update**: [index](index.md)에 새 문서를 연결했다. [README](../README.md)의 AO 결과 교차검증 절에 `hint_paths` 설명 한 단락을 추가했다.

## 2026-09-23 (5)
* **Creation**: 라벨 관례 정렬 결과와 추출 모델 비교를 [label-alignment-and-model-compare](2026-09-23-label-alignment-and-model-compare.md)에 기록했다(브랜치 `docs/model-compare`, 워크트리 `.worktrees/model-compare`, 기록 전용·코드/라벨/매니페스트 변경 없음). (a) 관례 정렬: 기존 36건 변경분(영수증 1,020셀·세부내역서 6셀·진단서 1행)과 미결 3건 적용(A·B 0셀, C 287셀, alias 후보 `입원료_상급병실` 1건), 단계별 rules 수치(`eval-20260923-014335` 8,065/8,527 94.58% → `020802` 9,065/9,525 95.17% → `022807` 8,794/9,238 95.19% fp 429 → `023404` 동일 correct에 fp 330), 분모가 8,527→9,525→9,238으로 두 번 바뀌어 09-23 이전 수치와 직접 비교할 수 없다는 경고, 급여 열 정리로 세부내역서 fp 372→273과 남은 141건이 `_grouped` 판정 실패 문서 7건에 몰린 사실을 정리했다. (b) 모델 비교: 같은 parse 캐시·같은 최종 라벨·같은 코드 `0d73241`·사고 모드 off 조건에서 `eval-20260923-023846`(이전 `qwen/qwen3-vl-32b-instruct`)과 `eval-20260923-023850`(새 `qwen/qwen3.5-27b`)을 대조해 전체 rules correct 8,794→8,569(95.2%→92.8%)·strict 7,764→7,411·fp 330→321, 유형별 진단서 89.6→85.4·소견서 83.5→81.9·영수증 97.1→96.1·세부내역서 94.3→90.5, holdout 세부내역서 91.6→84.8(−146셀이 사실상 `SA2020010683384` 1건의 −155셀)임을 표로 남겼다. 새 모델이 뒤진 원인 상위 5개(항목내역 행 밀림, 영수증 `항목내역.항목` 행 누락, `항목내역.투여량` 과잉 채움, 문자 단위 오독, 요약 금액 칸 오선택)를 예시 셀과 함께 정리하고, 지연 실측(76회 중앙값 36.9초·p90 105초·최대 268초·합 3,788초)과 단가(입력 $0.195 vs $0.104, 출력 $1.56 vs $0.416 per M), 재실행 변동(영수증 existing ±43셀)을 감안한 해석을 덧붙였다. 권고는 현 벤치마크 기준 이전 모델 유지이며 결정은 사용자 보류로 표시했다.
* **Update**: [vlm-model-qwen35](2026-09-23-vlm-model-qwen35.md)에 "76건 기준선 결과" 절을 신설해 새 문서로 연결하고 "남은 과제"를 전환 결정 보류 문장으로 갱신했다. [label-review](2026-09-23-label-review.md) "관련 자료" 끝에 새 문서 링크를 한 줄 추가했다. [index](index.md)에 새 문서를 연결했다.

## 2026-09-23 (4)
* **Update**: 라벨 표기 관례 미결 3건(⑦ 영수증 항목명 비영숫자·비한글 문자 전부 제거, ⑧ 밑줄 canonical은 `rules.ITEM_ALIASES` 단일 기준, ⑨ 세부내역서 행별 `급여` 열은 급여 값 칸이 인쇄된 서식만) 확정을 코드·문서에 반영했다(브랜치 `feat/conventions-2`, 워크트리 `.worktrees/conventions-2`). `backend/rules.py`의 `_columns`가 세부내역서 `급여` 칸을 급여구분·총액에서 무조건 채우던 것을 파싱 표 머리글에 하위 열 없는 독립된 `급여` 열이 보일 때만 채우도록 제한했다 — 판별은 기존 `_headers`·`_grouped`·`GROUPED`를 그대로 쓰고, 블록이 없으면(라벨 정리 `verify_label.conform` 경로 포함) 채우지 않는다. 이를 위해 `derive(doc_type, out, blocks=None)`에 블록 인자를 더하고 `apply`가 넘긴다. `비급여` 파생은 인쇄값 관례와 맞아 그대로 뒀다. `backend/doctypes.py`의 `_DETAIL_ITEM["급여"]` 설명을 "급여 값 칸이 인쇄된 서식만, 머리글이면 null, 총액에서 계산하지 않는다"로 고치고 `_RECEIPT_ITEM["항목"]`에 비영숫자 문자 제거(빗금 포함, 하위 항목 밑줄만 예외) 구절을 더했다. [ocr-verify-labels](2026-09-22-ocr-verify-labels.md) "표기 관례" 절의 ⑦을 확장하고 ⑧·⑨를 신설했으며, [label-review](2026-09-23-label-review.md)에 "미결 3건 확정(2026-09-23)" 절을 추가했다. `tests/test_rules.py`에 항목명 기호 제거 6케이스와 급여 파생 제한 2건을 더하고 기존 세부내역서 관례 테스트의 기대값을 고쳤다(302 passed). 2026-09-22 [kv-fill-false-positives](2026-09-22-kv-fill-false-positives.md)의 "급여 파생을 끄면 correct −77" 수치는 파생값을 담고 있던 옛 라벨 기준이라, 라벨 재작업이 끝난 뒤 새 기준으로 재측정한다.
* **Update**: 라벨 C 적용 뒤 재측정하고 후속 코드 2건을 반영했다(같은 브랜치). `rules.ITEM_ALIASES`·`RECEIPT_ITEM_NAMES`에 `입원료_상급병실`(`^입원료.*상급`, 세로 병합 '입원료' 상위 칸 + 하위 칸 '상급병실')을 추가했고, `_columns`가 묶음 머리글 확정(`_grouped`가 True)인 서식에서는 모델이 `총액−비급여`로 채워 온 행 `급여`를 null로 지우도록 했다(None이면 그대로 둔다). 같은 캐시로 재채점(`eval-20260923-022807.json` → `eval-20260923-023404.json`)한 결과 `항목내역.급여` fp 240→141, 세부내역서 rules fp 372→273(existing 176→109, holdout 196→164)이고 correct·strict는 전 유형·전 단계 무변화다. 남은 141건은 머리글 행 미검출 5건·머리글 병합 1건·`급여구분` 값 혼입 1건으로 `_grouped`가 True를 못 내는 문서들이며, 근거 없는 문서까지 지우는 선택은 인쇄값 삭제 위험이 있어 보류했다. 수치는 [label-review](2026-09-23-label-review.md) "미결 3건 확정" 절에 표로 남겼다(304 passed).

## 2026-09-23 (3)
* **Creation**: 추출 VLM `qwen/qwen3.5-27b` 전환 배경(OpenRouter slug·이미지 입력·`response_format` 지원 확인, 컨텍스트 262k, 단가 $0.195/$1.56 vs 이전 $0.104/$0.416 per M)과, 전환 후 드러난 기본 사고 모드로 인한 추출 호출 10배 이상 지연(실측 3건 중앙값 222초·최대 541초, `reasoning.enabled=false`면 1.7~16초·작은 프롬프트 `reasoning_tokens` 135→0)을 [vlm-model-qwen35](2026-09-23-vlm-model-qwen35.md)에 기록했다. SiliconFlow·Novita·AtlasCloud 등 provider 라우팅에 따른 지연 편차와 빈 응답(`{}`) 1건(재시도로 정상 복구) 사례도 남겼다. `backend/config.py`의 `ai_settings()`에 `AI_REASONING`(`off`(기본)/`on`)을 추가하고 `backend/engine.py`의 `_provider()`가 `off`일 때만 요청 본문에 `"reasoning": {"enabled": false}`를 넣도록(OpenRouter 표준 파라미터, 미지원 provider·모델은 무시) 구현했다. `tests/test_ai_provider.py`에 기본값·`on` 검증 테스트 2건을 추가했다(294 passed). `.env.example`·`deploy/aws/.env.aws.example`·README 환경변수 표에 `AI_REASONING`을 추가했다. 76건 기준선 재추출은 이 변경 이후 별도로 실행할 예정이다.
* **Update**: [index](index.md)에 새 문서를 연결했다.

## 2026-09-23 (2)
* **Update**: [label-review](2026-09-23-label-review.md)의 "관례 불일치 7건" 사용자 결정을 반영해 표의 상태를 "보류"→"확정(2026-09-23)"으로 바꾸고, ④(세부내역서 `급여_급여총액`)를 권장안(비급여 포함 합계행 총액)과 다르게 확정했다는 문단을 추가했다 — 확정 정의는 **급여(본인부담+공단부담+전액본인부담)만의 합계 인쇄값**, 서식에 급여 합계 칸이 없으면 null(직접 계산 금지), 근거는 harness-v2 고객 하네스 규칙 `CALC_0710_17`과 필드명. [ocr-verify-labels](2026-09-22-ocr-verify-labels.md) "표기 관례" 절을 ①~⑦ 확정 내용으로 갱신하고(영수증 합계 행 포함, 빈 금액 칸 `"0"`, 공단부담총액 대체 칸, 급여총액 정의, 여유 행 제외, 진료기간 종료일=시작일, 영수증 항목명 구두점 제거) "null 정책 불일치" 한계 지적에 ②로 확정됐다는 주석을 달았다. `backend/doctypes.py`의 `급여_급여총액` 설명을 확정 정의에 맞게 정정했다(`RECEIPT_HINT`·`_RECEIPT_ITEM["항목"]`·`rules.TOTALS`는 이미 ①②⑦ 및 인쇄값 원칙과 일치해 코드 로직 변경은 없었다). [README](../README.md) 정확도 평가 단락에 라벨 관례 확정 문서 링크를 추가했다. 292 passed.

## 2026-09-23
* **Creation**: 홀드아웃 40건(유형별 10건) silver 라벨을 네 에이전트가 원본 이미지와 대조해 교정한 기록을 [label-review](2026-09-23-label-review.md)에 남겼다. 감사 파일 4개 집계(교정 셀 합계 915건: 진단서 31·소견서 70·진료비영수증 254·세부내역서 560), 같은 parse/extract 캐시로 재채점(`eval-20260923-014335.json` vs `eval-20260922-232123.json`)해 existing 36건은 완전히 동일함을 확인하고 holdout 40건의 상승분이 라벨 오류 제거분임을 밝혔다(예: 진료비영수증 rules 91.9%→97.1%, 세부내역서 rules 75.0%→91.4%, existing은 모든 유형·단계에서 무변화). 교정 후 남은 오류를 유형별 상위 5개 필드로 집계해 저해상도 팩스 1건(세부내역서 잔여 오류의 62.7%)·투여량 추출 누락·행 정렬 오류·`선택항목_` 접두 등 진짜 시스템 한계를 라벨 잔여 문제와 구분했다. 기존 36건과의 관례 불일치 7건(영수증 합계 행 포함 여부, 빈 금액 0/null, 공단부담총액 대체 칸, 세부내역서 급여총액 정의, 여유 행·진료기간·항목명 구두점 통일)에 권장 통일안을 달았다(결정은 보류). `manifest.json`의 holdout 40건 `status`를 `reviewed`로 갱신하고 `label-audit.json`에 `review` 절을 추가했다.
* **Update**: [index](index.md)에 새 문서를 연결했다. [extract-grounding](2026-09-22-extract-grounding.md) "오류 확인" 절에 (a) 범주 대표 사례가 실은 라벨 오독이었고 348셀 집계가 과대평가일 수 있다는 문단을 추가했다. [accuracy-eval-expansion](2026-09-22-accuracy-eval-expansion.md) "남은 과제 1"에 홀드아웃 검수 완료와 관례 결정 문서 링크를 추가했다. [ocr-verify-labels](2026-09-22-ocr-verify-labels.md) 끝에 홀드아웃 검수 링크를 추가했다. [README](../README.md)의 정확도 평가 단락에서 "전체 원문 검수를 마친 정답셋으로 취급하지 않는다"를 "2026-09-23 이미지 대조 검수를 거쳤으나 사람 검수 gold는 아니다"로 갱신했다.

## 2026-09-22 (24)
* **Creation**: 파서 표 복원 보강을 [table-restore](2026-09-22-table-restore.md)에 기록했다. 모델과 무관한 구조 지표를 `scripts/parse_audit.py`로 먼저 만들고(머리글 검출·`_receipt_rows` 행 수·다중 금액 셀), 실패 6건을 원본 이미지와 대조해 원인을 기울기(2~3°)·`_runs` 팽창 창 off-by-one(마스크가 1px 밀리고 `length-1`만큼 짧아짐)·셀 병합 오판으로 분류했다. `backend/table_grid.py`에 `_skew`/`_straighten`(±3° 투영 기반 기울기 보정, crop과 줄 박스를 함께 회전), `slack = max(10, 글자높이/2)`, `FIRM=0.5`(절반 이상 행에서 잡히는 세로 경계는 인쇄된 열로 보고 글자가 가로지를 때만 병합)를 더했다. 38건 구조 지표 `multi` 2027→1818·`rebuilt>0` 15→18, 고객 보고 파싱 에러 사례 `multi` 12→0·`rebuilt` 21→23. 76건 rules 재평가(48건 재파싱, 27분) all correct 7238→7199·strict 6701→6768·fp 243→268, holdout strict 74.3→75.8%. 손실 −44·fp +19가 구조 지표가 그대로이거나 좋아진 두 문서에 몰려 있어(나머지 74건 correct +5·strict +113) 채택했다(292 passed).
* **Update**: [index](index.md)에 새 구현 문서를 연결했다. [README](../README.md) 파서 설명에 괘선 격자·기울기 보정 한 줄과 평가 절에 `scripts/parse_audit.py` 사용법 한 줄을 추가했다.

## 2026-09-22 (23)
* **Update**: [extract-grounding](2026-09-22-extract-grounding.md)에 3차 지침 절을 추가했다. `_RECEIPT_ITEM["항목"]`에 "분류 칸(기본항목·선택항목 등)은 항목명에 붙이지 않는다"를 더하고 영수증 19건만 재추출(`grounded-v3`, `eval-20260922-212737.json`). 2차 대비 all strict 6646→6701·fp 249→243, holdout strict 3435→3487·fp 178→167로 회복해 채택했다. 문제 문서 `SA2019040914066`의 strict는 40→136(기준선 173)이며 `선택항목_` 접두 자체는 남아 완전 복구는 아니다. 기준선 대비 누계 all 7185→7238·strict 6627→6701·fp 330→243(289 passed).

## 2026-09-22 (22)
* **Creation**: 추출 프롬프트에 표 근거 제약(`doctypes.GROUND_HINT`·`engine.TABLE_NOTE`)을 더해 인쇄되지 않은 표준 항목 행 생성과 표준 명칭 치환을 억제한 작업을 [extract-grounding](2026-09-22-extract-grounding.md)에 기록했다. 영수증 19건 동일 프롬프트 재실행으로 변동 폭(all rules +43, holdout 0)을 먼저 재고, 1차 지침(글자 그대로 복사·두 번째 코드 열)은 순손실(all rules 7185→7159, strict −160)이라 버렸다. 2차 지침 채택: 76건 rules 7185→7235(87.81→88.43%)·strict 6627→6646·fp 330→249, raw fp 459→244, holdout 세부내역서 정답 1765→1786·fp 105→59. 나빠진 지표는 holdout strict 75.68→73.15%로, −133이 `SA2019040914066` 한 건의 `선택항목_` 접두 때문이다(289 passed).
* **Update**: [index](index.md)에 새 구현 문서를 연결했다. [README](../README.md)의 교차검증 절에 표 근거 제약 한 줄을 추가했다.

## 2026-09-22 (21)
* **Creation**: 세 기능 브랜치(`feat/kv-row-align`·`feat/kv-fill-fp`·`feat/kv-master-correct`)를 main에 차례로 병합하고 76건 rules 단계로 재평가한 결과를 [kv-accuracy-integration](2026-09-22-kv-accuracy-integration.md)에 기록했다(전체 7173→7185·fp 365→330·strict 6617→6627, 기존 36건 94.49→94.78%, holdout 82.60→82.64%·fp 223→212, 개별 델타와 정확히 합산, 285 passed).
* **Update**: [kv-accuracy-review](2026-09-22-kv-accuracy-review.md)의 세부내역서 단가 fp 원인을 '룰 파생'에서 '모델 추출 단계 오탐(raw에서도 fp 39)'으로 바로잡고, 우선순위 2번에서 '라벨 근거 없는 단가 파생 중단'을 뺐다. '항목명 정규화 시 세분 항목 보존' 가설이 실제로는 `_receipt_table` 행 복원 위치 문제였다는 주석을 붙였다.
* **Update**: [index](index.md)에 통합 평가 문서를 연결했다.

## 2026-09-22 (20)
* **Creation**: [master-name-correction](2026-09-22-master-name-correction.md)에 KCD·EDI 마스터 사전 구축과 코드 일치 행의 1글자 명칭 교정, 임계값 스윕 근거(마스터 명칭 통째 대체는 순손실 -13), 76건 rules 전후 수치(순 +4, strict +3, holdout 무변화)를 기록했다.
* **Update**: [index](index.md)에 새 구현 문서를 연결했다. [README](../README.md)에 마스터 사전 준비 절과 `MASTER_DIR` 설정을 추가했다.

## 2026-09-22 (19)
* **Creation**: `rules._fill`이 문서 전체에서 첫 후보를 채우며 만들던 오탐을 환자/의료기관 영역 제약, 필드 무리 상호배제, 근거 등급(라벨 셀 > 텍스트 줄)과 동률·빈 라벨 칸 미채움으로 줄인 작업을 [kv-fill-false-positives](2026-09-22-kv-fill-false-positives.md)에 기록했다(76건 rules 단계 fp 365→339, correct 7173→7175, raw→rules 신규 오탐 53→27, 261 passed).

## 2026-09-22 (18)
* **Creation**: 표 행 짝짓기 규칙을 `rules.ROW_KEYS`·`rules.pair_rows` 한 곳으로 모으고(항목내역 키에 `시작일자` 추가), `verify._rows_same`을 키 열 대응 + 셀 단위 비교(`_row_diff`)로 바꾸고, 영수증 항목 행을 파서 표의 인쇄 순서·세분 항목명으로 바로잡고(`_receipt_table`), 소계 행을 보존하도록(`_totals`) 고친 작업을 [kv-row-align](2026-09-22-kv-row-align.md)에 기록했다. 76건 rules 단계 전체 87.7%·strict 80.9→81.0%·fp 365→356, 기존 36건 94.5→94.7%·strict 87.9→88.1%·fp 142→133, holdout 40건은 변화 없음, 나빠진 지표 없음. 표준 항목명 화이트리스트 완화는 오히려 나빠져 되돌렸다(261 passed).

## 2026-09-22 (17)
* **Update**: [kv-accuracy-review](2026-09-22-kv-accuracy-review.md)에 "harness-v2 참고 자산" 절을 추가했다. 개선 우선순위 1~4와 harness-v2 자산(행 정렬 키, Arbitration 원칙, 마스터 4종·매칭 모듈, 산식 검사, 영수증 서식 판별) 대응표, 고객 보고 오류 사례 3건, 스키마 정합 확인 사항, golden 데이터 한계를 기록했다.

## 2026-09-22 (16)
* **Creation**: [kv-accuracy-review](2026-09-22-kv-accuracy-review.md)에 76건 rules 단계 오류 분포와 코드 검토를 대조한 정확도 개선 우선순위를 기록했다(구현·재실행 없음).
* **Update**: [index](index.md)에 새 분석 문서를 연결했다.

## 2026-09-22 (15)
* **Update**: [accuracy-eval-expansion](2026-09-22-accuracy-eval-expansion.md)에 76건 전후·split별 정확도와 FP, 모델 비교, 원복한 임상 지침 실험, 254개 테스트 및 목표 미달을 기록했다. README에 평가 절차를 추가했다.

## 2026-09-22 (14)
* **Creation**: [accuracy-eval-expansion](2026-09-22-accuracy-eval-expansion.md)에 기존 36건과 내용 중복 없는 유형별 10건 holdout 매니페스트, 독립 라벨 provenance, rules 단독 실행 의존성, strict/legacy 정확도와 evaluated/skipped/error 집계를 기록했다.
* **Update**: [index](index.md)에 정확도 평가 확장 문서를 연결했다.

## 2026-09-22 (13)
* **Update**: 사용자 우선 목표인 정확도 96%와 유형별 추가 정답 필요량을 [rule-performance-review](2026-09-22-rule-performance-review.md)에 추가했다. 목표 단계·집계 단위는 미확정이며 속도 최적화는 후순위다.
* **Creation**: [rule-performance-review](2026-09-22-rule-performance-review.md)에 코드·저장 평가 기반 개선 우선순위를 기록했다(구현·신규 성능 측정 없음).
* **Update**: [index](index.md)에 분석 문서를 연결했다.

## 2026-09-22 (12)
* **Creation**: [readme-architecture](2026-09-22-readme-architecture.md)에 README 현행화와 Mermaid 아키텍처·처리 흐름 시각화 기록을 추가했다.
* **Update**: [README](../README.md)의 일반 추출·AO 검증, 스키마 출처, 실행·설정·검증 안내를 현재 코드와 대조해 갱신했다. [index](index.md)에 새 문서를 연결했다.

## 2026-09-22 (11)
* **Creation**: verify가 모델 추출 1차·룰 후처리 구조라 지연 시간 목표와 맞지 않는다는 논의를 정리해, 룰 1차 추출 + AO 비교 + Judge 1회로 전환하는 후속 작업 지시서를 [verify-rule-first-plan](2026-09-22-verify-rule-first-plan.md)에 남겼다(현재 단계별 실측 시간, 룰 자산, 평가 기준선, 예상 부작용과 대응, 세부 작업 A~D, 완료 기준).

## 2026-09-22 (10)
* **Creation**: 계획 문서의 미결 3건(정답셋·범위 4종·이미지 1장)을 확정하고 `POST /api/verify`를 구현한 기록을 [ocr-verify](2026-09-22-ocr-verify.md)에 남겼다. `backend/doctypes.py`(유형별 필드 정의)·`backend/rules.py`(twin reader 이식 룰 + 진료비영수증 항목내역 검사·교정)·`backend/verify.py`(평탄화·Judge·파이프라인)를 추가하고, AO 응답의 key·value 누락과 UI 응답 형식을 수용하며, harness-v2 오류 케이스 3건(비급여→급여 오추출·셀 병합·항목명 누락)을 실측했다. 룰 확장으로 36건 rules 단계 정확도가 raw 88.4%→92.9%, gold final은 진단서 100·소견서 90·진료비영수증 98·세부내역서 98.8%가 됐다(245 passed).
* **Update**: [ocr-verify-plan](2026-09-22-ocr-verify-plan.md)의 미결 사항에 결정 내용을 적고 완료 기준을 갱신했다.

## 2026-09-22 (9)
* **Creation**: `feedback.md` TODO의 harness-v2 통합 메모(AO 결과와 Docraft 결과 LLM 비교·선정, twin reader 룰 이식·확장, 자동 교정 JSON API)를 참고 경로·세부 작업·완료 기준·미결 사항을 갖춘 작업 지시서로 정리해 [ocr-verify-plan](2026-09-22-ocr-verify-plan.md)에 기록했다.

## 2026-09-22 (8)
* **Creation**: 요청 대기(`loading`)나 백그라운드 문서 처리(`polling`) 중 상단바에 로딩바와 진행 문구를 보여주는 기능을 [loading-bar](2026-09-22-loading-bar.md)에 기록했다.

## 2026-09-22 (7)
* **Creation**: 추출(`extract`)과 AI 스키마 생성(`generate_schema_from_documents`) 요청에 문서 페이지 이미지를 함께 보내도록 바꾼 작업을 [vision-extract](2026-09-22-vision-extract.md)에 기록했다. `_page_images`/`_data_url`/`_user`를 두 경로가 공유하고, 페이지 단위 청크는 그 청크의 페이지 이미지만 붙이며, 새 설정 `AI_VISION=false`로 기존 텍스트 전용 동작으로 되돌릴 수 있다. 실제 영수증 재검증에서 텍스트 전용이 지어내던 열별 합계(7381/17221)와 빈칸의 47300이 정확한 7300/17300/40000·null로 바뀌었고, 스키마 생성도 열을 불리언 플래그로 바꾸지 않고 열별 숫자 필드로 설계했다(85 passed).

## 2026-09-22 (6)
* **Update**: VL 행 매칭이 실패하거나 배열 합의 행 밖에서만 값을 찾은 leaf를 블록의 OCR 줄 텍스트로 직접 근거를 잡게 하고(`_line_leaf`, band 안일 때만), `_rank`에 4자 이상·비숫자 needle의 한 글자 오차 유사도 매칭(SequenceMatcher ≥0.85)을 더했다. `backend/engine.py` 순증 23줄. 실제 영수증 2건 재검증: leaf 14개가 바뀌었고 전부 개선(`/items/0/item_name` 0.0→1.0 등), 기존에 맞던 leaf는 회귀 0건. [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)의 "줄 텍스트 근거 인정과 유사도 매칭"·"남은 한계"에 기록했다(77 passed, 환경 종속 실패 1건 별개).

## 2026-09-22 (5)
* **Creation**: 새 프로젝트 생성·다른 프로젝트 이동 시 이전 프로젝트의 탭(스키마 설계)과 스키마 편집 내용이 남아 보이던 버그를 `projectId` 변경 시 프로젝트 단위 상태 초기화로 고친 작업을 [project-state-reset](2026-09-22-project-state-reset.md)에 기록했다.

## 2026-09-22 (4)
* **Creation**: 스키마 편집 화면에서 편집 중인 JSON Schema를 title과 함께 내려받는 `JSON Schema 내보내기`를 [schema-export](2026-09-22-schema-export.md)에 기록했다.

## 2026-09-22 (3)
* **Creation**: PaddleOCR-VL은 구조·내용만 담당하고 좌표는 별도 PP-OCRv5 일반 OCR 파이프라인(`PADDLEOCR_LINES_URL`, compose 서비스 `paddleocr-lines-api`)이 준 줄 단위 상자를 쓰도록 바꾼 작업을 [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)에 기록했다. 파서가 각 줄을 중심점이 들어가는 가장 작은 블록에 `block["lines"]`로 붙이고, `backend/engine.py`의 행 bbox 균등 분할 추정(`_row_bbox`)을 삭제했으며 불리언 leaf는 grounding 트리에서 제외했다. 실제 영수증 2건으로 재검증해 균등 분할이 3~5행씩 밀리던 자리가 모두 맞았다(71 passed).
* **Update**: [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)의 "행 bbox 추정" 절과 "남은 한계"의 균등 분할 추정 한계를 폐기됨으로 표시하고 [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)으로 연결했다.

## 2026-09-22 (2)
* **Creation**: 긴 문서를 페이지 경계로 나눠 여러 번 호출하고 스키마에 따라 병합하는 구현을 [extract-page-chunking](2026-09-22-extract-page-chunking.md)에 기록했다(61 passed).
* **Update**: [refs-improvement-review](2026-09-21-refs-improvement-review.md)의 #1 완료 메모에 블록 id grounding이 서버 측 행 grounding으로 교체됐고 이번 브랜치에서 페이지 단위 분할 추출까지 끝났음을 반영했다.

## 2026-09-22
* **Update**: [refs-improvement-review](2026-09-21-refs-improvement-review.md)에 #1(추출 grounding) main 병합 완료를 반영했다.
* **Creation**: refs 기반 개선 1~3단계 구현을 [refs-improvements](2026-09-22-refs-improvements.md)에 기록했다.
* **Update**: [refs-improvement-review](2026-09-21-refs-improvement-review.md)에 항목별 구현 상태를 추가했다.

## 2026-09-21
* **Creation**: AGENTS.md 작업 규칙 보강을 [agents-md-rules](2026-09-21-agents-md-rules.md)에 기록했다.
* **Creation**: 분석 결과 표 미리보기와 JSON 색상을 [table-preview](2026-09-21-table-preview.md)에 기록했다.
* **Creation**: refs 3사 화면과 현재 코드를 비교한 개선·기능 후보를 [refs-improvement-review](2026-09-21-refs-improvement-review.md)에 기록했다.
* **Creation**: feedback.md의 Markdown·HTML 뷰어 항목 구현을 [markdown-html-viewer](2026-09-21-markdown-html-viewer.md)에 기록했다.
* **Update**: 모든 wiki 문서에 날짜 prefix(`2026-09-21-`)를 붙이고 Open Knowledge Format v0.2 frontmatter를 추가했다. [index.md](index.md)를 만들었고, SQLite 시기 기록인 [backend-implementation](2026-09-21-backend-implementation.md)은 `deprecated`로 표시했다.
* **Creation**: 백엔드 로깅과 Docker 전체 스택 구성을 [logging-docker](2026-09-21-logging-docker.md)에 기록했다.
* **Creation**: 추출 JSON 파싱 실패의 원인 분석을 [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)에 기록했다.
* **Update**: [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응" 절을 실제 적용된 내용(블록 id grounding, 블록 단위 입력 자르기, strict 스키마 정규화, optional null 제거)으로 갱신했다.
* **Creation**: extract() grounding을 블록 id 참조로 바꾸고 strict 스키마 정규화가 만드는 optional null을 결과에서 제거한 작업을 [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)에 기록했다.
* **Update**: 사고 문서로 재현 테스트를 진행해 strict `json_schema`가 Alibaba provider에서 응답을 망가뜨리는 실제 원인임을 확인했다. [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)에 재현 실험 표와 최종 대응(철회 이력 포함)을 갱신하고, [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)를 `extract()`의 `response_format: json_object` 전환·`_strict_schema`/`require_parameters` 삭제에 맞춰 다시 썼다. `backend/engine.py`와 `tests/test_ai.py`, `tests/test_ai_provider.py`도 같이 바꿨다(33 passed).
* **Update**: `extract()`를 결과만 요청하는 계약으로 바꾸고 grounding을 서버가 원문 블록에서 값을 찾아 계산하도록 전환했다(같은 문서 재현 테스트 150~200초 → 61초, leaf 199개 전부 bbox 채워짐, 이슈 0건). [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)를 최종 구현에 맞춰 다시 쓰고 블록 id grounding은 중간 단계 이력으로 정리했으며, [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응" 절을 갱신했다(34 passed).

## 2026-09-22
* **Update**: grounding을 블록 단위에서 **행 단위**로 올렸다. table HTML을 `<tr>`/`<td>`로 읽어 값이 든 행을 찾고 블록 bbox를 행 수로 균등 분할해 근거 상자를 만들며, 셀 전체 일치 우선으로 짧은 값 오탐을 없애고, 배열 항목의 합의 행 밖에서만 발견된 값은 `confidence: 0.5`로 낮춘다. 실제 문서에서 leaf 199개 전부 1.0·16행이 서로 다른 `<tr>`에 매핑됐고, 다른 행 값을 주입하면 해당 leaf만 0.5로 잡힌다. [extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)에 "행 인식 grounding" 절을 추가하고 [extract-json-parse-failure](2026-09-21-extract-json-parse-failure.md)의 "대응"과 README를 갱신했다(38 passed).
* **Creation**: 추출 지침과 필드 구조를 모달에서 크게 편집하고 전체 화면으로 확대·축소하는 기능을 [zoom-modal](2026-09-22-zoom-modal.md)에 기록했다.
* **Creation**: 파싱·추출을 교체 가능한 작업 큐(`QUEUE_BACKEND=inline|celery`)와 worker로 실행하도록 바꾼 작업을 [job-queue](2026-09-22-job-queue.md)에 기록했다(61 passed, redis+celery 스모크 통과).
* **Creation**: worker 중단·inline 재시작 시 멈춘 작업을 heartbeat lease와 기동 시 `recover()`로 자동 복구하고 Docker로 검증한 작업을 [job-recovery](2026-09-22-job-recovery.md)에 기록했다(68 passed).
* **Update**: [job-queue](2026-09-22-job-queue.md)의 남은 한계에 해결된 항목을 표시했다.
* **Creation**: 같은 값이 여러 셀에 있을 때 필드 라벨 옆 줄을 고르는 grounding, 하이픈 허용, 합계 필드 추출 지시를 [label-grounding](2026-09-22-label-grounding.md)에 기록했다(87 passed, 실제 영수증에서 `47,300` 4개 leaf가 각자의 행으로, `공단부담총액` 10717 → 17300).
* **Update**: [ocr-line-grounding](2026-09-22-ocr-line-grounding.md)의 `47,300` 검증 판정이 오판이었음을 표시하고 후속 문서로 연결했다.
* **Creation**: PaddleOCR-VL 표의 병합 셀 정보를 파서가 버려 미리보기·Markdown/HTML·스키마 생성 입력의 표가 어긋나던 문제를 직사각형 격자와 `spans`로 고친 작업을 [table-spans](2026-09-22-table-spans.md)에 기록했다(88 passed, 샘플 5종 7개 표의 행 폭 일치).
* **Creation**: 표 인식 모델 비교(PaddleOCR-VL·PP-StructureV3·Qwen3-VL 32B/8B)와 VL 격자를 유지한 채 VLM으로 셀 텍스트만 교정하는 `TABLE_REFINE`을 [table-refine](2026-09-22-table-refine.md)에 기록했다(90 passed, 진료비영수증 30개 셀 교정).
* **Update**: [table-spans](2026-09-22-table-spans.md)에 PaddleOCR 경로에서 `spans`가 빠지던 버그와 수정 위치를 덧붙였다.
* **Creation**: 외부 파서 결과(`parse_202501020959270c.json`)가 격자 우선 방식임을 분석하고, PaddleOCR-VL 표 HTML 대신 괘선 격자로 행·열·병합 셀을 복원하는 `backend/table_grid.py`를 도입한 작업을 [ruled-table-grid](2026-09-22-ruled-table-grid.md)에 기록했다(93 passed, 진료비영수증 42×15 격자가 원본 양식과 일치).
* **Update**: [table-spans](2026-09-22-table-spans.md)의 "남은 모델 인식 오류"에 괘선 격자 후속 문서 링크를 추가했다.
* **Creation**: harness-v2 방식을 따라 같은 EC2에 Docraft 스택을 올리는 `deploy/aws/` 스크립트와 서버 조사 결과를 [aws-deploy](2026-09-22-aws-deploy.md)에 기록했다(compose 병합 확인, 실제 배포 전).
* **Update**: AWS smoke에서 약제비영수증 표가 2×2 격자로 뭉개져 VLM 결과를 덮어쓴 것을 발견했다. 격자 행 수가 VLM 행 수의 절반 미만이면 VLM 구조를 유지하도록 [ruled-table-grid](2026-09-22-ruled-table-grid.md)에 반영했다(94 passed).
* **Update**: [aws-deploy](2026-09-22-aws-deploy.md)에 실제 배포 결과를 추가했다(6개 컨테이너 healthy, harness 영향 없음, GPU 9.7/23GB, smoke 5종 parsed, 약제비영수증 과소 분할 수정 후 재배포).
* **Update**: [aws-deploy](2026-09-22-aws-deploy.md)에 외부 접근 옵션 `FRONTEND_BIND`(기본 루프백, 0.0.0.0이면 API 키 필수)와 OpenRouter 키 비노출 확인을 추가했다.
* **Update**: [aws-deploy](2026-09-22-aws-deploy.md)에 이슈 수집 스크립트 `collect.sh`와 backend 로그 파일 보존(`/data/logs`, 재배포 시 소실 방지)을 추가했다.
* **Creation**: AWS L4 서버에서 이미지 병렬 처리량(레이아웃 분당 약 12건 포화)과 100건 연속 처리(100/100 성공, 분당 10.6건)를 측정하고, UI 업로드 413과 프로젝트 삭제 시 원본 파일 잔존을 고친 작업을 [aws-throughput](2026-09-22-aws-throughput.md)에 기록했다(94 passed).
* **Creation**: VLM(claude-sonnet-4.5)으로 문서 유형 4종 정답셋(gold 4+silver 32, 36개)을 라벨링하는 `scripts/verify_label.py`와 raw/rules/ao/final 4단계 필드 정확도를 계산하는 `scripts/verify_eval.py`를 구현하고 실제로 돌린 결과를 [ocr-verify-labels](2026-09-22-ocr-verify-labels.md)에 기록했다(라벨 36개 ok=35·skip=1·error=0, gold 4건 전 단계 및 전체 36건 raw·rules 실행 완료).
* **Update**: 라벨 36건(gold 4+silver 32)을 전부 이미지와 대조해 검수하고 `scripts/verify_eval.py`를 보정했다. 표를 행 식별자(`항목`+`EDI코드`, `병명코드`·`수술일자`·`검사일`·`치료일`)로 먼저 짝짓고 남은 행만 순서로 잇도록 바꿨으며, 정오·오탐 판정을 `rules.same` 하나로 일원화하고 `실패 상위 20 필드` 표와 단계·이미지가 붙은 오답 목록을 추가했다. 재평가에서 raw는 진단서 79.6→82.0%·소견서 60.3→82.8%·진료비영수증 69.2→85.6%·세부내역서 80.8→94.5%로 올랐고, gold `final`은 100/90/100/98.6%, 진료비영수증 ao 오탐은 170건→12건이 됐다. [ocr-verify-labels](2026-09-22-ocr-verify-labels.md)에 검수 관례·파일별 수정량·새 평가표를 기록했다.
* **Creation**: `rules.apply`·`check`·`correct`의 흐름을 진단서·진료비영수증 예시 실행 결과로 풀어 쓴 [rules-flow-example](2026-09-23-rules-flow-example.md)을 추가하고, 그 과정에서 찾은 `_name`의 도장 표시(`홍길동 (인)` → `홍길동인`) 버그 수정을 기록했다.
* **Creation**: 남은 오류 873건·오탐 330건을 근거로 룰 엣지케이스 목록을 정의하고 구현한 기록을 [rules-edge-cases](2026-09-23-rules-edge-cases.md)에 추가했다(368 passed, 캐시 평가 세부내역서 fp 273→43·영수증 fp 27→11·correct +12, 진단서 fp 16→9). main의 급여 열 총액 채우기는 라벨 근거가 없어 뺐다.
* **Update**: [rules-edge-cases](2026-09-23-rules-edge-cases.md)에 세부내역서 급여 프롬프트 재추출 평가를 더했다(이전 프롬프트 대조군과 비교: raw 급여 오탐 240→93, 룰 적용 후는 둘 다 0, rules 단계 차이는 재추출 흔들림 폭 안).
