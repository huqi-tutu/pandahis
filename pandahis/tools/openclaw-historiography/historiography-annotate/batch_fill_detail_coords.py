#!/usr/bin/env python3
"""批量补全 Step4 细坐标：原文出处、五级细坐标、六级段落锚点。"""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from detail_coords import DETAIL_FIELDS, fill_all_detail_coords  # noqa: E402
from emperor_resolve import work_id_from_skeleton  # noqa: E402
from lib_config import paths  # noqa: E402


def missing_detail(entry: dict) -> bool:
    return any(not (entry.get(k) or "").strip() for k in DETAIL_FIELDS)


def process_file(path: Path, *, dry_run: bool = False) -> tuple[int, int]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries") or []
    if not entries:
        return 0, 0
    need = sum(1 for e in entries if missing_detail(e))
    if need == 0:
        return 0, 0
    work_id = work_id_from_skeleton(data, str(path))
    filled = fill_all_detail_coords(data, work_id=work_id, json_path=str(path))
    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return need, filled


def main() -> int:
    parser = argparse.ArgumentParser(description="批量补全 Step4 细坐标三字段")
    parser.add_argument(
        "works",
        nargs="+",
        help="著作前缀，如 01史记 01A尚书 01E吴越春秋",
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=None,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check-final", action="store_true", help="补完后跑 check_format final")
    args = parser.parse_args()
    if args.base is None:
        args.base = paths()["annotations"]

    py = sys.executable
    check_script = SKILL / "check_format.py"
    total_files = touched = total_need = total_filled = 0
    failed_checks: list[str] = []

    for work in args.works:
        files = sorted(
            f
            for f in args.base.glob(f"{work}_*_skeleton.json")
            if "_backup" not in str(f)
        )
        w_need = w_filled = w_touched = 0
        for fp in files:
            total_files += 1
            need, filled = process_file(fp, dry_run=args.dry_run)
            if need:
                w_touched += 1
                w_need += need
                w_filled += filled
                print(f"  ✓ {fp.name}: {filled} 条")
        total_need += w_need
        total_filled += w_filled
        touched += w_touched
        print(f"\n{work}: {len(files)} 卷，补全 {w_touched} 卷 / {w_filled} 条")

        if args.check_final and not args.dry_run:
            for fp in files:
                r = subprocess.run(
                    [py, str(check_script), str(fp), "--phase", "final"],
                    capture_output=True,
                    text=True,
                )
                if r.returncode != 0:
                    failed_checks.append(fp.name)

    print(
        f"\n✅ 合计 {total_files} 卷，写入 {touched} 卷，"
        f"补 {total_filled} 条细坐标"
    )
    if args.check_final and failed_checks:
        print(f"❌ final 未通过 {len(failed_checks)} 卷（前 10）:")
        for name in failed_checks[:10]:
            print(f"  - {name}")
        return 1
    if args.check_final and not args.dry_run:
        print("✅ 全部卷 final 终检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
