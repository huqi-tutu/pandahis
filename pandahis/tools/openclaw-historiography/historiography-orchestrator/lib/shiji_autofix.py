"""《史记》Step1 blocks / Step4 坐标脚本修复（编排器侧入口）。"""

from __future__ import annotations

import sys
from typing import Tuple

from lib.config import ANNOTATE_DIR
from lib import blocks_workflow, gates


def repair_step1_blocks(work: str, vol: str) -> Tuple[bool, str]:
    """pause/重试前修复 blocks exclude 误标与段落未覆盖。"""
    if not str(work).startswith("01史记"):
        return False, ""
    vol = vol.zfill(3)
    sys.path.insert(0, str(ANNOTATE_DIR))
    from shiji_pipeline_autofix import try_autofix_step1_blocks  # noqa: E402

    try:
        index = gates.load_paragraph_index(work, vol)
    except FileNotFoundError:
        return False, "缺少段落索引"
    blocks_path = blocks_workflow.blocks_path(work, vol)
    ok, logs = try_autofix_step1_blocks(work, vol, index, blocks_path)
    if not ok:
        return False, logs[0] if logs else "blocks 无需修复或仍失败"
    return True, "；".join(logs[:6])


def repair_step4_shiji(work: str, vol: str) -> Tuple[bool, str]:
    """Step4 脚本加固 + finalize + check_format final（熔断/失败恢复用）。"""
    if not str(work).startswith("01史记"):
        return False, ""
    vol = vol.zfill(3)
    sk = gates.skeleton_path(work, vol)
    if not sk:
        return False, "无 skeleton"
    ok, logs = gates.step4_recover_before_fail(sk, work, vol)
    if not ok:
        return False, logs[-1] if logs else "Step4 修复失败"
    return True, "；".join(logs[:10])
