"""翻译任务 SQLite 状态。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lib.config import paths

JOB_STATUSES = ("pending", "running", "done", "failed", "skipped")

JOB_COLUMNS = {
    "entry_name",
    "priority",
    "block_count",
    "paragraph_count",
    "status",
    "source_fingerprint",
    "output_word_count",
    "fail_count",
    "session_id",
    "started_at",
    "finished_at",
    "detail",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect() -> sqlite3.Connection:
    db_path = paths()["state_db"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS translate_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id TEXT NOT NULL UNIQUE,
                entry_name TEXT,
                priority TEXT,
                block_count INTEGER DEFAULT 0,
                paragraph_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                source_fingerprint TEXT,
                output_word_count INTEGER,
                fail_count INTEGER NOT NULL DEFAULT 0,
                session_id TEXT,
                started_at TEXT,
                finished_at TEXT,
                detail TEXT
            );
            CREATE TABLE IF NOT EXISTS translate_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        conn.commit()


def set_meta(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO translate_meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def get_meta(key: str) -> Optional[str]:
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM translate_meta WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None


def upsert_job(
    entry_id: str,
    *,
    entry_name: str = "",
    priority: str = "",
    block_count: int = 0,
    paragraph_count: int = 0,
    status: Optional[str] = None,
    reset_status: bool = False,
    **kwargs: Any,
) -> None:
    _validate_columns(kwargs)
    with connect() as conn:
        existing = conn.execute(
            "SELECT status FROM translate_jobs WHERE entry_id=?", (entry_id,)
        ).fetchone()
        if existing and not reset_status:
            conn.execute(
                """
                UPDATE translate_jobs SET
                    entry_name=?, priority=?, block_count=?, paragraph_count=?
                WHERE entry_id=?
                """,
                (entry_name, priority, block_count, paragraph_count, entry_id),
            )
        else:
            st = status or "pending"
            conn.execute(
                """
                INSERT INTO translate_jobs(
                    entry_id, entry_name, priority, block_count, paragraph_count, status
                ) VALUES(?,?,?,?,?,?)
                ON CONFLICT(entry_id) DO UPDATE SET
                    entry_name=excluded.entry_name,
                    priority=excluded.priority,
                    block_count=excluded.block_count,
                    paragraph_count=excluded.paragraph_count,
                    status=excluded.status
                """,
                (entry_id, entry_name, priority, block_count, paragraph_count, st),
            )
        if kwargs:
            cols = ", ".join(f"{k}=?" for k in kwargs)
            conn.execute(
                f"UPDATE translate_jobs SET {cols} WHERE entry_id=?",
                (*kwargs.values(), entry_id),
            )
        conn.commit()


def update_job(entry_id: str, **kwargs: Any) -> None:
    if not kwargs:
        return
    kwargs.setdefault("finished_at", utc_now()) if kwargs.get("status") in (
        "done",
        "failed",
        "skipped",
    ) else None
    _validate_columns(kwargs)
    cols = ", ".join(f"{k}=?" for k in kwargs)
    with connect() as conn:
        conn.execute(
            f"UPDATE translate_jobs SET {cols} WHERE entry_id=?",
            (*kwargs.values(), entry_id),
        )
        conn.commit()


def _validate_columns(kwargs: Dict[str, Any]) -> None:
    invalid = set(kwargs) - JOB_COLUMNS
    if invalid:
        raise ValueError(f"未知 translate_jobs 字段: {sorted(invalid)}")


def get_job(entry_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM translate_jobs WHERE entry_id=?", (entry_id,)
        ).fetchone()
        return dict(row) if row else None


def count_jobs(status: Optional[str] = None) -> int:
    with connect() as conn:
        if status:
            return conn.execute(
                "SELECT COUNT(*) FROM translate_jobs WHERE status=?", (status,)
            ).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM translate_jobs").fetchone()[0]


def list_jobs(
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    single_source_only: bool = False,
    from_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    clauses: List[str] = []
    params: List[Any] = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if priority:
        clauses.append("priority=?")
        params.append(priority)
    if single_source_only:
        clauses.append("block_count=1")
    if from_id:
        clauses.append("entry_id>=?")
        params.append(from_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM translate_jobs{where} ORDER BY entry_id LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def next_pending_job(
    *,
    from_id: Optional[str] = None,
    priority: Optional[str] = None,
    single_source_only: bool = False,
) -> Optional[Dict[str, Any]]:
    jobs = list_jobs(
        status="pending",
        from_id=from_id,
        priority=priority,
        single_source_only=single_source_only,
        limit=1,
    )
    return jobs[0] if jobs else None
