#!/usr/bin/env python3
"""蕃祚卷白名单（SSOT：reference/卷型补充/蕃祚卷型.md）。"""

from __future__ import annotations

import re
from typing import List

# 《史记》蕃祚卷（卷号 → 卷名关键词）
SHIJI_FANZUO_VOLUME_RES = {
    "110": r"匈奴",
    "113": r"南越",
    "114": r"东越",
    "115": r"朝鲜",
    "116": r"西南夷",
    "123": r"大宛",
}

# 《汉书》蕃祚卷（卷号 → 卷名正则片段）
HANSHU_FANZUO_VOLUME_RES = {
    "107": r"匈奴",
    "108": r"匈奴",
    "109": r"西南夷|两粤|朝鲜",
    "110": r"西域",
    "111": r"西域",
}

HANSHU_FANZUO_VOLUME_KEYWORDS = (
    "匈奴传",
    "西南夷两粤朝鲜传",
    "西域传",
)

# 《后汉书》蕃祚卷（卷号 → 卷名关键词；对齐 蕃祚卷型.md §3，并含东夷/西域/南匈奴）
HOUHANSHU_FANZUO_VOLUME_RES = {
    "095": r"东夷",
    "096": r"南蛮|西南夷",
    "097": r"西羌",
    "098": r"西域",
    "099": r"南匈奴|匈奴",
    "100": r"乌桓|鲜卑",
}

HOUHANSHU_FANZUO_VOLUME_KEYWORDS = (
    "东夷列传",
    "南蛮西南夷列传",
    "西羌传",
    "西域传",
    "南匈奴列传",
    "乌桓鲜卑列传",
)

# 《三国志》蕃祚卷（对齐 蕃祚卷型.md §4）
SANGUOZHI_FANZUO_VOLUME_RES = {
    "030": r"乌丸|鲜卑|东夷",
}

SANGUOZHI_FANZUO_VOLUME_KEYWORDS = (
    "乌丸鲜卑东夷传",
)


def is_fanzuo_volume(work: str, vol: str, volume_name: str = "") -> bool:
    """卷是否属于蕃祚卷型白名单。"""
    vol_p = str(vol or "").zfill(3)
    vn = (volume_name or "").strip()

    if work == "01史记":
        if vol_p in SHIJI_FANZUO_VOLUME_RES:
            return True
        return any(
            k in vn for k in ("匈奴", "南越", "东越", "朝鲜", "西南夷", "大宛")
        )

    if work == "02汉书":
        if vol_p in HANSHU_FANZUO_VOLUME_RES:
            return True
        return any(k in vn for k in HANSHU_FANZUO_VOLUME_KEYWORDS)

    if work == "03后汉书":
        if vol_p in HOUHANSHU_FANZUO_VOLUME_RES:
            return True
        return any(k in vn for k in HOUHANSHU_FANZUO_VOLUME_KEYWORDS)

    if work == "04三国志":
        if vol_p in SANGUOZHI_FANZUO_VOLUME_RES:
            return True
        return any(k in vn for k in SANGUOZHI_FANZUO_VOLUME_KEYWORDS)

    # 其他著作：据卷名关键词兜底（与蕃祚卷型.md 四夷/外国传体例一致）
    if vn and re.search(
        r"(匈奴|南匈奴|南越|东越|东夷|朝鲜|西南夷|南蛮|西羌|西域|乌桓|乌丸|鲜卑|四夷|外国|夷蛮|异域)列传?",
        vn,
    ):
        return True
    return False


def fanzuo_category_errors(
    work: str,
    vol: str,
    volume_name: str,
    pairs: List[tuple],
    *,
    prefix: str = "",
) -> List[str]:
    """非蕃祚卷使用 category=蕃祚 → 硬错误。"""
    if is_fanzuo_volume(work, vol, volume_name):
        return []
    errors: List[str] = []
    for name, cat in pairs:
        if (cat or "").strip() != "蕃祚":
            continue
        label = f"{prefix}{name!r}" if name else f"{prefix}(未命名)"
        errors.append(
            f"{label} 禁止蕃祚：本卷不在蕃祚卷型白名单"
            f"（见 reference/卷型补充/蕃祚卷型.md；《汉书》仅匈奴传/西南夷两粤朝鲜传/西域传）"
        )
    return errors
