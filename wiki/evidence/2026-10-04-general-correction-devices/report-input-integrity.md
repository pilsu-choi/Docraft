# input-integrity 보고 (Docraft feat/input-integrity)
커밋: 위 git log 첫 줄 (dev f3856b8 기반). 병합·push 안 함.

## 근본 원인 / 유형
- 입력 단계의 손실(2000px 축소, 5쪽부터 이미지 미첨부 A12, 다중 프레임 TIFF는 /api/read 422·큐에서는 첫 프레임만 조용히 읽음)이 결과에 기록되지 않음 = "입력 무결성 계측 부재".
- 같은 표·쪽 중복, 쪽 경계 반복 행, 쪽 순서 이상은 B2(경계 1건 제거) 외에 탐지 없음 = "단위 경계·중복 탐지 부재".

## 설계
- 새 구조 없음. engine.py에 함수 4개: `input_report`(AUX.INPUT: 쪽 수·EXIF 회전·파서 회전·쪽별 축소 배율·디코딩 실패·이미지 미전송 쪽), `unit_flags`(쪽 순서 P.WRG.ORDER.1, 같은 쪽 두 번 P.OVR.DUP.1, 쪽 경계 반복 행·같은 표 두 번 읽힘 E.OVR.DUP.1, 행 쪽 번호 역순 P.WRG.ORDER.1, 표 쪽 건너뜀 P.STR.LINK.1), `apply_integrity`(두 경로 공통 진입점), `_table_fields`(extract의 표 판별 코드를 공유로 뺌).
- 결과 형식 재사용: 영향받은 값의 `quality[path].issue_codes`에 코드 추가(기존 assess·annotate_groundings 경로로 groundings에도 노출), 요약 `{input, flags, lossy_pages}`는 큐에서는 `documents.completeness["integrity"]`(B6 completeness와 같은 칸, 최종 UPDATE에 completeness 포함), /api/read에서는 `diagnostics.integrity`. 쪽 단위 코드는 provenance.page로, 행 코드는 `표/행/` 경로 접두로 해당 값에 붙임. 노드 ID는 flag/input에 담김(INTEGRITY_NODES).
- 값은 바꾸지 않음. 판정 반영은 `INTEGRITY_REVIEW`(기본 false)가 true일 때만 PASS→SUSPICIOUS/RECHECK.
- 서식·필드·열 이름 하드코딩 없음(행은 값 서명, 쪽은 grounding page).
- 다중 프레임 TIFF: parse_image가 프레임을 EXIF 정규화 후 PDF로 펼쳐 기존 PDF 쪽 처리(OCR·_upright·쪽 번호) 재사용. VLM 이미지는 fitz가 TIFF 프레임을 쪽으로 열어 기존 경로 그대로. reprocess._crop은 쪽 번호에 맞는 프레임을 seek. /api/read는 다중 프레임 허용(process_image multipage=True), /api/verify는 AO가 단일 쪽이라 기존대로 422 유지.

## 변경 파일
backend/engine.py, main.py(run_extract·read_document·process_image), parsers.py(parse_image), reprocess.py(_crop), config.py(integrity_review), tests/test_input_integrity.py(신규), test_read.py·test_orientation.py·test_integrity.py(기대 변경).

## 테스트 (DB는 docker postgres:17 임시 컨테이너 5441, 외부 호출 0)
전체 900 통과(기존 대비 새 실패 없음). 신규 7건: 큰 쪽 축소/정상 쪽, 다중 프레임 TIFF 수·디코딩 실패, 5쪽 이후 미전송(표 쪽 묶음은 전송으로 간주, 소스 없음), 경계 반복(같은 쪽 반복·빈 행은 제외), 표 두 번 읽힘(공백·균일 행 제외), 쪽 순서·중복 쪽·표 쪽 건너뜀, apply_integrity가 값 불변·플래그 on 시 RECHECK. 수정: test_read(다중 TIFF 허용·요약 노출), test_orientation(프레임별 한 쪽), test_integrity(completeness에 integrity 포함).

## 로컬 측정
미실시(harness 기준 재생 대상 아님: 탐지만 추가, 값·정확도 불변). 정탐·오탐 측정은 harness 연동 시 필요.

## 위험 / 남은 일
- 'image_not_sent'는 정적 추정(청크·표 쪽 묶음 어느 호출에도 이미지가 안 실린 쪽). 호출 실제 첨부 기록이 아님.
- 반복 행 탐지는 실제 같은 행이 쪽 경계에 연속되는 정상 문서에서 오탐 가능(표시만, 기본 판정 불변).
- table_page_gap은 추출 대상이 아닌 표가 낀 쪽도 잡을 수 있음.
- reprocess._rotated(전체 쪽 회전 재시도)는 여전히 첫 프레임만 사용 — 다중 프레임에서 미보정.
- 큐 업로드 UI/API는 이미 다중 프레임 허용 상태였음(이제 첫 프레임만 읽는 손실이 해소).
- wiki·README 갱신은 하지 않음(오케스트레이터 몫). 가져갈 설정: INTEGRITY_REVIEW.
