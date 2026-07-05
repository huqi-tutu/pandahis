#!/usr/bin/env python3
"""标注进度同步：每完成 N 卷写入日志，并可选唤醒 Cursor agent。"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ORCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ORCH_DIR))

from lib.config import paths, orch_state_dir  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _progress_path(work: str) -> Path:
    return paths()["progress"] / f"{work}_progress.json"


def _meta_dir() -> Path:
    return orch_state_dir()


def _state_path(work: str) -> Path:
    return _meta_dir() / f"sync_state_{work}.json"


def _log_path(work: str) -> Path:
    return _meta_dir() / f"sync_{work}.log"


def load_state(work: str) -> dict:
    fp = _state_path(work)
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return {"last_milestone": 0, "last_failed_jobs": 0}


def save_state(work: str, state: dict) -> None:
    fp = _state_path(work)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot(work: str) -> dict:
    done_vols: list[str] = []
    volume_names: dict[str, str] = {}
    prog = _progress_path(work)
    if prog.exists():
        data = json.loads(prog.read_text(encoding="utf-8"))
        for vol, rec in sorted(data.get("volumes", {}).items(), key=lambda x: x[0]):
            if rec.get("overall") == "done":
                done_vols.append(vol)
                volume_names[vol] = rec.get("volume_name") or vol

    info: dict = {
        "done_count": len(done_vols),
        "done_vols": done_vols,
        "volume_names": volume_names,
        "jobs_done": 0,
        "jobs_pending": 0,
        "jobs_failed": 0,
        "work_status": None,
        "current_vol": None,
        "current_step": None,
        "batch_running": False,
    }

    db = paths()["state_db"]
    if db.exists():
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT status, current_vol, current_step FROM works WHERE id=?",
            (work,),
        ).fetchone()
        if row:
            info["work_status"] = row[0]
            info["current_vol"] = row[1]
            info["current_step"] = row[2]
        info["jobs_done"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE work_id=? AND status='done'",
            (work,),
        ).fetchone()[0]
        info["jobs_pending"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE work_id=? AND status='pending'",
            (work,),
        ).fetchone()[0]
        info["jobs_failed"] = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE work_id=? AND status='failed'",
            (work,),
        ).fetchone()[0]
        conn.close()

    import subprocess

    try:
        r = subprocess.run(
            ["pgrep", "-f", f"hist.py run-work --work {work}"],
            capture_output=True,
            text=True,
        )
        info["batch_running"] = r.returncode == 0
    except Exception:
        pass

    return info


def format_milestone_block(work: str, milestone: int, snap: dict, *, final: bool = False) -> str:
    done_vols = snap["done_vols"]
    total = 58
    last_vol = done_vols[-1] if done_vols else "?"
    last_name = snap["volume_names"].get(last_vol, "")
    title = f"全书完成 {total}/{total}" if final else f"里程碑 {milestone} 卷完成"
    lines = [
        "=" * 60,
        f"[{_utc_now()}] {work} — {title}",
        f"  已完成卷: {snap['done_count']}/{total}",
        f"  本段末卷: {last_vol} {last_name}".rstrip(),
        f"  jobs: done={snap['jobs_done']} pending={snap['jobs_pending']} failed={snap['jobs_failed']}",
    ]
    if snap.get("current_vol"):
        lines.append(
            f"  进行中: 卷{snap['current_vol']} Step{snap.get('current_step') or '?'}"
        )
    lines.append(f"  批处理进程: {'运行中' if snap['batch_running'] else '未检测到'}")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"


def append_log(work: str, text: str) -> Path:
    fp = _log_path(work)
    fp.parent.mkdir(parents=True, exist_ok=True)
    with fp.open("a", encoding="utf-8") as f:
        f.write(text)
    return fp


def emit_wake(log_fp: Path, work: str, milestone: int) -> None:
    payload = json.dumps(
        {
            "prompt": (
                f"读取 {log_fp} 最新一段里程碑记录，用中文向用户汇报"
                f" {work} 标注进度（每10卷同步）。"
            )
        },
        ensure_ascii=False,
    )
    print(f"AGENT_LOOP_WAKE_hist-progress {payload}", flush=True)


def check_and_sync(
    work: str,
    *,
    every_n: int = 10,
    total_vols: int = 58,
    wake_agent: bool = True,
) -> list[int]:
    """返回本次新写入的里程碑列表。"""
    state = load_state(work)
    snap = snapshot(work)
    done = snap["done_count"]
    last_ms = int(state.get("last_milestone", 0))
    emitted: list[int] = []

    # 失败 job 立即记一条（去重）
    failed = int(snap["jobs_failed"])
    if failed > int(state.get("last_failed_jobs", 0)):
        block = (
            f"\n!!! [{_utc_now()}] {work} 出现失败 job: {failed} 个 !!!\n"
            f"  当前卷: {snap.get('current_vol')} Step{snap.get('current_step')}\n"
            f"  请 hist resume --work {work}\n\n"
        )
        log_fp = append_log(work, block)
        state["last_failed_jobs"] = failed
        if wake_agent:
            emit_wake(log_fp, work, -1)
        save_state(work, state)

    next_ms = last_ms + every_n if last_ms > 0 else every_n
    while done >= next_ms and next_ms <= total_vols:
        block = format_milestone_block(work, next_ms, snap, final=(next_ms >= total_vols))
        log_fp = append_log(work, block + "\n")
        print(block, flush=True)
        if wake_agent:
            emit_wake(log_fp, work, next_ms)
        emitted.append(next_ms)
        last_ms = next_ms
        state["last_milestone"] = last_ms
        next_ms += every_n

    if done >= total_vols and state.get("final_logged") is not True:
        if total_vols not in emitted:
            block = format_milestone_block(work, total_vols, snap, final=True)
            log_fp = append_log(work, block + "\n")
            print(block, flush=True)
            if wake_agent:
                emit_wake(log_fp, work, total_vols)
        state["final_logged"] = True

    save_state(work, state)
    return emitted


def main() -> int:
    parser = argparse.ArgumentParser(description="尚书等著作标注进度同步")
    parser.add_argument("--work", required=True)
    parser.add_argument("--every-n-vols", type=int, default=10)
    parser.add_argument("--total-vols", type=int, default=58)
    parser.add_argument("--poll", type=int, default=60, help="轮询秒数；0=只跑一次")
    parser.add_argument("--no-wake", action="store_true", help="不输出 AGENT_LOOP_WAKE")
    parser.add_argument("--backfill", action="store_true", help="补写已错过的里程碑")
    args = parser.parse_args()

    if args.backfill:
        state = load_state(args.work)
        snap = snapshot(args.work)
        done = snap["done_count"]
        every_n = args.every_n_vols
        milestones = [m for m in range(every_n, done + 1, every_n)]
        if milestones:
            state["last_milestone"] = 0
            save_state(args.work, state)
        for _ in milestones:
            check_and_sync(
                args.work,
                every_n=every_n,
                total_vols=args.total_vols,
                wake_agent=not args.no_wake,
            )
        return 0

    if args.poll <= 0:
        check_and_sync(
            args.work,
            every_n=args.every_n_vols,
            total_vols=args.total_vols,
            wake_agent=not args.no_wake,
        )
        return 0

    print(
        f"📡 进度同步守护: {args.work} 每 {args.every_n_vols} 卷 → {_log_path(args.work)}",
        flush=True,
    )
    while True:
        try:
            check_and_sync(
                args.work,
                every_n=args.every_n_vols,
                total_vols=args.total_vols,
                wake_agent=not args.no_wake,
            )
        except Exception as e:
            append_log(args.work, f"\n[sync error {_utc_now()}] {e}\n")
        time.sleep(args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
