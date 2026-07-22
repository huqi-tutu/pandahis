"""前置引入分档：按母本厚度决定过渡/短引入/框架引入。"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from lib.mother_sentences import extract_mother_sentences

# 引入区字数：全档位统一硬上限（质检 enforce）
INTRO_MAX_CHARS = 400
INTRO_TARGET_MIN = 100  # 框架/短引入建议下限，不硬拦

# 方案 B：按母本厚度决定写法风格（字数上限见 INTRO_MAX_CHARS）
_THIN_CHAR_LIMIT = 150
_MEDIUM_CHAR_LIMIT = 500
_THIN_M_COUNT = 3

_TIER_META: Dict[str, Dict[str, Any]] = {
    "一句过渡": {"overlap_threshold": 0},
    "短引入": {"overlap_threshold": 3},
    "框架引入": {"overlap_threshold": 2},
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
    """返回：一句过渡 | 短引入 | 框架引入。"""
    if plan and plan.get("前置引入档位") in _TIER_META:
        return str(plan["前置引入档位"])

    chars = mother_source_char_count(recalled)
    m_count = len(extract_mother_sentences(recalled))
    if chars < _THIN_CHAR_LIMIT or m_count <= _THIN_M_COUNT:
        return "一句过渡"
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
        "字数建议": f"{INTRO_TARGET_MIN}–{INTRO_MAX_CHARS}",
        "字数硬上限": INTRO_MAX_CHARS,
    }


def intro_overlap_threshold(plan: Dict[str, Any]) -> int:
    tier = str(plan.get("前置引入档位") or "框架引入")
    return int(intro_tier_meta(tier).get("overlap_threshold", 2))


def verify_intro_length(detail: str, plan: Dict[str, Any]) -> Tuple[bool, str]:
    """引入区字数质检；失败信息供 Phase2 重试反馈。"""
    from lib.intro_zone import intro_zone_text as _intro_zone

    tier = str(plan.get("前置引入档位") or "框架引入")
    zone = _intro_zone(detail)
    if not zone:
        return False, f"前置引入档位为「{tier}」但缺少引入/过渡句"

    n = len(zone)
    if tier == "一句过渡":
        punct = zone.count("。") + zone.count("！") + zone.count("？")
        if punct > 1:
            return False, (
                "一句过渡档：引入区应仅为 1 句过渡进母本；"
                f"当前约{n}字、{punct}句，请压缩为一句（≤{INTRO_MAX_CHARS}字）。"
            )
    elif n < INTRO_TARGET_MIN and tier in ("短引入", "框架引入"):
        # 仅提示性：不 fail，避免与薄写法冲突
        pass

    if n > INTRO_MAX_CHARS:
        preview = zone[:72].replace("\n", "")
        return False, (
            f"引入过长：引入区{n}字，硬上限{INTRO_MAX_CHARS}字（建议概括精炼{INTRO_TARGET_MIN}–{INTRO_MAX_CHARS}字）。"
            f"请删去与正文重复的事件叙述，保留阅读框架与一句过渡。"
            f"引入区开头：「{preview}…」"
        )
    return True, ""
