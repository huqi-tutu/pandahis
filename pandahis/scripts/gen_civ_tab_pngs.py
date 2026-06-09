#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成本地「一级地域 Tab」缩略图（Morandi 圆角块 + accent 色），对齐首页沉浸横滑 Tab 视觉。

设计要点：奶油底、柔和渐变、大圆角、无文字（与稿一致）。后续可用 user-gpt-image-2-imagegen
text-to-image 生成更细插画，再经 COS 上传替换 tab_image_url。

用法:
  pip install pillow
  python scripts/gen_civ_tab_pngs.py
  python scripts/gen_civ_tab_pngs.py --out miniapp/images/civ-tab   # 仅调试：打入包（不推荐）

默认输出到仓库 .tmp/civ-tab/，便于再用腾讯云 COS MCP 上传为在线 URL，避免撑大小程序包。
"""
from __future__ import annotations

import argparse
from pathlib import Path


CIVS = [
    ("HX", "#84572F"),
    ("CX", "#9ABCC8"),
    ("RB", "#EDD5C0"),
    ("DNY", "#92ADA4"),
    ("ZY", "#C4A882"),
    ("BY", "#8B9EB5"),
    ("NY", "#E0C088"),
    ("XY", "#D4B098"),
    ("NO", "#92ADA4"),
    ("DO", "#9ABCC8"),
    ("XO", "#B3D9E0"),
    ("BO", "#A8C4D4"),
    ("BF", "#F1A805"),
    ("XF", "#84572F"),
    ("DF", "#B8956A"),
    ("ZM", "#F2D6A1"),
    ("BM", "#7F96B8"),
    ("NM", "#D4B098"),
]


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="输出目录（默认: 仓库根目录 .tmp/civ-tab）",
    )
    args = ap.parse_args()
    from PIL import Image, ImageDraw

    root = Path(__file__).resolve().parents[1]
    out_dir = args.out if args.out is not None else (root / ".tmp" / "civ-tab")
    out_dir.mkdir(parents=True, exist_ok=True)
    size = 256
    rad = 70
    for code, hx in CIVS:
        accent = hex_to_rgb(hx)
        cream = (252, 249, 244)
        wash = mix(cream, accent, 0.14)
        edge = mix(accent, (35, 38, 48), 0.4)

        im = Image.new("RGB", (size, size), cream)
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((10, 10, size - 10, size - 10), radius=rad, fill=wash, outline=edge, width=3)
        cx, cy = size // 2, size // 2
        rr = 52
        inner = mix(wash, accent, 0.35)
        dr.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=inner, outline=None)
        rr2 = 28
        core = mix(inner, (255, 255, 255), 0.25)
        dr.ellipse((cx - rr2, cy - rr2, cx + rr2, cy + rr2), fill=core, outline=None)

        path = out_dir / f"{code}.png"
        im.save(path, "PNG", optimize=True)
        print("Wrote", path)


if __name__ == "__main__":
    main()
