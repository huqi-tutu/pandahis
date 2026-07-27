"""兼容层：无锚点模糊出处已并入 legend_quota 配额检测（不再零容忍）。"""

from __future__ import annotations

from shared.legend_quota import UNANCHORED_ATTRIBUTION_TRIGGERS

# 兼容旧 import 名
VAGUE_CITATION_TRIGGERS = UNANCHORED_ATTRIBUTION_TRIGGERS

VAGUE_CITATION_COMPOUND_OK = (
    "口耳相传",
    "口传相传",
    "神话传说",
    "民间传说",
    "后世传说",
    "传说时代",
)


def detect_unanchored_vague_citations(text: str) -> list[str]:
    """已废弃零容忍；请使用 legend_quota.legend_quota_verify_issues。"""
    _ = text
    return []
