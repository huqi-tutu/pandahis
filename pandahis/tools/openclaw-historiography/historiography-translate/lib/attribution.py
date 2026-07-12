"""翻译归因清洗：非本传主事件、缺漏退场补全。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_EXIT_RE = re.compile(
    r"([\u4e00-\u9fff]{1,6})(崩|薨|卒)(?:，[^。；]{0,24})?(?:葬[^。；]{0,24})?"
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
                # 整句删除或压缩为旁注
                sent_pat = re.escape(m.group(0)) + r"[^。]*。"
                modified2 = re.sub(
                    sent_pat,
                    "",
                    modified,
                )
                if modified2 != modified:
                    changes.append(f"删除前文他人退场展开: {who}{m.group(2)}")
                    modified = modified2.strip()
        # 清理「说到这儿，得插一段…」类补丁句
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


def build_tail_exit_supplement(
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None = None,
) -> str:
    """为本传主生成尾部退场补全段落（若母本缺漏）。"""
    subject = str(recalled.get("史略名称") or "").strip()
    supplements = recalled.get("本传缺漏补全") or []
    if plan:
        supplements = supplements or plan.get("本传缺漏补全") or []

    if not supplements:
        return ""

    parts: List[str] = []
    for item in supplements:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        # 仅采纳纯退场/葬地句，跳过「X崩，而Y立」类即位过渡
        if re.search(r"崩，而|崩而|薨，而", text):
            continue
        if "崩" in text or "葬" in text:
            parts.append(
                f"《史记》又记，{text.rstrip('。')}。"
                f"这是{subject}一生的收束，亦标志世系承续的节点。"
            )
    return "\n\n".join(parts)


def apply_attribution_fixes(
    detail: str,
    recalled: Dict[str, Any],
    plan: Dict[str, Any] | None = None,
) -> Tuple[str, List[str]]:
    """归因清洗 + 尾部退场补全。"""
    changes: List[str] = []
    subject = str(recalled.get("史略名称") or "").strip()
    if not subject:
        return detail, changes

    cleaned, c1 = sanitize_foreign_exit_opening(detail, subject)
    changes.extend(c1)

    tail = build_tail_exit_supplement(recalled, plan)
    if tail and tail not in cleaned:
        ref_marker = "*参考著作*"
        if ref_marker in cleaned:
            head, ref = cleaned.split(ref_marker, 1)
            cleaned = head.rstrip() + "\n\n" + tail + "\n\n" + ref_marker + ref
        elif "参考著作" in cleaned:
            head, ref = cleaned.rsplit("参考著作", 1)
            cleaned = head.rstrip() + "\n\n" + tail + "\n\n参考著作" + ref
        else:
            cleaned = cleaned.rstrip() + "\n\n" + tail
        changes.append(f"尾部补全退场: {subject}")

    return cleaned, changes
