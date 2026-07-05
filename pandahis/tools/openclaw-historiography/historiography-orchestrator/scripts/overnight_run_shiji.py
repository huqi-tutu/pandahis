#!/usr/bin/env python3
"""无人值守跑批：《史记》run-work + Step1/Step4 脚本自动修复 + 续跑。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANNOTATE = ORCH.parent / "historiography-annotate"
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ANNOTATE))

from lib import gates, shiji_autofix  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402
from paths_config import get_histograph_root  # noqa: E402

WORK = "01史记"
LOG = Path("/tmp/hist-overnight-shiji.log")
POLL_SEC = 60
MAX_IDLE_ROUNDS = 480  # ~8h


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def work_status() -> dict:
    r = subprocess.run(
        [sys.executable, str(ORCH / "hist.py"), "status", "--work", WORK],
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "HISTOGRAPH_ROOT": str(get_histograph_root())},
    )
    text = r.stdout + r.stderr
    m_done = re.search(r"done (\d+)/(\d+)", text)
    m_vol = re.search(r"当前: 卷(\d+) Step(\d+)", text)
    state = "paused" if "状态: paused" in text else "running" if "状态: running" in text else "other"
    blocked = ""
    if "阻塞:" in text:
        blocked = text.split("阻塞:", 1)[1].strip()[:500]
    return {
        "raw": text,
        "state": state,
        "done": int(m_done.group(1)) if m_done else 0,
        "total": int(m_done.group(2)) if m_done else 0,
        "vol": m_vol.group(1) if m_vol else "",
        "step": m_vol.group(2) if m_vol else "",
        "blocked": blocked,
    }


def try_autofix_paused(vol: str, step: str, blocked: str = "") -> bool:
    """按 Step 调用脚本修复；成功则更新 job 并 resume。"""
    if not vol or not step:
        return False

    if step == "1":
        repaired, msg = shiji_autofix.repair_step1_blocks(WORK, vol)
        if not repaired:
            log(f"  Step1 自动修复未过: {msg[:200]}")
            return False
        log(f"  Step1 blocks 已修复: {msg}")
        conn = connect()
        conn.execute(
            "UPDATE jobs SET status='pending', fail_count=0, detail='', "
            "session_id=NULL, started_at=NULL, finished_at=NULL "
            "WHERE work_id=? AND vol=? AND step='1'",
            (WORK, vol.zfill(3)),
        )
        conn.execute(
            "UPDATE works SET status='running', blocked_reason=NULL WHERE id=?",
            (WORK,),
        )
        conn.commit()
        return True

    if step == "4":
        repaired, msg = shiji_autofix.repair_step4_shiji(WORK, vol)
        if not repaired:
            log(f"  Step4 自动修复未过: {msg[:200]}")
            return False
        log(f"  Step4 已修复: {msg}")
        conn = connect()
        now = utc_now()
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step='4'",
            (now, WORK, vol.zfill(3)),
        )
        conn.execute(
            "UPDATE works SET status='running', blocked_reason=NULL WHERE id=?",
            (WORK,),
        )
        conn.commit()
        return True

    log(f"  Step{step} 暂无自动修复规则")
    return False


def resume_work() -> None:
    subprocess.run(
        [sys.executable, str(ORCH / "hist.py"), "resume", "--work", WORK],
        env={**dict(__import__("os").environ), "HISTOGRAPH_ROOT": str(get_histograph_root())},
    )


def run_work_once() -> int:
    p = subprocess.run(
        [sys.executable, str(ORCH / "hist.py"), "run-work", "--work", WORK, "--one-volume"],
        env={**dict(__import__("os").environ), "HISTOGRAPH_ROOT": str(get_histograph_root())},
    )
    return p.returncode


def ensure_run_work() -> None:
    lock = Path(get_histograph_root()) / "data/05工作流中间产物/orchestrator/locks/run-01史记.lock"
    pgrep = subprocess.run(["pgrep", "-f", f"hist.py run-work --work {WORK}"], capture_output=True)
    if pgrep.returncode != 0:
        if lock.exists():
            try:
                lock.unlink()
            except OSError:
                pass
        run_work_once()


def main() -> None:
    log("=== 史记无人值守跑批启动（Step1+Step4 自动修复）===")
    idle = 0
    last_done = -1
    pause_streak: dict[tuple[str, str], int] = {}
    MAX_PAUSE_STREAK = 5

    while idle < MAX_IDLE_ROUNDS:
        st = work_status()
        if st["done"] == st["total"] and st["total"] > 0:
            log(f"🎉 全部完成 {st['done']}/{st['total']}")
            return

        if st["state"] == "paused":
            vol, step = st["vol"], st["step"]
            key = (vol, step)
            log(f"⏸ 暂停 卷{vol} Step{step} | {st['done']}/{st['total']}")
            if st["blocked"]:
                log(f"  原因: {st['blocked'][:180]}")
            fixed = try_autofix_paused(vol, step, st.get("blocked", ""))
            streak = pause_streak.get(key, 0) + 1
            pause_streak[key] = 0 if fixed else streak
            if fixed:
                log("  → 脚本修复成功，续跑")
                idle = 0
            elif streak >= MAX_PAUSE_STREAK:
                log(
                    f"  → 卷{vol} Step{step} 已连续 {streak} 次脚本未修妥，"
                    "暂停 resume（避免 LLM 空转）；请补 PATCH/学界表或手修 skeleton"
                )
                idle += 1
                time.sleep(POLL_SEC)
                continue
            else:
                log(f"  → 脚本未修妥（{streak}/{MAX_PAUSE_STREAK}），仍 resume 交 run-work/LLM 再试")
                idle += 1
            resume_work()
            ensure_run_work()
            time.sleep(POLL_SEC)
            continue

        pgrep = subprocess.run(["pgrep", "-f", f"hist.py run-work --work {WORK}"], capture_output=True)
        if pgrep.returncode != 0:
            log(f"启动 run-work | 进度 {st['done']}/{st['total']}")
            ensure_run_work()
            if st["done"] == last_done:
                idle += 1
            else:
                idle = 0
            last_done = st["done"]
        else:
            if st["done"] != last_done:
                log(f"▶ 进行中 {st['done']}/{st['total']} | 卷{st['vol']} Step{st['step']}")
                last_done = st["done"]
                idle = 0
            time.sleep(POLL_SEC)

    log("⚠️ 达到最大空闲轮次，退出")


if __name__ == "__main__":
    main()
