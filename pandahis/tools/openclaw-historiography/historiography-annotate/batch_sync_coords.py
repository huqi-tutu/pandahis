#!/usr/bin/env python3
"""批量：帝王表对齐坐标链 + 补全坐标 ID。"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from coordinate_index import migrate_entry_fields  # noqa: E402
from fill_fields import (  # noqa: E402
    reconcile_entries_coord_ids,
    reconcile_entries_coords_from_emperor,
)
from coordinate_index import (  # noqa: E402
    build_dynasty_index_from_json,
    build_emperor_index,
    build_regime_index,
)
from lib_config import paths  # noqa: E402


def process_file(path: Path, *, dry_run: bool = False) -> tuple[int, int]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries") or []
    if not entries:
        return 0, 0
    ei = build_emperor_index()
    ri = build_regime_index()
    di = build_dynasty_index_from_json()
    for e in entries:
        migrate_entry_fields(e)
    chain_logs = reconcile_entries_coords_from_emperor(
        entries, emperor_index=ei, regime_index=ri
    )
    id_logs = reconcile_entries_coord_ids(
        entries, emperor_index=ei, regime_index=ri, dynasty_index=di
    )
    if not dry_run and (chain_logs or id_logs):
        data["entries"] = entries
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return len(chain_logs), len(id_logs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern", help="如 01史记 或 glob")
    parser.add_argument("--base", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.base is None:
        args.base = paths()["annotations"]

    if "*" in args.pattern:
        files = sorted(Path(p) for p in glob.glob(str(args.base / args.pattern)))
    else:
        files = sorted(args.base.glob(f"{args.pattern}_*_skeleton.json"))
    files = [f for f in files if "_backup" not in str(f)]

    total_chain = total_id = 0
    touched = 0
    for fp in files:
        c, i = process_file(fp, dry_run=args.dry_run)
        if c or i:
            touched += 1
            total_chain += c
            total_id += i
            print(f"  {fp.name}: 坐标链 {c} | ID {i}")

    print(f"\n✅ {len(files)} 卷，改动 {touched} 卷，坐标链 {total_chain}，ID {total_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
