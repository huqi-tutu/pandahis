#!/usr/bin/env python3
"""将 civilization_l1.tab_image_url 更新为腾讯云 COS 公网地址（见 data_patch_civ_tab_cos_urls.sql）。"""
import argparse

import pymysql

DEFAULT_COS_PREFIX = (
    "https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mysql-host", default="127.0.0.1")
    ap.add_argument("--mysql-port", type=int, default=3306)
    ap.add_argument("--mysql-user", required=True)
    ap.add_argument("--mysql-password", default="")
    ap.add_argument("--mysql-db", required=True)
    ap.add_argument(
        "--cos-prefix",
        default=DEFAULT_COS_PREFIX,
        help="COS 目录前缀，须以 / 结尾，对象名为 {code}.png",
    )
    args = ap.parse_args()
    prefix = args.cos_prefix
    if not prefix.endswith("/"):
        prefix += "/"
    sql = (
        "UPDATE civilization_l1 SET tab_image_url = CONCAT(%s, code, '.png') "
        "WHERE code IS NOT NULL AND status = 1"
    )
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
            cur.execute(sql, (prefix,))
            n = cur.rowcount
        conn.commit()
        print("OK, rows affected:", n)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
