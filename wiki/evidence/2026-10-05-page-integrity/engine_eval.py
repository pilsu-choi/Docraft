"""Run the branch's engine.unit_flags over local parse caches (no external calls)."""
import pickle, os, sys, collections, itertools, io, json
sys.path.insert(0, "/home/pilsu/projects/mirae-assets/Docraft/.worktrees/page-integrity")
from backend import engine
from PIL import Image
S=os.path.dirname(os.path.abspath(__file__))
recs=pickle.load(open(f"{S}/recs.pkl","rb"))
def norm_blocks(blocks, page=None):
    out=[]
    for b in blocks:
        b=dict(b); b["page"]=int(b.get("page") or 1) if page is None else page; out.append(b)
    return out
out={}
# 1) every cached document as parsed (single runs, unique stems): flag counts
seen=set(); counts=collections.Counter(); flagged=[]
for r in recs:
    if r["stem"] in seen: continue
    seen.add(r["stem"]); b=norm_blocks(r["blocks"])
    fl=engine.unit_flags({}, {"properties":{}}, {}, b, r["img"])
    counts["docs"]+=1; counts["pages"]+=len({x["page"] for x in b}); counts["golden_docs"]+=r["golden"]
    for f in fl:
        counts[f["code"]]+=1; counts[f["code"]+("_golden" if r["golden"] else "")]+=r["golden"]
        flagged.append((r["stem"], f))
print("as-parsed:", dict(counts)); [print("  ",x) for x in flagged]
# page-level pool for synthetic bundles
pool={}
for r in recs:
    pages=collections.defaultdict(list)
    for b in norm_blocks(r["blocks"]): pages[b["page"]].append(b)
    for p,bl in pages.items(): pool.setdefault((r["stem"],p),dict(type=r["type"],blocks=bl,img=r["img"],golden=r["golden"]))
H={}
for k,v in pool.items():
    if v["img"]:
        h=engine._page_hashes(v["img"],{k[1]},{}); 
        if k[1] in h: H[k]=h[k[1]]
print("pages", len(pool), "hashed", len(H))
cur={}
engine._page_hashes=lambda source, pages, turns: {n:cur[n] for n in pages if n in cur}
def pair(a,b,ha=True):
    cur.clear()
    if ha: cur.update({1:H[a],2:H[b]})
    blocks=[dict(x,page=1) for x in pool[a]["blocks"]]+[dict(x,page=2) for x in pool[b]["blocks"]]
    return engine.unit_flags({}, {"properties":{}}, {}, blocks, "x.pdf")
# 2) synthetic 2-page bundles of two different pages (all pairs with images)
keys=sorted(H); c=collections.Counter(); dup=[]; bound=[]
for a,b in itertools.combinations(keys,2):
    fl=pair(a,b); c["pairs"]+=1; same=pool[a]["type"]==pool[b]["type"]; c["same_type" if same else "cross_type"]+=1
    for f in fl:
        if f["code"]=="duplicate_page": dup.append((a,b))
        if f["code"]=="document_boundary": c["boundary_"+("same" if same else "cross")]+=1; bound.append((a,b,f["titles"])) if same else None
print("bundles:", dict(c)); print(" duplicate_page:", dup); print(" boundary on same-type pairs:", bound[:10])
# 3) positives: same page OCR'd by different runs (text differs), image = same page hash
runs=collections.defaultdict(dict)
for r in recs:
    pages=collections.defaultdict(list)
    for b in norm_blocks(r["blocks"]): pages[b["page"]].append(b)
    for p,bl in pages.items(): runs[(r["stem"],p)]["".join(engine._normalized(x.get("text","")) for x in bl)]=bl
pos=collections.Counter()
for k,variants in runs.items():
    if k not in H: continue
    for ta,tb in itertools.combinations(list(variants),2):
        cur.clear(); cur.update({1:H[k],2:H[k]})
        blocks=[dict(x,page=1) for x in variants[ta]]+[dict(x,page=2) for x in variants[tb]]
        hit=any(f["code"]=="duplicate_page" for f in engine.unit_flags({}, {"properties":{}}, {}, blocks, "x.pdf"))
        pos["pairs"]+=1; pos["hit"]+=hit
print("same page, different OCR runs:", dict(pos))
