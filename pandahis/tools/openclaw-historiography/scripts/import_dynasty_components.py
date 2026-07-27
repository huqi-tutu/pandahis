#!/usr/bin/env python3
"""将 07/08/09 本地 JSON 批量导入 MySQL（仅导入，不调用 LLM）。"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CW_DIR = ROOT / "historiography-commentary-witness" / "scripts"
REL_DIR = ROOT / "historiography-person-relations" / "scripts"
sys.path.insert(0, str(CW_DIR))
sys.path.insert(0, str(REL_DIR))
sys.path.insert(0, str(ROOT))

import cw_lib as cw  # noqa: E402
import import_cw_lib as icw  # noqa: E402
import relations_lib as rl  # noqa: E402


def _manifest_completed(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    return list(doc.get("completed") or [])


def import_commentary_witness(
    dynasty: str,
    *,
    dry_run: bool,
    mysql: dict[str, Any],
) -> dict[str, int]:
    paths = cw.histograph_paths()
    data_root = paths["commentary"].parent
    c_items = _manifest_completed(data_root / "08评述" / f"{dynasty}_评述_manifest.json")
    w_items = _manifest_completed(data_root / "09见证" / f"{dynasty}_见证_manifest.json")
    ids = sorted({str(x.get("glbl") or "").strip() for x in c_items + w_items if x.get("glbl")})

    stats = {"commentary_files": 0, "witness_files": 0, "commentary_rows": 0, "witness_rows": 0, "ids": len(ids)}
    all_stmts: list[str] = []

    for eid in ids:
        entry = cw.find_entry(entry_id=eid)
        for mode in ("commentary", "witness"):
            fp = cw.output_path(mode, entry, paths)  # type: ignore[arg-type]
            if not fp.is_file():
                continue
            doc = icw.load_json(fp)
            stmts = icw.build_critique_sql(doc) if mode == "commentary" else icw.build_relic_sql(doc)
            rows = max(0, len(stmts) - 1)
            if mode == "commentary":
                stats["commentary_files"] += 1
                stats["commentary_rows"] += rows
            else:
                stats["witness_files"] += 1
                stats["witness_rows"] += rows
            all_stmts.extend(stmts)

    if dry_run:
        print(f"[dry-run] {dynasty} CW: {stats}")
        return stats

    if all_stmts:
        icw.execute_mysql(all_stmts, **mysql)
    print(
        f"✅ {dynasty} 评述/见证入库：{stats['commentary_files']} 文件 / {stats['commentary_rows']} 行评述，"
        f"{stats['witness_files']} 文件 / {stats['witness_rows']} 行见证"
    )
    return stats


def import_relations(
    dynasty: str,
    *,
    dry_run: bool,
    mysql: dict[str, Any],
) -> dict[str, int]:
    paths = rl.histograph_paths()
    rel_dir = paths["person_relations"]
    items = _manifest_completed(rel_dir / f"{dynasty}_关系补全_manifest.json")
    stats = {"files": 0, "edges": 0, "errors": 0}

    for item in items:
        eid = str(item.get("glbl") or "").strip()
        fname = str(item.get("file") or "").strip()
        if not eid or not fname:
            continue
        fp = rel_dir / fname
        if not fp.is_file():
            print(f"⚠️ {dynasty} 关系缺失文件: {fname} ({eid})")
            stats["errors"] += 1
            continue
        if dry_run:
            stats["files"] += 1
            stats["edges"] += int(item.get("count") or 0)
            continue
        try:
            rl.import_json_file(fp, entry_id=eid, mysql=mysql)
            stats["files"] += 1
            stats["edges"] += int(item.get("count") or 0)
        except Exception as ex:
            stats["errors"] += 1
            print(f"❌ {dynasty} 关系入库失败 {eid} {fname}: {ex}")
            traceback.print_exc()

    if dry_run:
        print(f"[dry-run] {dynasty} 关系: {stats}")
    else:
        print(f"✅ {dynasty} 关系入库：{stats['files']} 文件，约 {stats['edges']} 条关系，失败 {stats['errors']}")
    return stats


def verify_mysql_counts(dynasty: str, sample_ids: list[str], mysql: dict[str, Any]) -> None:
    import pymysql  # noqa: WPS433

    if not sample_ids:
        return
    conn = pymysql.connect(
        host=mysql["host"],
        port=int(mysql["port"]),
        user=mysql["user"],
        password=mysql.get("password", ""),
        database=mysql["db"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            for eid in sample_ids[:3]:
                cur.execute("SELECT COUNT(*) FROM box_critique WHERE box_id=%s", (eid,))
                c = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM box_relic WHERE box_id=%s", (eid,))
                r = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM box_graph_node WHERE box_id=%s", (eid,))
                g = cur.fetchone()[0]
                print(f"  抽查 {eid}: 评述={c} 见证={r} 关系节点={g}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="批量导入朝代组件数据到 MySQL")
    parser.add_argument(
        "--dynasties",
        nargs="+",
        default=["五帝", "夏", "商", "西周"],
        help="朝代名称",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-relations", action="store_true")
    parser.add_argument("--skip-cw", action="store_true")
    parser.add_argument("--mysql-host", default="49.235.165.220")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", default="histomap_admin")
    parser.add_argument("--mysql-password", default="pandahis#666")
    parser.add_argument("--mysql-db", default="histomap")
    args = parser.parse_args()

    cw.validate_histograph_root()
    rl.validate_histograph_root()
    mysql = {
        "host": args.mysql_host,
        "port": args.mysql_port,
        "user": args.mysql_user,
        "password": args.mysql_password,
        "db": args.mysql_db,
    }

    summary: dict[str, Any] = {}
    for dynasty in args.dynasties:
        print(f"\n========== {dynasty} ==========", flush=True)
        part: dict[str, Any] = {}
        if not args.skip_cw:
            part["cw"] = import_commentary_witness(dynasty, dry_run=args.dry_run, mysql=mysql)
        if not args.skip_relations:
            part["relations"] = import_relations(dynasty, dry_run=args.dry_run, mysql=mysql)
        summary[dynasty] = part

        if not args.dry_run:
            paths = cw.histograph_paths()
            data_root = paths["commentary"].parent
            c_items = _manifest_completed(data_root / "08评述" / f"{dynasty}_评述_manifest.json")
            sample = [str(x.get("glbl") or "").strip() for x in c_items[:3] if x.get("glbl")]
            print(f"--- {dynasty} 入库抽查 ---")
            verify_mysql_counts(dynasty, sample, mysql)

    out = cw.histograph_paths()["commentary"].parent / "05工作流中间产物" / "组件入库" / "import_dynasty_components_summary.json"
    if not args.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nsummary → {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
