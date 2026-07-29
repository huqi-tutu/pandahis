#!/usr/bin/env python3
"""全量恢复 box 子表：详情、评述、见证、关系（修复误删后使用）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CW_DIR = ROOT / "tools" / "openclaw-historiography" / "historiography-commentary-witness" / "scripts"
REL_DIR = ROOT / "tools" / "openclaw-historiography" / "historiography-person-relations" / "scripts"
TRANS_DIR = ROOT / "tools" / "openclaw-historiography" / "historiography-translate"

for p in (CW_DIR, REL_DIR, TRANS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import import_cw_lib as icw  # noqa: E402
import relations_lib as rl  # noqa: E402
from lib.remote_sync import sync_all_box_details  # noqa: E402


def default_mysql() -> dict:
    return {
        "host": "49.235.165.220",
        "port": 3306,
        "user": "histomap_admin",
        "password": "pandahis#666",
        "db": "histomap",
    }


def import_all_commentary_witness(mysql: dict, *, dry_run: bool) -> dict[str, int]:
    data = ROOT / "data"
    c_dir = data / "08评述"
    w_dir = data / "09见证"
    stats = {"commentary_files": 0, "witness_files": 0, "commentary_rows": 0, "witness_rows": 0, "stmts": 0}
    all_stmts: list[str] = []

    for fp in sorted(c_dir.glob("*_评述.json")):
        doc = icw.load_json(fp)
        if not doc.get("entries"):
            continue
        stmts = icw.build_critique_sql(doc)
        stats["commentary_files"] += 1
        stats["commentary_rows"] += max(0, len(stmts) - 1)
        all_stmts.extend(stmts)

    for fp in sorted(w_dir.glob("*_见证.json")):
        doc = icw.load_json(fp)
        if not doc.get("entries"):
            continue
        stmts = icw.build_relic_sql(doc)
        stats["witness_files"] += 1
        stats["witness_rows"] += max(0, len(stmts) - 1)
        all_stmts.extend(stmts)

    stats["stmts"] = len(all_stmts)
    if dry_run:
        return stats
    if all_stmts:
        icw.execute_mysql(all_stmts, **mysql)
    return stats


def import_all_relations(mysql: dict, *, dry_run: bool) -> dict[str, int]:
    rel_dir = ROOT / "data" / "07人物关系"
    files = sorted(rel_dir.glob("*关系表.json"))
    stats = {"files": 0, "errors": 0}
    for fp in files:
        if dry_run:
            stats["files"] += 1
            continue
        try:
            rl.import_json_file(fp, mysql=mysql)
            stats["files"] += 1
        except Exception as exc:
            stats["errors"] += 1
            print(f"⚠️ 跳过 {fp.name}: {exc}", flush=True)
    return stats


def verify_counts(mysql: dict) -> None:
    import pymysql

    conn = pymysql.connect(
        host=mysql["host"],
        port=int(mysql["port"]),
        user=mysql["user"],
        password=mysql["password"],
        database=mysql["db"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            for t in (
                "historical_box_detail",
                "box_critique",
                "box_relic",
                "box_graph_node",
                "box_graph_edge",
            ):
                cur.execute(f"SELECT COUNT(*) AS c FROM `{t}`")
                print(f"  {t}: {cur.fetchone()['c']}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="全量恢复史略子表数据")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-detail", action="store_true")
    parser.add_argument("--skip-cw", action="store_true")
    parser.add_argument("--skip-relations", action="store_true")
    args = parser.parse_args()
    mysql = default_mysql()

    print("=== 恢复前 ===")
    if not args.dry_run:
        verify_counts(mysql)

    if not args.skip_detail:
        translate_json = ROOT / "data" / "04史料翻译" / "史略翻译_汇总.json"
        dynasty_json = ROOT / "data" / "06朝代知识补全" / "详情" / "朝代知识详情_汇总.json"
        ok, msg = sync_all_box_details(
            translate_json=translate_json,
            dynasty_detail_json=dynasty_json,
            dry_run=args.dry_run,
            prune_orphans=False,
        )
        print(f"详情: {'[dry-run] ' if args.dry_run else ''}{msg}" if ok else f"详情失败: {msg}")
        if not ok:
            return 1

    if not args.skip_cw:
        cw_stats = import_all_commentary_witness(mysql, dry_run=args.dry_run)
        print(
            f"评述/见证: {cw_stats['commentary_files']} 评述文件 / {cw_stats['commentary_rows']} 行，"
            f"{cw_stats['witness_files']} 见证文件 / {cw_stats['witness_rows']} 行"
        )

    if not args.skip_relations:
        rel_stats = import_all_relations(mysql, dry_run=args.dry_run)
        print(f"关系: {rel_stats['files']} 文件，失败 {rel_stats['errors']}")

    if not args.dry_run:
        print("=== 恢复后 ===")
        verify_counts(mysql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
