#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 data/朝代.json 全量同步到 histomap.historical_dynasty。

约定（与产品确认）：
  - 以 JSON 条目为准，全量替换（删除 JSON 中不存在的旧记录）
  - 朝代 ID 使用 JSON「朝代ID」（如 CD_HX_SANGUO）
  - 新增 civilization_name / civilization_code 冗余列存 JSON 原文
  - end_year_raw =「至今」时 end_year 为 NULL
  - 「N世纪」按世纪起始年：7世纪→600，14世纪→1300；-7世纪→-700
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "朝代.json"

# historical_unit 中旧朝代名称 → 新 JSON 朝代ID（无精确匹配时的手工映射）
LEGACY_DYNASTY_NAME_TO_ID: dict[str, str] = {
    "三皇五帝文明": "CD_HX_WUDI",
}

CIV_CODE_TO_ID: dict[str, int] = {
    "HX": 1,
    "CX": 2,
    "RB": 3,
    "DNY": 4,
    "ZY": 5,
    "BY": 6,
    "NY": 7,
    "XY": 8,
    "NO": 9,
    "DO": 10,
    "XO": 11,
    "BO": 12,
    "BF": 13,
    "XF": 14,
    "DF": 15,
    "ZM": 16,
    "BM": 17,
    "NM": 18,
}


def sql_escape(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def parse_year(value: str | None) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "" or raw == "至今":
        return None

    compact = raw.replace(" ", "")
    century_match = re.match(r"^(约)?(-?\d+)世纪$", compact)
    if century_match:
        century = int(century_match.group(2))
        if century > 0:
            return century * 100 - 100
        return century * 100

    normalized = compact.replace("约", "").replace("前", "-")
    if re.fullmatch(r"-?\d+", normalized):
        return int(normalized)

    prefix_match = re.match(r"^(-?\d+)", normalized)
    if prefix_match:
        return int(prefix_match.group(1))
    return None


def load_rows(json_path: Path) -> list[dict]:
    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        raise ValueError("朝代.json 顶层必须是数组")
    return data


def build_dynasty_rows(data: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, item in enumerate(data):
        dynasty_id = str(item["朝代ID"]).strip()
        civ_code = str(item["文明ID"]).strip()
        civ_id = CIV_CODE_TO_ID.get(civ_code)
        if civ_id is None:
            raise ValueError(f"未知文明ID: {civ_code}（朝代 {dynasty_id}）")

        start_raw = str(item["开始时间"]).strip()
        end_raw = str(item["结束时间"]).strip()
        summary = item.get("朝代简介")
        if summary is not None:
            summary = str(summary).strip() or None
        rows.append(
            {
                "id": dynasty_id,
                "civilization_l1_id": civ_id,
                "civilization_name": str(item["文明"]).strip(),
                "civilization_code": civ_code,
                "name": str(item["朝代"]).strip(),
                "start_year": parse_year(start_raw),
                "end_year": parse_year(end_raw),
                "start_year_raw": start_raw,
                "end_year_raw": end_raw,
                "summary": summary,
                "sort_order": index,
                "status": 1,
            }
        )
    return rows


def ensure_schema(cursor) -> None:
    cursor.execute(
        """
        SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'historical_dynasty'
          AND COLUMN_NAME IN ('id', 'civilization_name')
        """
    )
    columns = {row["COLUMN_NAME"]: row["CHARACTER_MAXIMUM_LENGTH"] for row in cursor.fetchall()}

    if columns.get("id", 32) < 64:
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME, TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND REFERENCED_TABLE_NAME = 'historical_dynasty'
              AND REFERENCED_COLUMN_NAME = 'id'
            """
        )
        fk_rows = cursor.fetchall()
        for fk in fk_rows:
            cursor.execute(
                f"ALTER TABLE `{fk['TABLE_NAME']}` DROP FOREIGN KEY `{fk['CONSTRAINT_NAME']}`"
            )
        cursor.execute("ALTER TABLE historical_dynasty MODIFY COLUMN id VARCHAR(64) NOT NULL")
        cursor.execute("ALTER TABLE historical_unit MODIFY COLUMN dynasty_id VARCHAR(64) NULL")
        cursor.execute("ALTER TABLE historical_box MODIFY COLUMN dynasty_id VARCHAR(64) NULL")
        for fk in fk_rows:
            cursor.execute(
                f"ALTER TABLE `{fk['TABLE_NAME']}` "
                f"ADD CONSTRAINT `{fk['CONSTRAINT_NAME']}` "
                f"FOREIGN KEY (`dynasty_id`) REFERENCES historical_dynasty (`id`)"
            )

    if "civilization_name" not in columns:
        cursor.execute(
            """
            ALTER TABLE historical_dynasty
              ADD COLUMN civilization_name VARCHAR(64) NULL AFTER civilization_l1_id,
              ADD COLUMN civilization_code VARCHAR(16) NULL AFTER civilization_name
            """
        )

    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'historical_dynasty'
          AND COLUMN_NAME = 'summary'
        """
    )
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute(
            """
            ALTER TABLE historical_dynasty
              ADD COLUMN summary TEXT NULL COMMENT '朝代简介' AFTER end_year_raw
            """
        )


def remap_unit_dynasty_ids(cursor, name_to_id: dict[str, str]) -> int:
    updated = 0
    cursor.execute(
        "SELECT id, dynasty_id, dynasty_name FROM historical_emperor WHERE dynasty_id IS NOT NULL"
    )
    for row in cursor.fetchall():
        dynasty_name = (row["dynasty_name"] or "").strip()
        new_id = name_to_id.get(dynasty_name) or LEGACY_DYNASTY_NAME_TO_ID.get(dynasty_name)
        if new_id and new_id != row["dynasty_id"]:
            cursor.execute(
                "UPDATE historical_emperor SET dynasty_id = %s WHERE id = %s",
                (new_id, row["id"]),
            )
            updated += 1
        elif not new_id:
            cursor.execute(
                "UPDATE historical_emperor SET dynasty_id = NULL WHERE id = %s",
                (row["id"],),
            )
            updated += 1
    return updated


def upsert_dynasties(cursor, rows: list[dict]) -> int:
    upserted = 0
    for row in rows:
        cursor.execute(
            """
            INSERT INTO historical_dynasty (
              id, civilization_l1_id, civilization_name, civilization_code,
              name, start_year, end_year, start_year_raw, end_year_raw,
              summary, sort_order, status
            ) VALUES (
              %(id)s, %(civilization_l1_id)s, %(civilization_name)s, %(civilization_code)s,
              %(name)s, %(start_year)s, %(end_year)s, %(start_year_raw)s, %(end_year_raw)s,
              %(summary)s, %(sort_order)s, %(status)s
            )
            ON DUPLICATE KEY UPDATE
              civilization_l1_id = VALUES(civilization_l1_id),
              civilization_name = VALUES(civilization_name),
              civilization_code = VALUES(civilization_code),
              name = VALUES(name),
              start_year = VALUES(start_year),
              end_year = VALUES(end_year),
              start_year_raw = VALUES(start_year_raw),
              end_year_raw = VALUES(end_year_raw),
              summary = VALUES(summary),
              sort_order = VALUES(sort_order),
              status = VALUES(status)
            """,
            row,
        )
        upserted += 1
    return upserted


def delete_orphan_dynasties(cursor, rows: list[dict]) -> int:
    json_ids = [row["id"] for row in rows]
    if not json_ids:
        cursor.execute("DELETE FROM historical_dynasty")
        return cursor.rowcount
    placeholders = ", ".join(["%s"] * len(json_ids))
    cursor.execute(
        f"DELETE FROM historical_dynasty WHERE id NOT IN ({placeholders})",
        json_ids,
    )
    return cursor.rowcount


def render_sql(rows: list[dict], name_to_id: dict[str, str]) -> str:
    lines: list[str] = [
        "-- generated by scripts/import_dynasty_json.py",
        "ALTER TABLE historical_dynasty",
        "  ADD COLUMN IF NOT EXISTS civilization_name VARCHAR(64) NULL AFTER civilization_l1_id,",
        "  ADD COLUMN IF NOT EXISTS civilization_code VARCHAR(16) NULL AFTER civilization_name;",
        "",
    ]
    for dynasty_name, new_id in {**name_to_id, **LEGACY_DYNASTY_NAME_TO_ID}.items():
        lines.append(
            "UPDATE historical_unit "
            f"SET dynasty_id = {sql_escape(new_id)} "
            f"WHERE dynasty_name = {sql_escape(dynasty_name)};"
        )
    lines.append(
        "UPDATE historical_unit SET dynasty_id = NULL "
        "WHERE dynasty_name IS NOT NULL "
        "AND dynasty_name NOT IN ("
        + ", ".join(sql_escape(name) for name in {**name_to_id, **LEGACY_DYNASTY_NAME_TO_ID})
        + ");"
    )
    lines.append("DELETE FROM historical_dynasty;")
    for row in rows:
        lines.append(
            "INSERT INTO historical_dynasty ("
            "id, civilization_l1_id, civilization_name, civilization_code, "
            "name, start_year, end_year, start_year_raw, end_year_raw, sort_order, status"
            ") VALUES ("
            f"{sql_escape(row['id'])}, {row['civilization_l1_id']}, "
            f"{sql_escape(row['civilization_name'])}, {sql_escape(row['civilization_code'])}, "
            f"{sql_escape(row['name'])}, "
            f"{row['start_year'] if row['start_year'] is not None else 'NULL'}, "
            f"{row['end_year'] if row['end_year'] is not None else 'NULL'}, "
            f"{sql_escape(row['start_year_raw'])}, {sql_escape(row['end_year_raw'])}, "
            f"{row['sort_order']}, {row['status']}"
            ");"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--sql-out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mysql-host", default="49.235.165.220")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", default="histomap_admin")
    parser.add_argument("--mysql-password", default="pandahis#666")
    parser.add_argument("--mysql-db", default="histomap")
    args = parser.parse_args()

    data = load_rows(args.json)
    rows = build_dynasty_rows(data)
    name_to_id = {row["name"]: row["id"] for row in rows}

    if args.sql_out:
        args.sql_out.write_text(render_sql(rows, name_to_id), encoding="utf-8")
        print(f"已生成 SQL: {args.sql_out}（{len(rows)} 条）")
        if args.dry_run:
            return 0

    if args.dry_run:
        print(f"dry-run: 将导入 {len(rows)} 条朝代记录（未连接数据库）")
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
            upserted = upsert_dynasties(cursor, rows)
            unit_updates = remap_unit_dynasty_ids(cursor, name_to_id)
            deleted = delete_orphan_dynasties(cursor, rows)
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_dynasty")
            final_count = cursor.fetchone()["cnt"]
        conn.commit()
        print(
            f"完成: 导入/更新 {upserted} 条朝代，"
            f"更新 historical_unit 引用 {unit_updates} 条，"
            f"删除旧记录 {deleted} 条，"
            f"当前 historical_dynasty 共 {final_count} 条"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
