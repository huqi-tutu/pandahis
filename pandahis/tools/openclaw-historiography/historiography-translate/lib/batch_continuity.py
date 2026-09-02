"""分批成稿：P 边界切批 + 批间衔接上下文（程序生成，无 LLM）。"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from lib.m_anchor import extract_para_id, m_id_to_num


def default_batch_target() -> int:
    return max(1, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def prose_tail_budget() -> int:
    return max(200, int(os.environ.get("TRANSLATE_BATCH_TAIL_CHARS", "600")))


def mother_tail_count() -> int:
    return max(1, int(os.environ.get("TRANSLATE_BATCH_MOTHER_TAIL", "5")))


def split_checklist_at_p_boundaries(
    checklist: List[Dict[str, Any]],
    target_size: int | None = None,
) -> List[List[Dict[str, Any]]]:
    """
    按目标句数切批，优先在母本段落 P 边界处切断。
    单段 P 内句数超过 target 时仍可在段内硬切。
    """
    if not isinstance(checklist, list) or not checklist:
        return [[]]
    target = max(1, target_size or default_batch_target())
    if len(checklist) <= target:
        return [checklist]

    min_size = max(4, target // 2)
    max_size = target + 6
    min_tail = max(4, target // 3)
    boundary_slack = max(3, target // 4)

    batches: List[List[Dict[str, Any]]] = []
    start = 0
    n = len(checklist)

    while start < n:
        rest = n - start
        if rest <= target:
            batches.append(checklist[start:])
            break

        ideal = start + target
        lo = start + min_size
        hi = min(n, start + max_size)

        best = min(ideal, n)
        best_dist = 10_000
        found_boundary = False

        # 目标切点跨 P：在本段末句结束，不把下段首句纳入本批
        if ideal < n:
            p_before = extract_para_id(str(checklist[ideal - 1].get("段落") or ""))
            p_after = extract_para_id(str(checklist[ideal].get("段落") or ""))
            if (
                p_before is not None
                and p_after is not None
                and p_before != p_after
                and (ideal - start) >= min_size
            ):
                best = ideal - 1
                best_dist = 0
                found_boundary = True

        for cut in range(lo, hi + 1):
            if cut <= start or cut >= n:
                continue
            p0 = extract_para_id(str(checklist[cut - 1].get("段落") or ""))
            p1 = extract_para_id(str(checklist[cut].get("段落") or ""))
            if p0 is None or p1 is None or p0 == p1:
                continue
            dist = abs(cut - ideal)
            if dist < best_dist or (dist == best_dist and cut < best):
                best_dist = dist
                best = cut
                found_boundary = True

        if not found_boundary:
            best = min(ideal, n)
        elif best_dist > boundary_slack:
            best = min(ideal, n)

        batches.append(checklist[start:best])
        start = best

    if len(batches) >= 2 and len(batches[-1]) < min_tail:
        batches[-2] = batches[-2] + batches[-1]
        batches.pop()

    return batches


def prose_batch_tail(
    prev_body: str,
    *,
    max_chars: int | None = None,
    max_paras: int = 3,
) -> str:
    """上批成稿末段（字数上限内尽量多段）。"""
    text = (prev_body or "").strip()
    if not text:
        return ""
    budget = max_chars if max_chars is not None else prose_tail_budget()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        return text[:budget]

    selected: List[str] = []
    total = 0
    for para in reversed(paras[-max_paras:]):
        extra = len(para) + (2 if selected else 0)
        if selected and total + extra > budget:
            break
        selected.insert(0, para)
        total += extra
    if not selected:
        return paras[-1][:budget]
    return "\n\n".join(selected)


def mother_tail_before_batch(
    full_checklist: List[Dict[str, Any]],
    batch_items: List[Dict[str, Any]],
    *,
    count: int | None = None,
) -> List[Dict[str, str]]:
    """本批开始前，上若干条 M 的母本摘句（事实锚点）。"""
    if not batch_items:
        return []
    first_n = m_id_to_num(str(batch_items[0].get("编号") or ""))
    if first_n is None or first_n <= 1:
        return []

    n_take = count if count is not None else mother_tail_count()
    prior: List[Dict[str, str]] = []
    for item in full_checklist:
        if not isinstance(item, dict):
            continue
        num = m_id_to_num(str(item.get("编号") or ""))
        if num is None or num >= first_n:
            continue
        prior.append(
            {
                "编号": str(item.get("编号") or ""),
                "段落": str(item.get("段落") or ""),
                "原文摘句": str(item.get("原文摘句") or ""),
            }
        )
    return prior[-n_take:]


def build_continuity_prompt_block(
    *,
    batch_index: int,
    batch_total: int,
    batch_items: List[Dict[str, Any]],
    full_checklist: List[Dict[str, Any]],
    prev_body: str = "",
) -> str:
    """组装注入 batch prompt 的批间衔接块。"""
    if not batch_items:
        return ""

    sid0 = str(batch_items[0].get("编号") or "?")
    sid1 = str(batch_items[-1].get("编号") or "?")
    lines: List[str] = [
        "--- 批次定位 ---",
        f"第 {batch_index}/{batch_total} 批；本批 {sid0}–{sid1}。",
    ]

    if batch_index == 1:
        lines.extend(
            [
                "本批为开篇顺译：从 M 清单首句起笔，勿写全书前置引入（引入由后续装配单独写）。",
                "批末语气须能自然接到下一批，勿写「下文」「接下来」。",
            ]
        )
    else:
        lines.extend(
            [
                "本批为长文中段：须紧接上文叙事，勿重写前情、勿再写引入、勿重复上批已述事件。",
                "人称、年号、语气与「上批末段」保持一致；本批第一句应像同一段叙述的延续。",
            ]
        )

    mother_tail = mother_tail_before_batch(full_checklist, batch_items)
    if mother_tail:
        lines.append("")
        lines.append("--- 母本前情（上批末尾原文摘句，仅供事实锚点，勿重复译一遍）---")
        lines.append(json.dumps(mother_tail, ensure_ascii=False, indent=2))

    prose_tail = prose_batch_tail(prev_body) if batch_index > 1 else ""
    if prose_tail:
        lines.append("")
        lines.append("--- 上批末段白话（仅供衔接，勿重复输出）---")
        lines.append(prose_tail)

    return "\n".join(lines) + "\n"
