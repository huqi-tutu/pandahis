"""按 M 批次筛选 plan，供分批成稿注入本批 M 清单。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from lib.citation_mode import citation_mode_hint, detect_citation_mode


def plan_slice_for_batch(
    plan_data: Dict[str, Any],
    batch_items: List[Dict[str, Any]],
    *,
    batch_index: int = 1,
    batch_total: int = 1,
) -> Dict[str, Any]:
    """本批 M 清单（全字段，供 verify / 落盘对照）。"""
    del batch_index, batch_total  # 保留签名兼容
    sid0 = batch_items[0].get("编号") if batch_items else "?"
    sid1 = batch_items[-1].get("编号") if batch_items else "?"

    return {
        "史略ID": plan_data.get("史略ID"),
        "史略名称": plan_data.get("史略名称"),
        "母本著作": plan_data.get("母本著作"),
        "本批范围": f"{sid0}–{sid1}",
        "母本逐句清单": batch_items,
    }


def slim_checklist_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """成稿 prompt 用：仅编号 + 原文摘句。"""
    return {
        "编号": str(item.get("编号") or "").strip(),
        "原文摘句": str(item.get("原文摘句") or item.get("text") or "").strip(),
    }


def citation_modes_in_batch(batch_items: List[Dict[str, Any]]) -> Dict[str, str]:
    """本批出现的引用粒度 → 一句写法说明（去重，不逐条重复）。"""
    modes: Dict[str, str] = {}
    for item in batch_items:
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or item.get("text") or "").strip()
        if not orig:
            continue
        mode = str(item.get("引用粒度") or detect_citation_mode(orig)).strip() or "narrative"
        if mode not in modes:
            modes[mode] = citation_mode_hint(mode)
    return modes


def plan_slice_for_batch_prompt(
    plan_data: Dict[str, Any],
    batch_items: List[Dict[str, Any]],
    *,
    batch_index: int = 1,
    batch_total: int = 1,
) -> Dict[str, Any]:
    """本批 M 清单（瘦身版，仅注入成稿 prompt；verify 仍用 plan_slice_for_batch）。"""
    del batch_index, batch_total
    sid0 = batch_items[0].get("编号") if batch_items else "?"
    sid1 = batch_items[-1].get("编号") if batch_items else "?"
    slim_items = [slim_checklist_item(x) for x in batch_items if isinstance(x, dict)]
    out: Dict[str, Any] = {
        "史略ID": plan_data.get("史略ID"),
        "史略名称": plan_data.get("史略名称"),
        "母本著作": plan_data.get("母本著作"),
        "本批范围": f"{sid0}–{sid1}",
        "母本逐句清单": slim_items,
    }
    mode_hints = citation_modes_in_batch(batch_items)
    if mode_hints:
        out["引用粒度说明"] = mode_hints
    return out


def batch_plan_json_for_prompt(
    plan_data: Dict[str, Any],
    batch_items: List[Dict[str, Any]],
    *,
    batch_index: int = 1,
    batch_total: int = 1,
) -> str:
    """序列化为成稿 prompt 内的 JSON 块。"""
    payload = plan_slice_for_batch_prompt(
        plan_data,
        batch_items,
        batch_index=batch_index,
        batch_total=batch_total,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
