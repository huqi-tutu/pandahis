"""前置引入区边界（仅用于母本覆盖计分时剔除首段，不作质检硬拦）。"""

from __future__ import annotations

from typing import Any, Dict

_INTRO_TIER_REQUIRES = frozenset({"短引入", "框架引入", "一句过渡"})


def _body_paragraphs(detail: str) -> list[str]:
    body = detail.split("*参考著作*")[0].split("参考著作")[0]
    return [p.strip() for p in body.split("\n\n") if p.strip()]


def _tier_expects_intro(plan: Dict[str, Any] | None) -> bool:
    if not plan:
        return False
    tier = str(plan.get("前置引入档位") or "")
    return tier in _INTRO_TIER_REQUIRES


def intro_paragraph_count(
    detail: str,
    *,
    max_paras: int = 1,
    plan: Dict[str, Any] | None = None,
) -> int:
    """引入区 = 正文 ≥2 段时的首段（供覆盖计分剔除；不依赖过渡句式）。"""
    del max_paras  # 固定只认首段，避免多段误判
    paras = _body_paragraphs(detail)
    if not paras:
        return 0
    if _tier_expects_intro(plan) and len(paras) >= 2:
        return 1
    return 0


def intro_zone_text(detail: str, plan: Dict[str, Any] | None = None) -> str:
    """引入区正文（不计入母本覆盖）。"""
    n = intro_paragraph_count(detail, plan=plan)
    if n <= 0:
        return ""
    return "\n\n".join(_body_paragraphs(detail)[:n])


def body_without_intro_zone(detail: str, plan: Dict[str, Any] | None = None) -> str:
    """剔除前置引入区后的正文（母本覆盖计分域）。"""
    paras = _body_paragraphs(detail)
    if not paras:
        return detail.strip()
    n = intro_paragraph_count(detail, plan=plan)
    if n <= 0 or n >= len(paras):
        return "\n\n".join(paras).strip() if n <= 0 else ""
    return "\n\n".join(paras[n:]).strip()
