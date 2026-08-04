#!/usr/bin/env python3
"""为史略索引回填 史略来源 字段。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from entry_source import (  # noqa: E402
    SOURCE_EXTRACT,
    SOURCE_SUPPLEMENT,
    backfill_entries,
    infer_entry_source,
)
from paths_config import histograph_paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="回填史略索引 史略来源")
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="默认 data/03索引标注条目/史略索引_01至02.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = histograph_paths()
    index_path = args.index or paths["global_index"]
    data = json.loads(index_path.read_text(encoding="utf-8"))
    is_list = isinstance(data, list)
    entries = data if is_list else (data.get("entries") or [])

    new_entries, changed = backfill_entries(entries)
    extract_n = sum(1 for e in new_entries if infer_entry_source(e) == SOURCE_EXTRACT)
    supplement_n = sum(1 for e in new_entries if infer_entry_source(e) == SOURCE_SUPPLEMENT)

    print(f"索引: {index_path}")
    print(f"总条目: {len(new_entries)}")
    print(f"  史料提取: {extract_n}")
    print(f"  模型补全: {supplement_n}")
    print(f"需写入变更: {changed}")

    if args.dry_run or changed == 0:
        return 0

    backfill_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if is_list:
        index_path.write_text(
            json.dumps(new_entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        data["entries"] = new_entries
        data["entry_source_backfill_at"] = backfill_at
        index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
