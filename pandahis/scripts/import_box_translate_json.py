#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 data/史略翻译_汇总.json 全量同步到 histomap.historical_box_detail。

字段映射：
  史略ID   -> box_id
  翻译详情 -> translate_detail
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "史略翻译_汇总.json"


def load_rows(json_path: Path) -> list[dict]:
    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("史略翻译_汇总.json 缺少 entries 数组")
    rows: list[dict] = []
    for item in entries:
        box_id = str(item["史略ID"]).strip()
        detail = item.get("翻译详情")
        if detail is None:
            raise ValueError(f"史略 {box_id} 缺少 翻译详情")
        rows.append(
            {
                "box_id": box_id,
                "translate_detail": str(detail),
            }
        )
    return rows


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
        """,
        (table_name,),
    )
    return cursor.fetchone()["cnt"] > 0


def ensure_schema(cursor) -> None:
    if table_exists(cursor, "historical_box_detail"):
        return
    cursor.execute(
        """
        CREATE TABLE historical_box_detail (
          box_id VARCHAR(64) PRIMARY KEY COMMENT '史略ID',
          translate_detail LONGTEXT NOT NULL COMMENT '翻译详情',
          CONSTRAINT fk_box_detail_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='史略翻译详情'
        """
    )


def upsert_details(cursor, rows: list[dict]) -> int:
    upserted = 0
    for row in rows:
        cursor.execute(
            """
            INSERT INTO historical_box_detail (box_id, translate_detail)
            VALUES (%(box_id)s, %(translate_detail)s)
            ON DUPLICATE KEY UPDATE
              translate_detail = VALUES(translate_detail)
            """,
            row,
        )
        upserted += 1
    return upserted


def delete_orphan_details(cursor, rows: list[dict]) -> int:
    json_ids = [row["box_id"] for row in rows]
    if not json_ids:
        cursor.execute("DELETE FROM historical_box_detail")
        return cursor.rowcount
    placeholders = ", ".join(["%s"] * len(json_ids))
    cursor.execute(
        f"DELETE FROM historical_box_detail WHERE box_id NOT IN ({placeholders})",
        json_ids,
    )
    return cursor.rowcount


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mysql-host", default="49.235.165.220")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", default="histomap_admin")
    parser.add_argument("--mysql-password", default="pandahis#666")
    parser.add_argument("--mysql-db", default="histomap")
    args = parser.parse_args()

    rows = load_rows(args.json)

    if args.dry_run:
        print(f"dry-run: 将导入 {len(rows)} 条史略翻译详情")
        for row in rows:
            print(f"  - {row['box_id']} ({len(row['translate_detail'])} 字)")
        return 0

    try:
        import pymysql
    except ImportError:
        print("需要: pip install pymysql", file=sys.stderr)
        return 1

    conn = pymysql.connect(
        host=args.mysql_host,
        port=args.mysql_port,
        user=args.mysql_user,
        password=args.mysql_password,
        database=args.mysql_db,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            upserted = upsert_details(cursor, rows)
            deleted = delete_orphan_details(cursor, rows)
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_box_detail")
            final_count = cursor.fetchone()["cnt"]
        conn.commit()
        print(
            f"完成: 导入/更新 {upserted} 条史略翻译详情，"
            f"删除多余记录 {deleted} 条，"
            f"当前 historical_box_detail 共 {final_count} 条"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
