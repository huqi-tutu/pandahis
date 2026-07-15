"""单条/批量史略翻译同步到线上 historical_box_detail。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.verify import load_output


def auto_sync_enabled() -> bool:
    return os.environ.get("TRANSLATE_AUTO_SYNC", "1") != "0"


def mysql_settings() -> Dict[str, Any]:
    return {
        "host": os.environ.get("MYSQL_HOST", "49.235.165.220"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "histomap_admin"),
        "password": os.environ.get("MYSQL_PASSWORD", "pandahis#666"),
        "database": os.environ.get("MYSQL_DB", "histomap"),
    }


def _connect():
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("需要 pymysql: pip install pymysql") from exc

    cfg = mysql_settings()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
        """,
        (table_name,),
    )
    return cursor.fetchone()["cnt"] > 0


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    return cursor.fetchone()["cnt"] > 0


def ensure_schema(cursor) -> None:
    if not _table_exists(cursor, "historical_box_detail"):
        cursor.execute(
            """
            CREATE TABLE historical_box_detail (
              box_id VARCHAR(64) PRIMARY KEY COMMENT '史略ID',
              translate_detail LONGTEXT NOT NULL COMMENT '翻译详情',
              source_original_json LONGTEXT NULL COMMENT '史料原文 JSON（含 text/blocks）',
              CONSTRAINT fk_box_detail_box FOREIGN KEY (box_id) REFERENCES historical_box (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='史略翻译详情'
            """
        )
        return
    if not _column_exists(cursor, "historical_box_detail", "source_original_json"):
        cursor.execute(
            """
            ALTER TABLE historical_box_detail
              ADD COLUMN source_original_json LONGTEXT NULL COMMENT '史料原文 JSON（含 text/blocks）'
              AFTER translate_detail
            """
        )


def upsert_translate_detail(
    cursor,
    box_id: str,
    translate_detail: str,
    source_original_json: str | None = None,
) -> None:
    source_json = source_original_json if source_original_json is not None else None
    cursor.execute(
        """
        INSERT INTO historical_box_detail (box_id, translate_detail, source_original_json)
        VALUES (%(box_id)s, %(translate_detail)s, %(source_original_json)s)
        ON DUPLICATE KEY UPDATE
          translate_detail = VALUES(translate_detail),
          source_original_json = VALUES(source_original_json)
        """,
        {
            "box_id": box_id,
            "translate_detail": translate_detail,
            "source_original_json": source_json,
        },
    )


def sync_translate_detail(
    entry_id: str,
    translate_detail: str,
    *,
    source_text: str | None = None,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """将单条翻译详情 upsert 到线上 DB（不删除其它记录）。"""
    detail = str(translate_detail or "").strip()
    if not detail:
        return False, "翻译详情为空"

    source_json = source_text if source_text else None

    if dry_run:
        extra = f"，原文 {len(source_json or '')} 字" if source_json else ""
        return True, f"dry-run: 将 upsert {entry_id}（{len(detail)} 字{extra}）"

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            upsert_translate_detail(cursor, entry_id, detail, source_json)
        conn.commit()
        return True, f"{len(detail)} 字已写入 historical_box_detail"
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def sync_output_entry(
    entry_id: str,
    output_dir: Path,
    entry_name: str = "",
    *,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    ok, data, errs = load_output(entry_id, output_dir, entry_name)
    if not ok:
        return False, "; ".join(errs) or "无法读取产出 JSON"
    detail = str(data.get("翻译详情") or "")
    source_original = data.get("史料原文")
    if isinstance(source_original, str) and source_original.strip():
        return sync_translate_detail(
            entry_id, detail, source_text=source_original, dry_run=dry_run
        )
    if isinstance(source_original, dict) and source_original.get("text", "").strip():
        return sync_translate_detail(
            entry_id, detail, source_text=source_original["text"], dry_run=dry_run
        )
    return sync_translate_detail(entry_id, detail, dry_run=dry_run)


def _rows_from_aggregate_json(json_path: Path) -> List[Dict[str, Any]]:
    import json

    with json_path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    entries = data.get("entries") or []
    if not isinstance(entries, list):
        raise ValueError(f"{json_path} 缺少 entries 数组")

    rows: List[Dict[str, Any]] = []
    for item in entries:
        box_id = str(item["史略ID"]).strip()
        detail = item.get("翻译详情")
        if detail is None:
            raise ValueError(f"史略 {box_id} 缺少 翻译详情")
        source_original = item.get("史料原文")
        source_json = None
        if isinstance(source_original, str) and source_original.strip():
            source_json = source_original
        elif isinstance(source_original, dict) and source_original.get("text", "").strip():
            source_json = source_original["text"]
        rows.append(
            {
                "box_id": box_id,
                "translate_detail": str(detail),
                "source_original_json": source_json,
            }
        )
    return rows


def sync_all_box_details(
    *,
    translate_json: Path | None = None,
    dynasty_detail_json: Path | None = None,
    dry_run: bool = False,
    prune_orphans: bool = True,
) -> Tuple[bool, str]:
    """合并翻译汇总与朝代知识详情汇总，全量 upsert 到 historical_box_detail。"""
    merged: Dict[str, Dict[str, Any]] = {}
    sources: List[str] = []

    if translate_json and translate_json.is_file():
        tr_rows = _rows_from_aggregate_json(translate_json)
        for row in tr_rows:
            merged[row["box_id"]] = row
        sources.append(f"翻译 {len(tr_rows)} 条")
    if dynasty_detail_json and dynasty_detail_json.is_file():
        dk_rows = _rows_from_aggregate_json(dynasty_detail_json)
        for row in dk_rows:
            existing = merged.get(row["box_id"])
            if existing and existing["translate_detail"].strip():
                continue
            merged[row["box_id"]] = row
        sources.append(f"朝代补全 {len(dk_rows)} 条")

    rows = [merged[k] for k in sorted(merged)]
    if not rows:
        return False, "没有可同步的详情记录"

    if dry_run:
        return True, f"dry-run: 将导入 {len(rows)} 条（{' + '.join(sources)}）"

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            for row in rows:
                upsert_translate_detail(
                    cursor,
                    row["box_id"],
                    row["translate_detail"],
                    row.get("source_original_json"),
                )
            deleted = 0
            if prune_orphans:
                json_ids = [row["box_id"] for row in rows]
                if json_ids:
                    placeholders = ", ".join(["%s"] * len(json_ids))
                    cursor.execute(
                        f"DELETE FROM historical_box_detail WHERE box_id NOT IN ({placeholders})",
                        json_ids,
                    )
                    deleted = cursor.rowcount
                else:
                    cursor.execute("DELETE FROM historical_box_detail")
                    deleted = cursor.rowcount
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_box_detail")
            final_count = cursor.fetchone()["cnt"]
        conn.commit()
        return (
            True,
            f"导入/更新 {len(rows)} 条（{' + '.join(sources)}），"
            f"删除多余 {deleted} 条，当前共 {final_count} 条",
        )
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def sync_all_from_aggregate(
    json_path: Path,
    *,
    dry_run: bool = False,
    prune_orphans: bool = True,
) -> Tuple[bool, str]:
    """从汇总 JSON 全量同步（可选删除 JSON 中不存在的 orphan 记录）。"""
    try:
        rows = _rows_from_aggregate_json(json_path)
    except ValueError as exc:
        return False, str(exc)

    if dry_run:
        return True, f"dry-run: 将导入 {len(rows)} 条"

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            for row in rows:
                upsert_translate_detail(
                    cursor,
                    row["box_id"],
                    row["translate_detail"],
                    row.get("source_original_json"),
                )
            deleted = 0
            if prune_orphans:
                json_ids = [row["box_id"] for row in rows]
                if json_ids:
                    placeholders = ", ".join(["%s"] * len(json_ids))
                    cursor.execute(
                        f"DELETE FROM historical_box_detail WHERE box_id NOT IN ({placeholders})",
                        json_ids,
                    )
                    deleted = cursor.rowcount
                else:
                    cursor.execute("DELETE FROM historical_box_detail")
                    deleted = cursor.rowcount
            cursor.execute("SELECT COUNT(*) AS cnt FROM historical_box_detail")
            final_count = cursor.fetchone()["cnt"]
        conn.commit()
        return (
            True,
            f"导入/更新 {len(rows)} 条，删除多余 {deleted} 条，"
            f"当前共 {final_count} 条",
        )
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()
