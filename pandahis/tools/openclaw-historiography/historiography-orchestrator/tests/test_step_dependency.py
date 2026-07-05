"""Step 依赖门禁：前序 failed 时不得调度 Step N+1。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import db  # noqa: E402


def _seed(work: str, vol: str, statuses: dict[str, str]) -> None:
    db.init_schema()
    db.upsert_work(work, "测试", status="running")
    db.ensure_jobs(work, [vol], ["1", "2", "3", "4"])
    for step, st in statuses.items():
        j = db.get_job(work, vol, step)
        assert j
        db.update_job(j["id"], status=st)


def test_next_pending_skips_step2_when_step1_failed():
    work, vol = "T_DEP", "001"
    _seed(work, vol, {"1": "failed", "2": "pending", "3": "pending", "4": "pending"})
    job = db.next_pending_job(work)
    assert job is None or job["step"] != "2"
    if job:
        assert job["vol"] != vol


def test_next_pending_picks_step2_when_step1_done():
    work, vol = "T_DEP2", "002"
    _seed(work, vol, {"1": "done", "2": "pending", "3": "pending", "4": "pending"})
    job = db.next_pending_job(work)
    assert job is not None
    assert job["vol"] == vol
    assert job["step"] == "2"


def test_block_reason_when_prior_failed():
    work, vol = "T_DEP3", "003"
    _seed(work, vol, {"1": "failed", "2": "pending"})
    reason = db.step_dependency_block_reason(work, vol, "2")
    assert reason is not None
    assert "Step1=failed" in reason


if __name__ == "__main__":
    test_next_pending_skips_step2_when_step1_failed()
    test_next_pending_picks_step2_when_step1_done()
    test_block_reason_when_prior_failed()
    print("ok")
