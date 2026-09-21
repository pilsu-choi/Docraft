# PRD 구현 작업

- 작업 브랜치: `feat/prd-implementation`
- 작업 디렉토리: `../.worktrees/prd-implementation`
- 원본 요구사항: `../PRD.md`
- 범위: PRD 8장의 P0, 업로드 → 파싱 → 스키마 → 추출 → 근거 검수 → 내보내기/API.
- 역할: 루트 에이전트는 오케스트레이션, sol은 백엔드, terra는 프론트엔드, luna는 테스트 및 문서.
- 초기 상태: 코드가 없는 폴더였으므로 Git 저장소를 초기화하고 요구사항 기준 커밋 후 별도 worktree를 생성했다.
- 상세 구현과 검증 결과는 작업 디렉토리의 `wiki/`에 기록한다.
- P0 구현 완료: 웹 UI와 REST API, 업로드/파싱/스키마/추출/근거 검수/수정/승인/JSON·CSV 내보내기.
- 검증: 백엔드 통합 테스트 7개, 프론트 프로덕션 빌드, Chrome 일반·API 키 강제 모드의 전체 흐름 통과.
- 외부 AI 실호출과 Tesseract OCR은 미검증이며 추가 환경 설정이 필요하다. RBAC·webhook 등 후속 기능은 미구현이다.
- 테스트 서버는 종료했다. 실행 방법은 작업 디렉터리의 README를 참조한다.
- 후속 요청에 따라 구현 파일을 커밋하고 `dev` 브랜치로 통합한다. 루트 README는 실행 가능한 구현의 설치 안내로 교체된다.

## AI 통합 UI 보완

- 비밀값을 노출하지 않는 `GET /api/ai/status`를 UI가 조회해 provider/model 및 연결 준비 상태를 표시한다.
- 생성된 스키마와 수동 저장 스키마를 즉시 선택해, 생성 뒤 별도 선택 없이 추출을 이어갈 수 있게 했다.
- 앱 API 키와 AI provider 자격증명의 역할을 구분해 UI에서 provider 키를 입력하거나 표시하지 않는다.
- 검증: `frontend`에서 `npm run build` 통과.
- OCR 기본 경로는 라이브러리 파싱으로 표시하며, 선택된 원격 PaddleOCR 서버만 상태 API의 준비값에 따라 별도로 표기한다. 미설정 PaddleOCR은 업로드·스키마·추출 흐름을 비활성화하지 않는다.
