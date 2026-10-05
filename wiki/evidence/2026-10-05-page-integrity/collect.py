"""Collect (stem, type, run, page text, image path) records from local Docraft parse caches."""
import json, glob, os, re, pickle, collections
R="/home/pilsu/projects/mirae-assets"
S=os.path.dirname(__file__)
imgs={}
for line in open(f"{S}/dataset_files.txt"):
    p=line.strip(); imgs.setdefault(os.path.basename(p), p)
E=f"{R}/exp/e2e_call_test"
for d in ["진료비영수증 테스트 샘플","세부내역서 테스트 샘플"]:
    for f in os.listdir(f"{E}/{d}"): imgs[f]=f"{E}/{d}/{f}"
for f in glob.glob(f"{R}/exp/e2e_call_test/out/extra-detail-1002/**/*",recursive=True):
    if re.search(r"\.(tif|jpg|png|pdf|jpeg)$",f,re.I): imgs.setdefault(os.path.basename(f),f)
def norm(t): return re.sub(r"[\s,]+|\\n","",str(t))
recs=[]
def add(blocks, stem, typ, run, golden=False):
    pages=collections.defaultdict(list)
    for b in blocks: pages[b.get("page")].append(b)
    img=imgs.get(stem) or next((v for k,v in imgs.items() if os.path.splitext(k)[0]==os.path.splitext(stem)[0]),None)
    recs.append(dict(stem=stem,type=typ,run=run,golden=golden,img=img,blocks=blocks))
for f in glob.glob(f"{R}/Docraft/data/verify/**/*.parse.json",recursive=True):
    base=os.path.basename(f)[:-len(".parse.json")]; typ,stem=base.split("__",1) if "__" in base else ("?",base)
    x=json.load(open(f)); b=x if isinstance(x,list) else x.get("blocks")
    if isinstance(b,list) and b: add(b,stem,typ,f)
for d in ["ab-rowmajor-1002","integrate-1003","extra-detail-1002"]:
    for f in glob.glob(f"{E}/out/{d}/ocr/**/*.json",recursive=True):
        x=json.load(open(f)); b=x if isinstance(x,list) else x.get("blocks")
        if not isinstance(b,list) or not b: continue
        typ=os.path.basename(os.path.dirname(f)); stem=os.path.basename(f)[:-5]
        add(b,stem,typ if typ!="ocr" else "세부내역서",f,golden=d!="extra-detail-1002")
print(len(recs), sum(r["img"] is not None for r in recs), len({r["stem"] for r in recs}), len({r["stem"] for r in recs if r["img"]}))
pickle.dump(recs,open(f"{S}/recs.pkl","wb"))
