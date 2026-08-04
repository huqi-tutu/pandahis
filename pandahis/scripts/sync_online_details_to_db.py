#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 11新标注条目翻译 + 06朝代知识补全 详情同步到线上 historical_box_detail。

用法：
  # 全量（按 online 索引过滤，删除非 11/06 详情）
  python3 scripts/sync_online_details_to_db.py

  # 仅 upsert 本地 11+06 文件，不 prune
  python3 scripts/sync_online_details_to_db.py --no-prune

  # 单条（promote 后增量）
  python3 scripts/sync_online_details_to_db.py --id GLBL_00730

未来新增翻译：写入 data/11新标注条目翻译/ 后运行本脚本即可。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
TRANSLATE_DIR = TOOLS / "historiography-translate"
ONLINE_INDEX = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(TRANSLATE_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSLATE_DIR))

from online_detail_sync import (  # noqa: E402
    build_online_detail_rows,
    find_json_by_id,
    load_online_ids,
    row_from_detail_json,
    sync_online_details,
)
from lib.remote_sync import sync_translate_detail  # noqa: E402
from paths_config import histograph_paths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="11+06 详情 → MySQL")
    parser.add_argument("--index", type=Path, default=ONLINE_INDEX, help="线上索引（过滤用）")
    parser.add_argument("--no-index-filter", action="store_true", help="不按 online 索引过滤")
    parser.add_argument("--no-prune", action="store_true", help="不删除非 11/06 的线上详情")
    parser.add_argument("--id", dest="entry_id", help="单条 GLBL ID")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.entry_id:
        eid = args.entry_id.strip()
        paths = histograph_paths()
        row = None
        p11 = find_json_by_id(paths["translate_output_v2"], eid)
        if p11:
            row = row_from_detail_json(p11, detail_source="translate")
        if not row:
            p06 = find_json_by_id(paths["dynasty_knowledge_details"], eid)
            if p06:
                row = row_from_detail_json(p06, detail_source="compose")
        if not row:
            print(f"❌ {eid} 在 11/06 中无可用详情", file=sys.stderr)
            return 1
        if args.dry_run:
            print(f"dry-run: 将 upsert {eid}（{len(row['translate_detail'])} 字）")
            return 0
        import json

        src_path = p11 or p06
        data = json.loads(src_path.read_text(encoding="utf-8"))
        ok, msg = sync_translate_detail(
            eid,
            row["translate_detail"],
            source_original=data.get("史料原文"),
            source_citation=row.get("source_citation"),
            detail_source=row.get("detail_source"),
        )
        print(f"{'✅' if ok else '❌'} {msg}")
        return 0 if ok else 1

    online_ids = None
    if not args.no_index_filter:
        if not args.index.is_file():
            print(f"缺少线上索引: {args.index}", file=sys.stderr)
            return 1
        online_ids = load_online_ids(args.index)
        print(f"线上索引过滤: {len(online_ids)} 条")

    if args.no_prune:
        rows, stats = build_online_detail_rows(online_ids)
        print("详情来源（仅 11 + 06）:", stats)
        if args.dry_run:
            print(f"dry-run: 将 upsert {len(rows)} 条（不 prune）")
            return 0
        from lib.remote_sync import _connect, ensure_schema, upsert_translate_detail, _ensure_detail_source_column

        conn = _connect()
        try:
            with conn.cursor() as cursor:
                ensure_schema(cursor)
                _ensure_detail_source_column(cursor)
                for row in rows:
                    upsert_translate_detail(
                        cursor,
                        row["box_id"],
                        row["translate_detail"],
                        row.get("source_original_json"),
                        row.get("source_citation"),
                        detail_source=row.get("detail_source"),
                    )
            conn.commit()
            print(f"✅ upsert {len(rows)} 条（未 prune）")
            return 0
        except Exception as exc:
            conn.rollback()
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        finally:
            conn.close()

    ok, msg, stats = sync_online_details(online_ids, dry_run=args.dry_run)
    print("详情来源（仅 11 + 06）:", stats)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
