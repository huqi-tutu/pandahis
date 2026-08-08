#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
史略分类规范化：割据政权/列国国君 → 诸侯；仅统领全国者保留君王。

用于 build_online_index 与 06 源数据修正。
"""

from __future__ import annotations

import re
from copy import deepcopy

# 三级政权坐标：列国/割据（非周天子、非统一王朝）
FEUDAL_REGIME_IDS = frozenset({
    "齐", "鲁", "楚", "燕", "赵", "魏", "韩", "卫", "宋", "郑", "陈", "蔡", "曹",
    "吴", "越", "秦",  # 秦统一前为诸侯国；统一后条目另有判定
    "西楚", "项", "淮阳", "梁", "淮南", "长沙", "济北", "胶东", "河间", "江都",
})

NATIONAL_REGIME_IDS = frozenset({
    "东周", "西周", "周", "夏", "商", "殷", "汉", "新", "秦",  # 秦帝国期
})

# 用户裁定：项羽虽有本纪但归君王（非诸侯）
FORCE_JUNWANG_IDS = frozenset({"GLBL_00143"})
FORCE_JUNWANG_NAMES = frozenset({"项羽"})

# 明确裁定：有本纪但未统一天下（项羽除外，见 FORCE_JUNWANG_*）
FORCE_ZHUHOU_IDS = frozenset()

FORCE_ZHUHOU_NAMES = frozenset()


def _regime_label(entry: dict) -> str:
    return str(
        entry.get("三级政权坐标")
        or entry.get("政权")
        or entry.get("regime_name")
        or ""
    ).strip()


def _source_text(entry: dict) -> str:
    return str(entry.get("主要史料出处") or "") + str(entry.get("母本著作") or "")


def should_be_zhuhou(entry: dict) -> bool:
    """判断是否应从君王降为诸侯。"""
    eid = str(entry.get("史略ID") or "").strip()
    name = str(entry.get("史略名称") or "").strip()
    if eid in FORCE_JUNWANG_IDS or name in FORCE_JUNWANG_NAMES:
        return False

    cat = str(entry.get("史略分类") or "").strip()
    if cat != "君王":
        return False

    regime = _regime_label(entry)
    src = _source_text(entry)

    # 周天子（东周/西周）保留君王
    if regime in ("东周", "西周", "周") or (name.startswith("周") and "王" in name and regime in ("", "东周", "西周", "周")):
        if "周本纪" in src or "周本纪" in str(entry.get("主要史料出处") or ""):
            return False
        if name.startswith("周") and len(name) <= 4:
            return False

    # 史记世家 → 列国国君
    if "世家" in src and "周本纪" not in src:
        return True

    # 割据政权
    if regime in FEUDAL_REGIME_IDS:
        # 秦始皇等统一后君王：本纪 + 秦 + 战国末年
        if regime == "秦" and "秦始皇" in name:
            return False
        if regime == "秦":
            sy = entry.get("史略开始年")
            if sy is not None and int(sy) >= -221:
                return False  # 帝制秦
            return True  # 先秦秦为诸侯
        return True

    if regime == "西楚":
        return False  # 项羽等 FORCE_JUNWANG 已单独处理；其余西楚条目保持原分类

    return False


def _patch_fine_coordinate(entry: dict, new_cat: str) -> None:
    coord = str(entry.get("五级细坐标") or "")
    if not coord:
        return
    entry["五级细坐标"] = re.sub(r"·君王·", f"·{new_cat}·", coord)
    entry["五级细坐标"] = re.sub(r"·君纪·", f"·{new_cat}·", entry["五级细坐标"])


def normalize_entry_category(entry: dict, *, in_place: bool = False) -> tuple[dict, bool]:
    """
    若条目应为诸侯而非君王，修正 史略分类 与五级细坐标。
    若条目强制为君王（如项羽），从诸侯升回君王。
    返回 (entry, changed)。
    """
    e = entry if in_place else deepcopy(entry)
    eid = str(e.get("史略ID") or "").strip()
    name = str(e.get("史略名称") or "").strip()
    if eid in FORCE_JUNWANG_IDS or name in FORCE_JUNWANG_NAMES:
        old = str(e.get("史略分类") or "").strip()
        if old != "君王":
            e["史略分类"] = "君王"
            _patch_fine_coordinate(e, "君王")
            return e, True
        return e, False
    if not should_be_zhuhou(e):
        return e, False
    old = str(e.get("史略分类") or "").strip()
    if old == "诸侯":
        return e, False
    e["史略分类"] = "诸侯"
    _patch_fine_coordinate(e, "诸侯")
    return e, True


def normalize_entries(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """批量规范化，返回 (entries, change_log)。"""
    out: list[dict] = []
    log: list[str] = []
    for item in entries:
        fixed, changed = normalize_entry_category(item)
        out.append(fixed)
        if changed:
            log.append(
                f"{fixed.get('史略ID')} {fixed.get('史略名称')}: 君王 → 诸侯"
            )
    return out, log
