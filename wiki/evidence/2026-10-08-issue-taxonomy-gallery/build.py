"""out-P.json·out-E.json·img-index.json 을 합쳐 issue-examples.json 과 페이지 HTML 을 만든다."""
import json, os, re, sys
from PIL import Image

S = os.path.dirname(os.path.abspath(__file__))
TREE = "/home/pilsu/projects/mirae-assets/wiki/2026-10-03-parse-extract-issue-taxonomy.md"

def tree_order():
    exp = []
    for blk, d1 in re.findall(r"```text\n((?:Parse|Extract) \[(\w)\].*?)```", open(TREE).read(), re.S):
        d2 = d3 = None
        for l in blk.splitlines():
            m = re.search(r"\[(\w+)\]\s*$", l)
            if m and ("├─" in l or "└─" in l):
                if l.startswith(("├", "└")): d2 = m.group(1)
                else: d3 = m.group(1)
            m2 = re.search(r"[├└]─ (\d+) ", l)
            if m2: exp.append(f"{d1}.{d2}.{d3}.{m2.group(1)}")
    return exp

exp = tree_order()
data = json.load(open(f"{S}/out-P.json")) + json.load(open(f"{S}/out-E.json"))
ids = [x["id"] for x in data]
assert sorted(set(ids)) == sorted(ids), "dup"
assert not [e for e in exp if e not in ids], [e for e in exp if e not in ids]
idx = json.load(open(f"{S}/img-index.json")) if os.path.exists(f"{S}/img-index.json") else {}
hl = {}
for f in ("hl-P.json", "hl-E.json"):
    if os.path.exists(f"{S}/{f}"): hl.update(json.load(open(f"{S}/{f}")))
for x in data:
    x.pop("img", None)
    g = idx.get(x["id"])
    if not g or not os.path.exists(f"{S}/{g['edge']}"): continue
    img = {"edge": g["edge"], "edge_wh": list(Image.open(f"{S}/{g['edge']}").size), "note": g.get("note", ""),
           "run": g.get("run", ""), "mechanism": g.get("mechanism", "")}
    if g.get("base") and os.path.exists(f"{S}/{g['base']}"):
        img["base"] = g["base"]; img["base_wh"] = list(Image.open(f"{S}/{g['base']}").size)
    h = hl.get(x["id"])
    if h:
        img.update(boxes=h.get("boxes", []), base_boxes=h.get("base_boxes", []), label=h.get("label", ""))
        z = f"img/{x['id']}-zoom.jpg"
        if os.path.exists(f"{S}/{z}"): img.update(zoom=z, zoom_wh=list(Image.open(f"{S}/{z}").size))
    x["img"] = img
order = {e: i for i, e in enumerate(exp)}
data.sort(key=lambda x: (order.get(x["id"], 999), x["id"]))
json.dump(data, open(f"{S}/issue-examples.json", "w"), ensure_ascii=False, indent=1)
t = open(f"{S}/template.html").read()
open(f"{S}/issue-taxonomy-gallery.html", "w").write(t.replace("/*DATA*/", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
c = {s: sum(x["status"] == s for x in data) for s in ("observed", "synthetic", "assumed")}
print(len(data), c, "img", sum("img" in x for x in data), "base", sum("base" in x.get("img", {}) for x in data), "zoom", sum("zoom" in x.get("img", {}) for x in data))
