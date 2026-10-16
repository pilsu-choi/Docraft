---
okf_version: "0.2"
---

- [backend·vLLM 라우터 2파드 고가용성](2026-10-15-ha-replicas.md) — 동시성 합계 나눔·RollingUpdate·기동 작업 경합 점검
- [릴리스 전 리뷰 수정](2026-10-15-review-fixes.md) — ephemeral requests 축소·failed 폴더명·저장 비동기·stage 오염·VLM 응답 마지막 20개
- [판독 실패 진단성 개선](2026-10-15-failure-observability.md) — 타임아웃 408 통일·실패 한 줄·VLM 호출 rid/upstream·실패 입력 보존/replay·Envoy 로그·ephemeral-storage 한도
- [진료비영수증 고객 오류 보고(10.14) 원인·대응](2026-10-14-receipt-customer-errors-cause.md) — 1·2차 보고 22사례 유형 P1~P8, 인쇄 행 이름·소계·빈 금액 0·보충 채택 규칙·인쇄 행 위치 대조, 97.01→97.14%(상위 wiki 동기화)

- [진단상태 칸 판독 구현](2026-10-14-cert-status-read-impl.md) — 상위 wiki에서 동기화
- [임상적추정·최종진단 오추출 원인](2026-10-14-cert-diagnosis-status-checkbox-cause.md) — 고객 75건 분석·검증 이력, 상위 wiki에서 동기화
- [짧은 키 파일럿·확대 측정](2026-10-14-short-keys-pilot.md) — 나머지 필드·금액산정 SHORT_KEYS, 필드 호출 출력 −17%, 기본 켬 dev 반영
- [응답 harness.timings](2026-10-13-response-timings.md) — 상위 wiki에서 동기화
- [끊긴 keep-alive 연결 재사용 오류 수정](2026-10-13-stale-keepalive-fix.md) — 공용 HTTP 클라이언트 경합, 유휴 2초·응답 전 끊김 1회 재전송
- [harness·Docraft 속도 개선과 L40S 동시 처리 상향](2026-10-13-speed-opt-gpu-concurrency.md) — GPU 동시 처리 한도 상향·연결 재사용·위치 찾기 선행 기본 켬, 실측 전
- [세부내역서 band 읽기 — OCR 행 경계 띠 (v1~v4)](2026-10-12-detail-band-ocr-rows.md) — 1쪽 세부내역서 band(BAND_DOC_TYPES로 켬), qwen3.8-27b 30건 rowmajor 84.5% → 92.3%(하네스 기준 89.7%), 영수증 불변, 띠 자르기 구조 수정 v11 96.1%, v13 97.0%
- [영수증 띠 프롬프트 쪼개진 머리글 안내(BAND_HEADER_NOTE)](2026-10-12-band-header-note.md) — 기본 켬(10/12), Nebius 10건 소표본 표 95.10→95.68%·고침 7·깨뜨림 0
- [영수증 금액 칸 단위 열 옮김 — OCR 인쇄 머리글 열로](2026-10-12-receipt-cell-column-move.md) — 모델 열과 인쇄 머리글 열이 다른 금액을 값 그대로 옮김, 바로 위 머리글 줄만 읽기, 197건 98.16→98.21%(12/0)·g25 불변
- [영수증 맨 오른쪽 열 — 열 맞바꿈 쪽 고르기·금액산정 경계 자르기](2026-10-12-receipt-rightcol-swap-crop.md) — 인쇄 머리글로 틀린 쪽(항목/합계 행) 고르기, 표 끝=패널 라벨 정렬선, 197건 98.05→98.14%·g25 불변·잘림 16→4칸
- [Docraft wiki 정리 (2026-10-12)](2026-10-12-wiki-cleanup.md) — 삭제·흡수·갱신 내역, 복구 기준 21db625, 판단 보류 목록
- [영수증 문서 단위 인쇄 정합(PRINT_REGISTER) 이식](2026-10-09-receipt-print-register-port.md) — band 결과의 반 행 인쇄 밀림을 OCR 줄 좌표·합계 기준점으로 문서 단위 되돌림, 기본 꺼짐, 197건 +48/0·g25 0/0 재생 일치
- [페이지 기울기 보정(PAGE_DESKEW)](2026-10-12-page-skew-correction.md) — 방향(90도 단위)+기울기를 한 각도로 합쳐 모델 이미지를 돌림, 띠 상자는 돌린 페이지 기준
- [영수증 항목표 band 읽기 이식](2026-10-09-receipt-band-port.md) — 위치 찾기→3띠 짧은 키 읽기→금액산정 블록 따로, 저장 응답 195건 재생 일치
- [영수증 합계 행 금액 되돌림](2026-10-09-receipt-total-row-shift.md) — 합계 금액이 위 행에 붙어 읽힌 것을 열 합으로 판별해 되돌림, 197건 고침 8·깨짐 0
- [영수증 별칭 재선별·위치 제약 이름·열 되돌림](2026-10-08-receipt-name-column-rules.md) — 정답지 30건 raw 96.44→97.37%
- [영수증 정답지 30건 Docraft 오류 원인](2026-10-08-receipt-g30-error-cause.md) — 항목명 오독 37%, 위치 제약 이름 맞춤 제안
- [영수증 항목표 OCR 행 골격 커버리지](2026-10-08-receipt-row-skeleton-coverage.md) — 인쇄만 78.0%·보충 93.4% vs A 90.3%, 행 후보 목록으로 호출 실험 예정
- [/api/read groundings 자료형·재처리 key 불일치 수정](2026-10-07-read-groundings-reprocess-keys.md) — unit_flags list 502, 재처리 KeyError
- [진료비영수증 항목명 원본 인쇄 표기 유지](2026-10-07-receipt-item-print-name.md) — 요약, 상세는 상위 wiki, dev 9ced432
- [진단서4종 진료소견 판독 필드 추가](2026-10-06-clinical-opinion-extract.md) — `_MEDICAL_FIELDS` 진료소견 text, dev 3d4f9e5
- [CI 공통 영수증 규칙 동기화](2026-10-03-ci-shared-receipt-policy.md) — 종료일 필수 키 사본 불일치 수정·gitlink 검증



# Docraft wiki

* [하네스·Docraft 에이전트 자가교정 설계](2026-10-05-agent-self-correction-design.md) - 실행 고리·개발 고리, 관문, 도입 순서(상위 wiki 동기화)
* [원본 데이터셋 7종의 이슈 노드 발생 조건](2026-10-04-dataset-node-conditions.md) - 97건 검토, 노드별 조건·회귀 후보

* [쪽 단위 무결성 탐지 — 근사 중복 쪽과 문서 경계](2026-10-05-page-integrity.md) - P.OVR.DUP.1·P.STR.DOC 탐지, 359쪽·31,626쌍 기준값, 정답지 59건 오탐 0

* [서식 무관 일반 보정 장치 1차 구현](2026-10-04-general-correction-devices.md) - 탐지 장치 5종, 59건 재생 정확도 불변, 정탐·오탐

* [Parse와 Extract 이슈 유형 계층 분류](2026-10-03-parse-extract-issue-taxonomy.md) - v4 생성 틀·111노드·완결성 검증
* [Parse·Extract 이슈 분류 의료비 문서 적용 프로파일](2026-10-03-parse-extract-taxonomy-medical-profile.md) - 노드별·문서 7종별 예시, 26건 대응
* [이슈 유형별 보정 장치 대응표](2026-10-04-issue-taxonomy-correction-coverage.md) - 일반 보정 방법·하네스/Docraft 장치 현황·우선순위
- [Parse·Extract 이슈 도감](2026-10-08-issue-taxonomy-gallery.md) — 노드 111개·보조 원인 10개의 원문·출력 비교 예시(관측 74·합성 38·추정 9), artifact 페이지
- [이슈 분류에 입력 매체·화질 조건 기록 축 추가](2026-10-12-issue-taxonomy-media-quality-axes.md) — 매체 14종·화질 열화 12종 포괄 점검, 입력 매체(생성·전달 경로·열화 이력)·화질 조건 축과 결과 노드·합성 메커니즘 대응


작업 기록은 Open Knowledge Format v0.2(`type` 등 YAML frontmatter + markdown 본문)을 따르며, 파일명은 `YYYY-MM-DD-<주제>.md`다. 변경 이력은 [log.md](log.md)에 남긴다.


# 계획과 구현 기록

* [진료비영수증 항목명 이름 규칙 보강(표준 표기 유지)](2026-09-30-receipt-item-names.md) - 재활및물리치료료·조제료 이름 규칙, 예약진찰료·응급 관리료 표준 항목 추가(하네스와 공통 표), 보철교정료·입원료_2-3인실 표기 유지
* [세부내역서 급여구분 스키마 설명: 공란 칸을 급여로 채우지 않기](2026-09-29-benefit-class-hint.md) - 급여구분 힌트에 인쇄된 값만·공란 null·추정 금지·TABLE_HINT 추가, 원인 경로(VLM 추출·BLANK_AO 채택)와 표본 4건 실측
* [/api/verify 응답에 요청 처리시간(verify.elapsed_ms) 추가](2026-09-28-response-elapsed.md) - 업로드 저장부터 응답 직전까지 걸린 시간을 documents[0].verify.elapsed_ms로 반환
* [auto_reprocess=false 읽기 오류와 ROI VLM 오채택 수정](2026-09-29-read-reprocess-fix.md) - 미할당 recovery_groundings 502 수정, ROI OCR이 지지한 원값을 VLM이 덮어쓰지 못하게 함
* [날짜·체크·표 셀의 유형별 원문 근거](2026-09-27-typed-evidence.md) - 라벨 역할이 확인된 날짜·체크 표기, 물리 표 셀·총계·빈칸과 제한된 null 교정
* [자동 재처리의 근거·규칙 우선순위](2026-09-27-reprocess-priority.md) - 원문 줄 위치와 규칙 위반을 확인한 필드에 제한된 재처리 예산을 먼저 배정
* [근거 기반 자동 재처리 루프](2026-09-27-auto-reprocess.md) - 일반 추출·의료 읽기 공통 ROI 재파싱·VLM 재판독, 필드별 재검증, 예산·취소·감사 이력과 안전한 채택 경계
* [자연 문서 자동 교정과 서식 인쇄 정렬 추론](2026-09-28-natural-corrections.md) - 독립 날짜 anchor로 인쇄 오프셋을 증명하고 등록 합계식으로 금액 필드를 원자적으로 교정한 기록
* [Parse·Extract 근거와 검토 상태 보강](2026-09-27-parse-extract-quality.md) - OCR 원문·행/열·페이지 좌표 기반 품질 신호와 API 계약, 76건 캐시 평가 및 97% 목표의 남은 한계
* [/api/read 최종 값의 원문 좌표 반환](2026-09-27-read-groundings.md) - 규칙 적용 뒤 값·행이 유일하게 대응하는 근거만 `groundings`로 제공
* [Harness와 Docraft의 key-value 추출 흐름 점검](2026-09-27-harness-docraft-kv-pipeline-review.md) - OCR·스키마 추출·검증·근거·사람 검토의 구현 범위와 통합 경로의 한계
* [운영자 긴급 중지: 문서 잡·in-flight 호출 취소 API](2026-09-27-작업-중지-API.md) - 대기·실행 중인 문서 잡 단건 취소(`POST /api/documents/{id}/cancel`)와 전체 취소(`POST /api/admin/cancel-all?confirm=true`). queued는 즉시 canceled, 실행 중은 documents.cancel_requested로 다음 단계 경계에서 협조적 취소, cancel-all은 진행 중인 모든 /api/verify·/api/read 호출도 함께 끊어 409로 마무리(클라이언트 연결 끊김 499와 구분)
* [Docraft를 하네스 읽기 서비스로 만드는 POST /api/read](2026-09-27-read-api.md) - AO 비교·rules.run·Judge 없이 Docraft 자체 추출만 돌려주는 읽기 전용 API. verify.run에서 공용 부분(resolve_doc_type·resolve_keys·verify.read)을 뽑아 재사용하고, /api/verify와 업로드·취소·in-flight 보일러플레이트(process_image)를 공유. health의 verify_inflight는 이름을 유지한 채 두 경로 합계를 센다
* [필수 필드 오독 교정 확대](2026-09-26-misread-correction.md) - 진료비영수증 항목명 오독 교정을 세 글자 이하까지 자모 하나 차이로 넓히고('진칠료'→'진찰료'), 날짜의 숫자에 붙은 O·I·l을 0·1로 읽게 함. 라벨 오독 매칭은 실제 낱말 오매칭('발생일'→'발행일')으로 보류
* [GPU 할당 방식 이원화: 카드 지정 모드 + device plugin 자원 모드](2026-09-26-GPU-할당-방식.md) - helm/docraft 차트의 paddleocrVl·paddleocrLines·vllmVlm 에 harness-v2 embedding 차트와 같은 nvidia.com/gpu 요청 기반 device plugin 모드를 추가하고 기존 deviceIds 카드 지정 모드와 헬퍼를 통합
* [보험 청구서류 7종 OCR 엣지 케이스 카탈로그 대응 점검](2026-09-25-ocr-edge-catalog-audit.md) - 카탈로그 102개 ID와 검산식 11개를 현재 코드와 대조한 지원·부분·미지원 판정 및 우선 대응 순서
* [하네스 표본 7종 e2e에서 드러난 /api/verify 수정](2026-09-24-verify-harness-e2e-fixes.md) - 진단서 계열 정의 밖 key(사고발생일자) 502, `_balance` 가 Docraft 항목명까지 가져오던 문제(이름 유지 짝 조건·합계 행·정의 밖 열), 하네스 서식 재분류의 값 없는 AO 요청은 Judge 없이 Docraft 추출값 사용
* [자동 통과 칸 review 표시와 자동 통과 정확도](2026-09-24-auto-review.md) - AO·Docraft 엄격 불일치·남은 CALC·STRUCT 이상·통째로 빈 인쇄 열에 `review`를 붙여, 자동 통과 칸 정확도 세부내역서 99.71%(76.2%)·영수증 99.11%(81.5%), 남은 오류와 공유 서버 운영 주의
* [e2e 57건 엣지케이스](2026-09-24-e2e-edge-cases.md) - `비급 구분` 열 서식(빈칸·`100%`=급여), 실시일 칸 입원기간, 병실 칸 진료과, 섹션 제목 행, `총투`·`수량` 머리글, 코드 칸 `-`, AO 자리표시 `열추출`, Judge의 금액 지어내기, 정답지 관례 차이와 처리 상태
* [harness-v2 e2e 57건 AO 단독 vs AO+Docraft 최종 정확도](2026-09-24-e2e-ao-verify.md) - AO 응답을 AWS `/api/verify`에 넣고 e2e 채점기로 같은 칸 집합에서 비교: 영수증 96.16%→98.04%, 세부내역서 94.36%→94.08%(악화 원인·남은 오류 필드), 하네스는 값을 바꾸지 않음
* [세부내역서 머리글 없는 표 처리](2026-09-24-detail-headerless.md) - `_headers`가 오타·병합 셀·머리글 없는 이어지는 쪽에서 열 머리글을 놓치던 문제를 머리글 낱말 행·병합 셀 분리·금액×횟수×일수=총액 추론으로 보강. 76건 세부내역서 fp 88→63, e2e 차이는 Judge 편차
* [세부내역서 e2e 표적 룰](2026-09-24-detail-target-rules.md) - 병실 진료과·섹션 항목·투여량(총투·수량 머리글, AO 빈 칸)·EDI S/B 정규화·Judge 합의 칸 보존. e2e 재적용 94.08%→95.33%, 76건 rules 변화 없음(fp −1)
* [/api/verify 연결 끊김 중단과 AWS 배포 잠금](2026-09-23-verify-ops.md) - 클라이언트가 끊기면 추출·Judge 전에 멈추고(실측 89.9초에 중단), 배포 잠금(`flock`)·배포 기록(`DEPLOYED`)·처리 중 요청이 있으면 거부(`verify_inflight`, 실측 exit 3)·자기 터널만 끄는 `tunnel.sh`, 필수 필드에서 납부할금액 제외
* [필수 필드 누락 룰 MISSING.REQUIRED](2026-09-23-required-fields.md) - 설계안 4단계: 고객 후처리 플러그인·반출 샘플·라벨 93건 빈 값 비율로 유형별 필수 필드를 `rules.yaml` `required`에 정의하고, AO에서 비면 Judge 힌트로 보내고 끝까지 비면 `review`로 표시. 라벨 헛경고 93건 중 2건
* [룰 레지스트리·반복 교정·rulesets YAML 구현](2026-09-23-rule-registry.md) - 설계안 1~3단계: 검사·교정 18개를 `rules.RULES`로, `rules.run` 최대 3회 반복·`verify.trace`·ESCALATE `review` 표시, 룰 데이터 표 23개를 `backend/rulesets/rules.yaml`로 옮기고 `disable` 추가. 1·3단계 동작 변화 0 대조, 범위 룰은 걸릴 일이 없어 뺌
* [합계식 Judge 판정 보조와 선별급여 라벨 통일](2026-09-23-sum-guard-labels.md) - Judge 판정이 합계식을 더 어기면 불일치가 줄어드는 AO·Docraft 값으로 되돌리는 `verify._balance`(`rules.sum_errors`)와 한방 흐린 팩스 문서 결과, 정답셋 선별급여 행 이름 7건 conform과 76건 새 기준점
* [진료비영수증 이슈 정리 260923 룰 해결](2026-09-23-receipt-issues-0923.md) - 열 전체가 서식에 없는 열로 간 매핑 오류(파서 머리글 기준 `no_column`, 교정은 `column_shift`로 통합), 선별급여 유의어·한방 항목·한 글자 오독 항목명 교정(`item_name`), 한방 소계 열 오매핑 비우기와 퇴행·라벨 관례 충돌 측정
* [마스터 명칭 유사도 검토 필요 플래그 — 임계값 스윕 결과와 보류 결정](2026-09-23-master-name-mismatch-flag.md) - 코드는 마스터에 있는데 인쇄 명칭이 후보 전부와 크게 다른 행을 `검토 필요`로 표시하는 안을 difflib로, 이어서 harness-v2 BAAI/bge-m3 임베딩 코사인 유사도로 76건 재평가(임계값 0.05~0.95 스윕, 결합 규칙 포함)했으나 최고 정밀도가 병명 40%·EDI 21%로 목표(70%) 미달이라 검사는 추가하지 않고 두 조회 함수(difflib `similarity()`, 임베딩) 모두 제거한 결정 기록
* [KCD·EDI 마스터 원본 소스를 harness DB·docraft DB로 재사용](2026-09-23-master-source-reuse.md) - `data/master`(dockerignore 대상, 로컬 전용) 대신 harness-v2 Postgres 재사용 → docraft DB `master_code` 재사용 → `MASTER_SOURCE_DIR` 원본 신규 적재 순으로 소스를 해석하는 구현: advisory lock으로 감싼 COPY 적재, `python -m backend.master --source` 강제 재적재, compose/helm 배포 배선, 381 passed
* [POST /api/verify에 hint_paths 필드 추가](2026-09-23-verify-hint-paths.md) - harness-v2 룰 엔진이 확정 못한 필드만 골라 Docraft 교차검증·Judge를 돌리는 선택 form 필드 `hint_paths` 구현: 추출 스키마 축소, 힌트 밖 필드는 판정 정보 없이 AO 값 그대로 반환, counts는 판정된 key만 집계
* [Docraft Helm 차트(k8s, GPU 서빙 포함)](2026-09-23-k8s-helm-chart.md) - harness-installer 우산 차트의 서브차트로 쓸 `deploy/k8s/helm/docraft`를 harness-v2 mlife-harness 차트 관례로 구현. backend/worker/frontend, 외부 Postgres·Redis 연결(existingSecret 패턴), PaddleOCR-VL·PP-OCRv5·Qwen3-VL(vLLM) 세 GPU 컴포넌트의 deviceIds 기반 카드 지정과 L40S 2장 배치 기본값, helm lint/template 검증과 정수 quote 버그 수정 기록
* [수술확인서·입퇴원확인서·약제비영수증 유형 추가](2026-09-23-doctypes-3more.md) - 남은 3종 정의(진단서 스키마 재사용, 약제비 15필드, AO 이름 alias), 제목 확인으로 고른 57건 평가셋, VLM 라벨 검수 248건, 검수 후속 룰 보강과 rules 정확도(수술 92.1%, 입퇴원 96.2%, 약제비 94.8%)
* [룰 엔진 엣지케이스 확장](2026-09-23-rules-edge-cases.md) - 열 밀림·통째 맞바꿈·산술·근거·형식·표 구조 엣지케이스 목록과 룰별 캐시 평가 효과(세부내역서 fp 273→43, 영수증 fp 27→11), 헛경고 측정, 버린 룰, main 급여 열 관례 조정
* [rules 후처리 흐름 예시 풀이](2026-09-23-rules-flow-example.md) - 추출(`rules.apply`)과 룰 검사·교정 반복(`rules.run`), Judge·합계 보조를 진단서·진료비영수증 예시로 실제 실행해 보여 주는 설명과 이름 도장 표시(`(인)`) 버그 수정
* [추출 VLM qwen3.5-27b 전환과 AI_REASONING](2026-09-23-vlm-model-qwen35.md) - qwen3.5-27b 전환 배경·OpenRouter 확인(단가·컨텍스트)과, 기본 사고 모드로 인한 추출 호출 10배 지연 실측 및 `AI_REASONING` 설정으로 끄는 구현

* [파서 표 복원 보강(기울기 보정·해상도 비례 격자)](2026-09-22-table-restore.md) - 모델과 무관한 파서 구조 지표(`scripts/parse_audit.py`), 기울기·`_runs` 정렬 버그·셀 병합 오판 분류, 38건 구조 지표와 76건 정확도 전후

* [추출 프롬프트에 인쇄 항목명·코드 근거 제약 추가](2026-09-22-extract-grounding.md) - 인쇄되지 않은 표준 항목 행 생성과 표준 명칭 치환을 프롬프트로 억제한 구현, 모델 재실행 변동 폭 측정과 1차 지침 실패·2차 채택 근거

* [key-value 정확도 개선 3건 통합 평가](2026-09-22-kv-accuracy-integration.md) - 행 정렬·보충 오탐 억제·마스터 명칭 교정 세 브랜치 병합과 76건 재평가, 가산성 확인과 남은 오류 원인

* [KCD·EDI 마스터 사전 명칭 교정](2026-09-22-master-name-correction.md) - 마스터 조회 CSV 생성과 코드 일치 행의 1글자 명칭 교정, 76건 전후 수치와 임계값 근거

* [라벨 보충(_fill) 오탐 억제](2026-09-22-kv-fill-false-positives.md) - 영역 제약·상호배제·근거 등급으로 rules 보충 오탐을 줄인 구현과 전후 수치

* [표 행을 키 열로 대응하고 세분 항목명을 보존](2026-09-22-kv-row-align.md) - 짝짓기 규칙을 rules.pair_rows 한 곳으로 모으고, 영수증 항목 행을 파서 표 순서·세분 항목명으로 바로잡고 소계 행을 보존한 구현(76건 전후 수치 포함)





* [Agentic OCR 2.0 결과 교차검증·자동 교정 API 구현](2026-09-22-ocr-verify.md) - POST /api/verify 구현 기록: doctypes·rules(twin reader 이식·확장)·verify(Judge)·AO 키/값 누락 대응·진료비영수증 표 오류 검출·교정과 정답셋 평가 결과
* [추출·스키마 생성에 페이지 이미지 첨부](2026-09-22-vision-extract.md) - OCR 텍스트만 보내던 VLM 호출에 문서 페이지 이미지를 함께 보내 병합 셀 표의 값·합계 오류를 없앤 기록
* [OCR 줄 좌표 기반 grounding](2026-09-22-ocr-line-grounding.md) - 표 블록을 행 수로 균등 분할해 추정하던 grounding bbox를 PP-OCRv5 줄 단위 OCR 좌표로 교체한 기록
* [라벨 기준 grounding과 합계 필드 추출 지시](2026-09-22-label-grounding.md) - 같은 값이 여러 셀에 있을 때 필드 라벨 옆 줄을 고르고, 합계 필드가 개별 항목 값을 가져오던 추출 오류를 프롬프트로 바로잡은 기록
* [작업 큐(Queue·Worker) 구조 도입](2026-09-22-job-queue.md) - 파싱·추출을 inline·celery로 교체 가능한 작업 큐에서 실행하고 공용 redis/Celery 인프라에 붙이는 구성
* [작업 큐 중단 작업 자동 복구](2026-09-22-job-recovery.md) - heartbeat lease와 기동 시 재등록으로 worker 중단·inline 재시작에도 문서가 멈추지 않게 한 구성
* [스키마 내보내기](2026-09-22-schema-export.md) - 편집 중인 JSON Schema를 title(스키마 이름)과 함께 파일로 내려받는 기능
* [프로젝트 전환 시 이전 스키마 상태 노출 수정](2026-09-22-project-state-reset.md) - 새 프로젝트 생성·이동 시 이전 프로젝트의 탭·스키마 편집 상태가 남던 버그의 원인과 수정
* [추출 지침·필드 구조 확대 편집 모달](2026-09-22-zoom-modal.md) - 추출 지침·필드 구조를 모달에서 편집하고 전체 화면으로 확대·축소하는 기능
* [표 모델 비교와 VLM 셀 텍스트 교정](2026-09-22-table-refine.md) - VL·PP-StructureV3·Qwen3-VL 표 인식 비교와 VL 격자에 VLM 셀 교정을 얹은 TABLE_REFINE
* [표 병합 셀 보존](2026-09-22-table-spans.md) - PaddleOCR-VL 표의 rowspan·colspan을 직사각형 격자와 spans로 보존하고 남은 모델 인식 오류를 정리
* [괘선 격자 기반 표 구조 복원](2026-09-22-ruled-table-grid.md) - 외부 파서 결과를 분석해 격자 우선 방식을 확인하고, VLM 표 HTML 대신 인쇄된 괘선에서 행·열·병합 셀을 복원
* [AWS 개발 서버 배포 스크립트](2026-09-22-aws-deploy.md) - harness-v2와 같은 EC2(NVIDIA L4)에 app + PaddleOCR 스택을 오버레이 방식으로 올리는 deploy/aws 스크립트
* [AWS 이미지 병렬 처리량과 중규모 내구성](2026-09-22-aws-throughput.md) - 서비스별 동시성 한계와 이미지 100건 연속 처리 측정, QUEUE_CONCURRENCY=6 결정, 업로드 413·삭제 파일 잔존 수정
* [작업 진행 중 로딩바](2026-09-22-loading-bar.md) - 요청 대기·백그라운드 문서 처리 중 상단바에 로딩바와 진행 문구를 보여주는 기능
* [추출 페이지 단위 분할 호출](2026-09-22-extract-page-chunking.md) - 긴 문서를 페이지 경계 기준으로 나눠 여러 번 호출하고 스키마에 따라 결과를 병합하는 구현
* [레퍼런스 기반 개선 1~3단계 구현](2026-09-22-refs-improvements.md) - 문서 목록 경량화·삭제, 결과 표·일괄 추출·XLSX, 블록 연동·스키마 편집·API 탭·파싱 옵션 구현
* [피드백 UI 반영](2026-09-21-feedback-ui.md) - feedback.md 4개 항목(필드 근거 호버, Markdown·JSON 토글, 스키마 설명 편집) 반영
* [Markdown·HTML 뷰어](2026-09-21-markdown-html-viewer.md) - Markdown·HTML 원본 렌더링, 분석 결과 미리보기·HTML 출력, HTML 업로드 파싱
* [분석 결과 표 미리보기와 JSON 색상](2026-09-21-table-preview.md) - 블록 카드 미리보기로 OCR 표 렌더링, JSON 문법 색상
* [Agentic OCR 2.0.1 fixture conversion](2026-09-21-fixture-conversion.md) - Agentic OCR 2.0.1 PNG fixture를 텍스트 레이어 포함 PDF로 변환한 절차
* [구현 기록](2026-09-21-implementation.md) - PRD P0 요구사항과 검증 근거 매핑, 통합 검증 결과
* [백엔드 로깅과 Docker 전체 스택](2026-09-21-logging-docker.md) - 백엔드 레벨별 로깅(docraft.log)과 postgres·backend·frontend Docker 전체 스택 구성
* [PaddleOCR-VL 로컬 Docker 호스팅](2026-09-21-paddleocr-docker.md) - PaddleOCR-VL을 compose ocr profile로 로컬 GPU에 호스팅한 구성과 검증
* [PDF 근거 상자 정밀화](2026-09-21-pdf-line-bbox.md) - PDF 근거 상자를 텍스트 블록에서 줄 단위로 정밀화
* [프로젝트 작업공간 백엔드 변경 기록](2026-09-21-project-workspace-backend.md) - PostgreSQL 전환, 프로젝트·스키마 CRUD, SQLite 이관 도구 기록

# 조사

* [레퍼런스 기반 개선·기능 추가 후보](2026-09-21-refs-improvement-review.md) - refs 3사 화면과 현재 UI·backend를 비교한 개선·신규 기능 후보와 우선순위
* [PaddleOCR 호환성 조사](2026-09-21-paddleocr-compatibility.md) - PaddleOCR 원격·on-prem layout-parsing HTTP 계약과 Docraft adapter 출력 규약 조사

# 장애와 버그 수정

* [원문 근거 상자 표시 수정](2026-09-21-bbox-rendering-fix.md) - 원문 근거 상자가 정규화 좌표로 오인돼 잘못 그려지던 문제의 원인과 수정
* [추출 실패: VLM 응답 JSON 파싱 오류](2026-09-21-extract-json-parse-failure.md) - VLM 추출 응답 JSON 파싱 실패(Expecting ',' delimiter)의 원인 분석과 대응 후보
* [추출 grounding 서버 측 계산 전환과 json_object 계약](2026-09-21-extract-grounding-block-id.md) - extract()를 json_object 단일 결과 계약으로 바꾸고, grounding을 모델 응답 대신 서버가 원문 블록에서 값을 찾아 계산하도록 전환한 기록
* [원본 문서 미리보기 크기 수정](2026-09-21-ui-preview-fix.md) - 원본 PDF·이미지 미리보기가 패널보다 커지던 문제의 원인과 수정

# 테스트 기록

* [AI provider 검증 기록](2026-09-21-ai-provider-validation.md) - OpenAI 호환 AI provider 계약 테스트와 OpenRouter Qwen 실호출 검증
* [프로젝트 작업공간 테스트 기록](2026-09-21-project-workspace-tests.md) - 프로젝트 작업공간의 PostgreSQL 격리 통합 테스트와 E2E 결과

* [/api/read row_filter](2026-09-29-read-row-filter.md) - 지정한 행만 생성하게 해 재읽기 시간을 줄이는 인자
* [요양기관종류 체크박스 판독 지침과 텍스트 일치 판정 보정](2026-10-02-institution-type-checkbox.md) - 표시된 선택지만 답이라는 필드 설명, 선택지를 품은 값을 같다고 보던 오판을 enum 정확 비교로 수정
* [/api/read 지연과 HTTP 408 대응](2026-10-02-read-지연-대응.md) - 같은 페이지 OCR·표 교정 공유, 표 교정 병렬·분할, GPU OCR 동시성 제한, 재처리·모델 호출 시한, 단계별 시간 로그
* [돌아간 스캔의 방향 정규화](2026-10-02-scan-orientation.md) - 90°·180°·270° 스캔을 줄 상자·마침표 위치로 판별해 바로 세워 다시 읽고 좌표는 원본 기준 유지
* [rowmajor 열 배치·게이트 보강과 무리 값 채우기](2026-10-02-rowmajor-rotation-fixes.md) - 기간 한 칸 두 일자·못 읽은 짝 열 유지·같은 개념 열 표기·금액 빈 행·무너진 행 게이트(0.6)·출력 상한·섹션 제목·진료기간 채우기, 59건 92.47%
* [여러 쪽 표를 쪽 묶음별로 나눠 읽기](2026-10-03-pagewise-table.md) - 응답 상한 16k·4쪽 안의 쪽 묶음 병렬, 쪽 다수결 열 배치 하나, 실패한 쪽만 asis, 쪽 순서 이어 붙이기. length 오류 0, 21세기 −59% 지연, 아주대 0→330행
* [rowmajor 열 배치는 근거가 있을 때만, 약하면 알림](2026-10-05-column-evidence.md) - 필수 열은 머리글 조각·본문 값 근거로만, 코드 두 열은 낱말·값 꼴, 머리글 없는 표는 yaml 순서·값 꼴 점수, column_plan 알림, OpenRouter 35회

## 루트 공통 기록 동기화 (2026-10-03)

* [2026-09-27-auto-reprocess-loop](2026-09-27-auto-reprocess-loop.md)
* [2026-09-27-image-parse-extract-edge-cases](2026-09-27-image-parse-extract-edge-cases.md)
* [2026-09-28-extract-coverage-rules](2026-09-28-extract-coverage-rules.md)
* [2026-09-29-request-trace-logging](2026-09-29-request-trace-logging.md)
* [2026-09-30-autoscaling-plan](2026-09-30-autoscaling-plan.md)
* [2026-09-30-aws-orchestrator-harness-callback-e2e](2026-09-30-aws-orchestrator-harness-callback-e2e.md)
* [2026-09-30-golden-set-59-aws-harness-benchmark](2026-09-30-golden-set-59-aws-harness-benchmark.md)
* [2026-10-02-detail-filldown-group-values](2026-10-02-detail-filldown-group-values.md)
* [2026-10-02-detail-testset200](2026-10-02-detail-testset200.md)
* [2026-10-02-docraft-read-latency-analysis](2026-10-02-docraft-read-latency-analysis.md)
* [2026-10-02-extra-detail-validation](2026-10-02-extra-detail-validation.md)
* [2026-10-02-extraction-accuracy-paper-experiments](2026-10-02-extraction-accuracy-paper-experiments.md)
* [2026-10-02-golden-harness-misextraction-analysis](2026-10-02-golden-harness-misextraction-analysis.md)
* [2026-10-02-rule-based-kv-extract-review](2026-10-02-rule-based-kv-extract-review.md)
* [2026-10-02-six-type-testsets](2026-10-02-six-type-testsets.md)
* [2026-10-02-table-rowmajor-report](2026-10-02-table-rowmajor-report.md)
* [2026-10-03-golden-benefit-printed-only](2026-10-03-golden-benefit-printed-only.md)
* [2026-10-03-harness-docraft-architecture-quality-review](2026-10-03-harness-docraft-architecture-quality-review.md)
* [2026-10-03-medical-table-parsing-research](2026-10-03-medical-table-parsing-research.md)
* [2026-10-03-model-fixed-table-algorithms](2026-10-03-model-fixed-table-algorithms.md)
* [2026-10-03-review-integrity-remediation](2026-10-03-review-integrity-remediation.md)
* [2026-10-03-summary-rows-policy-integration](2026-10-03-summary-rows-policy-integration.md)
* [2026-10-03-synthetic-dataset-codex-작업지시서](2026-10-03-synthetic-dataset-codex-작업지시서.md)
* [2026-10-03-parse-extract-보강-작업지시서](2026-10-03-parse-extract-보강-작업지시서.md)


- [서식 재분류 기본 OFF와 재생성 가이드](2026-10-03-classification-default-off.md) — ON/OFF·API/worker·AWS/Helm 적용

- [약제영수증 진료비내역-비급여 칸 반영](2026-10-05-pharmacy-noncovered-field.md) — 1005 약제 스키마 비교, 비급여 추가(상위 wiki 동기화)

- [빽빽한 표 쪽을 행 띠로 나눠 읽기](2026-10-05-dense-page-split.md) — 한 응답에 들지 않는 쪽만 OCR 줄 틈에서 띠로 잘라 읽기, 건국대 41→195행·청담 2·3쪽 0→124행
- [진료비영수증 키 상한액초과금 정정](2026-10-07-limit-excess-key.md) — Docraft 키 상환액초과금 오기 정정, 입력 별칭 장치 없음
* [사고 모드 끄기 — vLLM enable_thinking·json_schema 포함](2026-10-13-thinking-off-vllm.md) - AI_REASONING=off가 모든 호출에 reasoning + chat_template_kwargs.enable_thinking=false
- [고객 AO 추출 항목 변경 대응 (투여량·선택진료료이외총액·입퇴원일자 배열)](2026-10-14-ao-field-change-1014.md) — harness dev 7318fd2·Docraft dev 484fc3b(미push), 날짜 선후 배열·배열 형식 보존, 정답지 200건·채점 별칭
- [영수증 같은 인쇄 행 판정 통일·인쇄명 사전 우선](2026-10-15-receipt-row-identity.md) — 하네스 문서 동기화, Docraft rules._item 사전 우선·공용 yaml
