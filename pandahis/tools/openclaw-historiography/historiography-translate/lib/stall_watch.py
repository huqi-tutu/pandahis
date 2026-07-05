"""翻译 LLM 阶段心跳：检测长时间无进展（默认 3 分钟）。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def stall_threshold_sec() -> int:
    return int(os.environ.get("TRANSLATE_STALL_SEC", "180"))


def heartbeat_path(work_dir: Path, entry_id: str) -> Path:
    return work_dir / f".heartbeat_{entry_id}.json"


def touch_heartbeat(
    work_dir: Path,
    entry_id: str,
    *,
    stage: str,
    detail: str = "",
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "entry_id": entry_id,
        "stage": stage,
        "detail": detail,
        "updated_at": time.time(),
        "updated_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    heartbeat_path(work_dir, entry_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_heartbeat(work_dir: Path, entry_id: str) -> Dict[str, Any] | None:
    path = heartbeat_path(work_dir, entry_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def is_stalled(work_dir: Path, entry_id: str, *, threshold_sec: int | None = None) -> Tuple[bool, str]:
    hb = read_heartbeat(work_dir, entry_id)
    if not hb:
        return False, ""
    limit = threshold_sec if threshold_sec is not None else stall_threshold_sec()
    age = time.time() - float(hb.get("updated_at") or 0)
    if age <= limit:
        return False, ""
    stage = str(hb.get("stage") or "?")
    detail = str(hb.get("detail") or "")
    return True, f"{entry_id} 在「{stage}」已 {int(age)}s 无心跳（阈值 {limit}s）{(' — ' + detail) if detail else ''}"


def diagnose_stall(work_dir: Path, entry_id: str, entry_name: str = "") -> List[str]:
    """卡顿超过阈值时的快速诊断清单。"""
    from lib.work_artifacts import load_plan, mother_draft_path, plan_path, verify_plan
    from lib.verify import verify_mother_draft

    hints: List[str] = []
    hb = read_heartbeat(work_dir, entry_id)
    if hb:
        hints.append(f"最后心跳: {hb.get('updated_iso')} stage={hb.get('stage')}")

    pf = plan_path(entry_id, entry_name, work_dir)
    if pf.is_file():
        ok, _, errs = load_plan(pf)
        if ok:
            from lib.recall import recall_entry

            try:
                recalled = recall_entry(entry_id)
                p_ok, p_errs = verify_plan(entry_id, recalled, pf)
                if not p_ok:
                    hints.append("plan 硬伤: " + "; ".join(p_errs[:3]))
            except Exception as exc:
                hints.append(f"plan 无法校验: {exc}")
    else:
        hints.append("缺少 plan 文件")

    mf = mother_draft_path(entry_id, entry_name, work_dir)
    if mf.is_file():
        try:
            from lib.recall import recall_entry

            recalled = recall_entry(entry_id)
            _, plan_data, _ = load_plan(pf) if pf.is_file() else (False, {}, [])
            m_ok, m_errs = verify_mother_draft(
                entry_id, recalled, mf, plan=plan_data if plan_data else None
            )
            if not m_ok:
                hints.append("Phase1 硬伤: " + "; ".join(m_errs[:3]))
        except Exception as exc:
            hints.append(f"Phase1 无法校验: {exc}")

    hints.append("若 stage 含 llm_*：可能在等 DeepSeek 响应（正常可至 5–10 分钟）")
    hints.append("若 stage 含 verify_* 失败：查看上方硬伤并重试")
    return hints
