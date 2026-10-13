"""``TABLE_EXTRACT=band``: 1쪽 문서의 긴 항목 표를 가로 띠로 잘라 읽는 데 쓰는 순수 함수.

모델 호출과 OCR 행 경계로 띠 자르기(세부내역서, ``engine._bands``)는 ``engine``이 한다. 여기는 문서 유형별 설정(``PROFILES``),
진료비영수증 위치 응답 후처리(``boxes``)·띠 자르기(``clips``)·금액산정 블록 크롭(``summary_clip``)·띠 겹침 판정(``overlap``), 짧은 키 읽기
형식(``prompt``·``expand``)만 둔다. 좌표는 모두 쪽 크기를 1000으로 본 값이다."""

import difflib
import re

from . import doctypes, rules

BANDS, OVERLAP, TAIL, SIMILAR, ALIGN = 3, 0.10, 8, 0.7, 15
SUMMARY_KEYS = ("진료비총액", "환자부담총액", "이미납부한금액", "납부할금액", "납부한금액_카드", "납부한금액_현금영수증", "납부한금액_현금",
                "납부한금액_합계", "공단부담총액", "상한액초과금")  # 항목표 밖 금액산정 블록에 인쇄된 필드
REGIONS = {"item_grid": "ONLY the itemized charge table: the item-name column plus its 급여/비급여 amount columns, from the column-header rows down to and including the final 합계/계 row. "
                        "EXCLUDE the 금액산정(payment calculation) panel (진료비 총액·환자부담 총액·납부한 금액 …) even if it sits to the right of the table in the same frame",
           "header": "only the column-header rows of item_grid (항목 / 급여 / 일부본인부담 / 본인부담금 / 공단부담금 / 전액본인부담 / 비급여 ...), all header levels together",
           "first_row": "the first data row of item_grid (usually 진찰료), within item_grid's x range",
           "total": "the final 합계/계 row of item_grid, within item_grid's x range",
           "summary": "the 금액산정내용 block wherever it is (right side, below or beside the table): 진료비 총액, 환자부담 총액, 이미 납부한 금액, 납부할 금액, 납부한 금액 카드/현금영수증/현금/합계, 공단부담 총액, 상한액 초과금 etc."}
LOCATE_PROMPT = ("Locate regions of this Korean medical receipt (진료비 계산서·영수증). For each key give a bounding box [x1, y1, x2, y2] "
                 "in coordinates normalized to 0-1000 of the image width/height:\n" + "\n".join(f"- {key}: {text}" for key, text in REGIONS.items())
                 + "\nReturn only JSON: {" + ", ".join(f'"{key}": [...]' for key in REGIONS)
                 + "}. Use null for a region that is not present.")
LAYOUTS = ("(a) 요양급여 | 비급여; (b) 본인부담금 | 공단부담금 | 전액본인부담 | 비급여; (c) 본인부담금 | 공단부담금 | 전액본인부담 | 선택진료료 | 비급여; "
           "(d) 본인부담금 | 공단부담금 | 전액본인부담 | 선택진료료 | 선택진료료외; (e) 본인부담금 | 공단부담금 | 전액본인부담 | 선택진료료외")
HEADER_NOTE = ("Column headers: a header's characters are often split over lines or spaced out inside one header cell ('선택진료료 / 이외', "
               "'선택진료 / 료 외', '선 택 진 료 료 외'); join the characters of the same cell before naming its column. A header with 외 or 이외 "
               "(also numbered ⑤) is 선택진료료외; 선택진료료 without 외 (④) is 선택진료료. When 비급여 is printed above sub-columns "
               "(선택진료료, 선택진료료외), it is only their group title: put each value under its sub-column key and 0 under 비급여.")
DETAIL_CLOSING = ("Every row in the strip is whole: the strip is cut in the blank space between printed rows, so transcribe every row, also the "  # 겹침 없는 OCR 행 띠
                  "first and last rows touching the top or bottom edge. Include the printed 소계·계·합계·끝수처리 조정금액 rows where they are printed, their "
                  "label in the 항목 key. Never return header rows. Copy the printed digits only, never compute or infer a value. "
                  "A blank cell is null (per the schema): write it as \"\".")
SUMMARY_PROMPT = ("This image is the 금액산정내용 (payment calculation) block of a Korean medical receipt. Extract these fields only:\nSchema:\n{schema}\n"
                  "Copy the printed digits only, never compute; use null for a field whose label or value is not printed.")


# 문서 유형별 band 설정. rows: None이면 VLM으로 표 위치를 찾아(LOCATE_PROMPT, boxes) BAND_STRIPS개로 겹쳐 자르고, 수이면 위치 찾기 없이
# OCR 행 경계에서 띠당 그만큼의 금액 행으로 자른다(engine._bands). hint: 열 설명에서 뗄 표 공통 힌트, name: 짧은 키 "n"으로 따로 받는 행 이름 열
# (None이면 모든 열이 짧은 키), zero: 빈칸을 "0"으로 채우는 열 종류(doctypes.kind, 나머지 빈칸은 None), sample: 응답 예시 값, statutory: 법정
# 서식 안내(항목 목록·열 배치 5종·머리글 안내)와 마지막 합계 행 하나만 남기기, 아니면 rowmajor 열 배치(table_layout.plan)로 인쇄된 열만 인쇄
# 순서로 묻는다. closing: 프롬프트 끝 규칙.
PROFILES = {
    "진료비영수증": {"rows": None, "hint": doctypes.RECEIPT_HINT, "name": "항목", "zero": ("amount",), "statutory": True,
                "sample": {"항목": "검사료", "본인부담금": "1,200", "공단부담금": "4,800"},
                "closing": "Skip rows whose name is cut off at the top or bottom edge. Include the final 합계 row if visible. Never return header rows. "
                           "Copy the printed digits only, never compute or infer a value. A blank cell is 0 (per the schema)."},
    # 세부내역서 항목 열(진찰료 등 구분명)은 같은 이름이 여러 행에 되풀이되고 섹션 제목 행에만 인쇄되기도 해 행 이름이 아니라 열 하나로 받는다.
    # 칸은 인쇄된 값만(DETAIL_HINT: 인쇄되지 않은 칸은 null) — 빈칸을 0으로 채우지 않는다. 미인쇄 급여 열의 0은 하네스 출력 단계 몫(2026-10-12).
    # 띠는 행 사이에서 잘라 겹치지 않으므로 같은 이름(진찰료)이 되풀이되는 행을 견줄 겹침 판정이 없다.
    "세부내역서": {"rows": 12, "hint": doctypes.DETAIL_HINT, "name": None, "zero": (), "statutory": False,
              "sample": {"항목": "진찰료", "시작일자": "20240105", "EDI코드": "AA154", "EDI명칭": "초진진찰료", "단가": "17,610", "횟수": "1", "일수": "1",
                         "총액": "17,610", "본인부담": "5,280", "공단부담": "12,330"},
              "closing": DETAIL_CLOSING},
}
RECEIPT = "진료비영수증"


def _box(value):
    """``[[x1, y1, x2, y2]]`` 로 감싼 응답도 받는다. 숫자 네 개가 아니면 None."""
    value = value[0] if isinstance(value, list) and len(value) == 1 and isinstance(value[0], list) else value
    return list(value) if isinstance(value, list) and len(value) == 4 and all(isinstance(x, (int, float)) for x in value) else None


def boxes(reply, lines=()):
    """위치 응답 → {grid, header, first_row, total[, summary]} 또는 None(표 상자가 모자라거나 순서가 어긋남). 높이 8% 미만 상자는 금액산정 블록이 아니라 버린다.

    금액산정 상자가 항목 표 옆(표 가로 40% 오른쪽)에 있으면 표의 오른쪽 끝은 패널 라벨의 왼쪽 끝이다(``panel_edge``, OCR 줄 ``lines``는 바로 선
    쪽 1000 정규화). 위치 응답의 표·패널 경계는 한 열쯤 어긋나곤 해(패널 상자가 표 맨 오른쪽 열을 덮거나 표 상자가 그 열 앞에서 끝남) 라벨 근거를
    먼저 따르고, 근거가 없으면 패널 상자가 표와 겹칠 때만 그 왼쪽에서 자른다."""
    found = {key: _box(value) for key, value in reply.items()} if isinstance(reply, dict) else {}
    if not all(found.get(key) for key in ("item_grid", "header", "first_row", "total")):
        return None
    result = {"grid": found["item_grid"], **{key: found[key] for key in ("header", "first_row", "total")}}
    grid, summary = result["grid"], found.get("summary")
    if not (result["header"][1] < result["first_row"][1] < result["total"][3]) or grid[0] >= grid[2]:
        return None
    if summary and summary[2] > summary[0] and summary[3] - summary[1] >= 80:
        result["summary"] = summary
        if grid[0] + 0.4 * (grid[2] - grid[0]) < summary[0]:
            edge = panel_edge(lines, summary, result["first_row"][1], result["total"][3])
            grid[2] = edge if edge is not None else min(grid[2], summary[0])
    return result


def panel_edge(lines, summary, top, bottom):
    """금액산정 상자 안·표 본문 높이(``top``~``bottom``)에 가운데가 든 패널 라벨(한글 두 글자 이상인 OCR 줄)의 왼쪽 정렬선: 왼쪽 끝이 ALIGN
    안에 가장 많이 모인 자리(같으면 왼쪽). 없으면 None. 가장 왼쪽 끝이 아니다 — 표와 패널에 걸친 안내 문구나 표 칸 오독 글자, 들여 쓴 하위 라벨이
    섞여도 라벨 열 자리는 그대로다."""
    lefts = [x0 for line in lines for x0, y0, x1, y1 in [line["bbox"]] if len(re.findall(r"[가-힣]", str(line["text"]))) >= 2
             and summary[0] <= (x0 + x1) / 2 <= summary[2] and max(top, summary[1]) <= (y0 + y1) / 2 <= min(bottom, summary[3])]
    return max(lefts, key=lambda x: (sum(x <= other <= x + ALIGN for other in lefts), -x), default=None)


def summary_clip(found):
    """금액산정 블록 크롭(쪽 비율 [x1, y1, x2, y2]). 표 옆 패널이면 라벨 열을 담게 왼쪽을 넓히고 세로는 표 높이까지, 아니면 사방을 조금 넓힌다."""
    (x1, y1, x2, y2), grid = found["summary"], found["grid"]
    beside = x1 > grid[0] + 0.4 * (grid[2] - grid[0])
    box = [x1 - (120 if beside else 40), min(y1, grid[1]) if beside else y1 - 30, x2 + 40, max(y2, grid[3]) if beside else y2 + 30]
    return [min(max(value, 0), 1000) / 1000 for value in box]


def clips(found, count=BANDS):
    """띠 읽기용 크롭 목록(쪽 비율). 표 머리글 위쪽부터 마지막 합계 행까지를 ``count``(``BAND_STRIPS``, 기본 BANDS) 등분해
    OVERLAP 만큼 겹치게 자른다. 첫 띠는 머리글째, 나머지 띠는 머리글 띠(첫 데이터 행 제외)를 앞에 둔다(읽을 때 위에 이어 붙여 한 장, ``engine._stacked``)."""
    x1, x2 = max(0, found["grid"][0] - 20), min(1000, found["grid"][2] + 20)
    head, first = max(0, found["header"][1] - 10), found["first_row"][1]
    top, bottom = first, min(1000, found["total"][3] + 15)
    height = bottom - top
    result = []
    for i in range(count):
        strip = [x1, head if i == 0 else max(top, top + height * i / count - OVERLAP * height), x2, min(bottom, top + height * (i + 1) / count + OVERLAP * height)]
        result.append([[value / 1000 for value in box] for box in ([strip] if i == 0 else [[x1, head, x2, first], strip])])
    return result


def short_keys(item, doc_type=RECEIPT, plan=None):
    """항목내역 열(행 이름 열 ``name`` 제외)을 순서대로 a, b, c… 에 대응한 {짧은 키: 열 이름}. 출력 토큰을 줄인다. 열은 ``plan``(rowmajor
    열 배치 ``table_layout.plan``: 인쇄된 열만 인쇄 순서로)이 있으면 그 열, 없으면 스키마 순서의 모든 열."""
    name = PROFILES[doc_type]["name"]
    return {chr(97 + i): key for i, key in enumerate(key for key in (plan[1] if plan else item["items"]["properties"]) if key != name)}


def prompt(item, note, header_note=False, doc_type=RECEIPT, plan=None):
    """띠 읽기 프롬프트: 모든 행에 (행 이름 열이 있는 유형은 이름 n과) 모든 짧은 키 열을 스키마 순서로 쓰게 한다. ``note``는 이미지 구성 안내.
    법정 서식(``statutory``, 진료비영수증)만 항목명 규칙·항목 목록·열 배치 5종을 붙이고, ``header_note``(``BAND_HEADER_NOTE``)면 쪼개 인쇄된
    머리글 이어 읽기·비급여 묶음 제목 안내(``HEADER_NOTE``)를 서식 목록 뒤에 붙인다. ``plan``이 있으면 열과 열 설명·표 설명은 rowmajor와 같은
    그 배치의 것(인쇄된 열만, 인쇄 순서, '이 문서에서는 … 열이다' 안내와 열 배치 안내 포함)."""
    profile, props, keys = PROFILES[doc_type], item["items"]["properties"], short_keys(item, doc_type, plan)
    name, sample = profile["name"], profile["sample"]
    texts = plan[1] if plan else {column: prop["description"] for column, prop in props.items()}
    columns = "\n".join(f'  "{key}" = {column}: ' + (re.sub(" +", " ", texts[column].replace(profile["hint"], "")) if plan
                                                      else texts[column].removesuffix(profile["hint"])).strip() for key, column in keys.items())
    example = ", ".join(f'"{key}": "{sample.get(column, "")}"' for key, column in (({"n": name} if name else {}) | keys).items())
    statutory = (f"항목 naming rule: {props['항목']['description']}\n"
                 "Reading aid: printed names on this statutory form usually come from this list: " + ", ".join(rules.ITEM_ORDER) + ". Use it to read blurred or partial names; "
                 "still output only rows actually printed, never add a row because it is in the list; names not in the list are written as printed.\n"
                 f"The form has one of 5 column layouts: {LAYOUTS}.\n" + (f"{HEADER_NOTE}\n" if header_note else "")) if profile["statutory"] else ""
    return (f"{note.strip()}\nReturn {{\"rows\": [...]}} with every table row " + ("whose item-name cell is fully visible" if name else "that is fully visible")
            + ", in printed order, one object per printed row: {" + (f'"n": "<{name} name as printed>", ' if name else "") + "\"<key>\": \"<printed value>\", ...}.\n"
            "Short keys for the " + ("amount " if name else "") + "columns:\n" + columns + "\n"
            "Every row object must contain ALL keys: " + ("\"n\" and every amount key (" if name else "every key (") + ", ".join(keys) + ") in this order. "
            "Write an empty string \"\" for a blank or '-' cell, \"0\" only if a 0 is printed; never skip a key and never write null. Never compute.\n"
            f"Example reply: {{\"rows\": [{{{example}}}]}}\n" + statutory
            + f"Rules (same as the schema): {plan[0] if plan else item['description']}\n" + profile["closing"])


def expand(rows, item, doc_type=RECEIPT, plan=None):
    """짧은 키 행 → 스키마 열 행(스키마 순서): 묻은 열의 빈칸·빠진 키는 열 종류가 ``zero``면 "0"(영수증 금액 열: 빈칸=0 규칙), 아니면
    None(세부내역서: 인쇄된 값만). ``plan``에 없어 묻지 않은 열은 그 배치의 채움 값(rowmajor ``_read_rows``와 같다), 스키마 밖 배치 열은 버린다.
    (행 목록, 모르는 키 수, 키가 빠진 행 수)."""
    profile, keys, unknown, missing, result = PROFILES[doc_type], short_keys(item, doc_type, plan), 0, 0, []
    asked = set(keys.values())
    blank = {column: ("0" if doctypes.kind(doc_type, column, rules.ITEM_TABLE) in profile["zero"] else None) if column in asked else plan[2]
             for column in item["items"]["properties"] if column != profile["name"]}
    for row in (row for row in rows if isinstance(row, dict)):
        missing += not set(keys) <= set(row)
        expanded = {**({profile["name"]: row.get("n")} if profile["name"] else {}), **blank}
        for key, value in row.items():
            if key in keys and keys[key] in blank and str(value if value is not None else "").strip():
                expanded[keys[key]] = str(value).strip()
            unknown += key not in keys and key != "n"
        result.append(expanded)
    return result, unknown, missing


def _name(row):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(row.get("항목") or ""))


def overlap(rows, part):
    """``part`` 앞쪽 k(≤TAIL)개 행의 이름이 ``rows`` 끝 k개와 모두 비슷한(difflib ≥ SIMILAR) 가장 큰 k: 띠가 겹쳐 두 번 읽은 행 수."""
    return next((k for k in range(min(TAIL, len(rows), len(part)), 0, -1)
                 if all(difflib.SequenceMatcher(None, _name(rows[len(rows) - k + j]), _name(part[j])).ratio() >= SIMILAR for j in range(k))), 0)


def last_total(rows):
    """합계 행은 마지막 것만 남긴 행 목록(띠마다 합계 행을 읽은 경우)."""
    last = max((i for i, row in enumerate(rows) if _name(row) == "합계"), default=-1)
    return [row for i, row in enumerate(rows) if _name(row) != "합계" or i == last]
