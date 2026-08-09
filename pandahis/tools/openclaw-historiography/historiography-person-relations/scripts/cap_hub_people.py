#!/usr/bin/env python3
"""将各二级枢纽下直接人物截断为最多 10 人（按重要/紧密度保留）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sanitize_relations import sanitize_relation_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Cap hub direct people to 10 by importance")
    parser.add_argument("paths", nargs="+", help="JSON file or directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files: list[Path] = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*关系表.json")))
        elif path.is_file():
            files.append(path)

    changed = 0
    for path in files:
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            continue
        new_recs, notes = sanitize_relation_records(records)
        if not notes and new_recs == records:
            continue
        # 仅当内容实质变化时写入
        if json.dumps(new_recs, ensure_ascii=False) == json.dumps(records, ensure_ascii=False):
            continue
        print(f"{path.name}: {len(records)}→{len(new_recs)}")
        for n in notes:
            print(f"  {n}")
        if not args.dry_run:
            path.write_text(
                json.dumps(new_recs, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        changed += 1
    print(f"\n{'would change' if args.dry_run else 'updated'}: {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
