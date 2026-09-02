"""翻译归因清洗 + 成稿程序化终处理（引号 / 参考著作）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# 历史 attribution 尾部模板（已废弃生成，仅用于存量清洗）
_TAIL_TEMPLATE_RE = re.compile(
    r"\n*\*?\s*\n*《史记》又记，[^。\n]+。这是[^。\n]+一生的收束，亦标志世系承续的节点。",
    re.MULTILINE,
)


def strip_tail_exit_template(detail: str) -> Tuple[str, bool]:
    """清除已废弃的「《史记》又记…一生收束」尾部模板段。"""
    new_detail, n = _TAIL_TEMPLATE_RE.subn("", detail)
    # 清孤立 * 分隔行
    new_detail = re.sub(r"\n\n\*\n\n", "\n\n", new_detail)
    new_detail = re.sub(r"\n\n\*\s*$", "", new_detail.rstrip()) + (
        "\n" if detail.endswith("\n") else ""
    )
    return new_detail, n > 0


def build_tail_exit_supplement(
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None = None,
) -> str:
    """已废弃：不再生成「《史记》又记」尾部补丁。保留函数签名供旧脚本 import。"""
    _ = recalled, plan
    return ""


def apply_attribution_fixes(
    detail: str,
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None = None,
) -> Tuple[str, List[str]]:
    """归因清洗 + 引号校正 + 程序拼接参考著作。"""
    changes: List[str] = []
    cleaned, stripped = strip_tail_exit_template(detail)
    if stripped:
        changes.append("清除尾部又记模板")
    from lib.final_polish import finalize_translation_detail

    finalized, polish_changes = finalize_translation_detail(
        cleaned, recalled, plan=plan
    )
    changes.extend(polish_changes)
    return finalized, changes
