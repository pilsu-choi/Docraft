"""rowmajor 표 추출(``TABLE_EXTRACT=rowmajor``)에서 모델에 줄 열 배치를 OCR 블록으로 정한다(규칙 기반, LLM 호출 없음).

rowmajor는 행마다 값 배열만 받으므로 열 자리가 문서에 인쇄된 열과 다르면 합집합에만 있는 자리가 이웃 값을 가로챈다.
그래서 유형·표마다(``rulesets/table_layouts.yaml``의 ``tables``) 두 방법 중 하나로 인쇄 열을 정한다.

- layout: 표 셀 낱말로 진료비영수증 양식 번호(1~5)를 판별해 그 양식의 인쇄 열과 열 설명을 준다.
- header: 표 블록 OCR 줄(글자+bbox)에서 머리글 낱말을 찾아 x 순으로 정렬한 열을 준다.

정하지 못하면 ``plan``이 None을 돌려주고 engine이 합집합 열 순서로 읽는다.
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


def _lines(blocks):
    """표 블록 OCR 줄(바로 선 페이지 좌표). 돌아간 페이지의 블록(``orientation``)은 좌표가 원본 기준이라 돌려서 본다.
    두 줄로 갈려 인쇄된 머리글 낱말('전액'/'본인부담')은 위아래로 붙고 합친 글자가 머리글 낱말이면 한 줄로 합친다."""
    from .parsers import unturn  # parsers → engine → table_layout 순환을 피한다
    lines = []
    for block in blocks:
        if block.get("type") != "table":
            continue
        if block.get("orientation"):
            block = unturn([block], 360 - block["orientation"])[0]
        lines += [{"text": line["text"], "bbox": list(line["bbox"])} for line in block.get("lines") or [] if line.get("bbox")]
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
    머리글 줄에서 열을 ``min_columns``개 미만으로 읽으면 None.

    못 읽은 열은 ``OPTIONAL``이면 서식에 없다고 보고 빼고, 아니면 OCR 오독으로 보고 합집합 순서의 제자리에 둔다.
    다만 열이 없다는 판단은 근거가 있을 때만 한다. 짝 열(``PAIRS``)은 짝이 없다는 근거가 없으면 짝 옆에 함께 둔다.
    - 짝(예: 원내코드·EDI코드)의 개념 낱말을 하나도 못 읽어 짝을 제자리에 넣었으면 열 수를 세지 못했다(코드 열이 하나뿐인
      서식은 ``rules``가 원내코드를 EDI코드로 모은다).
    - 짝의 머리글 칸에 머리글 낱말로 읽지 못한 글자가 있으면 그 칸에 열이 더 있을 수 있다.
    한 칸이 두 열의 값을 싣는 개념(``SPANS``, '일자' 한 칸의 진료기간)은 본문이 그렇게 찍혔으면 두 열을 함께 묻는다."""
    lines = _lines(blocks)
    tokens = [{**t, "hits": hits, "exact": d == 0} for t in _tokens(lines) for hits, d in [_concepts(t["text"])]]
    exact = {t["hits"][0] for t in tokens if t["exact"] and len(t["hits"]) == 1}
    for t in tokens:  # 두 개념과 같은 거리의 오독('임수' = 일수·횟수)은 이미 정확히 읽힌 개념을 뺀 쪽이다
        rest = set(t["hits"]) - exact
        t["c"] = t["hits"][0] if len(t["hits"]) == 1 else rest.pop() if len(rest) == 1 else None
    unread, tokens = [t for t in tokens if not t["c"] and len(re.findall(r"[가-힣A-Za-z]", t["text"])) >= 2], [t for t in tokens if t["c"]]
    if not tokens:
        return None
    height = median(t["h"] for t in tokens)
    rows = []  # y로 묶은 줄(위에서 아래)
    for t in sorted(tokens, key=lambda t: t["y"]):
        if rows and t["y"] - rows[-1][-1]["y"] <= height * 0.6:
            rows[-1].append(t)
        else:
            rows.append([t])
    head = next((i for i, row in enumerate(rows) if len({t["c"] for t in row}) >= min_columns), None)
    if head is None:
        return None
    picked = list(rows[head])
    for row in rows[head + 1:head + 3]:  # 묶음 제목 아래 하위 열 줄
        if row[0]["y"] - picked[-1]["y"] <= height * 3:
            picked += [t for t in row if t["c"] in SUBS]
    picked.sort(key=lambda t: t["x"])
    if SUBS & {t["c"] for t in picked}:
        picked = [t for t in picked if t["c"] != "급여"]  # 하위 열이 있으면 급여는 묶음 제목이다
    concepts = [t["c"] for t in picked]
    seen, columns, at, words = {}, [], {}, {}
    for t in picked:
        concept = t["c"]
        n = seen[concept] = seen.get(concept, 0) + 1
        once = concepts.count(concept) == 1
        keys = ((once and concept in SPANS and _spans(concept, t["x"], picked, lines)) or
                [SINGLE[concept] if once and concept in SINGLE else KEYS[concept][n - 1] if n <= len(KEYS[concept]) else None])
        for key in keys:
            if key in union and key not in columns:
                columns.append(key)
                at[key] = t["x"]
                if len(KEYS[concept]) > 1 and not once:  # 한 개념의 열이 여럿이면(코드 둘·단가와 금액) 머리글 글자를 남긴다
                    words[key] = word if (word := re.sub(r"\W", "", t["text"])) in WORDS else None
    if len(columns) < min_columns:
        return None
    read, xs = set(columns), sorted(at.values())
    band = [t for t in unread  # 머리글 줄의 읽지 못한 글자: x가 가장 가까운 머리글 낱말과 같은 줄에 있다
            if abs(t["y"] - min(picked, key=lambda p: abs(p["x"] - t["x"]))["y"]) <= height * 0.6]

    def unreadable(key, pair):
        """짝 열 머리글 칸의 key 쪽 절반(이웃 머리글과의 가운데까지)에 key 개념 낱말과 두 글자 이상 겹치는, 머리글 낱말로
        읽지 못한 글자가 있다('단민부금' = 본인부담금 오독)."""
        i = xs.index(at[pair])
        left = union.index(key) < union.index(pair)
        lo = (xs[i - 1] + xs[i]) / 2 if left and i else float("-inf") if left else xs[i]
        hi = xs[i] if left else (xs[i] + xs[i + 1]) / 2 if i + 1 < len(xs) else float("inf")
        own = [word for word, concept in WORDS.items() if key in KEYS[concept]]
        return any(lo <= t["x"] <= hi and any(len(set(t["text"]) & set(word)) >= 2 for word in own) for t in band)
    for key in sorted((key for key in union if key not in columns), key=lambda key: key in OPTIONAL):  # 못 읽은 필수 열 먼저
        pair = next((other for other in columns if other in PAIRS.get(key, ()) and (other not in read or unreadable(key, other))),
                    None) if key in OPTIONAL else None
        if pair is not None:
            i = columns.index(pair)
            columns.insert(i if union.index(key) < union.index(pair) else i + 1, key)
        elif key not in OPTIONAL:
            before = [columns.index(other) for other in union[:union.index(key)] if other in columns]
            columns.insert(before[-1] + 1 if before else 0, key)
    named = None not in words.values() and len(set(words.values())) == len(words)  # 오독했거나 같은 글자('금액'·'금액')면 못 가른다
    return {key: words.get(key) if named else None for key in columns}


def plan(doc_type, table, blocks, description, columns):
    """(표 설명, 인쇄 열 → 열 설명, 묻지 않은 열의 값). ``columns``는 합집합 열 → 설명. 배치를 정하지 못하면 None."""
    method = METHODS.get(doc_type, {}).get(table)
    if method == "layout" and (form := receipt_form(blocks)) in FORMS and set(FORMS[form]["columns"]) <= set(columns):
        return FORMS[form]["description"], dict(FORMS[form]["columns"]), FILL
    if method == "header" and (printed := printed_columns(blocks, list(columns))):
        return description + NOTE, {key: columns[key] + (f" 이 문서에서는 '{word}' 열이다." if word else "") for key, word in printed.items()}, None
    return None
