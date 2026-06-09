#!/usr/bin/env python3
"""按顺序执行 xlsx_export_mysql.py 生成的 .stmts.json（需 pymysql）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    try:
        import pymysql
    except ImportError:
        print("请先安装: pip install pymysql", file=sys.stderr)
        raise SystemExit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--stmts",
        type=Path,
        default=_REPO / "deploy" / "xlsx-import-histomap.stmts.json",
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", default="histomap")
    ap.add_argument("--password", default="")
    ap.add_argument("--database", default="histomap")
    args = ap.parse_args()

    stmts = json.loads(args.stmts.read_text(encoding="utf-8"))
    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            for i, sql in enumerate(stmts):
                cur.execute(sql)
                if (i + 1) % 20 == 0 or i == 0:
                    print(f"… {i + 1}/{len(stmts)}")
        print("done:", len(stmts), "statements")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
