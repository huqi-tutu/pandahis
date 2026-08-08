#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本地 11/06/08/09/07 资产恢复线上 MySQL 子表（详情/评述/见证/关系）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
CW_DIR = TOOLS / "historiography-commentary-witness" / "scripts"
REL_DIR = TOOLS / "historiography-person-relations" / "scripts"
ONLINE_INDEX = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"

for p in (str(ROOT / "scripts"), str(TOOLS), str(CW_DIR), str(REL_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from online_detail_sync import build_online_detail_rows, load_online_ids  # noqa: E402
from lib.remote_sync import (  # noqa: E402
    _connect,
    _ensure_detail_source_column,
    ensure_schema,
    upsert_translate_detail,
)
import import_cw_lib as icw  # noqa: E402
import cw_lib as cw  # noqa: E402
import relations_lib as rl  # noqa: E402


def restore_details(online_ids: set[str], *, dry_run: bool) -> dict:
    rows, stats = build_online_detail_rows(online_ids)
    print(f"[详情] 待 upsert {len(rows)} 条 | stats={stats}")
    if dry_run:
        return {"upserted": len(rows), **stats}
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            _ensure_detail_source_column(cursor)
            for row in rows:
                upsert_translate_detail(
                    cursor,
                    row["box_id"],
                    row["translate_detail"],
                    row.get("source_original_json"),
                    row.get("source_citation"),
                    detail_source=row.get("detail_source"),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"upserted": len(rows), **stats}


def restore_commentary_witness(online_ids: set[str], index_path: Path, *, dry_run: bool) -> dict:
    paths = cw.histograph_paths() if hasattr(cw, "histograph_paths") else None
    from paths_config import histograph_paths  # noqa: WPS433

    paths = histograph_paths()
    mysql = icw.default_mysql_kwargs()
    ok_c, ok_w, skip_c, skip_w, fail = 0, 0, 0, 0, 0
    failures: list[str] = []

    for eid in sorted(online_ids):
        try:
            entry = cw.find_entry(entry_id=eid, index_path=index_path)
        except KeyError:
            continue
        for mode, counter_name in (("commentary", "c"), ("witness", "w")):
            fp = cw.output_path(mode, entry, paths)  # type: ignore[arg-type]
            if not fp.is_file():
                if counter_name == "c":
                    skip_c += 1
                else:
                    skip_w += 1
                continue
            doc = icw.load_json(fp)
            stmts = (
                icw.build_critique_sql(doc)
                if mode == "commentary"
                else icw.build_relic_sql(doc)
            )
            if dry_run:
                if mode == "commentary":
                    ok_c += 1
                else:
                    ok_w += 1
                continue
            try:
                icw.execute_mysql(stmts, **mysql)
                if mode == "commentary":
                    ok_c += 1
                else:
                    ok_w += 1
            except Exception as exc:  # noqa: BLE001
                fail += 1
                failures.append(f"{eid}/{mode}: {exc}")

    print(
        f"[评述/见证] commentary={ok_c} witness={ok_w} "
        f"skip_c={skip_c} skip_w={skip_w} fail={fail}"
    )
    if failures:
        print("  失败样例:", failures[:5])
    return {
        "commentary": ok_c,
        "witness": ok_w,
        "skip_commentary": skip_c,
        "skip_witness": skip_w,
        "fail": fail,
    }


def restore_relations(index_path: Path, *, dry_run: bool) -> dict:
    rl.validate_histograph_root()
    paths = rl.histograph_paths()
    rel_dir = paths["person_relations"]
    mysql = {
        "host": "49.235.165.220",
        "port": 3306,
        "user": "histomap_admin",
        "password": "pandahis#666",
        "db": "histomap",
    }
    files = sorted(rel_dir.glob("*关系表.json"))
    ok, skip, fail = 0, 0, 0
    failures: list[str] = []

    for fp in files:
        name = fp.stem.replace("关系表", "")
        try:
            entry = rl.find_entry(name=name, index_path=index_path)
        except KeyError:
            skip += 1
            continue
        except Exception as exc:  # noqa: BLE001
            skip += 1
            failures.append(f"{fp.name}: lookup {exc}")
            continue
        if not rl.is_person_entry(entry):
            skip += 1
            continue
        eid = str(entry.get("史略ID", "")).strip()
        if dry_run:
            ok += 1
            continue
        try:
            rl.import_json_file(fp, entry_id=eid, index_path=index_path, mysql=mysql)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            fail += 1
            failures.append(f"{eid} {name}: {exc}")

    print(f"[关系] ok={ok} skip={skip} fail={fail} files={len(files)}")
    if failures:
        print("  失败样例:", failures[:5])
    return {"ok": ok, "skip": skip, "fail": fail, "files": len(files)}


def print_db_counts() -> None:
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            for table in (
                "historical_box",
                "historical_box_detail",
                "box_critique",
                "box_relic",
                "box_graph_edge",
                "box_graph_node",
            ):
                cursor.execute(f"SELECT COUNT(*) AS c FROM `{table}`")
                print(f"  {table}: {cursor.fetchone()['c']}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复线上 MySQL 子表")
    parser.add_argument("--index", type=Path, default=ONLINE_INDEX)
    parser.add_argument("--skip-details", action="store_true")
    parser.add_argument("--skip-cw", action="store_true")
    parser.add_argument("--skip-relations", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.index.is_file():
        print(f"缺少索引: {args.index}", file=sys.stderr)
        return 1

    online_ids = load_online_ids(args.index)
    print(f"线上索引: {len(online_ids)} 条")
    print("恢复前 DB:")
    print_db_counts()

    summary = {}
    if not args.skip_details:
        summary["details"] = restore_details(online_ids, dry_run=args.dry_run)
    if not args.skip_cw:
        summary["cw"] = restore_commentary_witness(
            online_ids, args.index, dry_run=args.dry_run
        )
    if not args.skip_relations:
        summary["relations"] = restore_relations(args.index, dry_run=args.dry_run)

    print("summary:", json.dumps(summary, ensure_ascii=False))
    if not args.dry_run:
        print("恢复后 DB:")
        print_db_counts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
