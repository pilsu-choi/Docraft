"""rowmajor 표 추출(``TABLE_EXTRACT=rowmajor``)에서 모델에 줄 열 배치를 OCR 블록으로 정한다(규칙 기반, LLM 호출 없음).

rowmajor는 행마다 값 배열만 받으므로 열 자리가 문서에 인쇄된 열과 다르면 합집합에만 있는 자리가 이웃 값을 가로챈다.
그래서 유형·표마다(``rulesets/table_layouts.yaml``의 ``tables``) 두 방법 중 하나로 인쇄 열을 정한다.

- layout: 표 셀 낱말로 진료비영수증 양식 번호(1~5)를 판별해 그 양식의 인쇄 열과 열 설명을 준다.
- header: 표 블록 OCR 줄(글자+bbox)에서 머리글 낱말을 찾아 x 순으로 정렬한 열을 준다.

정하지 못하면 ``plan``이 None을 돌려주고 engine이 합집합 열 순서로 읽는다.
"""

import re
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
PAIRS = {key: {other for other in keys if other != key} for keys in KEYS.values() for key in keys}  # 짝 열(같은 개념의 다른 열)
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


def _segment(text):
    """띄어쓰기 없이 붙은 머리글('수량횟수일수')을 머리글 낱말 여럿으로 나눈다. 다 못 나누면 None."""
    if not text:
        return []
    for word in sorted(WORDS, key=len, reverse=True):
        if text.startswith(word) and (rest := _segment(text[len(word):])) is not None:
            return [word, *rest]
    return None


def _words(text):
    """줄 글자를 머리글 낱말 단위로: 떨어져 쓴 낱말('급여 구분', 'EDI 코드')은 합치고 붙어 쓴 낱말은 나눈다."""
    parts, out, i = text.split() or [text], [], 0
    while i < len(parts):
        k = next((k for k in (3, 2) if "".join(parts[i:i + k]) in WORDS), 1)
        word, i = "".join(parts[i:i + k]), i + k
        split = _segment(word) or []
        out += split if not _concepts(word)[0] and len(split) > 1 else [word]
    return out


def _tokens(blocks):
    """표 블록 줄을 머리글 낱말로 쪼갠 {text, x, y, h}. 한 줄에 낱말이 여럿이면 글자 수로 줄 폭을 나눠 x를 정한다.
    돌아간 페이지의 블록(``orientation``)은 좌표가 원본 기준이므로 바로 선 페이지 좌표로 돌려서 본다."""
    from .parsers import unturn  # parsers → engine → table_layout 순환을 피한다
    out = []
    for block in blocks:
        if block.get("type") != "table":
            continue
        if block.get("orientation"):
            block = unturn([block], 360 - block["orientation"])[0]
        for line in block.get("lines") or []:
            x0, y0, x1, y1 = line["bbox"]
            words = _words(line["text"])
            total, at = sum(map(len, words)) or 1, 0
            for word in words:
                out.append({"text": word, "x": x0 + (x1 - x0) * (at + len(word) / 2) / total, "y": (y0 + y1) / 2, "h": y1 - y0})
                at += len(word)
    return out


def printed_columns(blocks, union, min_columns=4):
    """머리글 줄에서 읽은 열을 인쇄 순서로 둔 합집합 열의 부분열. 머리글 줄에서 열을 ``min_columns``개 미만으로 읽으면 None.

    못 읽은 열은 ``OPTIONAL``이면 서식에 없다고 보고 빼고, 아니면 OCR 오독으로 보고 합집합 순서의 제자리에 둔다.
    다만 열이 없다는 판단은 그 개념의 머리글 낱말을 읽어 열 수를 셌을 때만 한다. 한 개념의 열(예: 원내코드·EDI코드)을
    하나도 못 읽어 짝 열을 제자리에 넣었으면 그 개념의 열 수를 모르므로 못 읽은 짝도 그 옆에 둔다(코드 열이 하나뿐인
    서식은 ``rules``가 원내코드를 EDI코드로 모은다)."""
    tokens = [{**t, "hits": hits, "exact": d == 0} for t in _tokens(blocks) for hits, d in [_concepts(t["text"])] if hits]
    exact = {t["hits"][0] for t in tokens if t["exact"] and len(t["hits"]) == 1}
    for t in tokens:  # 두 개념과 같은 거리의 오독('임수' = 일수·횟수)은 이미 정확히 읽힌 개념을 뺀 쪽이다
        rest = set(t["hits"]) - exact
        t["c"] = t["hits"][0] if len(t["hits"]) == 1 else rest.pop() if len(rest) == 1 else None
    tokens = [t for t in tokens if t["c"]]
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
    concepts = [t["c"] for t in sorted(picked, key=lambda t: t["x"])]
    if SUBS & set(concepts):
        concepts = [c for c in concepts if c != "급여"]  # 하위 열이 있으면 급여는 묶음 제목이다
    seen, columns = {}, []
    for concept in concepts:
        n = seen[concept] = seen.get(concept, 0) + 1
        key = (SINGLE[concept] if concept in SINGLE and concepts.count(concept) == 1
               else KEYS[concept][n - 1] if n <= len(KEYS[concept]) else None)
        if key in union and key not in columns:
            columns.append(key)
    if len(columns) < min_columns:
        return None
    read = set(columns)
    for key in sorted((key for key in union if key not in columns), key=lambda key: key in OPTIONAL):  # 못 읽은 필수 열 먼저
        pair = next((other for other in columns if other in PAIRS[key] and other not in read), None) if key in OPTIONAL else None
        if pair is not None:
            at = columns.index(pair)
            columns.insert(at if union.index(key) < union.index(pair) else at + 1, key)
        elif key not in OPTIONAL:
            before = [columns.index(other) for other in union[:union.index(key)] if other in columns]
            columns.insert(before[-1] + 1 if before else 0, key)
    return columns


def plan(doc_type, table, blocks, description, columns):
    """(표 설명, 인쇄 열 → 열 설명, 묻지 않은 열의 값). ``columns``는 합집합 열 → 설명. 배치를 정하지 못하면 None."""
    method = METHODS.get(doc_type, {}).get(table)
    if method == "layout" and (form := receipt_form(blocks)) in FORMS and set(FORMS[form]["columns"]) <= set(columns):
        return FORMS[form]["description"], dict(FORMS[form]["columns"]), FILL
    if method == "header" and (printed := printed_columns(blocks, list(columns))):
        return description + NOTE, {key: columns[key] for key in printed}, None
    return None
