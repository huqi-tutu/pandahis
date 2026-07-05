#!/usr/bin/env python3
"""知识性决策溯源：LLM 必填项 vs 脚本机械修复的分界。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SKIP_VOLUME_TYPES = frozenset({"表", "志书数据"})

# repair 脚本伪考订痕迹（非学界 SSOT 表）
SCRIPT_ONLY_YEAR_MARKERS = (
    "repair_hanshu",
    "repair脚本",
    "repair 脚本",
    "YEAR_META",
    "VOL_PLANS",
    "人工块界",
    "批量 repair",
    "批量返工",
    "脚本硬编码",
    "白名单门禁 + 人工",
)

# 脚本废止：不得再替代 LLM 写知识性字段
FORBIDDEN_REPAIR_KNOWLEDGE_FIELDS = frozenset(
    {
        "史略分类",
        "史略开始年",
        "史略结束年",
        "四级帝王坐标",
        "二级朝代坐标",
        "三级政权坐标",
        "一级文明坐标",
        "五级细坐标",
        "优先级",
        "优先级判定理由",
        "paragraphs",
        "segment_attribution",
        "entries",
    }
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_skip_volume(data: dict) -> bool:
    entries = data.get("entries") or []
    if entries:
        return False
    vt = (data.get("volume_type") or "").strip()
    return vt in SKIP_VOLUME_TYPES


def is_script_only_year_basis(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    return any(m.lower() in low for m in SCRIPT_ONLY_YEAR_MARKERS)


def stamp_provenance(
    skeleton_path: Path,
    step: str,
    *,
    source: str,
    session_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """编排器在 LLM 或合规 skip 后写入溯源标记。"""
    data = json.loads(skeleton_path.read_text(encoding="utf-8"))
    prov = data.setdefault("knowledge_provenance", {})
    rec: Dict[str, Any] = {"source": source, "at": utc_now_iso()}
    if session_id:
        rec["session_id"] = session_id
    if reason:
        rec["reason"] = reason
    prov[f"step{step}"] = rec
    skeleton_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def works_require_llm_knowledge(work: str) -> bool:
    try:
        import sys
        from pathlib import Path as _P

        orch = _P(__file__).resolve().parent.parent / "historiography-orchestrator"
        if str(orch) not in sys.path:
            sys.path.insert(0, str(orch))
        from lib.config import get_work_config  # noqa: WPS433

        return bool(get_work_config(work).get("require_llm_knowledge"))
    except Exception:
        return work.startswith("02汉书")


def validate_knowledge_provenance(
    data: dict,
    work: str,
    *,
    phase: str = "final",
) -> List[str]:
    """Step4 final：要求叙事卷 Step1/Step4 经 LLM（或合规 skip）。"""
    if phase != "final":
        return []
    if not works_require_llm_knowledge(work):
        return []

    errors: List[str] = []
    prov = data.get("knowledge_provenance") or {}
    entries = data.get("entries") or []

    if is_skip_volume(data):
        step1 = prov.get("step1") or {}
        src = step1.get("source")
        if src not in ("skip_non_narrative", "llm"):
            errors.append(
                "表/志 skip 卷须在 knowledge_provenance.step1 标记 "
                "skip_non_narrative（机械 skip）或 llm（经模型确认）"
            )
        return errors

    if not entries:
        return errors

    step1 = prov.get("step1") or {}
    if step1.get("source") != "llm":
        errors.append(
            "叙事卷 Step1 块界/分类/归属须由 LLM 完成"
            "（knowledge_provenance.step1.source 须为 llm）"
        )

    step4 = prov.get("step4") or {}
    if step4.get("source") != "llm":
        errors.append(
            "叙事卷 Step4 年份/坐标/优先级须由 LLM 考订"
            "（knowledge_provenance.step4.source 须为 llm）"
        )

    for i, entry in enumerate(entries):
        af = entry.get("_auto_filled") or {}
        basis = (af.get("_年LLM依据") or entry.get("_年LLM依据") or "").strip()
        if is_script_only_year_basis(basis):
            name = entry.get("史略名称", "?")
            errors.append(
                f"条目[{i + 1}] {name} 的 _年LLM依据 含 repair 伪考订，须 LLM 重填"
            )

    return errors


