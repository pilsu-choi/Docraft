작업 내역을 현재 디렉토리의 wiki에 기록해놓아라. wiki 파일 작성시 날짜 prefix를 붙여라. 내용은 open knowledge format을 준수하여 작성하도록 해라.
병렬로 작업 가능한 부분은 sub-agents를 활용하여 작업 진행하도록 해라.
sub-agents를 활용할 때는 작업의 경중 유무를 판단하여 동적으로 모델을 선택해서 진행해라.
단, 다른 세션과의 작업 호환성을 위해 git worktree 및 새로운 브랜치를 생성해서 진행하여라.
README.md가 최신화가 필요하다면 주기적인 최신화를 진행해라.
사용 가능한 skills를 활용하도록 해라.
코드는 최대한 간결하게 유지하도록 해라. 비슷한 의미를 내포하는 class, enum, 혹은 function 등의 기능은 없어야 한다.

gpu 환경 더 필요하다면 /home/pilsu/projects/mirae-assets/harness-v2/deploy/aws 여기 정보 참고해서 aws에 배포해서 테스트 진행해라.

## 브랜치·워크트리

- 워크트리는 `.worktrees/<주제>`에 만들고, 브랜치는 `feat/`·`fix/`·`docs/` 접두사를 붙인다.
- main에 병합한 뒤에는 해당 워크트리와 브랜치를 정리한다.

## 커밋

- 메시지는 한국어로 `기능:`·`수정:`·`추가:`·`문서:`·`설정:` 접두사를 붙인다.
- 작업 브랜치 커밋 후 main에는 `--no-ff`로 `병합: <내용>을 main에 반영` 커밋을 남긴다.

## wiki

- frontmatter에 `type`, `title`, `description`, `tags`, `status`를 둔다. 더 이상 유효하지 않은 문서는 `status: deprecated`로 표시한다.
- 본문 첫머리에 날짜·브랜치·워크트리를 적는다.
- 새 문서는 `wiki/index.md`에 링크하고, 생성·수정 내역을 `wiki/log.md`에 `Creation`/`Update` 항목으로 남긴다.
