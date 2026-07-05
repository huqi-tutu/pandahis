#!/usr/bin/env python3
"""批量将 skeleton 君纪名对齐为帝王.json 标准名（刘邦→汉高祖等）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from junji_naming import collect_junji_violations, rename_junji_in_skeleton
from emperor_resolve import align_skeleton_emperors


def repair_file(path: Path, *, dry_run: bool = False) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    before = collect_junji_violations(data)
    data, changes = align_skeleton_emperors(data)
    after = collect_junji_violations(data)

    if not changes and not before:
        return 0

    print(f"\n📄 {path.name}")
    for c in changes:
        print(f"   · {c}")
    if after:
        print(f"   ⚠️  仍有 {len(after)} 项无法自动修复")
        for v in after[:5]:
            print(f"      {v}")

    if not dry_run and changes:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("   ✅ 已写入")
    elif dry_run and changes:
        print("   (dry-run，未写入)")
    return len(changes)


def main() -> int:
    parser = argparse.ArgumentParser(description="修复君纪裸称命名")
    parser.add_argument("paths", nargs="*", help="skeleton 文件或目录")
    parser.add_argument("--work", help="如 01A尚书，修复该著作全部 skeleton")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files: list[Path] = []
    if args.work:
        import os

        root = Path(
            os.environ.get("HISTOGRAPH_ROOT", Path.home() / "Desktop" / "历史图谱")
        )
        ann = paths()["annotations"]
        files.extend(sorted(ann.glob(f"{args.work}_*_skeleton.json")))

    for p in args.paths:
        pp = Path(p)
        if pp.is_dir():
            files.extend(sorted(pp.glob("*_skeleton.json")))
        elif pp.is_file():
            files.append(pp)

    if not files:
        print("未找到 skeleton 文件", file=sys.stderr)
        return 1

    total_changes = 0
    for fp in files:
        total_changes += repair_file(fp, dry_run=args.dry_run)

    print(f"\n合计变更: {total_changes} 处（{len(files)} 个文件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
