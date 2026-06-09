#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 文明 tab 配图：从微信素材目录复制并重命名为 {CODE}.png。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".tmp" / "civ-tab-import"
DEFAULT_SRC = Path(
    r"C:\Users\user\xwechat_files\wxid_0h9hbfgcgqd122_c826\msg\file\2026-05\文明配图和icon\文明tab配图"
)

# sort, 文件名前缀, display_name, code, color_hex
CIV_18 = [
    (1, "01_华夏", "华夏", "HX", "#84572F"),
    (2, "02_朝鲜", "朝鲜", "CX", "#9ABCC8"),
    (3, "03_日本", "日本", "RB", "#EDD5C0"),
    (4, "04_东南亚", "东南亚", "DNY", "#92ADA4"),
    (5, "05_中亚", "中亚", "ZY", "#C4A882"),
    (6, "06_北亚", "北亚", "BY", "#8B9EB5"),
    (7, "07_南亚", "南亚", "NY", "#E0C088"),
    (8, "08_西亚", "西亚", "XY", "#D4B098"),
    (9, "09_南欧", "南欧", "NO", "#92ADA4"),
    (10, "10_东欧", "东欧", "DO", "#9ABCC8"),
    (11, "11_西欧", "西欧", "XO", "#B3D9E0"),
    (12, "12_北欧", "北欧", "BO", "#A8C4D4"),
    (13, "13_北非", "北非", "BF", "#F1A805"),
    (14, "14_西非", "西非", "XF", "#84572F"),
    (15, "15_东非", "东非", "DF", "#B8956A"),
    (16, "16_中美", "中美", "ZM", "#F2D6A1"),
    (17, "17_北美", "北美", "BM", "#7F96B8"),
    (18, "18_南美", "南美", "NM", "#D4B098"),
]


def main():
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src_dir.is_dir():
        print(f"源目录不存在: {src_dir}", file=sys.stderr)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for sort_order, prefix, display_name, code, color_hex in CIV_18:
        matches = list(src_dir.glob(f"{prefix}*.png"))
        if not matches:
            print(f"未找到: {prefix}*.png in {src_dir}", file=sys.stderr)
            sys.exit(1)
        src = matches[0]
        dst = OUT / f"{code}.png"
        shutil.copy2(src, dst)
        manifest.append(
            {
                "sortOrder": sort_order,
                "displayName": display_name,
                "code": code,
                "colorHex": color_hex,
                "sourceFile": src.name,
                "stagedFile": dst.name,
                "cosKey": f"histomap/civ-tab/{code}.png",
            }
        )
        print(f"OK {src.name} -> {dst.name}")

    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {manifest_path} ({len(manifest)} items)")


if __name__ == "__main__":
    main()
