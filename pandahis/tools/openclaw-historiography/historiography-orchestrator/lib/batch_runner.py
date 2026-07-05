"""著作队列批量跑批：逐卷逐步仍走 LLM，编排层自动循环、少人工点确认。"""

from __future__ import annotations

import os
import time
from typing import List, Optional

from lib import db
from lib.config import get_work_config, queue_order
from lib import watchdog
from lib import work_runner
from lib import decisions


def batch_auto_enabled() -> bool:
    """无人值守：自动坐标决策 / 自动 resume（不含金标，金标须 hist approve-gold）。"""
    return os.environ.get("HIST_BATCH_AUTO") == "1"


def auto_gold_enabled() -> bool:
    return os.environ.get("HIST_AUTO_GOLD") == "1"


def _work_done(work: str) -> bool:
    w = db.get_work(work)
    return bool(w and w.get("work_approved"))


def _work_actionable(work: str) -> bool:
    w = db.get_work(work)
    if not w:
        return True
    if w.get("work_approved"):
        return False
    return w["status"] not in ("done",)


def _watchdog_snapshot(work: str, w: Optional[dict] = None) -> watchdog.WorkSnapshot:
    w = w or db.get_work(work) or {}
    return watchdog.WorkSnapshot(
        done=db.count_jobs(work, "done"),
        failed=db.count_jobs(work, "failed"),
        state=w.get("status") or "other",
        vol=(w.get("current_vol") or ""),
        step=(w.get("current_step") or ""),
        blocked=(w.get("blocked_reason") or ""),
    )


def try_auto_unblock(
    work: str,
    *,
    probe: Optional[watchdog.WatchdogObservation] = None,
) -> bool:
    """
    批量模式下尝试解除阻塞，返回 True 表示可继续 run_work。
    金标须事先 hist approve-gold，或设 HIST_AUTO_GOLD=1。
    """
    w = db.get_work(work)
    if not w:
        return True
    if probe and probe.should_probe:
        vol = (w.get("current_vol") or "").zfill(3)
        step = w.get("current_step") or "?"
        print(
            f"🩺 自动巡检 {work}: 连续 {probe.idle_rounds} 轮无新进展，"
            f"当前状态={w['status']} 卷{vol} Step{step}",
            flush=True,
        )

    if w["status"] == "awaiting_decision" and batch_auto_enabled():
        if probe and probe.should_escalate_block:
            print(
                f"🛑 {work} 同一阻塞连续 {probe.same_blocked_rounds} 轮未收敛，"
                f"停止盲目自动决策：{(w.get('blocked_reason') or '')[:120]}",
                flush=True,
            )
            return False
        vol = (w.get("current_vol") or "").zfill(3)
        choice = os.environ.get("HIST_AUTO_COORD", "emperor-ssot").strip()
        if vol and decisions.try_auto_coord_decision(work, vol, choice):
            print(f"🤖 批量自动坐标决策 {work} 卷{vol} → {choice}", flush=True)
            return True
        return False

    if w["status"] == "paused":
        if batch_auto_enabled():
            if probe and probe.should_escalate_block:
                print(
                    f"🛑 {work} 同一阻塞连续 {probe.same_blocked_rounds} 轮未收敛，"
                    f"停止盲目 auto-resume：{(w.get('blocked_reason') or '')[:120]}",
                    flush=True,
                )
                return False
            vol = (w.get("current_vol") or "").zfill(3)
            blocked = w.get("blocked_reason") or ""
            if vol and watchdog.is_mechanical_blocked_reason(blocked) and work.startswith("02汉书"):
                from lib.hanshu_autofix import repair_and_requeue_verify

                repaired, msg = repair_and_requeue_verify(work, vol)
                if repaired:
                    print(f"🔧 批量自动修复 {work} 卷{vol}: {msg}", flush=True)
            work_runner.resume(work)
            print(f"🤖 批量自动 resume {work}", flush=True)
            return True
        return False

    if (
        w["status"] == "gold_review"
        and not w.get("gold_approved")
        and auto_gold_enabled()
    ):
        work_runner.approve_gold(work)
        print(f"🤖 批量自动金标通过 {work}", flush=True)
        return True

    if (
        w["status"] == "work_review"
        and not w.get("work_approved")
        and os.environ.get("HIST_AUTO_WORK") == "1"
    ):
        work_runner.approve_work(work)
        print(f"🤖 批量自动封板 {work}", flush=True)
        return False

    return w["status"] in ("running", "bootstrapping", "queued", "gold_review", "work_review")


def _ensure_bootstrapped(work: str) -> None:
    if not db.get_work(work):
        work_runner.bootstrap(work)


def run_batch_for_work(
    work: str,
    *,
    max_jobs: Optional[int] = None,
    stop_on_fail: bool = False,
    watchdog_state: Optional[watchdog.WorkWatchdog] = None,
) -> int:
    """跑一本书直到无 pending、遇硬阻塞或达到 max_jobs。"""
    _ensure_bootstrapped(work)
    if _work_done(work):
        print(f"⏭  {work} 已封板，跳过", flush=True)
        return 0
    probe = None
    if watchdog_state is not None:
        probe = watchdog_state.observe(_watchdog_snapshot(work))
    if not try_auto_unblock(work, probe=probe):
        w = db.get_work(work) or {}
        print(
            f"⏸ {work} 阻塞（{w.get('status')}），"
            f"需人工处理或设 HIST_BATCH_AUTO=1",
            flush=True,
        )
        return 0
    return work_runner.run_work(
        work,
        max_jobs=max_jobs,
        stop_on_fail=stop_on_fail,
        one_volume=True,
    )


def run_batch(
    works: Optional[List[str]] = None,
    *,
    max_jobs: Optional[int] = None,
    loop: bool = False,
    sleep_sec: int = 120,
    max_rounds: Optional[int] = None,
) -> int:
    """
    按 catalog 队列逐著作跑批。
    - 不设 max_jobs：每轮每本书连续跑完所有 pending job（逐卷 Step1–4，LLM 步照常）
    - loop：遇暂停/失败时休眠后重试（配合 HIST_BATCH_AUTO）
    """
    db.init_schema()
    catalog = works or queue_order()
    if not catalog:
        print("⚠️ catalog 队列为空")
        return 1

    round_no = 0
    watchdogs = {
        work: watchdog.WorkWatchdog(watchdog.thresholds_for_work(work))
        for work in catalog
    }
    while True:
        round_no += 1
        if max_rounds is not None and round_no > max_rounds:
            break

        any_active = False
        for work in catalog:
            if _work_done(work):
                continue
            any_active = True
            cfg = get_work_config(work)
            print(
                f"\n{'=' * 52}\n"
                f"▶ 批量跑批 [{round_no}] {work}（{cfg.get('title', work)}）\n"
                f"{'=' * 52}",
                flush=True,
            )
            run_batch_for_work(
                work,
                max_jobs=max_jobs,
                stop_on_fail=False,
                watchdog_state=watchdogs.get(work),
            )

        if not any_active:
            print("\n✅ 队列中全部著作已封板", flush=True)
            return 0

        if not loop:
            break

        pending_total = sum(db.count_jobs(w, "pending") for w in catalog if db.get_work(w))
        failed_total = sum(db.count_jobs(w, "failed") for w in catalog if db.get_work(w))
        if pending_total == 0 and failed_total == 0:
            break

        print(
            f"\n💤 批量休眠 {sleep_sec}s（pending={pending_total} failed={failed_total}）…",
            flush=True,
        )
        time.sleep(sleep_sec)

    return 0


def format_batch_status(works: Optional[List[str]] = None) -> str:
    catalog = works or queue_order()
    lines = ["📊 批量进度摘要", ""]
    for work in catalog:
        w = db.get_work(work)
        if not w:
            lines.append(f"  {work:12s} 未 bootstrap")
            continue
        done = db.count_jobs(work, "done")
        total = db.count_jobs(work)
        pending = db.count_jobs(work, "pending")
        failed = db.count_jobs(work, "failed")
        lines.append(
            f"  {work:12s} {w['status']:16s} "
            f"done {done}/{total}  pending {pending}  failed {failed}"
        )
    return "\n".join(lines)
