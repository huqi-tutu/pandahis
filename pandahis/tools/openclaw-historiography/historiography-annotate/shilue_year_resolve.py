#!/usr/bin/env python3
"""事略年份推断：原文纪年解析 + 缺年单点锚定。"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from coordinate_index import normalize_entry_category
from emperor_resolve import (
    build_emperor_info_index,
    junji_from_entry_segments,
    volume_junji_emperors,
    _nearest_junji_for_entry,
    _pick_volume_primary_junji,
)

_CN_DIG = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "两": 2,
}

# 叙事纪年：N年 / 元年（排除「三十三岁」等年龄表述）
_RE_YUAN = re.compile(r"(?<![岁])元年")
_RE_NIAN = re.compile(r"(?<![岁])([一二三四五六七八九十两]+|\d+)年")
_RE_BC = re.compile(r"前(\d{1,4})")
# 具名帝王纪年：秦二世元年、高祖三年、武帝元狩元年 等
_RE_NAMED_REIGN = re.compile(
    r"(秦二世|秦始皇帝|秦始皇|始皇帝|二世|"
    r"汉高祖|高祖|惠帝|高后|文帝|景帝|武帝|昭帝|宣帝|元帝|"
    r"成帝|哀帝|平帝|王莽|更始帝|光武帝|明帝|章帝|"
    r"[\u4e00-\u9fff]{1,4}帝|"
    r"[\u4e00-\u9fff]{1,3}王)"
    r"(?:元狩|元鼎|元封|太初|天汉|太始|征和|后元|建元|元光|元朔|元狩|"
    r"元鼎|元封|太初|天汉|太始|征和|后元|"
    r"[\u4e00-\u9fff]{1,2})?"
    r"(?<![岁])(?:元年|([一二三四五六七八九十两]+|\d+)年)"
)

# 庙号/简称 → 帝王表键名
_EMPEROR_ALIASES: Dict[str, str] = {
    "秦始皇": "秦始皇帝",
    "始皇帝": "秦始皇帝",
    "二世": "秦二世",
    "高祖": "汉高祖",
    "惠帝": "汉惠帝",
    "高后": "吕后",
    "文帝": "汉文帝",
    "景帝": "汉景帝",
    "武帝": "汉武帝",
    "昭帝": "汉昭帝",
    "宣帝": "汉宣帝",
    "元帝": "汉元帝",
}

# 《史记》「始皇N年」含秦王政在位（前246即位），非仅帝号前221
_QIN_SHIHUANG_KING_ACCESSION = -246
_QIN_SHIHUANG_NAMES = frozenset({"秦始皇", "秦始皇帝"})
# 帝王表占位/脏数据：超宽或过早的即位年不可用于纪年换算
_PLACEHOLDER_ACCESSION_CUTOFF = -400


def cn_reign_year_to_int(token: str) -> Optional[int]:
    """中文纪年数字 → 整数（元年=1，二十二=22）。"""
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token == "元":
        return 1
    if token == "十":
        return 10
    if token.startswith("十") and len(token) == 2:
        return 10 + _CN_DIG.get(token[1], 0)
    if "十" in token:
        parts = token.split("十", 1)
        tens = _CN_DIG.get(parts[0], 1) if parts[0] else 1
        ones = _CN_DIG.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    if len(token) == 1 and token in _CN_DIG:
        return _CN_DIG[token]
    return None


def extract_bc_years(text: str) -> List[int]:
    """从原文提取「前N年」绝对年（公元前为负），去重保序。"""
    years: List[int] = []
    seen: Set[int] = set()
    for m in _RE_BC.finditer(text or ""):
        y = -int(m.group(1))
        if y not in seen:
            years.append(y)
            seen.add(y)
    return years


def extract_reign_years_from_text(text: str) -> List[int]:
    """从原文提取相对纪年（在位第 N 年），去重保序。"""
    if not text:
        return []
    years: List[int] = []
    seen: Set[int] = set()
    if _RE_YUAN.search(text):
        years.append(1)
        seen.add(1)
    for m in _RE_NIAN.finditer(text):
        val = cn_reign_year_to_int(m.group(1))
        if val is not None and val not in seen:
            years.append(val)
            seen.add(val)
    return years


def reign_year_to_absolute(reign_year: int, accession_year: int) -> int:
    """在位第 N 年 → 绝对年（公元前为负）。"""
    return accession_year + (reign_year - 1)


def emperor_accession_year(
    entry: dict,
    emperor_index: Dict[str, dict],
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """返回 (即位年, 退位年, 帝王名)。"""
    auto = entry.get("_auto_filled") or {}
    rs = auto.get("帝王开始年")
    re = auto.get("帝王结束年")
    coord = (entry.get("四级帝王坐标") or "").strip()
    if coord and coord in emperor_index:
        info = emperor_index[coord]
        rs = rs if rs is not None else info.get("start_year")
        re = re if re is not None else info.get("end_year")
        return rs, re, coord
    if rs is not None:
        return rs, re, coord or None
    return None, None, coord or None


def reign_accession_for_text(
    entry: dict,
    emperor_index: Dict[str, dict],
    text: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    解析用于「N年/元年」换算的即位年。
    秦始皇条目若原文含「始皇N年」且换算结果早于前221，用秦王政即位前246，而非帝号前221。
    """
    accession, reign_end, emp_name = emperor_accession_year(entry, emperor_index)
    body = text if text is not None else f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    if emp_name not in _QIN_SHIHUANG_NAMES or "始皇" not in (body or ""):
        return accession, reign_end, emp_name
    reign_years = extract_reign_years_from_text(body)
    if not reign_years:
        return accession, reign_end, emp_name
    earliest = min(
        reign_year_to_absolute(y, _QIN_SHIHUANG_KING_ACCESSION) for y in reign_years
    )
    bad_accession = accession is None or accession <= _PLACEHOLDER_ACCESSION_CUTOFF
    if bad_accession or accession == -221 or earliest < -221:
        return _QIN_SHIHUANG_KING_ACCESSION, reign_end, emp_name
    return accession, reign_end, emp_name


def _resolve_anchor_emperor(
    entry: dict,
    data: Optional[dict],
    emperor_index: Dict[str, dict],
) -> Tuple[Optional[int], Optional[int], str]:
    """缺原文纪年时，取共段君纪即位年作单点锚定。"""
    rs, re, name = emperor_accession_year(entry, emperor_index)
    if rs is not None:
        return rs, re, name or "关联帝王"

    if not data:
        return None, None, ""
    junji = volume_junji_emperors(data)
    primary = (
        junji_from_entry_segments(entry, data, junji)
        or _nearest_junji_for_entry(entry, data, junji)
        or _pick_volume_primary_junji(junji)
    )
    if primary and primary in emperor_index:
        info = emperor_index[primary]
        return info.get("start_year"), info.get("end_year"), primary
    return None, None, ""


def infer_shilue_years(
    entry: dict,
    *,
    data: Optional[dict] = None,
    emperor_index: Optional[Dict[str, dict]] = None,
    text: Optional[str] = None,
) -> Optional[Tuple[int, int, str, str]]:
    """
    推断事略起止年。
    返回 (开始年, 结束年, 兜底级别, 说明)；无法推断则 None。
    """
    if normalize_entry_category(entry.get("史略分类", "")) not in ("事略", "典制"):
        return None

    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()
    body = text if text is not None else (
        f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    )
    accession, reign_end, emp_name = reign_accession_for_text(entry, eidx, body)

    reign_years = extract_reign_years_from_text(body)
    abs_years: List[int] = []
    named_years = extract_named_reign_abs_years(body, eidx)
    if named_years:
        abs_years.extend(named_years)
    elif accession is not None:
        abs_years = [reign_year_to_absolute(y, accession) for y in reign_years]
    abs_years.extend(extract_bc_years(body))

    if len(abs_years) >= 2:
        start, end = min(abs_years), max(abs_years)
        if normalize_entry_category(entry.get("史略分类", "")) == "典制":
            return (start, start, "text_single", f"典制取最早纪年 → 单点 {start}")
        if start != end:
            return (
                start,
                end,
                "text_span",
                f"原文纪年 → 绝对年 {start}～{end}",
            )

    if len(abs_years) >= 1:
        y = abs_years[0] if len(abs_years) == 1 else min(abs_years)
        return (y, y, "text_single", f"原文纪年 → 单点 {y}")

    accession, reign_end, emp_name = _resolve_anchor_emperor(entry, data, eidx)
    if accession is not None:
        label = emp_name or "共段君纪"
        return (
            accession,
            accession,
            "junji_accession_single_point",
            f"史无详年，单点锚定「{label}」即位年 {accession}",
        )
    return None


def extract_named_reign_abs_years(
    text: str,
    emperor_index: Dict[str, dict],
) -> List[int]:
    """从「秦二世元年」「高祖三年」等具名纪年提取绝对年。"""
    if not text or not emperor_index:
        return []
    years: List[int] = []
    seen: Set[int] = set()
    for m in _RE_NAMED_REIGN.finditer(text):
        raw_name = m.group(1)
        year_token = m.group(2)
        emp_key = _EMPEROR_ALIASES.get(raw_name, raw_name)
        if emp_key not in emperor_index:
            # 尝试模糊：X帝 → 汉X帝 / 直接匹配
            for candidate in (f"汉{raw_name}", raw_name):
                if candidate in emperor_index:
                    emp_key = candidate
                    break
            else:
                continue
        info = emperor_index[emp_key]
        accession = info.get("start_year")
        if accession is None:
            continue
        if year_token in (None, ""):
            reign_year = 1
        else:
            reign_year = cn_reign_year_to_int(year_token)
        if reign_year is None:
            continue
        abs_y = reign_year_to_absolute(reign_year, accession)
        if abs_y not in seen:
            years.append(abs_y)
            seen.add(abs_y)
    return years


def is_accession_single_point(
    start: int,
    end: int,
    accession: Optional[int],
) -> bool:
    """事略年是否为即位年单点占位（未据原文锚定）。"""
    return accession is not None and start == end == accession


def volume_junji_year_span(
    data: Optional[dict],
) -> Tuple[Optional[int], Optional[int]]:
    """取本卷君纪条目的起止年（卷级占位年的比对基准）。"""
    if not data:
        return None, None
    for entry in data.get("entries") or []:
        if normalize_entry_category(entry.get("史略分类", "")) != "君纪":
            continue
        start, end = entry.get("史略开始年"), entry.get("史略结束年")
        if isinstance(start, int) and isinstance(end, int):
            return start, end
    return None, None


def is_volume_junji_year_copy(
    start: int,
    end: int,
    data: Optional[dict],
) -> bool:
    """事略/典制年是否与本卷君纪条目完全相同（卷级批量占位）。"""
    js, je = volume_junji_year_span(data)
    return js is not None and je is not None and start == js and end == je


def is_manual_year_confirmed(entry: dict) -> bool:
    """人工/LLM 已确认具体年，不再视为占位。"""
    auto = entry.get("_auto_filled") or {}
    return bool((auto.get("_年LLM依据") or "").strip())


def is_shilue_year_placeholder(
    start: int,
    end: int,
    accession: Optional[int],
    reign_end: Optional[int],
    *,
    data: Optional[dict] = None,
    entry: Optional[dict] = None,
) -> bool:
    """事略年是否为帝王在位期照搬、即位年单点或卷级君纪占位。"""
    if entry and is_manual_year_confirmed(entry):
        return False
    if is_volume_junji_year_copy(start, end, data):
        return True
    return is_full_reign_copy(start, end, accession, reign_end) or is_accession_single_point(
        start, end, accession
    )


def is_full_reign_copy(
    start: int,
    end: int,
    accession: Optional[int],
    reign_end: Optional[int],
) -> bool:
    """事略年是否等于关联帝王完整在位期（多年区间）。"""
    return (
        accession is not None
        and reign_end is not None
        and start == accession
        and end == reign_end
        and accession != reign_end
    )
