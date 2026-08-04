#!/usr/bin/env python3
"""批量补全 五级细坐标 / 六级段落锚点 / 原文出处（规则生成，不调 LLM）。

目标：
  - data/10新标注条目/史略索引_史记汉书.json（GLBL 条目，按母本+合并规则）
  - data/10新标注条目/*_skeleton.json（卷级 SSOT，可选同步）

用法:
  python3 patch_detail_coords.py
  python3 patch_detail_coords.py --dry-run
  python3 patch_detail_coords.py --index-only
  python3 patch_detail_coords.py --skeleton-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from detail_coords import (  # noqa: E402
    build_paragraph_anchor,
    build_wuji_coord,
    build_yuanwen_chuchu,
    fill_all_detail_coords,
    volume_num_from_sources,
    work_short_name,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _muban_paragraphs(entry: dict) -> List[dict]:
    paras = entry.get("paragraphs") or []
    muban = [p for p in paras if p.get("role") == "母本"]
    return muban if muban else paras[:1]


def _merge_glbl_anchor(entry: dict) -> str:
    """跨源合并锚点，与 merge_global_entries._merge_anchor 一致。"""
    parts: List[str] = []
    for pg in entry.get("paragraphs") or []:
        a, b = int(pg["paragraph_from"]), int(pg["paragraph_to"])
        parts.append(f"P{a}" if a == b else f"P{a}-P{b}")
    if not parts:
        return ""
    inner = ",".join(parts)
    return f"[{inner}]"


def fill_glbl_detail_coords(entry: dict) -> dict:
    """为全局索引单条写入三字段。"""
    muban_id = (entry.get("母本史略ID") or "").strip()
    work_id = (entry.get("母本著作") or "").strip()
    muban_paras = _muban_paragraphs(entry)

    pseudo = {
        "史略ID": muban_id,
        "史略分类": entry.get("史略分类", ""),
        "paragraphs": muban_paras,
        "主要史料出处": entry.get("主要史料出处", ""),
    }
    vol_num = volume_num_from_sources(muban_id, *(p.get("vol", "") for p in muban_paras))
    vol_name = (muban_paras[0].get("volume") or "").strip() if muban_paras else ""

    entry["五级细坐标"] = build_wuji_coord(pseudo, work_id=work_id, vol_num=vol_num)

    if (entry.get("来源条目数") or 1) > 1:
        entry["六级段落锚点"] = _merge_glbl_anchor(entry)
    else:
        pseudo_all = {**pseudo, "paragraphs": entry.get("paragraphs") or []}
        entry["六级段落锚点"] = build_paragraph_anchor(pseudo_all)

    entry["原文出处"] = build_yuanwen_chuchu(pseudo, vol_name=vol_name)
    return entry


def patch_index(index_path: Path, *, dry_run: bool = False) -> int:
    entries = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"期望 JSON 数组: {index_path}")
    for entry in entries:
        fill_glbl_detail_coords(entry)
    if not dry_run:
        index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(entries)


def patch_skeletons(skeleton_dir: Path, *, dry_run: bool = False) -> int:
    total = 0
    for fp in sorted(skeleton_dir.glob("*_skeleton.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        work_id = "01史记" if fp.name.startswith("01") else "02汉书"
        n = fill_all_detail_coords(data, work_id=work_id, json_path=str(fp))
        if n:
            total += n
            if not dry_run:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument("--skeleton-only", action="store_true")
    args = parser.parse_args()

    root = _repo_root()
    v2 = root / "data" / "10新标注条目"
    index_path = v2 / "史略索引_史记汉书.json"

    do_index = not args.skeleton_only
    do_skel = not args.index_only

    if do_index:
        if not index_path.is_file():
            print(f"缺少索引: {index_path}")
            return 1
        n = patch_index(index_path, dry_run=args.dry_run)
        print(f"索引 {index_path.name}: {n} 条已补三字段")

    if do_skel:
        n = patch_skeletons(v2, dry_run=args.dry_run)
        print(f"V2 skeleton: {n} 条 entry 已补三字段")

    if not args.dry_run:
        print("✅ 完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
