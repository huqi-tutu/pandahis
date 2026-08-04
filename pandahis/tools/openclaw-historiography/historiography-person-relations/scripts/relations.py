#!/usr/bin/env python3
"""
人物关系补全编排器（固定 DeepSeek v4 Pro）

用法:
  python3 relations.py test-llm
  python3 relations.py compose-one --id GLBL_00149 [--sync] [--sql-out out.sql]
  python3 relations.py import-one --name 黄帝 [--sql-out out.sql]
  python3 relations.py import-all [--sql-out dir/]
  python3 relations.py verify --name 黄帝
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import relations_lib as rl  # noqa: E402


def _mysql_from_args(args: argparse.Namespace) -> dict | None:
    if not getattr(args, "mysql_host", None):
        return None
    return {
        "host": args.mysql_host,
        "port": args.mysql_port,
        "user": args.mysql_user,
        "password": args.mysql_password or "",
        "db": args.mysql_db,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="人物关系补全（DeepSeek v4 Pro）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test-llm", help="测试 DeepSeek v4 Pro 连通")

    p = sub.add_parser("compose-one", help="补全单个人物关系表")
    p.add_argument("--id", dest="entry_id", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-revise", action="store_true")
    p.add_argument("--sync", action="store_true", help="verify 通过后导入 box_graph_*")
    p.add_argument("--sql-out", type=Path, default=None)
    p.add_argument("--mysql-host", default=None)
    p.add_argument("--mysql-port", type=int, default=3306)
    p.add_argument("--mysql-user", default=None)
    p.add_argument("--mysql-password", default=None)
    p.add_argument("--mysql-db", default=None)

    p = sub.add_parser("compose", help="按朝代批量补全（逐人串行）")
    p.add_argument("--dynasty", required=True)
    p.add_argument("--max", type=int, default=1)
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sync", action="store_true")
    p.add_argument("--sql-out", type=Path, default=None)
    p.add_argument("--mysql-host", default=None)
    p.add_argument("--mysql-port", type=int, default=3306)
    p.add_argument("--mysql-user", default=None)
    p.add_argument("--mysql-password", default=None)
    p.add_argument("--mysql-db", default=None)

    p = sub.add_parser("import-one", help="导入单个 07 JSON 到 box_graph_*")
    p.add_argument("--id", dest="entry_id", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--file", type=Path, default=None)
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--sql-out", type=Path, default=None)
    p.add_argument("--mysql-host", default=None)
    p.add_argument("--mysql-port", type=int, default=3306)
    p.add_argument("--mysql-user", default=None)
    p.add_argument("--mysql-password", default=None)
    p.add_argument("--mysql-db", default=None)

    p = sub.add_parser("import-all", help="导入目录下全部 *关系表.json")
    p.add_argument("--dir", type=Path, default=None)
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--sql-out", type=Path, default=None)
    p.add_argument("--mysql-host", default=None)
    p.add_argument("--mysql-port", type=int, default=3306)
    p.add_argument("--mysql-user", default=None)
    p.add_argument("--mysql-password", default=None)
    p.add_argument("--mysql-db", default=None)

    p = sub.add_parser("verify", help="校验已产出 JSON")
    p.add_argument("--id", dest="entry_id", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--file", type=Path, default=None)
    p.add_argument("--strict", action="store_true", default=True)
    p.add_argument("--no-strict", action="store_true")

    args = parser.parse_args()
    mysql = _mysql_from_args(args) if hasattr(args, "mysql_host") else None

    try:
        if args.cmd == "test-llm":
            label = rl.ensure_deepseek_v4_pro()
            out = rl.call_llm("回复 OK", session_prefix="rel-test-")
            print(f"✅ {label} 连通成功: {out[:80]!r}")
            return 0

        if args.cmd == "compose-one":
            if not args.entry_id and not args.name:
                print("compose-one 需要 --id 或 --name", file=sys.stderr)
                return 1
            rl.compose_one(
                entry_id=args.entry_id,
                name=args.name,
                index_path=args.index,
                dry_run=args.dry_run,
                revise_on_fail=not args.no_revise,
                sync_db=args.sync,
                sql_out=args.sql_out,
                mysql=mysql,
            )
            return 0

        if args.cmd == "compose":
            persons = rl.list_dynasty_persons(args.dynasty, args.index)
            failed = 0
            for e in persons[: args.max]:
                eid = str(e.get("史略ID", "")).strip()
                name = str(e.get("史略名称", "")).strip()
                try:
                    rl.compose_one(
                        entry_id=eid,
                        index_path=args.index,
                        dry_run=args.dry_run,
                        sync_db=args.sync,
                        sql_out=args.sql_out,
                        mysql=mysql,
                    )
                except Exception as exc:
                    failed += 1
                    print(f"❌ {eid} {name}: {exc}", file=sys.stderr)
            if not args.dry_run:
                rl.write_dynasty_manifest(args.dynasty, index_path=args.index)
            return 1 if failed else 0

        if args.cmd == "import-one":
            rl.import_one(
                entry_id=args.entry_id,
                name=args.name,
                file_path=args.file,
                index_path=args.index,
                sql_out=args.sql_out,
                mysql=mysql,
            )
            return 0

        if args.cmd == "import-all":
            rl.validate_histograph_root()
            paths = rl.histograph_paths()
            root = args.dir or paths["person_relations"]
            files = sorted(root.glob("*关系表.json"))
            if not files:
                print(f"no files in {root}", file=sys.stderr)
                return 1
            for fp in files:
                out_sql = None
                if args.sql_out:
                    args.sql_out.mkdir(parents=True, exist_ok=True)
                    out_sql = args.sql_out / f"{fp.stem}.sql"
                rl.import_one(file_path=fp, index_path=args.index, sql_out=out_sql, mysql=mysql)
            return 0

        if args.cmd == "verify":
            rl.validate_histograph_root()
            paths = rl.histograph_paths()
            if args.file:
                fp = args.file
            else:
                entry = rl.find_entry(entry_id=args.entry_id, name=args.name, index_path=args.index)
                fp = rl.output_path(paths, str(entry.get("史略名称", "")).strip())
            strict = args.strict and not args.no_strict
            ok, out = rl.run_verify(fp, strict=strict)
            print(out)
            return 0 if ok else 1

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
