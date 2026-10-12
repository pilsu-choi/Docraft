---
okf_version: "0.2"
type: change
title: 페이지 기울기 보정(PAGE_DESKEW)
description: 방향(90도 단위)과 작은 기울기를 페이지마다 한 각도로 합쳐 모델에 보내는 이미지를 돌리고, 띠 상자와 표 상자는 그 돌린 페이지 기준으로 맞췄다. 원근 보정은 넣지 않았다
tags: [docraft, 기울기, orientation, band, vlm, 이미지]
status: active
---

날짜: 2026-10-12
브랜치: `feat/page-skew`(dev 기준)
워크트리: `Docraft/.worktrees/page-skew`

## 왜

모델에 보내는 페이지 이미지는 90도 단위로만 세웠다. 사진·복사로 몇 도 기울어진 영수증은 기울어진 채 띠로 잘렸다. 실험(`exp/e2e_call_test/fix_receipt_images.py`)에서 방향을 세운 뒤 미세 기울기를 펴자 띠 읽기 정확도가 95.04%에서 97.17%로 올랐다(원근 보정은 오히려 나빠져 넣지 않음).

## 설계: 회전은 하나

방향과 기울기는 둘 다 회전이다. 측정은 따로(기울기 측정은 0도와 180도를 못 가르고, 방향 투표는 3도를 못 본다) 하되, 돌리는 일과 좌표 대응은 한 가지 규칙으로 합쳤다.

| 단계 | 내용 |
| --- | --- |
| 측정 | `parsers._upright`가 방향을 정한 뒤, 바로 선 페이지 사본에 `table_grid._skew`(`tilt=8`)를 적용한다. 0.3도 미만이거나 탐색 한계(7.8도 이상)에 붙은 값은 0으로 본다 |
| 저장 | 블록의 `orientation`(90도 단위, OCR 좌표 기준)은 그대로 두고, 기울기는 같은 쪽 블록의 `skew`로 둔다. OCR 좌표와 `unturn` 소비자(table_layout, reprocess 등)는 바뀌지 않는다 |
| 합산 | `engine._angle(block) = orientation + skew`. `_turns(blocks)`가 쪽별 합계 각도를 낸다 |
| 이미지 | `engine._data_url`이 합계 각도로 돌린다. 90도 배수는 기존대로 페이지 행렬(`prerotate`)로 그려 결과가 바이트까지 같고, 그 밖의 각도는 그린 영역을 쌍삼차(bicubic)로 돌린다(흰 바탕, 모서리 확장) |
| 좌표 | `parsers.spin`이 "페이지를 `angle`도 돌렸을 때 점이 놓이는 곳"(두 페이지의 중심 기준)을 하나로 정한다. `unturn`도 이 규칙으로 일반 각도를 받는다(상자는 중심만 옮기고 크기는 유지, 90도 근처에서만 가로세로 교환) |
| 띠 | `_bands`·`_located_bands`는 OCR 줄을 돌린 페이지로 옮겨 행을 나누고, `clips`는 돌린 페이지 기준 비율이다. 원본 파일 좌표로 되돌리는 일은 `_data_url` 한 곳(`_covering`)이 한다. 예전 `_clip`의 90도 분기는 사라졌다 |

설정은 `PAGE_DESKEW`(기본 `1`). 끄면 `skew`가 붙지 않아 이전 경로와 같다. `.env.example`, `deploy/aws/.env.aws.example`, helm `backend.pageDeskew`, README 설정 표에 추가했다.

## 건드리지 않은 곳

- 표 교정(`refine_tables`)의 표 크롭: 방향만 쓴다(기울기 보정 없음). OCR 좌표 기준 크롭이라 기울기를 따로 반영하지 않았다.
- `reprocess._crop`, `table_layout._lines`, 쪽 해시(`_page_hashes`): 블록 좌표 기준 또는 근접 쪽 비교용이라 90도 방향만 쓴다. 해시는 합계 각도를 받아도 쪽끼리 같은 방식으로 돌아 비교에 영향이 작다.
- `/api/read` 근거 상자(grounding)는 OCR 좌표 그대로다. 모델 이미지만 돌리므로 되돌릴 상자가 없다.

## 위험

- 기울기 추정은 글자·괘선이 적은 쪽에서 틀릴 수 있다. 탐색 한계에 붙거나 0.3도 미만이면 돌리지 않는다.
- 표 상자와 OCR 줄 상자는 기울어진 쪽의 바깥 상자라, 돌린 뒤에도 같은 크기로 둔다(중심만 이동). 3도 기울기에서 띠 경계가 약간 여유 있게 잡힌다.
- 정확도 영향은 아직 실측하지 않았다(외부 호출 없이 단위 시험만). AWS 배포 담당 세션에서 영수증 정답지 회귀로 확인해야 한다.

## 검증

`tests/test_skew.py`(신규 39건): 기울기 추정(±2·±5·±7도, 0.2도 무시, 한계 밖 무시), 방향 90/180/270+기울기 합산, 끔 스위치, 임의 각도의 띠 조각이 원본의 같은 곳을 보여 주는지(0·±2·±5·93·178·274·90·180도), 90도 배수 렌더링이 이전 방식과 바이트 동일(전체 쪽·띠), `unturn` 일반 각도 좌표. 영향 모듈(band·rowmajor·orientation·read·verify·pagewise·parsers·ai_provider·reprocess 등) 461건 통과. 외부 호출 없음.
