"""Step 打回时失效中间产物，避免在错误 protagonists/blocks 上重复 LLM。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Set

from lib import gates
from lib.blocks_workflow import blocks_path
from lib.protagonist_workflow import protagonists_path


ArtifactKind = str

ALL_STEP1_ARTIFACTS: Set[ArtifactKind] = frozenset(
    {"protagonists", "blocks", "skeleton"}
)


def invalidate(
    work: str,
    vol: str,
    kinds: Iterable[ArtifactKind],
    *,
    reason: str = "",
) -> List[str]:
    """删除指定中间文件；返回日志行。"""
    vol = vol.zfill(3)
    logs: List[str] = []
    tag = f" ({reason})" if reason else ""

    for kind in kinds:
        if kind == "protagonists":
            p = protagonists_path(work, vol)
            if p.exists():
                p.unlink()
                logs.append(f"已删除 protagonists.json{tag}")
        elif kind == "blocks":
            p = blocks_path(work, vol)
            if p.exists():
                p.unlink()
                logs.append(f"已删除 blocks.json{tag}")
        elif kind == "skeleton":
            sk = gates.skeleton_path(work, vol)
            if sk is not None and sk.exists():
                sk.unlink()
                logs.append(f"已删除 skeleton{tag}")
    return logs


def invalidate_for_step2_rollback(
    work: str,
    vol: str,
    err_str: str,
    *,
    redo_step1a: bool = False,
) -> List[str]:
    """Step2 打回 Step1：默认清 blocks+skeleton；主轴类错误再清 protagonists。"""
    kinds: List[ArtifactKind] = ["blocks", "skeleton"]
    if redo_step1a:
        kinds.insert(0, "protagonists")
    else:
        from lib.failure_classifier import classify_failure  # noqa: WPS433

        plan = classify_failure("2", err_str, work=work, vol=vol)
        if plan.redo_step1a:
            kinds.insert(0, "protagonists")
    return invalidate(work, vol, kinds, reason="Step2 打回 Step1")


def invalidate_for_failure_plan(work: str, vol: str, plan) -> List[str]:
    if not plan.invalidate:
        return []
    return invalidate(work, vol, plan.invalidate, reason=plan.root_cause)
