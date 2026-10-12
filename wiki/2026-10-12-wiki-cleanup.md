---
type: change
title: Docraft wiki 정리 (2026-10-12)
description: 낡은 중간 기록·구현 끝난 계획서를 삭제하거나 최신 문서로 흡수하고, 현재 기본값에 맞게 일부 문서와 README를 갱신한 정리 내역
tags: [docraft, wiki, cleanup]
status: active
---

날짜: 2026-10-12
브랜치: `docs/wiki-cleanup` (dev 21db625 기준)
워크트리: `Docraft/.worktrees/docs-wiki-cleanup`

복구 기준 커밋은 Docraft dev `21db625`다. 삭제·흡수한 문서는 `git show 21db625:wiki/<파일명>.md`로 되살릴 수 있다. 현재 상태 요약은 상위 진입 문서 `/home/pilsu/projects/mirae-assets/wiki/2026-10-12-current-state.md`를 본다.

## 처리 내역

| 문서 | 처리 | 이유 | 흡수한 문서 |
| --- | --- | --- | --- |
| 2026-09-21-agents-md-rules | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-21-backend-implementation | 삭제 | 이미 deprecated, SQLite·Tesseract 시기 구현 | - |
| 2026-09-21-dev-merge | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-21-implementation-session | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-21-project-workspace-plan | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-21-ui-redesign-plan | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-22-accuracy-eval-expansion | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-22-kv-accuracy-review | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-22-ocr-verify-labels | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-22-ocr-verify-plan | 삭제 | draft 계획서, 구현 또는 후속 문서로 대체(rule-registry·ocr-verify·read-api 등) | - |
| 2026-09-22-readme-architecture | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-22-rule-performance-review | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-22-verify-rule-first-plan | 삭제 | draft 계획서, 구현 또는 후속 문서로 대체(rule-registry·ocr-verify·read-api 등) | - |
| 2026-09-23-label-alignment-and-model-compare | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-23-label-review | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-23-receipt-issue-cases | 흡수 후 삭제 | 같은 0923 영수증 이슈 3건 중복 정리 | 2026-09-23-receipt-issues-0923 |
| 2026-09-23-rule-engine-design | 삭제 | draft 계획서, 구현 또는 후속 문서로 대체(rule-registry·ocr-verify·read-api 등) | - |
| 2026-09-23-verify-test-0922 | 흡수 후 삭제 | AO 교차검증 시기 평가 수치·라벨 관례(정답지 59건 체계로 대체) 흡수 | 2026-09-22-ocr-verify |
| 2026-09-24-e2e-210-plan | 삭제 | draft 계획서, 구현 또는 후속 문서로 대체(rule-registry·ocr-verify·read-api 등) | - |
| 2026-09-25-edge-speed-accuracy-priorities | 삭제 | draft 계획서, 구현 또는 후속 문서로 대체(rule-registry·ocr-verify·read-api 등) | - |
| 2026-09-27-request-id-logging | 흡수 후 삭제 | 요청 ID 로깅을 trace 문서가 포괄 | 2026-09-29-request-trace-logging |
| 2026-09-27-untrack-context-feedback | 삭제 | 일회성 진행·계획 기록, README·AGENTS.md·코드가 현재 근거 | - |
| 2026-09-28-mig-gpu-resource-name | 흡수 후 삭제 | GPU 자원명 변경 근거를 GPU 할당 문서로 합침 | 2026-09-26-GPU-할당-방식 |
| 2026-09-29-harness-flow-briefing | 삭제 | 10-08 하네스·Docraft 흐름 보고서와 README가 대체 | - |
| 2026-09-30-harness-issue-todo | 흡수 후 삭제 | 9/30 TODO, 남은 항목은 오추출 분석으로 흡수 | 2026-10-02-golden-harness-misextraction-analysis |
| 2026-09-30-harness-weekly-briefing | 삭제 | 10-08 하네스·Docraft 흐름 보고서와 README가 대체 | - |
| 2026-10-02-agents-aws-batch-test | 삭제 | AGENTS.md에 이미 반영된 지침 또는 일회성 요약 | - |
| 2026-10-02-agents-bug-principle | 삭제 | AGENTS.md에 이미 반영된 지침 또는 일회성 요약 | - |
| 2026-10-02-aws-integrated-deploy-1002c | 흡수 후 삭제 | 배포 중간 회차, 회차별 결과 표로 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-1002d | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-1002f | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-1002g | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-1002h | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-1002i | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-1002j | 흡수 후 삭제 | 배포 중간 회차, 회차별 결과 표로 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-deploy-r3 | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-aws-integrated-feature-test | 흡수 후 삭제 | 기능별 AWS 확인 결과를 콜백 e2e로 흡수 | 2026-09-30-aws-orchestrator-harness-callback-e2e |
| 2026-10-02-aws-redeploy-golden59-rerun | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-02-golden-benefit-col-extract-unify | 흡수 후 삭제 | 열추출 유지 결정이 10-03 인쇄분만 정책으로 대체 | 2026-10-03-golden-benefit-printed-only |
| 2026-10-02-institution-type-r3-followup | 흡수 후 삭제 | 요양기관종류 후속 결정(표준 4종) | 2026-10-02-institution-type-checkbox |
| 2026-10-02-table-rowmajor-ab-experiment | 흡수 후 삭제 | rowmajor 실험·조건·이식 기록을 보고서로 합침(기본값은 이후 band, 비영수증은 rowmajor) | 2026-10-02-table-rowmajor-report |
| 2026-10-02-table-rowmajor-conditional | 흡수 후 삭제 | rowmajor 실험·조건·이식 기록을 보고서로 합침(기본값은 이후 band, 비영수증은 rowmajor) | 2026-10-02-table-rowmajor-report |
| 2026-10-02-table-rowmajor-port | 흡수 후 삭제 | rowmajor 실험·조건·이식 기록을 보고서로 합침(기본값은 이후 band, 비영수증은 rowmajor) | 2026-10-02-table-rowmajor-report |
| 2026-10-03-classification-toggle-check | 흡수 후 삭제 | 재분류 설정 확인은 기본 OFF 운영 가이드가 포괄 | 2026-10-03-classification-default-off |
| 2026-10-03-colplan-evidence | 흡수 후 삭제 | 열 배치 근거 규칙을 column-evidence가 포괄 | 2026-10-05-column-evidence |
| 2026-10-03-issue-taxonomy-work-plan | 흡수 후 삭제 | draft 작업 계획, 분류 본문이 포괄 | 2026-10-03-parse-extract-issue-taxonomy |
| 2026-10-03-medical-table-comparison-design | 삭제 | 이미 deprecated, 모델 고정 실험안으로 대체 | - |
| 2026-10-03-oct02-weekly-report-summary | 삭제 | 10-08 하네스·Docraft 흐름 보고서와 README가 대체 | - |
| 2026-10-03-parallel-subagents-preference | 삭제 | AGENTS.md에 이미 반영된 지침 또는 일회성 요약 | - |
| 2026-10-03-printed-only-derive | 흡수 후 삭제 | 인쇄된 값만 추출 정책(고객사 결정 10-03) 근거 통합 | 2026-10-03-summary-rows-policy-integration |
| 2026-10-03-printed-period-fields | 흡수 후 삭제 | 인쇄된 값만 추출 정책(고객사 결정 10-03) 근거 통합 | 2026-10-03-summary-rows-policy-integration |
| 2026-10-03-review-integrity | 흡수 후 삭제 | 구조 검토 D1·D3·D5 근거를 보강 기록에 합침 | 2026-10-03-review-integrity-remediation |
| 2026-10-03-root-wiki-sync | 삭제 | AGENTS.md에 이미 반영된 지침 또는 일회성 요약 | - |
| 2026-10-03-summary-rows-printed-benefit | 흡수 후 삭제 | 인쇄된 값만 추출 정책(고객사 결정 10-03) 근거 통합 | 2026-10-03-summary-rows-policy-integration |
| 2026-10-06-aws-integrated-deploy-1006a | 흡수 후 삭제 | 배포 회차별 59건 점수 수치만 남기고 흡수 | 2026-09-30-golden-set-59-aws-harness-benchmark |
| 2026-10-07-receipt-alias-sync | 흡수 후 삭제 | 별칭 법령 오독 변경은 이름 열 규칙에 반영 | 2026-10-08-receipt-name-column-rules |
| 2026-10-08-receipt-docraft-error-cause | 흡수 후 삭제 | 197건 오류 원인 요약을 g30 원인 분석이 포괄 | 2026-10-08-receipt-g30-error-cause |
| 2026-10-08-receipt-schema-aliases | 삭제 | 이미 deprecated, 별칭은 10-08 name-column-rules에서 되돌림 | - |
| 2026-09-22-aws-deploy | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-23-vlm-model-qwen35 | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-22-master-name-correction | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-23-master-name-mismatch-flag | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-23-master-source-reuse | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-23-rules-flow-example | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-23-verify-hint-paths | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-27-read-api | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-10-02-read-지연-대응 | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-09-23-k8s-helm-chart | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-10-02-table-rowmajor-report | 갱신 | 2026-10-12 갱신 절 추가 | - |
| 2026-10-03-classification-default-off | 갱신 | 2026-10-12 갱신 절 추가 | - |

## 판단 보류 (손대지 않음)

- 2026-09-21-fixture-conversion
- 2026-09-21-implementation
- 2026-09-21-refs-improvement-review
- 2026-09-22-refs-improvements
- 2026-09-27-parse-extract-quality
- 2026-09-30-autoscaling-plan
- 2026-10-02-rule-based-kv-extract-review
- 2026-10-02-scan-orientation
- 2026-10-03-medical-table-parsing-research
- 2026-10-03-model-fixed-table-algorithms
- 2026-10-03-parse-extract-보강-작업지시서
- 2026-10-03-synthetic-dataset-codex-작업지시서
- refs-competitor-capture

## 기타

- README: OpenRouter 서술을 Nebius vLLM·고객사 자체 vLLM으로 고치고 `AI_TIMEOUT` 행을 추가했다.
- 삭제 문서로 가던 링크는 텍스트로 바꾸거나 흡수 대상 문서로 돌렸다. `log.md`의 기존 이력은 유지했다.
