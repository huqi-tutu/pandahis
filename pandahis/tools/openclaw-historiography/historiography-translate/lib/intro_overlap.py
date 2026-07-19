"""前置引入与母本开头去重检测。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from lib.mother_sentences import MAX_MUST_PHRASES, extract_must_phrases


def _intro_zone(detail: str) -> str:
    body = detail.split("*参考著作*")[0].split("参考著作")[0]
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    # 引入区：前两段 + 含过渡句的第三段
    zone: List[str] = []
    for p in paras[:3]:
        zone.append(p)
        if re.search(r"让我们|下面|来看一看|按下.*顺序|如何记载", p):
            break
    return "\n".join(zone)


def _forbidden_phrases(plan: Dict[str, Any]) -> List[str]:
    forbidden = list(plan.get("前置引入禁区") or [])
    preview = plan.get("母本首句预览") or {}
    for key in ("M001必现词", "M002必现词", "M003必现词"):
        for w in preview.get(key) or []:
            if len(str(w).strip()) >= 2:
                forbidden.append(str(w).strip())
    for item in (plan.get("母本逐句清单") or [])[:3]:
        if not isinstance(item, dict):
            continue
        orig = str(item.get("原文摘句") or "")
        for w in extract_must_phrases(orig)[:MAX_MUST_PHRASES]:
            if len(w) >= 2:
                forbidden.append(w)
    # 去重保序
    seen: set[str] = set()
    out: List[str] = []
    for w in forbidden:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def intro_mother_overlap(
    detail: str,
    plan: Dict[str, Any],
    *,
    threshold: int = 2,
) -> List[str]:
    """引入区与母本前三句必现词重叠过多 → 报错。"""
    intro = _intro_zone(detail)
    if not intro:
        return []

    hits: List[str] = []
    for phrase in _forbidden_phrases(plan):
        if len(phrase) < 2:
            continue
        if phrase in intro or f"「{phrase}」" in intro:
            hits.append(phrase)

    if len(hits) >= threshold:
        return [
            f"前置引入与母本开头重复（{len(hits)}处）: "
            + "、".join(hits[:6])
            + "；引入应写阅读框架，不重复身世/品貌/早年。"
        ]
    return []
