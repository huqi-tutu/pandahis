#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 data/帝王.json 全量同步到 histomap.historical_emperor。

迁移约定：
  - historical_unit 重命名为 historical_emperor（全新表结构）
  - historical_box.unit_id → emperor_id（暂清空，待 box 优化后用帝王ID 关联）
  - 即位/退位/在位时长/标签 字段对齐 JSON
  - card_image_url、status 保留
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "帝王.json"

CIV_CODE_TO_ID: dict[str, int] = {
    "HX": 1, "CX": 2, "RB": 3, "DNY": 4, "ZY": 5, "BY": 6, "NY": 7, "XY": 8,
    "NO": 9, "DO": 10, "XO": 11, "BO": 12, "BF": 13, "XF": 14, "DF": 15,
    "ZM": 16, "BM": 17, "NM": 18,
}


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text == "-":
        return None
    return text


def parse_int(value: str | None) -> int | None:
    text = blank_to_none(value)
    if text is None:
        return None
    if text.lstrip("-").isdigit():
        return int(text)
    try:
        return int(float(text))
    except ValueError:
        return None


def load_rows(json_path: Path) -> list[dict]:
    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        raise ValueError("帝王.json 顶层必须是数组")
    return data


def build_emperor_rows(data: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, item in enumerate(data):
        emperor_id = str(item["帝王ID"]).strip()
        civ_code = str(item["文明ID"]).strip()
        civ_id = CIV_CODE_TO_ID.get(civ_code)
        if civ_id is None:
            raise ValueError(f"未知文明ID: {civ_code}（帝王 {emperor_id}）")

        enthronement_raw = str(item["即位时间"]).strip()
        abdication_raw = str(item["退位时间"]).strip()
        rows.append(
            {
                "id": emperor_id,
                "name": str(item["帝王名称"]).strip(),
                "ruler_name": blank_to_none(item.get("帝王原名")),
                "regime_id": str(item["政权ID"]).strip(),
                "regime_name": str(item["政权"]).strip(),
                "dynasty_id": str(item["朝代ID"]).strip(),
                "dynasty_name": str(item["朝代"]).strip(),
                "civilization_l1_id": civ_id,
                "civilization_name": str(item["文明"]).strip(),
                "civilization_code": civ_code,
                "temple_name": blank_to_none(item.get("庙号")),
                "era_name": blank_to_none(item.get("年号")),
                "enthronement_year": parse_int(enthronement_raw),
                "abdication_year": parse_int(abdication_raw),
                "enthronement_year_raw": enthronement_raw,
                "abdication_year_raw": abdication_raw,
                "reign_duration": parse_int(item.get("在位时长")),
                "importance_level": parse_int(item.get("重要性评级")),
                "tags": blank_to_none(item.get("标签")),
                "card_image_url": None,
                "sort_order": index,
                "status": 1,
            }
        )
    return rows


def table_exists(cursor, name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """,
        (name,),
    )
    return cursor.fetchone()["cnt"] > 0


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    return cursor.fetchone()["cnt"] > 0


def drop_fk_if_exists(cursor, table: str, constraint: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (table, constraint),
    )
    if cursor.fetchone()["cnt"]:
        cursor.execute(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{constraint}`")


def migrate_schema(cursor) -> dict[str, str]:
    if table_exists(cursor, "historical_emperor"):
        return {}

    card_images_by_name: dict[str, str] = {}
    if table_exists(cursor, "historical_unit"):
        cursor.execute(
            "SELECT name, card_image_url FROM historical_unit "
            "WHERE card_image_url IS NOT NULL AND TRIM(card_image_url) <> ''"
        )
        for row in cursor.fetchall():
            card_images_by_name[row["name"]] = row["card_image_url"]

    if table_exists(cursor, "historical_box"):
        cursor.execute(
            """
            SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'historical_box'
              AND REFERENCED_TABLE_NAME = 'historical_unit'
            """
        )
        for row in cursor.fetchall():
            drop_fk_if_exists(cursor, "historical_box", row["CONSTRAINT_NAME"])

        if column_exists(cursor, "historical_box", "unit_id"):
            cursor.execute(
                "ALTER TABLE historical_box CHANGE COLUMN unit_id emperor_id VARCHAR(128) NULL"
            )
        if column_exists(cursor, "historical_box", "subject_unit_id"):
            cursor.execute(
                "ALTER TABLE historical_box "
                "CHANGE COLUMN subject_unit_id subject_emperor_id VARCHAR(128) NULL"
            )
        cursor.execute(
            "UPDATE historical_box SET emperor_id = NULL, subject_emperor_id = NULL"
        )

    if table_exists(cursor, "historical_unit"):
        cursor.execute("DROP TABLE historical_unit")

    cursor.execute(
        """
        CREATE TABLE historical_emperor (
          id VARCHAR(128) PRIMARY KEY COMMENT '帝王ID',
          name VARCHAR(128) NOT NULL COMMENT '帝王名称',
          ruler_name VARCHAR(64) NULL COMMENT '帝王原名',
          regime_id VARCHAR(128) NOT NULL COMMENT '政权ID',
          regime_name VARCHAR(128) NOT NULL COMMENT '政权名称',
          dynasty_id VARCHAR(64) NOT NULL COMMENT '朝代ID',
          dynasty_name VARCHAR(128) NOT NULL COMMENT '朝代名称',
          civilization_l1_id BIGINT NOT NULL COMMENT '文明ID',
          civilization_name VARCHAR(64) NULL COMMENT '文明名称',
          civilization_code VARCHAR(16) NULL COMMENT '文明编码',
          temple_name VARCHAR(64) NULL COMMENT '庙号',
          era_name VARCHAR(64) NULL COMMENT '年号',
          enthronement_year INT NULL COMMENT '即位时间（数值）',
          abdication_year INT NULL COMMENT '退位时间（数值）',
          enthronement_year_raw VARCHAR(32) NULL COMMENT '即位时间原文',
          abdication_year_raw VARCHAR(32) NULL COMMENT '退位时间原文',
          reign_duration INT NULL COMMENT '在位时长',
          importance_level TINYINT NULL COMMENT '重要性评级',
          tags TEXT NULL COMMENT '标签',
          card_image_url VARCHAR(512) NULL COMMENT '卡片配图',
          sort_order INT NOT NULL DEFAULT 0,
          status TINYINT NOT NULL DEFAULT 1,
          INDEX idx_emperor_regime (regime_id),
          INDEX idx_emperor_dynasty (dynasty_id),
          INDEX idx_emperor_civ (civilization_l1_id),
          CONSTRAINT fk_emperor_regime FOREIGN KEY (regime_id) REFERENCES historical_regime (id),
          CONSTRAINT fk_emperor_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
          CONSTRAINT fk_emperor_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帝王'
        """
    )
    return card_images_by_name


def preserve_card_images(cursor, rows: list[dict]) -> None:
    if not table_exists(cursor, "historical_emperor"):
        return
    cursor.execute(
        "SELECT id, card_image_url FROM historical_emperor WHERE card_image_url IS NOT NULL"
    )
    existing = {r["id"]: r["card_image_url"] for r in cursor.fetchall()}
    for row in rows:
        if row["id"] in existing:
            row["card_image_url"] = existing[row["id"]]


def upsert_emperors(cursor, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        cursor.execute(
            """
            INSERT INTO historical_emperor (
              id, name, ruler_name, regime_id, regime_name, dynasty_id, dynasty_name,
              civilization_l1_id, civilization_name, civilization_code,
              temple_name, era_name,
              enthronement_year, abdication_year, enthronement_year_raw, abdication_year_raw,
              reign_duration, importance_level, tags, card_image_url, sort_order, status
            ) VALUES (
              %(id)s, %(name)s, %(ruler_name)s, %(regime_id)s, %(regime_name)s,
              %(dynasty_id)s, %(dynasty_name)s,
              %(civilization_l1_id)s, %(civilization_name)s, %(civilization_code)s,
              %(temple_name)s, %(era_name)s,
              %(enthronement_year)s, %(abdication_year)s,
              %(enthronement_year_raw)s, %(abdication_year_raw)s,
              %(reign_duration)s, %(importance_level)s, %(tags)s,
              %(card_image_url)s, %(sort_order)s, %(status)s
            )
            ON DUPLICATE KEY UPDATE
              name = VALUES(name),
              ruler_name = VALUES(ruler_name),
              regime_id = VALUES(regime_id),
              regime_name = VALUES(regime_name),
              dynasty_id = VALUES(dynasty_id),
              dynasty_name = VALUES(dynasty_name),
              civilization_l1_id = VALUES(civilization_l1_id),
              civilization_name = VALUES(civilization_name),
              civilization_code = VALUES(civilization_code),
              temple_name = VALUES(temple_name),
              era_name = VALUES(era_name),
              enthronement_year = VALUES(enthronement_year),
              abdication_year = VALUES(abdication_year),
              enthronement_year_raw = VALUES(enthronement_year_raw),
              abdication_year_raw = VALUES(abdication_year_raw),
              reign_duration = VALUES(reign_duration),
              importance_level = VALUES(importance_level),
              tags = VALUES(tags),
              card_image_url = COALESCE(VALUES(card_image_url), card_image_url),
              sort_order = VALUES(sort_order),
              status = VALUES(status)
            """,
            row,
        )
        count += 1
    return count


def delete_orphans(cursor, rows: list[dict]) -> int:
    json_ids = [row["id"] for row in rows]
    if not json_ids:
        cursor.execute("DELETE FROM historical_emperor")
        return cursor.rowcount
    placeholders = ", ".join(["%s"] * len(json_ids))
    cursor.execute(
        f"DELETE FROM historical_emperor WHERE id NOT IN ({placeholders})",
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

    data = load_rows(args.json)
    rows = build_emperor_rows(data)

    if args.dry_run:
        print(f"dry-run: 将导入 {len(rows)} 条帝王记录到 historical_emperor")
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
        read_timeout=180,
        write_timeout=180,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cursor:
            card_images = migrate_schema(cursor)
            for row in rows:
                if not row.get("card_image_url") and row["name"] in card_images:
                    row["card_image_url"] = card_images[row["name"]]
            preserve_card_images(cursor, rows)
            upserted = upsert_emperors(cursor, rows)
            deleted = delete_orphans(cursor, rows)
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_emperor")
            final_count = cursor.fetchone()["cnt"]
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM historical_box WHERE emperor_id IS NOT NULL"
            )
            linked_boxes = cursor.fetchone()["cnt"]
        conn.commit()
        print(
            f"完成: 导入/更新 {upserted} 条帝王，"
            f"删除多余 {deleted} 条，"
            f"historical_emperor 共 {final_count} 条，"
            f"box.emperor_id 已关联 {linked_boxes} 条（待 box 优化）"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
