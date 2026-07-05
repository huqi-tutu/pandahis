"""Step 4 细坐标与原文出处：五级细坐标、六级段落锚点、原文出处。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from coordinate_index import normalize_entry_category

# 02汉书 → 汉书；01史记 → 史记
_WORK_SHORT = re.compile(r"^\d{2}(.+)$")
_VOL_FROM_PATH = re.compile(r"_(\d{3})_")
_VOL_FROM_ID = re.compile(r"^[A-Z]+_(\d{3})_\d{2}$")
_CAT_SEQ_FROM_ID = re.compile(r"^[A-Z]+_\d{3}_(\d{2})$")


def work_short_name(work_id: str) -> str:
    """01史记 → 史记；02汉书 → 汉书。"""
    wid = (work_id or "").strip()
    m = _WORK_SHORT.match(wid)
    return m.group(1) if m else wid


def volume_num_from_sources(*sources: str) -> str:
    """从路径或史略ID解析三位卷号，如 001。"""
    for src in sources:
        if not src:
            continue
        m = _VOL_FROM_PATH.search(str(src))
        if m:
            return m.group(1)
        m = _VOL_FROM_ID.match(str(src).strip())
        if m:
            return m.group(1)
    return "000"


def category_seq_from_id(entry_id: str) -> str:
    m = _CAT_SEQ_FROM_ID.match((entry_id or "").strip())
    return m.group(1) if m else "00"


def build_paragraph_anchor(entry: dict) -> str:
    """六级段落锚点：单段 [P8]，区间 [P8-P10]，多段逗号连接。"""
    paragraphs = entry.get("paragraphs") or []
    parts: List[str] = []
    for p in paragraphs:
        pf = p.get("paragraph_from")
        pt = p.get("paragraph_to")
        if not isinstance(pf, int) or not isinstance(pt, int):
            continue
        if pf == pt:
            parts.append(f"[P{pf}]")
        else:
            parts.append(f"[P{pf}-P{pt}]")
    return ",".join(parts)


def build_wuji_coord(
    entry: dict,
    *,
    work_id: str = "",
    vol_num: str = "",
) -> str:
    """五级细坐标：著作·卷NNN·分类·序号。"""
    eid = (entry.get("史略ID") or "").strip()
    cat = normalize_entry_category(entry.get("史略分类", ""))
    work = work_short_name(work_id)
    vol = vol_num or volume_num_from_sources(eid)
    seq = category_seq_from_id(eid)
    return f"{work}·卷{vol}·{cat}·{seq}"


def _strip_book_title(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("《") and s.endswith("》"):
        return s[1:-1]
    return s


def build_yuanwen_chuchu(entry: dict, *, vol_name: str = "") -> str:
    """
    原文出处：著作卷名·段落锚点（不含方括号）。
    例：汉书·高帝纪上·P8-P10
    """
    vol = vol_name or (entry.get("paragraphs") or [{}])[0].get("volume", "")
    vol = _strip_book_title(vol) or _strip_book_title(entry.get("主要史料出处", ""))
    anchor = build_paragraph_anchor(entry)
    if not anchor:
        return vol
    plain = anchor.replace("[", "").replace("]", "")
    return f"{vol}·{plain}" if vol else plain


def fill_entry_detail_coords(
    entry: dict,
    *,
    work_id: str = "",
    vol_num: str = "",
    vol_name: str = "",
) -> dict:
    """为单条 entry 写入三字段（幂等覆盖）。"""
    entry["五级细坐标"] = build_wuji_coord(entry, work_id=work_id, vol_num=vol_num)
    entry["六级段落锚点"] = build_paragraph_anchor(entry)
    entry["原文出处"] = build_yuanwen_chuchu(entry, vol_name=vol_name)
    return entry


def fill_all_detail_coords(
    data: dict,
    *,
    work_id: str = "",
    json_path: str = "",
) -> int:
    """为 skeleton 全部 entries 补三字段，返回更新条数。"""
    vol_num = volume_num_from_sources(json_path, data.get("source_file", ""))
    vol_name = (data.get("volume") or "").strip()
    count = 0
    for entry in data.get("entries") or []:
        fill_entry_detail_coords(
            entry,
            work_id=work_id,
            vol_num=vol_num,
            vol_name=vol_name,
        )
        count += 1
    return count


DETAIL_FIELDS = ("原文出处", "五级细坐标", "六级段落锚点")
