#!/usr/bin/env python3
"""《汉书》Step4 年份加固：禁止无 _年LLM依据 的占位年冒充考订结果。"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from coordinate_index import build_dynasty_index_from_json, normalize_entry_category
from emperor_resolve import build_emperor_info_index
from lib_config import coerce_year, year_range_label
from person_year_fallback import (
    entry_has_complete_years,
    entry_has_llm_year_basis,
    is_person_category,
    person_year_fallback_note,
)
from shilue_year_resolve import (
    emperor_accession_year,
    is_accession_single_point,
    is_full_reign_copy,
)

PERSON_CATS = frozenset({"文臣", "武将", "宗戚", "宦官", "庶众", "蕃祚"})


def entry_year_needs_llm_basis(entry: dict) -> bool:
    """条目已填年但缺 LLM/人工考订依据 → 须走完整 Step4 LLM。"""
    if entry_has_llm_year_basis(entry):
        return False
    return entry_has_complete_years(entry)


def person_year_needs_llm(entry: dict) -> bool:
    """人物类条目缺考订依据（兼容旧名）。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in PERSON_CATS:
        return False
    return entry_year_needs_llm_basis(entry)


def detect_person_year_placeholder(
    entry: dict,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> Optional[str]:
    """人物年生卒是否疑似帝王在位/朝代起始占位（无 _年LLM依据 时）。"""
    if not is_person_category(entry.get("史略分类", "")):
        return None
    if entry_has_llm_year_basis(entry):
        return None
    start = coerce_year(entry.get("史略开始年"))
    end = coerce_year(entry.get("史略结束年"))
    if start is None or end is None:
        return None

    eidx = emperor_index or build_emperor_info_index()
    di = dynasty_index or build_dynasty_index_from_json()
    acc, reign_end, emp = emperor_accession_year(entry, eidx)
    emp = emp or (entry.get("四级帝王坐标") or "?").strip()

    if is_full_reign_copy(start, end, acc, reign_end):
        return f"生卒等于四级帝王「{emp}」完整在位 {acc}～{reign_end}"
    if is_accession_single_point(start, end, acc):
        return f"生卒等于「{emp}」即位年单点 {acc}"
    if reign_end is not None and start == end == reign_end:
        return f"生卒等于「{emp}」退位/崩年单点 {reign_end}"

    dynasty = (entry.get("二级朝代坐标") or "").strip()
    dinfo = di.get(dynasty) or {}
    dyn_start = coerce_year(dinfo.get("start_year"))
    if dyn_start is not None and start == end == dyn_start:
        return f"生卒等于二级朝代「{dynasty}」起始年 {dyn_start}"

    if acc is not None and reign_end is not None and end == reign_end:
        span = end - start
        if span >= 4:
            if start < acc and span <= 20:
                return (
                    f"生卒疑似取「{emp}」汉初活跃期/在位末期占位 {start}～{end}，"
                    f"非学界生卒考订"
                )
            floor = dyn_start if dyn_start is not None else acc - 25
            if start <= acc and start >= floor:
                return (
                    f"生卒疑似取「{emp}」活跃期/在位期占位 {start}～{end}，"
                    f"非学界生卒考订"
                )
    return None


def _year_clear_note(entry: dict, reason: Optional[str]) -> str:
    if reason:
        return reason
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat == "君王":
        return "缺 _年LLM依据，须由 Step4 LLM 据史料考订即位/退位年"
    if cat in PERSON_CATS:
        return "缺 _年LLM依据，须由 Step4 LLM 据史料考订生卒"
    return "缺 _年LLM依据，须由 Step4 LLM 据史料考订年份"


def clear_entries_without_year_basis(
    entries: list,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
    force_all_without_basis: bool = False,
) -> Tuple[int, List[str]]:
    """
    清空无 _年LLM依据 的已填年份，并标 _needs_llm。

    force_all_without_basis=True（汉书 Step4）：凡已填年且无考订依据一律清空（含君王/人物）。
    """
    eidx = emperor_index or build_emperor_info_index()
    di = dynasty_index or build_dynasty_index_from_json()
    cleared = 0
    logs: List[str] = []
    for entry in entries:
        if not entry_year_needs_llm_basis(entry):
            continue
        start = coerce_year(entry.get("史略开始年"))
        end = coerce_year(entry.get("史略结束年"))
        if start is None or end is None:
            continue
        cat = normalize_entry_category(entry.get("史略分类", ""))
        reason = None
        if is_person_category(cat):
            reason = detect_person_year_placeholder(
                entry, emperor_index=eidx, dynasty_index=di
            )
        if not force_all_without_basis and not reason:
            continue
        eid = entry.get("史略ID", "?")
        name = entry.get("史略名称", "?")
        entry.pop("史略开始年", None)
        entry.pop("史略结束年", None)
        af = dict(entry.get("_auto_filled") or {})
        af.pop("_年兜底级别", None)
        af.pop("_年兜底依据", None)
        af["年规则"] = year_range_label(cat)
        if cat in PERSON_CATS:
            af["年规则备注"] = person_year_fallback_note()
        note = _year_clear_note(entry, reason)
        af["_年待LLM"] = note
        entry["_auto_filled"] = af
        needs = list(entry.get("_needs_llm") or [])
        for field in ("史略开始年", "史略结束年"):
            if field not in needs:
                needs.append(field)
        entry["_needs_llm"] = needs
        cleared += 1
        logs.append(f"[{eid}] {name}: 已清空 {start}～{end}（{note}）")
    return cleared, logs


def clear_placeholder_person_years(
    entries: list,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
    force_without_placeholder: bool = False,
) -> Tuple[int, List[str]]:
    """兼容旧名；行为同 clear_entries_without_year_basis。"""
    return clear_entries_without_year_basis(
        entries,
        emperor_index=emperor_index,
        dynasty_index=dynasty_index,
        force_all_without_basis=force_without_placeholder,
    )


def volume_needs_full_step4_llm(entries: list) -> bool:
    """卷内是否仍有须 LLM 考订年份的条目。"""
    return any(entry_year_needs_llm_basis(e) for e in entries)


def any_entry_missing_year_basis(entries: list) -> bool:
    """任一条目已填年但无考订依据。"""
    return any(entry_year_needs_llm_basis(e) for e in entries)


def any_person_missing_year_basis(entries: list) -> bool:
    """兼容旧名。"""
    return any_entry_missing_year_basis(entries)
