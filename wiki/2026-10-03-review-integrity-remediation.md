---
type: implementation
title: 고객 첫 설치를 위한 Harness·Docraft 리뷰 후속 수정
description: 필수 저장·작업 소유권·인증 기본값·내보내기·부분 결과·빌드 및 평가 재현성 수정과 검증
tags: [harness, docraft, installer, integrity, review]
status: active
---

날짜: 2026-10-03  
브랜치: fix/review-integrity (Harness·Docraft), fix/review-auth (installer), fix/review-evaluation (Harness)  
워크트리: 각 저장소 `.worktrees/review-integrity`, installer `.worktrees/review-auth`, Harness `.worktrees/review-evaluation`  
기준: Harness dev 5ddf433, Docraft dev 120feef, installer dev e9e588f

## 범위와 우선순위

사용자가 직접 확인하고 동의한 7개 항목을 수정한다.
첫 설치의 데이터 무결성과 접근 경계(저장 실패, 작업 상태 경쟁, 인증 기본값)를 우선한다.
CSV/XLSX 수식 삽입·부분 페이지 결과 표시·잠금 파일 빌드·평가 실행 동결을 함께 처리한다.
메시지 끝에 누락된 심각도 하향 항목은 지정되지 않았으므로 임의로 작업 범위에 추가하지 않았다.
callback URL 목적지, 원격 JSON Schema ref, readiness/분산 동시성은 이번 지정 범위 밖이다.

## 근본 원인과 일반화 범위

| 항목 | 근본 원인 / 문제 유형 | 적용 범위 |
| --- | --- | --- |
| 필수 저장 | 분석용 best-effort 실패 정책을 필수 상태/결과에 사용, 분리 쓰기 | API 접수·종료 원자 기록, 저장 실패 전파, 캐시 무효화, 스풀 정리 |
| 상태 경쟁 | 문서 ID만으로 완료/승인 쓰기, 작업 세대·소유권 없음 | parse/extract 재시도·claim·heartbeat·cancel·완료/실패·review/approve |
| 수식 삽입 | 신뢰되지 않은 문자열을 스프레드시트 실행 문맥에 삽입 | 공통 CSV/XLSX 헤더·셀, 단일/프로젝트 내보내기 |
| 부분 추출 | 실패한 페이지 그룹을 제외한 결과에 완전성 정보가 없음 | 페이지/표 범위 정보, 문서 결과·검토 UI·내보내기·완료 및 승인 제한 |
| 빌드 | lock 존재와 실제 설치 경로가 분리됨 | Harness 이미지 uv.lock 사용, 빌드 도구의 잠금 |
| 기본 인증 | 고객 설치값이 개발용 무인증 설정을 그대로 사용 | 우산 차트 api_key 기본, 앱 간 공유 키, 설치/업그레이드/스모크/벤치 |
| 평가 | 가변 정답과 과거 grade 공존, 입력/채점기 버전 누락 | 정답·응답·이미지·채점기·정책 snapshot, SHA256, 별도 run, 실패 run 보존 |

## 평가 재현성 검증

버전 관리 대상: `harness-v2/tools/evaluation_run.py`, `tools/evaluation_dispatch.patch`.
Git 저장소가 아닌 공유 `e2e`에는 기존 grade 명령의 dispatcher와 단일 구현 연결을 적용했다.
회귀 5개 통과. 저장 r9 응답 59건으로 기존 명령의 새 실행 경로를 확인했다.

- 최종 산출물: [manifest](/home/pilsu/projects/mirae-assets/e2e/out/review-1003-evaluation-r9-final/manifest.json),
  [리포트](/home/pilsu/projects/mirae-assets/e2e/out/review-1003-evaluation-r9-final/reports/grades.xlsx),
  [로그](/home/pilsu/projects/mirae-assets/e2e/out/review-1003-evaluation-r9-final/grading.log).
- 식별 해시: `02a5f0b30536296c9506d83ad3750f1d851ee8d2e37401bb1fdd54c14dc2d889`.
- 현 정답/현 채점기 기준 14,186/14,577 = 97.3177%.
- 리뷰 이후 인쇄값 정책 변경이 더 반영되어 리뷰의 99.40%/99.16%와 기준이 다르다.
  **저장 r9 응답 재채점**이며 새 dev 추론 품질이 아니다.
- 외부 추론 호출 0회. 기존 정답·응답·grade·xlsx는 덮어쓰지 않았다.

## 통합과 검증

| 저장소 | 이번 수정의 GitLab 반영/검증 커밋 | 검증 |
| --- | --- | --- |
| Harness | `e311a2f9d24551b66495248a566e258837110fb1` | 전체 1,941 passed, 2 skipped, 8 deselected; 장애/관련 100 passed; 최종 저장/취소 45 passed; 평가 별도 5 passed |
| Docraft | `d73f16dc40d5f5d09531c0bd474ebfde873bde55` | 개별 879 passed, 최신 dev 인쇄값 정책 포함 통합 889 passed; frontend 빌드와 Chromium UI_INTEGRITY_OK |
| installer | `c7c9ffcb2cc5f73f9ad037cb34ad37304c9b064a` | 인증 20 passed; 갱신한 앱 고정 커밋으로 다시 20 passed; strict Helm lint, GPU 프로파일 5종 렌더, shell 문법 |

세 저장소 모두 dev에 `--no-ff` 병합하고 GitLab에 push했다. Installer gitlinks는 위 앱 dev SHA로 고정했다.
다른 세션의 Docraft `6015f0c` 인쇄값 정책과 installer `d4cfe4e` 포인터 변경을 보존하며 통합했다.
충돌은 wiki 기록의 양쪽 항목을 모두 남기고, Docraft 포인터는 `6015f0c`의 후손인 새 SHA로 해결했다.

기존 사용자 미커밋 요구사항 문서와 refs는 보존했다. 독립 워크트리에서 구현·검증하고 병합 후 작업 브랜치/워크트리를 정리했다.
Installer의 기존 apps 디렉토리는 미커밋 파일 변경이 없음을 확인한 후 새 gitlinks와 일치하도록 갱신했다.

실제 Docker image build도 로컬 Docker 접근을 승인받아 성공했다.
빌드 context는 dev에서 pyproject.toml·uv.lock·README·src만 추출해 3.76MB로 제한했다.
전체 이미지가 bit-for-bit 동일하다는 보장은 아니며 베이스 이미지 digest는 아직 소스에 고정하지 않았다.

- 빌드 소스: 검증한 `e311a2f`, 이미지 `mlife-harness:review-integrity-e311a2f`.
- 이미지 ID: `sha256:5caed43e28a438e94627c0f35a1829ea802c73b78cc39b7c576bc7cae261b6de`.
- 네트워크를 끈 컨테이너에서 앱의 site-packages import와 설치된 앱/의존성 **62개 전부 uv.lock 버전 일치** 확인.
- [이미지 검증 결과](2026-10-03-review-integrity-evidence/image-validation.json),
  [검증 스크립트](2026-10-03-review-integrity-evidence/verify_image.py).
- 앱 저장소의 최초 wiki 기록은 Docker 접근 제한 전 검증이다. 위 실제 build/import 확인이 후속 검증이다.

최종 정리 중 다른 세션이 Harness 금액 소수 인쇄값 유지 `36f02ac`와 installer 포인터 `888e781`을 dev에 추가했다.
모두 이번 커밋의 후손이며 이번 수정은 그대로 포함된다. 위 회귀와 이미지의 기준은 표에 적은 고정 커밋이다.
다른 세션이 반영한 이후 추출 규칙의 검증을 이번 저장/상태/인증 검증과 혼동하지 않는다.

## 추가한 회귀 범위

- Harness 21개: 생성/상태/결과/commit 장애, 신규·기존 작업 롤백, 응답 없는 completed,
  취소 경합, 접수 503 세 진입점, 캐시 스냅샷, 저장 재시도 성공/소진 때 OCR 1회,
  워커 시작/완료 및 큐 전달/인라인 처리 실패 시 스풀 보존.
- Docraft 31개: 오래된 parse/extract/validate 성공·실패, 리스 인계·오래된 전달/heartbeat,
  단건/일괄 queued 승인·검토 거부, 취소 초기화, 수식 헤더/값·공백/제어문자와 숫자,
  partial 유지·승인 거부·단건/프로젝트 JSON/CSV/XLSX, 페이지 묶음 실패,
  누락/null/비목록/잘못된 행과 유효 빈 표 구분. 기존 한 페이지 실패에도 coverage 검증을 추가했다.
- Installer 20개: 기본 인증/내부 키 계약, opt-out과 잘못된 모드/타입/빈 키,
  offline preview·실제 lookup의 신규/전환/유지/교체·403 전파, 공용 Secret 변경 재기동.
- 평가 5개: 과거 grade 보존, 파일/산출물 SHA256, 변경 후 별도 run, 기존/실패 run 재사용 거부,
  채점 중 입력 변조와 채점기 누락 탐지.
- UI: 부분 실패 경고·표 표시, queued/partial 승인 차단, 완전 결과 승인 활성화.

## 운영 한계와 AWS 전달 상태

저장 재시도 소진 시 입력은 보존되지만 자동 OCR 재호출은 하지 않는다.
기존 청소 루프가 DB 복구 후 오래된 queued/running을 failed로 종결하며 운영자가 재접수할 수 있다.
과거 Docraft `completeness={}`는 미확인이다. 실패 페이지를 소급 복원하지 않는다.
API/worker는 같은 버전으로 배포해야 하며 부분 단건 JSON 다운로드 계약은 `{result, completeness}`다.
새 기본 인증을 고객 설치에 적용하려면 새 우산 차트를 담은 installer 번들이 필요하다.

현재 앱 서버의 활성/최근 세션 50개를 두 차례 확인했으나 `mirae-assets-6c` 배포 담당을 찾지 못했다.
AWS 배포/실물 모델 호출은 0회이며 통합 배포 요청을 담당에게 전달하지 못했다.
차후 담당이 취합할 확인 항목은 위 커밋·push 완료 상태와 접수/결과 조회, 무키/오키 거부,
부분 결과의 승인 차단 및 늦은 작업 덮어쓰기 방어다. 이번 변경은 추출 규칙 변경이 아니므로
새 59건 모델 호출을 직접 실행하지 않았다.

## 관련 근거

- [원래 아키텍처·품질 리뷰](2026-10-03-harness-docraft-architecture-quality-review.md).
- [평가 스냅샷 구현](/home/pilsu/projects/mirae-assets/harness-v2/wiki/2026-10-03-evaluation-snapshots.md).
