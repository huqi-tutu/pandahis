#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
线上 cutover：V2+06 合并索引 → historical_box；
详情仅 11新标注条目翻译 + 06朝代知识补全 → historical_box_detail。

步骤：
  1. build_online_index（可选 --skip-build）
  2. import_box_index_json upsert + delete_orphans（移除不在 online 索引中的 V1 条）
  3. 11+06 详情 upsert，prune 非 11/06 详情（含 V1/04 残留）

不触碰：box_graph_edge/node、box_critique、box_relic（任务关系、评述、见证）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONLINE_INDEX = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"

from online_detail_sync import load_online_ids, sync_online_details  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="线上索引 cutover → MySQL")
    parser.add_argument("--skip-build", action="store_true", help="跳过 build_online_index")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引 import（仅同步详情）")
    parser.add_argument("--index", type=Path, default=ONLINE_INDEX)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-details", action="store_true")
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_build and not args.skip_index:
        code = subprocess.call([py, str(ROOT / "scripts" / "build_online_index.py")])
        if code != 0:
            return code

    if not args.index.is_file():
        print(f"缺少线上索引: {args.index}", file=sys.stderr)
        return 1

    online_ids = load_online_ids(args.index)
    print(f"线上索引: {len(online_ids)} 条 → {args.index}")

    if not args.skip_index:
        import_cmd = [
            py,
            str(ROOT / "scripts" / "import_box_index_json.py"),
            "--json",
            str(args.index),
        ]
        if args.dry_run:
            import_cmd.append("--dry-run")
        rc = subprocess.call(import_cmd)
        if rc != 0:
            return rc

    if args.skip_details:
        return 0

    ok, msg, stats = sync_online_details(online_ids, dry_run=args.dry_run)
    print("详情来源（仅 11 + 06）:", stats)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
