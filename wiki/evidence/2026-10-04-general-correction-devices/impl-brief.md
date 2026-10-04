# 일반 보정 장치 구현 공통 지침 (2026-10-04)

먼저 읽을 것
- /home/pilsu/projects/mirae-assets/AGENTS.md 와 대상 저장소 AGENTS.md (반드시 준수)
- /home/pilsu/projects/mirae-assets/wiki/2026-10-04-issue-taxonomy-correction-coverage.md (일반 보정 방법 M1~M12, 현재 구현, 우선순위, 원칙)
- /home/pilsu/projects/mirae-assets/wiki/2026-10-03-parse-extract-issue-taxonomy.md (분류 ID)
- 장치 목록: /home/pilsu/projects/mirae-assets/wiki/evidence/2026-10-04-issue-taxonomy-v4/inv-harness.md, inv-docraft.md

브랜치·워크트리
- 대상 저장소의 로컬 `dev`에서 `git worktree add -b <브랜치> .worktrees/<주제> dev`. 메인 워크트리는 건드리지 않는다(다른 세션이 쓰는 중).
- 커밋 메시지: 한국어, `기능:`/`수정:`/`추가:`/`문서:`/`설정:` 접두사, 끝에 빈 줄 후 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- dev 병합·push·AWS 호출 금지. 오케스트레이터가 검토 후 병합한다.

설계 원칙 (어기면 반려)
1. 일반 장치: 문서 유형명·서식 코드·필드명·열 이름·라벨 문자열을 코드에 넣지 않는다. 서식 지식이 필요하면 선언 데이터(yaml)에서 읽는다. 선언이 없어도 기본 동작(값 모양 추정 등)이 되게 한다.
2. 탐지 우선: 새 장치는 값을 바꾸지 않고 증거(evidence)만 남긴다. 판정 상태(검토 필요 등)에 반영하는 것은 설정 플래그로 두고 기본 꺼짐. 값 변경이 꼭 필요하면 서로 독립된 근거 둘 이상일 때만, 그리고 보고서에 명시.
3. 기존 구조 재사용: 기존 규칙 엔진·증거 형식·판정 경로·trace를 따른다. 비슷한 의미의 새 class/enum/function을 만들지 않는다(AGENTS.md). 같은 기능이 이미 서식 한정으로 있으면 일반 장치로 흡수할 수 있는지 검토하고, 흡수했으면 기존 테스트가 통과해야 한다.
4. 분류 ID: 증거에 탐지 대상 노드 ID(예: `E.OVR.GEN.1`)를 담는다.
5. 코드는 간결하게.

테스트
- 단위 테스트: 보고된 사례가 아니라 유형의 변형(경계값·다른 형식·다른 진입 경로·장치가 건드리면 안 되는 정상 사례)을 포함한다.
- harness-v2: `uv run pytest tests/unit -q`. dev에도 기존 실패 17건(샘플 데이터 JSON 중복, 수술확인서·입퇴원확인서)이 있다. 새 실패가 없어야 한다.

로컬 측정 (harness-v2, 외부 호출 0건)
- 폴더: /home/pilsu/projects/mirae-assets/exp/e2e_call_test
- 재생: `uv run --project <내 워크트리 절대경로> python replay_harness.py --sample out/review-1003-evaluation-r9-final/inputs --parse-cache out/ao-parse-r9 --out out/replay-r9-<주제>` (캐시만 사용. 캐시가 없는 건이 생기면 AO 호출이 일어나므로 그런 건은 건너뛰도록 확인하고, 절대 외부 호출하지 말 것. 명령이 다르면 out/replay-r9-dev.log 와 replay_harness.py 를 보고 맞춰라)
- 채점: `../../Docraft/.venv/bin/python grade_samples.py --sample out/replay-r9-<주제> --run-dir out/replay-r9-<주제>-grade` → 셀별 판정은 `*-grade/inputs/**/*.grade.json`.
- 기준선: dev `15b172a`의 결과 out/replay-r9-dev, 채점 out/replay-r9-dev-grade (97.405%, 14191/14569). 내 브랜치 결과와 비교한다.
- 탐지 장치는 정확도가 바뀌면 안 된다(바뀌면 원인 보고). 대신 정탐·오탐을 잰다: 장치가 의심 표시한 칸 중 채점상 오답인 칸(정탐), 정답인 칸(오탐), 오답인데 표시 못 한 칸(미탐). 측정 스크립트는 scratchpad에 두고 저장소에 넣지 않는다.

보고 (필수)
- /tmp/claude-1000/-home-pilsu-projects-mirae-assets/b955a553-930f-4857-9836-00c1b1dbc493/scratchpad/report-<주제>.md 에: 브랜치·커밋, 근본 원인과 문제 유형, 설계(어떤 선언을 읽는지, 일반성 근거), 변경 파일, 흡수한 기존 장치, 테스트 목록과 결과, 로컬 측정(정확도·정탐·오탐·미탐, 노드별), 부작용 위험, 남은 일. 최종 응답은 15줄 이내 요약.
