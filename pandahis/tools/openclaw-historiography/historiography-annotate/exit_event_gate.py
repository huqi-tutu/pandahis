#!/usr/bin/env python3
"""标注 gate：君王条目退场句错挂检测。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from transition_spans import validate_entry_exit_attribution  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="检测君王条目退场句错挂")
    parser.add_argument("--json", type=Path, required=True, help="史略索引或 skeleton JSON")
    parser.add_argument("--entry-id", default=None)
    args = parser.parse_args()

    data = json.loads(args.json.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    if not entries and "segment_attribution" in data:
        entries = data.get("entries") or []

    issues: list[str] = []
    for entry in entries:
        eid = str(entry.get("史略ID") or "")
        if args.entry_id and eid != args.entry_id:
            continue
        for msg in validate_entry_exit_attribution(entry):
            issues.append(f"{eid or entry.get('史略名称')}: {msg}")

    if issues:
        print("❌ 退场句归属问题:")
        for line in issues:
            print(f"  - {line}")
        return 1
    print("✅ 退场句归属检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
