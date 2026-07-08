#!/usr/bin/env python3
"""
Step 4: 字段补全辅助脚本
从 reference/帝王.json、政权.json、朝代.json 自动填充时空坐标。

用法:
  python3 fill_fields.py <skeleton.json> [--output enhanced.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from coordinate_index import (
    COORD_FIELDS,
    COORD_ID_FIELDS,
    FOURTH_EMPIRE_COORD_FIELD,
    SCRIPT_COORD_FIELDS,
    coords_and_ids_from_emperor,
    coords_from_emperor,
    entry_coords_mismatch_emperor,
    migrate_entry_fields,
    normalize_entry_category,
    sync_entry_coord_ids,
    sync_entry_coords_from_emperor,
)
from emperor_resolve import (
    align_skeleton_emperors,
    align_event_emperor_coords,
    auto_supplement_emperors_from_skeleton,
    build_emperor_info_index,
    co_segment_peers,
    infer_spindle_emperor,
    pick_emperor_from_text,
    resolve_emperor_label,
    volume_has_junji,
    work_id_from_skeleton,
    work_id_from_volume,
    _sanitized_coord_hints,
)
from shilue_year_resolve import (
    infer_shilue_years,
    is_full_reign_copy,
    is_shilue_year_placeholder,
    emperor_accession_year,
)
from detail_coords import fill_all_detail_coords
from dynasty_resolve import auto_normalize_dynasty_reference, canonicalize_entry_dynasty_coords
from regime_resolve import auto_normalize_reference_coords, canonicalize_entry_regime_coords
from lib_config import (
    LEGACY_CATS,
    LLM_AUTO_FILLED_PRESERVE_KEYS,
    SINGLE_YEAR_CATEGORIES,
    VALID_CATS,
    VALID_PRIORITIES,
    build_dynasty_index,
    build_emperor_index,
    detect_cross_regime_person,
    load_regime_index,
    person_spindle_rationale,
    PERSON_SPINDLE_RATIONALE_MIN_LEN,
    spindle_rationale_prompt,
    validate_entry_coordinates,
    validate_entry_years,
    validate_person_spindle_rationale_batch,
    year_range_label,
)
from category_v3 import SPINDLE_CATEGORIES, OFFICIAL_CATEGORIES
from coordinate_index import build_regime_index, build_dynasty_index_from_json

from coord_attrib_rules import PERSON_COORD_ATTRIB_RULE, SPINDLE_RATIONALE_PROMPT_SUFFIX

SPINDLE_CATEGORIES = SPINDLE_CATEGORIES  # re-export from category_v3

NO_JUNJI_COORD_RULE = (
    PERSON_COORD_ATTRIB_RULE
    + " **不依赖本卷是否出现君王条目**；据史略主题与史学常识判定四级帝王，"
    "一～三级坐标由编排器据帝王.json 自动反推。"
)

# Step4 正式字段（与 check_format --phase final 一致）
STEP4_FORMAL_FIELDS = [
    "优先级",
    "优先级判定理由",
    "史略开始年",
    "史略结束年",
    *COORD_FIELDS,
    *COORD_ID_FIELDS,
]

AUTO_TO_FORMAL = {f: f for f in (*COORD_FIELDS, *COORD_ID_FIELDS)}

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "historiography-pipeline"


def _enforce_lease(json_path: str) -> None:
    sys.path.insert(0, str(PIPELINE_DIR))
    from hist_gates import GateError, enforce_script, gate_fail  # noqa: WPS433

    try:
        enforce_script(json_path)
    except GateError as e:
        gate_fail(str(e))


def find_emperor_match(
    entry: dict,
    emperor_index: Dict[str, dict],
    *,
    work_id: str = "",
) -> Optional[tuple]:
    """分层匹配，返回 (info, confidence)。"""
    name = entry.get("史略名称", "").strip()
    cat = normalize_entry_category(entry.get("史略分类", ""))
    intro = entry.get("史略简介", "")
    text = entry.get("原文字句", "")

    # 事略/典制/士臣/民录：禁止用史略名称 exact 匹配帝王表
    event_like = cat in (SPINDLE_CATEGORIES - {"君王"})

    if not event_like:
        # 0. 别名 / 帝王名字 / 去前缀解析（论著/君王）
        info, method = resolve_emperor_label(
            name,
            work_id=work_id,
            dynasty_hint=(entry.get("二级朝代坐标") or "").strip(),
            regime_hint=(entry.get("三级政权坐标") or "").strip(),
            emperor_index=emperor_index,
        )
        if info:
            return info, method or "resolved"

    # 1. 君王：名称精确匹配帝王表
    if cat == "君王" and name in emperor_index:
        return emperor_index[name], "exact_name"

    # 2. 四级帝王坐标（含别名；须与史略名称不同，避免事略名自指）
    coord = (entry.get("四级帝王坐标") or "").strip()
    if coord and (not event_like or coord != name):
        cinfo, cmethod = resolve_emperor_label(
            coord, work_id=work_id, emperor_index=emperor_index
        )
        if cinfo:
            return cinfo, cmethod or "coord_resolved"

    if event_like:
        d_hint, r_hint = _sanitized_coord_hints(entry, work_id)
        info, method = pick_emperor_from_text(
            f"{intro} {text}",
            emperor_index,
            work_id=work_id,
            dynasty_hint=d_hint,
            regime_hint=r_hint,
        )
        if info:
            return info, method or "text_inferred"
        return None

    # 3. 任意类：名称精确匹配
    if name in emperor_index:
        return emperor_index[name], "exact_name"

    # 4. 去除书名号后精确匹配（论著类）
    clean = name.strip("《》")
    if clean in emperor_index:
        return emperor_index[clean], "exact_name_clean"

    # 5. 简介/原文中出现唯一帝王名
    search_text = f"{intro} {text}"
    hits = []
    for emp_name, info in emperor_index.items():
        if len(emp_name) >= 2 and emp_name in search_text:
            hits.append((emp_name, info))
    if len(hits) == 1:
        return hits[0][1], "text_single_hit"
    if len(hits) > 1:
        return None

    return None


def fill_entries(
    entries: list,
    emperor_index: Dict[str, dict],
    dynasty_index: Dict[str, dict],
    regime_index: Dict[str, dict],
    *,
    work_id: str = "",
    data: Optional[dict] = None,
    no_junji: bool = False,
) -> list:
    for entry in entries:
        migrate_entry_fields(entry)
        prev_auto = entry.get("_auto_filled") or {}
        preserved = {
            k: prev_auto[k]
            for k in LLM_AUTO_FILLED_PRESERVE_KEYS
            if prev_auto.get(k) not in (None, "")
        }
        auto: dict = {}
        cat = normalize_entry_category(entry.get("史略分类", ""))

        match = find_emperor_match(entry, emperor_index, work_id=work_id)
        if match:
            info, confidence = match
            spindle = cat in SPINDLE_CATEGORIES
            if no_junji and spindle:
                auto["match_confidence"] = confidence
                auto["_主轴参考"] = (
                    f"脚本猜测主轴帝王「{info['emperor']}」（{confidence}），"
                    f"请据史略主题确认或修正"
                )
                if info.get("start_year") is not None:
                    auto["帝王开始年"] = info["start_year"]
                if info.get("end_year") is not None:
                    auto["帝王结束年"] = info["end_year"]
            else:
                auto.update(coords_and_ids_from_emperor(info))
                auto["match_confidence"] = confidence
                if info.get("start_year") is not None:
                    auto["帝王开始年"] = info["start_year"]
                if info.get("end_year") is not None:
                    auto["帝王结束年"] = info["end_year"]

                regime = info.get("regime", "")
                if regime and regime in regime_index:
                    ri = regime_index[regime]
                    auto["政权开始年"] = ri.get("start_year")
                    auto["政权结束年"] = ri.get("end_year")

                dynasty = info.get("dynasty", "")
                if dynasty and dynasty in dynasty_index:
                    di = dynasty_index[dynasty]
                    auto["朝代开始年"] = di.get("start_year")
                    auto["朝代结束年"] = di.get("end_year")

        if no_junji and cat in SPINDLE_CATEGORIES and data:
            auto["_坐标规则"] = NO_JUNJI_COORD_RULE
            intro = (entry.get("史略简介") or "").strip()
            if intro:
                auto["_史略主题"] = f"{entry.get('史略名称', '')}：{intro}"
            peers = co_segment_peers(entry, data)
            if peers:
                auto["_共段条目"] = peers
            if not auto.get("_主轴参考"):
                hint, method = infer_spindle_emperor(
                    entry, data, emperor_index, work_id=work_id
                )
                if hint:
                    auto["_主轴参考"] = (
                        f"脚本猜测主轴帝王「{hint['emperor']}」（{method}），"
                        f"请据史略主题确认或修正"
                    )

        if cat == "君王":
            emp_name = (entry.get("史略名称") or "").strip()
            resolved, rmethod = resolve_emperor_label(
                emp_name, work_id=work_id, emperor_index=emperor_index
            )
            if resolved:
                canonical = resolved["emperor"]
                if canonical != emp_name:
                    auto["_君王名提示"] = (
                        f"君王名称「{emp_name}」应改为帝王表标准名「{canonical}」"
                        f"（{rmethod}）"
                    )
                else:
                    auto["_君王名提示"] = f"君王名称须与帝王.json「帝王」一致：{canonical}"
                auto.update(coords_from_emperor(resolved))
            elif emp_name in emperor_index:
                auto.update(coords_from_emperor(emperor_index[emp_name]))
                auto["_君王名提示"] = f"君王名称须与帝王.json「帝王」一致：{emp_name}"
            if auto.get("帝王开始年") is not None:
                auto["_年建议"] = (
                    f"君王 → 即位年={auto.get('帝王开始年')}, "
                    f"退位年={auto.get('帝王结束年')}"
                )

        auto["年规则"] = year_range_label(cat)
        if cat in SINGLE_YEAR_CATEGORIES:
            auto["年规则备注"] = "史略开始年=史略结束年（时间轴单点）"
        elif cat == "事略":
            auto["年规则备注"] = (
                "填事件起止年；禁止与君主在位期完全相同；"
                "史无详年则单点锚定（即位年或原文纪年）"
            )
        elif cat == "蕃祚":
            from collective_volume_subjects import fanzuo_year_fallback_note

            work_title = (data.get("work_title") or data.get("work") or work_id or "").strip()
            volume_name = (data.get("volume") or "").strip() if data else ""
            regime_name = (entry.get("史略名称") or "").strip()
            auto["年规则备注"] = fanzuo_year_fallback_note(
                work_title=work_title,
                volume_name=volume_name,
                regime_name=regime_name,
            )
        elif cat in (SPINDLE_CATEGORIES - {"君王", "蕃祚"}):
            from person_year_fallback import person_year_fallback_note

            auto["年规则备注"] = person_year_fallback_note()

        auto.update(preserved)
        entry["_auto_filled"] = auto
        entry["_needs_llm"] = _needs_for_entry(entry, entries=entries)

    return entries


def _spindle_needs_llm_coords(entry: dict) -> bool:
    """非君王主轴：仅需 LLM 补四级帝王坐标。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in SPINDLE_CATEGORIES:
        return False
    return not (entry.get(FOURTH_EMPIRE_COORD_FIELD) or "").strip()


def _needs_for_entry(entry: dict, *, entries: Optional[list] = None) -> List[str]:
    needs: List[str] = []
    cat = normalize_entry_category(entry.get("史略分类", ""))
    spindle_non_junji = cat in SPINDLE_CATEGORIES
    for key in STEP4_FORMAL_FIELDS:
        if spindle_non_junji and key in (*SCRIPT_COORD_FIELDS, *COORD_ID_FIELDS):
            continue
        val = entry.get(key)
        if val is None or val == "":
            needs.append(key)
    if entries is not None:
        reason = detect_cross_regime_person(entry, entries)
        if reason and len(person_spindle_rationale(entry)) < PERSON_SPINDLE_RATIONALE_MIN_LEN:
            if "_坐标主轴说明" not in needs:
                needs.append("_坐标主轴说明")
            auto = dict(entry.get("_auto_filled") or {})
            auto["_坐标主轴待说明"] = spindle_rationale_prompt(reason)
            entry["_auto_filled"] = auto
        else:
            auto = dict(entry.get("_auto_filled") or {})
            if auto.pop("_坐标主轴待说明", None) is not None or auto:
                entry["_auto_filled"] = auto
            elif "_auto_filled" in entry:
                entry.pop("_auto_filled", None)
    return needs


def refresh_needs_llm(entries: list) -> None:
    for entry in entries:
        needs = _needs_for_entry(entry, entries=entries)
        if needs:
            entry["_needs_llm"] = needs
        else:
            entry.pop("_needs_llm", None)


def entry_missing_fields(entry: dict) -> List[str]:
    migrate_entry_fields(entry)
    missing = []
    for key in STEP4_FORMAL_FIELDS:
        val = entry.get(key)
        if val is None or val == "":
            missing.append(key)
    pri = entry.get("优先级", "")
    if pri and pri not in VALID_PRIORITIES:
        missing.append(f"非法优先级:{pri}")
    cat = normalize_entry_category(entry.get("史略分类", ""))
    raw_cat = (entry.get("史略分类") or "").strip()
    if raw_cat in LEGACY_CATS:
        missing.append("史略分类须为君王/宗戚/宦官/文臣/武将/蕃祚/庶众")
    if cat not in VALID_CATS and cat != "士臣":
        missing.append(f"非法分类:{cat}")
    return missing


def merge_auto_into_formal(entry: dict, *, skip_coord_merge: bool = False) -> None:
    auto = entry.get("_auto_filled") or {}
    for ak, fk in AUTO_TO_FORMAL.items():
        if ak not in auto or auto[ak] in (None, ""):
            continue
        if skip_coord_merge and ak in COORD_FIELDS:
            continue
        # 坐标与坐标 ID 以脚本反推（帝王表）为准，覆盖 LLM 误填
        if ak in COORD_FIELDS or ak in COORD_ID_FIELDS:
            entry[fk] = auto[ak]
        elif not entry.get(fk):
            entry[fk] = auto[ak]
    if normalize_entry_category(entry.get("史略分类", "")) == "君王":
        auto = entry.get("_auto_filled") or {}
        rs, re = auto.get("帝王开始年"), auto.get("帝王结束年")
        if auto.get("_年冲突提示") and rs is not None and re is not None:
            entry["史略开始年"] = rs
            entry["史略结束年"] = re
        else:
            if not entry.get("史略开始年") and rs is not None:
                entry["史略开始年"] = rs
            if not entry.get("史略结束年") and re is not None:
                entry["史略结束年"] = re


def _normalize_single_year_entries(entry: dict) -> None:
    """典制/论著须单年；误填区间时收敛为开始年。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in SINGLE_YEAR_CATEGORIES:
        return
    start = entry.get("史略开始年")
    end = entry.get("史略结束年")
    if start is not None and end is not None and start != end:
        entry["史略结束年"] = start


def _flag_ambiguous_junji_years(entries: list) -> None:
    """
    同政权君王年份完全撞车 → 标 _needs_llm 交 LLM 复核。
    合传卷（陈/杞等）不同政权可同年，不在此列。
    """
    buckets: Dict[Tuple[int, int, str], List[dict]] = {}
    for entry in entries:
        if normalize_entry_category(entry.get("史略分类", "")) != "君王":
            continue
        start, end = entry.get("史略开始年"), entry.get("史略结束年")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        regime = (entry.get("三级政权坐标") or "").strip()
        buckets.setdefault((start, end, regime), []).append(entry)

    for key, group in buckets.items():
        if len(group) < 2:
            continue
        start, end, regime = key
        hint = (
            f"同政权「{regime}」内 {len(group)} 个君王共用 {start}～{end}；"
            f"请据史料区分即位/退位，史无记载则开始年=结束年=即位年"
        )
        for entry in group:
            auto = dict(entry.get("_auto_filled") or {})
            auto["_年冲突提示"] = hint
            entry["_auto_filled"] = auto
            needs = list(entry.get("_needs_llm") or [])
            for field in ("史略开始年", "史略结束年"):
                if field not in needs:
                    needs.append(field)
            entry["_needs_llm"] = needs


def _apply_junji_unknown_reign_fallback(entry: dict) -> None:
    """
    君王史无明确退位年：仅知即位/封国年 → 开始年=结束年（兜底链第一级）。
    触发：简介含始封/封于，且当前为可疑长占位区间（≥30年且同卷多君王共享）。
    """
    if normalize_entry_category(entry.get("史略分类", "")) != "君王":
        return
    intro = entry.get("史略简介", "") or ""
    if not any(k in intro for k in ("始封", "封于", "封之於", "封于")):
        return
    start = entry.get("史略开始年")
    end = entry.get("史略结束年")
    if not isinstance(start, int) or not isinstance(end, int):
        return
    if start == end:
        return
    if end - start < 30:
        return
    entry["史略结束年"] = start
    auto = dict(entry.get("_auto_filled") or {})
    auto["_年兜底"] = f"史无明确退位记载，已按「仅知一年」收敛为 {start}"
    entry["_auto_filled"] = auto


def _clear_shilue_reign_copy_years(
    entry: dict,
    *,
    data: Optional[dict] = None,
    emperor_index: Optional[Dict[str, dict]] = None,
) -> bool:
    """事略/典制年若与卷级君王占位相同 → 清空，待原文锚定。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in ("事略", "典制"):
        return False
    eidx = emperor_index or build_emperor_info_index()
    auto = entry.get("_auto_filled") or {}
    rs, re = auto.get("帝王开始年"), auto.get("帝王结束年")
    start, end = entry.get("史略开始年"), entry.get("史略结束年")
    if not (isinstance(start, int) and isinstance(end, int)):
        return False
    acc, reign_end, _ = emperor_accession_year(entry, eidx)
    rs = rs if rs is not None else acc
    re = re if re is not None else reign_end
    if not is_shilue_year_placeholder(start, end, rs, re, data=data, entry=entry):
        return False
    entry.pop("史略开始年", None)
    entry.pop("史略结束年", None)
    auto = dict(auto)
    auto["_年冲突提示"] = (
        f"事略年({start}～{end})疑似卷级占位，已清空；将据原文纪年或单点锚定重填"
    )
    entry["_auto_filled"] = auto
    return True


def _apply_shilue_year_fallback(
    entry: dict,
    *,
    data: Optional[dict] = None,
    emperor_index: Optional[Dict[str, dict]] = None,
) -> None:
    """事略/典制缺年或卷级占位 → 原文纪年 / 共段君王即位年单点锚定。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in ("事略", "典制"):
        return
    start, end = entry.get("史略开始年"), entry.get("史略结束年")
    eidx = emperor_index or build_emperor_info_index()
    acc, reign_end, _ = emperor_accession_year(entry, eidx)
    if isinstance(start, int) and isinstance(end, int):
        if not is_shilue_year_placeholder(start, end, acc, reign_end, data=data, entry=entry):
            return

    inferred = infer_shilue_years(entry, data=data, emperor_index=emperor_index)
    if not inferred:
        return

    start, end, level, msg = inferred
    eidx = emperor_index or build_emperor_info_index()
    acc, reign_end, emp_name = emperor_accession_year(entry, eidx)

    if is_full_reign_copy(start, end, acc, reign_end):
        start = end = acc
        level = "junji_accession_single_point"
        msg = f"原文跨度等同「{emp_name or '关联帝王'}」在位全期，收敛为即位年单点 {acc}"

    entry["史略开始年"] = start
    entry["史略结束年"] = end
    auto = dict(entry.get("_auto_filled") or {})
    auto["_年兜底"] = msg
    auto["_年兜底级别"] = level
    auto["_年建议"] = f"事略 → {start}～{end}（{msg}）"
    entry["_auto_filled"] = auto


def entry_paragraph_span(entry: dict) -> int:
    """统计 entry.paragraphs 覆盖的段落总数。"""
    total = 0
    for p in entry.get("paragraphs") or []:
        pf = int(p.get("paragraph_from") or 0)
        pt = int(p.get("paragraph_to") or pf)
        if pf > 0 and pt >= pf:
            total += pt - pf + 1
    return total


def infer_junji_priority(entry: dict, *, junji_entries: list) -> Tuple[str, str]:
    """
    君王优先级脚本兜底：按叙事段数推断 P0–P2（与卷001金标口径一致）。
    仅填补缺失项，不覆盖 LLM 已填值。
    """
    span = entry_paragraph_span(entry)
    name = (entry.get("史略名称") or "?").strip()
    spans = [entry_paragraph_span(e) for e in junji_entries]
    max_span = max(spans) if spans else span

    if span >= 10 or (span == max_span and span >= 8):
        return "P0", f"本纪主轴叙事，共{span}段"
    if span >= 2:
        return "P1", f"合传独立块{span}段，篇幅次于卷首主轴"
    return "P2", f"单段记{name}即位或事迹"


def apply_inferred_junji_priorities(entries: list) -> int:
    """君王优先级缺口补全：仅当 LLM/人工未填时，按叙事段数推断 P0–P2。"""
    junji = [
        e
        for e in entries
        if normalize_entry_category(e.get("史略分类", "")) == "君王"
    ]
    if not junji:
        return 0
    filled = 0
    for entry in junji:
        if (entry.get("优先级") or "").strip() in VALID_PRIORITIES:
            continue
        pri, reason = infer_junji_priority(entry, junji_entries=junji)
        entry["优先级"] = pri
        entry["优先级判定理由"] = reason
        filled += 1
    return filled


def prepare_spindle_emperor_for_llm(
    data: dict,
    *,
    work_id: str = "",
    emperor_index: Optional[Dict[str, dict]] = None,
) -> int:
    """
    非君王主轴：清空四级帝王坐标，交 LLM 据史略主题判定（不依赖本卷君王条目）。
    一～三级坐标由 reconcile 据帝王.json 反推，不要求 LLM 填写。
    """
    eidx = emperor_index or build_emperor_info_index()
    flagged = 0
    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        cat = normalize_entry_category(entry.get("史略分类", ""))
        if cat not in SPINDLE_CATEGORIES:
            continue
        fourth = (entry.get(FOURTH_EMPIRE_COORD_FIELD) or "").strip()
        if fourth and fourth in eidx:
            continue
        for field in SCRIPT_COORD_FIELDS:
            entry.pop(field, None)
        for field in COORD_ID_FIELDS[:3]:
            entry.pop(field, None)
        entry.pop(FOURTH_EMPIRE_COORD_FIELD, None)
        entry.pop("帝王ID", None)
        auto = dict(entry.get("_auto_filled") or {})
        for field in (*SCRIPT_COORD_FIELDS, FOURTH_EMPIRE_COORD_FIELD):
            auto.pop(field, None)
        auto["_坐标规则"] = NO_JUNJI_COORD_RULE
        intro = (entry.get("史略简介") or "").strip()
        name = (entry.get("史略名称") or "").strip()
        if intro:
            auto["_史略主题"] = f"{name}：{intro}"
        peers = co_segment_peers(entry, data)
        if peers:
            auto["_共段条目"] = peers
        if not auto.get("_主轴参考"):
            hint, method = infer_spindle_emperor(
                entry, data, eidx, work_id=work_id
            )
            if hint:
                auto["_主轴参考"] = (
                    f"脚本猜测主轴帝王「{hint['emperor']}」（{method}），"
                    f"请据史略主题确认或修正（可推翻，勿依赖本卷君王条目）"
                )
        entry["_auto_filled"] = auto
        needs = list(entry.get("_needs_llm") or [])
        for field in SCRIPT_COORD_FIELDS:
            if field in needs:
                needs.remove(field)
        for field in COORD_ID_FIELDS[:3]:
            if field in needs:
                needs.remove(field)
        if FOURTH_EMPIRE_COORD_FIELD not in needs:
            needs.append(FOURTH_EMPIRE_COORD_FIELD)
        entry["_needs_llm"] = needs
        flagged += 1
    return flagged


def prepare_no_junji_spindle_for_llm(
    data: dict,
    *,
    work_id: str = "",
    emperor_index: Optional[Dict[str, dict]] = None,
) -> int:
    """兼容旧名；行为同 prepare_spindle_emperor_for_llm。"""
    return prepare_spindle_emperor_for_llm(
        data, work_id=work_id, emperor_index=emperor_index
    )


def merge_all_entries(
    entries: list,
    *,
    data: Optional[dict] = None,
    json_path: str = "",
    emperor_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
    work_id: str = "",
) -> None:
    if data:
        n = prepare_spindle_emperor_for_llm(
            data, work_id=work_id, emperor_index=emperor_index
        )
        if n:
            print(
                f"\n  📌 非君王主轴 {n} 条：四级帝王交 LLM 判定"
                f"（一～三级由帝王.json 反推，不依赖本卷君王条目）"
            )
        if emperor_index and dynasty_index and regime_index:
            fill_entries(
                entries,
                emperor_index,
                dynasty_index,
                regime_index,
                work_id=work_id,
                data=data,
                no_junji=True,
            )
    ri = build_regime_index()
    di = build_dynasty_index_from_json()
    for e in entries:
        migrate_entry_fields(e)
        merge_auto_into_formal(e, skip_coord_merge=_spindle_needs_llm_coords(e))
        canonicalize_entry_regime_coords(e, ri)
        canonicalize_entry_dynasty_coords(e, di)
        _normalize_single_year_entries(e)
        _apply_junji_unknown_reign_fallback(e)
        _clear_shilue_reign_copy_years(e, data=data, emperor_index=emperor_index)
        _apply_shilue_year_fallback(
            e,
            data=data,
            emperor_index=emperor_index,
        )
    fill_all_detail_coords(data, work_id=work_id, json_path=json_path or "")
    sync_logs = reconcile_entries_coords_from_emperor(
        entries, emperor_index=emperor_index, regime_index=ri
    )
    if sync_logs:
        print(f"\n  🔗 帝王表坐标链对齐 {len(sync_logs)} 处:")
        for line in sync_logs[:12]:
            print(f"    · {line}")
    id_logs = reconcile_entries_coord_ids(
        entries,
        emperor_index=emperor_index,
        regime_index=ri,
        dynasty_index=di,
    )
    if id_logs:
        print(f"\n  🆔 坐标 ID 补全 {len(id_logs)} 处:")
        for line in id_logs[:12]:
            print(f"    · {line}")
    _flag_ambiguous_junji_years(entries)
    pri_n = apply_inferred_junji_priorities(entries)
    if pri_n:
        print(f"\n  🏷 君王优先级补缺 {pri_n} 条（仅填 LLM 未写的空位）")
    refresh_needs_llm(entries)


def reconcile_entries_coords_from_emperor(
    entries: list,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
) -> List[str]:
    """四级帝王已在帝王表时，以帝王表 SSOT 同步整条坐标链（覆盖 LLM 误填如 秦→战国·秦）。"""
    ei = emperor_index or build_emperor_index()
    ri = regime_index or build_regime_index()
    logs: List[str] = []
    for entry in entries:
        migrate_entry_fields(entry)
        msg = sync_entry_coords_from_emperor(entry, ei, regime_index=ri)
        if msg:
            logs.append(msg)
    return logs


def reconcile_entries_coord_ids(
    entries: list,
    *,
    emperor_index: Optional[Dict[str, dict]] = None,
    regime_index: Optional[Dict[str, dict]] = None,
    dynasty_index: Optional[Dict[str, dict]] = None,
) -> List[str]:
    """为每条史略补全四级坐标 ID（SSOT：帝王.json → 政权/朝代/文明.json）。"""
    ei = emperor_index or build_emperor_index()
    ri = regime_index or build_regime_index()
    di = dynasty_index or build_dynasty_index_from_json()
    logs: List[str] = []
    for entry in entries:
        migrate_entry_fields(entry)
        msg = sync_entry_coord_ids(
            entry, ei, regime_index=ri, dynasty_index=di
        )
        if msg:
            logs.append(msg)
    return logs


def collect_coord_decisions(data: dict) -> dict:
    """收集须人工决策的坐标冲突（四级帝王在表但坐标链与帝王表不一致）。"""
    ei = build_emperor_index()
    ri = build_regime_index()
    items: List[dict] = []
    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        emp = (entry.get("四级帝王坐标") or "").strip()
        if not emp or emp not in ei:
            continue
        mismatched = entry_coords_mismatch_emperor(entry, ei[emp], regime_index=ri)
        if not mismatched:
            continue
        expected = coords_from_emperor(ei[emp], ri)
        current = {f: (entry.get(f) or "").strip() for f in COORD_FIELDS}
        items.append({
            "entry_id": entry.get("史略ID", ""),
            "name": entry.get("史略名称", ""),
            "emperor": emp,
            "mismatched_fields": mismatched,
            "current": current,
            "expected": expected,
        })
    return {
        "kind": "coord_mismatch",
        "volume": data.get("volume", ""),
        "items": items,
        "choices": {
            "emperor-ssot": "采用帝王表坐标（推荐：如 秦 → 战国·秦）",
            "keep-current": "保留当前 skeleton 坐标（需自行改帝王表/政权表后 resume）",
        },
    }


def apply_coord_decision(data: dict, choice: str) -> Tuple[int, List[str]]:
    """应用人工坐标决策；返回 (改动条数, 日志)。"""
    choice = (choice or "").strip().lower()
    logs: List[str] = []
    n = 0
    if choice in ("emperor-ssot", "emperor_ssot", "1", "ssot"):
        for msg in reconcile_entries_coords_from_emperor(data.get("entries", [])):
            logs.append(msg)
            n += 1
        return n, logs
    if choice in ("keep-current", "keep_current", "2", "keep"):
        logs.append("保留当前坐标，未改写 skeleton")
        return 0, logs
    raise ValueError(f"未知决策: {choice}（可用 emperor-ssot / keep-current）")


def verify_step4(data: dict, *, require_clean: bool = False) -> tuple[bool, list[str]]:
    issues: List[str] = []
    emperor_index = build_emperor_index()
    regime_index = load_regime_index()
    dynasty_index = build_dynasty_index()
    for i, entry in enumerate(data.get("entries", []), 1):
        migrate_entry_fields(entry)
        eid = entry.get("史略ID", f"#{i}")
        for m in entry_missing_fields(entry):
            issues.append(f"[{i}/{len(data.get('entries', []))}] {eid} 缺少: {m}")
        if require_clean:
            if "_needs_llm" in entry:
                issues.append(f"[{i}] {eid} 仍含 _needs_llm（应由脚本 finalize 删除）")
            if "_auto_filled" in entry:
                issues.append(f"[{i}] {eid} 仍含 _auto_filled")
        for msg in validate_entry_years(entry):
            issues.append(f"[{i}] {msg}")
        for msg in validate_entry_coordinates(
            entry,
            emperor_index=emperor_index,
            regime_index=regime_index,
            dynasty_index=dynasty_index,
        ):
            issues.append(f"[{i}] {msg}")
    for msg in validate_person_spindle_rationale_batch(data.get("entries", [])):
        issues.append(msg)
    return len(issues) == 0, issues


def finalize_entries(entries: list) -> None:
    """删除 Step4 临时字段；保留考订/主轴等审计用 _auto_filled 子键。"""
    keep_auto = frozenset({
        "_年LLM依据",
        "_坐标主轴说明",
        "年规则",
        "年规则备注",
        # 峰值年审计元数据（Step4d peak_year.py 写入）
        "_峰值LLM依据",
        "_峰值待审",
        "_峰值兜底级别",
        "_峰值人工锁定",
    })
    for entry in entries:
        auto = entry.get("_auto_filled")
        if auto:
            kept = {k: v for k, v in auto.items() if k in keep_auto and v not in (None, "")}
            if kept:
                entry["_auto_filled"] = kept
            else:
                entry.pop("_auto_filled", None)
        else:
            entry.pop("_auto_filled", None)
        entry.pop("_needs_llm", None)


def build_llm_missing_report(data: dict) -> str:
    lines = ["## 待补字段清单（逐条补全后再回复 STEP4_DONE）", ""]
    spindle_entries = [
        e
        for e in data.get("entries", [])
        if normalize_entry_category(e.get("史略分类", "")) in SPINDLE_CATEGORIES
    ]
    if spindle_entries:
        lines.extend([
            "### 坐标补全规则（非君王主轴）",
            "",
            "**你只需填写 `四级帝王坐标`**（须为 `帝王.json` 标准名）。",
            "**不要**填写一～三级坐标——编排器将根据四级帝王从帝王表自动反推。",
            "**不依赖**本卷是否出现对应君王条目；据史略主题与史学常识判定。",
            "",
        ])
    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        missing = entry_missing_fields(entry)
        cat = normalize_entry_category(entry.get("史略分类", "?"))
        auto = entry.get("_auto_filled") or {}
        spindle = cat in SPINDLE_CATEGORIES
        if spindle:
            missing = [
                f
                for f in missing
                if f not in SCRIPT_COORD_FIELDS and f not in COORD_ID_FIELDS[:3]
            ]
            if not (entry.get(FOURTH_EMPIRE_COORD_FIELD) or "").strip():
                if FOURTH_EMPIRE_COORD_FIELD not in missing:
                    missing.append(FOURTH_EMPIRE_COORD_FIELD)
        if not missing:
            continue
        eid = entry.get("史略ID", "?")
        name = entry.get("史略名称", "?")
        lines.append(f"### {eid} {name}（{cat}）")
        lines.append(f"- **年规则**: {year_range_label(cat)}")
        if spindle:
            lines.append(f"- **坐标规则**: {NO_JUNJI_COORD_RULE}")
            lines.append("- **坐标**: 仅填 `四级帝王坐标`；一～三级由脚本反推")
            if auto.get("_史略主题"):
                lines.append(f"- **史略主题**: {auto['_史略主题']}")
            elif entry.get("史略简介"):
                lines.append(
                    f"- **史略主题**: {name}：{entry.get('史略简介', '')}"
                )
            if auto.get("_共段条目"):
                peers = "、".join(
                    f"{p['name']}({p['category']})" for p in auto["_共段条目"]
                )
                lines.append(f"- **共段条目**: {peers}")
            if auto.get("_主轴参考"):
                lines.append(f"- **参考（可推翻）**: {auto['_主轴参考']}")
        elif cat == "君王":
            lines.append(
                "- **坐标**: 君王条目由帝王表对齐；补优先级与年份"
            )
        if auto.get("年规则备注"):
            lines.append(f"- **注意**: {auto['年规则备注']}")
        if auto.get("_年兜底"):
            lines.append(f"- **年兜底**: {auto['_年兜底']}")
        if auto.get("_年建议"):
            lines.append(f"- {auto['_年建议']}")
        if auto.get("_年冲突提示"):
            lines.append(f"- ⚠️ {auto['_年冲突提示']}")
        if auto.get("_坐标主轴待说明"):
            lines.append(f"- **跨时期主轴**: {auto['_坐标主轴待说明']}")
            lines.append(
                "- 须在 `_auto_filled._坐标主轴说明` 写 1～2 句（见 reference/跨时期人物坐标.md）"
            )
        elif auto.get("_坐标主轴说明"):
            lines.append(f"- **主轴说明**: {auto['_坐标主轴说明']}")
        lines.append(f"- 仍缺: {', '.join(missing)}")
        if auto:
            lines.append(f"- _auto_filled 可参考: {json.dumps(auto, ensure_ascii=False)}")
        if cat == "君王" and auto.get("_年建议"):
            lines.append(f"- {auto['_年建议']}")
        if cat == "君王" and auto.get("_君王名提示"):
            lines.append(f"- {auto['_君王名提示']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 4: 字段补全辅助")
    parser.add_argument("json_path", help="通过 Step 2+3 的骨架 JSON")
    parser.add_argument("--output", "-o", default=None, help="输出路径（默认覆盖原文件）")
    parser.add_argument("--merge-auto", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument(
        "--refresh-needs",
        action="store_true",
        help="仅刷新 _needs_llm（不重建 _auto_filled，保留 LLM 考订字段）",
    )
    parser.add_argument("--report-missing", action="store_true")
    parser.add_argument(
        "--align-emperors",
        action="store_true",
        help="先按帝王表标准名对齐君王（刘邦→汉高祖等）",
    )
    parser.add_argument(
        "--no-auto-supplement",
        action="store_true",
        help="禁用从 skeleton 自动补录帝王.json",
    )
    parser.add_argument(
        "--sync-coord-ids",
        action="store_true",
        help="仅补全四级坐标 ID（文明ID/朝代ID/政权ID/帝王ID）",
    )
    args = parser.parse_args()

    if not os.path.exists(args.json_path):
        print(f"❌ 文件不存在: {args.json_path}")
        sys.exit(1)

    if not args.report_missing and not args.sync_coord_ids:
        _enforce_lease(args.json_path)

    out_path = args.output or args.json_path

    print("📖 加载坐标索引 (reference/帝王.json 等)...")
    emperor_index = build_emperor_info_index()
    dynasty_index = build_dynasty_index()
    regime_index = load_regime_index()
    print(
        f"   帝王 {len(emperor_index)} | 政权 {len(regime_index)} | "
        f"朝代 {len(dynasty_index)}"
    )

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    vol = data.get("volume", "未知卷")
    work_id = work_id_from_skeleton(data, args.json_path)
    print(f"\n🔧 字段补全: {vol} ({len(entries)} 条目)")

    if args.sync_coord_ids:
        di = build_dynasty_index_from_json()
        ri = build_regime_index()
        ei = build_emperor_index()
        for e in entries:
            migrate_entry_fields(e)
        logs = reconcile_entries_coord_ids(
            entries, emperor_index=ei, regime_index=ri, dynasty_index=di
        )
        print(f"  🆔 坐标 ID 补全 {len(logs)} 处")
        for line in logs[:8]:
            print(f"    · {line}")
        data["entries"] = entries
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"✅ 已写回: {out_path}")
        sys.exit(0)

    run_fill = not args.report_missing and not args.finalize
    if not args.verify or args.merge_auto:
        run_fill = run_fill or args.merge_auto

    if run_fill and not args.no_auto_supplement:
        added, patched, sup_logs = auto_supplement_emperors_from_skeleton(data)
        emp_reg, reg_reg, sk_reg, reg_logs = auto_normalize_reference_coords(data)
        dyn_emp, dyn_add, sk_dyn, dyn_logs = auto_normalize_dynasty_reference(data)
        if sup_logs or reg_logs or dyn_logs:
            print(f"\n  📚 帝王表自动补全: 新增 {added}，修补 {patched}")
            for line in sup_logs[:8]:
                print(f"    · {line}")
            if reg_logs:
                print(
                    f"  🏛 政权对齐: 帝王表 {emp_reg} 处，"
                    f"政权.json 补录 {reg_reg}，skeleton {sk_reg} 处"
                )
                for line in reg_logs[:8]:
                    print(f"    · {line}")
            if dyn_logs:
                print(
                    f"  📜 朝代对齐: 帝王表 {dyn_emp} 处，"
                    f"朝代.json 补录 {dyn_add}，skeleton {sk_dyn} 处"
                )
                for line in dyn_logs[:8]:
                    print(f"    · {line}")
        emperor_index = build_emperor_info_index()
        dynasty_index = build_dynasty_index()
        regime_index = load_regime_index()

    if args.align_emperors or args.merge_auto:
        data, align_changes = align_skeleton_emperors(data, emperor_index=emperor_index)
        entries = data.get("entries", [])
        if align_changes:
            print(f"\n  👑 帝王名对齐 {len(align_changes)} 处:")
            for c in align_changes[:10]:
                print(f"    · {c}")

    if args.report_missing:
        print(build_llm_missing_report(data))
        sys.exit(0)

    if args.refresh_needs:
        refresh_needs_llm(entries)
        data["entries"] = entries
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("✅ 已刷新 _needs_llm 并写回（未重建 _auto_filled）")
        sys.exit(0)

    if args.finalize:
        ok, issues = verify_step4(data, require_clean=False)
        if not ok:
            print("❌ Step4 finalize 前校验失败:")
            for line in issues[:30]:
                print(f"  - {line}")
            sys.exit(1)
        finalize_entries(entries)
        data["entries"] = entries
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ Step4 finalize：已删除临时字段并写回")
        sys.exit(0)

    if args.verify and not args.merge_auto:
        ok, issues = verify_step4(data, require_clean=args.require_clean)
        if not ok:
            print("❌ Step4 字段校验失败:")
            for line in issues[:30]:
                print(f"  - {line}")
            sys.exit(1)
        print("✅ Step4 字段校验通过")
        sys.exit(0)

    if args.merge_auto:
        merge_all_entries(
            entries,
            data=data,
            json_path=args.json_path,
            emperor_index=emperor_index,
            dynasty_index=dynasty_index,
            regime_index=regime_index,
            work_id=work_id,
        )
    else:
        entries = fill_entries(
            entries,
            emperor_index,
            dynasty_index,
            regime_index,
            work_id=work_id,
            data=data,
            no_junji=not volume_has_junji(data),
        )

    need_attention = [e for e in entries if e.get("_needs_llm")]
    if need_attention:
        print("\n  📋 以下条目仍需 LLM 补全:")
        for e in need_attention:
            print(f"    - [{e['史略ID']}] {e['史略名称']} 缺: {e.get('_needs_llm', [])}")

    data["entries"] = entries
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入: {out_path}")
    if not args.merge_auto:
        print("\n⚠️  下一步: fill_fields.py --merge-auto → LLM 补缺 → --verify → --finalize")


if __name__ == "__main__":
    main()
