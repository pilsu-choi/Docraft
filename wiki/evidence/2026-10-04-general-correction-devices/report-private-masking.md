# private-masking 보고

브랜치 feat/private-masking (워크트리 harness-v2/.worktrees/private-masking), 기반 dev 39e6698. 커밋은 `git log -1` 참조.

## 원인·유형
주민번호 같은 출력 금지 값이 선언(private 형식)은 있으나 출력 단계에서 가리는 장치가 없고 탐지(PRIV.1)만 있었음. 유형: "선언된 출력 금지 값이 고객 출력의 어느 위치에서든 원문으로 남는 문제".

## 설계
- config.py `mask_private_output`(env MASK_PRIVATE_OUTPUT, 기본 False). runner -> assemble(mask_private=...).
- schema.yaml 항목에 `mask_keep: 7` (앞에서 7개 숫자만 남기고 나머지 숫자는 *). FieldDecl.mask_keep, `masking_rules()`(선언 전체에서 mask_keep 있는 칸), `mask_text()`(private 형식에 이미 맞는 값은 그대로) — rules/schema.py. 필드명·형식 코드 하드코딩 없음.
- emit/mask.py `mask_private_output`: assemble 마지막 한 곳. 문서마다 가림 칸(그룹·표 셀 포함, key 기준)의 value·masked_value·predicted_*·harness.final_value·ao_value·candidates 원문과 숫자만 남긴 표기를 모아, 문서 JSON의 모든 문자열(증거 detail 포함, 다른 칸 본문 포함)에서 가린 값으로 치환. 그 칸의 masked_value·predicted_masked_value는 가린 값으로 채움. 문서 redact_applied=true(가린 문서만). UI response(result)도 처리.
- emit/schema.py assert_input_preserved(mask_private=True): 원본에서 같은 치환표를 만들어, 치환으로 설명되는 값 차이와 가림 칸 masked_* 채움, redact_applied 만 허용. 다른 칸 동일성은 그대로(테스트로 확인). MASK_SOURCE 상수 공유.
- README 설정표에 MASK_PRIVATE_OUTPUT 추가.

## 테스트 (tests/unit/test_private_masking.py, 15건 통과)
선언 로드, mask_text 8형(13자리·하이픈 없음·이미 가림·7자리·6자리·빈값·일부 인쇄·숫자 없음), 꺼짐=동일·Settings 기본 False, 켜짐 전 위치 가림+다른 칸 유지+입력 불변+validate_output+계약 검사 통과, 이미 가림/빈값/해당없음은 켜도 출력 동일, ao_value·candidates, UI·그룹·표 셀, 계약 검사가 다른 칸 변경·엉뚱한 값은 계속 위반으로 잡음. `uv run pytest tests/unit -q`: 17 failed(기존과 동일) / 2061 passed.

## 로컬 측정
- r9 59건 재생(꺼짐): out/replay-r9-private-masking. 같은 코드 기반 dev 39e6698 재생(out/replay-r9-dev39)과 비교해 processed_at·audit_ref 제외 59건 중 58건 완전 동일, 1건은 parser.elapsed_ms(0 vs 1)만 다름. 채점 out/replay-r9-private-masking-grade: 전체 97.4%(14569칸) 기준선과 동일, 개선/악화/무효 239/1/22 동일. (기준선 dev 15b172a 대비 JSON 차이는 이후 dev 커밋의 grounding·규칙 1건 추가 때문이며 본 변경 아님.)
- 켜짐 확인: 소견서 표본 4건의 환자 주민번호를 900101-1234568로 바꾼 입력(scratchpad/mk-in), parse-cache 없이 AO env unset. 꺼짐 출력은 13자리 16회 포함, 켜짐 출력은 13자리·숫자만 표기 0회, redact_applied true, 값은 900101-1******.
- 참고: exp/e2e_call_test/evaluation_run.py 심볼릭 링크가 ../harness-v2/tools/ 로 깨져 있어(exp 아래 harness-v2 없음) 채점 시 PYTHONPATH=<워크트리>/tools 로 우회.

## 확인 사항
1. DB 기록(이번에는 미변경): PersistenceRecorder.save_result 의 output(Postgres job payload)은 가려진 출력이지만, ClickHouse fact rows(_primary_rows의 node.value, 판정 final_value, 재판독 ev.value)와 Postgres 증거·trace는 result.transaction/outcome 의 원래 값을 쓴다. 가림을 켜도 DB 쪽에는 원문(및 규칙 detail)이 남을 수 있음. 필요하면 recorder 입구에서 같은 mask_text를 적용하는 후속 작업.
2. SCHEMA_PRIVATE(탐지) 설계: 탐지는 내부 원래 값 기준이므로 켜짐에서도 warn 유지가 맞다고 본다(판정·감사는 원본 기준, 가림은 출력 표현). 단 출력 기준으로는 이미 가려졌으므로 고객에게 보이는 증거 문구가 "가려지지 않고 나옴"이면 혼란이다. 안은 (a) 켜짐이면 detail 문구를 "출력에서 가림 적용"으로 치환하거나 (b) 증거에 masked=true 표식. 이번엔 미변경.
3. 누출 가능 경로(범위 밖): 규칙 detail 이 원문에서 파생한 값(예: R-CERT-BIRTH "계산값 19900101"은 주민번호 앞 6자리에서 계산)은 원문 문자열이 아니라 치환되지 않는다. 앞 6자리는 허용 형식이라 노출 수준은 같음.
4. 부작용: 가림 칸이 아닌 다른 칸 본문에 같은 원문이 있으면 함께 치환(의도). 선언 키 이름이 문서 종류 간 같으면 모든 종류에 적용(masking_rules 는 모든 종류 합집합). 켜짐에서 value 형식이 달라지므로 하류 적재에서 값 검증이 있으면 확인 필요. ruff는 변경 파일 기준 기존 F841 1건(rules/schema.py unknown)만 남음(기존).

## 남은 일
DB 기록 가림 여부 결정, SCHEMA_PRIVATE 출력 문구 처리, 가림 켜짐 채점 영향(주민번호 칸이 채점 대상이면 정답 비교 방식 확인).
