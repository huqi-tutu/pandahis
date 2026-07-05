#!/usr/bin/env python3
"""exclude 内容硬门：禁止把正文段误标为卷首标题 / 世系链等。

补 check_format 仅单向校验卷名行、以及 blocks expand 不读正文的漏洞。
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from paragraph_utils import classify_paragraph_header, _looks_like_narrative_body

HEADER_EXCLUDES = frozenset({"卷首标题", "篇内小标题", "纯纪年"})

# 有独立事迹/生平信息的标记（非纯族谱「X 生 Y」）
NARRATIVE_ACTION_MARKERS = (
    "立",
    "即位",
    "代立",
    "为秦王",
    "为汉王",
    "为相",
    "将军",
    "崩",
    "薨",
    "伐",
    "攻",
    "破",
    "围",
    "封",
    "赐",
    "见",
    "梦",
    "生於",
    "生于",
    "名曰",
    "字",
    "年十",
    "迁",
    "杀",
    "起兵",
    "反",
    "悦而取",
    "质子",
)

# 本纪开篇定语句式（「X者，Y之子也」等）——仍属主轴叙事，非世系链
OPENING_IDENTITY_RE = re.compile(
    r"^.+者，.+?(?:之子|之孙|之苗裔|中子|长子|次子|幼子|微时)",
)


def _snippet(text: str, n: int = 40) -> str:
    t = (text or "").strip()
    return t[:n] + ("…" if len(t) > n else "")


def is_opening_narrative_body(text: str) -> bool:
    """段落为可归属主轴的开篇叙事（含本纪定语起句）。"""
    t = (text or "").strip()
    if not t or len(t) < 16:
        return False
    if not _looks_like_narrative_body(t):
        return False
    if OPENING_IDENTITY_RE.match(t):
        return True
    if "。" in t and len(t) >= 24:
        return True
    return False


def is_mislabeled_genealogy_exclude(text: str) -> bool:
    """正文段不宜标世系链。"""
    t = (text or "").strip()
    if not t:
        return False
    if is_opening_narrative_body(t):
        return True
    if t.count("。") >= 2 and len(t) > 50:
        if any(m in t for m in NARRATIVE_ACTION_MARKERS):
            return True
    if any(m in t for m in ("生於", "生于", "代立", "即位", "立为", "名政", "名曰")):
        if "。" in t:
            return True
    return False


def validate_exclude_for_paragraph(
    paragraph_id: int,
    text: str,
    exclude_reason: str,
    *,
    work_id: str = "",
) -> List[str]:
    """单段 exclude 与正文是否匹配。"""
    errors: List[str] = []
    reason = (exclude_reason or "").strip()
    if not reason:
        return errors
    p = int(paragraph_id)
    t = (text or "").strip()
    header = classify_paragraph_header(t)

    if reason in HEADER_EXCLUDES:
        if header != reason:
            if header is None:
                errors.append(
                    f"P{p} 为正文（{_snippet(t)}），禁止 exclude={reason!r}"
                )
            else:
                errors.append(
                    f"P{p} 须为 exclude={header!r}，当前为 {reason!r}"
                )

    if reason == "世系链" and is_mislabeled_genealogy_exclude(t):
        errors.append(
            f"P{p} 为叙事正文（{_snippet(t)}），禁止 exclude=世系链"
        )

    if p == 1 and reason in ("卷首标题", "世系链"):
        if is_opening_narrative_body(t):
            hint = "（史记等拆分 txt 无卷首标题行）" if work_id == "01史记" else ""
            errors.append(
                f"P1 为正文开篇（{_snippet(t)}），禁止 exclude={reason!r}{hint}"
            )

    if reason == "太史公曰":
        if t.startswith("褚先生曰"):
            errors.append(
                f"P{p} 为褚先生曰，禁止 exclude=太史公曰（应标「其他」或归入三王叙事块）"
            )
        elif not t.startswith("太史公曰"):
            errors.append(
                f"P{p} 非「太史公曰」起笔（{_snippet(t)}），禁止 exclude=太史公曰"
            )

    return errors


def _paragraphs_from_excludes(draft: dict) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for item in draft.get("excludes") or []:
        if not isinstance(item, dict):
            continue
        reason = (item.get("exclude_reason") or "").strip()
        pf = int(item.get("paragraph_from") or 0)
        pt = int(item.get("paragraph_to") or pf)
        for p in range(pf, pt + 1):
            out.append((p, reason))
    return out


def validate_blocks_excludes(
    draft: dict,
    para_text: Dict[int, str],
    *,
    work_id: str = "",
) -> Tuple[bool, str]:
    """blocks expand 前：excludes 须与段落正文一致。"""
    errors: List[str] = []
    for p, reason in _paragraphs_from_excludes(draft):
        text = para_text.get(p, "")
        errors.extend(
            validate_exclude_for_paragraph(p, text, reason, work_id=work_id)
        )

    # P1 被 exclude 且主轴 block 从 P2 起 → 典型误标（卷首太史公曰除外）
    p1_excluded = any(p == 1 for p, _ in _paragraphs_from_excludes(draft))
    p1_text = para_text.get(1, "")
    p1_reason = next(
        (r for p, r in _paragraphs_from_excludes(draft) if p == 1), ""
    )
    if p1_excluded and is_opening_narrative_body(p1_text):
        if p1_reason == "太史公曰" and p1_text.startswith("太史公曰"):
            pass
        else:
            for blk in draft.get("blocks") or []:
                if not isinstance(blk, dict):
                    continue
                pf = int(blk.get("paragraph_from") or 0)
                if pf == 2:
                    name = (blk.get("name") or "").strip()
                    errors.append(
                        f"P1 误 exclude 导致主轴 {name!r} 从 P2 起，须从 P1 纳入"
                    )
                    break

    if errors:
        return False, "exclude 内容门未过:\n" + "\n".join(f"  - {e}" for e in errors[:15])
    return True, "exclude 内容 OK"


def validate_skeleton_excludes(
    data: dict,
    para_text: Dict[int, str],
    *,
    work_id: str = "",
) -> Tuple[bool, str]:
    """skeleton verify：segment_attribution excludes 与正文一致。"""
    errors: List[str] = []
    for row in data.get("segment_attribution") or []:
        reason = (row.get("exclude_reason") or "").strip()
        if not reason:
            continue
        p = int(row.get("paragraph") or 0)
        if p <= 0:
            continue
        text = para_text.get(p, "")
        errors.extend(
            validate_exclude_for_paragraph(p, text, reason, work_id=work_id)
        )

    if errors:
        return False, "exclude 内容门未过:\n" + "\n".join(f"  - {e}" for e in errors[:15])
    return True, "exclude 内容 OK"
