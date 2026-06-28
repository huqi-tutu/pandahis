#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 data/华夏历史全朝代_政权简介（适配历史图谱 完整版·分段规范）.md
同步朝代简介到 data/朝代.json 与 historical_dynasty.summary。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD = ROOT / "data" / "华夏历史全朝代_政权简介（适配历史图谱 完整版·分段规范）.md"
DEFAULT_JSON = ROOT / "data" / "朝代.json"

# JSON 朝代名 -> Markdown 章节标题
SUMMARY_TITLE_ALIASES: dict[str, str] = {
    "新": "新朝",
    "秦朝": "秦",
}


def parse_summary_sections(md_path: Path) -> dict[str, str]:
    text = md_path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if not current_title:
            return
        body = "\n".join(current_lines).strip()
        body = re.sub(r"\n>.*$", "", body, flags=re.MULTILINE).strip()
        if body:
            sections[current_title] = body
        current_title = None
        current_lines = []

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            continue
        if current_title is None or line.startswith("# "):
            continue
        if line.startswith("> "):
            continue
        current_lines.append(line)

    flush()
    return sections


def resolve_summary(dynasty_name: str, sections: dict[str, str]) -> str | None:
    title = SUMMARY_TITLE_ALIASES.get(dynasty_name, dynasty_name)
    return sections.get(title)


def update_json(json_path: Path, sections: dict[str, str]) -> tuple[int, list[str]]:
    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)

    matched = 0
    missing: list[str] = []
    for item in data:
        if str(item.get("文明ID", "")).strip() != "HX":
            item.pop("朝代简介", None)
            continue

        name = str(item["朝代"]).strip()
        summary = resolve_summary(name, sections)
        if summary:
            item["朝代简介"] = summary
            matched += 1
        else:
            item.pop("朝代简介", None)
            missing.append(name)

    with json_path.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write("\n")

    return matched, missing


def ensure_summary_column(cursor) -> None:
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


def sync_db(json_path: Path, mysql_args: dict) -> tuple[int, int]:
    try:
        import pymysql
    except ImportError:
        print("需要: pip install pymysql", file=sys.stderr)
        raise SystemExit(1)

    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)

    conn = pymysql.connect(
        **mysql_args,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
    )
    updated = 0
    cleared = 0
    try:
        with conn.cursor() as cursor:
            ensure_summary_column(cursor)
            for item in data:
                dynasty_id = str(item["朝代ID"]).strip()
                summary = item.get("朝代简介")
                if summary:
                    cursor.execute(
                        """
                        UPDATE historical_dynasty
                        SET summary = %s
                        WHERE id = %s
                        """,
                        (summary, dynasty_id),
                    )
                    updated += cursor.rowcount
                else:
                    cursor.execute(
                        """
                        UPDATE historical_dynasty
                        SET summary = NULL
                        WHERE id = %s
                        """,
                        (dynasty_id,),
                    )
                    cleared += cursor.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return updated, cleared


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--mysql-host", default="49.235.165.220")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", default="histomap_admin")
    parser.add_argument("--mysql-password", default="pandahis#666")
    parser.add_argument("--mysql-db", default="histomap")
    args = parser.parse_args()

    sections = parse_summary_sections(args.md)
    matched, missing = update_json(args.json, sections)
    print(f"JSON: 已写入 {matched} 条华夏朝代简介（共 {len(sections)} 个 Markdown 章节）")
    if missing:
        print("JSON: 华夏朝代无对应简介:", "、".join(missing))

    if args.json_only:
        return 0

    updated, cleared = sync_db(
        args.json,
        {
            "host": args.mysql_host,
            "port": args.mysql_port,
            "user": args.mysql_user,
            "password": args.mysql_password,
            "database": args.mysql_db,
        },
    )
    print(f"DB: 更新 summary {updated} 条，清空 {cleared} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
