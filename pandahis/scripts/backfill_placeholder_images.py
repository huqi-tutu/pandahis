#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
占位图批量处理辅助：找出 civilization_l1.tab_image_url、historical_unit.card_image_url、
box_relic.image_url 为空或含「待查找」的记录，输出待处理清单。

推荐流程（与 Cursor MCP 配合）:
  1) 生图：MCP 服务器 user-gpt-image-2-imagegen，工具 text-to-image。
     必填参数 text（英文提示词更稳）、outputPath（本机绝对路径 .png）。
     可选 size: 256x256 | 512x512 | 1024x1024 | 1536x1024 | 1024x1536 | 1792x1024 | 1024x1792。
     提示词建议包含文物/时代/风格，并要求 no readable text, no watermark。
  2) 上传：MCP user-cos-upload，工具 upload-file（filePath=上一步 PNG，key=如 histomap/relic/{id}.png）。
  3) 一级地域 Tab：scripts/gen_civ_tab_pngs.py 输出到 .tmp/civ-tab/，COS key 建议 histomap/civ-tab/{CODE}.png；
     写库用 scripts/apply_civ_tab_cos_urls.py 或 backend/src/main/resources/data_patch_civ_tab_cos_urls.sql（勿把 Tab 图打入小程序包）。
  4) 将返回的 HTTPS URL 填入本脚本打印的 UPDATE，经 MySQL MCP（project-0-pandahis-mysql-histomap / mysql_query）执行。

用法:
  python scripts/backfill_placeholder_images.py --mysql-host ... --mysql-user ... --mysql-db histomap --dry-run
"""

from __future__ import annotations

import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mysql-host", default="127.0.0.1")
    ap.add_argument("--mysql-port", type=int, default=3306)
    ap.add_argument("--mysql-user", required=True)
    ap.add_argument("--mysql-password", default="")
    ap.add_argument("--mysql-db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, display_name FROM civilization_l1 WHERE tab_image_url IS NULL OR TRIM(tab_image_url)='' "
                "OR tab_image_url LIKE '%待查%'"
            )
            civs = cur.fetchall()
            cur.execute(
                "SELECT id, name FROM historical_unit WHERE card_image_url IS NULL OR TRIM(card_image_url)='' "
                "OR card_image_url LIKE '%待查%'"
            )
            units = cur.fetchall()
            cur.execute(
                "SELECT id, box_id, name, image_url FROM box_relic WHERE image_url IS NULL OR TRIM(image_url)='' "
                "OR image_url LIKE '%待查%'"
            )
            relics = cur.fetchall()
    finally:
        conn.close()

    print("-- civilization_l1 待配图:", len(civs))
    for cid, name in civs:
        print(f"--   id={cid} name={name}")
        print(f"-- UPDATE civilization_l1 SET tab_image_url='https://YOUR_COS/...' WHERE id={cid};")

    print("\n-- historical_unit 待配图:", len(units))
    for uid, name in units:
        print(f"--   id={uid} name={name}")
        print(f"-- UPDATE historical_unit SET card_image_url='https://YOUR_COS/...' WHERE id={repr(uid)};")

    print("\n-- box_relic 待配图:", len(relics))
    for rid, bid, name, url in relics:
        print(f"--   relic_id={rid} box_id={bid} name={name} url={url!r}")
        print(f"-- UPDATE box_relic SET image_url='https://YOUR_COS/...' WHERE id={rid};")

    if args.dry_run:
        print("\n(--dry-run: 未修改数据库。去掉 --dry-run 后本脚本仍只打印 SQL，请复制到 MCP/MySQL 执行。)")


if __name__ == "__main__":
    main()
