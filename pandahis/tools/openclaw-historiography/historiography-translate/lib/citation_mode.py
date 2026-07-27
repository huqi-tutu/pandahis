"""母本摘句引用粒度：叙事句 / 并列句群 / 世系 / 品评。"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def detect_citation_mode(orig: str) -> str:
    """返回 narrative | parallel_cluster | genealogy | appraisal。"""
    s = orig.strip()
    if not s:
        return "narrative"

    # 世系：X父曰Y，Y父曰Z
    if len(re.findall(r"父曰|母曰|生曰|孙曰", s)) >= 2:
        return "genealogy"

    # 并列排比：多个「，」分隔的 2-6 字短语，无完整主谓
    clauses = [c.strip() for c in re.split(r"[，,]", s) if c.strip()]
    short_clauses = [c for c in clauses if 2 <= len(c) <= 8]
    if len(short_clauses) >= 3 and len(short_clauses) >= len(clauses) * 0.6:
        return "parallel_cluster"

    # 品评 dense：静渊以有谋；聪以知远
    if re.search(r"[\u4e00-\u9fff]{1,4}以[\u4e00-\u9fff]{1,6}", s) and len(clauses) >= 2:
        return "appraisal"

    return "narrative"


def citation_mode_hint(mode: str) -> str:
    hints = {
        "narrative": "叙事句：专名与数字融入白话叙述；「」用于完整摘句、对话或并列句群。",
        "parallel_cluster": (
            "并列句群：先整段或整簇引用原文，再作一段白话解释。"
        ),
        "genealogy": "世系句：整句引用后串讲谱系。",
        "appraisal": "品评句：对称句群整段引用后作一段品评。",
    }
    return hints.get(mode, hints["narrative"])


def enrich_checklist_citation_modes(checklist: List[Dict[str, Any]]) -> None:
    for item in checklist:
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or "").strip()
        if not orig:
            continue
        mode = detect_citation_mode(orig)
        item["引用粒度"] = mode
        item.setdefault("母本提示", "")
        hint = citation_mode_hint(mode)
        prev = str(item.get("母本提示") or "").strip()
        if hint not in prev:
            item["母本提示"] = f"{prev}；{hint}" if prev else hint


def count_short_quote_density(text: str, *, threshold_len: int = 4) -> int:
    """统计过短「」引用次数（≤threshold_len 字）。"""
    return sum(
        1
        for m in re.finditer(r"「([^」]+)」", text)
        if len(m.group(1).strip()) <= threshold_len
    )
