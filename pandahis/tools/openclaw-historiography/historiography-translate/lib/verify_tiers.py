"""verify 结果分级：BLOCK 阻断 / TICKET 工单 / LOG 仅记录。"""

from __future__ import annotations

import os
from typing import List, Tuple

# 命中则降为 TICKET（不阻断 run-one / verify 通过）
_TICKET_PATTERNS: tuple[str, ...] = (
    "段落过碎",
    "篇末空泛升华",
    "描述性称呼过多",
    "引用宜以完整摘句",
    "引用过碎",
    "母本引用过碎",
    "未授权引用",
    "参考著作节书目",
    "AI 腔词",
    "ai_flavor",
    "传说/二手表述",
    "二手表述触发词",
    "legend_dominance",
    "疑似重复段落",
    "plan 外部补全",
    "采用:true 未在正文",
    "多源条目但正文",
    "参考著作与正文之间",
    "参考著作：前须空一行",
    "段末破折号",
    "字数偏少",
    "字数不足",
    "低于下限",
)

# 覆盖类：仅在 report 模式下降为 TICKET
_COVERAGE_TICKET_PATTERNS: tuple[str, ...] = (
    "覆盖不足",
    "覆盖率",
    "语义覆盖",
    "未传达",
    "传达率",
    "母本顺译 覆盖",
    "母本顺译 语义",
)


def verify_tiers_enabled() -> bool:
    return os.environ.get("TRANSLATE_VERIFY_TIERS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def coverage_verify_report_only() -> bool:
    return os.environ.get("TRANSLATE_COVERAGE_VERIFY", "report").strip().lower() in {
        "report",
        "warn",
        "ticket",
        "1",
        "true",
        "yes",
    }


def partition_verify_errors(
    errors: List[str],
    *,
    verify_mode: str = "full",
    coverage_report: bool = False,
) -> Tuple[List[str], List[str], List[str]]:
    """返回 (block_errors, ticket_errors, log_errors)。"""
    if not verify_tiers_enabled():
        return list(errors), [], []

    use_cov_ticket = coverage_report or coverage_verify_report_only()
    blocks: List[str] = []
    tickets: List[str] = []
    logs: List[str] = []

    for raw in errors:
        msg = str(raw).strip()
        if not msg:
            continue
        if _is_ticket(msg, use_cov_ticket=use_cov_ticket):
            tickets.append(msg)
        elif msg.startswith("[info]"):
            logs.append(msg)
        else:
            blocks.append(msg)

    return blocks, tickets, logs


def _is_ticket(message: str, *, use_cov_ticket: bool) -> bool:
    if use_cov_ticket and any(p in message for p in _COVERAGE_TICKET_PATTERNS):
        return True
    return any(p in message for p in _TICKET_PATTERNS)
