#!/usr/bin/env python3
"""按用户白名单修正《汉书》101–106 卷 v2 skeleton / blocks / protagonists。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
for p in (str(_ROOT), str(SKILL_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from paths_config import get_histograph_root  # noqa: E402

ROOT = get_histograph_root()
INDEX_DIR = ROOT / "data" / "03索引标注条目" / "段落索引"
SKEL_DIR = ROOT / "data" / "10新标注条目"
BLOCKS_DIR = ROOT / "data" / "05工作流中间产物" / "标注-v2"
WORK = "02汉书"

OwnerSpec = Tuple[int, int, str, str]  # from, to, name, category
EntrySpec = Tuple[str, str, int, int]  # name, category, from, to

# (owners, entries, special_excludes: (from,to,reason), multi_owner_paragraphs: {p: [(name,cat),...]})
VOL_CONFIG: Dict[str, dict] = {
    "101": {
        "owners": [
            (11, 11, "丁宽", "文臣"),
            (18, 18, "伏生", "文臣"),
            (21, 21, "夏侯胜", "文臣"),
            (24, 24, "孔安国", "文臣"),
            (25, 25, "申公", "文臣"),
        ],
        "entries": [
            ("丁宽", "文臣", 11, 11),
            ("伏生", "文臣", 18, 18),
            ("夏侯胜", "文臣", 21, 21),
            ("孔安国", "文臣", 24, 24),
            ("申公", "文臣", 25, 25),
        ],
        "special_excludes": [(40, 40, "论赞")],
        "multi": {},
        "volume_subtype": "liezhuan_hezhuan",
    },
    "102": {
        "owners": [
            (6, 8, "文翁", "文臣"),
            (10, 19, "黄霸", "文臣"),
            (20, 23, "朱邑", "文臣"),
            (24, 27, "龚遂", "文臣"),
            (28, 31, "召信臣", "文臣"),
        ],
        "entries": [
            ("文翁", "文臣", 6, 8),
            ("黄霸", "文臣", 10, 19),
            ("朱邑", "文臣", 20, 23),
            ("龚遂", "文臣", 24, 27),
            ("召信臣", "文臣", 28, 31),
        ],
        "special_excludes": [(9, 9, "共段总述")],
        "multi": {},
        "volume_subtype": "liezhuan_hezhuan",
    },
    "103": {
        "owners": [
            (4, 8, "郅都", "文臣"),
            (19, 23, "王温舒", "文臣"),
            (30, 31, "田延年", "文臣"),
            (32, 37, "严延年", "文臣"),
        ],
        "entries": [
            ("郅都", "文臣", 4, 8),
            ("王温舒", "文臣", 19, 23),
            ("田延年", "文臣", 30, 31),
            ("严延年", "文臣", 32, 37),
        ],
        "special_excludes": [(42, 42, "论赞")],
        "multi": {},
        "volume_subtype": "hezhuan",
    },
    "104": {
        "owners": [
            (6, 6, "范蠡", "庶众"),
            (8, 8, "白圭", "庶众"),
            (9, 9, "猗顿", "庶众"),
            (14, 14, "蜀卓氏", "庶众"),
            (16, 16, "罗裒", "庶众"),
        ],
        "entries": [
            ("范蠡", "庶众", 6, 6),
            ("白圭", "庶众", 8, 8),
            ("猗顿", "庶众", 9, 9),
            ("蜀卓氏", "庶众", 14, 14),
            ("罗裒", "庶众", 16, 16),
        ],
        "special_excludes": [(2, 2, "篇内小标题"), (26, 26, "论赞")],
        "multi": {},
        "volume_subtype": "hezhuan",
    },
    "105": {
        "owners": [
            (7, 7, "朱家", "庶众"),
            (8, 8, "剧孟", "庶众"),
            (10, 17, "郭解", "庶众"),
        ],
        "entries": [
            ("朱家", "庶众", 7, 7),
            ("剧孟", "庶众", 8, 9),
            ("郭解", "庶众", 10, 17),
            ("王孟", "庶众", 9, 9),
            ("薛况", "庶众", 9, 9),
        ],
        "special_excludes": [(45, 45, "共段总述")],
        "multi": {
            9: [
                ("剧孟", "庶众"),
                ("王孟", "庶众"),
                ("薛况", "庶众"),
            ],
        },
        "volume_subtype": "hezhuan",
    },
    "106": {
        "owners": [
            (3, 6, "邓通", "庶众"),
            (8, 11, "韩嫣", "庶众"),
            (12, 12, "李延年", "庶众"),
            (14, 20, "石显", "宦官"),
            (26, 34, "董贤", "庶众"),
        ],
        "entries": [
            ("邓通", "庶众", 3, 6),
            ("韩嫣", "庶众", 8, 11),
            ("李延年", "庶众", 12, 12),
            ("石显", "宦官", 14, 20),
            ("董贤", "庶众", 26, 34),
        ],
        "special_excludes": [
            (7, 7, "共段总述"),
            (13, 13, "共段总述"),
            (21, 25, "共段总述"),
            (35, 35, "论赞"),
        ],
        "multi": {},
        "volume_subtype": "hezhuan",
    },
}


def _para_map(idx: dict) -> Dict[int, str]:
    return {int(p["id"]): p.get("text", "") for p in idx.get("paragraphs") or []}


def _quote(paras: Dict[int, str], pf: int, limit: int = 200) -> str:
    return re.sub(r"\s+", "", paras.get(pf, ""))[:limit]


def _owner_map(
    owners: List[OwnerSpec],
    multi: Dict[int, List[Tuple[str, str]]],
) -> Dict[int, List[Tuple[str, str]]]:
    pmap: Dict[int, List[Tuple[str, str]]] = {}
    for pf, pt, name, cat in owners:
        for p in range(pf, pt + 1):
            pmap[p] = [(name, cat)]
    for p, items in multi.items():
        pmap[p] = items
    return pmap


def _exclude_map(special: List[Tuple[int, int, str]]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for pf, pt, reason in special:
        for p in range(pf, pt + 1):
            out[p] = reason
    return out


def build_segment_attribution(
    total: int,
    owners: List[OwnerSpec],
    special_excludes: List[Tuple[int, int, str]],
    multi: Dict[int, List[Tuple[str, str]]],
) -> List[dict]:
    omap = _owner_map(owners, multi)
    exmap = _exclude_map(special_excludes)
    rows: List[dict] = []
    for p in range(1, total + 1):
        if p == 1:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "卷首标题"})
        elif p in exmap:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": exmap[p]})
        elif p in omap:
            rows.append(
                {
                    "paragraph": p,
                    "owners": [{"name": n, "category": c} for n, c in omap[p]],
                }
            )
        else:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "共段总述"})
    return rows


def build_entries(
    vol: str,
    vol_name: str,
    specs: List[EntrySpec],
    paras: Dict[int, str],
) -> List[dict]:
    entries: List[dict] = []
    for i, (name, cat, pf, pt) in enumerate(specs, 1):
        quote = _quote(paras, pf)
        entries.append(
            {
                "史略ID": f"HANSHU_{vol}_{i:02d}",
                "史略名称": name,
                "史略简介": name,
                "原文字句": quote,
                "史略分类": cat,
                "主要史料出处": f"《02汉书·卷{vol}·{vol_name}》",
                "paragraphs": [
                    {"volume": vol_name, "paragraph_from": pf, "paragraph_to": pt}
                ],
            }
        )
    return entries


def build_blocks(
    vol: str,
    total: int,
    cfg: dict,
    paras: Dict[int, str],
    volume_subtype: str,
) -> dict:
    owners: List[OwnerSpec] = cfg["owners"]
    special = cfg["special_excludes"]
    multi: Dict[int, List[Tuple[str, str]]] = cfg.get("multi") or {}

    excl: List[dict] = []
    excl.append({"paragraph_from": 1, "paragraph_to": 1, "exclude_reason": "卷首标题"})
    exmap = _exclude_map(special)
    covered: Set[int] = {1}
    for pf, pt, reason in special:
        excl.append({"paragraph_from": pf, "paragraph_to": pt, "exclude_reason": reason})
        covered.update(range(pf, pt + 1))

    owner_ranges: Dict[str, Tuple[int, int, str]] = {}
    for pf, pt, name, cat in owners:
        owner_ranges[name] = (pf, pt, cat)

    for name, cat, pf, pt in cfg["entries"]:
        if name not in owner_ranges:
            owner_ranges[name] = (pf, pt, cat)

    blocks: List[dict] = []
    for name, cat, pf, pt in cfg["entries"]:
        phrase = _quote(paras, pf, 60)
        blocks.append(
            {
                "name": name,
                "category": cat,
                "paragraph_from": pf,
                "paragraph_to": pt,
                "boundary_evidence": {
                    "open_paragraph": pf,
                    "open_phrase": phrase,
                    "close_paragraph": pt,
                    "close_note": f"用户白名单 manual repair P{pf}–P{pt}",
                },
            }
        )

    # 共段 exclude 区间（合并连续段）
    exclude_reason = "共段总述"
    run_start: Optional[int] = None
    for p in range(2, total + 1):
        if p in covered:
            if run_start is not None:
                excl.append(
                    {
                        "paragraph_from": run_start,
                        "paragraph_to": p - 1,
                        "exclude_reason": exclude_reason,
                    }
                )
                run_start = None
            continue
        owned = p in _owner_map(owners, multi)
        if owned:
            if run_start is not None:
                excl.append(
                    {
                        "paragraph_from": run_start,
                        "paragraph_to": p - 1,
                        "exclude_reason": exclude_reason,
                    }
                )
                run_start = None
        else:
            if run_start is None:
                run_start = p
    if run_start is not None:
        excl.append(
            {
                "paragraph_from": run_start,
                "paragraph_to": total,
                "exclude_reason": exclude_reason,
            }
        )

    excl.sort(key=lambda x: (x["paragraph_from"], x["paragraph_to"]))
    merged: List[dict] = []
    for item in excl:
        if merged and merged[-1]["exclude_reason"] == item["exclude_reason"]:
            if merged[-1]["paragraph_to"] + 1 == item["paragraph_from"]:
                merged[-1]["paragraph_to"] = item["paragraph_to"]
                continue
        merged.append(dict(item))

    multi_segs = []
    for p, items in sorted(multi.items()):
        if len(items) > 1:
            multi_segs.append(
                {
                    "paragraph": p,
                    "owners": [{"name": n, "category": c} for n, c in items],
                }
            )

    return {
        "work": WORK,
        "vol": vol,
        "total_paragraphs": total,
        "volume_subtype": volume_subtype,
        "derived_from": f"{WORK}_{vol}_user_protagonists.json",
        "excludes": merged,
        "blocks": blocks,
        "multi_owner_segments": multi_segs,
    }


def build_protagonists(vol: str, vol_name: str, cfg: dict, volume_subtype: str) -> dict:
    protagonists = []
    for name, cat, pf, pt in cfg["entries"]:
        protagonists.append(
            {
                "name": name,
                "category": cat,
                "rationale": f"《{vol_name}》用户指定史略主人公，叙事块 P{pf}–P{pt}。",
            }
        )
    return {
        "work": WORK,
        "vol": vol,
        "volume_name": vol_name,
        "volume_type_guess": "列传",
        "volume_arc": "C",
        "narrative_mode": "hezhuan",
        "volume_subtype": volume_subtype,
        "skip_reason": None,
        "protagonists": protagonists,
        "excluded_kinds_hint": ["卷首标题", "赞曰", "共段总述"],
    }


def find_skeleton(vol: str) -> Path:
    matches = list(SKEL_DIR.glob(f"{WORK}_{vol}_*_skeleton.json"))
    if not matches:
        raise FileNotFoundError(f"未找到 skeleton: {vol}")
    return matches[0]


def repair_vol(vol: str) -> str:
    vol = vol.zfill(3)
    cfg = VOL_CONFIG[vol]
    idx = json.loads((INDEX_DIR / f"{WORK}_{vol}.json").read_text(encoding="utf-8"))
    total = int(idx["total"])
    vol_name = (idx.get("volume") or "").strip() or cfg.get("volume_name", "")
    if not vol_name:
        sk_old = find_skeleton(vol)
        vol_name = json.loads(sk_old.read_text(encoding="utf-8")).get("volume", "")
    paras = _para_map(idx)

    sk_path = find_skeleton(vol)
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    sk["segment_attribution"] = build_segment_attribution(
        total,
        cfg["owners"],
        cfg["special_excludes"],
        cfg.get("multi") or {},
    )
    sk["entries"] = build_entries(vol, sk["volume"], cfg["entries"], paras)
    sk["total_paragraphs"] = total
    sk["volume_subtype"] = cfg["volume_subtype"]
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    blocks = build_blocks(vol, total, cfg, paras, cfg["volume_subtype"])
    blocks_path = BLOCKS_DIR / f"{WORK}_{vol}_blocks.json"
    blocks_path.write_text(json.dumps(blocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prots = build_protagonists(vol, sk["volume"], cfg, cfg["volume_subtype"])
    prots_path = BLOCKS_DIR / f"{WORK}_{vol}_protagonists.json"
    prots_path.write_text(json.dumps(prots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return f"卷{vol} {sk['volume']}：{len(cfg['entries'])} 条"


def main() -> None:
    vols = sys.argv[1:] if len(sys.argv) > 1 else list(VOL_CONFIG.keys())
    for vol in vols:
        print(repair_vol(vol.zfill(3)))


if __name__ == "__main__":
    main()
