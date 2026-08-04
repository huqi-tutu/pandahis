#!/usr/bin/env python3
"""元数据一致性审计与修复（史略来源 / 06 sidecar / 未 merge 条目）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
sys.path.insert(0, str(TOOLS))

from entry_source import (  # noqa: E402
    SOURCE_SUPPLEMENT,
    backfill_entries,
    entry_source_to_db,
    infer_entry_source,
)
from paths_config import histograph_paths  # noqa: E402


def load_entries(index_path: Path) -> tuple[list[dict], bool]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, True
    return list(data.get("entries") or []), False


def save_entries(index_path: Path, entries: list[dict], *, is_list: bool) -> None:
    if is_list:
        index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        data["entries"] = entries
        index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def supplement_ids_from_06() -> set[str]:
    ids: set[str] = set()
    idx_dir = ROOT / "data/06朝代知识补全/索引条目"
    for fp in idx_dir.glob("*.json"):
        if fp.name.startswith("旧"):
            continue
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            if str(e.get("史略来源", "")).strip() == SOURCE_SUPPLEMENT:
                eid = str(e.get("史略ID", "")).strip()
                if eid:
                    ids.add(eid)
    return ids


def audit(entries: list[dict], supp_ids: set[str]) -> dict:
    global_ids = {e["史略ID"] for e in entries}
    ids06_all: set[str] = set()
    idx_dir = ROOT / "data/06朝代知识补全/索引条目"
    for fp in idx_dir.glob("*.json"):
        if fp.name.startswith("旧"):
            continue
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            eid = str(e.get("史略ID", "")).strip()
            if eid:
                ids06_all.add(eid)

    only06 = sorted(ids06_all - global_ids)
    sidecar = [
        e for e in entries
        if e["史略ID"] in ids06_all
        and infer_entry_source(e) != SOURCE_SUPPLEMENT
    ]
    wrong_source = [
        e for e in entries
        if e["史略ID"] in supp_ids and infer_entry_source(e) != SOURCE_SUPPLEMENT
    ]
    return {
        "only06": only06,
        "sidecar": sidecar,
        "wrong_source": wrong_source,
    }


def sync_entry_source_mysql(entries: list[dict], *, dry_run: bool) -> int:
    import os

    import pymysql

    env = TOOLS / ".env"
    if env.is_file():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    conn = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        autocommit=False,
    )
    updated = 0
    try:
        with conn.cursor() as cur:
            for e in entries:
                eid = e["史略ID"]
                src = entry_source_to_db(infer_entry_source(e))
                if dry_run:
                    cur.execute(
                        "SELECT entry_source FROM historical_box WHERE id=%s", (eid,)
                    )
                    row = cur.fetchone()
                    if row and row[0] != src:
                        updated += 1
                    continue
                cur.execute(
                    "UPDATE historical_box SET entry_source=%s WHERE id=%s AND entry_source<>%s",
                    (src, eid, src),
                )
                updated += cur.rowcount
        if not dry_run:
            conn.commit()
    finally:
        conn.close()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="元数据一致性审计/修复")
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--fix-json", action="store_true", help="回填全局索引 史略来源")
    parser.add_argument("--sync-mysql", action="store_true", help="同步 entry_source 到 MySQL")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = histograph_paths()
    index_path = args.index or paths["global_index"]
    entries, is_list = load_entries(index_path)
    supp_ids = supplement_ids_from_06()
    report = audit(entries, supp_ids)

    print(f"索引: {index_path} ({len(entries)} 条)")
    print(f"06 标模型补全 ID: {len(supp_ids)}")
    print(f"❌ 补全来源错误（需 --fix-json）: {len(report['wrong_source'])}")
    print(f"ℹ️  06 sidecar（史料提取副本，无需改来源）: {len(report['sidecar'])}")
    print(f"⏳ 06 未 merge 进全局: {len(report['only06'])}")

    if report["wrong_source"]:
        for e in report["wrong_source"][:10]:
            print(f"  - {e['史略ID']} {e['史略名称']}")
    if report["only06"]:
        print(f"  例: {', '.join(report['only06'][:5])}{'…' if len(report['only06']) > 5 else ''}")

    if args.fix_json and not args.dry_run:
        new_entries, changed = backfill_entries(entries)
        if changed:
            save_entries(index_path, new_entries, is_list=is_list)
            print(f"✅ 已回填 JSON 史略来源 ({changed} 处)")
            entries = new_entries
        else:
            print("JSON 史略来源无需变更")

    if args.sync_mysql:
        n = sync_entry_source_mysql(entries, dry_run=args.dry_run)
        label = "将更新" if args.dry_run else "已更新"
        print(f"{'[dry-run] ' if args.dry_run else ''}{label} MySQL entry_source: {n} 条")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
