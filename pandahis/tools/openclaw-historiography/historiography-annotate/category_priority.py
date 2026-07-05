#!/usr/bin/env python3
"""史略分类唯一性：同一人多重身份时取最高类（v3）。

君王 ＞ 宗戚 ＞ 宦官 ＞ 文臣 / 武将 ＞ 蕃祚 ＞ 庶众

注意：本模块只解决「某人已定为 entry 后填哪一类」，不决定「本卷主人公是谁」。
"""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from category_v3 import VALID_CATS

CATEGORY_RANK: Dict[str, int] = {
    "君王": 7,
    "宗戚": 6,
    "宦官": 5,
    "文臣": 4,
    "武将": 4,
    "蕃祚": 2,
    "庶众": 1,
    # 读盘兼容（迁移前）
    "士臣": 4,
}

PRIORITY_CHAIN_DESC = "君王 ＞ 宗戚 ＞ 宦官 ＞ 文臣/武将 ＞ 蕃祚 ＞ 庶众"

GLOBAL_CATEGORY_FORCE: Dict[str, str] = {
    "孔子": "文臣",
    "陈涉": "庶众",
}


def pick_higher_category(a: str, b: str) -> str:
    ra = CATEGORY_RANK.get((a or "").strip(), 0)
    rb = CATEGORY_RANK.get((b or "").strip(), 0)
    return a if ra >= rb else b


def candidate_categories(
    name: str,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    volume_overrides: Optional[Dict[str, str]] = None,
) -> Set[str]:
    n = (name or "").strip()
    cats: Set[str] = set()
    if not n:
        return cats
    if volume_overrides and n in volume_overrides:
        cats.add(volume_overrides[n])
    eidx = emperor_index or {}
    if n in eidx:
        cats.add("君王")
    return cats


def resolve_person_category(
    name: str,
    proposed: str,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    volume_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[str, Optional[str]]:
    n = (name or "").strip()
    cat = (proposed or "").strip()
    if not n or cat not in CATEGORY_RANK:
        return cat, None

    overrides = volume_overrides or {}
    if n in overrides:
        want = overrides[n]
        if cat != want:
            return want, f"{n} 卷级特例 {cat}→{want}"
        return cat, None

    if n in GLOBAL_CATEGORY_FORCE:
        want = GLOBAL_CATEGORY_FORCE[n]
        if cat != want:
            return want, f"{n} 强制分类 {cat}→{want}（非君王叙事）"
        return cat, None

    candidates = {cat}
    candidates.update(
        candidate_categories(n, emperor_index=emperor_index, volume_overrides=overrides)
    )
    best = max(candidates, key=lambda c: CATEGORY_RANK.get(c, 0))
    if best != cat:
        return best, f"{n} 分类优先级 {cat}→{best}（{PRIORITY_CHAIN_DESC}）"
    return cat, None


def normalize_category_fields(
    items: list,
    *,
    name_key: str = "name",
    category_key: str = "category",
    emperor_index: Optional[Dict[str, dict]] = None,
    volume_overrides: Optional[Dict[str, str]] = None,
) -> list:
    logs: list = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get(name_key) or "").strip()
        cat = (item.get(category_key) or "").strip()
        if not name or not cat:
            continue
        resolved, msg = resolve_person_category(
            name,
            cat,
            emperor_index=emperor_index,
            volume_overrides=volume_overrides,
        )
        if msg:
            item[category_key] = resolved
            logs.append(msg)
    return logs


def volume_category_overrides(
    work: str, vol: str, volume_name: str = ""
) -> Dict[str, str]:
    from identity_gate import _rule_for  # noqa: WPS433

    vol_z = vol.zfill(3)
    overrides: Dict[str, str] = dict(GLOBAL_CATEGORY_FORCE)
    rule = _rule_for(work, vol_z, volume_name)
    if rule:
        for req in rule.get("required") or []:
            n = (req.get("name") or "").strip()
            c = (req.get("category") or "").strip()
            if n and c:
                overrides[n] = c
    return overrides
