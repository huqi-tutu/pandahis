#!/usr/bin/env python3
"""将厚度审计 downgrade 条目从线上清除（与「仅索引上线」同逻辑）。

- historical_box: status=0（小程序不可见）
- historical_box_detail: DELETE（含已有详情的 3 条）
- 本地翻译：移入归档目录并从汇总 JSON 剔除

用法:
  python3 offline_downgrade_glbl.py --dry-run
  python3 offline_downgrade_glbl.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
CROSS_JSON = ROOT / "data" / "05工作流中间产物" / "薄标注待补全" / "downgrade_cross_table.json"
TRANSLATE_DIR = ROOT / "data" / "04史料翻译"
AGGREGATE_JSON = TRANSLATE_DIR / "史略翻译_汇总.json"
ARCHIVE_DIR = ROOT / "data" / "05工作流中间产物" / "薄标注待补全" / "archived_translations"
LOG_JSON = ROOT / "data" / "05工作流中间产物" / "薄标注待补全" / "offline_downgrade_log.json"

TOOLS = ROOT / "tools" / "openclaw-historiography"


def _load_env() -> None:
    env_file = TOOLS / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _mysql_connect():
    import pymysql

    _load_env()
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
    )


def load_downgrade_ids() -> list[dict[str, Any]]:
    doc = json.loads(CROSS_JSON.read_text(encoding="utf-8"))
    return list(doc.get("entries") or [])


def offline_mysql(ids: list[str], *, dry_run: bool) -> dict[str, Any]:
    if not ids:
        return {"box_updated": 0, "detail_deleted": 0}
    if dry_run:
        return {"box_updated": len(ids), "detail_deleted": "dry-run", "ids": ids}

    conn = _mysql_connect()
    ph = ",".join(["%s"] * len(ids))
    stats: dict[str, Any] = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE historical_box SET status=0 WHERE id IN ({ph})",
                ids,
            )
            stats["box_updated"] = cur.rowcount
            cur.execute(
                f"DELETE FROM historical_box_detail WHERE box_id IN ({ph})",
                ids,
            )
            stats["detail_deleted"] = cur.rowcount
            cur.execute(
                f"SELECT id, status FROM historical_box WHERE id IN ({ph})",
                ids,
            )
            stats["verify"] = {str(r["id"]): int(r["status"]) for r in cur.fetchall()}
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return stats


def archive_local_translations(entries: list[dict[str, Any]], *, dry_run: bool) -> list[str]:
    archived: list[str] = []
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for row in entries:
        fp = row.get("translate_file")
        if not fp or not row.get("has_local_translation"):
            continue
        src = ROOT / fp
        if not src.is_file():
            continue
        dst = ARCHIVE_DIR / src.name
        if dry_run:
            archived.append(str(src))
            continue
        shutil.move(str(src), str(dst))
        archived.append(str(dst.relative_to(ROOT)))

    if not AGGREGATE_JSON.is_file():
        return archived

    doc = json.loads(AGGREGATE_JSON.read_text(encoding="utf-8"))
    ids = {row["史略ID"] for row in entries}
    before = len(doc.get("entries") or [])
    if isinstance(doc.get("entries"), list):
        doc["entries"] = [e for e in doc["entries"] if str(e.get("史略ID")) not in ids]
        doc["count"] = len(doc["entries"])
        doc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not dry_run:
            AGGREGATE_JSON.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    archived.append(f"aggregate: {before} -> {doc.get('count', before)}")
    return archived


def main() -> int:
    parser = argparse.ArgumentParser(description="下线 downgrade GLBL 条目")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not CROSS_JSON.is_file():
        print(f"❌ 缺少 {CROSS_JSON}")
        return 1

    entries = load_downgrade_ids()
    ids = [str(e["史略ID"]) for e in entries]
    print(f"待下线 {len(ids)} 条（含已有详情 {sum(1 for e in entries if e.get('online_detail'))} 条）")

    db_stats = offline_mysql(ids, dry_run=args.dry_run)
    archived = archive_local_translations(entries, dry_run=args.dry_run)

    log = {
        "schema": "offline_downgrade_log/v1",
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": args.dry_run,
        "ids": ids,
        "db": db_stats,
        "archived_local": archived,
        "action": "historical_box.status=0; DELETE historical_box_detail; archive local translate",
    }
    if not args.dry_run:
        LOG_JSON.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(log, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print(f"\n✅ 日志 → {LOG_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
