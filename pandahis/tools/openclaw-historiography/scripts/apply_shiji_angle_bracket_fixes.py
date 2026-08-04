#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPLIT = ROOT / "data/02二十四史拆分后/01史记_拆分后"
IDX = ROOT / "data/03索引标注条目/段落索引"
OUT = ROOT / "data/05工作流中间产物/原文清洗"
MOTHER = ROOT / "data/00原文母本/二十四史原文/01史记.txt"

def S(*cps):
    return "".join(chr(c) for c in cps)

def T(*cps):
    return "<" + S(*cps) + ">"

pairs = [
    (S(0x9CF7)+T(0x652F,0x96B9), S(0x9CF7)),
    ("{"+S(0x5C71,0x757E)+"}", S(0x5792)),
    (T(0x6728,0x8656), S(0x6A17)),
    (T(0x8011,0x72AE), S(0x9EFB)),
    (T(0x8011,0x752B), S(0x9EFC)),
    (T(0x96E8,0x56DE), S(0x96F7)),
    (T(0x961D,0x4E5D), S(0x9098)),
    (T(0x7FBD,0x6C0F), S(0x7FC5)),
    (T(0x9ED1,0x65E6), S(0x9EEB)),
    (T(0x5189,0x9875), S(0x9AEF)),
    (T(0x5193,0x9875), S(0x8BB2)),
    (T(0x76EE,0x5939), S(0x776B)),
    (T(0x8C78,0x539F), S(0x8C72)),
    (T(0x6728,0x8BF8), S(0x69E0)),
    (T(0x866B,0x5E7D), S(0x86B4)),
    (T(0x89D2,0x8011), S(0x7AEF)),
    (T(0x8F66,0x60E0), S(0x8F4A)),
    (T(0x9C7C,0x4E98), S(0x9CDE)),
    (T(0x9E1F,0x52A0), S(0x9D10)),
    (T(0x5C71,0x80E5), S(0x5CF8)),
    (T(0x5E7F,0x758C), S(0x36E4)),
    (T(0x9C7C,0x53DF), S(0x9CB0)),
    (T(0x5C71,0x757E), S(0x5792)),
    (T(0x652F,0x96B9), S(0x9CF7)),
    (T(0x76EE,0x5944), S(0x667B)),
    (T(0x8C37,0x5BB3), S(0x8C39)),
    (T(0x9C7C,0x77A2), S(0x9C6F)),
    (T(0x53E3,0x72AE), S(0x7782)),
    (T(0x77F3,0x84B2), S(0x84B2)),
    (T(0x6B64,0x9E1F), S(0x75B5)),
    (T(0x7389,0x9E1F), S(0x5C5E,0x7389)),
    (T(0x77F3,0x7758), S(0x789D)),
    (T(0x8C37,0x51E1), S(0x8C3B)),
    (T(0x9E1F,0x7758), S(0x9E00)),
    (T(0x9E1F,0x8474), S(0x7BB4)),
    (T(0x6708,0x537A), S(0x8DFD)),
]

def apply_text(text):
    log=[]; out=text
    for pat,rep in pairs:
        n=out.count(pat)
        if n:
            out=out.replace(pat,rep); log.append((pat,rep,n))
    return out, log

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    changed, logs = [], []
    for fp in sorted(SPLIT.glob("01史记_*.txt")):
        old=fp.read_text(encoding="utf-8"); new,log=apply_text(old)
        if new!=old:
            fp.write_text(new, encoding="utf-8"); changed.append(fp.name)
            for item in log: logs.append((fp.name,)+item)
    if MOTHER.exists():
        old=MOTHER.read_text(encoding="utf-8"); new,log=apply_text(old)
        if new!=old:
            MOTHER.write_text(new, encoding="utf-8")
            print("mother", sum(n for _,_,n in log))
    remain=[]
    for fp in sorted(SPLIT.glob("01史记_*.txt")):
        text=fp.read_text(encoding="utf-8")
        for m in re.finditer(r"<[^>\n]+>", text): remain.append((fp.name,m.group(0)))
    print("changed", len(changed), "repl", sum(x[3] for x in logs), "remain", len(remain), remain)
    vols=sorted({re.match(r"01史记_(\d+)_", n).group(1) for n in changed})
    for vol in vols:
        src=next(SPLIT.glob(f"01史记_{vol}_*.txt"))
        idx_path=IDX/f"01史记_{vol}.json"
        old_idx=json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
        lines=src.read_text(encoding="utf-8").splitlines()
        old_total=int(old_idx.get("total") or 0)
        nonempty=[ln for ln in lines if ln.strip()!=""]
        paras_src = lines if old_total==len(lines) else (nonempty if old_total==len(nonempty) else lines)
        paragraphs=[{"id":i,"text":line} for i,line in enumerate(paras_src,1)]
        new_idx=dict(old_idx)
        new_idx.update({"work":"01史记","vol":vol,"source_file":old_idx.get("source_file") or src.name,"paragraph_mode":old_idx.get("paragraph_mode") or "line","total":len(paragraphs),"paragraphs":paragraphs})
        idx_path.write_text(json.dumps(new_idx, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print("index", vol, old_total, "->", new_idx["total"])
    with (OUT/"史记_尖括号修复明细.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.writer(f); w.writerow(["file","pattern","replacement","count"])
        for row in logs: w.writerow(row)
    (OUT/"史记_尖括号合字映射.json").write_text(json.dumps([{"pattern":a,"replacement":b,"basis":"user-confirmed"} for a,b in pairs], ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    checks=[("043",S(0x9B13,0x9E9F,0x9AED,0x9AEF)),("054",S(0x8427,0x4F55,0x4E3A,0x6CD5,0xFF0C,0x8BB2,0x82E5,0x753B,0x4E00)),("005",S(0x5929,0x5B50,0x8D3A,0x4EE5,0x9EFC,0x9EFB)),("005",S(0x6A17,0x91CC,0x75BE)),("040",S(0x718A,0x9EEB)),("117",S(0x5C5E,0x7389)),("069",S(0x9769,0x6289,0x7782,0x82AE)),("126",S(0x97A0,0x8DFD)),("037",S(0x36E4,0x4F2F)),("045",S(0x97E9,0x5C06,0x9CB0)),("117",S(0x8FC7,0x9CF7,0x9E4A))]
    for vol,needle in checks:
        fp=next(SPLIT.glob(f"01史记_{vol}_*.txt"))
        print(("OK" if needle in fp.read_text(encoding="utf-8") else "MISS"), vol, needle)

if __name__ == "__main__":
    main()
