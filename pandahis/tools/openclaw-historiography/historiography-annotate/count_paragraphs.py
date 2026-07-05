#!/usr/bin/env python3
"""Step 0：统计原文段落数（标注前必须先跑）。

用法:
  python3 count_paragraphs.py --work 01A尚书 --vol 058
  python3 count_paragraphs.py /path/to/01A尚书_058_周书_秦誓_skeleton.json
  python3 count_paragraphs.py --src /path/to/01A尚书_058_周书_秦誓.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib_config import paths
from paragraph_utils import (
    count_source_paragraphs,
    resolve_source_file,
    split_mode_for_work,
    split_paragraphs,
    vol_from_skeleton_path,
    work_from_skeleton_path,
)


def skeleton_for(work: str, vol: str) -> Path | None:
    vol = vol.zfill(3)
    matches = sorted(paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None


def main() -> None:
    parser = argparse.ArgumentParser(description="统计原文段落数（Step 0 硬门）")
    parser.add_argument("json_path", nargs="?", help="skeleton.json（可选）")
    parser.add_argument("--work", help="著作前缀，如 01A尚书")
    parser.add_argument("--vol", help="卷号，如 058")
    parser.add_argument("--src", help="直接指定原文 .txt")
    parser.add_argument("--preview", type=int, default=0, help="预览前 N 段")
    args = parser.parse_args()

    skeleton: Path | None = None
    data: dict = {}

    if args.json_path:
        skeleton = Path(args.json_path)
        if skeleton.exists():
            data = json.loads(skeleton.read_text(encoding="utf-8"))
    elif args.work and args.vol:
        skeleton = skeleton_for(args.work, args.vol)
        if skeleton and skeleton.exists():
            data = json.loads(skeleton.read_text(encoding="utf-8"))
    elif not args.src:
        parser.error("需要 json_path、或 --work + --vol、或 --src")

    if args.src:
        src = Path(args.src)
        work = args.work or ""
    else:
        work = args.work or (work_from_skeleton_path(skeleton) if skeleton else "")
        vol = args.vol or (vol_from_skeleton_path(skeleton) if skeleton else "")
        src = resolve_source_file(data, skeleton) if skeleton and skeleton.exists() else None
        if not src and work and vol:
            vol = vol.zfill(3)
            src_root = paths()["sources"]
            for sub in sorted(src_root.iterdir()):
                if not sub.is_dir():
                    continue
                matches = sorted(sub.glob(f"*_{vol}_*.txt"))
                if matches:
                    src = matches[0]
                    break
        if not src:
            print("❌ 无法定位原文文件，请检查 原文路径 或 --src")
            sys.exit(1)
        if not work and skeleton:
            work = work_from_skeleton_path(skeleton)

    text = src.read_text(encoding="utf-8")
    mode = split_mode_for_work(work, text)
    paras = split_paragraphs(text, mode)
    actual = len(paras)

    print(f"\n📄 {src.name}")
    print(f"   著作: {work or '(未知)'}")
    print(f"   切分模式: {mode} ({'全角缩进行' if mode == 'indent' else '非空行'})")
    print(f"   实际段落数: {actual}")

    if data:
        declared = data.get("total_paragraphs")
        attr_n = len(data.get("segment_attribution", []))
        print(f"   skeleton total_paragraphs: {declared}")
        print(f"   skeleton 归属表行数: {attr_n}")
        if declared != actual or attr_n != actual:
            print(f"\n❌ 与 skeleton 不一致，Step1 必须改为 {actual} 段并重写归属表")
            sys.exit(1)
        print("\n✅ skeleton 段数与原文一致")
    else:
        print(f"\n✅ 标注时请设 total_paragraphs={actual}，归属表写满 {actual} 行")

    if args.preview > 0:
        print(f"\n--- 前 {min(args.preview, actual)} 段预览 ---")
        for i, p in enumerate(paras[: args.preview], 1):
            print(f"  [{i:02d}] {p[:72]}{'…' if len(p) > 72 else ''}")


if __name__ == "__main__":
    main()
