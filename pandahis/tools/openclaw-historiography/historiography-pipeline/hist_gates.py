"""史料标注硬门：卷序互斥、编排租约、金标门禁（pipeline / annotate / orchestrator 共用）。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PIPELINE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = PIPELINE_DIR.parent
ORCH_CATALOG = SKILLS_DIR / "historiography-orchestrator" / "catalog" / "works.json"

sys.path.insert(0, str(SKILLS_DIR))
from paths_config import histograph_paths  # noqa: E402


class GateError(Exception):
    """硬门拒绝（exit 2）。"""


# 标注流水线有效步（Step4 完成后即视为本卷标注完成）
PIPELINE_STEPS = ("1", "2", "3", "4")
RETIRED_PIPELINE_STEPS = ("5",)  # 原参考文献环节，已取消


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repair_mode() -> bool:
    return os.environ.get("HIST_REPAIR") == "1"


def orch_state_dir() -> Path:
    d = histograph_paths()["state_root"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def active_job_path() -> Path:
    return orch_state_dir() / "active_job.json"


def read_active_job() -> Optional[Dict[str, Any]]:
    fp = active_job_path()
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_active_job(
    work: str,
    vol: str,
    step: str,
    *,
    job_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> Path:
    data = {
        "work": work,
        "vol": vol.zfill(3),
        "step": str(step),
        "job_id": job_id,
        "session_id": session_id,
        "updated_at": utc_now(),
    }
    fp = active_job_path()
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


def clear_active_job() -> None:
    fp = active_job_path()
    if fp.exists():
        fp.unlink()


def parse_skeleton_path(path: Path | str) -> Tuple[str, str]:
    """从 skeleton 路径解析 (work, vol)。"""
    p = Path(path)
    stem = p.stem.replace("_skeleton", "")
    m = re.match(r"^(.+?)_(\d{3})_.+$", stem)
    if not m:
        raise GateError(f"无法从路径解析著作/卷号: {p.name}")
    return m.group(1), m.group(2)


def load_work_catalog(work: str) -> dict:
    if not ORCH_CATALOG.exists():
        return {}
    data = json.loads(ORCH_CATALOG.read_text(encoding="utf-8"))
    return data.get("works", {}).get(work, {})


def gold_volumes(work: str) -> list[str]:
    cfg = load_work_catalog(work)
    return [str(v).zfill(3) for v in cfg.get("gold_volumes", [])]


def is_gold_approved(work: str) -> bool:
    db_path = orch_state_dir() / "state.sqlite"
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT gold_approved FROM works WHERE id=?", (work,)
        ).fetchone()
        conn.close()
        return bool(row and row[0])
    except sqlite3.Error:
        return False


def prev_vol(vol: str) -> Optional[str]:
    n = int(vol)
    if n <= 1:
        return None
    return str(n - 1).zfill(3)


def volume_overall_done(progress: dict, vol: str) -> bool:
    vol = vol.zfill(3)
    v = progress.get("volumes", {}).get(vol)
    if not v:
        return False
    return v.get("overall") == "done"


def check_gold_gate(work: str, vol: str) -> Tuple[bool, str]:
    vol = vol.zfill(3)
    gold = gold_volumes(work)
    if not gold:
        return True, "无金标卷配置"
    if vol in gold:
        return True, "金标卷"
    if is_gold_approved(work):
        return True, "金标已通过"
    return (
        False,
        f"卷 {vol} 在金标确认前不可操作（金标卷: {', '.join(gold)}）。"
        f"请先 hist approve-gold --work {work}，或单卷修复时设 HIST_REPAIR=1",
    )


def check_volume_order(work: str, vol: str, progress: dict) -> Tuple[bool, str]:
    """上一卷 overall=done 才允许操作本卷。"""
    vol = vol.zfill(3)
    pv = prev_vol(vol)
    if pv is None:
        return True, "首卷"
    if volume_overall_done(progress, pv):
        return True, f"上一卷 {pv} 已完成"
    pv_rec = progress.get("volumes", {}).get(pv)
    prev_state = pv_rec.get("overall", "未登记") if pv_rec else "未登记"
    return (
        False,
        f"卷序硬门：卷 {pv} 须 overall=done 才能操作卷 {vol}（当前 {pv}={prev_state}）。"
        f"禁止批量 verify/mark。逐卷: hist run-work --max-jobs 1",
    )


def check_active_job(work: str, vol: str, step: Optional[str] = None) -> Tuple[bool, str]:
    """pipeline 命令须经 hist.py 持有租约。"""
    vol = vol.zfill(3)
    job = read_active_job()
    if not job:
        return (
            False,
            "编排租约：无 active_job。禁止直接调用 pipeline。"
            "请用: hist.py run-work --work … --max-jobs 1"
            "（单卷修复: HIST_REPAIR=1）",
        )
    if job.get("work") != work or job.get("vol") != vol:
        return (
            False,
            f"编排租约：当前仅允许 {job.get('work')} 卷{job.get('vol')} Step{job.get('step')}，"
            f"拒绝 {work} 卷{vol}",
        )
    if step is not None and str(job.get("step")) != str(step):
        return (
            False,
            f"编排租约：当前 Step{job.get('step')}，拒绝 Step{step}",
        )
    return True, "租约匹配"


def check_script_lease(skeleton_path: Path | str, step: Optional[str] = None) -> Tuple[bool, str]:
    work, vol = parse_skeleton_path(skeleton_path)
    return check_active_job(work, vol, step)


def enforce_pipeline(work: str, vol: str, progress: dict, *, force_order: bool = False) -> None:
    if repair_mode():
        return
    ok, msg = check_gold_gate(work, vol)
    if not ok:
        raise GateError(msg)
    if not force_order:
        ok, msg = check_volume_order(work, vol, progress)
        if not ok:
            raise GateError(msg)
    ok, msg = check_active_job(work, vol)
    if not ok:
        raise GateError(msg)


def enforce_script(skeleton_path: Path | str, step: Optional[str] = None) -> None:
    if repair_mode():
        return
    ok, msg = check_script_lease(skeleton_path, step)
    if not ok:
        raise GateError(msg)


def can_register_volume(work: str, vol: str, progress: dict) -> Tuple[bool, str]:
    """init --scan 仅允许登记「下一卷」。"""
    vol = vol.zfill(3)
    if vol in progress.get("volumes", {}):
        return True, "已登记"
    ok, msg = check_gold_gate(work, vol)
    if not ok:
        return False, msg
    volumes = progress.get("volumes", {})
    if not volumes:
        if vol == "001" or vol == min(gold_volumes(work) or ["001"]):
            return True, "首卷登记"
        return False, f"进度为空时只能登记首卷，不能登记 {vol}"
    for candidate in sorted(volumes.keys()):
        if volumes[candidate].get("overall") != "done":
            if vol == candidate:
                return True, "当前待办卷"
            return False, f"只能登记当前待办卷 {candidate}，不能登记 {vol}"
    # 全部 done：允许登记下一卷号
    last = max(volumes.keys())
    next_v = str(int(last) + 1).zfill(3)
    if vol == next_v:
        return True, f"上一卷 {last} 已完成，可登记 {vol}"
    return False, f"只能按序登记卷 {next_v}，不能登记 {vol}"


def gate_fail(msg: str) -> None:
    print(f"🚫 硬门拒绝: {msg}", file=sys.stderr)
    sys.exit(2)
