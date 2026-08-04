"""单条/批量史略翻译同步到线上 historical_box_detail。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.verify import load_output


def encode_source_original_json(source_original: Any) -> str | None:
    """将本地「史料原文」规范为 DB 列 JSON：{"text":"..."}（可附带 blocks）。"""
    if isinstance(source_original, str) and source_original.strip():
        return json.dumps({"text": source_original}, ensure_ascii=False)
    if isinstance(source_original, dict):
        text = str(source_original.get("text") or "").strip()
        if not text:
            blocks = source_original.get("blocks")
            if isinstance(blocks, list):
                parts: List[str] = []
                for block in blocks:
                    if isinstance(block, dict):
                        bt = str(block.get("text") or "").strip()
                        if bt:
                            parts.append(bt)
                    elif isinstance(block, str) and block.strip():
                        parts.append(block.strip())
                text = "\n".join(parts)
        if text:
            payload = dict(source_original)
            payload["text"] = text
            return json.dumps(payload, ensure_ascii=False)
    return None


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
              source_citation VARCHAR(512) NULL COMMENT '原文出处（母本著作名称）',
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
    if not _column_exists(cursor, "historical_box_detail", "source_citation"):
        cursor.execute(
            """
            ALTER TABLE historical_box_detail
              ADD COLUMN source_citation VARCHAR(512) NULL COMMENT '原文出处（母本著作名称）'
              AFTER source_original_json
            """
        )


def upsert_translate_detail(
    cursor,
    box_id: str,
    translate_detail: str,
    source_original_json: str | None = None,
    source_citation: str | None = None,
    *,
    detail_source: str | None = None,
) -> None:
    source_json = source_original_json if source_original_json is not None else None
    citation = (source_citation or "").strip() or None
    cursor.execute(
        """
        INSERT INTO historical_box_detail
          (box_id, translate_detail, source_original_json, source_citation)
        VALUES
          (%(box_id)s, %(translate_detail)s, %(source_original_json)s, %(source_citation)s)
        ON DUPLICATE KEY UPDATE
          translate_detail = VALUES(translate_detail),
          source_original_json = VALUES(source_original_json),
          source_citation = VALUES(source_citation)
        """,
        {
            "box_id": box_id,
            "translate_detail": translate_detail,
            "source_original_json": source_json,
            "source_citation": citation,
        },
    )
    if detail_source:
        _update_box_detail_source(cursor, box_id, detail_source)


def _column_exists_on_box(cursor, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'historical_box'
          AND COLUMN_NAME = %s
        """,
        (column_name,),
    )
    return cursor.fetchone()["cnt"] > 0


def _ensure_detail_source_column(cursor) -> None:
    if _column_exists_on_box(cursor, "detail_source"):
        return
    cursor.execute(
        """
        ALTER TABLE historical_box
          ADD COLUMN detail_source VARCHAR(16) NULL
            COMMENT '详情来源: translate=史料顺译 compose=大模型撰写'
            AFTER entry_source
        """
    )


def _update_box_detail_source(cursor, box_id: str, detail_source: str) -> None:
    value = str(detail_source or "").strip().lower()
    if value not in {"translate", "compose"}:
        return
    if not _column_exists_on_box(cursor, "detail_source"):
        _ensure_detail_source_column(cursor)
    cursor.execute(
        """
        UPDATE historical_box
        SET detail_source=%s
        WHERE id=%s
        """,
        (value, box_id),
    )


def sync_translate_detail(
    entry_id: str,
    translate_detail: str,
    *,
    source_text: str | None = None,
    source_original: Any = None,
    source_citation: str | None = None,
    dry_run: bool = False,
    detail_source: str | None = "translate",
) -> Tuple[bool, str]:
    """将单条翻译详情 upsert 到线上 DB（不删除其它记录）。"""
    detail = str(translate_detail or "").strip()
    if not detail:
        return False, "翻译详情为空"

    if source_original is not None:
        source_json = encode_source_original_json(source_original)
    elif source_text:
        source_json = encode_source_original_json(source_text)
    else:
        source_json = None
    citation = (source_citation or "").strip() or None

    if dry_run:
        text_len = 0
        if source_json:
            try:
                text_len = len(json.loads(source_json).get("text") or "")
            except Exception:
                text_len = len(source_json)
        extra = f"，原文 {text_len} 字" if source_json else ""
        if citation:
            extra += f"，出处 {citation}"
        return True, f"dry-run: 将 upsert {entry_id}（{len(detail)} 字{extra}）"

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            ensure_schema(cursor)
            upsert_translate_detail(
                cursor, entry_id, detail, source_json, citation, detail_source=detail_source
            )
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
    citation = data.get("原文出处")
    return sync_translate_detail(
        entry_id,
        detail,
        source_original=source_original,
        source_citation=str(citation).strip() if citation else None,
        dry_run=dry_run,
        detail_source="translate",
    )


def _rows_from_aggregate_json(json_path: Path) -> List[Dict[str, Any]]:
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
        citation = item.get("原文出处")
        rows.append(
            {
                "box_id": box_id,
                "translate_detail": str(detail),
                "source_original_json": encode_source_original_json(source_original),
                "source_citation": (
                    str(citation).strip() if isinstance(citation, str) and citation.strip() else None
                ),
                "detail_source": "translate",
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
            row["detail_source"] = "compose"
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
                    row.get("source_citation"),
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
