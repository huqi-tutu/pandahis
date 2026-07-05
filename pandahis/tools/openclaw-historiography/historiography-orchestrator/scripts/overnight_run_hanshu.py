#!/usr/bin/env python3
"""无人值守跑批：《汉书》逐卷 Step1–4（LLM），遇暂停自动 resume。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
_ROOT = ORCH.parent
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(_ROOT))

# 加载 .env（nohup 子进程不继承交互 shell 环境）
_env_file = _ROOT / ".env"
if _env_file.is_file():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())

from paths_config import get_histograph_root  # noqa: E402
from lib.watchdog import (  # noqa: E402
    WorkSnapshot,
    WorkWatchdog,
    is_mechanical_blocked_reason,
    thresholds_for_work,
)

WORK = "02汉书"
LOG = Path(get_histograph_root()) / "data/05工作流中间产物/编排/logs/overnight-hanshu.log"
POLL_SEC = 90
MAX_ROUNDS = 2000  # 足够跑完全书


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def env() -> dict:
    root = str(get_histograph_root())
    return {
        **os.environ,
        "HISTOGRAPH_ROOT": root,
        "HIST_BATCH_AUTO": "1",
        "HIST_AUTO_COORD": os.environ.get("HIST_AUTO_COORD", "emperor-ssot"),
    }


def run_hist(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ORCH / "hist.py"), *args],
        capture_output=True,
        text=True,
        env=env(),
    )


def parse_status(text: str) -> dict:
    m_jobs = re.search(r"jobs: done (\d+)/(\d+)\s+pending (\d+)\s+failed (\d+)", text)
    m_done = re.search(r"done (\d+)/(\d+)", text)
    m_vol = re.search(r"当前: 卷(\d+) Step(\d+)", text)
    state = "other"
    if "状态: paused" in text:
        state = "paused"
    elif "状态: running" in text:
        state = "running"
    elif "状态: awaiting_decision" in text:
        state = "awaiting_decision"
    elif "状态: work_review" in text:
        state = "work_review"
    blocked = ""
    if "阻塞:" in text:
        blocked = text.split("阻塞:", 1)[1].strip()[:400]
    return {
        "state": state,
        "done": int((m_jobs or m_done).group(1)) if (m_jobs or m_done) else 0,
        "total": int((m_jobs or m_done).group(2)) if (m_jobs or m_done) else 0,
        "pending": int(m_jobs.group(3)) if m_jobs else 0,
        "failed": int(m_jobs.group(4)) if m_jobs else 0,
        "vol": m_vol.group(1) if m_vol else "",
        "step": m_vol.group(2) if m_vol else "",
        "blocked": blocked,
        "raw": text,
    }


def main() -> int:
    log(f"启动汉书无人值守 | LOG={LOG}")
    watcher = WorkWatchdog(thresholds_for_work(WORK))

    for rnd in range(1, MAX_ROUNDS + 1):
        st_proc = run_hist("status", "--work", WORK)
        st = parse_status(st_proc.stdout + st_proc.stderr)
        probe = watcher.observe(
            WorkSnapshot(
                done=st["done"],
                failed=st.get("failed", 0),
                state=st["state"],
                vol=st.get("vol", ""),
                step=st.get("step", ""),
                blocked=st.get("blocked", ""),
            )
        )
        log(
            f"轮次 {rnd} | done {st['done']}/{st['total']} | "
            f"状态 {st['state']} | 卷{st['vol']} Step{st['step']}"
        )
        if probe.should_probe:
            log(
                f"🩺 自动巡检：连续 {probe.idle_rounds} 轮无新进展 | "
                f"状态 {st['state']} | 卷{st['vol']} Step{st['step']}"
            )

        if st["done"] == st["total"] and st["total"] > 0:
            log("✅ 全部 jobs done，尝试封板前检查 work_review")
            run_hist("run-work", "--work", WORK)
            st2 = parse_status(run_hist("status", "--work", WORK).stdout)
            if st2["state"] == "work_review":
                log("📋 进入 work_review，停止无人值守（需人工封板或设 HIST_AUTO_WORK=1）")
            else:
                log("✅ 汉书标注批次完成")
            return 0

        if st["state"] in ("paused", "awaiting_decision"):
            vol = st.get("vol") or ""
            blocked = st.get("blocked") or ""
            if probe.should_escalate_block:
                log(
                    f"🛑 同一阻塞连续 {probe.same_blocked_rounds} 轮未收敛，"
                    f"停止盲目 auto-resume：{blocked[:160]}"
                )
                return 2
            if vol and is_mechanical_blocked_reason(blocked):
                try:
                    sys.path.insert(0, str(ORCH))
                    from lib.hanshu_autofix import repair_and_requeue_verify  # noqa: E402

                    ok, msg = repair_and_requeue_verify(WORK, vol)
                    if ok:
                        log(f"🔧 自动头段修复 卷{vol}: {msg}")
                except Exception as e:
                    log(f"⚠️ 自动修复失败: {e}")
            log(f"自动 resume（阻塞: {blocked[:120]}）")
            run_hist("resume", "--work", WORK)

        log("▶ run-work --one-volume（逐卷封板 Step1–4）")
        proc = run_hist("run-work", "--work", WORK, "--one-volume")
        tail = (proc.stdout or "") + (proc.stderr or "")
        for line in tail.strip().splitlines()[-12:]:
            if line.strip():
                log(f"  | {line.strip()}")

        if proc.returncode != 0:
            log(f"run-batch exit {proc.returncode}，{POLL_SEC}s 后重试")
        time.sleep(POLL_SEC)

    log("达到 MAX_ROUNDS，退出")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
