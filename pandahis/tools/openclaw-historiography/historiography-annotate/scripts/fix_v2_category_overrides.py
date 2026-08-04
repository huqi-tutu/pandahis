#!/usr/bin/env python3
"""V2 skeleton 分类覆盖（人工裁定 SSOT）。

当前：董贤、范蠡、邓通、韩嫣、李延年 → 文臣
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

WENCHEN_NAMES = frozenset({"董贤", "范蠡", "邓通", "韩嫣", "李延年"})
TARGET = "文臣"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def fix_skeleton(data: dict) -> Tuple[int, List[str]]:
    changes: List[str] = []
    count = 0

    for entry in data.get("entries") or []:
        name = str(entry.get("史略名称") or "").strip()
        if name not in WENCHEN_NAMES:
            continue
        old = str(entry.get("史略分类") or "").strip()
        if old != TARGET:
            entry["史略分类"] = TARGET
            changes.append(f"entry {entry.get('史略ID')}: {name} {old} → {TARGET}")
            count += 1

    for seg in data.get("segment_attribution") or []:
        for owner in seg.get("owners") or []:
            name = str(owner.get("name") or "").strip()
            if name not in WENCHEN_NAMES:
                continue
            old = str(owner.get("category") or "").strip()
            if old != TARGET:
                owner["category"] = TARGET
                count += 1

    return count, changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = _repo_root()
    target = root / "data" / "10新标注条目"
    total = 0
    for fp in sorted(target.glob("*_skeleton.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        n, log = fix_skeleton(data)
        if n:
            total += n
            print(f"{fp.name}: {n} changes")
            for line in log:
                print(f"  {line}")
            if not args.dry_run:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n合计 {total} 处分类修正")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
