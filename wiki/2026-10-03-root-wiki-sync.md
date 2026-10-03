---
okf_version: "0.2"
type: report
title: 루트 공통 wiki의 Docraft 관련 기록 동기화
description: 누락된 공통 기록과 첨부를 저장소 wiki에 병합하고 공통 원본 우선 지침을 반영한 기록
tags: [docraft, wiki, synchronization, provenance]
status: active
---

날짜: 2026-10-03  
브랜치: `docs/wiki-sync-20261003` → `dev`  
워크트리: `Docraft/.worktrees/wiki-sync-20261003`

## 범위와 판단

공통 원본은 `/home/pilsu/projects/mirae-assets/wiki`다. Parse·Extract·OCR 엣지 케이스, 사용자 정책, 통합 파이프라인·배포·정확도 평가, 데이터셋/실험 설계, 아키텍처와 공통 AGENTS 규칙을 내용으로 선정했다. UI 응답 수집·Viewer 전용 작업과 past-data 저장소 갱신은 제외했다. label-viewer만 변경한 1002e도 제외했다. 통합 배포에서 Docraft 버전·입출력·평가를 다룬 기록은 포함한다.

날짜 없는 작업지시서는 `2026-10-03-parse-extract-보강-작업지시서.md`로 옮겨 동기화 날짜·원문 경로·메타데이터를 명시했다. 원본 작성일을 추정하지 않았다. 원문 frontmatter의 active/deprecated 상태와 당시 브랜치·실측 범위를 보존했다.

## 같은 이름 기록 병합

기존 저장소 문서 5건의 구현 설명·검증 결과를 보존하고 루트의 상세 실험 및 다른 저장소 통합 이력을 출처가 있는 보충 절에 합쳤다. 서로 다른 날짜의 정책·수치를 하나의 현행 결과로 합산하지 않는다.

- [2026-09-27-parse-extract-quality.md](2026-09-27-parse-extract-quality.md)
- [2026-09-27-reprocess-priority.md](2026-09-27-reprocess-priority.md)
- [2026-09-27-typed-evidence.md](2026-09-27-typed-evidence.md)
- [2026-09-28-natural-corrections.md](2026-09-28-natural-corrections.md)
- [2026-09-28-response-elapsed.md](2026-09-28-response-elapsed.md)

## 동기화 목록

신규 공통 문서 46건, 기존 문서 보충 5건, 첨부 12건. 이 동기화 보고서는 별도 신규 문서다.

- [2026-09-27-auto-reprocess-loop.md](2026-09-27-auto-reprocess-loop.md)
- [2026-09-27-image-parse-extract-edge-cases.md](2026-09-27-image-parse-extract-edge-cases.md)
- [2026-09-28-extract-coverage-rules.md](2026-09-28-extract-coverage-rules.md)
- [2026-09-29-harness-flow-briefing.md](2026-09-29-harness-flow-briefing.md)
- [2026-09-29-request-trace-logging.md](2026-09-29-request-trace-logging.md)
- [2026-09-30-autoscaling-plan.md](2026-09-30-autoscaling-plan.md)
- [2026-09-30-aws-orchestrator-harness-callback-e2e.md](2026-09-30-aws-orchestrator-harness-callback-e2e.md)
- [2026-09-30-golden-set-59-aws-harness-benchmark.md](2026-09-30-golden-set-59-aws-harness-benchmark.md)
- [2026-09-30-harness-issue-todo.md](2026-09-30-harness-issue-todo.md)
- [2026-09-30-harness-weekly-briefing.md](2026-09-30-harness-weekly-briefing.md)
- [2026-10-02-agents-aws-batch-test.md](2026-10-02-agents-aws-batch-test.md)
- [2026-10-02-agents-bug-principle.md](2026-10-02-agents-bug-principle.md)
- [2026-10-02-aws-integrated-deploy-1002c.md](2026-10-02-aws-integrated-deploy-1002c.md)
- [2026-10-02-aws-integrated-deploy-1002d.md](2026-10-02-aws-integrated-deploy-1002d.md)
- [2026-10-02-aws-integrated-deploy-1002f.md](2026-10-02-aws-integrated-deploy-1002f.md)
- [2026-10-02-aws-integrated-deploy-1002g.md](2026-10-02-aws-integrated-deploy-1002g.md)
- [2026-10-02-aws-integrated-deploy-1002h.md](2026-10-02-aws-integrated-deploy-1002h.md)
- [2026-10-02-aws-integrated-deploy-1002i.md](2026-10-02-aws-integrated-deploy-1002i.md)
- [2026-10-02-aws-integrated-deploy-1002j.md](2026-10-02-aws-integrated-deploy-1002j.md)
- [2026-10-02-aws-integrated-deploy-r3.md](2026-10-02-aws-integrated-deploy-r3.md)
- [2026-10-02-aws-integrated-feature-test.md](2026-10-02-aws-integrated-feature-test.md)
- [2026-10-02-aws-redeploy-golden59-rerun.md](2026-10-02-aws-redeploy-golden59-rerun.md)
- [2026-10-02-detail-filldown-group-values.md](2026-10-02-detail-filldown-group-values.md)
- [2026-10-02-detail-testset200.md](2026-10-02-detail-testset200.md)
- [2026-10-02-docraft-read-latency-analysis.md](2026-10-02-docraft-read-latency-analysis.md)
- [2026-10-02-extra-detail-validation.md](2026-10-02-extra-detail-validation.md)
- [2026-10-02-extraction-accuracy-paper-experiments.md](2026-10-02-extraction-accuracy-paper-experiments.md)
- [2026-10-02-golden-benefit-col-extract-unify.md](2026-10-02-golden-benefit-col-extract-unify.md)
- [2026-10-02-golden-harness-misextraction-analysis.md](2026-10-02-golden-harness-misextraction-analysis.md)
- [2026-10-02-institution-type-r3-followup.md](2026-10-02-institution-type-r3-followup.md)
- [2026-10-02-rule-based-kv-extract-review.md](2026-10-02-rule-based-kv-extract-review.md)
- [2026-10-02-six-type-testsets.md](2026-10-02-six-type-testsets.md)
- [2026-10-02-table-rowmajor-ab-experiment.md](2026-10-02-table-rowmajor-ab-experiment.md)
- [2026-10-02-table-rowmajor-conditional.md](2026-10-02-table-rowmajor-conditional.md)
- [2026-10-02-table-rowmajor-report.md](2026-10-02-table-rowmajor-report.md)
- [2026-10-03-golden-benefit-printed-only.md](2026-10-03-golden-benefit-printed-only.md)
- [2026-10-03-harness-docraft-architecture-quality-review.md](2026-10-03-harness-docraft-architecture-quality-review.md)
- [2026-10-03-medical-table-comparison-design.md](2026-10-03-medical-table-comparison-design.md)
- [2026-10-03-medical-table-parsing-research.md](2026-10-03-medical-table-parsing-research.md)
- [2026-10-03-model-fixed-table-algorithms.md](2026-10-03-model-fixed-table-algorithms.md)
- [2026-10-03-oct02-weekly-report-summary.md](2026-10-03-oct02-weekly-report-summary.md)
- [2026-10-03-parallel-subagents-preference.md](2026-10-03-parallel-subagents-preference.md)
- [2026-10-03-review-integrity-remediation.md](2026-10-03-review-integrity-remediation.md)
- [2026-10-03-summary-rows-policy-integration.md](2026-10-03-summary-rows-policy-integration.md)
- [2026-10-03-synthetic-dataset-codex-작업지시서.md](2026-10-03-synthetic-dataset-codex-작업지시서.md)
- [2026-10-03-parse-extract-보강-작업지시서.md](2026-10-03-parse-extract-보강-작업지시서.md)

## 첨부와 외부 의존

- [2026-10-03-harness-docraft-review-evidence/architecture-review-quality.json](2026-10-03-harness-docraft-review-evidence/architecture-review-quality.json)
- [2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-frontend-build.log](2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-frontend-build.log)
- [2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-probes.log](2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-probes.log)
- [2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-probes.py](2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-probes.py)
- [2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-tests.log](2026-10-03-harness-docraft-review-evidence/docraft-architecture-review-tests.log)
- [2026-10-03-harness-docraft-review-evidence/harness-architecture-review-probes.log](2026-10-03-harness-docraft-review-evidence/harness-architecture-review-probes.log)
- [2026-10-03-harness-docraft-review-evidence/harness-architecture-review-probes.py](2026-10-03-harness-docraft-review-evidence/harness-architecture-review-probes.py)
- [2026-10-03-harness-docraft-review-evidence/harness-architecture-review-stats.json](2026-10-03-harness-docraft-review-evidence/harness-architecture-review-stats.json)
- [2026-10-03-harness-docraft-review-evidence/harness-architecture-review-tests.log](2026-10-03-harness-docraft-review-evidence/harness-architecture-review-tests.log)
- [2026-10-03-review-integrity-evidence/image-validation.json](2026-10-03-review-integrity-evidence/image-validation.json)
- [2026-10-03-review-integrity-evidence/verify_image.py](2026-10-03-review-integrity-evidence/verify_image.py)
- [artifacts/2026-10-03-synthetic-bills-review/validation.json](artifacts/2026-10-03-synthetic-bills-review/validation.json)

wiki 안의 첨부는 동일한 상대 경로로 복사했다. 다른 저장소 문서·외부 e2e 결과·비공개 평가 자료 링크는 원래 작업 공간의 절대 경로로 바꾸어 대상이 다른 저장소 내부로 잘못 이동하지 않게 했다. 의료 원문, 평가 응답, 대형 데이터셋은 복사하지 않는다. Git 저장소 밖 경로는 같은 작업 공간이 필요한 외부 의존으로 남는다.

원본 단계부터 존재하지 않는 다음 참조는 만들거나 다른 결과로 대체하지 않았다.

- `2026-10-03-medical-table-parsing-research.md`: `2026-10-03-synthetic-korean-bills-sample25-analysis.md`
- `2026-09-27-parse-extract-quality.md`: `/home/pilsu/projects/mirae-assets/harness-v2/.worktrees/dev-integration/docs/harness-sample-output/quality-20260927.json`
- `2026-09-27-parse-extract-quality.md`: `/home/pilsu/projects/mirae-assets/harness-v2/.worktrees/dev-integration/docs/harness-sample-output/quality-20260927-before-header-fix.json`

## 검증

원본 SHA-256과 상대 경로를 manifest에 기록했다. 신규 문서는 원문을 보존하되 문서 링크만 목적지에 맞게 조정했고, 기존 5건은 원래 내용을 보존했다. 첨부 SHA-256 일치, 신규·보충 문서의 index 연결 및 log 기록, 상대 wiki 링크 검사, `git -c core.whitespace=-blank-at-eol diff --check` (Markdown 두 칸 줄바꿈 보존)를 확인한다. 코드 변경과 원격 모델 호출은 없다.

[원본 해시·목록 manifest](artifacts/2026-10-03-root-wiki-sync/manifest.json)
