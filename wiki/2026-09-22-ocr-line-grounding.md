---
type: Implementation Log
title: "OCR 줄 좌표 기반 grounding"
description: "표 블록을 행 수로 균등 분할해 추정하던 grounding bbox를 PP-OCRv5 줄 단위 OCR 좌표로 교체한 기록"
tags: [backend, ocr, grounding, paddleocr, deployment]
generated: {by: claude-code/claude-fable-5-1, at: 2026-09-22}
status: stable
---

# OCR 줄 좌표 기반 grounding

[extract-grounding-block-id](2026-09-21-extract-grounding-block-id.md)에서 도입한 행 bbox 추정("블록 상자를 `<tr>` 개수로 세로 균등 분할")을 폐기하고, **구조·내용은 PaddleOCR-VL, 좌표는 PP-OCRv5 일반 OCR 파이프라인**이 맡는 구조로 바꿨다.

## 문제: 균등 분할은 실제 영수증에서 행을 맞히지 못한다

검증 문서(`e1bf4c835ab44912b87bec610dd321bc.png`, 외래 진료비 영수증)는 페이지 거의 전체가 표 블록 하나(42행)이고, rowspan이 많으며 하단에 높이가 다른 설명문 행이 있다. 행 높이를 모두 같다고 가정한 균등 분할은 여기서 이렇게 어긋났다.

| 값 | 실제 행 | 균등 분할이 그린 행 |
|----|---------|---------------------|
| `진찰료` | 진찰료 행 | 입원료 행 |
| `처치 및 수술료` | 처치 및 수술료 행 | 3행 아래 |
| `수액` | 수액 행 | 5행 아래 |

앞선 검증 문서(`2303314528.png`)에서 오차가 눈에 띄지 않았던 것은 그 표의 25행이 우연히 거의 균등했기 때문이다. 틀린 강조는 표 전체를 강조하는 것보다 나쁘다. 사용자가 "이 값의 근거"라고 믿고 보는 위치가 다른 행이면 검토가 오히려 오염된다.

## 검토한 대안

| 대안 | 판단 |
|------|------|
| **PP-OCRv5 일반 OCR 파이프라인(채택)** | 같은 PaddleOCR-VL 이미지에 이미 들어 있는 `pipeline: OCR`을 별도 포트로 한 번 더 띄우면 끝. 줄 단위 상자(`rec_boxes`)를 VL과 **같은 이미지 좌표계**로 돌려준다. 이 영수증에서 CPU 6.7초, 155줄. 추가 모델·라이선스·외부 전송 없음 |
| PP-StructureV3 | 표를 셀 단위로 인식해 셀 좌표를 주지만 파이프라인이 무겁고(레이아웃+표인식+OCR 재실행) VL이 이미 만든 구조와 중복·불일치가 생긴다. 셀 좌표까지 필요한 수준의 문제가 아니었다 |
| PaddleOCR-VL-1.5 text spotting | VL이 좌표까지 직접 내는 모드. 현재 서빙 중인 1.6 계열 `/layout-parsing` 응답에는 `block_bbox`뿐이고, 모드를 바꾸면 이미 검증된 구조·내용 품질을 다시 검증해야 한다 |
| 외부 OCR API(클라우드) | 문서가 병원 영수증이라 외부 전송이 불가. on-prem 원칙에 어긋난다 |
| Tesseract·EasyOCR 등 | 별도 엔진·모델 관리가 늘고 한국어 인식 품질이 PP-OCRv5보다 낮다. 좌표만 필요한데 파이프라인이 하나 더 생긴다 |

## 구조: VL은 구조, PP-OCRv5는 좌표

```
문서 ─┬─→ PaddleOCR-VL /layout-parsing → 블록(구조·내용·블록 bbox)
      └─→ PP-OCRv5   /ocr             → 줄(텍스트·줄 bbox)
                                          ↓
                        줄을 "중심점이 들어가는 가장 작은 블록"에 붙임
                                          ↓
                              block["lines"] = [{text, bbox}, …]
```

`backend/parsers.py`의 `_attach_lines()`가 붙인다. 두 호출은 같은 파일(이미지면 원본, 페이지 범위를 지정한 PDF면 같은 부분 PDF)을 쓰므로 좌표계와 페이지 인덱스가 일치한다. 규칙은 셋뿐이다.

- 줄의 중심점이 들어가는 블록 중 **면적이 가장 작은 블록**에 붙인다(표가 텍스트 블록 안에 겹쳐 있을 때 표를 고른다).
- 어느 블록에도 안 들어가는 줄은 버린다.
- `/ocr` 호출이 실패하면 warning 로그만 남기고 줄 없이 진행한다. 좌표 정밀도만 잃고 파싱은 성공한다.

DB 스키마는 그대로다. `lines`는 `documents.blocks` JSON에 키 하나가 더 붙는 것뿐이고, 프론트엔드는 블록에서 필요한 키만 골라 읽으므로(`Blocks.tsx`, `Rendered.tsx`, `Preview.tsx`) 영향이 없다. 타입 선언에만 `Block.lines?`를 추가했다.

## grounding: 줄 상자 선택

`backend/engine.py`에서 `_row_bbox()`(균등 분할)를 삭제했다. 매칭된 위치의 bbox는 이렇게 정한다.

1. 값이 들어 있는 `(블록, 행)`을 찾는 규칙(`_hits`)과 confidence 규칙(합의 행 기반 1.0/0.5/0.0)은 **그대로**다. 줄 상자는 bbox 정밀화에만 쓴다.
2. 그 블록에 `lines`가 있으면 값과 일치하는 줄을 고른다. 일치 판정은 `_hits`와 같은 기준을 공유하는 `_rank()`(정규화 전체 일치 2점 > 3자 이상 부분 포함 1점)로 하고, 점수가 높은 후보만 남긴다.
3. 후보가 여럿이면(`47,300` 4곳, `40,000` 2곳) **형제 leaf들이 모인 y 대역**에 가장 가까운 줄을 고른다. 대역은 후보 줄이 하나뿐인 형제들의 y 중심 중앙값이다(`_band`). HTML 행 합의의 기하학적 대응물이며, 형제 정보가 없으면 첫 후보를 쓴다.
4. 일치하는 줄이 없으면 **블록 bbox**를 쓴다. 더 이상 추정하지 않는다.

## 불리언 leaf 제외

불리언은 원문에 그 글자로 적히지 않는 파생 값이라(`true`/`false`는 문서 어디에도 없다) 전부 `confidence 0.0`이 되어 `low_confidence` 오탐을 만들었다. 이제 `_grounding_tree`가 불리언 leaf를 트리에 넣지 않는다.

누락은 안전하다. `backend/main.py`의 `grounding_list()`는 트리에 있는 키만 평탄화하고, `validate()`의 `check_groundings`도 존재하는 항목만 순회한다. 프론트엔드는 `doc.groundings?.find(g => g.path === key)`가 `undefined`를 돌려주면 해당 필드를 "위치 없음"으로 그리고 상자를 만들지 않는다(값이 있지만 bbox가 없을 때 이미 쓰던 경로와 같다).

## 설정과 배포

```dotenv
PADDLEOCR_LINES_URL=http://127.0.0.1:8081   # 비우면 기능 전체 비활성(기존 블록 단위 동작)
```

compose `ocr` profile에 `paddleocr-lines-api`를 추가했다. 기존 `paddleocr-vl` 이미지를 그대로 재사용하고 `deploy/paddleocr/ocr_lines.yaml`(PP-OCRv5_server_det + korean_PP-OCRv5_mobile_rec, doc preprocessor·textline orientation 끔)을 `paddlex --serve --device cpu`로 띄운다. 호스트 포트는 `PADDLEOCR_LINES_PORT`(기본 8081), 모델 캐시는 named volume `docraft_paddlex_models`를 `/home/paddleocr/.paddlex`(이미지의 `$HOME`)에 붙인다. backend·worker 환경변수에는 `PADDLEOCR_LINES_URL: http://paddleocr-lines-api:8080`이 들어간다.

**CPU로 돌려도 GPU 예약(`deploy: *gpu`)이 필요하다.** 이 이미지는 paddlepaddle-gpu 빌드라 `--device cpu`여도 `libcuda`를 로드한다. 프로토타입에서 `--gpus all` 없이 띄우면 ImportError로 죽었다. GPU 메모리는 쓰지 않으므로 VL 컨테이너와 같은 GPU를 공유해도 된다.

`docker compose --profile ocr --profile app config`로 문법과 환경변수 주입만 확인했다(프로토타입이 8081을 쓰고 있어 실제 기동은 하지 않았다).

## 검증

### 단위 테스트

```
python -m pytest tests -q --ignore=tests/ui_smoke.py --ignore=tests/ui_preview_layout.py --ignore=tests/ui_project_workspace.py
71 passed
```

새로 넣은 것: 줄이 올바른(가장 작은) 블록에 붙는지·블록 밖 줄이 버려지는지, `/ocr` 실패 시 줄 없이 파싱 성공, 미설정이면 `/ocr`를 아예 호출하지 않음, 줄이 있으면 leaf bbox가 줄 상자가 되는지, 같은 값 후보가 둘일 때 형제와 가까운 줄을 고르는지, 줄이 없으면 블록 bbox(분할 아님)인지, 불리언 leaf가 트리에 없고 `validate()` 이슈도 없는지. 기존 행 분할 bbox 테스트는 새 동작으로 교체했다.

### 실제 문서 (LLM 호출 없이 저장된 result 재사용)

**영수증 `e1bf4c83…`** (블록 2개, 줄 152개). 문제로 지목된 위치가 전부 맞았다.

| leaf | 값 | conf | bbox | 기대 |
|------|-----|------|------|------|
| `/items/0/patient_burden` | 4593 | 1.0 | [362, 411, 431, 444] | ✅ 일치 |
| `/items/0/insurance_burden` | 10717 | 1.0 | [494, 406, 571, 443] | ✅ 일치 |
| `/items/1/item_name` | 처치 및 수술료 | 1.0 | [116, 726, 280, 759] | ✅ 일치 |
| `/items/1/patient_burden` | 2788 | 1.0 | [365, 727, 433, 761] | ✅ 같은 행 |
| `/items/1/insurance_burden` | 6504 | 1.0 | [504, 726, 574, 760] | ✅ 같은 행 |
| `/items/2/patient_burden` | 40000 | 1.0 | [912, 1239, 990, 1273] | ✅ 수액 행(합계 행 1437 아님) |
| `/total_medical_cost` | 64600 | 1.0 | [1374, 351, 1449, 381] | ✅ |
| `/amount_to_pay` 등 `47,300` 4개 leaf | 47300 | 1.0 | [1374, 426, 1449, 456] | ✅ 같은 형제 대역 |

`40,000`은 줄 후보가 2곳(y 1239, y 1437), `47,300`은 4곳이었고 형제 대역 규칙이 올바른 쪽을 골랐다.

기대와 달랐던 항목과 원인:

- `/items/0/item_name`(`진찰료`) → `confidence 0.0`. 이번 재파싱에서 VL이 그 셀을 `진 찰 로`로 읽어(저장된 result의 `진찰료`와 다름) 행 매칭 자체가 실패했다. grounding이 아니라 VL 인식 편차다. PP-OCRv5 쪽은 같은 자리를 `진찰료`로 정확히 읽었다.
- `/medical_facility_info/name`(`연세암은이비인후과`), `/patient_info/registration_number` → 블록 bbox로 fallback. 줄 OCR은 같은 자리를 `연세앓은이비인후과`로 읽어 두 엔진의 문자열이 달라 줄을 고르지 못했다.
- `/payment_details/cash_payment` 등 값이 `0`인 leaf → `0.0`. 1글자 값은 부분 일치를 허용하지 않는 기존 규칙 때문이며 이번 변경과 무관하다.

**진료비 세부산정내역 `6b9d27e7…`** (블록 3개, 줄 243개, 항목 16개). 16개 항목이 전부 서로 다른 y 대역에 1:1로 매핑됐다.

| 항목 | 0 | 1 | 2 | … | 14 | 15 | 합계 |
|------|---|---|---|---|----|----|------|
| 대역 y 중앙값 | 560 | 604 | 646 | (42px씩 증가) | 1158 | 1200 | 1340 |

한 항목 안 leaf 13개의 y 중심이 최대 10px 안에 모였고(행 높이 약 42px), 208개 leaf 전부 `confidence 1.0`, `low_confidence` 이슈 0건이었다. 최상위 `환자성명`·`진료기간`은 환자 정보 행(y 299~344), 중첩 객체 `합계`는 합계 행(y 1320~1360)을 가리킨다. 블록 bbox로 fallback한 것은 긴 약품 `명칭` 7개뿐이다.

## 남은 한계

- **긴 값은 줄 하나에 안 들어간다.** OCR이 두 줄로 끊어 읽은 약품 명칭처럼 값 전체를 담은 줄이 없으면 블록 bbox로 돌아간다(문서 2에서 16개 중 7개). 조각 줄들을 이어 붙이는 방법은 다른 행의 같은 조각까지 묶을 위험이 있어 넣지 않았다.
- **두 엔진의 텍스트가 다르면 줄을 못 고른다.** VL과 PP-OCRv5는 서로 다른 인식기라 `암`↔`앓`처럼 한 글자가 갈리면 일치 판정이 실패하고 블록 bbox가 된다. 값 매칭 기준을 느슨하게 하면 다른 값에 붙을 위험이 커져 그대로 뒀다.
- **같은 행에 같은 값이 여러 컬럼에 있으면 컬럼을 구분하지 못한다.** 문서 2의 `전액본인부담`·`비급여`가 둘 다 `0`이면 같은 줄 상자를 가리킨다. 대역은 세로 방향만 보기 때문이다. 스키마 필드를 표 컬럼에 매핑하기 전에는 해결되지 않는다(행 밀림 한계와 같은 뿌리).
- **처리 시간이 늘어난다.** 이 영수증 기준 CPU에서 약 6.7초가 파싱에 더 붙는다. GPU로 돌리거나 끄고 싶으면 `PADDLEOCR_LINES_URL`을 비우면 된다.
- `confidence`의 의미는 그대로 "원문의 어느 행에서 값을 찾았는지"다. 줄 상자를 쓴다고 추출 품질이 검증되지는 않는다.
