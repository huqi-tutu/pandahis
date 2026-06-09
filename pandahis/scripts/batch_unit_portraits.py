#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量为 historical_unit.card_image_url 生成人物肖像并写回 MySQL。

推荐与 Cursor MCP 配合：
  1) user-gpt-image-2-imagegen / text-to-image
  2) user-cos-upload / upload-file 或 upload-many
  3) project-0-pandahis-mysql-histomap / mysql_query

本脚本负责：查询待配图单元、生成英文提示词、输出 manifest（供 Agent 批处理）。

用法:
  python scripts/batch_unit_portraits.py --limit 20 --civ 1
  python scripts/batch_unit_portraits.py --manifest .tmp/unit-portrait/manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / ".tmp" / "unit-portrait"
COS_PREFIX = "histomap/unit-portrait"


def slug_key(unit_id: str) -> str:
    h = hashlib.sha1(unit_id.encode("utf-8")).hexdigest()[:12]
    return f"{COS_PREFIX}/{h}.png"


def year_label(y: int) -> str:
    if y < 0:
        return f"{abs(y)} BCE"
    return f"{y} CE"


def build_prompt(row: dict) -> str:
    name = row["name"] or "historical figure"
    dynasty = (row.get("dynasty_name") or "").strip()
    ruler = (row.get("ruler_name") or "").strip()
    era = (row.get("era_name") or "").strip()
    sy, ey = row.get("start_year"), row.get("end_year")
    period = ""
    if sy is not None and ey is not None:
        period = f", active circa {year_label(sy)} to {year_label(ey)}"
    ctx = dynasty or era or "ancient China"
    title = ruler if ruler and ruler != name else name
    elements = {
        "伏羲": "mythic sage-king Fuxi with Bagua motifs, ancient Chinese legendary era",
        "女娲": "goddess Nüwa, subtle serpent symbolism, creation myth, ancient China",
        "黄帝": "Yellow Emperor Xuanyuan, bronze-age Chinese sovereign, dignified regalia",
        "神农": "Shennong divine farmer, herbal plants, ancient agrarian sage",
        "女娲": "Nüwa goddess repairing heavens, ancient mythic China",
    }
    extra = elements.get(name, f"{ctx} historical ruler or sage")
    return (
        f"Scholarly portrait of {title} ({extra}){period}. "
        "Historical atlas illustration style, warm parchment palette, half-body dignified pose, "
        "traditional Chinese ceremonial dress appropriate to era, soft painterly brushwork, "
        "museum educational tone, no text, no watermark, no modern objects, square composition."
    )


def fetch_units(args) -> list[dict]:
    try:
        import pymysql
    except ImportError:
        print("pip install PyMySQL", file=sys.stderr)
        sys.exit(1)
    conn = pymysql.connect(
        host=args.mysql_host,
        port=args.mysql_port,
        user=args.mysql_user,
        password=args.mysql_password,
        database=args.mysql_db,
        charset="utf8mb4",
    )
    sql = (
        "SELECT id, name, ruler_name, dynasty_name, era_name, start_year, end_year, civilization_l1_id "
        "FROM historical_unit WHERE status=1 "
        "AND (card_image_url IS NULL OR TRIM(card_image_url)='' OR card_image_url LIKE '%待查%')"
    )
    params: list = []
    if args.civ:
        sql += " AND civilization_l1_id=%s"
        params.append(args.civ)
    sql += " ORDER BY civilization_l1_id, start_year"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mysql-host", default="49.235.165.220")
    ap.add_argument("--mysql-port", type=int, default=3306)
    ap.add_argument("--mysql-user", default="root")
    ap.add_argument("--mysql-password", default="")
    ap.add_argument("--mysql-db", default="histomap")
    ap.add_argument("--civ", type=int, default=None, help="civilization_l1_id filter")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--manifest", type=Path, default=None, help="write manifest JSON path")
    args = ap.parse_args()

    rows = fetch_units(args)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for row in rows:
        uid = row["id"]
        key = slug_key(uid)
        local = out_dir / f"{hashlib.sha1(uid.encode()).hexdigest()[:12]}.png"
        manifest.append(
            {
                "unitId": uid,
                "name": row["name"],
                "cosKey": key,
                "localPath": str(local.resolve()),
                "prompt": build_prompt(row),
            }
        )

    manifest_path = args.manifest or (out_dir / "manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest)} items to {manifest_path}")
    for item in manifest[:5]:
        print(f"  - {item['name']}: {item['localPath']}")


if __name__ == "__main__":
    main()
