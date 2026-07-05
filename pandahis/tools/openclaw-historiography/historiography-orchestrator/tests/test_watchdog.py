"""watchdog 回归：长期无进展与同一阻塞反复出现。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.watchdog import (  # noqa: E402
    WatchdogThresholds,
    WorkSnapshot,
    WorkWatchdog,
    blocked_signature,
    is_mechanical_blocked_reason,
)


def test_watchdog_escalates_same_blocked_signature():
    watcher = WorkWatchdog(WatchdogThresholds(idle_rounds=8, blocked_rounds=3))
    blocked = "段2 为篇内小标题，不得设 owners，须 exclude_reason=篇内小标题"
    obs1 = watcher.observe(
        WorkSnapshot(done=10, failed=1, state="paused", vol="092", step="2", blocked=blocked)
    )
    obs2 = watcher.observe(
        WorkSnapshot(done=10, failed=1, state="paused", vol="092", step="2", blocked=blocked)
    )
    obs3 = watcher.observe(
        WorkSnapshot(done=10, failed=1, state="paused", vol="092", step="2", blocked=blocked)
    )
    assert obs1.same_blocked_rounds == 1
    assert obs2.same_blocked_rounds == 2
    assert obs3.same_blocked_rounds == 3
    assert obs3.should_escalate_block


def test_watchdog_resets_idle_rounds_after_progress():
    watcher = WorkWatchdog(WatchdogThresholds(idle_rounds=2, blocked_rounds=3))
    watcher.observe(WorkSnapshot(done=10, failed=0, state="running", vol="092", step="2"))
    obs1 = watcher.observe(WorkSnapshot(done=10, failed=0, state="running", vol="092", step="2"))
    obs2 = watcher.observe(WorkSnapshot(done=10, failed=0, state="running", vol="092", step="2"))
    obs3 = watcher.observe(WorkSnapshot(done=11, failed=0, state="running", vol="093", step="1"))
    assert obs1.idle_rounds == 1
    assert obs2.should_probe
    assert obs3.idle_rounds == 0
    assert obs3.progress_changed


def test_watchdog_signature_and_mechanical_reason():
    blocked = "  段2 为篇内小标题，  不得设 owners  "
    assert is_mechanical_blocked_reason(blocked)
    sig = blocked_signature("paused", "92", "2", blocked)
    assert sig.startswith("paused|092|2|")
    assert "不得设 owners" in sig


if __name__ == "__main__":
    test_watchdog_escalates_same_blocked_signature()
    test_watchdog_resets_idle_rounds_after_progress()
    test_watchdog_signature_and_mechanical_reason()
    print("ok")
