"""rowmajor 표 추출(``TABLE_EXTRACT=rowmajor``)에서 모델에 줄 열 배치를 OCR 블록으로 정한다(규칙 기반, LLM 호출 없음).

rowmajor는 행마다 값 배열만 받으므로 열 자리가 문서에 인쇄된 열과 다르면 합집합에만 있는 자리가 이웃 값을 가로챈다.
그래서 유형·표마다(``rulesets/table_layouts.yaml``의 ``tables``) 두 방법 중 하나로 인쇄 열을 정한다.

- layout: 표 셀 낱말로 진료비영수증 양식 번호(1~5)를 판별해 그 양식의 인쇄 열과 열 설명을 준다.
- header: 표 블록 OCR 줄(글자+bbox, 줄 상자가 없으면 셀)에서 머리글 낱말을 찾아 x 순으로 정렬한 열을 준다.
  머리글을 못 읽으면 셀 값 꼴(날짜·코드·글자·금액·수)의 순서로 정한다(value, ``shaped_columns``).

정하지 못하면 ``plan``이 None을 돌려주고 engine이 합집합 열 순서로 읽는다. ``planned``는 출처와 실패 사유도 준다.
"""

import re
from functools import lru_cache
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
    """``(인쇄 열 → 머리글 글자 | None, 읽은 열 → x, 실패 사유 | None, 두 줄로 쌓인 같은 개념 낱말의 열)``.

    머리글 줄은 열 개념 낱말이 ``min_columns``개 이상인 첫 줄이다. 위아래 두 줄 안(줄 높이 3배 안, 사이에 숫자 줄이 없을 때)의
    낱말도 그 x에 다른 머리글 낱말이 없고 정확히 읽혔거나 머리글 낱말이 둘 이상인 줄에 있으면 열이다 — 칸 높이가 다른 머리글('총액'이
    두 줄 칸 가운데). 같은 개념 낱말이 같은 x에 쌓였으면('코드' 아래 '{수가코드}') 한 칸, 한 열이다. 묶음 제목 아래 하위 열(``SUBS``)은
    늘 받는다. 곱하는 열이 둘이면 횟수·일수다(``COUNTS``, '총투'·'일수').

    못 읽은 열은 그 자리에 열이 있다는 근거가 있을 때만 넣는다 — 머리글 낱말이 다 읽혔는데 열을 끼우면 이웃 값이 그 자리로 간다.
    - 필수 열(``OPTIONAL`` 밖)은 합집합 순서의 제자리 양옆 머리글 사이에 머리글 낱말로 읽지 못한 글자가 있거나 그 사이가 넓을 때
      (OCR이 낱말을 통째로 놓쳤다) 넣는다. 오독으로 붙은 긴 글자(다섯 자 이상)가 있으면 머리글을 다 읽지 못했다고 보고 늘 넣는다.
    - 짝 열(``PAIRS``)은 짝을 근거로 넣었거나(열 수를 세지 못했다) 짝의 머리글 칸에 그 열 낱말과 겹치는 읽지 못한 글자가 있으면
      짝 옆에 함께 둔다. 나머지 선택 열은 서식에 없다고 본다.
    한 칸이 두 열의 값을 싣는 개념(``SPANS``, '일자' 한 칸의 진료기간)은 본문이 그렇게 찍혔으면 두 열을 함께 묻는다.
    낱말 하나뿐인 개념은 ``SINGLE``(낱말이나 개념 → 열)을 따른다. 다만 그 열을 다른 개념이 차지하면 따르지 않는다."""
    lines = _lines(blocks)
    if not lines:
        return None, {}, "no_table_text", set()
    tokens = [{**t, "hits": hits, "exact": d == 0} for t in _tokens(lines) for hits, d in [_concepts(t["text"])]]
    exact = {t["hits"][0] for t in tokens if t["exact"] and len(t["hits"]) == 1}
    for t in tokens:  # 두 개념과 같은 거리의 오독('임수' = 일수·횟수)은 이미 정확히 읽힌 개념을 뺀 쪽이다
        rest = set(t["hits"]) - exact
        t["c"] = t["hits"][0] if len(t["hits"]) == 1 else rest.pop() if len(rest) == 1 else None
    unread, tokens = [t for t in tokens if not t["c"] and re.search(r"[가-힣A-Za-z]", t["text"])], [t for t in tokens if t["c"]]
    if not tokens:
        return None, {}, "no_header_words", set()
    height = median(t["h"] for t in tokens)
    rows = []  # y로 묶은 줄(위에서 아래)
    for t in sorted(tokens, key=lambda t: t["y"]):
        if rows and t["y"] - rows[-1][-1]["y"] <= height * 0.6:
            rows[-1].append(t)
        else:
            rows.append([t])
    head = next((i for i, row in enumerate(rows) if len({t["c"] for t in row}) >= min_columns), None)
    if head is None:
        return None, {}, "few_header_columns", set()
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
    picked = sorted((t for i, t in enumerate(picked) if not any(p["c"] == t["c"] and abs(p["x"] - t["x"]) < height for p in picked[:i])),
                    key=lambda t: t["x"])
    if SUBS & {t["c"] for t in picked}:
        picked = [t for t in picked if t["c"] != "급여"]  # 하위 열이 있으면 급여는 묶음 제목이다
    concepts = [t["c"] for t in picked]
    band = [t for t in unread  # 머리글 줄의 읽지 못한 글자: x가 가장 가까운 머리글 낱말과 같은 줄에 있다
            if abs(t["y"] - min(picked, key=lambda p: abs(p["x"] - t["x"]))["y"]) <= height * 0.6]
    maybe = [hit for t in band for hit in t["hits"]]  # 두 개념 사이 오독('총맥' = 총액·총투)
    seen, columns, at, words = {}, [], {}, {}
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
                at[key] = t["x"]
                if len(KEYS[concept]) > 1 and not once:  # 한 개념의 열이 여럿이면(코드 둘·단가와 금액) 머리글 글자를 남긴다
                    words[key] = word if word in WORDS else None
    if len(columns) < min_columns:
        return None, {}, "few_header_columns", set()
    poorly = any(t["hits"] and set(t["hits"]) & {"횟수", "일수", "투여량"} for t in unread)  # 곱하는 열 머리글을 다 읽지 못했다
    counts = [key for key in columns if key in COUNTS[3]]
    if len(counts) == 2 and counts != COUNTS[2] and not poorly:  # 곱하는 두 열은 횟수·일수다('총투'·'일수', 표준 서식·정답지 관례)
        names = dict(zip(counts, COUNTS[len(counts)]))
        columns, at = [names.get(key, key) for key in columns], {names.get(key, key): x for key, x in at.items()}
        words = {names.get(key, key): word for key, word in words.items()}
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

    def unread_between(i):
        """columns[i] 자리 양옆 머리글(x를 아는 열) 사이에 머리글 낱말로 읽지 못한 글자가 있거나, 그 사이가 머리글 간격
        중앙값의 2.5배보다 넓다(머리글 글자를 OCR이 통째로 놓쳤다)."""
        lo = max((at[key] for key in columns[:i] if key in at), default=float("-inf"))
        hi = min((at[key] for key in columns[i:] if key in at), default=float("inf"))
        return poor or any(lo < t["x"] < hi for t in band) or wide < hi - lo < float("inf")
    poor = any(len(re.findall(r"[가-힣A-Za-z]", t["text"])) >= 5 for t in band)  # 낱말 여럿이 오독으로 붙은 머리글: 다 읽히지 않았다
    for key in sorted((key for key in union if key not in columns), key=lambda key: key in OPTIONAL):  # 못 읽은 필수 열 먼저
        pair = next((other for other in columns if other in PAIRS.get(key, ()) and (other not in read or unreadable(key, other))),
                    None) if key in OPTIONAL else None
        if pair is not None:
            i = columns.index(pair)
            columns.insert(i if union.index(key) < union.index(pair) else i + 1, key)
        elif key not in OPTIONAL:
            before = [columns.index(other) for other in union[:union.index(key)] if other in columns]
            # 제자리: 합집합 순서로 바로 앞 열 뒤부터, 앞 열이 모두 인쇄된 뒤까지 가운데 근거가 있는 첫 자리
            if (i := next((i for i in range(before[-1] + 1 if before else 0, max(before, default=-1) + 2) if unread_between(i)), None)) is not None:
                columns.insert(i, key)
    named = None not in words.values() and len(set(words.values())) == len(words)  # 오독했거나 같은 글자('금액'·'금액')면 못 가른다
    return {key: words.get(key) if named else None for key in columns}, at, None, {key for key in columns if at.get(key) in stacked}


_DATE = re.compile(r"(?:19|20)?\d{2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}")
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


def _column_shapes(blocks):
    """가장 큰 표 블록의 셀 행(가장 흔한 칸 수의 행)을 열마다 본 값 꼴 목록. 열의 값 꼴은 채운 칸 60% 이상의 꼴이고,
    수는 0이 아닌 값의 중앙값이 100 이상이면 amount, 아니면 count다(모두 0인 열은 amount). 못 정하면 None."""
    tables = [block.get("rows") or [] for block in blocks if block.get("type") == "table"]
    rows = max(tables, key=len, default=[])
    width = max(set(map(len, rows)), key=[len(row) for row in rows].count, default=0)
    rows = [row for row in rows if len(row) == width]
    if width < 6 or len(rows) < 3:
        return None
    shapes = []
    for cells in zip(*rows):
        kinds = [kind for cell in cells if (kind := _shape(cell))]
        kind = max(set(kinds), key=kinds.count, default=None)
        if not kinds or kinds.count(kind) < len(kinds) * 0.6 and not {kind, *kinds} <= {"date", "period"}:
            return None
        if kind == "number":
            values = [value for cell in cells if _shape(cell) == "number" and (value := abs(float(str(cell).replace(",", ""))))]
            kind = "amount" if not values or median(values) >= 100 else "count"
        shapes.append(("period" if "period" in kinds else "date") if kind in ("date", "period") else kind)
        if kind == "code":
            shapes[-1] = ("code", sum(bool(EDI.fullmatch(str(cell).strip().upper())) for cell in cells))
    return shapes


COUNTS = {1: ["횟수"], 2: ["횟수", "일수"], 3: ["투여량", "횟수", "일수"]}  # 단가와 총액 사이 곱하는 열 수 → 열(표준 서식 금액·횟수·일수)
SHARES = ["본인부담", "공단부담", "전액본인부담", "비급여"]  # 총액 뒤 금액 열의 서식 순서(급여: 일부본인부담 본인·공단, 전액본인부담 | 비급여)


def shaped_columns(blocks, union):
    """머리글을 못 읽은 표의 인쇄 열을 셀 값 꼴의 순서로 정한다(``_column_shapes``): 날짜 → 시작일자(기간이면 종료일자도),
    코드 → EDI코드(둘이면 EDI 꼴이 많은 쪽이 EDI코드), 날짜·코드 앞 글자 → 항목, 뒤 글자 → EDI명칭, 급여구분 값 → 급여구분,
    수 열은 [단가] 횟수류(1~3열) 총액 [본인부담 공단부담 (전액본인부담 (비급여))] 꼴일 때만(총액 뒤 열은 금액으로 본다). 꼴이 이 틀에 맞지 않으면 None."""
    shapes = _column_shapes(blocks)
    if not shapes:
        return None
    numbers = "".join("a" if shape == "amount" else "c" for shape in shapes if shape in ("amount", "count"))
    match = re.fullmatch(r"(a?)(c{1,3})(a)([ac]*)", numbers)  # 총액 뒤는 모두 금액 열이다(0이 많은 열은 수처럼 보인다)
    if not match or len(match[4]) not in (0, 2, 3, 4):
        return None
    amounts = (["단가"] if match[1] else []) + COUNTS[len(match[2])] + ["총액"] + SHARES[:len(match[4])]
    codes = [shape[1] for shape in shapes if isinstance(shape, tuple)]
    if len(codes) > 2:
        return None
    code_keys = iter(["EDI코드"] if len(codes) < 2 else ["원내코드", "EDI코드"] if codes[0] <= codes[1] else ["EDI코드", "원내코드"])
    columns, texts = [], 0
    for shape in shapes:
        if isinstance(shape, tuple):
            columns.append(next(code_keys))
        elif shape in ("date", "period"):
            columns += ["시작일자", "종료일자"] if shape == "period" else ["종료일자" if "시작일자" in columns else "시작일자"]
        elif shape == "text":
            texts += 1
            columns.append("EDI명칭" if {"시작일자", "EDI코드"} & set(columns) else "항목")
        elif shape == "class":
            columns.append("급여구분")
        else:
            columns.append(amounts.pop(0))
    if texts > 2 or len(set(columns)) < len(columns) or "총액" not in columns or not {"EDI명칭", "EDI코드"} & set(columns):
        return None
    return {key: None for key in columns if key in union}


def plan(doc_type, table, blocks, description, columns):
    """(표 설명, 인쇄 열 → 열 설명, 묻지 않은 열의 값). ``columns``는 합집합 열 → 설명. 배치를 정하지 못하면 None."""
    return planned(doc_type, table, blocks, description, columns)[0]


def planned(doc_type, table, blocks, description, columns):
    """``(plan, 열 배치 출처, 머리글을 못 읽은 사유)``. 출처는 layout(영수증 양식)·header(머리글)·value(셀 값 꼴,
    ``shaped_columns``)·union(못 정해 합집합 순서). 사유는 머리글 방법이 머리글을 못 읽었을 때만:
    no_table_text(표 글자 없음)·no_header_words(머리글 낱말 없음)·few_header_columns(한 줄에 4열 미만)."""
    method = METHODS.get(doc_type, {}).get(table)
    if method == "layout":
        if (form := receipt_form(blocks)) in FORMS and set(FORMS[form]["columns"]) <= set(columns):
            return (FORMS[form]["description"], dict(FORMS[form]["columns"]), FILL), "layout", None
        return None, "union", "unknown_form"
    if method != "header":
        return None, "union", None
    printed, _, reason, _ = _header(blocks, list(columns))
    if printed:
        return (description + NOTE, {key: columns[key] + (f" 이 문서에서는 '{word}' 열이다." if word else "") for key, word in printed.items()},
                None), "header", None
    if shaped := shaped_columns(blocks, list(columns)):
        return (description + NOTE, {key: columns[key] for key in shaped}, None), "value", reason
    return None, "union", reason
