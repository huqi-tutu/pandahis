"""前置引入分档：按母本厚度写入 plan 说明（无程序质检）。"""

from __future__ import annotations

from typing import Any, Dict

from lib.mother_sentences import extract_mother_sentences

# 写入 plan / 提示词的建议篇幅（非硬拦）
INTRO_PROMPT_MAX_CHARS = 250
INTRO_PROMPT_MIN_CHARS = 60

_THIN_CHAR_LIMIT = 150
_MEDIUM_CHAR_LIMIT = 500
_THIN_M_COUNT = 3

_TIER_META: Dict[str, Dict[str, Any]] = {
    "一句过渡": {},
    "短引入": {},
    "框架引入": {},
}


def mother_source_char_count(recalled: Dict[str, Any]) -> int:
    total = 0
    for block in recalled.get("blocks") or []:
        if block.get("role") != "母本":
            continue
        paras = block.get("paragraphs") or []
        if paras:
            for para in paras:
                total += len(str(para.get("text") or ""))
        else:
            total += len(str(block.get("text") or ""))
    return total


def resolve_intro_tier(
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None = None,
) -> str:
    """返回：短引入 | 框架引入（历史 plan 或存档位名「一句过渡」视同短引入）。"""
    if plan and plan.get("前置引入档位") in _TIER_META:
        tier = str(plan["前置引入档位"])
        return "短引入" if tier == "一句过渡" else tier

    chars = mother_source_char_count(recalled)
    m_count = len(extract_mother_sentences(recalled))
    if chars < _THIN_CHAR_LIMIT or m_count <= _THIN_M_COUNT:
        return "短引入"
    if chars < _MEDIUM_CHAR_LIMIT:
        return "短引入"
    return "框架引入"


def intro_tier_meta(tier: str) -> Dict[str, Any]:
    return dict(_TIER_META.get(tier, _TIER_META["框架引入"]))


def inject_intro_tier(plan: Dict[str, Any], recalled: Dict[str, Any]) -> None:
    tier = resolve_intro_tier(recalled, plan)
    chars = mother_source_char_count(recalled)
    m_count = len(extract_mother_sentences(recalled))
    plan["前置引入档位"] = tier
    plan["前置引入档位说明"] = {
        "母本字数": chars,
        "母本句数": m_count,
        "作用": "笼统定位后自然进入母本叙事；不展开具体事迹",
        "字数建议": f"{INTRO_PROMPT_MIN_CHARS}–{INTRO_PROMPT_MAX_CHARS}",
        "质检": "无程序硬拦；不展开细节靠写作自律",
    }
