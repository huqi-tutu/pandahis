#!/usr/bin/env python3
"""根据本地翻译/补全详情汇总，回填 historical_box.detail_source。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from detail_source import detail_source_to_db, infer_detail_source  # noqa: E402

DEFAULT_INDEX = ROOT / "data" / "03索引标注条目" / "史略索引_01至02.json"
DEFAULT_TRANSLATE = ROOT / "data" / "04史料翻译" / "史略翻译_汇总.json"
DEFAULT_DYNASTY_DETAIL = (
    ROOT / "data" / "06朝代知识补全" / "详情" / "朝代知识详情_汇总.json"
)


def _load_env() -> None:
    env_file = TOOLS / ".env"
    if not env_file.is_file():
        return
    import os

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def _entry_ids(json_path: Path) -> set[str]:
    if not json_path.is_file():
        return set()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    entries = data.get("entries") or data
    if not isinstance(entries, list):
        return set()
    out: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        eid = str(item.get("史略ID") or "").strip()
        if eid:
            out.add(eid)
    return out


def _load_index_entries(json_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    entries = data.get("entries")
    if isinstance(entries, list):
        return entries
    raise ValueError(f"无法解析索引: {json_path}")


def _connect():
    import os

    import pymysql

    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "49.235.165.220"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "histomap_admin"),
        password=os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        database=os.environ.get("MYSQL_DB", "histomap"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_column(cursor) -> None:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'historical_box'
          AND COLUMN_NAME = 'detail_source'
        """
    )
    if cursor.fetchone()["cnt"]:
        return
    cursor.execute(
        """
        ALTER TABLE historical_box
          ADD COLUMN detail_source VARCHAR(16) NULL
            COMMENT '详情来源: translate=史料顺译 compose=大模型撰写'
            AFTER entry_source
        """
    )


def sync_detail_source(
    *,
    index_path: Path,
    translate_path: Path,
    dynasty_detail_path: Path,
    dry_run: bool,
) -> int:
    translate_ids = _entry_ids(translate_path)
    dynasty_detail_ids = _entry_ids(dynasty_detail_path)
    entries = _load_index_entries(index_path)
    by_id = {str(e.get("史略ID") or "").strip(): e for e in entries if e.get("史略ID")}

    planned: dict[str, str] = {}
    for eid, entry in sorted(by_id.items()):
        label = infer_detail_source(
            entry,
            translate_ids=translate_ids,
            dynasty_detail_ids=dynasty_detail_ids,
        )
        db_val = detail_source_to_db(label)
        if db_val:
            planned[eid] = db_val

    if dry_run:
        translate_n = sum(1 for v in planned.values() if v == "translate")
        compose_n = sum(1 for v in planned.values() if v == "compose")
        print(f"[dry-run] 将更新 {len(planned)} 条 detail_source（顺译 {translate_n} / 撰写 {compose_n}）")
        return 0

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_column(cursor)
            updated = 0
            for eid, db_val in planned.items():
                cursor.execute(
                    """
                    UPDATE historical_box
                    SET detail_source=%s
                    WHERE id=%s AND (detail_source IS NULL OR detail_source<>%s)
                    """,
                    (db_val, eid, db_val),
                )
                updated += cursor.rowcount
        conn.commit()
        print(f"✅ detail_source 已更新 {updated} 条")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--translate-json", type=Path, default=DEFAULT_TRANSLATE)
    parser.add_argument("--dynasty-json", type=Path, default=DEFAULT_DYNASTY_DETAIL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()
    return sync_detail_source(
        index_path=args.index,
        translate_path=args.translate_json,
        dynasty_detail_path=args.dynasty_json,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
