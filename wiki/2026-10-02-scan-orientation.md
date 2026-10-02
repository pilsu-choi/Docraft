---
okf_version: "0.2"
type: change
title: 돌아간 스캔의 방향 정규화
description: 90°·180°·270° 돌아간 스캔 페이지를 OCR 줄 상자와 마침표·쉼표 위치로 판별해 바로 세워 다시 읽고, 좌표는 원본 파일 기준으로 되돌린다
tags: [docraft, paddleocr, orientation, scan, table, reprocess, vision]
status: active
---

- 날짜: 2026-10-02
- 브랜치: fix/scan-orientation
- 워크트리: .worktrees/rotation-fix

## 증상

정답지 세부내역서 `20250102091737a0.tif`·`a2.tif`·`a3.tif`(1728×2333, 단일 프레임, EXIF 회전 없음)는 가로 서식을 세로 용지에 시계 방향 90°로 눕혀 팩스로 보낸 스캔이다(맨 위 팩스 머리글만 바로 서 있음). rowmajor 실험에서 OCR 줄 좌표가 세로로 나와 열 순서 판별이 실패했고, 행 전체가 빠졌다(누락 117셀 대부분, asis도 49.6%·49.8%·77.2%).

## 근본 원인

이미지가 들어온 방향 그대로 PaddleOCR-VL·줄 OCR·괘선 격자(`_ruled_tables`)·VLM 페이지 이미지·재처리 크롭에 쓰였다. 방향 보정은 EXIF(`exif_transpose`)뿐이었고, 줄 OCR 설정(`deploy/paddleocr/ocr_lines.yaml`)은 좌표가 바뀐다는 이유로 doc preprocessor를 끈 상태다. 재처리(`reprocess`)의 `rotate_ccw`/`rotate_cw` 단계가 사후에 페이지 전체를 두 방향으로 다시 읽어 보는 것이 유일한 대응이었고, 그것도 합계 필드에만 적용됐다.

## 문제 유형과 범위

**입력 페이지 방향이 정규화되지 않은 채 OCR·VLM에 들어간다.** 같은 원인을 공유하는 경로:

| 경로 | 처리 |
| --- | --- |
| 이미지 OCR(`parse_image`, 다중 프레임 TIF는 첫 프레임) | 판별 후 바로 세워 다시 읽음 |
| 스캔 PDF OCR(`parse_pdf`, 페이지 범위 포함) | 페이지마다 판별, 돌아간 페이지만 다시 읽음 |
| 괘선 격자·셀 좌표(`_ruled_tables`) | 다시 읽기 안에서 바로 선 이미지로 계산 → 원본 좌표로 되돌림 |
| 추출 VLM 페이지 이미지(`engine.extract` → `_page_images`) | 블록 `orientation`대로 돌려서 보냄 |
| 재처리 ROI 크롭(`reprocess._crop`/`_remap`) | 크롭을 바로 세워 읽고 `unturn`으로 되돌림 |
| 재처리 회전 단계 | 이미 정규화된 페이지면 건너뜀. 좌표 되돌리기는 공통 `unturn` 사용(`_remap_rotation` 삭제) |

범위 밖으로 남긴 것: `verify.judge`와 스키마 생성(`generate_schema_from_documents`)의 VLM 이미지. 블록을 받지 않는 호출이라 `turns` 전달에 호출부 변경이 필요하고, 같은 파일을 고치는 `feat/rowmajor-table`과 충돌을 피하려고 병합 뒤 후속으로 둔다.

## 설계

1. 첫 OCR(평소 그대로)의 줄 상자(`lines`)를 원본 페이지 이미지 위에서 본다. `parsers.orientation(image, lines)`:
   - 줄 상자를 Otsu로 이진화하고, 글자 띠 높이의 30% 이하인 작은 표(마침표·쉼표)가 띠의 위/아래 어느 끝에 있는지 센다. 한글·숫자·라틴 인쇄 모두 마침표·쉼표는 기준선에 붙는다.
   - 세로로 긴 상자는 누운 글자다. 표가 왼쪽이면 시계 방향으로 누운 것(반시계 90° 보정), 오른쪽이면 270°.
   - 최다 득표가 4표 이상이고 나머지 합의 3배 이상일 때만 돌린다. 근거가 약하면 0(그대로).
   - numpy·Pillow만 쓴다. 새 의존성·모델 없음, 페이지당 35ms 이하.
2. 돌아간 페이지만 `image.rotate(turn, expand=True)`로 세워 `_remote_paddle`로 한 번 더 읽는다(바로 선 문서는 추가 호출 0). 다시 읽기가 실패하면 첫 결과를 유지하고 경고를 남긴다.
3. `parsers.unturn(blocks, turn)`이 bbox·줄·셀·다각형을 원본 좌표로 되돌리고 `page_size`를 원본 크기로 바꾼다. 90° 단위 회전은 기울기 보정 각도(`rotation_degrees`)와 교환되므로 빈칸 셀 근거(`rotated_cell_hull`)는 유효하게 남긴다(기존 `_remap_rotation`은 무효화했다).

### 좌표 기준

응답의 `bbox`·`page_size`·`polygon`은 항상 **요청 파일(EXIF 회전 반영) 픽셀 기준**이다. 돌아간 페이지의 블록에는 `orientation`(바로 세우려고 반시계로 돌린 각도: 90·180·270)이 붙는다. 클라이언트(하네스 ROI 크롭·뷰어)는 바꿀 것이 없다.

## 오프라인 검증 (AWS 호출 없음)

저장된 OCR 블록(`e2e/out/ab-rowmajor-1002/ocr/`)의 줄 상자와 원본 이미지로 판별기만 돌렸다. 스크립트: 세션 scratchpad `ori/validate.py`.

| 집합 | 결과 |
| --- | --- |
| 정답지 59장 원본 | 59/59 — a0·a2·a3은 90, 나머지 56장은 0(잘못 돌린 것 없음) |
| 59장 × 90·180·270 합성 회전(이미지와 줄 상자를 함께 회전) | 177/177 |
| 합계 | 236/236 |

## 테스트

`tests/test_orientation.py`(15건): 0·90·180·270 합성 페이지 판별, 근거 부족 시 그대로, `unturn` 90·180·270 역변환(줄·셀·다각형·`orientation`), 돌아간 이미지 재판독과 원본 좌표 보고, 바로 선 이미지는 1회 호출, 재판독 실패 시 첫 결과 유지, 다중 프레임 TIF 첫 프레임, 스캔 PDF는 돌아간 페이지만 재판독, VLM 페이지 이미지 회전, 재처리 ROI 크롭 회전·역매핑. `tests/test_reprocess_inference.py`는 공통 `unturn`으로 갱신. 전체 676 passed.

## AWS 대기

판별 이후의 정확도(누락 117셀 회복 여부)는 재OCR이 필요하다. AWS PaddleOCR-VL이 꺼져 있어 배포 담당 세션에 다음을 요청한다.

- 대상: Docraft `fix/scan-orientation`(dev 병합 후), 문서 3건 `세부내역서/20250102091737a0.tif`·`a2.tif`·`a3.tif`
- 실행: 컨테이너에서 기존 `ocr/세부내역서/<파일>.json` 3건을 지우고 `/tmp/ab/imgs`에 3건만 두고 `python ocr_only.py 3` → rowmajor·asis 헤더 채점 재실행
- 확인: 블록 `orientation == 90`, 줄 상자 가로, 3건 셀 정확도(asis 49.6%·49.8%·77.2% 대비)
