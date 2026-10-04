---
okf_version: "0.2"
type: change
title: "서식 무관 일반 보정 장치 1차 구현"
description: "이슈 유형별 보정 장치 대응표의 우선순위에 따라 하네스에 원문 대조(M1)·표 구조 일관성(M3·M7)·스키마 선언 기반 형식·제약·공개 규칙 검사(M5·M8)·변경 감사(M6)를, Docraft에 입력 무결성 계측과 쪽·표·행 반복·순서 탐지(M9·M7)를 넣었다. 모두 값을 바꾸지 않는 탐지이고 판정 반영 설정은 기본 꺼짐이다. 정답지 59건 로컬 재생에서 정확도는 그대로이며 장치별 정탐·오탐을 기록한다."
tags: [harness, docraft, taxonomy, correction, generalization, detection]
status: active
---

날짜: 2026-10-04 (Asia/Seoul)

브랜치: harness-v2 `feat/change-audit`(`1d55ec0`)·`feat/source-grounding`(`50b8688`)·`feat/table-consistency`(`0a4bf85`)·`feat/schema-declarations`(`01c37fe`) → dev `f909459`. Docraft `feat/input-integrity`(`d0babbc`) → dev `fba0d91`. 모두 dev `3d79d0e`·`f3856b8` 기준.

워크트리: 각 저장소 `.worktrees/<주제>` (병합 후 정리)

기준 원본: 상위 `mirae-assets/wiki` (이 문서는 Docraft wiki 동기화본)

## 목적

[이슈 유형별 보정 장치 대응표](2026-10-04-issue-taxonomy-correction-coverage.md)는 하네스·Docraft의 판단 엔진은 일반이지만 판단 기준이 서식별 코드 상수라, 새 서식·새 사례에서 막는 것이 거의 없다고 정리했다. 이번 작업은 그 우선순위 1~7 중 장치가 없던 칸에 서식과 무관한 장치를 넣는 1차 구현이다.

공통 원칙(작업 지시: [evidence/2026-10-04-general-correction-devices/impl-brief.md](evidence/2026-10-04-general-correction-devices/impl-brief.md)):
- 문서 유형·서식 코드·필드명·열 이름을 코드에 넣지 않는다. 서식 지식이 필요하면 선언 데이터에서 읽고, 선언이 없어도 값 모양 추정으로 동작한다.
- 새 장치는 값을 바꾸지 않고 증거만 남긴다. 판정(검토 필요 등) 반영은 설정 플래그이며 기본 꺼짐이다.
- 기존 규칙 엔진·증거 형식·trace를 재사용한다.

## 구현 요약

| 방법 | 저장소 | 장치 | 탐지 노드 | 판정 반영 설정(기본 꺼짐) |
|---|---|---|---|---|
| M1 원문 대조 | harness-v2 | `normalizer/grounding.py`: 출력의 비어 있지 않은 값이 AO parse 글자에 인쇄돼 있는지 값 모양(숫자·날짜·글자)으로 비교. 결과는 원문 있음 / 원문 없음 / 같은 행 다른 칸에서만 발견(복제 의심) / 판정 불가. 산출물 `harness.parser.documents[].grounding` | `E.OVR.GEN.1`·`.2`, `E.OVR.DUP.2`, `E.WRG.HOLD.1` | 없음(기록만) |
| M3·M7 표 구조 일관성 | harness-v2 | `normalizer/consistency.py`: 열마다 값 모양 분포를 추정해 어긋난 칸, 행 내 k칸 밀림, 열 맞바뀜, 전치, 행 종류 이상, 행 중복(parse 인쇄 횟수와 대조), 쪽 경계 반복을 `RuleEvidence`(STRUCT, warn)로 남김. StructAnomaly 행 칸 수 이상 2종도 같은 증거로 올림 | `E.WRG.ASSIGN.2`, `E.STR.ARRAY.1`, `E.STR.GROUP.1`, `E.OVR.DUP.1`, `P.OVR.DUP.1` | `TABLE_CONSISTENCY_BLOCKS_CONFIRMATION` |
| M5·M8 스키마 선언 검사 | harness-v2 | `rulesets/shared/schema.yaml`(칸 종류·코드 형식·체크섬·허용 목록·날짜 선후·합계·가림 형식, 필수·동의어는 형식만) + 로더 `rules/schema.py::load_declarations` + 공통 규칙 `rulesets/schema_checks.yaml`. 약제비영수증(0730) 합계 관계 선언(정답지 38건 중 36건 일치, 2건은 원문 인쇄 자체 불일치) | `E.CON.RANGE.1`~`.3`, `E.CON.SCHEMA.2`, `E.CON.PRIV.1`·`.2` | `SCHEMA_CHECKS_JUDGE` |
| M6 변경 감사 | harness-v2 | 값을 바꾸는 판정 전부를 `arbitration.change_records()` 한 곳에서 `DocumentTrace.changes`로 기록(단계·분기·이전 값·새 값·근거 종류: 원문 인쇄·산식·재판독·참조 마스터·추론). 근거가 산식·추론 하나뿐인 변경을 막는 가드 | `AUX.POST.*`, `E.OVR.GEN.2` | `CHANGE_AUDIT_GUARD` |
| M9·M7 입력 무결성·반복 | Docraft | `engine.input_report`(쪽 수, EXIF·파서 회전, 쪽별 축소 배율, 디코딩 실패, 이미지 미전송 쪽)와 `engine.unit_flags`(쪽 순서 이상, 같은 쪽 두 번, 쪽 경계 반복 행, 표 두 번 읽힘, 행 쪽 역순, 표 쪽 건너뜀)를 `apply_integrity`로 기존 `issue_codes`에 붙임. 큐는 `documents.completeness["integrity"]`, `/api/read`는 `diagnostics.integrity`. 다중 프레임 TIFF는 422 거부 대신 프레임을 쪽으로 펼쳐 기존 PDF 경로로 처리(`/api/verify`는 422 유지) | `AUX.INPUT`, `P.MIS.AREA.1`, `P.WRG.ORDER.1`, `P.OVR.DUP.1`, `E.OVR.DUP.1`, `P.STR.LINK.1` | `INTEGRITY_REVIEW` |

## 검증

- harness-v2 dev `f909459`: `uv run pytest tests/unit -q` → 2046 통과, 17 실패. 실패 17건은 작업 전 dev와 같은 기존 실패(샘플 JSON 중복, 수술확인서·입퇴원확인서)다. 새 테스트는 원문 대조 27건, 표 구조 32건, 스키마 검사 60건, 변경 감사 12건이다.
- Docraft dev `fba0d91` 기준 브랜치: 전체 900건 통과(임시 postgres:17 컨테이너, 외부 호출 0). 새 테스트 7건. 동작이 바뀐 기존 테스트 3건(다중 TIFF 허용, 프레임별 한 쪽, completeness에 integrity 포함)은 기대값을 새 동작에 맞췄다.
- 정답지 59건 로컬 재생(r9 AO 결과 + parse 캐시, AO·Docraft·마스터 호출 0): 네 장치를 합친 하네스 dev의 채점 결과가 기준선(dev `15b172a`, 97.405%, 14191/14569)과 같다. 59개 채점 파일 중 차이는 한 칸에 `STRUCT_COLUMN_OUTLIER:warn` 표시가 붙은 것뿐이다. 결과 `exp/e2e_call_test/out/replay-r9-merged(-grade)`.

## 장치별 측정 (r9 59건, 셀 단위)

정탐은 장치가 표시한 칸 중 채점상 오답, 오탐은 정답인 칸이다.

| 장치 | 정탐 | 오탐 | 해석 |
|---|---:|---:|---|
| 원문 대조: 원문 없음(`GEN.1`) | 4 | 18 | 오탐 대부분은 parse가 OCR로 빠뜨린 값 |
| 원문 대조: 계산값(`GEN.2`) | 5 | 12 | 오탐은 정답지가 계산 합계를 허용한 칸 — 계산값 허용 정책 결정 필요 |
| 원문 대조: 추측 확정(`HOLD.1`) | 8 | 9 | AO 신뢰도 기준 |
| 원문 대조: 복제 의심(`DUP.2`) | 73 | 87 | 복제 칸과 원본 칸을 쌍으로 표시해서 생긴 오탐이 71. 쌍 단위로는 대부분 정탐. 정의상 같은 값이 16 |
| 표 구조 일관성 | 1 | 0 | r9 오답은 종료일자 정책·빈칸·숫자끼리 오류라 모양 이상이 거의 없음. 정답지 표 칸 10,492개 중 오탐 2칸(0.02%). 합성 변형 재현율: 칸 맞바뀜 98%, 행 1~2칸 밀림 99~100%, 날짜↔금액 열 맞바뀜 96%, 행 중복 100% |
| 스키마 검사 | 0 | 0 | r9에는 형식 위반이 없음. 표본 205건(AO 원값): 합계 정탐 3·오탐 2, 번호 정탐 3·오탐 14(합성 문서 주민번호 체크섬), 주민번호 노출 65건·가림 형식 위반 3건 |
| 변경 감사 가드(켰을 때) | 개선 1 | 악화 78 | 정확도 97.405 → 96.877%(-0.53%p). 악화는 전부 분기 10-n의 합계로 확인된 다칸 교정(끝수 조정 14, 요약 행 칸 밀림 28, 빈 투여량 채움 10, 공단부담금 열 이동 13 등) |

원문 대조의 오탐은 이 59건으로 조정하면서 줄였다(원문 없음 638→18, 복제 의심 567→87). 같은 데이터로 조정하고 잰 값이라 실제 오탐률은 더 높을 수 있다. 판정 반영을 켜기 전에 205건·7종 테스트셋처럼 조정에 쓰지 않은 데이터로 다시 잰다.

## 측정으로 바뀐 판단

- **값 변경에 독립 근거 둘을 요구하는 원칙은 이 시스템에서 너무 엄격했다.** 합계식으로 확인한 다칸 교정은 이 데이터에서 거의 항상 맞았고, 가드를 켜면 1칸 개선에 78칸 악화였다. 가드는 기본 꺼짐으로 두고, 대응표의 원칙을 "검증식 통과 하나만으로 원문과 달라지는 값을 확정하지 않는다. 다만 여러 칸이 함께 맞아야 하는 합계 확인은 독립 근거로 본다"로 고친다. 마스터·Docraft 재판독이 있는 경로(분기 7·7-i·10-a~g)는 로컬 재생에서 발화하지 않아 AWS에서 켬/끔을 비교해야 한다.
- **표 구조 장치는 정답지 59건에서 일할 일이 거의 없다.** 59건의 남은 오답은 정책(종료일자)·빈칸·숫자끼리 오류다. 이 장치의 가치는 새 서식·새 촬영 조건에 대한 기본 방어선이며, 그 효과는 합성 변형 재현율로만 확인했다.

## 부작용과 주의

- 표 구조 장치의 warn 증거가 붙은 칸은 등급이 "검증됨"으로 바뀔 수 있고, `rule_results_summary`의 warn·total이 늘어난다. 스키마 검사는 날짜 선후 pass 증거를 문서당 1~3건 늘린다.
- `rulesets/schema_checks.yaml`의 `rule_set_version`은 기존 차트 일치 테스트 때문에 `2026.09.22`로 맞췄다. 다음 배포에서 `RULE_SET_VERSION`을 올릴 때 이 파일도 함께 올린다([AWS .env.aws 규칙셋 버전 고정](/home/pilsu/.claude/projects/-home-pilsu-projects-mirae-assets/memory/aws-env-ruleset-version.md) 참고).
- 원문 대조는 parse 글자가 쪽 구분 없는 문서 단위 목록이라 문서 전체와 대조한다. 숫자가 다른 숫자의 부분 문자열로 우연히 맞으면(`12290` ⊂ `112290`) 놓친다.
- Docraft `image_not_sent`는 호출 기록이 아니라 청크·표 묶음 규칙으로 추정한 값이다. 스캔 PDF는 쪽 크기(포인트) 기준 배율이라 고해상도 스캔을 2000px로 줄인 손실은 `downscaled`로 잡히지 않는다. 다중 프레임에서 전체 쪽 회전 재시도(`reprocess._rotated`)는 아직 첫 프레임만 쓴다.
- 주민번호 노출(`E.CON.PRIV.1`)은 표본 205건에서 65건 탐지됐다. 출력 가림 여부는 고객 정책 결정이 필요하다.

## 남은 일

1. AWS 확인: dev push 후 배포 담당 세션에 요청. 마스터·재판독 경로에서 변경 감사 기록과 가드 켬/끔 비교, Docraft 다중 프레임 TIFF 실제 처리.
2. 조정에 쓰지 않은 데이터(205건, 7종 테스트셋)로 장치별 정탐·오탐 재측정 후 판정 반영 설정을 켤지 결정.
3. 원문 대조의 복제 쌍에서 복사된 칸 하나 고르기(parse 열 위치), 쪽·근거 좌표 단위 대조.
4. 표 구조 장치를 기존 영수증·세부내역서 전용 열 보정(N-COLSHIFT 등)의 후보 선정에 쓰는 3단계 이전([보고서](evidence/2026-10-04-general-correction-devices/report-table-consistency.md)).
5. 스키마 선언의 필수 여부·동의어를 채우고 Docraft가 같은 선언을 읽게 하기(공통 사본 동기화 방식 결정 필요).
6. 정책 결정: 계산값 허용 범위 — 2026-10-05 세부내역서 합계 급여 총액은 허용(A)으로 결정·반영(아래 추가 절). 주민번호 출력 가림은 설정으로 해결(아래 추가 절, 기본 꺼짐).

## 추가: 출력 가림 설정 (2026-10-04)

사용자 결정으로 가림 대상 값(현재 선언: 환자 주민번호)을 고객 출력에서 가리는 기능을 설정으로 켜고 끌 수 있게 했다. **기본은 가리지 않음**이다. harness-v2 `feat/private-masking`(`1034386`) → dev `af711ce`.

| 항목 | 내용 |
|---|---|
| 설정 | `MASK_PRIVATE_OUTPUT`(기본 `false`). README 설정표에 추가 |
| 가림 형식 | 선언 `rulesets/shared/schema.yaml`의 `mask_keep: 7` — 앞 숫자 7개(생년월일 6자리 + 뒷자리 첫 숫자)만 남기고 나머지 숫자는 `*` (예: `900101-1******`). 이미 허용 형식으로 가려진 값은 건드리지 않음. 필드명·형식은 코드에 없음 |
| 처리 위치 | 출력 조립 마지막 한 곳(`emit/mask.py`). 가림 칸의 `value`·`masked_value`·`predicted_*`와 하네스 블록의 `final_value`·`ao_value`·후보를 모아 문서 JSON의 모든 문자열(증거 설명 포함)에서 가린 값으로 바꾸고, 가린 문서는 `redact_applied: true` |
| 내부 처리 | 판정·규칙·재판독은 원래 값으로 한다. 탐지 규칙 `SCHEMA_PRIVATE`는 켜져 있어도 원래 값 기준 warn이 남는다(고객이 보는 문구와 어긋날 수 있어 문구 조정은 후속) |
| 출력 계약 검사 | 켜졌을 때만 가림 치환으로 설명되는 차이와 `masked_*`·`redact_applied` 변경을 허용하고, 다른 칸의 변경은 계속 위반으로 본다 |
| 원문이 남는 곳 | Postgres 작업 결과(`output`)는 가려진다. ClickHouse 사실 행과 Postgres 증거·trace는 원래 값을 쓴다(이번에 바꾸지 않음). 규칙 설명의 파생값(예: 생년월일 계산값 `19900101`)은 앞 6자리 수준이라 그대로 남는다 |

검증: 새 테스트 15건, `tests/unit` 2061 통과·17 실패(기존과 동일). 정답지 59건 재생(꺼짐)은 기준선과 같다(97.4%). 켜짐 확인은 소견서 표본 4건의 주민번호를 가짜 13자리로 바꿔 돌렸고, 꺼짐 출력에는 13자리가 16회, 켜짐 출력에는 0회였다.

## 추가: 인쇄되지 않은 합계의 계산값 허용 (2026-10-05)

사용자 결정(A): 세부내역서 `합계` 그룹의 `급여_급여총액`처럼 서식에 칸이 없어 인쇄되지 않은 합계는 **계산해서 채워도 된다**. 합계 줄에 본인부담·공단부담·전액본인부담은 인쇄되고 급여 총액 칸만 없는 서식에서, AO가 세 금액을 더해 채운 값을 그대로 낸다. 하네스 출력과 정답지는 원래 이 기준이었고, Docraft와 원문 대조 장치를 맞췄다. 처음에 이 칸을 진료비영수증 칸으로 잘못 안내했다가 바로잡고 다시 확인받았다.

| 저장소 | 변경 | 커밋 |
|---|---|---|
| Docraft | 인쇄되지 않은 합계(`rulesets/rules.yaml`의 `unprinted_totals`, 옛 `unprinted_null`)를 무조건 비우던 것을, 계산으로 설명되면(합계식 `field_sums`에 맞거나 대응 항목 열 합과 같음) 두도록 바꿨다. 다른 칸을 베낀 값과 계산으로 설명되지 않는 값은 지금처럼 비운다. 빈 칸을 새로 계산해 채우지는 않는다 | `fix/unprinted-total-computed` 81693c8 → dev 45e0756 |
| harness-v2 | 스키마 선언에 `computed: allowed`를 추가하고 `세부내역서.급여_급여총액`에 선언. 원문 대조는 이 칸의 계산값을 의심(`E.OVR.GEN.2`) 대신 `computed`로 기록한다. 원문에 없고 계산으로도 설명되지 않는 값·복제는 그대로 표시 | `feat/computed-allowed` 6a89f17 → dev e294618 |

검증: Docraft 908 통과(새 테스트 7변형 + 인쇄값 유지), harness `tests/unit` 2066 통과·17 실패(기존과 동일). 59건 재생 정확도·칸 값 불변. 원문 대조 계산값 표시는 정탐 5·오탐 12 → 정탐 3·오탐 1(정답이 0인데 계산값을 낸 2건은 더 이상 표시되지 않음 — 허용 칸의 틀린 계산은 기존 합계식 규칙 `detail_0710.yaml`이 본다). Docraft 변경의 정답지 대비 영향은 저장된 Docraft 결과가 없어 재지 못했다.

범위 밖(이번 결정과 별개로 유지): 세부내역서 표 열은 10/03 고객사 기준(인쇄된 값만), `합계` 줄 자체가 그 쪽에 인쇄되지 않은 경우 하네스가 합계 그룹을 0으로 두는 규칙(`_unprinted_totals`, 정답지 관례 0).

## 근거 파일

[evidence/2026-10-04-general-correction-devices/](evidence/2026-10-04-general-correction-devices/): 작업 지시 `impl-brief.md`, 장치별 보고서 `report-source-grounding.md`·`report-table-consistency.md`·`report-schema-declarations.md`·`report-change-audit.md`·`report-input-integrity.md`.

AWS 배포·외부 호출은 하지 않았다.
