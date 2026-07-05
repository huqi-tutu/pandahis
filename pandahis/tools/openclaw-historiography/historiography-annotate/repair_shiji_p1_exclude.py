#!/usr/bin/env python3
"""修复史记 006/008/009/010：P1 误 exclude → 归入主轴 block。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # pandahis/pandahis（含 data/）
DATA = ROOT / "data"
ANNOTATE = DATA / "03索引标注条目"
INTERMEDIATE = DATA / "05工作流中间产物" / "标注"
IDX_DIR = ANNOTATE / "段落索引"

REPAIRS = {
    "006": {"protagonist": ("秦始皇", "君王")},
    "008": {"protagonist": ("汉高祖", "君王")},
    "009": {"protagonist": ("吕太后", "宗戚")},
    "010": {"protagonist": ("汉文帝", "君王")},
}


def opening_quote(text: str, min_len: int = 12) -> str:
    t = (text or "").strip()
    if len(t) <= min_len:
        return t
    return t[: min(len(t), 80)]


def fix_blocks(vol: str) -> bool:
    bp = INTERMEDIATE / f"01史记_{vol}_blocks.json"
    if not bp.exists():
        print(f"  跳过 blocks {vol}: 不存在")
        return False
    data = json.loads(bp.read_text(encoding="utf-8"))
    excludes = []
    for ex in data.get("excludes") or []:
        pf, pt = int(ex["paragraph_from"]), int(ex["paragraph_to"])
        if pf == 1 and pt == 1:
            continue
        excludes.append(ex)
    data["excludes"] = excludes
    name, cat = REPAIRS[vol]["protagonist"]
    for blk in data.get("blocks") or []:
        if (blk.get("name") or "").strip() == name and (blk.get("category") or "").strip() == cat:
            if int(blk.get("paragraph_from") or 0) == 2:
                blk["paragraph_from"] = 1
    bp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  ✅ blocks {vol}")
    return True


def fix_skeleton(vol: str) -> bool:
    matches = sorted(ANNOTATE.glob(f"01史记_{vol}_*_skeleton.json"))
    if not matches:
        print(f"  跳过 skeleton {vol}: 不存在")
        return False
    sk_path = matches[0]
    idx = json.loads((IDX_DIR / f"01史记_{vol}.json").read_text(encoding="utf-8"))
    p1_text = idx["paragraphs"][0]["text"]
    name, cat = REPAIRS[vol]["protagonist"]

    data = json.loads(sk_path.read_text(encoding="utf-8"))
    attr = data.get("segment_attribution") or []
    if attr and attr[0].get("paragraph") == 1:
        attr[0] = {
            "paragraph": 1,
            "owners": [{"name": name, "category": cat}],
        }

    for ent in data.get("entries") or []:
        if (ent.get("史略名称") or "").strip() != name:
            continue
        for pr in ent.get("paragraphs") or []:
            if int(pr.get("paragraph_from") or 0) == 2:
                pr["paragraph_from"] = 1
        ent["原文字句"] = opening_quote(p1_text)
        # 更新原文出处若存在
        if ent.get("原文出处"):
            parts = []
            for pr in ent.get("paragraphs") or []:
                pf, pt = int(pr["paragraph_from"]), int(pr["paragraph_to"])
                if pf == pt:
                    parts.append(f"P{pf}")
                else:
                    parts.append(f"P{pf}-P{pt}")
            vol_name = data.get("volume") or ""
            ent["原文出处"] = f"{vol_name}·{','.join(parts)}"

    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  ✅ skeleton {vol} → {sk_path.name}")
    return True


def main() -> None:
    for vol in REPAIRS:
        print(f"卷 {vol}:")
        fix_blocks(vol)
        fix_skeleton(vol)
    print("完成")


if __name__ == "__main__":
    main()
