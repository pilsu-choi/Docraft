"""``PRINT_REGISTER``: 진료비영수증 금액 층이 양식 칸선에서 통째로 반 행가량 밀려 찍힌 인쇄(양식 층·프린터 층 정합 오류)를
OCR 줄 좌표로 문서 단위에서 되돌리는 순수 함수. 모델 호출은 없다.

값마다 가까운 행으로 옮기지 않고(앵커 단건을 믿으면 고친 만큼 깨뜨린다) 사람이 맞추듯 문서 전체에 이동량 c(행 단위) 하나를 정해
인쇄 줄(같은 높이의 금액 묶음) 단위로 옮긴다.
1. 기울기 보정(``_deskew``) 뒤 항목 격자 안 숫자 상자를 인쇄 줄로 묶는다. 한 줄 상자에 금액이 여럿 붙으면 글자 위치 비례로 나눈다.
2. 항목명 글줄로 행 앵커를 잡고(이름 상자는 항목 격자 왼쪽 끝 오른쪽만 - 표 왼쪽 카드 칸 글줄이 같은 높이로 섞이지 않게)
   Theil-Sen 추세로 거른 뒤 구간 보간해 y → 행 좌표 u 를 만든다.
3. 합계 줄(VLM 합계 행 값·열 합과 2개 이상 일치하는 가장 아래 줄)을 기준점으로, 합계 줄=합계 행·모든 줄이 첫 행~합계 행 안·
   한 행 한 줄인 c 가운데 줄 적합도가 가장 높은 것을 고른다. 같은 적합도의 배정이 둘이면(c 와 c±1) 모호해 손대지 않는다.
4. 게이트(|c| ≥ LO, c 를 빼면 줄의 FIT 이상이 행 중심 TOL 안)를 통과하면 줄의 값을 열 그대로 옮긴다. 도착 칸이 다른 값으로
   차 있고 비워지지 않으면 문서 전체를 포기한다.
검증·근거: wiki/2026-10-09-receipt-print-register-port.md
"""

import re
import statistics as st
from collections import defaultdict
from difflib import SequenceMatcher

from . import rules

LO, TOL, FIT, PITCH = 0.3, 0.25, 0.7, 0.1  # 이동 하한(행), 행 중심 허용(행), 맞아야 할 줄 비율, 고른 앵커 구간의 행 간격 허용 비율
NAME_COL, NAME_RATIO, MARGIN = 0.4, 0.75, 0.05  # 이름 상자 가로 상한(쪽 폭 비율), 이름 유사도 하한, 남는 후보와의 점수 차
_strip = lambda s: re.sub(r"[^가-힣A-Za-z0-9]", "", str(s or ""))
_num = lambda s: re.sub(r"\D", "", str(s or "")).lstrip("0")  # 숫자열(구분자·앞 0 제거), 빈 문자열 = 0/빈칸
_label = lambda name: _strip(str(name).split("_", 1)[-1])  # 하위 행은 하위 이름표만(입원료_1인실 → 1인실)


def _is_num(t):
    return bool(_num(t)) and not re.search(r"[가-힣]", t) and sum(c.isdigit() for c in t) >= 0.5 * len(re.sub(r"[,.]", "", t))


def _boxes(blocks, page):
    """쪽의 OCR 줄 → 상자 {x,l,r,y,h,t}. 금액이 여럿 붙은 숫자 줄(``12,000 3,400``)은 글자 위치 비례로 토큰마다 나눈다."""
    out = []
    for line in (line for b in blocks if b.get("page") == page for line in b.get("lines") or [] if line.get("bbox") and str(line.get("text") or "").strip()):
        (x0, y0, x1, y1), t = line["bbox"], str(line["text"])
        parts = [(m.start(), m.end()) for m in re.finditer(r"\S+", t)] if rules._MULTI_AMOUNT.search(t) and not re.search(r"[가-힣]", t) else [(0, len(t))]
        for a, z in parts:
            l, r = x0 + (x1 - x0) * a / len(t), x0 + (x1 - x0) * z / len(t)
            out.append({"x": (l + r) / 2, "l": l, "r": r, "y": (y0 + y1) / 2, "h": y1 - y0, "t": t[a:z]})
    return out


def _deskew(boxes):
    """같은 줄로 보이는 상자쌍(세로 차 < 높이 절반, 가로 3높이 이상) 기울기 중앙값으로 y 를 x=0 기준으로 되돌린다."""
    ss = [(b["y"] - a["y"]) / (b["x"] - a["x"]) for a in boxes for b in boxes
          if b["x"] - a["x"] > 3 * a["h"] and abs(b["y"] - a["y"]) < 0.5 * min(a["h"], b["h"])]
    s = st.median(ss) if len(ss) >= 5 else 0
    return [{**b, "y": b["y"] - s * b["x"]} for b in boxes], s


def _group(boxes, chain):
    """y 순으로 세로가 겹치는 상자끼리 묶는다. ``chain``이면 바로 앞 상자와(이름 글줄), 아니면 묶음 평균 높이와(인쇄 줄) 비교한다."""
    out = []
    for b in sorted(boxes, key=lambda b: b["y"]):
        if out:
            g = out[-1]
            y, h = (g[-1]["y"], g[-1]["h"]) if chain else (st.mean(x["y"] for x in g), st.median(x["h"] for x in g))
            if abs(b["y"] - y) < 0.5 * max(b["h"], h):
                g.append(b)
                continue
        out.append([b])
    return out


def _names(boxes, width, left=0):
    """이름 상자: 쪽 폭 ``NAME_COL`` 왼쪽이고 항목 격자 왼쪽 끝(``left``) 오른쪽인, 숫자가 아닌 글자 상자."""
    return [b for b in boxes if b["x"] < NAME_COL * width and b["r"] > left and re.search(r"[가-힣A-Za-z]", b["t"]) and not _is_num(b["t"])]


def _score(label, line):
    """이름표와 글줄(앞·뒤 창)의 유사도. 긴 이름표가 앞서도록 길이를 조금 더한다(진찰료 vs 예약진찰료)."""
    n = len(label)
    best = max(SequenceMatcher(None, label, w).ratio() for k in (n - 1, n, n + 1, n + 2) if k > 0 for w in (line[-k:], line[:k]))
    return best + 0.01 * n if best >= NAME_RATIO else 0


def _anchors(names, boxes):
    """행 인덱스 → 이름 글줄 y, 앵커 상자들. 글줄마다 점수 1등 행 하나에만 배정(동점 제외), 같은 이름표 행 수만큼 순서대로 짝,
    Theil-Sen 직선에서 3행 넘게 벗어나거나 y 순서를 어기는 앵커는 버린다."""
    hit = defaultdict(list)
    for bs in _group(boxes, True):
        text = "".join(b["t"] for b in sorted(bs, key=lambda b: b["x"]))
        forms = {_strip(text), _strip(rules.item(text))}
        sc = sorted(((max(_score(_label(n), f) for f in forms), i) for i, n in enumerate(names) if n and len(_label(n)) > 1), reverse=True)
        if sc and sc[0][0] > 0 and (len(sc) == 1 or sc[0][0] > sc[1][0]):
            hit[sc[0][1]].append((st.median(b["y"] for b in bs), bs, sc[0][0]))
    anc, abox, group = {}, [], defaultdict(list)
    for i, n in enumerate(names):
        group[_label(n) if n else None].append(i)
    for lab, idx in group.items():
        got = sorted((c for i in idx for c in hit.get(i, [])), key=lambda c: -c[2])
        if lab and len(got) >= len(idx) and (len(got) == len(idx) or got[len(idx) - 1][2] - got[len(idx)][2] >= MARGIN):
            for i, (y, bs, _) in zip(idx, sorted(got[:len(idx)], key=lambda c: c[0])):
                anc[i] = y
                abox += bs
    ix = sorted(anc)
    if len(ix) < 3:
        return {}, abox
    b = st.median((anc[j] - anc[i]) / (j - i) for i in ix for j in ix if j > i)
    a = st.median(anc[i] - b * i for i in ix)
    ok = [i for i in ix if abs(anc[i] - a - b * i) <= 3 * abs(b)]
    return {i: anc[i] for k, i in enumerate(ok) if b > 0 and (k == 0 or anc[i] > anc[ok[k - 1]])}, abox


def _row_coord(anc):
    """y → (행 좌표 u, 받침 여부). 고른 앵커 구간(4행 이하이거나 행 간격이 중앙값의 ±PITCH 안) 안이면 선형 보간,
    아니면 가장 가까운 앵커 + 거리/행 간격이고 그 앵커에서 1행 이내일 때만 받친다."""
    ix = sorted(anc)
    seg = lambda p, q: (anc[q] - anc[p]) / (q - p)
    med = st.median(seg(p, q) for p, q in zip(ix, ix[1:]))

    def u(y):
        for p, q in zip(ix, ix[1:]):
            if anc[p] <= y <= anc[q] and (q - p <= 4 or abs(seg(p, q) / med - 1) <= PITCH):
                return p + (y - anc[p]) / seg(p, q), True
        a = min(ix, key=lambda i: abs(anc[i] - y))
        return a + (y - anc[a]) / med, abs(y - anc[a]) <= med
    return u, med


def register(rows, blocks, found, page=1):
    """``rows``(VLM 항목내역 행) → (새 행 목록, 진단 info). info["reason"]은 "적용" 또는 손대지 않은 이유(이때 행은 그대로).
    ``found``는 band 위치 상자(쪽 1000 정규화, ``band.boxes``), ``blocks``는 OCR 줄(``lines``)이 붙은 같은 쪽 파싱 블록.
    합계 줄은 합계 행 값으로 찾으므로, 같은 인쇄 밀림으로 합계 금액이 바로 위 행에 붙은 것(``rules._misplaced_total``)을 먼저 되돌려 본다
    (뒤의 ``rules.apply``가 같은 일을 하므로 적용할 때만 그 결과를 함께 돌려준다)."""
    table = {rules.ITEM_TABLE: [dict(r) for r in rows]}
    rules._misplaced_total(table)
    new, info = _register(table[rules.ITEM_TABLE], blocks, found, page)
    return (new, info) if info["reason"] == "적용" else (rows, info)


def _register(rows, blocks, found, page):
    names = [r.get("항목") for r in rows]
    t = next((i for i in range(len(rows) - 1, -1, -1) if rules.total_label(rows[i]) in ("계", "합계")), None)
    size = next((b["page_size"] for b in blocks if b.get("page") == page and b.get("page_size")), None)
    if t is None or len(rows) < 4 or not size:
        return rows, {"reason": "합계 행 없음" if t is None else "행 부족" if len(rows) < 4 else "쪽 크기 없음"}
    W, H = size
    g, sm = ([v[0] * W / 1000, v[1] * H / 1000, v[2] * W / 1000, v[3] * H / 1000] if v else None for v in (found["grid"], found.get("summary")))
    boxes, slope = _deskew(_boxes(blocks, page))
    nameb = _names(boxes, W, g[0])
    anc, abox = _anchors(names, nameb)
    info = {"slope": round(slope, 4), "anchored": len(anc), "rows": len(rows)}
    if len(anc) < 4:
        return rows, {**info, "reason": "앵커 부족"}
    u, med = _row_coord(anc)
    summ = sm if sm and sm[0] > (g[0] + g[2]) / 2 else None  # 표 오른쪽 금액산정 칸의 숫자는 빼고 본다
    edge = st.quantiles([b["r"] for b in abox], n=10)[-1] if len(abox) >= 2 else 0.3 * W
    ys = sorted(anc.values())
    lo, hi = min(ys[0], g[1]) - 2 * med, max(ys[-1], g[3]) + 2 * med
    nums = [b for b in boxes if b["l"] > edge and lo <= b["y"] <= hi and _is_num(b["t"]) and not (summ and b["x"] >= summ[0] and summ[1] <= b["y"] <= summ[3])]
    lines = [(st.median(b["y"] for b in bs), {_num(b["t"]) for b in bs}) for bs in _group(nums, False)]
    vals = {i: {k: _num(r.get(k)) for k in rules.ITEM_COLUMNS if _num(r.get(k))} for i, r in enumerate(rows)}
    r2l = {}  # VLM 행 → 인쇄 줄: 행 값 숫자열이 가장 많이 든 줄(동점이면 미정)
    for i, vs in vals.items():
        sc = sorted(((sum(x in ls for x in vs.values()), li) for li, (_, ls) in enumerate(lines)), reverse=True)
        if sc and sc[0][0] and (len(sc) == 1 or sc[0][0] > sc[1][0]):
            r2l[i] = sc[0][1]
    tv = set(vals[t].values()) | {str(sum(int(vals[i].get(k, 0)) for i in range(len(rows)) if i != t)) for k in rules.ITEM_COLUMNS} - {"0"}
    tl = next((li for li in range(len(lines) - 1, -1, -1) if len(tv & lines[li][1]) >= 2), None)
    if tl is not None and t not in anc:  # 합계 행 앵커가 없으면 합계 줄 1행 안의 '합'·'합계' 이름 상자로 잡는다
        tls = [b["y"] for b in nameb if re.fullmatch(r"합|합계.{0,2}", _strip(b["t"])) and abs(b["y"] - lines[tl][0]) <= med and b["y"] > max(anc.values())]
        if tls:
            anc[t] = min(tls, key=lambda y: abs(y - lines[tl][0]))
            u, med = _row_coord(anc)
    us = {li: u(lines[li][0]) for li in set(r2l.values()) | ({tl} - {None})}
    used = sorted(li for li, (_, ok) in us.items() if ok)
    info["rows_on_line"] = f"{len(r2l)}/{sum(1 for x in vals.values() if x)}"
    if tl not in used:
        return rows, {**info, "reason": "합계 줄 못 찾음/받침 없음"}
    if len(used) < 3:
        return rows, {**info, "reason": "줄 부족"}

    def place(c):  # c 만큼 옮긴 줄 → 행. 합계 줄=합계 행, 첫 행~합계 행 안, 한 행 한 줄을 어기면 None
        rr = {li: round(us[li][0] - c) for li in used}
        if rr[tl] != t or any(not 0 <= r <= t for r in rr.values()) or len(set(rr.values())) < len(rr):
            return None
        return rr, sum(abs(us[li][0] - c - rr[li]) <= TOL for li in used) / len(used)
    cand = [(p[1], c / 20, tuple(sorted(p[0].items()))) for c in range(-60, 61) if (p := place(c / 20))]
    if not cand:
        return rows, {**info, "reason": "경계 제약 만족하는 이동 없음"}
    fit = max(f for f, _, _ in cand)
    top = [(c, a) for f, c, a in cand if f == fit]
    c = st.median(c for c, _ in top)
    info.update(c=round(c, 2), fit=round(fit, 2))
    if len({a for _, a in top}) > 1:
        return rows, {**info, "reason": "모호(같은 적합도의 다른 배정)"}
    if fit < FIT:
        return rows, {**info, "reason": "게이트: 줄이 행 중심에 안 맞음"}
    if abs(c) < LO:
        return rows, {**info, "reason": "게이트: c 작음(정상 인쇄)"}
    l2r = dict(top[0][1])
    plan = [(i, l2r[li], k, rows[i][k]) for i, li in r2l.items() if li in l2r and l2r[li] != i for k, x in vals[i].items() if x in lines[li][1]]
    leaving = {(i, k) for i, _, k, _ in plan}
    if any(_num(rows[j].get(k)) not in ("", _num(val)) and (j, k) not in leaving for _, j, k, val in plan):
        return rows, {**info, "reason": "도착 칸 점유", "moves": len(plan)}
    new = [dict(r) for r in rows]
    for i, _, k, _ in plan:
        new[i][k] = "0"
    for _, j, k, val in plan:
        new[j][k] = val
    return new, {**info, "reason": "적용", "moves": [[names[i], names[j], k, val] for i, j, k, val in plan]}
