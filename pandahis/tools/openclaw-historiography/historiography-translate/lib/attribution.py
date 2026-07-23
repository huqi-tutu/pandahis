"""翻译归因清洗：非本传主事件展开压缩；尾部模板补丁清除。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_EXIT_RE = re.compile(
    r"([\u4e00-\u9fff]{1,6})(崩|薨|卒)(?:，[^。；]{0,24})?(?:葬[^。；]{0,24})?"
)

# 历史 attribution 尾部模板（已废弃生成，仅用于存量清洗）
_TAIL_TEMPLATE_RE = re.compile(
    r"\n*\*?\s*\n*《史记》又记，[^。\n]+。这是[^。\n]+一生的收束，亦标志世系承续的节点。",
    re.MULTILINE,
)


def _normalize_name(name: str) -> str:
    n = (name or "").strip()
    for prefix in ("帝", "王"):
        if n.startswith(prefix) and len(n) > 1:
            return n[len(prefix) :]
    return n


def _names_match(a: str, b: str) -> bool:
    na, nb = _normalize_name(a), _normalize_name(b)
    return bool(na and nb and (na == nb or na in nb or nb in na))


def detect_foreign_exit_in_opening(
    detail: str,
    subject: str,
    *,
    head_ratio: float = 0.25,
) -> List[str]:
    """正文前部是否展开非本传主的退场/葬地。"""
    issues: List[str] = []
    body = detail.split("*参考著作*")[0].split("参考著作")[0]
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        return issues
    head_chars = max(400, int(len(body) * head_ratio))
    head = body[:head_chars]

    for m in _EXIT_RE.finditer(head):
        who = m.group(1)
        if who and not _names_match(who, subject):
            issues.append(
                f"正文前部展开他人退场: {who}{m.group(2)}（本传主为{subject}）"
            )
    return issues


def sanitize_foreign_exit_opening(detail: str, subject: str) -> Tuple[str, List[str]]:
    """删除/压缩正文前部对他人退场的展开描写。"""
    changes: List[str] = []
    subject_norm = _normalize_name(subject)

    paras = detail.split("\n\n")
    ref_idx = next(
        (i for i, p in enumerate(paras) if "*参考著作*" in p or p.strip().startswith("参考著作")),
        len(paras),
    )
    body_paras = paras[:ref_idx]
    tail_paras = paras[ref_idx:]

    new_body: List[str] = []
    for i, para in enumerate(body_paras):
        if i > 2:
            new_body.append(para)
            continue
        modified = para
        for m in list(_EXIT_RE.finditer(para)):
            who = m.group(1)
            if who and not _names_match(who, subject):
                sent_pat = re.escape(m.group(0)) + r"[^。]*。"
                modified2 = re.sub(
                    sent_pat,
                    "",
                    modified,
                )
                if modified2 != modified:
                    changes.append(f"删除前文他人退场展开: {who}{m.group(2)}")
                    modified = modified2.strip()
        modified = re.sub(
            r"说到这儿，得插一段[^。]+。",
            "",
            modified,
        ).strip()
        if modified:
            new_body.append(modified)

    if not changes:
        return detail, changes
    return "\n\n".join([*new_body, *tail_paras]), changes


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
    """归因清洗 + 清除历史尾部模板残留。"""
    changes: List[str] = []
    subject = str(recalled.get("史略名称") or "").strip()
    if not subject:
        cleaned, stripped = strip_tail_exit_template(detail)
        if stripped:
            changes.append("清除尾部又记模板")
        return cleaned, changes

    cleaned, c1 = sanitize_foreign_exit_opening(detail, subject)
    changes.extend(c1)

    cleaned, stripped = strip_tail_exit_template(cleaned)
    if stripped:
        changes.append("清除尾部又记模板")

    return cleaned, changes
