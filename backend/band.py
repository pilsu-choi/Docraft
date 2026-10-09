"""``TABLE_EXTRACT=band``: 긴 항목 표(진료비영수증)를 위치부터 찾아 가로 띠로 잘라 읽는 데 쓰는 순수 함수.

모델 호출은 ``engine``이 한다. 여기는 위치 응답 후처리(``boxes``), 띠 자르기(``clips``), 금액산정 블록 크롭(``summary_clip``),
짧은 키 읽기 형식(``prompt``·``expand``), 띠 겹침 판정(``overlap``)만 둔다. 좌표는 모두 쪽 크기를 1000으로 본 값이다."""

import difflib
import re

from . import doctypes, rules

BANDS, OVERLAP, TAIL, SIMILAR = 3, 0.10, 8, 0.7
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
SUMMARY_PROMPT = ("This image is the 금액산정내용 (payment calculation) block of a Korean medical receipt. Extract these fields only:\nSchema:\n{schema}\n"
                  "Copy the printed digits only, never compute; use null for a field whose label or value is not printed.")


def _box(value):
    """``[[x1, y1, x2, y2]]`` 로 감싼 응답도 받는다. 숫자 네 개가 아니면 None."""
    value = value[0] if isinstance(value, list) and len(value) == 1 and isinstance(value[0], list) else value
    return list(value) if isinstance(value, list) and len(value) == 4 and all(isinstance(x, (int, float)) for x in value) else None


def boxes(reply):
    """위치 응답 → {grid, header, first_row, total[, summary]} 또는 None(표 상자가 모자라거나 순서가 어긋남).
    금액산정 상자가 항목 표 옆에서 가로로 겹치면 표의 오른쪽 끝을 그 왼쪽에서 자르고, 높이 8% 미만 상자는 금액산정 블록이 아니라 버린다."""
    found = {key: _box(value) for key, value in reply.items()} if isinstance(reply, dict) else {}
    if not all(found.get(key) for key in ("item_grid", "header", "first_row", "total")):
        return None
    result = {"grid": found["item_grid"], **{key: found[key] for key in ("header", "first_row", "total")}}
    grid, summary = result["grid"], found.get("summary")
    if not (result["header"][1] < result["first_row"][1] < result["total"][3]) or grid[0] >= grid[2]:
        return None
    if summary and summary[2] > summary[0] and summary[3] - summary[1] >= 80:
        result["summary"] = summary
        if grid[0] + 0.4 * (grid[2] - grid[0]) < summary[0] < grid[2]:
            grid[2] = summary[0]
    return result


def summary_clip(found):
    """금액산정 블록 크롭(쪽 비율 [x1, y1, x2, y2]). 표 옆 패널이면 라벨 열을 담게 왼쪽을 넓히고 세로는 표 높이까지, 아니면 사방을 조금 넓힌다."""
    (x1, y1, x2, y2), grid = found["summary"], found["grid"]
    beside = x1 > grid[0] + 0.4 * (grid[2] - grid[0])
    box = [x1 - (120 if beside else 40), min(y1, grid[1]) if beside else y1 - 30, x2 + 40, max(y2, grid[3]) if beside else y2 + 30]
    return [min(max(value, 0), 1000) / 1000 for value in box]


def clips(found):
    """띠 읽기용 크롭 목록(쪽 비율). 표 머리글 위쪽부터 마지막 합계 행까지를 BANDS 등분해 OVERLAP 만큼 겹치게 자른다.
    첫 띠는 머리글째, 나머지 띠는 머리글 띠(첫 데이터 행 제외)가 첫 이미지로 붙는다."""
    x1, x2 = max(0, found["grid"][0] - 20), min(1000, found["grid"][2] + 20)
    head, first = max(0, found["header"][1] - 10), found["first_row"][1]
    top, bottom = first, min(1000, found["total"][3] + 15)
    height = bottom - top
    result = []
    for i in range(BANDS):
        strip = [x1, head if i == 0 else max(top, top + height * i / BANDS - OVERLAP * height), x2, min(bottom, top + height * (i + 1) / BANDS + OVERLAP * height)]
        result.append([[value / 1000 for value in box] for box in ([strip] if i == 0 else [[x1, head, x2, first], strip])])
    return result


def short_keys(item):
    """스키마 항목내역 속성(항목 제외)을 순서대로 a, b, c… 에 대응한 {짧은 키: 열 이름}. 출력 토큰을 줄인다."""
    return {chr(97 + i): key for i, key in enumerate(key for key in item["items"]["properties"] if key != "항목")}


def prompt(item, note):
    """띠 읽기 프롬프트: 모든 행에 이름(n)과 모든 금액 열 키를 스키마 순서로 쓰게 한다. ``note``는 이미지 구성 안내."""
    props, keys = item["items"]["properties"], short_keys(item)
    columns = "\n".join(f'  "{key}" = {column}: {props[column]["description"].removesuffix(doctypes.RECEIPT_HINT).strip()}' for key, column in keys.items())
    example = ", ".join(f'"{key}": "{value}"' for key, value in zip(keys, ["1,200", "4,800"] + [""] * len(keys)))
    return (f"{note.strip()}\nReturn {{\"rows\": [...]}} with every table row whose item-name cell is fully visible, in printed order, one object per printed row: "
            "{\"n\": \"<항목 name as printed>\", \"<key>\": \"<printed value>\", ...}.\nShort keys for the amount columns:\n" + columns + "\n"
            "Every row object must contain ALL keys: \"n\" and every amount key (" + ", ".join(keys) + ") in this order. Write an empty string \"\" for a blank or '-' cell, "
            "\"0\" only if a 0 is printed; never skip a key and never write null. Never compute.\n"
            f"Example reply: {{\"rows\": [{{\"n\": \"검사료\", {example}}}]}}\n"
            f"항목 naming rule: {props['항목']['description']}\n"
            "Reading aid: printed names on this statutory form usually come from this list: " + ", ".join(rules.ITEM_ORDER) + ". Use it to read blurred or partial names; "
            "still output only rows actually printed, never add a row because it is in the list; names not in the list are written as printed.\n"
            f"The form has one of 5 column layouts: {LAYOUTS}.\n"
            f"Rules (same as the schema): {item['description']}\n"
            "Skip rows whose name is cut off at the top or bottom edge. Include the final 합계 row if visible. Never return header rows. "
            "Copy the printed digits only, never compute or infer a value. A blank cell is 0 (per the schema).")


def expand(rows, item):
    """짧은 키 행 → 스키마 열 행: 빈칸·빠진 금액 열은 "0"(빈칸=0 규칙). (행 목록, 모르는 키 수, 키가 빠진 행 수)."""
    keys, unknown, missing, result = short_keys(item), 0, 0, []
    for row in (row for row in rows if isinstance(row, dict)):
        missing += not set(keys) <= set(row)
        expanded = {"항목": row.get("n"), **dict.fromkeys(keys.values(), "0")}
        for key, value in row.items():
            if key in keys and str(value if value is not None else "").strip():
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
