"""Rebuild a ruled table's structure from its printed lines instead of trusting the VLM's generated HTML.

The VLM writes rowspan/colspan token by token, so one miscounted span shifts every later row of a large form.
Here the grid comes first: horizontal/vertical rule lines give row and column boundaries, a missing rule
between two grid cells means they are merged, and PP-OCRv5 line boxes fill the cells. A rectangular grid is
guaranteed by construction; only merges can go wrong."""
from bisect import bisect_left

import numpy as np

GAP = 3  # px: rule thickness; profile rows closer than this belong to one rule
SLACK = 10  # px: how far a warped scan bends a rule away from its table-wide position


def _runs(dark, length, axis):
    """Mask of pixels on a dark run of at least `length` along `axis` (erode then dilate with a 1-D window)."""
    if dark.shape[axis] < length:
        return np.zeros_like(dark)
    csum = np.cumsum(np.pad(dark.astype(np.int32), [(1, 0) if a == axis else (0, 0) for a in range(2)]), axis=axis)
    head = np.take(csum, range(length, dark.shape[axis] + 1), axis=axis) - np.take(csum, range(dark.shape[axis] - length + 1), axis=axis) == length
    csum = np.cumsum(np.pad(head.astype(np.int32), [(length, 0) if a == axis else (0, 0) for a in range(2)]), axis=axis)
    return np.take(csum, range(length, csum.shape[axis]), axis=axis) - np.take(csum, range(csum.shape[axis] - length), axis=axis) > 0


def _positions(profile, size, minimum, text):
    """Centers of consecutive rows/columns whose line pixel count reaches `minimum`. The crop edge is added
    only where OCR text lies beyond the outermost rule (an open-sided table), so empty margins stay out."""
    found, group = [], []
    for i in np.flatnonzero(profile >= minimum):
        if group and i - group[-1] > GAP:
            found.append(sum(group) / len(group))
            group = []
        group.append(i)
    if group:
        found.append(sum(group) / len(group))
    if not found or any(t < found[0] for t in text):
        found.insert(0, 0.0)
    if any(t > found[-1] for t in text):
        found.append(float(size))
    return [round(p) for i, p in enumerate(found) if i == 0 or p - found[i - 1] > 2 * GAP]


def _reading(boxes):
    """Text of OCR boxes [x0, y0, x1, y1, text] in reading order: visual lines top to bottom, left to right within."""
    lines = []
    for box in sorted(boxes, key=lambda b: b[1] + b[3]):
        if lines and abs((box[1] + box[3]) - (lines[-1][0][1] + lines[-1][0][3])) < box[3] - box[1]:
            lines[-1].append(box)
        else:
            lines.append([box])
    return "\n".join(" ".join(b[4] for b in sorted(line)) for line in lines)


def _dark(gray, window=31, contrast=20):
    """Pixels darker than their local mean, so photographed pages with uneven light and shaded cells still binarize."""
    img = gray.astype(np.int64)
    pad = window // 2
    integral = np.pad(np.pad(img, pad, mode="edge").cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    h, w = img.shape
    total = integral[window:window + h, window:window + w] - integral[:h, window:window + w] - integral[window:window + h, :w] + integral[:h, :w]
    return img < total / window ** 2 - contrast


def _split(box, x):
    """Cut an OCR box at vertical rule `x` on the word gap nearest to it; None when the rule would cut a word.

    PP-OCR often joins text of adjacent cells ("1 12,380"), while scan streaks run through the middle of words."""
    x0, y0, x1, y1, text = box
    step = (x1 - x0) / len(text)
    gaps = [i for i, ch in enumerate(text) if ch == " "]
    best = min(gaps, key=lambda i: abs(x0 + (i + 0.5) * step - x), default=None)
    if best is None or abs(x0 + (best + 0.5) * step - x) > 2 * step:
        return None
    return [x0, y0, x, y1, text[:best].strip()], [x, y0, x1, y1, text[best + 1:].strip()]


def ruled_table(image, bbox, lines):
    """(rows, spans) of the table at `bbox` in `image` (PIL), or None if it is not a ruled grid.

    `lines` are OCR {"text", "bbox"} boxes in the same coordinates; rows/spans follow the `_grid` convention."""
    x0, y0, x1, y1 = (round(v) for v in bbox)
    crop = image.crop((x0, y0, x1, y1)).convert("L")
    dark = _dark(np.asarray(crop))
    h, w = dark.shape
    # Thicken by one pixel across the line direction so slightly skewed scan rules stay one continuous run.
    thick_h, thick_v = dark | np.roll(dark, 1, 0) | np.roll(dark, -1, 0), dark | np.roll(dark, 1, 1) | np.roll(dark, -1, 1)
    boxes = [[b[0] - x0, b[1] - y0, b[2] - x0, b[3] - y0, str(line["text"]).strip()] for line in lines for b in [line["bbox"]] if str(line["text"]).strip()]
    # A rule spans at least one cell: cells are taller than 1.2 text heights and wider than two glyphs,
    # while a glyph stroke is at most one text height long.
    text_h = float(np.median([b[3] - b[1] for b in boxes])) if boxes else 25
    across, down = max(30, round(2 * text_h)), max(20, round(1.2 * text_h))
    horizontal, vertical = _runs(thick_h, across, 1), _runs(thick_v, down, 0)
    words = [b for b in boxes if len(b[4]) > 1]  # single glyphs at the edge are usually scan specks
    ys = _positions(horizontal.sum(1), h, across, [(b[1] + b[3]) / 2 for b in words])
    xs = _positions(vertical.sum(0), w, down, [(b[0] + b[2]) / 2 for b in words])
    rows, cols = len(ys) - 1, len(xs) - 1
    if rows < 2 or cols < 2:
        return None

    def ruled(mask, at, start, end, axis):
        band = mask[max(0, at - SLACK):at + SLACK + 1, start + GAP:end - GAP] if axis else mask[start + GAP:end - GAP, max(0, at - SLACK):at + SLACK + 1]
        return band.size and band.any(axis=0 if axis else 1).mean() >= 0.9

    def row_of(b):
        return next((r for r in range(rows) if (b[1] + b[3]) / 2 <= ys[r + 1]), rows - 1)

    def crosses(b, x):
        return min(x - b[0], b[2] - x) > (b[3] - b[1]) / 2

    queue, boxes = boxes, []
    while queue:  # split boxes that span a real rule at a word gap
        b = queue.pop()
        x = next((x for x in xs[1:-1] if crosses(b, x) and ruled(vertical, x, ys[row_of(b)], ys[row_of(b) + 1], 0)), None)
        parts = _split(b, x) if x is not None else None
        if parts:
            queue.extend(parts)
        else:
            boxes.append(b)
    # open_right[r][c]: no rule between (r, c) and (r, c + 1); open_down[r][c]: none between (r, c) and (r + 1, c).
    # Text still running across a rule after splitting means the "rule" is scan noise through a word.
    open_right = [[not ruled(vertical, xs[c + 1], ys[r], ys[r + 1], 0) or any(crosses(b, xs[c + 1]) and row_of(b) == r for b in boxes)
                   for c in range(cols - 1)] for r in range(rows)]
    open_down = [[not ruled(horizontal, ys[r + 1], xs[c], xs[c + 1], 1) or any(
        min(ys[r + 1] - b[1], b[3] - ys[r + 1]) > (b[3] - b[1]) / 3 and xs[c] <= (b[0] + b[2]) / 2 <= xs[c + 1] for b in boxes)
                  for c in range(cols)] for r in range(rows - 1)]
    # Each row splits into runs at its rules; a run continues the cell above when it covers the same columns and most
    # of the rule between them is missing. Cells are rectangles by construction and never merge across a rule.
    rects, above = [], {}
    for r in range(rows):
        runs, start = [], 0
        for c in range(cols):
            if c == cols - 1 or not open_right[r][c]:
                runs.append((start, c))
                start = c + 1
        current = {}
        for c0, c1 in runs:
            rect = above.get((c0, c1))
            if rect and sum(open_down[r - 1][c0:c1 + 1]) * 2 > c1 - c0 + 1:
                rect[2] = r
            else:
                rect = [r, c0, r, c1]
                rects.append(rect)
            current[(c0, c1)] = rect
        above = current
    texts = {}
    for b in boxes:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for i, (r0, c0, r1, c1) in enumerate(rects):
            if xs[c0] <= cx <= xs[c1 + 1] and ys[r0] <= cy <= ys[r1 + 1]:
                texts.setdefault(i, []).append(b)
                break

    def kept(edges, first, last):
        """Grid boundaries some cell ends on, minus the leading edge of a text-free sliver bounded by two such
        boundaries (double rules, two nearly aligned rules), so the cell before the sliver absorbs it."""
        ends = {0} | {rect[last] + 1 for rect in rects}
        return sorted(ends - {k for k in ends if k and k + 1 in ends and edges[k + 1] - edges[k] < text_h
                              and all(n not in texts for n, rect in enumerate(rects) if rect[first] == rect[last] == k)})

    keep_r, keep_c = kept(ys, 0, 2), kept(xs, 1, 3)
    grid, spans = [[""] * (len(keep_c) - 1) for _ in keep_r[:-1]], []
    for n, (r0, c0, r1, c1) in enumerate(rects):
        top, left, bottom, right = bisect_left(keep_r, r0), bisect_left(keep_c, c0), bisect_left(keep_r, r1 + 1), bisect_left(keep_c, c1 + 1)
        if top == bottom or left == right:
            continue  # an empty cell lying wholly inside a dropped sliver
        text = _reading(texts.get(n, []))
        for r in range(top, bottom):
            grid[r][left:right] = [text] * (right - left)
        if bottom - top > 1 or right - left > 1:
            spans.append([top, left, bottom - top, right - left])
    return (grid, sorted(spans)) if len(grid) > 1 and len(grid[0]) > 1 else None
