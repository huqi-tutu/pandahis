#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 data/政权.json 全量同步到 histomap.historical_regime。

字段映射：
  政权ID       -> id
  政权         -> name
  朝代ID       -> dynasty_id
  朝代         -> dynasty_name
  dynasty_zy   -> dynasty_zy
  文明ID       -> civilization_code + civilization_l1_id
  文明         -> civilization_name
  开始/结束时间 -> start_year_raw/end_year_raw + start_year/end_year
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "政权.json"

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
        raise ValueError("政权.json 顶层必须是数组")
    return data


def build_regime_rows(data: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, item in enumerate(data):
        regime_id = str(item["政权ID"]).strip()
        dynasty_id = str(item["朝代ID"]).strip()
        civ_code = str(item["文明ID"]).strip()
        civ_id = CIV_CODE_TO_ID.get(civ_code)
        if civ_id is None:
            raise ValueError(f"未知文明ID: {civ_code}（政权 {regime_id}）")

        start_raw = str(item["开始时间"]).strip()
        end_raw = str(item["结束时间"]).strip()
        rows.append(
            {
                "id": regime_id,
                "name": str(item["政权"]).strip(),
                "dynasty_id": dynasty_id,
                "dynasty_name": str(item["朝代"]).strip(),
                "dynasty_zy": str(item.get("dynasty_zy", "")).strip() or None,
                "civilization_l1_id": civ_id,
                "civilization_name": str(item["文明"]).strip(),
                "civilization_code": civ_code,
                "start_year": parse_year(start_raw),
                "end_year": parse_year(end_raw),
                "start_year_raw": start_raw,
                "end_year_raw": end_raw,
                "sort_order": index,
                "status": 1,
            }
        )
    return rows


def ensure_schema(cursor) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'historical_regime'
        """
    )
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute(
            """
            CREATE TABLE historical_regime (
              id VARCHAR(128) PRIMARY KEY COMMENT '政权ID（JSON 政权ID）',
              name VARCHAR(128) NOT NULL COMMENT '政权名称',
              dynasty_id VARCHAR(64) NOT NULL COMMENT '所属朝代ID',
              dynasty_name VARCHAR(128) NOT NULL COMMENT '朝代名称（JSON 原文）',
              dynasty_zy VARCHAR(128) NULL COMMENT '主朝代归属（JSON dynasty_zy）',
              civilization_l1_id BIGINT NOT NULL COMMENT '所属文明ID',
              civilization_name VARCHAR(64) NULL COMMENT '文明名称（JSON 原文）',
              civilization_code VARCHAR(16) NULL COMMENT '文明编码（JSON 文明ID）',
              start_year INT NULL COMMENT '开始年份',
              end_year INT NULL COMMENT '结束年份',
              start_year_raw VARCHAR(32) NULL COMMENT '开始时间原文',
              end_year_raw VARCHAR(32) NULL COMMENT '结束时间原文',
              sort_order INT NOT NULL DEFAULT 0,
              status TINYINT NOT NULL DEFAULT 1,
              INDEX idx_regime_dynasty (dynasty_id),
              INDEX idx_regime_civ (civilization_l1_id),
              CONSTRAINT fk_regime_dynasty FOREIGN KEY (dynasty_id) REFERENCES historical_dynasty (id),
              CONSTRAINT fk_regime_civ FOREIGN KEY (civilization_l1_id) REFERENCES civilization_l1 (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='政权'
            """
        )


def upsert_regimes(cursor, rows: list[dict]) -> int:
    upserted = 0
    for row in rows:
        cursor.execute(
            """
            INSERT INTO historical_regime (
              id, name, dynasty_id, dynasty_name, dynasty_zy,
              civilization_l1_id, civilization_name, civilization_code,
              start_year, end_year, start_year_raw, end_year_raw,
              sort_order, status
            ) VALUES (
              %(id)s, %(name)s, %(dynasty_id)s, %(dynasty_name)s, %(dynasty_zy)s,
              %(civilization_l1_id)s, %(civilization_name)s, %(civilization_code)s,
              %(start_year)s, %(end_year)s, %(start_year_raw)s, %(end_year_raw)s,
              %(sort_order)s, %(status)s
            )
            ON DUPLICATE KEY UPDATE
              name = VALUES(name),
              dynasty_id = VALUES(dynasty_id),
              dynasty_name = VALUES(dynasty_name),
              dynasty_zy = VALUES(dynasty_zy),
              civilization_l1_id = VALUES(civilization_l1_id),
              civilization_name = VALUES(civilization_name),
              civilization_code = VALUES(civilization_code),
              start_year = VALUES(start_year),
              end_year = VALUES(end_year),
              start_year_raw = VALUES(start_year_raw),
              end_year_raw = VALUES(end_year_raw),
              sort_order = VALUES(sort_order),
              status = VALUES(status)
            """,
            row,
        )
        upserted += 1
    return upserted


def delete_orphan_regimes(cursor, rows: list[dict]) -> int:
    json_ids = [row["id"] for row in rows]
    if not json_ids:
        cursor.execute("DELETE FROM historical_regime")
        return cursor.rowcount
    placeholders = ", ".join(["%s"] * len(json_ids))
    cursor.execute(
        f"DELETE FROM historical_regime WHERE id NOT IN ({placeholders})",
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
    rows = build_regime_rows(data)

    if args.dry_run:
        print(f"dry-run: 将导入 {len(rows)} 条政权记录")
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
            upserted = upsert_regimes(cursor, rows)
            deleted = delete_orphan_regimes(cursor, rows)
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_regime")
            final_count = cursor.fetchone()["cnt"]
        conn.commit()
        print(
            f"完成: 导入/更新 {upserted} 条政权，"
            f"删除多余记录 {deleted} 条，"
            f"当前 historical_regime 共 {final_count} 条"
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
