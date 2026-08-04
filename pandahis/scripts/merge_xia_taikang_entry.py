#!/usr/bin/env python3
"""将 GLBL_00993 太康失国 merge 进全局索引并同步 MySQL。"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data/03索引标注条目/史略索引_01至02.json"
DK = ROOT / "data/06朝代知识补全/索引条目/夏_事略典制论著.json"
DETAIL = ROOT / "data/06朝代知识补全/详情/GLBL_00993_太康失国.json"
TOOLS = ROOT / "tools/openclaw-historiography"

sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(TOOLS / "historiography-translate"))

from emperor_year_align import (  # noqa: E402
    align_junji_entry_years,
    build_emperor_indexes,
    load_emperor_rows,
)
from import_box_index_json import (  # noqa: E402
    DEFAULT_EMPEROR_JSON,
    build_box_rows,
    ensure_schema,
    upsert_boxes,
)
from lib.remote_sync import sync_translate_detail  # noqa: E402
from sync_zhanguo_dynasty_online import load_index_entries, save_index_entries  # noqa: E402


def main() -> int:
    if not DETAIL.is_file():
        print(f"❌ 缺少详情: {DETAIL}")
        return 1

    entries_doc = json.loads(DK.read_text(encoding="utf-8"))
    entry = deepcopy(next(e for e in entries_doc["entries"] if e["史略ID"] == "GLBL_00993"))
    entry.setdefault("峰值年", entry.get("史略开始年", -1900))
    entry.setdefault("优先级", "P1")
    entry.setdefault(
        "优先级判定理由",
        "太康失国为夏初世袭体制崩溃的标志性转折，影响少康中兴叙事，属夏史核心事略。",
    )
    entry.setdefault("五级细坐标", "夏·事略·太康失国")
    entry.setdefault("paragraphs", [])

    rows = [r for r in load_emperor_rows(DEFAULT_EMPEROR_JSON) if r.get("朝代ID") == "CD_HX_XIA"]
    by_name, by_id = build_emperor_indexes(rows)
    entry, _ = align_junji_entry_years(entry, by_name=by_name, by_id=by_id, force=True)

    for i, e in enumerate(entries_doc["entries"]):
        if e["史略ID"] == "GLBL_00993":
            entries_doc["entries"][i] = entry
            break
    DK.write_text(json.dumps(entries_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("✅ 06 索引已补峰值年/优先级")

    main_entries, doc, fmt = load_index_entries(INDEX)
    by_id_map = {e["史略ID"]: i for i, e in enumerate(main_entries)}
    if entry["史略ID"] in by_id_map:
        main_entries[by_id_map[entry["史略ID"]]] = entry
        print("✅ 全局索引更新 GLBL_00993")
    else:
        main_entries.append(entry)
        print("✅ 全局索引新增 GLBL_00993")
    save_index_entries(INDEX, main_entries, doc, fmt)

    env = TOOLS / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    import pymysql

    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=15,
    )
    rows_box, skipped = build_box_rows([entry])
    with conn.cursor() as cursor:
        ensure_schema(cursor)
        n = upsert_boxes(cursor, rows_box)
        conn.commit()
    print(f"✅ historical_box upsert: {n} (skipped={len(skipped)})")

    text = str(json.loads(DETAIL.read_text(encoding="utf-8")).get("翻译详情", "")).strip()
    ok, msg = sync_translate_detail("GLBL_00993", text, dry_run=False)
    conn.close()
    if not ok:
        print(f"❌ detail sync: {msg}")
        return 1
    print("✅ historical_box_detail upsert OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
