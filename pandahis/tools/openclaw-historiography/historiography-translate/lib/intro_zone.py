"""前置引入区边界（计分、去重共用同一套规则）。"""

from __future__ import annotations

import re

# 过渡标记：命中则当前段视为引入末段。勿用「原文如下」——详情均为白话译文。
INTRO_BREAK = re.compile(
    r"让我们|下面|来看一看|按下.*顺序|如何记载|写起[。.]|《[^》]+》[^。]{0,40}(?:载|写道|记)[：:]?"
)

_MAX_INTRO_PARAS = 3


def _body_paragraphs(detail: str) -> list[str]:
    body = detail.split("*参考著作*")[0].split("参考著作")[0]
    return [p.strip() for p in body.split("\n\n") if p.strip()]


# 无过渡标记时：仅当首段极短且后接正文，才视为单独引入（母本顺译首段往往较长，不剔除）
_SHORT_STANDALONE_INTRO_MAX = 100


def intro_paragraph_count(detail: str, *, max_paras: int = _MAX_INTRO_PARAS) -> int:
    """引入区占前几段；无过渡标记时不剔除（母本顺译等直入叙事）。"""
    paras = _body_paragraphs(detail)
    if not paras:
        return 0
    for i, p in enumerate(paras[:max_paras]):
        if INTRO_BREAK.search(p):
            return i + 1
    if len(paras) >= 2 and len(paras[0]) <= _SHORT_STANDALONE_INTRO_MAX:
        return 1
    return 0


def intro_zone_text(detail: str) -> str:
    """引入区正文（用于字数、去重检测）。"""
    n = intro_paragraph_count(detail)
    if n <= 0:
        return ""
    return "\n\n".join(_body_paragraphs(detail)[:n])


def body_without_intro_zone(detail: str) -> str:
    """剔除前置引入区后的正文（母本覆盖计分域）。"""
    paras = _body_paragraphs(detail)
    if not paras:
        return detail.strip()
    n = intro_paragraph_count(detail)
    if n <= 0 or n >= len(paras):
        return "\n\n".join(paras).strip() if n <= 0 else ""
    return "\n\n".join(paras[n:]).strip()
