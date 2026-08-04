#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 06 战国二期 enrichment 回写全局索引，并同步 MySQL（105 条 upsert + 167 条 enrichment）。"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INDEX_MAIN = DATA / "03索引标注条目" / "史略索引_01至02.json"
DK_IDX = DATA / "06朝代知识补全" / "索引条目"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"
TOOLS = ROOT / "tools" / "openclaw-historiography"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from import_box_index_json import (  # noqa: E402
    build_box_rows,
    ensure_schema,
    update_enrichment_fields,
    upsert_boxes,
)

MERGE_KEYS = (
    "史略开始年",
    "史略结束年",
    "优先级",
    "优先级判定理由",
    "峰值年",
    "峰值原因",
    "峰值类型",
    "峰值置信度",
    "人物标签",
    "人物标签判定理由",
    "人物标签置信度",
    "论著标签",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_index_entries(path: Path) -> tuple[list[dict], dict | list, str]:
    doc = load_json(path)
    if isinstance(doc, list):
        return doc, doc, "list"
    entries = list(doc.get("entries") or [])
    return entries, doc, "dict"


def save_index_entries(path: Path, entries: list[dict], doc: dict | list, fmt: str) -> None:
    if fmt == "list":
        save_json(path, entries)
    else:
        doc["entries"] = entries
        save_json(path, doc)


def load_phase2_entries() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for name in ("战国_事略典制论著.json", "战国_人物.json"):
        path = DK_IDX / name
        for e in load_json(path).get("entries") or []:
            eid = str(e.get("史略ID") or "").strip()
            if eid:
                by_id[eid] = e
    return by_id


def merge_enrichment_into_global(*, dry_run: bool = False) -> tuple[int, list[dict]]:
    phase2 = load_phase2_entries()
    entries, doc, fmt = load_index_entries(INDEX_MAIN)
    by_id = {str(e.get("史略ID", "")): i for i, e in enumerate(entries)}
    updated = 0
    for eid, src in phase2.items():
        if eid not in by_id:
            continue
        dst = entries[by_id[eid]]
        changed = False
        for key in MERGE_KEYS:
            if key not in src:
                continue
            val = src.get(key)
            if dst.get(key) != val:
                dst[key] = val
                changed = True
        if changed:
            updated += 1
    if not dry_run:
        save_index_entries(INDEX_MAIN, entries, doc, fmt)
    zhanguo = [e for e in entries if e.get("二级朝代坐标") == "战国"]
    return updated, zhanguo


def connect_mysql():
    import os
    import pymysql

    env_file = TOOLS / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=300,
        write_timeout=300,
        cursorclass=pymysql.cursors.DictCursor,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="战国 enrichment → 全局索引 + MySQL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        n, zhanguo = merge_enrichment_into_global(dry_run=True)
        p2 = load_phase2_entries()
        rows, skipped = build_box_rows([p2[eid] for eid in sorted(p2)])
        print(f"[dry-run] 全局索引将更新 {n} 条（06 二期 {len(p2)} 条）")
        print(f"[dry-run] MySQL upsert 行 {len(rows)}，跳过 {len(skipped)}")
        print(f"[dry-run] MySQL enrichment 战国 {len(zhanguo)} 条")
        return 0

    if not args.no_backup:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup = INDEX_MAIN.with_name(f"史略索引_01至02.json.bak_{ts}")
        shutil.copy2(INDEX_MAIN, backup)
        print(f"已备份 → {backup.name}")

    n, zhanguo = merge_enrichment_into_global(dry_run=False)
    print(f"✅ 全局索引 enrichment 回写 {n} 条")

    phase2 = load_phase2_entries()
    p2_list = [phase2[eid] for eid in sorted(phase2)]
    rows_p2, skipped = build_box_rows(p2_list)
    if skipped:
        print(f"⚠️ 二期缺年跳过: {skipped}")

    rows_zg, skipped_zg = build_box_rows(zhanguo)
    if skipped_zg:
        print(f"⚠️ 战国缺年跳过 enrichment: {skipped_zg}")

    conn = connect_mysql()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            box_n = upsert_boxes(cursor, rows_p2)
            print(f"historical_box upsert（二期 105）: {box_n} 条")
            enrich_n = update_enrichment_fields(cursor, rows_zg)
            print(f"enrichment 更新（战国 167）: {enrich_n} 条")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    peak_ok = sum(1 for e in zhanguo if e.get("峰值年") is not None)
    tag_ok = sum(
        1
        for e in zhanguo
        if str(e.get("人物标签") or "").strip()
        or (e.get("_auto_filled") or {}).get("_人物标签留空")
    )
    print(f"校验（全局索引·战国）: 峰值年 {peak_ok}/167")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
