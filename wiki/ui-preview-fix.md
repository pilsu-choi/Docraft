# 원본 문서 미리보기 크기 수정

2026-09-21

- 원인: PDF는 고정 1.5배, 이미지는 원본 픽셀 크기로 렌더링해 문서 패널 너비보다 커졌다. PDF 캔버스의 실제 픽셀 크기와 화면 크기도 분리되지 않아 고해상도 화면과 근거 상자 좌표에서 불일치할 수 있었다.
- 수정: PDF·이미지의 기본 크기를 패널 너비에 맞추고, 사용자가 누른 확대·축소 배율을 그 기준에 적용한다. `ResizeObserver`로 패널 접기·펼치기와 창 크기 변경을 반영한다. PDF 캔버스는 DPR을 실제 픽셀에만 적용하고 CSS 크기와 근거 상자는 문서의 화면 좌표계로 계산한다. 확대 결과가 패널보다 크면 미리보기 영역에서 스크롤한다.
- 연속 리사이즈·페이지 변경에서 이전 PDF 렌더 작업이 끝나기 전에 같은 캔버스에 새 작업이 시작되지 않도록 직렬화했다.
- 검증: `frontend`에서 `npm run build` 성공. 격리된 Vite 5175와 API 전부 모킹한 Playwright `tests/ui_preview_layout.py`에서 데스크톱·800px·390px PDF/큰 이미지 너비 맞춤, DPR 2 캔버스, 확대 후 가로 스크롤, 작업 패널 접기·펼치기 후 재맞춤, 근거 상자 위치 및 390px 본문 가로 넘침 없음까지 확인했다. 홈·프로젝트 목록·단계 이동과 선택 지침 유지도 확인했으며 실제 프로젝트 또는 AI API는 사용하지 않았다.
- 시각 자료: `/tmp/docraft-preview-home.png`, `/tmp/docraft-preview-projects.png`, `/tmp/docraft-preview-pdf-fit.png`, `/tmp/docraft-preview-pdf-zoom.png`, `/tmp/docraft-preview-image-fit.png`, `/tmp/docraft-preview-narrow.png`, `/tmp/docraft-preview-mobile-390.png`.
- 최종 화면 재설계에 맞춰 기존 `tests/ui_smoke.py`, `tests/ui_project_workspace.py`의 단계 버튼·생성·추출·승인·다운로드 선택자를 갱신했다. 두 테스트는 실제 서버와 provider 동작을 포함하므로 이번 작업에서는 정적 대조와 Python 문법 검사만 수행하고 실행하지 않았다.
