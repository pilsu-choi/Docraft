---
okf_version: "0.2"
type: bugfix
title: CI 고정 앱 공통 영수증 규칙 동기화
description: 종료일 필수 키 정책의 앱 사본 불일치로 실패한 번들 빌드 원인과 수정
tags: [ci, receipt, rulesets, submodule]
status: active
---

날짜: 2026-10-03
브랜치: Docraft `fix/receipt-policy-sync`, installer `fix/pinned-build` → 각 `dev`
워크트리: 각 저장소 `.worktrees/receipt-policy-sync`, `.worktrees/pinned-build`

## 근본 원인과 문제 유형

GitLab 파이프라인1605/작업6087에서 소스와 submodule 다운로드는 성공했다.
빌드 시작 시 공통 `receipt_items.yaml`의 바이트 불일치 검증에 걸려 업로드 전에 실패했다.
harness6b7b01c는 종료일을 인쇄값만 유지하는 정책에 맞춰 `required_keys`에서 종료일을 제외했지만
Docraft8781af3의 사본은 종료일을 필수로 두었다. 문제 유형은 "공유 규칙 변경의 앱 사본 동기화 누락"이다.

## 수정 범위

Docraft 자체 GitLab dev59d6e52 기준 별도 워크트리에서 공통 표 사본을 맞춘다.
installer에서는 앱 파일을 수정하지 않고, 앱 저장소에 먼저 push된 수정 커밋으로 Docraft gitlink만 갱신한다.
harness 고정6b7b01c의 인쇄값 정책을 유지하며, guard를 삭제하거나 이전 앱으로 되돌리지 않는다.
표의 alias·표준 항목·swap 등 다른 공유 섹션도 전체 파일 비교로 함께 검증한다.

## 검증과 반영 상태

- GitLab 원격 dev 확인: harness28fa77d, Docraft59d6e52.
- Docraft 수정: 종료일 required_keys 제외와 설명 동기화, tests/test_rules.py에 공유 정책 회귀 추가.
- tests/test_rules.py·test_rules_receipt_accuracy.py·test_typed_evidence.py: **404 passed**.
- 변형: 시작일 필수 유지, 종료일 제외, 외래/입원 미인쇄 종료일, 인쇄 기간·세부내역서 날짜 보존.
- 전체 표 Git blob 9cc3206891f83eb894d637207289b1e6fd4ea7fe, harness6b7b01c와 일치.
- 새 고정 커밋은 앱 dev 병합·GitLab push 완료 후 기록한다.
- installer는 30분 일괄 push 정책에 따라 검증 완료분을 다음 배치에 반영한다.
- 최초 실패 빌드는 패키지 업로드 단계에 도달하지 않아 결과물이 없다.

## 빌드 결과 위치

Generic package는 installer 프로젝트의 `installer-bundle`에 저장한다.
그룹 https://git.sparklingsoda.ai:8443/groups/clients/miraeasset-life/agenticocr/-/packages 에서 함께 조회할 수 있다.
성공한 dev 빌드는 `X.Y.Z-dev-<pipeline ID>` 아래 tar·sha256·INSTALL.md·manifest.json을 둔다.
