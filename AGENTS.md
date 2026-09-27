작업 내역을 현재 디렉토리의 wiki에 기록해놓아라. wiki 파일 작성시 날짜 prefix를 붙여라. 내용은 open knowledge format을 준수하여 작성하도록 해라.
병렬로 작업 가능한 부분은 sub-agents를 활용하여 작업 진행하도록 해라.
sub-agents를 활용할 때는 토큰 최적화를 위해 최상위 모델은 오케스트레이터 역할을 코드 탐색 및 구현 등의 작업은 기타 경량 모델을 선택해서 진행해라.

작업 진행시 자동 승인 모드로 진행해라.
단, 다른 세션과의 작업 호환성을 위해 git worktree 및 새로운 브랜치를 생성해서 진행하여라.
README.md가 최신화가 필요하다면 주기적인 최신화를 진행해라.
사용 가능한 skills를 활용하도록 해라.ㄴ
코드는 최대한 간결하게 유지하도록 해라. 비슷한 의미를 내포하는 class, enum, 혹은 function 등의 기능은 없어야 한다.

gpu 환경 더 필요하다면 /home/pilsu/projects/mirae-assets/harness-v2/deploy/aws 여기 정보 참고해서 aws에 배포해서 테스트 진행해라.

최신화는 각 레포의 dev 브랜치에서 진행하도록 한다.

## 브랜치·워크트리

- 워크트리는 `.worktrees/<주제>`에 만들고, 브랜치는 `feat/`·`fix/`·`docs/` 접두사를 붙인다.
- dev에 병합한 뒤에는 해당 워크트리와 브랜치를 정리한다.

## 커밋

- 메시지는 한국어로 `기능:`·`수정:`·`추가:`·`문서:`·`설정:` 접두사를 붙인다.
- 작업 브랜치 커밋 후 main에는 `--no-ff`로 `병합: <내용>을 main에 반영` 커밋을 남긴다.

## wiki

- frontmatter에 `type`, `title`, `description`, `tags`, `status`를 둔다. 더 이상 유효하지 않은 문서는 `status: deprecated`로 표시한다.
- 본문 첫머리에 날짜·브랜치·워크트리를 적는다.
- 새 문서는 `wiki/index.md`에 링크하고, 생성·수정 내역을 `wiki/log.md`에 `Creation`/`Update` 항목으로 남긴다.
