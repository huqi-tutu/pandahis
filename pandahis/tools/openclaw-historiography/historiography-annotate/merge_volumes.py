#!/usr/bin/env python3
"""merge_volumes.py — 将单卷 skeleton 合并为著作级条目索引。

用法:
  python3 merge_volumes.py <著作前缀>    # 例如: python3 merge_volumes.py 01史记
  python3 merge_volumes.py --all         # 合并所有著作

产出:
  $HISTOGRAPH_ROOT/data/03索引标注条目/{著作}_条目索引.json
"""

import json
import os
import sys
from pathlib import Path
from collections import Counter

from lib_config import get_histograph_root, paths
from generate_stats import generate_stats

def find_volume_files(annotations_dir: Path, work_prefix: str) -> list[Path]:
    """扫描 directory，找出指定著作的所有卷 skeleton 文件。"""
    files = sorted(annotations_dir.glob(f"{work_prefix}_*_skeleton.json"))
    return files

def merge_volumes(annotations_dir: Path, work_prefix: str) -> dict:
    """合并单卷 skeleton → 著作级索引。"""
    vol_files = find_volume_files(annotations_dir, work_prefix)
    if not vol_files:
        print(f"⚠️ 未找到 {work_prefix} 的卷 skeleton 文件")
        return None

    volumes = []
    all_entries = []

    for vf in vol_files:
        with open(vf, 'r', encoding='utf-8') as f:
            sk = json.load(f)

        volumes.append({
            "volume": sk["volume"],
            "source_file": sk["source_file"],
            "原文路径": sk.get("原文路径", ""),
            "total_paragraphs": sk["total_paragraphs"],
            "volume_type": sk.get("volume_type", "纪传叙事"),
        })

        all_entries.extend(sk.get("entries", []))

    merged = {
        "著作": work_prefix,
        "卷数": len(volumes),
        "volumes": volumes,
        "entries": all_entries,
        "audit_revision": {
            "deleted_entry_ids": [],
            "deleted_reasons": {}
        }
    }

    # 统计
    cats = Counter()
    for e in all_entries:
        cats[e["史略分类"]] += 1

    return merged, cats

def main():
    annotations_dir = paths()["annotations"]

    if len(sys.argv) < 2:
        print("用法: merge_volumes.py <著作前缀>  或  merge_volumes.py --all")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--all":
        # 扫描所有著作前缀
        prefixes = set()
        for f in annotations_dir.glob("*_*_*_skeleton.json"):
            # 文件名格式: 01史记_001_五帝本纪_skeleton.json
            parts = f.name.split('_')
            prefixes.add(f"{parts[0]}_{parts[1]}")
        
        if not prefixes:
            print("⚠️ 未找到任何 skeleton 文件")
            sys.exit(1)

        for prefix in sorted(prefixes):
            result = merge_volumes(annotations_dir, prefix)
            if result:
                merged, cats = result
                out_path = annotations_dir / f"{prefix}_条目索引.json"
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(merged, f, ensure_ascii=False, indent=2)
                print(f"✅ {prefix}: {len(merged['volumes'])} 卷, {len(merged['entries'])} 条 → {out_path.name}")
                for cat, count in sorted(cats.items()):
                    print(f"   {cat}: {count}")
                # 同步生成统计
                stats_dir = paths()["stats"]
                generate_stats(str(out_path), str(stats_dir))
    else:
        prefix = arg
        result = merge_volumes(annotations_dir, prefix)
        if result:
            merged, cats = result
            out_path = annotations_dir / f"{prefix}_条目索引.json"
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            print(f"✅ {prefix}: {len(merged['volumes'])} 卷, {len(merged['entries'])} 条 → {out_path.name}")
            for cat, count in sorted(cats.items()):
                print(f"   {cat}: {count}")
            # 同步生成统计
            stats_dir = paths()["stats"]
            generate_stats(str(out_path), str(stats_dir))
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
