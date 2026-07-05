#!/usr/bin/env python3
"""Step4 脚本加固：在 LLM / finalize / check_format 前后自动补全可确定性字段。

目标：编排器不必等用户追问再手工修；凡 PATCH/学界表/兜底能解决的，一律先跑脚本。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

_ANNOTATE = Path(__file__).resolve().parent


def _run_fill(skeleton: Path, *args: str) -> Tuple[bool, str]:
    cmd = [sys.executable, str(_ANNOTATE / "fill_fields.py"), str(skeleton), *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode == 0, out[-2000:]


def harden_shiji_step4_skeleton(
    skeleton: Path,
    vol: str,
    *,
    work_id: str = "01史记",
    provenance: bool = True,
    merge_auto: bool = True,
) -> Tuple[int, List[str]]:
    """
    对单卷 skeleton 执行确定性 Step4 加固。
    返回 (改动条数估计, 日志行)。
    """
    if not str(work_id).startswith("01史记"):
        return 0, []
    if not skeleton.exists():
        return 0, ["skeleton 不存在"]

    logs: List[str] = []
    changes = 0

    if merge_auto:
        ok, msg = _run_fill(skeleton, "--merge-auto")
        if ok:
            logs.append("merge-auto OK")
        else:
            logs.append(f"merge-auto 失败: {msg[-120:]}")

    data = json.loads(skeleton.read_text(encoding="utf-8"))
    before_sig = _entry_signature(data)

    from shiji_person_fallback import (  # noqa: WPS433
        apply_volume_step4_fallback,
        ensure_spindle_rationale,
        prepare_year_quality_repatch,
    )

    yr = prepare_year_quality_repatch(data)
    if yr:
        logs.append(f"年份质检重刷 {yr} 条")
        changes += yr

    ok_count, fb_logs = apply_volume_step4_fallback(data, vol, work_id=work_id)
    logs.extend(fb_logs)
    changes += ok_count

    for entry in data.get("entries") or []:
        if ensure_spindle_rationale(entry, data):
            name = (entry.get("史略名称") or "").strip()
            if not any(name in ln for ln in logs):
                logs.append(f"OK {name} 主轴说明")
                changes += 1

    skeleton.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if provenance:
        from backfill_provenance_fields import backfill_file  # noqa: WPS433

        y, a = backfill_file(skeleton, dry_run=False)
        if y or a:
            logs.append(f"考订字段 +年{y} +主轴{a}")
            changes += y + a

    ok, _ = _run_fill(skeleton, "--sync-coord-ids")
    if ok:
        logs.append("sync-coord-ids OK")

    after = json.loads(skeleton.read_text(encoding="utf-8"))
    after_sig = _entry_signature(after)
    if after_sig != before_sig and changes == 0:
        changes = 1

    return changes, logs


def _entry_signature(data: dict) -> str:
    parts = []
    for e in data.get("entries") or []:
        af = e.get("_auto_filled") or {}
        parts.append(
            "|".join(
                [
                    str(e.get("史略ID")),
                    str(e.get("史略开始年")),
                    str(e.get("史略结束年")),
                    str(e.get("四级帝王坐标")),
                    str(af.get("_年LLM依据", ""))[:20],
                    str(af.get("_坐标主轴说明", ""))[:20],
                ]
            )
        )
    return "\n".join(parts)


def try_recover_step4_final(
    skeleton: Path,
    vol: str,
    *,
    work_id: str = "01史记",
    finalize_fn=None,
    verify_final_fn=None,
) -> Tuple[bool, List[str]]:
    """check_format final 失败时：脚本加固 → finalize → 再验。"""
    logs: List[str] = []
    n, harden_logs = harden_shiji_step4_skeleton(skeleton, vol, work_id=work_id)
    logs.extend(harden_logs)
    if n == 0 and not harden_logs:
        logs.append("无脚本可修项")
        return False, logs

    if finalize_fn:
        ok, msg = finalize_fn(skeleton)
        if not ok:
            logs.append(f"finalize 失败: {msg[-200:]}")
            return False, logs
        logs.append("finalize OK")

    if verify_final_fn:
        ok, msg = verify_final_fn(skeleton)
        if not ok:
            logs.append(f"check_format 仍失败: {msg[-400:]}")
            return False, logs
        logs.append("check_format final OK")

    return True, logs
