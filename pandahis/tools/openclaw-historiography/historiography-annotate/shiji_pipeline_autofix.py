#!/usr/bin/env python3
"""《史记》流水线统一自动修复：Step1 blocks + Step4 坐标/年份/考订。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from shiji_blocks_autofix import try_repair_blocks_file
from step4_hardening import harden_shiji_step4_skeleton, try_recover_step4_final


def try_autofix_step1_blocks(
    work: str,
    vol: str,
    index: dict,
    blocks_path: Path,
) -> Tuple[bool, List[str]]:
    if not str(work).startswith("01史记"):
        return False, []
    ok, logs = try_repair_blocks_file(blocks_path, index, work_id=work)
    return ok, logs


def try_autofix_step4_skeleton(
    skeleton_path: Path,
    vol: str,
    *,
    work_id: str = "01史记",
    finalize: bool = False,
    verify_fn=None,
    finalize_fn=None,
) -> Tuple[bool, List[str]]:
    """脚本加固；finalize=True 时走完整 recover（finalize + check_format final）。"""
    if not str(work_id).startswith("01史记"):
        return False, []
    if not skeleton_path.exists():
        return False, ["skeleton 不存在"]

    if finalize and finalize_fn and verify_fn:
        ok, logs = try_recover_step4_final(
            skeleton_path,
            vol,
            work_id=work_id,
            finalize_fn=finalize_fn,
            verify_final_fn=verify_fn,
        )
        return ok, logs

    n, logs = harden_shiji_step4_skeleton(skeleton_path, vol, work_id=work_id)
    if n == 0 and not any(ln.startswith("OK ") for ln in logs):
        return False, logs
    logs.append(f"Step4 加固改动约 {n} 项")
    return True, logs
