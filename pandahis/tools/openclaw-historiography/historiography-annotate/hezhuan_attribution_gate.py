"""合传卷 segment_attribution 归属规则：共段可多人，分段独立须单段单人物。"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

# 与 audit_hezhuan_alignment 对齐的别名
PERSON_ALIASES: Dict[str, str] = {
    "子赣": "子贡",
    "朱公": "陶朱公",
    "范蠡": "陶朱公",
    "蜀卓氏": "卓氏",
    "韩王孙嫣": "韩嫣",
    "翁伯": "郭解",
    "广德": "薛广德",
}

# 传主在正文中的常见代称/家系称呼（段内出现即视为涉及该传主）
PATRONYMIC_HINTS: Dict[str, tuple[str, ...]] = {
    "张耳": ("张王", "张敖", "故耳"),
}

# 已知卷内交接例外：正文虽未重复点名上一传主，但条目仍需覆盖交接段。
# 仅按「卷名 + 段号 + owner 精确集合」放行，避免放宽普通合传。
HANDOFF_MULTI_OWNER_EXEMPTIONS: Dict[str, Dict[int, Set[str]]] = {
    "眭两夏侯京翼李传": {
        3: {"眭弘", "夏侯始昌"},
    },
}

# 单字称呼常见句式（古典史传）
_SINGLE_CHAR_CTX_TMPL = (
    r"(?:^|[，。；：「『（(])"
    r"({})"
    r"(?:[、，。；：」』）)]|曰|怒|闻|使|乃|遂|复|与|谓|对|从|败|走|立|封|薨|崩|卒|死|将|相|王|客|也)"
)


def infer_hezhuan_protagonists(data: dict) -> List[str]:
    """合传传主名单：manifest / entries 主轴人物。"""
    names: List[str] = []
    seen: Set[str] = set()

    mode = (data.get("narrative_mode") or "").strip()
    if mode and mode != "hezhuan":
        return []

    for src in (
        data.get("protagonists_manifest") or [],
        data.get("entries") or [],
    ):
        for item in src:
            name = (item.get("name") or item.get("史略名称") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)

    if len(names) >= 2:
        return names

    if int(data.get("protagonist_count") or 0) >= 2:
        for item in data.get("entries") or []:
            name = (item.get("史略名称") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)

    return names if len(names) >= 2 else []


def is_hezhuan_volume(data: dict) -> bool:
    mode = (data.get("narrative_mode") or "").strip()
    if mode == "hezhuan":
        return True
    if mode in ("skip", "single", "fanzuo"):
        return False
    vol = (data.get("volume") or "").strip()
    if "传" in vol and len(infer_hezhuan_protagonists(data)) >= 2:
        return True
    return len(infer_hezhuan_protagonists(data)) >= 2


def _alias_hits(name: str, text: str) -> bool:
    for alias, canon in PERSON_ALIASES.items():
        if canon == name and alias in text:
            return True
    return False


def paragraph_mentions_person(name: str, text: str) -> bool:
    """段内是否涉及该传主（全名、别名或可信单字称呼）。"""
    if not name or not text:
        return False
    if name in text:
        return True
    if _alias_hits(name, text):
        return True
    for hint in PATRONYMIC_HINTS.get(name, ()):
        if hint in text:
            return True
    if len(name) < 2:
        return False
    ch = name[-1]
    plain = text.replace("\n", "")
    if re.search(_SINGLE_CHAR_CTX_TMPL.format(re.escape(ch)), plain):
        return True
    # 顿号并列：耳、馀
    if f"{ch}、" in text or f"、{ch}" in text:
        return True
    return False


def protagonists_mentioned_in_paragraph(
    text: str, protagonists: List[str]
) -> List[str]:
    return [n for n in protagonists if paragraph_mentions_person(n, text)]


def _is_exempt_multi_owner_handoff(data: dict, paragraph: int, owners: List[dict]) -> bool:
    volume = (data.get("volume") or "").strip()
    by_para = HANDOFF_MULTI_OWNER_EXEMPTIONS.get(volume) or {}
    expected = by_para.get(paragraph)
    if not expected:
        return False
    actual = {(o.get("name") or "").strip() for o in owners if (o.get("name") or "").strip()}
    return actual == expected


def hezhuan_uses_independent_paragraphs(
    data: dict, para_text: Dict[int, str], protagonists: List[str]
) -> bool:
    """
    分段独立合传：各叙事段正文至多显式涉及一位传主（写完一人再写另一人）。
    """
    for row in data.get("segment_attribution") or []:
        if row.get("exclude_reason"):
            continue
        p = int(row.get("paragraph") or 0)
        text = para_text.get(p, "")
        if not text:
            continue
        if len(protagonists_mentioned_in_paragraph(text, protagonists)) > 1:
            return False
    return True


def validate_segment_ownership(
    data: dict,
    para_text: Optional[Dict[int, str]] = None,
) -> List[str]:
    """
    返回归属错误文案列表（空=通过）。

    非合传：单段单人物。
    合传·分段独立：单段单人物。
    合传·共段叙事：允许多归属，但段内须涉及所挂全部传主。
    """
    errors: List[str] = []
    if not is_hezhuan_volume(data):
        for row in data.get("segment_attribution") or []:
            owners = row.get("owners") or []
            if len(owners) > 1:
                p = row.get("paragraph")
                errors.append(
                    f"段{p}: 禁止多归属（单段单人物），当前 {len(owners)} 个 owner"
                )
        return errors

    protagonists = infer_hezhuan_protagonists(data)
    if len(protagonists) < 2:
        for row in data.get("segment_attribution") or []:
            owners = row.get("owners") or []
            if len(owners) > 1:
                p = row.get("paragraph")
                errors.append(
                    f"段{p}: 禁止多归属（单段单人物），当前 {len(owners)} 个 owner"
                )
        return errors

    para_text = para_text or {}
    independent = (
        hezhuan_uses_independent_paragraphs(data, para_text, protagonists)
        if para_text
        else None
    )

    for row in data.get("segment_attribution") or []:
        owners = row.get("owners") or []
        if len(owners) <= 1:
            continue
        p = int(row.get("paragraph") or 0)
        text = para_text.get(p, "")

        if _is_exempt_multi_owner_handoff(data, p, owners):
            continue

        if independent is True:
            errors.append(
                f"段{p}: 分段独立合传禁止同段多归属（当前 {len(owners)} 人），"
                f"须每段仅归一位传主"
            )
            continue

        if not text:
            errors.append(
                f"段{p}: 合传共段多归属须对照正文校验，缺少段落原文"
            )
            continue

        for o in owners:
            name = (o.get("name") or "").strip()
            if not name:
                continue
            if not paragraph_mentions_person(name, text):
                errors.append(
                    f"段{p}: 合传共段多归属须正文涉及 [{name}]，当前段未见其描写"
                )

    return errors


def load_paragraph_text_map(data: dict, skeleton_path=None) -> Dict[int, str]:
    """从段落索引或原文加载段号→正文。"""
    from pathlib import Path

    from paragraph_utils import (
        resolve_source_file,
        split_mode_for_work,
        split_paragraphs,
    )

    work_m = None
    if skeleton_path:
        import re

        m = re.search(r"^(\d{2}[^_]+)_(\d{3})_", Path(skeleton_path).name)
        if m:
            work_m = m.group(1)

    src = resolve_source_file(data, Path(skeleton_path) if skeleton_path else None)
    if src and src.is_file():
        raw = src.read_text(encoding="utf-8")
        work = work_m or ""
        lines = split_paragraphs(raw, split_mode_for_work(work, raw))
        return {i + 1: ln for i, ln in enumerate(lines)}
    return {}
