#!/usr/bin/env python3
"""人物类史略年份：语义约定与脚本兜底（LLM 未填时）。

优先级（整体）：
1. 大模型据史学界主流观点填写（尽量体现正常生卒或即位/退位），脚本不得覆盖
2. 脚本兜底链见 infer_person_year_fallback / apply_person_year_fallback
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from coordinate_index import build_dynasty_index_from_json
from lib_config import coerce_year, normalize_entry_category

from category_v3 import SPINDLE_CATEGORIES

PERSON_CATEGORIES = SPINDLE_CATEGORIES - {"君王", "蕃祚"}

# 兜底级别（写入 _auto_filled._年兜底级别）
FALLBACK_LLM = "llm"
FALLBACK_JUNWANG = "君王表"
FALLBACK_SCHOLARLY = "学界生卒表"
FALLBACK_DEATH = "去世年单点"
FALLBACK_EMPEROR = "活跃期帝王在位"
FALLBACK_DYNASTY = "朝代起始年"


def is_person_category(category: str) -> bool:
    return normalize_entry_category(category) in PERSON_CATEGORIES


def person_year_semantics(category: str) -> str:
    """各分类时间坐标语义（供 Step4 / 硬检提示）。"""
    cat = normalize_entry_category(category)
    if cat == "君王":
        return "即位年 → 退位/崩年"
    if cat == "蕃祚":
        return "政权立国年 → 政权灭亡年"
    if cat in PERSON_CATEGORIES:
        return "出生年 → 去世年（君王类人物条目同即位/退位）"
    return "开始年 → 结束年"


def fanzuo_year_fallback_note_text() -> str:
    from collective_volume_subjects import COLLECTIVE_YEAR_RULE_NOTE

    return COLLECTIVE_YEAR_RULE_NOTE


def person_year_fallback_note() -> str:
    return (
        "优先由大模型据史学界主流观点填写，尽量体现正常生卒或即位/退位（含推测生年）。"
        "脚本兜底：学界有推测生卒则填完整区间；仅当完全无出生年推测且知去世年时，"
        "开始=结束=去世年；不知去世年但知活跃期则取活跃期帝王在位起止；"
        "活跃期亦未知则取对应朝代开始年（两年相同）。"
    )


def entry_has_llm_year_basis(entry: dict) -> bool:
    """是否已有 LLM/人工考订年份依据（脚本不得覆盖）。"""
    af = entry.get("_auto_filled") or {}
    return bool((af.get("_年LLM依据") or "").strip())


def entry_has_complete_years(entry: dict) -> bool:
    return (
        coerce_year(entry.get("史略开始年")) is not None
        and coerce_year(entry.get("史略结束年")) is not None
    )


def normalize_partial_person_years(entry: dict) -> bool:
    """兜底：仅知去世年（或仅知一年）时，开始年=结束年。"""
    if not is_person_category(entry.get("史略分类", "")):
        return False
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    if start is not None and end is None:
        entry["史略结束年"] = start
        return True
    if end is not None and start is None:
        entry["史略开始年"] = end
        af = dict(entry.get("_auto_filled") or {})
        af["_死亡年锚定"] = True
        entry["_auto_filled"] = af
        return True
    return False


def infer_person_year_fallback(
    entry: dict,
    *,
    emperor_info: Optional[dict] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
    death_year: Optional[int] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """
    人物类脚本兜底（LLM 未填完整时）。

    1. 学界有推测生卒（含仅生年推测）→ 完整生年～卒年
    2. 完全无出生年推测、仅知去世年 → 开始年 = 结束年 = 去世年
    3. 不知去世年、知活跃期（四级帝王已锚定）→ 活跃期帝王在位起止
    4. 活跃期亦未知 → 二级朝代对应朝代开始年（两年相同）
    """
    if not is_person_category(entry.get("史略分类", "")):
        return None, None

    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    if end is not None and start is None:
        return end, end
    if start is not None and end is None:
        return start, start
    if start is not None and end is not None:
        return None, None

    if death_year is not None:
        y = int(death_year)
        return y, y

    if emperor_info:
        es = emperor_info.get("start_year")
        ee = emperor_info.get("end_year")
        if es is not None and ee is not None:
            return int(es), int(ee)

    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    dynasty = (entry.get("二级朝代坐标") or "").strip()
    if not dynasty:
        auto = entry.get("_auto_filled") or {}
        dynasty = (auto.get("二级朝代坐标") or "").strip()
    if dynasty:
        dinfo = di.get(dynasty)
        if dinfo and dinfo.get("start_year") is not None:
            y = int(dinfo["start_year"])
            return y, y

    return None, None


def apply_person_year_fallback(
    entry: dict,
    *,
    emperor_info: Optional[dict] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> Tuple[Optional[int], Optional[int], str, str]:
    """
    执行兜底并返回 (开始年, 结束年, 级别, 说明)。
    条目已有完整年份时返回 (None, None, '', '')。
    """
    from shiji_death_years import lookup_death_year
    from shiji_scholarly_lifespans import (
        is_death_only_candidate,
        lookup_scholarly_lifespan,
    )

    if not is_person_category(entry.get("史略分类", "")):
        return None, None, "", ""

    normalize_partial_person_years(entry)
    if entry_has_complete_years(entry):
        return None, None, "", ""

    span = lookup_scholarly_lifespan(entry)
    if span is not None:
        ys, ye, note = span
        return ys, ye, FALLBACK_SCHOLARLY, note

    death = lookup_death_year(entry)
    if death is not None and is_death_only_candidate(entry):
        ys, ye = infer_person_year_fallback(
            entry, death_year=death, dynasty_index=dynasty_index
        )
        if ys is not None:
            note = f"仅知去世年前{abs(death)}、无学界出生年推测，开始年=结束年"
            return ys, ye, FALLBACK_DEATH, note

    if emperor_info:
        ys, ye = infer_person_year_fallback(
            entry, emperor_info=emperor_info, dynasty_index=dynasty_index
        )
        if ys is not None and ye is not None and ys != ye:
            emp = emperor_info.get("emperor") or emperor_info.get("帝王名称") or "?"
            return (
                ys,
                ye,
                FALLBACK_EMPEROR,
                f"活跃期取四级帝王「{emp}」在位 {ys}～{ye}",
            )

    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    ys, ye = infer_person_year_fallback(entry, dynasty_index=di)
    if ys is not None:
        dyn = (entry.get("二级朝代坐标") or "").strip()
        return ys, ye, FALLBACK_DYNASTY, f"取二级朝代「{dyn}」起始年 {ys}"

    return None, None, "", ""


def write_fallback_years_to_entry(
    entry: dict,
    start: int,
    end: int,
    level: str,
    note: str,
) -> None:
    """写入兜底年份与元数据；不覆盖已有 _年LLM依据。"""
    if entry_has_llm_year_basis(entry):
        return
    entry["史略开始年"] = int(start)
    entry["史略结束年"] = int(end)
    af = dict(entry.get("_auto_filled") or {})
    af["_年兜底级别"] = level
    af["_年兜底依据"] = note
    af.pop("_年待LLM", None)
    if level == FALLBACK_DEATH:
        af["_死亡年锚定"] = True
    elif level == FALLBACK_SCHOLARLY:
        af.pop("_死亡年锚定", None)
        af["_年LLM依据"] = note
        af.pop("_年兜底级别", None)
        af.pop("_年兜底依据", None)
        entry["_auto_filled"] = af
        needs = [n for n in (entry.get("_needs_llm") or []) if n not in (
            "史略开始年", "史略结束年",
        )]
        if needs:
            entry["_needs_llm"] = needs
        else:
            entry.pop("_needs_llm", None)
        return
    else:
        af.pop("_死亡年锚定", None)
    entry["_auto_filled"] = af
    needs = [n for n in (entry.get("_needs_llm") or []) if n not in (
        "史略开始年", "史略结束年",
    )]
    # 帝王在位/朝代单年兜底后仍交 LLM 补全生卒
    if level in (FALLBACK_EMPEROR, FALLBACK_DYNASTY):
        for f in ("史略开始年", "史略结束年"):
            if f not in needs:
                needs.append(f)
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)
