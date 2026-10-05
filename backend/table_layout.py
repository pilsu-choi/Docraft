"""rowmajor 표 추출(``TABLE_EXTRACT=rowmajor``)에서 모델에 줄 열 배치를 OCR 블록으로 정한다(규칙 기반, LLM 호출 없음).

rowmajor는 행마다 값 배열만 받으므로 열 자리가 문서에 인쇄된 열과 다르면 합집합에만 있는 자리가 이웃 값을 가로챈다.
그래서 유형·표마다(``rulesets/table_layouts.yaml``의 ``tables``) 두 방법 중 하나로 인쇄 열을 정한다.

- layout: 표 셀 낱말로 진료비영수증 양식 번호(1~5)를 판별해 그 양식의 인쇄 열과 열 설명을 준다.
- header: 표 블록 OCR 줄(글자+bbox, 줄 상자가 없으면 셀)에서 머리글 낱말을 찾아 x 순으로 정렬한 열을 준다.
  머리글을 못 읽으면 셀 값 꼴(날짜·코드·글자·금액·수)을 yaml에 적은 인쇄 순서에 맞춰 정한다(value, ``shaped_columns``).

근거가 약한 곳은 추측하지 않고 알린다(``planned``의 알림): 근거 없는 열은 넣지 않고, 이름을 정하지 못한 열은 읽고 버린다.

정하지 못하면 ``plan``이 None을 돌려주고 engine이 합집합 열 순서로 읽는다. ``planned``는 출처와 실패 사유도 준다.
"""

import re
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from statistics import median

import yaml

_DATA = yaml.safe_load((Path(__file__).with_name("rulesets") / "table_layouts.yaml").read_text(encoding="utf-8"))
METHODS = _DATA["tables"]
NOTE = _DATA["header"]["note"]
WORDS = _DATA["header"]["words"]
ENDINGS = _DATA["header"]["endings"]
SUBS = set(_DATA["header"]["subs"])
KEYS = {concept: tuple(keys) for concept, keys in _DATA["header"]["keys"].items()}
SINGLE = _DATA["header"]["single"]
OPTIONAL = set(_DATA["header"]["optional"])
PAIRS = {key: set(group) - {key} for group in _DATA["header"]["pairs"] for key in group}
SPANS = {concept: (span["keys"], re.compile(span["value"])) for concept, span in _DATA["header"]["spans"].items()}
CODE_WORDS = _DATA["header"]["code_words"]
SHAPES = _DATA["header"]["shapes"]
RUNS = {name: {int(width): keys for width, keys in run.items()} for name, run in _DATA["runs"].items()}  # 같은 꼴 열 묶음 수 → 열
COUNTS = RUNS["counts"]  # 단가와 총액 사이 곱하는 열 수 → 열(rules도 쓴다)
VALUE = _DATA["value"]
FILL = _DATA["layout"]["fill"]
FORMS = _DATA["layout"]["forms"]

_OUT = re.compile(r"진[료르토]{2}\W*(이외|이의|이와|외)|(?:^|\s)\W?이[외의와](?:\s|$)")  # '선택진료료 외·이외'(OCR 오독, 칸이 갈린 '이외' 포함)
_SEL = re.compile(r"선[택착]\W*진[료르토]{2}")  # '선택진료 신청'(신청란)은 '진료' 뒤에 '료'가 없어 빠진다
_COVERED = re.compile(r"요양급여\W*①\W*[+＋]\W*②")  # 양식 1 머리글 '요양급여(①+②)'. 다른 양식 머리글에는 없다


def receipt_form(blocks):
    """표 블록 셀 낱말로 정한 진료비영수증 양식 번호. 요양급여(①+②) → 선택진료료외 → 선택진료료 → 본인부담 열 순서로 본다.
    선택진료료만 보이면 양식 3인지 '외' 칸을 OCR이 놓친 양식 4인지 가를 수 없어 None이다."""
    text = " ".join(dict.fromkeys(str(cell) for block in blocks if block.get("type") == "table"
                                  for row in block.get("rows") or [] for cell in row))
    if _COVERED.search(text):
        return 1
    if _OUT.search(text):
        return 4 if _SEL.search(_OUT.sub("", text)) else 5
    if _SEL.search(text):
        return None
    return 2 if "본인부담" in text.replace(" ", "") else None


def _distance(a, b):
    if abs(len(a) - len(b)) > 1:  # 거리 1 이하만 쓰므로 길이가 둘 이상 다르면 계산하지 않는다
        return 2
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


def _concepts(text):
    """가장 가까운 열 개념들(동률이면 여럿)과 편집거리. 두 글자 이상이고 거리 1 이하만 받는다. 괄호 안('횟수(총투)')은 부가 설명이다.
    끝말(``ENDINGS``)로 끝나는 낱말은 앞말과 상관없이 그 개념이다('처방코드'를 '서발코드'로 읽어도 코드 열)."""
    text = re.sub(r"\W", "", re.sub(r"\(.*?\)", "", text))
    if ending := next((concept for word, concept in ENDINGS.items() if len(text) > len(word) and text.endswith(word)), None):
        return [ending], 0
    near = {concept: min(_distance(text, word) for word, c in WORDS.items() if c == concept) for concept in set(WORDS.values())}
    best = min(near.values())
    return ([concept for concept, d in near.items() if d == best], best) if best <= 1 and len(text) >= 2 else ([], best)


@lru_cache(maxsize=4096)
def _segment(text):
    """띄어쓰기 없이 붙은 머리글('수량횟수일수', OCR이 한 줄로 읽은 '본인부당금공단부담금')을 머리글 낱말 여럿으로 나눈다.
    네 글자 이상 조각은 한 글자 오독까지 받는다. 다 못 나누면 None."""
    if not text:
        return ()
    for size in range(len(text), 1, -1):
        piece = text[:size]
        if (piece in WORDS or size >= 4 and _concepts(piece)[0]) and (rest := _segment(text[size:])) is not None:
            return (piece, *rest)
    return None


def _words(text):
    """줄 글자를 머리글 낱말 단위로: 떨어져 쓴 낱말('급여 구분', 'EDI 코드')은 합치고 붙어 쓴 낱말은 나눈다."""
    parts, out, i = text.split() or [text], [], 0
    while i < len(parts):
        k = next((k for k in (3, 2) if "".join(parts[i:i + k]) in WORDS), 1)
        word, i = "".join(parts[i:i + k]), i + k
        bare = re.sub(r"\W", "", word)
        split = _segment(bare) or () if len(bare) <= 16 and not re.search(r"\d", bare) else ()
        out += split if not _concepts(word)[0] and len(split) > 1 else [word]
    return out


def _cell_lines(block, at):
    """줄 상자가 없는 표 블록의 셀을 줄로: x는 열 번호, y는 행 번호(``at``은 블록 차례, 표끼리 겹치지 않게 띄운다).
    병합 칸이 옆 칸에 같은 글자로 되풀이되면 한 줄로 합쳐 그 칸들의 가운데에 둔다."""
    lines = []
    for r, row in enumerate(block.get("rows") or []):
        y = (at * 1000 + r) * 40
        for c, cell in enumerate(row):
            text = str(cell or "").strip()
            if text and (c == 0 or str(row[c - 1] or "").strip() != text or not re.search(r"[가-힣]", text)):
                end = next((k for k in range(c + 1, len(row)) if str(row[k] or "").strip() != text or not re.search(r"[가-힣]", text)), len(row))
                lines.append({"text": text, "bbox": [c * 100, y, end * 100 - 10, y + 30]})
    return lines


def _lines(blocks):
    """표 블록 OCR 줄(바로 선 페이지 좌표). 돌아간 페이지의 블록(``orientation``)은 좌표가 원본 기준이라 돌려서 본다.
    줄 상자가 없는 블록은 셀로 줄을 만든다(``_cell_lines``).
    두 줄로 갈려 인쇄된 머리글 낱말('전액'/'본인부담')은 위아래로 붙고 합친 글자가 머리글 낱말이면 한 줄로 합친다."""
    from .parsers import unturn  # parsers → engine → table_layout 순환을 피한다
    lines = []
    for at, block in enumerate(blocks):
        if block.get("type") != "table":
            continue
        if block.get("orientation"):
            block = unturn([block], 360 - block["orientation"])[0]
        lines += ([{"text": line["text"], "bbox": list(line["bbox"])} for line in block.get("lines") or [] if line.get("bbox")]
                  or _cell_lines(block, at))
    short = [line for line in lines if len(re.sub(r"\W", "", line["text"])) <= 6]
    for top in short:
        x0, y0, x1, y1 = top["bbox"]
        below = next((line for line in short if line is not top and line["text"] and 0 <= line["bbox"][1] - y1 <= (y1 - y0)
                      and x0 <= (line["bbox"][0] + line["bbox"][2]) / 2 <= x1
                      and re.sub(r"\W", "", top["text"] + line["text"]) in WORDS), None)
        if top["text"] and below:
            top["text"], top["bbox"] = top["text"] + below["text"], [min(x0, below["bbox"][0]), y0, max(x1, below["bbox"][2]), below["bbox"][3]]
            below["text"] = ""
    return [line for line in lines if line["text"]]


def _tokens(lines):
    """줄을 머리글 낱말로 쪼갠 {text, x, y, h}. 한 줄에 낱말이 여럿이면 글자 수로 줄 폭을 나눠 x를 정한다."""
    out = []
    for line in lines:
        x0, y0, x1, y1 = line["bbox"]
        words = _words(line["text"])
        total, at = sum(map(len, words)) or 1, 0
        for word in words:
            out.append({"text": word, "x": x0 + (x1 - x0) * (at + len(word) / 2) / total, "y": (y0 + y1) / 2, "h": y1 - y0})
            at += len(word)
    return out


def _spans(concept, x, head, lines):
    """머리글 낱말 하나 아래 칸이 값을 둘씩 싣는지('일자' 칸의 '시작 ~ 종료'): 그 열 x 범위(이웃 머리글과의 가운데까지)의
    본문 줄을 행(y)으로 묶어, ``SPANS`` 값 꼴을 둘 이상 담은 행이 둘 이상(값 있는 행이 하나면 그 행)이면 그렇다 — 기간을 찍는
    행이 일부뿐인 서식도 그 칸은 두 값을 싣는다. 범위 표시(~·-)로 시작하거나 끝나는 줄은 한 칸에 두 줄로 쌓인 범위
    ('2021-08-19' / '~2021-08-21')라 이웃 줄과 한 행이다."""
    keys, value = SPANS[concept]
    xs = sorted(t["x"] for t in head)
    at = xs.index(x)
    lo, hi = (xs[at - 1] + x) / 2 if at else float("-inf"), (xs[at + 1] + x) / 2 if at + 1 < len(xs) else float("inf")
    top = min(t["y"] for t in head)
    rows = []  # 본문 행: [y, 글자]
    for line in sorted(lines, key=lambda line: line["bbox"][1] + line["bbox"][3]):
        x0, y0, x1, y1 = line["bbox"]
        if (y0 + y1) / 2 > top and lo <= (x0 + x1) / 2 <= hi:
            if rows and ((y0 + y1) / 2 - rows[-1][0] <= (y1 - y0) * 0.6 or re.match(r"\s*[~∼-]", line["text"])
                         or re.search(r"[~∼-]\s*$", rows[-1][1])):
                rows[-1][1] += " " + line["text"]
            else:
                rows.append([(y0 + y1) / 2, line["text"]])
    counts = [n for _, text in rows if (n := len(value.findall(text)))]
    return keys if sum(n >= 2 for n in counts) >= min(2, len(counts) or 1) else None


def printed_columns(blocks, union, min_columns=4):
    """머리글 줄에서 읽은 열을 인쇄 순서로 둔 합집합 열의 부분열 → 같은 개념의 열이 여럿일 때 그 열의 머리글 글자
    ('수가코드'·'청구코드', '단가'·'금액'. 열 설명만으로는 어느 쪽인지 가를 수 없다). 그 밖의 열은 None.
    머리글 줄에서 열을 ``min_columns``개 미만으로 읽으면 None. 자세한 규칙은 ``_header``."""
    return _header(blocks, union, min_columns)[0]


def header_positions(blocks, union):
    """``(머리글에서 읽은 열 → 머리글 낱말의 x(바로 선 페이지 좌표), 한 칸에 같은 개념 낱말이 두 줄로 쌓인 열)``. 머리글을 못
    읽으면 빈 dict·빈 집합. ``rules``가 값이 어느 열 아래 인쇄됐는지, 한 칸에 두 값('AU211'/'{AIAU211}')이 찍혔는지 볼 때 쓴다."""
    return _header(blocks, union)[1::2]


def _header(blocks, union, min_columns=4):
    """``(인쇄 열 → 머리글 글자 | None, 읽은 열 → x, 실패 사유 | None, 두 줄로 쌓인 같은 개념 낱말의 열, 알림)``.

    머리글 줄은 열 개념 낱말이 ``min_columns``개 이상인 첫 줄이다. 위아래 두 줄 안(줄 높이 3배 안, 사이에 숫자 줄이 없을 때)의
    낱말도 그 x에 다른 머리글 낱말이 없고 정확히 읽혔거나 머리글 낱말이 둘 이상인 줄에 있으면 열이다 — 칸 높이가 다른 머리글('총액'이
    두 줄 칸 가운데). 같은 개념 낱말이 같은 x에 쌓였으면('코드' 아래 '{수가코드}') 한 칸, 한 열이다. 묶음 제목 아래 하위 열(``SUBS``)은
    늘 받는다. 곱하는 열이 둘이면 횟수·일수다(``COUNTS``, '총투'·'일수'). 코드 열이 둘이면 ``code_keys``로 가른다.

    못 읽은 열은 그 자리에 열이 있다는 근거가 있을 때만 넣는다 — 머리글 낱말이 다 읽혔는데 열을 끼우면 이웃 값이 그 자리로 간다.
    - 필수 열(``OPTIONAL`` 밖)은 합집합 순서의 제자리 양옆 머리글 사이에 그 열 낱말과 가까운 읽지 못한 글자(조각을 이어 읽는다,
      ``_near``)가 있거나 그 사이 본문에 그 열 값 꼴(``SHAPES``) 칸이 세 행 이상·그 둘레 행의 절반 이상 찍혔을 때 넣는다. 읽지 못한 글자나 넓은
      간격(머리글 간격 중앙값의 2.5배)만 있고 근거가 없으면 넣지 않고 ``column_unplaced``로 알린다.
    - 짝 열(``PAIRS``)은 짝을 근거로 넣었거나(열 수를 세지 못했다) 짝의 머리글 칸에 그 열 낱말과 겹치는 읽지 못한 글자가 있으면
      짝 옆에 함께 둔다. 나머지 선택 열은 서식에 없다고 본다.
    한 칸이 두 열의 값을 싣는 개념(``SPANS``, '일자' 한 칸의 진료기간)은 본문이 그렇게 찍혔으면 두 열을 함께 묻는다.
    낱말 하나뿐인 개념은 ``SINGLE``(낱말이나 개념 → 열)을 따른다. 다만 그 열을 다른 개념이 차지하면 따르지 않는다.
    알림은 ``(code, 열)``: column_unplaced(근거가 약해 넣지 않은 필수 열), code_order(코드 두 열을 인쇄 순서로만 갈랐다)."""
    lines = _lines(blocks)
    if not lines:
        return None, {}, "no_table_text", set(), []
    every = [{**t, "hits": hits, "exact": d == 0} for t in _tokens(lines) for hits, d in [_concepts(t["text"])]]
    exact = {t["hits"][0] for t in every if t["exact"] and len(t["hits"]) == 1}
    for t in every:  # 두 개념과 같은 거리의 오독('임수' = 일수·횟수)은 이미 정확히 읽힌 개념을 뺀 쪽이다
        rest = set(t["hits"]) - exact
        t["c"] = t["hits"][0] if len(t["hits"]) == 1 else rest.pop() if len(rest) == 1 else None
    unread, tokens = [t for t in every if not t["c"] and re.search(r"[가-힣A-Za-z]", t["text"])], [t for t in every if t["c"]]
    if not tokens:
        return None, {}, "no_header_words", set(), []
    height = median(t["h"] for t in tokens)
    rows = []  # y로 묶은 줄(위에서 아래)
    for t in sorted(tokens, key=lambda t: t["y"]):
        if rows and t["y"] - rows[-1][-1]["y"] <= height * 0.6:
            rows[-1].append(t)
        else:
            rows.append([t])
    head = next((i for i, row in enumerate(rows) if len({t["c"] for t in row}) >= min_columns), None)
    if head is None:
        return None, {}, "few_header_columns", set(), []
    picked, y = list(rows[head]), rows[head][0]["y"]
    xs = sorted(t["x"] for t in picked)
    reach = median(b - a for a, b in zip(xs, xs[1:])) / 2 if len(xs) > 1 else height
    for row in rows[max(head - 2, 0):head][::-1] + rows[head + 1:head + 3]:  # 위 줄부터(아래 줄의 왼쪽 글자는 본문 무리 제목일 수 있다)
        lo, hi = sorted((row[0]["y"], y))
        if hi - lo <= height * 3 and not any(lo + height * 0.6 < (line["bbox"][1] + line["bbox"][3]) / 2 < hi - height * 0.6
                                             and re.search(r"\d", line["text"]) for line in lines):  # 사이에 값 줄이 끼면 다른 표 머리글이다
            picked += [t for t in row if t["c"] in SUBS or (t["exact"] or len(row) > 1) and all(abs(t["x"] - p["x"]) > reach for p in picked)
                       or any(p["c"] == t["c"] and abs(p["x"] - t["x"]) < height for p in picked)]  # 쌓인 낱말은 아래에서 한 열로
    picked.sort(key=lambda t: t["y"])  # 같은 개념 낱말이 같은 x에 쌓였으면('코드' 아래 '{수가코드}') 한 칸, 한 열이다
    stacked = {p["x"] for i, t in enumerate(picked) for p in picked[:i] if p["c"] == t["c"] and abs(p["x"] - t["x"]) < height}
    bottom = picked[-1]["y"] + height * 0.6
    cells = sorted(({"x": (x0 + x1) / 2, "y": (y0 + y1) / 2, "text": line["text"]} for line in lines  # 머리글 아래 본문 칸(OCR 줄)
                    for x0, y0, x1, y1 in [line["bbox"]] if (y0 + y1) / 2 > bottom), key=lambda cell: cell["y"])
    picked = sorted((t for i, t in enumerate(picked) if not any(p["c"] == t["c"] and abs(p["x"] - t["x"]) < height for p in picked[:i])),
                    key=lambda t: t["x"])
    if SUBS & {t["c"] for t in picked}:
        picked = [t for t in picked if t["c"] != "급여"]  # 하위 열이 있으면 급여는 묶음 제목이다
    concepts = [t["c"] for t in picked]
    band = [t for t in unread  # 머리글 줄의 읽지 못한 글자: x가 가장 가까운 머리글 낱말과 같은 줄에 있다
            if abs(t["y"] - min(picked, key=lambda p: abs(p["x"] - t["x"]))["y"]) <= height * 0.6]
    maybe = [hit for t in band for hit in t["hits"]]  # 두 개념 사이 오독('총맥' = 총액·총투)
    seen, columns, at, words, raw = {}, [], {}, {}, {}
    for t in picked:
        concept, word = t["c"], re.sub(r"\W", "", t["text"])
        n = seen[concept] = seen.get(concept, 0) + 1
        once = concepts.count(concept) == 1
        single = SINGLE.get(word, SINGLE.get(concept))
        if single in {KEYS[other][0] for other in [*concepts, *maybe] if other != concept}:
            single = None
        keys = ((once and concept in SPANS and _spans(concept, t["x"], picked, lines)) or
                [single if once and single else KEYS[concept][n - 1] if n <= len(KEYS[concept]) else None])
        for key in keys:
            if key in union and key not in columns:
                columns.append(key)
                at[key], raw[key] = t["x"], word
                if len(KEYS[concept]) > 1 and not once:  # 한 개념의 열이 여럿이면(코드 둘·단가와 금액) 머리글 글자를 남긴다
                    words[key] = word if word in WORDS else None
    if len(columns) < min_columns:
        return None, {}, "few_header_columns", set(), []
    poorly = any(t["hits"] and set(t["hits"]) & {"횟수", "일수", "투여량"} for t in unread)  # 곱하는 열 머리글을 다 읽지 못했다
    counts = [key for key in columns if key in COUNTS[3]]
    names = dict(zip(counts, COUNTS[2])) if len(counts) == 2 and counts != COUNTS[2] and not poorly else {}  # 곱하는 두 열은 횟수·일수
    flags = []
    codes = sorted(("원내코드", "EDI코드"), key=lambda key: at.get(key, 0))
    if set(codes) <= set(at) and at[codes[0]] != at[codes[1]]:  # 코드 두 열: 값 꼴·머리글 낱말로 가른다(인쇄 순서 가정을 하지 않는다)
        under = [[cell["text"] for cell in cells if min(at.values(), key=lambda x: abs(x - cell["x"])) == at[key]] for key in codes]
        keys, assumed = code_keys([raw[key] for key in codes], [_edi_ratio(values) for values in under])
        names |= dict(zip(codes, keys))
        flags += [("code_order", "EDI코드")] * assumed
    columns = [names.get(key, key) for key in columns]
    at, words = ({names.get(key, key): value for key, value in found.items()} for found in (at, words))
    read, xs = set(columns), sorted(at.values())
    wide = median(b - a for a, b in zip(xs, xs[1:])) * 2.5

    def unreadable(key, pair):
        """짝 열 머리글 칸의 key 쪽 절반(이웃 머리글과의 가운데까지)에 key 개념 낱말과 두 글자 이상 겹치는, 머리글 낱말로
        읽지 못한 글자가 있다('단민부금' = 본인부담금 오독)."""
        i = xs.index(at[pair])
        left = union.index(key) < union.index(pair)
        lo = (xs[i - 1] + xs[i]) / 2 if left and i else float("-inf") if left else xs[i]
        hi = xs[i] if left else (xs[i] + xs[i + 1]) / 2 if i + 1 < len(xs) else float("inf")
        own = [word for word, concept in WORDS.items() if key in KEYS[concept]]
        return any(lo <= t["x"] <= hi and any(len(set(t["text"]) & set(word)) >= 2 for word in own) for t in band if len(t["text"]) >= 2)

    def evidence(key, i):
        """columns[i] 자리 양옆 머리글(x를 아는 열) 사이에 key 열이 인쇄됐다는 ``(근거, 실마리)``. 근거는 사이의 읽지 못한 머리글
        글자가 key 낱말과 가깝거나(``_near``) 본문 행이 양옆 열 칸 말고도 key 값 꼴 칸을 하나 더 싣는 것(``extra``), 실마리는
        읽지 못한 글자·넓은 간격·근거에 못 미치는 본문 칸이다."""
        lo = max((at[other] for other in columns[:i] if other in at), default=float("-inf"))
        hi = min((at[other] for other in columns[i:] if other in at), default=float("inf"))
        near = [t for t in band if lo < t["x"] < hi]
        text = re.sub(r"\W", "", "".join(t["text"] for t in sorted(near, key=lambda t: (round(t["y"] / height), t["x"]))))
        own = {concept for concept, keys in KEYS.items() if key in keys}
        named = any(own & set(t["hits"]) for t in near) or any(_near(text, word) for word, concept in WORDS.items() if concept in own)

        rows = []  # 양옆 머리글 둘레(머리글 간격 절반까지)의 본문 칸을 y로 묶은 행. 좁은 띠라 기울어진 스캔에서도 행이 갈린다
        for cell in (cell for cell in cells if lo - reach < cell["x"] < hi + reach):
            if rows and cell["y"] - rows[-1][-1]["y"] <= height * 0.6:
                rows[-1].append(cell)
            else:
                rows.append([cell])

        family = _family(SHAPES[key])
        left, right = ({_family(SHAPES[other]) for other in side[-1:] if other in at} == {family}
                       for side in ([other for other in columns[:i] if other in at], [other for other in columns[i:] if other in at][:1]))

        def extra(row):  # 사이에 key 값 꼴 칸이 있다. 이웃 열과 값 꼴이 같으면 그 쪽 끝 칸은 이웃 열 값이 밀려 찍힌 것일 수 있어 뺀다
            row = sorted(row, key=lambda cell: cell["x"])
            return any(lo + reach / 2 < cell["x"] < hi - reach / 2 and _family(_shape(cell["text"])) == family
                       and not (left and j == 0 or right and j == len(row) - 1) for j, cell in enumerate(row))
        shown = sum(map(extra, rows))
        return named or shown >= max(3, len(rows) / 2), bool(near or shown) or wide < hi - lo < float("inf")

    for key in sorted((key for key in union if key not in columns), key=lambda key: key in OPTIONAL):  # 못 읽은 필수 열 먼저
        pair = next((other for other in columns if other in PAIRS.get(key, ()) and (other not in read or unreadable(key, other))),
                    None) if key in OPTIONAL else None
        if pair is not None:
            i = columns.index(pair)
            columns.insert(i if union.index(key) < union.index(pair) else i + 1, key)
        elif key not in OPTIONAL:
            before = [columns.index(other) for other in union[:union.index(key)] if other in columns]
            # 제자리: 합집합 순서로 바로 앞 열 뒤부터, 앞 열이 모두 인쇄된 뒤까지 가운데 근거가 있는 첫 자리
            found = [(i, *evidence(key, i)) for i in range(before[-1] + 1 if before else 0, max(before, default=-1) + 2)]
            if (i := next((i for i, sure, _ in found if sure), None)) is not None:
                columns.insert(i, key)
            elif any(hint for _, _, hint in found):
                flags.append(("column_unplaced", key))
    named = None not in words.values() and len(set(words.values())) == len(words)  # 오독했거나 같은 글자('금액'·'금액')면 못 가른다
    return ({key: words.get(key) if named else None for key in columns}, at, None, {key for key in columns if at.get(key) in stacked},
            flags)


def _near(text, word):
    """``text``(읽지 못한 머리글 조각을 이은 글자)에 머리글 낱말 ``word``가 있다. 세 글자 이상 낱말은 그 안 어디서든 한 글자
    오독·빠짐·더함까지('ED코드'의 EDI), 두 글자 낱말은 글자 전체가 한 글자 차이일 때만('총', '함'+'목') 받는다 — 두 글자 낱말을
    긴 글자 안에서 찾으면 아무 글자에나 걸린다('영수증'의 '영수' = 횟수)."""
    if len(word) <= 2:
        return word in text or _distance(text, word) <= 1
    return any(_distance(text[i:i + n], word) <= 1 for n in (len(word) - 1, len(word), len(word) + 1) for i in range(len(text) - n + 1))


# 날짜: 구분자 있는 꼴('2023-03-03'·'23.3.3')과 붙여 쓴 꼴('191225'·'20191228', 달·날이 맞을 때만 — 붙여 쓴 금액·코드와 가른다)
_DATE = re.compile(r"(?:19|20)?\d{2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}"
                   r"|(?<!\d)(?:19|20)?\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?!\d)")
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_CODE = re.compile(r"[{(\[]?[A-Za-z0-9][A-Za-z0-9-]{3,11}[})\]]?")
_CLASS = re.compile(r"(?:비|선별)?급여|급|비")
EDI = re.compile(r"[A-Z]{1,2}\d{3,4}[A-Z0-9]{0,3}|\d{9}")  # EDI 수가코드 꼴: 행위·치료재료(AA157·MX122S1·N0021001), 약가(9자리)


def _shape(text):
    """칸 값의 꼴: date(기간이면 period)·code·class(급여구분)·number·text. 빈칸·기호는 None."""
    text = str(text or "").strip()
    if len(dates := _DATE.findall(text)) >= 1 and len(re.findall(r"[가-힣A-Za-z]", text)) <= 1:
        return "period" if len(dates) >= 2 or re.search(r"[~∼]", text) else "date"
    if NUMBER.fullmatch(text):
        digits = text.replace(",", "")
        return "code" if "," not in text and "." not in text and (len(digits) >= 8 or len(digits) >= 5 and digits[0] == "0") else "number"
    if _CLASS.fullmatch(text):
        return "class"
    if _CODE.fullmatch(text) and re.search(r"\d", text) and re.search(r"[A-Za-z]", text):
        return "code"
    return "text" if re.search(r"[가-힣A-Za-z]{2}", text) else None


def _family(shape):
    """값 꼴을 비교하는 갈래: 기간은 날짜, 금액·수는 number(칸 하나로는 금액과 수를 가르지 못한다)."""
    return {"period": "date", "amount": "number", "count": "number"}.get(shape, shape)


def _edi_ratio(values):
    """코드 꼴 값 중 EDI 수가코드 꼴(``EDI``, 괄호를 벗겨 본다) 비율. 코드 꼴 값이 셋 미만이면 None."""
    codes = [re.sub(r"[\s{}()\[\]]", "", str(value)).upper() for value in values if _shape(value) == "code"]
    return sum(bool(EDI.fullmatch(code)) for code in codes) / len(codes) if len(codes) >= 3 else None


def edi_side(ratios):
    """두 코드 열의 EDI 꼴 비율 → ``(EDI코드 열 차례, 확실한지)``. 비율을 모르거나 차이가 3할 미만이면 None.
    확실: 높은 쪽이 8할 이상이고 차이가 5할 이상. 열 배치(``code_keys``)와 rules의 코드 열 맞바꿈이 함께 쓴다."""
    if None in ratios or abs(ratios[0] - ratios[1]) < 0.3:
        return None
    side = int(ratios[1] > ratios[0])
    return side, ratios[side] >= 0.8 and abs(ratios[0] - ratios[1]) >= 0.5


def code_keys(words, ratios):
    """인쇄 순서대로 놓인 코드 두 열의 ``(열 키 둘, 근거가 약한지)``. 근거는 머리글 낱말(``CODE_WORDS``, 한 글자 오독까지
    ``_near``. 두 열이 다른 쪽을 가리킬 때) → 값 꼴(``edi_side``) 차례다. 값 꼴은 OCR이 이웃 칸 값을 붙여 읽거나('0AL851') 병원
    코드가 EDI 꼴('A002')이어서 낱말보다 뒤에 본다. 둘 다 없으면 앞 열을 원내코드로 두고, 확실한 값 꼴도 낱말도 없으면 약하다."""
    named = [next((key for key, parts in CODE_WORDS.items() if any(_near(str(word or "").upper(), part.upper()) for part in parts)), None)
             for word in words]
    side = edi_side(ratios)
    if named[0] != named[1]:
        edi = named.index("EDI코드") if "EDI코드" in named else 1 - named.index("원내코드")
    elif side:
        edi = side[0]
    else:
        return ("원내코드", "EDI코드"), True
    return ("EDI코드", "원내코드") if edi == 0 else ("원내코드", "EDI코드"), named[0] == named[1] and not side[1]


def _column_shapes(blocks):
    """가장 큰 표 블록의 셀 행(가장 흔한 칸 수의 행, 여섯 열·세 행 이상)을 열마다 본 ``{kinds: {꼴: 채운 칸 중 비율}, period, edi}``.
    수 칸은 그 열의 0이 아닌 값 중앙값이 100 이상이면 amount, 아니면 count다(0만 있는 열은 amount). 기간은 date로 세고
    period(날짜 열에 기간 칸이 있다)로 따로 알린다. edi는 ``_edi_ratio``. 표가 작으면 None."""
    tables = [block.get("rows") or [] for block in blocks if block.get("type") == "table"]
    rows = max(tables, key=len, default=[])
    width = max(set(map(len, rows)), key=[len(row) for row in rows].count, default=0)
    rows = [row for row in rows if len(row) == width]
    if width < 6 or len(rows) < 3:
        return None
    shapes = []
    for cells in zip(*rows):
        kinds = [kind for cell in cells if (kind := _shape(cell))]
        values = [value for cell in cells if _shape(cell) == "number" and (value := abs(float(str(cell).replace(",", ""))))]
        number = "amount" if not values or median(values) >= 100 else "count"
        named = [{"period": "date", "number": number}.get(kind, kind) for kind in kinds]
        shapes.append({"kinds": {kind: named.count(kind) / len(named) for kind in set(named)},
                       "period": "period" in kinds and max(named, key=named.count) == "date",
                       "edi": _edi_ratio(cells)})
    return shapes


def _fit(shape, key):
    """열 값 꼴이 key 값 꼴에 맞는 정도(0~1). 금액·수가 엇갈리면 반만 친다(0이 많은 금액 열은 수처럼 보인다)."""
    kind = SHAPES[key]
    other = {"amount": "count", "count": "amount"}.get(kind)
    return shape["kinds"].get(kind, 0) + 0.5 * shape["kinds"].get(other, 0)


def _named(keys, shapes):
    """한 배치(열마다 키)를 서식 관례로 이름 짓는다: 같은 꼴 열 묶음은 ``RUNS``(열 수가 없으면 None = 모른다), 코드 두 열은
    ``code_keys``, 한 열뿐인 코드·일자는 ``SINGLE``(EDI코드·시작일자)."""
    keys = list(keys)
    for run in RUNS.values():
        members = {key for names in run.values() for key in names}
        if at := [i for i, key in enumerate(keys) if key in members]:
            keys[at[0]:at[-1] + 1] = run.get(len(at)) or [None] * len(at)
    code = [i for i, key in enumerate(keys) if key in KEYS["코드"]]
    if len(code) == 2:
        keys[code[0]], keys[code[1]] = code_keys([None, None], [shapes[i]["edi"] for i in code])[0]
    for concept in set(SINGLE) & set(KEYS):  # 한 열뿐인 개념(코드·일자)은 SINGLE 열이다
        if len(used := [i for i, key in enumerate(keys) if key in KEYS[concept]]) == 1:
            keys[used[0]] = SINGLE[concept]
    return tuple(keys)


def shaped_columns(blocks, union):
    """머리글을 못 읽은 표의 인쇄 열을 셀 값 꼴(``_column_shapes``)로 정한다 → ``(인쇄 열 → None, 알림)``. 못 정하면 None.

    ``VALUE.free`` 열(급여구분)은 그 값 꼴의 열이 하나뿐이면 그 열에 둔다. 나머지 열은 ``VALUE.order``(인쇄 순서)의 열에 순서를 지키며
    하나씩 맞춰, ``VALUE.required`` 묶음을 갖춘 배치 중 값 꼴 점수(``_fit``) 합이 가장 큰 배치를 모두 찾는다. 서식 관례(``_named``)로
    이름 지은 뒤에도 배치마다 이름이 갈리거나 이름이 없거나 점수가 6할 미만인 열은 ``VALUE.unknown`` 키(읽고 버리는 열)로 두고
    ``column_shape``로 알린다 — 근거 없이 이웃 열 이름을 붙이지 않는다. 기간 칸 열은 시작·종료일자 두 키다.
    값 꼴이 6할 이상인 꼴이 없는 열(빈 열·뒤섞인 열)이 있으면 셀 표를 못 믿어, 정한 열이 절반 미만이면 None."""
    shapes = _column_shapes(blocks)
    if not shapes or any(max(shape["kinds"].values(), default=0) < 0.6 for shape in shapes):  # 값 꼴을 못 읽은 열: 표를 못 믿는다
        return None
    free = {i: key for key in VALUE["free"] if len(fits := [i for i, shape in enumerate(shapes) if _fit(shape, key) >= 0.6]) == 1
            for i in fits}
    rest = [i for i in range(len(shapes)) if i not in free]
    period = any(shapes[i]["period"] for i in rest)
    order = [key for key in VALUE["order"] if key in union and not (period and key == "종료일자")]
    scored = [(round(sum(_fit(shapes[i], key) for i, key in zip(rest, keys)), 6), keys) for keys in combinations(order, len(rest))
              if all(set(group) & set(keys) for group in VALUE["required"])]
    if not scored:
        return None
    best = max(score for score, _ in scored)
    named = {_named(keys, [shapes[i] for i in rest]) for score, keys in scored if score == best}  # 가장 좋은 배치들(이름 지은 뒤)
    keys = []  # 열마다 정한 키(못 정하면 None)
    for i, shape in enumerate(shapes):
        names = {free[i]} if i in free else {option[rest.index(i)] for option in named}
        keys.append(key if len(names) == 1 and (key := names.pop()) and _fit(shape, key) >= 0.6 else None)
    if any(not set(group) & set(keys) for group in VALUE["required"]) or keys.count(None) * 2 > len(keys):
        return None
    flags = {("column_shape", i + 1) for i, key in enumerate(keys) if key is None}
    if len(code := [shape["edi"] for shape, key in zip(shapes, keys) if key in KEYS["코드"]]) == 2 and code_keys([None, None], code)[1]:
        flags.add(("code_order", "EDI코드"))
    columns, unknown = [], iter(range(1, len(keys) + 1))
    for shape, key in zip(shapes, keys):
        columns += [key, "종료일자"] if key == "시작일자" and shape["period"] else [key or f"{VALUE['unknown']['key']}{next(unknown)}"]
    return dict.fromkeys(columns), sorted(flags)


def plan(doc_type, table, blocks, description, columns):
    """(표 설명, 인쇄 열 → 열 설명, 묻지 않은 열의 값). ``columns``는 합집합 열 → 설명. 배치를 정하지 못하면 None."""
    return planned(doc_type, table, blocks, description, columns)[0]


def planned(doc_type, table, blocks, description, columns):
    """``(plan, 열 배치 출처, 머리글을 못 읽은 사유, 알림)``. 출처는 layout(영수증 양식)·header(머리글)·value(셀 값 꼴,
    ``shaped_columns``)·union(못 정해 합집합 순서). 사유는 머리글 방법이 머리글을 못 읽었을 때만:
    no_table_text(표 글자 없음)·no_header_words(머리글 낱말 없음)·few_header_columns(한 줄에 4열 미만).
    알림은 근거가 약해 추측하지 않은 곳 ``(code, 열)``: column_unplaced·code_order(``_header``)·column_shape(``shaped_columns``)."""
    method = METHODS.get(doc_type, {}).get(table)
    if method == "layout":
        if (form := receipt_form(blocks)) in FORMS and set(FORMS[form]["columns"]) <= set(columns):
            return (FORMS[form]["description"], dict(FORMS[form]["columns"]), FILL), "layout", None, []
        return None, "union", "unknown_form", []
    if method != "header":
        return None, "union", None, []
    printed, _, reason, _, flags = _header(blocks, list(columns))
    if printed:
        return (description + NOTE, {key: columns[key] + (f" 이 문서에서는 '{word}' 열이다." if word else "") for key, word in printed.items()},
                None), "header", None, flags
    if shaped := shaped_columns(blocks, list(columns)):
        return ((description + NOTE, {key: columns.get(key, VALUE["unknown"]["description"]) for key in shaped[0]}, None), "value", reason,
                shaped[1])
    return None, "union", reason, []
