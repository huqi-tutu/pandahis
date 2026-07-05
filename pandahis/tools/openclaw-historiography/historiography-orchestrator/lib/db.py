"""SQLite 状态：著作 / 卷 / job。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lib.config import paths

WORK_STATUSES = (
    "queued",
    "bootstrapping",
    "gold_review",
    "running",
    "paused",
    "awaiting_decision",
    "work_review",
    "merging",
    "done",
    "failed",
)

JOB_STATUSES = ("pending", "running", "done", "failed", "skipped")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect() -> sqlite3.Connection:
    db = paths()["state_db"]
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS works (
                id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                gold_approved INTEGER NOT NULL DEFAULT 0,
                work_approved INTEGER NOT NULL DEFAULT 0,
                volume_count INTEGER DEFAULT 0,
                volumes_done INTEGER DEFAULT 0,
                current_vol TEXT,
                current_step TEXT,
                blocked_reason TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS volumes (
                work_id TEXT NOT NULL,
                vol TEXT NOT NULL,
                volume_name TEXT,
                overall TEXT DEFAULT 'not_started',
                PRIMARY KEY (work_id, vol)
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id TEXT NOT NULL,
                vol TEXT NOT NULL,
                step TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                session_id TEXT,
                started_at TEXT,
                finished_at TEXT,
                detail TEXT,
                UNIQUE(work_id, vol, step)
            );
            """
        )
        _ensure_jobs_columns(conn)
        conn.commit()


def _ensure_jobs_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if "fail_count" not in cols:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN fail_count INTEGER NOT NULL DEFAULT 0"
        )


@contextmanager
def transaction():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_work(work_id: str, title: str, status: str = "queued", **kwargs: Any) -> None:
    init_schema()
    with transaction() as conn:
        row = conn.execute("SELECT id FROM works WHERE id=?", (work_id,)).fetchone()
        fields = {"title": title, "status": status, "updated_at": utc_now(), **kwargs}
        if row:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE works SET {sets} WHERE id=?",
                (*fields.values(), work_id),
            )
        else:
            cols = ["id"] + list(fields.keys())
            conn.execute(
                f"INSERT INTO works ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                (work_id, *fields.values()),
            )


def get_work(work_id: str) -> Optional[Dict[str, Any]]:
    init_schema()
    with connect() as conn:
        row = conn.execute("SELECT * FROM works WHERE id=?", (work_id,)).fetchone()
        return dict(row) if row else None


def set_work_status(work_id: str, status: str, **kwargs: Any) -> None:
    init_schema()
    with transaction() as conn:
        fields = {"status": status, "updated_at": utc_now(), **kwargs}
        sets = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE works SET {sets} WHERE id=?", (*fields.values(), work_id))


def ensure_jobs(work_id: str, vols: List[str], steps: List[str]) -> None:
    init_schema()
    with transaction() as conn:
        for vol in vols:
            conn.execute(
                "INSERT OR IGNORE INTO volumes (work_id, vol, overall) VALUES (?,?,?)",
                (work_id, vol, "not_started"),
            )
            for step in steps:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs (work_id, vol, step, status)
                    VALUES (?,?,?,?)
                    """,
                    (work_id, vol, step, "pending"),
                )


def next_pending_job(work_id: str) -> Optional[Dict[str, Any]]:
    """取下一 pending job；Step N 须 Step N-1 为 done/skipped。"""
    init_schema()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT j.* FROM jobs j
            WHERE j.work_id=? AND j.status='pending'
            AND (
                CAST(j.step AS INTEGER) = 1
                OR EXISTS (
                    SELECT 1 FROM jobs j0
                    WHERE j0.work_id = j.work_id AND j0.vol = j.vol
                      AND CAST(j0.step AS INTEGER) = CAST(j.step AS INTEGER) - 1
                      AND j0.status IN ('done', 'skipped')
                )
            )
            ORDER BY j.vol, CAST(j.step AS INTEGER)
            LIMIT 1
            """,
            (work_id,),
        ).fetchone()
        return dict(row) if row else None


def prior_step_status(work_id: str, vol: str, step: str) -> Optional[str]:
    """Step N 的直接前一步 job 状态；Step1 返回 None。"""
    init_schema()
    vol = vol.zfill(3)
    s = int(step)
    if s <= 1:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT status FROM jobs
            WHERE work_id=? AND vol=? AND step=?
            """,
            (work_id, vol, str(s - 1)),
        ).fetchone()
        return row[0] if row else None


def step_dependency_block_reason(work_id: str, vol: str, step: str) -> Optional[str]:
    """若本 step 因前序未过而不可运行，返回说明。"""
    prior = prior_step_status(work_id, vol, step)
    if prior is None:
        return None
    if prior in ("done", "skipped"):
        return None
    return (
        f"卷{vol.zfill(3)} Step{step} 须先完成 Step{int(step) - 1}"
        f"（当前 Step{int(step) - 1}={prior}）"
    )


def mark_volume_steps_done(work_id: str, vol: str, through_step: str) -> int:
    """将单卷 step1..through_step 标为 done（跳过 skipped 不动）。"""
    init_schema()
    vol = vol.zfill(3)
    with transaction() as conn:
        cur = conn.execute(
            """
            UPDATE jobs SET status='done', finished_at=?, fail_count=0,
                   detail=NULL, session_id=NULL, started_at=NULL
            WHERE work_id=? AND vol=? AND CAST(step AS INTEGER) <= CAST(? AS INTEGER)
              AND status NOT IN ('done', 'skipped')
            """,
            (utc_now(), work_id, vol, through_step),
        )
        conn.execute(
            "UPDATE volumes SET overall='in_progress' WHERE work_id=? AND vol=?",
            (work_id, vol),
        )
    return cur.rowcount


def reset_volume_step(work_id: str, vol: str, step: str) -> int:
    """重置单卷指定 step 为 pending。"""
    init_schema()
    vol = vol.zfill(3)
    with transaction() as conn:
        cur = conn.execute(
            """
            UPDATE jobs SET status='pending', detail=NULL, session_id=NULL,
                   started_at=NULL, finished_at=NULL, fail_count=0
            WHERE work_id=? AND vol=? AND step=?
            """,
            (work_id, vol, step),
        )
    return cur.rowcount


def count_blocked_pending_jobs(work_id: str) -> int:
    """pending 但因前序未 done 而暂不可跑的 job 数。"""
    init_schema()
    with connect() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) FROM jobs j
            WHERE j.work_id=? AND j.status='pending'
            AND CAST(j.step AS INTEGER) > 1
            AND NOT EXISTS (
                SELECT 1 FROM jobs j0
                WHERE j0.work_id = j.work_id AND j0.vol = j.vol
                  AND CAST(j0.step AS INTEGER) = CAST(j.step AS INTEGER) - 1
                  AND j0.status IN ('done', 'skipped')
            )
            """,
            (work_id,),
        ).fetchone()[0]


def get_job(work_id: str, vol: str, step: str) -> Optional[Dict[str, Any]]:
    init_schema()
    vol = vol.zfill(3)
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE work_id=? AND vol=? AND step=?",
            (work_id, vol, step),
        ).fetchone()
        return dict(row) if row else None


def update_job(job_id: int, **kwargs: Any) -> None:
    init_schema()
    with transaction() as conn:
        sets = ", ".join(f"{k}=?" for k in kwargs)
        conn.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*kwargs.values(), job_id))


def reset_volume_steps(work_id: str, vol: str, through_step: str = "3") -> int:
    """将单卷 step1..through_step 重置为 pending，供 Step3 打回后重跑。"""
    init_schema()
    vol = vol.zfill(3)
    with transaction() as conn:
        cur = conn.execute(
            """
            UPDATE jobs SET status='pending', detail=NULL, session_id=NULL,
                   started_at=NULL, finished_at=NULL, fail_count=0
            WHERE work_id=? AND vol=? AND CAST(step AS INTEGER) <= CAST(? AS INTEGER)
            """,
            (work_id, vol, through_step),
        )
        conn.execute(
            "UPDATE volumes SET overall='in_progress' WHERE work_id=? AND vol=?",
            (work_id, vol),
        )
    return cur.rowcount


def skip_volume_jobs(
    work_id: str, vol: str, reason: str, *, force: bool = False
) -> int:
    """整卷跳过：将该卷 job 标为 skipped（表卷/书卷等无叙事主人公）。

    force=True 时含已 done 的 job（纠正误入队的非叙事卷）。
    """
    init_schema()
    vol = vol.zfill(3)
    status_clause = "status != 'skipped'" if force else "status NOT IN ('done', 'skipped')"
    with transaction() as conn:
        cur = conn.execute(
            f"""
            UPDATE jobs SET status='skipped', detail=?, finished_at=?,
                   session_id=NULL, started_at=NULL, fail_count=0
            WHERE work_id=? AND vol=? AND {status_clause}
            """,
            (f"skipped:{reason}"[:2000], utc_now(), work_id, vol),
        )
        conn.execute(
            "UPDATE volumes SET overall='skipped' WHERE work_id=? AND vol=?",
            (work_id, vol),
        )
    return cur.rowcount


def retire_reference_step_jobs(work_id: str) -> int:
    """废止参考文献 Step5：将遗留 job 标为 skipped。"""
    init_schema()
    with transaction() as conn:
        cur = conn.execute(
            """
            UPDATE jobs SET status='skipped', detail='retired:参考文献环节已取消',
                   finished_at=?
            WHERE work_id=? AND step='5' AND status NOT IN ('done', 'skipped')
            """,
            (utc_now(), work_id),
        )
    return cur.rowcount


def reset_jobs(work_id: str) -> None:
    """将该著作全部 job 重置为 pending。"""
    init_schema()
    with transaction() as conn:
        conn.execute(
            """
            UPDATE jobs SET status='pending', detail=NULL, session_id=NULL,
                   started_at=NULL, finished_at=NULL, fail_count=0
            WHERE work_id=?
            """,
            (work_id,),
        )
        conn.execute(
            "UPDATE volumes SET overall='not_started' WHERE work_id=?",
            (work_id,),
        )


def count_jobs(work_id: str, status: Optional[str] = None) -> int:
    init_schema()
    with connect() as conn:
        if status:
            return conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE work_id=? AND status=?",
                (work_id, status),
            ).fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE work_id=?", (work_id,)
        ).fetchone()[0]
