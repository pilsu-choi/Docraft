"""진료비영수증 문서 단위 인쇄 정합(``backend.print_register``)과 ``verify.read`` 연결(``PRINT_REGISTER``)."""

from backend import band, engine, latency, print_register, rules, verify

W, H, PITCH, TOP = 1000, 1400, 40, 300
NAMES = ["진찰료", "입원료", "식대", "투약및조제료", "주사료", "마취료", "처치및수술료", "검사료", "합계"]
T = len(NAMES) - 1
TRUE = {i: (f"{(i + 1) * 1100:,}", f"{(i + 1) * 3300:,}") for i in range(1, T - 1)}  # 인쇄된 값(첫 행·합계 바로 위 행은 비움)
TOTAL = tuple(f"{sum(int(v[c].replace(',', '')) for v in TRUE.values()):,}" for c in (0, 1))
FOUND = {"grid": [50, 150, 900, 750], "header": [50, 150, 900, 200], "first_row": [50, 205, 900, 225], "total": [50, 430, 900, 455]}
COLS = (400, 600)  # 본인부담금·공단부담금 열 x


def line(text, x0, y, width=80):
    return {"text": text, "bbox": [x0, y - 10, x0 + width, y + 10]}


def blocks(shift=0.0, merged=False, extra=()):
    """양식 이름 줄은 제자리, 금액 줄은 ``shift`` 행만큼 밀려 찍힌 쪽."""
    lines = [line(name, 100, TOP + PITCH * i) for i, name in enumerate(NAMES)]
    for i, values in [*TRUE.items(), (T, TOTAL)]:
        y = TOP + PITCH * (i + shift)
        lines += [line(f"{values[0]} {values[1]}", COLS[0], y, COLS[1] + 80 - COLS[0])] if merged else [line(v, x, y) for v, x in zip(values, COLS)]
    return [{"page": 1, "page_size": [W, H], "type": "table", "lines": [*lines, *extra]}]


def rows(read):
    """``read``: 행 → 그 행에 붙여 읽은 인쇄 값(본인부담금, 공단부담금)."""
    out = [{"항목": name, **dict.fromkeys(rules.ITEM_COLUMNS, "0")} for name in NAMES]
    for i, values in read.items():
        out[i].update(본인부담금=values[0], 공단부담금=values[1])
    return out


TRUTH = rows({**TRUE, T: TOTAL})
UP = rows({**{i - 1: v for i, v in TRUE.items()}, T: TOTAL})  # 반 행 위로 찍혀 VLM 이 한 행 위에 붙여 읽음
DOWN = rows({**{i + 1: v for i, v in TRUE.items()}, T: TOTAL})  # 반 행 아래로 찍혀 한 행 아래에 붙여 읽음


def amounts(table):
    return [(r["항목"], r["본인부담금"], r["공단부담금"]) for r in table]


def test_half_row_up_print_is_moved_back_to_the_form_rows():
    new, info = print_register.register(UP, blocks(-0.45), FOUND)
    assert info["reason"] == "적용" and -0.6 < info["c"] < -0.3
    assert amounts(new) == amounts(TRUTH)


def test_half_row_down_print_is_moved_back_to_the_form_rows():
    new, info = print_register.register(DOWN, blocks(0.45), FOUND)
    assert info["reason"] == "적용" and 0.3 < info["c"] < 0.6
    assert amounts(new) == amounts(TRUTH)


def test_normal_print_is_left_alone():
    new, info = print_register.register(TRUTH, blocks(0.0), FOUND)
    assert info["reason"] == "게이트: c 작음(정상 인쇄)" and new is TRUTH


def test_amounts_merged_into_one_line_box_are_split_by_character_position():
    new, info = print_register.register(UP, blocks(-0.45, merged=True), FOUND)
    assert info["reason"] == "적용" and amounts(new) == amounts(TRUTH)


def test_ambiguous_assignment_is_left_alone():
    # 금액 줄이 정확히 반 행 어긋나 c 와 c±1 이 같은 적합도로 다른 배정을 낸다
    page = blocks(0.0)
    page[0]["lines"] = [x if x["bbox"][0] < COLS[0] or TOP + PITCH * T - 10 == x["bbox"][1] else {**x, "bbox": [x["bbox"][0], x["bbox"][1] - PITCH / 2, x["bbox"][2], x["bbox"][3] - PITCH / 2]}
                        for x in page[0]["lines"]]
    new, info = print_register.register(UP, page, FOUND)
    assert info["reason"].startswith("모호") and new is UP


def test_occupied_target_cell_gives_up_the_whole_document():
    read = [dict(r) for r in UP]
    read[T - 2]["본인부담금"] = "999"  # 어느 인쇄 줄에도 없는 값이 도착 칸을 차지
    new, info = print_register.register(read, blocks(-0.45), FOUND)
    assert info["reason"] == "도착 칸 점유" and new is read


def test_text_left_of_the_item_grid_does_not_pull_the_name_anchors():
    # 표 왼쪽 결제 칸의 '합계' 글줄이 표 합계 행보다 0.7행 위에 있다(표 합계 이름은 OCR 이 놓침). 항목 격자 왼쪽 끝 오른쪽 상자만
    # 이름 앵커로 쓰지 않으면 이 글줄이 합계 앵커가 되어 정상 인쇄 문서 전체를 옮긴다(g25 SA2019123157794 유형)
    page = blocks(0.0, extra=[line("합계", 0, TOP + PITCH * (T - 0.7), 45)])
    page[0]["lines"] = [x for x in page[0]["lines"] if not (x["text"] == "합계" and x["bbox"][0] == 100)]
    assert print_register.register(TRUTH, page, {**FOUND, "grid": [0, *FOUND["grid"][1:]]})[1]["reason"] == "적용"  # 격자 한정이 없을 때
    new, info = print_register.register(TRUTH, page, FOUND)
    assert info["reason"] == "게이트: c 작음(정상 인쇄)" and new is TRUTH


def test_locate_reply_with_wrapped_grid_box_is_normalized():
    reply = {"item_grid": [FOUND["grid"]], "header": FOUND["header"], "first_row": FOUND["first_row"], "total": [FOUND["total"]]}
    new, info = print_register.register(UP, blocks(-0.45), band.boxes(reply))
    assert info["reason"] == "적용" and amounts(new) == amounts(TRUTH)


def test_total_read_on_the_row_above_is_returned_once_and_stays_put_in_rules_apply():
    # 같은 밀림으로 합계 금액까지 바로 위 행에 붙여 읽은 경우: 합계 줄을 찾으려 _misplaced_total 을 먼저 보고, 뒤의 rules.apply 와 겹치지 않는다
    read = [dict(r) for r in UP]
    read[T - 1].update(본인부담금=TOTAL[0], 공단부담금=TOTAL[1])
    read[T].update(본인부담금="0", 공단부담금="0")
    new, info = print_register.register(read, blocks(-0.45), FOUND)
    assert info["reason"] == "적용" and amounts(new) == amounts(TRUTH)
    after = rules.apply("진료비영수증", {rules.ITEM_TABLE: new}, [])[rules.ITEM_TABLE]
    assert [(r["항목"], r["본인부담금"]) for r in after][-2:] == [(NAMES[T - 1], "0"), ("합계", TOTAL[0].replace(",", ""))]


def _read(monkeypatch, page, enabled=True):
    seen = {}
    monkeypatch.setattr(verify, "parse", lambda *a, **k: ("md", page))
    monkeypatch.setattr(engine, "ai_settings", lambda: {"table_extract": "asis", "print_register": enabled, "table_recheck_ratio": 0.6})

    def extract(schema, blocks, source=None, located=None, **kwargs):
        seen["located"] = located is not None
        if located is not None:
            located.update(FOUND)
        return {rules.ITEM_TABLE: [dict(r) for r in UP]}, {}
    monkeypatch.setattr(engine, "extract", extract)
    monkeypatch.setattr(rules, "apply", lambda doc_type, result, blocks: seen.setdefault("applied", result))
    with latency.track() as stats:
        verify.read("scan.png", "진료비영수증", auto_reprocess=False)
    return seen, stats


def test_read_registers_an_upright_one_page_receipt_before_rules(monkeypatch):
    seen, stats = _read(monkeypatch, blocks(-0.45))
    assert amounts(seen["applied"][rules.ITEM_TABLE]) == amounts(TRUTH)
    assert stats["print_register"]["reason"] == "적용"


def test_read_skips_a_turned_page_and_the_disabled_setting(monkeypatch):
    turned = [{**blocks(-0.45)[0], "orientation": 90}]
    seen, stats = _read(monkeypatch, turned)
    assert amounts(seen["applied"][rules.ITEM_TABLE]) == amounts(UP) and "print_register" not in stats
    seen, stats = _read(monkeypatch, blocks(-0.45), enabled=False)
    assert not seen["located"] and amounts(seen["applied"][rules.ITEM_TABLE]) == amounts(UP)
