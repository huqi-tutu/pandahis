#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补全 V2/线上索引中缺少年份与四级坐标 ID 的条目，写回 V2 全局索引并重建 online。

用法：
  python3 scripts/backfill_incomplete_entries.py
  python3 scripts/backfill_incomplete_entries.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANN = ROOT / "tools/openclaw-historiography/historiography-annotate"
SCR = ROOT / "scripts"
V2_INDEX = ROOT / "data" / "10新标注条目" / "史略索引_史记汉书.json"
V2_INDEX_03_04 = ROOT / "data" / "10新标注条目" / "史略索引_03至04.json"
EMPEROR_JSON = ROOT / "data" / "01历史坐标数据" / "帝王.json"

sys.path.insert(0, str(ANN))
sys.path.insert(0, str(SCR))

from fill_fields import (  # noqa: E402
    build_emperor_index,
    migrate_entry_fields,
    reconcile_entries_coord_ids,
    sync_entry_coords_from_emperor,
)
from coordinate_index import build_regime_index, coords_and_ids_from_emperor  # noqa: E402
from person_year_fallback import (  # noqa: E402
    apply_person_year_fallback,
    entry_has_complete_years,
    write_fallback_years_to_entry,
)
from emperor_resolve import pick_emperor_from_text  # noqa: E402
from emperor_year_align import junji_reign_years, load_emperor_rows, parse_emperor_year  # noqa: E402
from shiji_person_fallback import lookup_person_patch, resolve_person_fallback  # noqa: E402
from category_v3 import normalize_entry_category  # noqa: E402

# 扩展：按 paragraphs.source_entry_id 补年（合并 apply_llm_year_fixes_73 与汉书条目）
SOURCE_YEAR_FIXES: dict[str, tuple[int, int, str]] = {
    "SHIJI_055_01": (-250, -186, "张良生卒约前250–前186"),
    "SHIJI_054_01": (-190, -190, "曹参卒年单点（峰值年）"),
    "SHIJI_053_01": (-210, -193, "萧何生卒主流"),
    "SHIJI_056_01": (-250, -178, "陈平生卒主流"),
    "SHIJI_057_01": (-242, -169, "周勃生卒主流"),
    "SHIJI_052_04": (-180, -157, "刘将闾封齐孝王，文帝间"),
    "SHIJI_052_05": (-157, -141, "刘次景封济北王，景帝间"),
    "SHIJI_034_01": (-1046, -1043, "召公奭辅周初"),
    "SHIJI_038_04": (-1092, -1076, "微子启商末"),
    "SHIJI_077_01": (-276, -243, "信陵君魏无忌活跃期"),
    "SHIJI_129_04": (-180, -100, "任氏景武间巨商"),
    "SHIJI_128_01": (-180, -120, "卫平景武间"),
    "SHIJI_063_02": (-342, -301, "庄子与齐宣王同时代"),
    "SHIJI_041_01": (-496, -448, "范蠡事越"),
    "SHIJI_074_02": (-305, -240, "邹衍生卒约"),
    "SHIJI_045_01": (-576, -576, "韩厥晋景公时"),
    "SHIJI_057_02": (-180, -157, "周亚夫文帝景帝间"),
    "SHIJI_065_02": (-380, -316, "孙膑战国齐将"),
    "SHIJI_081_02": (-229, -229, "李牧单点（赵将）"),
    "SHIJI_081_04": (-265, -260, "赵奢活跃赵武灵王惠文王间"),
    "SHIJI_093_03": (-202, -195, "陈豨汉初反"),
    "SHIJI_039_01": (-1042, -1040, "唐叔虞封晋"),
    "SHIJI_043_04": (-298, -266, "赵惠文王在位"),
    "SHIJI_042_05": (-529, -514, "郑定公在位"),
    "SHIJI_046_02": (-374, -357, "齐桓公午在位"),
    "HANSHU_048_03": (-194, -180, "刘友赵幽王，惠帝至吕后间"),
    "HANSHU_048_04": (-194, -181, "刘恢赵共王"),
    "HANSHU_113_05": (-7, -1, "孝哀丁姬，哀帝后"),
    "HANSHU_074_05": (-74, -74, "昌邑王刘贺在位27日"),
    "HANSHU_046_02": (-178, -154, "楚王刘戊景帝吴楚之乱"),
    "HANSHU_046_03": (-77, -8, "刘向成哀间"),
    "HANSHU_046_04": (-53, 23, "刘歆新莽间"),
    "HANSHU_078_04": (-33, 33, "王䜣元帝时外戚"),
    "HANSHU_104_02": (-120, -99, "田仁"),
    "HANSHU_105_04": (-180, -120, "王孟"),
    "HANSHU_104_05": (-180, -120, "罗裒"),
    "HANSHU_105_05": (-180, -120, "薛况"),
    "HANSHU_104_04": (-180, -100, "蜀卓氏"),
    "HANSHU_109_02": (-203, -111, "南越/两粤政权跨度"),
    "HANSHU_110_01": (-138, -60, "西域诸国叙事：张骞至宣帝间"),
}

# 四级帝王锚点（source_entry_id 或 GLBL）
PATRON_BY_SOURCE: dict[str, str] = {
    "HANSHU_048_03": "吕太后",
    "HANSHU_048_04": "吕太后",
    "HANSHU_113_05": "汉哀帝",
    "HANSHU_074_05": "汉昭帝",
    "HANSHU_046_02": "汉景帝",
    "HANSHU_046_03": "汉成帝",
    "HANSHU_046_04": "王莽",
    "HANSHU_109_02": "汉武帝",
    "HANSHU_110_01": "汉武帝",
    "SHIJI_065_02": "吴王阖闾",
    "SHIJI_081_02": "赵惠文王",
    "SHIJI_081_04": "赵惠文王",
    "SHIJI_074_02": "齐宣王",
    "SHIJI_104_02": "汉武帝",
    "SHIJI_129_04": "汉武帝",
    "SHIJI_128_01": "汉武帝",
}

WORK_DYNASTY_HINT: dict[str, str] = {
    "03后汉书": "东汉",
    "04三国志": "三国",
}

HOUHANSHU_COORD_DEFAULTS: dict[str, str] = {
    "文明ID": "HX",
    "朝代ID": "CD_HX_DONGHAN",
    "一级文明坐标": "华夏",
    "二级朝代坐标": "东汉",
    "政权ID": "ZQ_HX_DONGHAN_DONGHAN",
    "三级政权坐标": "东汉",
}

SANGUO_COORD_DEFAULTS: dict[str, str] = {
    "文明ID": "HX",
    "朝代ID": "CD_HX_SANGUO",
    "一级文明坐标": "华夏",
    "二级朝代坐标": "三国",
}

# 03/04 宗戚·蕃祚：卷名 / 名号前缀 → 挂靠帝王（标准名）
VOLUME_PATRON_RULES: tuple[tuple[str, str, str], ...] = (
    ("03后汉书", "章帝八王", "汉章帝"),
    ("03后汉书", "孝明八王", "汉明帝"),
    ("03后汉书", "光武十王", "汉光武帝"),
    ("03后汉书", "宗室四王", "汉光武帝"),
    ("04三国志", "二主妃子", "汉昭烈帝"),
    ("04三国志", "武文世王公", "魏武帝"),
    ("04三国志", "任城陈萧王", "魏武帝"),
    ("04三国志", "吴主五子", "吴大帝"),
    ("04三国志", "宗室传", "吴大帝"),
    ("04三国志", "诸葛滕二孙濮阳", "吴大帝"),
    ("04三国志", "刘二牧", "汉灵帝"),
)

QUEEN_PREFIX_PATRON: tuple[tuple[str, str], ...] = (
    ("先主", "汉昭烈帝"),
    ("光武", "汉光武帝"),
    ("光烈", "汉光武帝"),
    ("明德", "汉明帝"),
    ("章德", "汉章帝"),
    ("和熹", "汉和帝"),
    ("安思", "汉安帝"),
    ("顺烈", "汉顺帝"),
    ("灵思", "汉灵帝"),
    ("文德", "魏文帝"),
    ("文昭", "魏文帝"),
    ("明元", "魏明帝"),
    ("明悼", "魏明帝"),
    ("武宣", "魏武帝"),
)

ENTRY_PATRON_BY_EID: dict[str, str] = {
    "GLBL_01147": "汉灵帝",
    "GLBL_01160": "汉灵帝",
    "GLBL_01162": "汉灵帝",
    "GLBL_01173": "汉灵帝",
    "GLBL_01200": "汉桓帝",
    "GLBL_01201": "汉顺帝",
    "GLBL_01202": "汉光武帝",
    "GLBL_01203": "汉章帝",
    "GLBL_01204": "汉明帝",
    "GLBL_01205": "汉和帝",
    "GLBL_01208": "汉桓帝",
    "GLBL_01210": "汉光武帝",
    "GLBL_01211": "汉明帝",
}

PATRON_CANONICAL: dict[str, str] = {
    "汉昭烈帝": "蜀昭烈帝",
    "魏武帝": "曹操",
}

WRONG_PATRONS_DONGHAN = frozenset({"吴乌程侯", "曹操", "蜀昭烈帝", "吴大帝"})

DONGHAN_VOLUME_PATRON: tuple[tuple[str, str], ...] = (
    ("宦者列传", "汉灵帝"),
    ("皇后纪", "汉光武帝"),
    ("光武十王", "汉光武帝"),
    ("孝明八王", "汉明帝"),
    ("章帝八王", "汉章帝"),
    ("宗室四王", "汉光武帝"),
)

DONGHAN_CATEGORY_PATRON: dict[str, str] = {
    "宦官": "汉灵帝",
}


def _resolve_patron_name(patron: str, ei: dict) -> str:
    """将史略惯用帝王名映射为帝王索引标准名。"""
    name = PATRON_CANONICAL.get(str(patron or "").strip(), str(patron or "").strip())
    return name if name in ei else ""


def _build_donghan_era_patron(em_rows: list[dict]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for row in em_rows:
        if str(row.get("朝代") or "").strip() != "东汉":
            continue
        emperor = str(row.get("帝王名称") or "").strip()
        eras = str(row.get("年号") or "").strip()
        if not emperor or not eras or eras == "-":
            continue
        for era in re.split(r"[/、，,\s]+", eras):
            era = era.strip()
            if era and era != "-":
                out.append((era, emperor))
    out.sort(key=lambda x: -len(x[0]))
    return out


def _infer_donghan_patron(
    entry: dict,
    *,
    ei: dict,
    era_patrons: list[tuple[str, str]],
) -> str:
    """后汉书人物：年号/卷名/分类 → 挂靠东汉帝王。"""
    patron = _resolve_patron_name(str(entry.get("四级帝王坐标") or "").strip(), ei)
    if patron and patron not in WRONG_PATRONS_DONGHAN and _emperor_in_dynasty(ei, patron, "东汉"):
        return patron

    rule_patron = _infer_patron_from_rules(entry)
    if rule_patron and _emperor_in_dynasty(ei, _resolve_patron_name(rule_patron, ei) or rule_patron, "东汉"):
        return _resolve_patron_name(rule_patron, ei) or rule_patron

    vol = _volume_name(entry)
    for vol_key, p in DONGHAN_VOLUME_PATRON:
        if vol_key in vol:
            resolved = _resolve_patron_name(p, ei)
            if resolved:
                return resolved

    cat = normalize_entry_category(entry.get("史略分类", ""))
    cat_patron = DONGHAN_CATEGORY_PATRON.get(cat)
    if cat_patron:
        resolved = _resolve_patron_name(cat_patron, ei)
        if resolved:
            return resolved

    text = f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    for era, p in era_patrons:
        if era in text:
            resolved = _resolve_patron_name(p, ei)
            if resolved:
                return resolved

    info, _ = pick_emperor_from_text(text, ei, work_id="03后汉书", dynasty_hint="东汉")
    if info:
        p = str(info.get("emperor") or info.get("帝王名称") or "").strip()
        resolved = _resolve_patron_name(p, ei)
        if resolved and _emperor_in_dynasty(ei, resolved, "东汉"):
            return resolved

    return "汉光武帝"


def _sync_full_coords_from_patron(entry: dict, *, ei: dict, ri: dict) -> None:
    """以四级帝王为 SSOT，同步中文坐标 + 四级 ID（避免只 sync ID 造成分裂）。"""
    patron = _resolve_patron_name(str(entry.get("四级帝王坐标") or "").strip(), ei)
    if not patron:
        return
    entry["四级帝王坐标"] = patron
    sync_entry_coords_from_emperor(entry, ei, regime_index=ri)


def _coord_chain_mismatch(entry: dict, *, work: str, ei: dict) -> bool:
    hint = WORK_DYNASTY_HINT.get(work)
    if not hint:
        return False
    expected_dyn_id = (
        HOUHANSHU_COORD_DEFAULTS["朝代ID"]
        if work == "03后汉书"
        else SANGUO_COORD_DEFAULTS["朝代ID"]
    )
    if str(entry.get("朝代ID") or "").strip() != expected_dyn_id:
        return True
    if str(entry.get("二级朝代坐标") or "").strip() != hint:
        return True
    if work != "03后汉书":
        return False
    patron = _resolve_patron_name(str(entry.get("四级帝王坐标") or "").strip(), ei)
    if patron in WRONG_PATRONS_DONGHAN:
        return True
    if patron and not _emperor_in_dynasty(ei, patron, hint):
        return True
    return False


def _years_poisoned_by_wrong_patron(entry: dict) -> bool:
    """误挂后 person_year_fallback 常产出帝王在位年当生卒。"""
    sy = entry.get("史略开始年")
    ey = entry.get("史略结束年")
    patron = str(entry.get("四级帝王坐标") or "").strip()
    if patron in WRONG_PATRONS_DONGHAN and sy == 264 and ey == 264:
        return True
    if patron in STICKY_WRONG_SANGUO_PATRONS and sy == 264 and ey == 280:
        return True
    return False


FANZUO_0304_META: dict[str, dict] = {
    "东夷": {
        "start": 57,
        "end": 220,
        "patron": "汉光武帝",
        "note": "后汉东夷朝贡叙事，以光武重开朝贡为起点，至东汉末",
    },
    "乌丸": {
        "start": 190,
        "end": 240,
        "patron": "魏武帝",
        "note": "曹魏征服乌桓、融合期（官渡后至魏末）",
    },
    "乌桓": {
        "start": 25,
        "end": 207,
        "patron": "汉光武帝",
        "note": "乌桓附汉至袁绍势力覆灭",
    },
    "南匈奴": {
        "start": 48,
        "end": 216,
        "patron": "汉光武帝",
        "note": "南匈奴附汉至东汉末单于入朝体系",
    },
    "南蛮": {
        "start": 25,
        "end": 220,
        "patron": "汉光武帝",
        "note": "东汉南疆蛮族总体叙事跨度",
    },
    "西南夷": {
        "start": 25,
        "end": 220,
        "patron": "汉光武帝",
        "note": "东汉西南夷诸部叙事跨度",
    },
    "西羌": {
        "start": 107,
        "end": 184,
        "patron": "汉安帝",
        "note": "东汉羌乱主期（永初至汉末）",
    },
    "鲜卑": {
        "start": 48,
        "end": 235,
        "patron": "汉和帝",
        "note": "鲜卑崛起与东汉北疆互动期",
    },
}


def _volume_name(entry: dict) -> str:
    for key in ("主要史料出处",):
        m = re.search(r"卷\d+·([^》]+)", str(entry.get(key) or ""))
        if m:
            return m.group(1).strip()
    for p in entry.get("paragraphs") or []:
        vol = str(p.get("volume") or "").strip()
        if vol:
            return vol
    return ""


def _infer_patron_from_rules(entry: dict) -> str:
    eid = str(entry.get("史略ID") or "").strip()
    if eid in ENTRY_PATRON_BY_EID:
        return ENTRY_PATRON_BY_EID[eid]

    name = str(entry.get("史略名称") or "").strip()
    cat = normalize_entry_category(entry.get("史略分类", ""))

    if cat == "蕃祚" and name in FANZUO_0304_META:
        return str(FANZUO_0304_META[name]["patron"])

    for prefix, patron in QUEEN_PREFIX_PATRON:
        if name.startswith(prefix):
            return patron

    work = _work_id(entry)
    vol = _volume_name(entry)
    for rule_work, vol_key, patron in VOLUME_PATRON_RULES:
        if work == rule_work and vol_key in vol:
            return patron

    if cat == "宗戚" and name.startswith("刘") and work == "04三国志":
        if "二主妃子" in vol or name in {"刘永", "刘理", "刘璿"}:
            return "汉昭烈帝"

    if cat == "宗戚" and name.startswith("曹"):
        return "魏武帝"
    if cat == "宗戚" and name.startswith("孙"):
        return "吴大帝"

    return ""


def _apply_fanzuo_years(entry: dict) -> bool:
    name = str(entry.get("史略名称") or "").strip()
    meta = FANZUO_0304_META.get(name)
    if not meta:
        return False
    entry["史略开始年"] = int(meta["start"])
    entry["史略结束年"] = int(meta["end"])
    af = dict(entry.get("_auto_filled") or {})
    af["_年兜底级别"] = "蕃祚政权表"
    af["_年LLM依据"] = str(meta["note"])
    entry["_auto_filled"] = af
    return True


def _emperor_in_dynasty(ei: dict, emperor_name: str, dynasty_hint: str) -> bool:
    info = ei.get(str(emperor_name or "").strip())
    if not info:
        return False
    return str(info.get("dynasty") or info.get("朝代") or "").strip() == dynasty_hint


def _enforce_work_dynasty_coords(
    entry: dict,
    *,
    ei: dict,
    ri: dict,
    em_rows: list[dict],
    era_patrons: list[tuple[str, str]] | None = None,
) -> dict:
    """按母本著作锁定朝代坐标，避免后汉书条目被误挂到三国/新莽等。"""
    work = _work_id(entry)
    dynasty_hint = WORK_DYNASTY_HINT.get(work)
    if not dynasty_hint:
        return entry

    if era_patrons is None:
        era_patrons = _build_donghan_era_patron(em_rows)

    out = entry
    if work == "03后汉书":
        out.update(HOUHANSHU_COORD_DEFAULTS)
    elif work == "04三国志":
        out.update(SANGUO_COORD_DEFAULTS)

    cat = normalize_entry_category(out.get("史略分类", ""))
    name = str(out.get("史略名称") or "").strip()

    if cat == "君王" and name in ei and _emperor_in_dynasty(ei, name, dynasty_hint):
        _apply_coords_from_patron(out, name, ei, ri)
        row = next((r for r in em_rows if r.get("帝王名称") == name), None)
        if row:
            rs, re = junji_reign_years(row)
            if rs is not None:
                out["史略开始年"] = rs
            if re is not None:
                out["史略结束年"] = re
    elif cat == "诸侯" and dynasty_hint == "东汉":
        _apply_zhuhou(out, ei, ri, em_rows)
    elif cat == "蕃祚":
        rule_patron = _infer_patron_from_rules(out)
        if rule_patron:
            _apply_coords_from_patron(out, rule_patron, ei, ri)
        _apply_fanzuo_years(out)
    elif cat == "宗戚":
        patron = str(out.get("四级帝王坐标") or "").strip()
        if not patron or not _emperor_in_dynasty(ei, patron, dynasty_hint):
            rule_patron = _infer_patron_from_rules(out)
            if rule_patron:
                patron = rule_patron
                _apply_coords_from_patron(out, patron, ei, ri)
        if not str(out.get("四级帝王坐标") or "").strip():
            text = f"{out.get('史略简介', '')} {out.get('原文字句', '')}"
            info, _ = pick_emperor_from_text(
                text,
                ei,
                work_id=work,
                dynasty_hint=dynasty_hint,
            )
            if info:
                patron = str(info.get("emperor") or info.get("帝王名称") or "").strip()
                if patron:
                    _apply_coords_from_patron(out, patron, ei, ri)
    else:
        patron = str(out.get("四级帝王坐标") or "").strip()
        if work == "03后汉书" and (
            not patron or not _emperor_in_dynasty(ei, patron, dynasty_hint)
        ):
            new_patron = _infer_donghan_patron(out, ei=ei, era_patrons=era_patrons)
            _apply_coords_from_patron(out, new_patron, ei, ri)
        elif work == "04三国志" and (
            not patron or not _emperor_in_dynasty(ei, patron, dynasty_hint)
        ):
            new_patron = _infer_sanguo_patron(out, ei=ei)
            _apply_coords_from_patron(out, new_patron, ei, ri)
        elif not patron or not _emperor_in_dynasty(ei, patron, dynasty_hint):
            text = f"{out.get('史略简介', '')} {out.get('原文字句', '')}"
            info, _ = pick_emperor_from_text(
                text,
                ei,
                work_id=work,
                dynasty_hint=dynasty_hint,
            )
            if info:
                patron = str(info.get("emperor") or info.get("帝王名称") or "").strip()
                if patron:
                    _apply_coords_from_patron(out, patron, ei, ri)

    # 全链同步：中文坐标 + ID 均以四级帝王为准，禁止 reconcile 只改 ID
    _sync_full_coords_from_patron(out, ei=ei, ri=ri)

    if work == "03后汉书" and str(out.get("朝代ID") or "").strip() != HOUHANSHU_COORD_DEFAULTS["朝代ID"]:
        new_patron = _infer_donghan_patron(out, ei=ei, era_patrons=era_patrons)
        _apply_coords_from_patron(out, new_patron, ei, ri)
        _sync_full_coords_from_patron(out, ei=ei, ri=ri)
    elif work == "04三国志" and str(out.get("朝代ID") or "").strip() != SANGUO_COORD_DEFAULTS["朝代ID"]:
        new_patron = _infer_sanguo_patron(out, ei=ei)
        _apply_coords_from_patron(out, new_patron, ei, ri)
        _sync_full_coords_from_patron(out, ei=ei, ri=ri)

    if work == "03后汉书" and out.get("史略开始年") is not None:
        try:
            if int(out["史略开始年"]) >= 220:
                out["史略开始年"] = None
                out["史略结束年"] = None
        except (TypeError, ValueError):
            pass

    if not entry_has_complete_years(out):
        emp = ei.get(str(out.get("四级帝王坐标") or ""))
        sy, ey, level, note = apply_person_year_fallback(out, emperor_info=emp)
        if sy is not None:
            write_fallback_years_to_entry(out, sy, ey, level, note)

    if out.get("史略开始年") is None and out.get("峰值年") is not None:
        p = int(out["峰值年"])
        out["史略开始年"] = p
        out["史略结束年"] = p

    return out


COORD_KEYS = ("文明ID", "朝代ID", "政权ID", "帝王ID")


def _source_entry_id(entry: dict) -> str:
    for p in entry.get("paragraphs") or []:
        sid = str(p.get("source_entry_id") or "").strip()
        if sid:
            return sid
    return ""


def _work_id(entry: dict) -> str:
    for p in entry.get("paragraphs") or []:
        if p.get("work"):
            return str(p["work"])
    src = str(entry.get("主要史料出处") or "")
    mother = str(entry.get("母本著作") or "")
    for hint in (mother, src):
        if "03后汉书" in hint or "后汉书" in hint:
            return "03后汉书"
        if "04三国志" in hint or "三国志" in hint:
            return "04三国志"
    if "汉书" in src:
        return "02汉书"
    if "史记" in src:
        return "01史记"
    return ""


def _core_person_name(name: str) -> str:
    name = (name or "").strip()
    for prefix in (
        "留侯", "平阳侯", "酂侯", "户牖侯", "绛侯",
        "昌邑王", "楚王", "赵幽王", "赵共王",
    ):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _entry_incomplete(entry: dict) -> bool:
    sy = entry.get("史略开始年")
    peak = entry.get("峰值年")
    if sy is None and peak is None:
        return True
    return any(not str(entry.get(k) or "").strip() for k in COORD_KEYS)


def _apply_coords_from_patron(entry: dict, patron: str, ei: dict, ri: dict) -> None:
    resolved = _resolve_patron_name(patron, ei)
    if not resolved:
        return
    info = ei[resolved]
    entry.update(coords_and_ids_from_emperor(info, ri))
    entry["四级帝王坐标"] = resolved


def _apply_zhuhou(entry: dict, ei: dict, ri: dict, em_rows: list[dict]) -> dict:
    name = str(entry.get("史略名称") or "").strip()
    if name in ei:
        _apply_coords_from_patron(entry, name, ei, ri)
        row = next((r for r in em_rows if r.get("帝王名称") == name), None)
        if row:
            rs, re = junji_reign_years(row)
            if rs is not None:
                entry["史略开始年"] = rs
            if re is not None:
                entry["史略结束年"] = re
    return entry


def _apply_years_from_source(entry: dict) -> bool:
    sid = _source_entry_id(entry)
    fix = SOURCE_YEAR_FIXES.get(sid)
    if not fix:
        return False
    start, end, note = fix
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    af = dict(entry.get("_auto_filled") or {})
    af["_年兜底级别"] = "补全脚本"
    af["_年LLM依据"] = note
    entry["_auto_filled"] = af
    return True


def backfill_entry(entry: dict, *, all_entries: list[dict], ei: dict, ri: dict, em_rows: list[dict]) -> tuple[dict, bool]:
    out = deepcopy(entry)
    if not _entry_incomplete(out):
        return out, False

    migrate_entry_fields(out)
    changed = True
    cat = normalize_entry_category(out.get("史略分类", ""))
    sid = _source_entry_id(out)

    _apply_years_from_source(out)

    if cat in {"宗戚", "蕃祚"}:
        rule_patron = _infer_patron_from_rules(out)
        if rule_patron:
            _apply_coords_from_patron(out, rule_patron, ei, ri)
        if cat == "蕃祚":
            _apply_fanzuo_years(out)

    if cat == "诸侯":
        _apply_zhuhou(out, ei, ri, em_rows)
        return out, changed

    if cat == "君王":
        name = str(out.get("史略名称") or "").strip()
        if name in ei:
            _apply_coords_from_patron(out, name, ei, ri)
        row = next((r for r in em_rows if r.get("帝王名称") == name), None)
        if row:
            rs, re = junji_reign_years(row)
            if rs is not None:
                out["史略开始年"] = rs
            if re is not None:
                out["史略结束年"] = re
        reconcile_entries_coord_ids([out])
        return out, changed

    # 坐标：patch / source patron / 文本推断
    patron = PATRON_BY_SOURCE.get(sid)
    if not patron:
        patch = lookup_person_patch(_core_person_name(str(out.get("史略名称") or "")))
        if patch:
            patron = patch["patron"]
    if not patron:
        wid = _work_id(out)
        text = f"{out.get('史略简介', '')} {out.get('原文字句', '')}"
        info, _ = pick_emperor_from_text(text, ei, work_id=wid)
        if info:
            patron = info.get("emperor") or info.get("帝王名称")
    if not patron and cat != "蕃祚":
        data = {"entries": all_entries, "volume": sid.rsplit("_", 1)[0] if sid else ""}
        fb = resolve_person_fallback(out, data, ei, work_id=_work_id(out) or "01史记")
        if fb:
            out.update(fb["coords"])
            out["四级帝王坐标"] = fb["patron"]
            if out.get("史略开始年") is None and fb.get("start") is not None:
                out["史略开始年"] = fb["start"]
                out["史略结束年"] = fb["end"]
            reconcile_entries_coord_ids([out])
            return out, changed

    if patron:
        _apply_coords_from_patron(out, patron, ei, ri)

    if cat == "蕃祚" and not str(out.get("四级帝王坐标") or "").strip():
        rule_patron = _infer_patron_from_rules(out)
        if rule_patron:
            _apply_coords_from_patron(out, rule_patron, ei, ri)
        if not str(out.get("四级帝王坐标") or "").strip():
            _apply_coords_from_patron(out, "汉武帝", ei, ri)

    reconcile_entries_coord_ids([out])

    if not entry_has_complete_years(out):
        emp = ei.get(str(out.get("四级帝王坐标") or ""))
        sy, ey, level, note = apply_person_year_fallback(out, emperor_info=emp)
        if sy is not None:
            write_fallback_years_to_entry(out, sy, ey, level, note)

    if out.get("史略开始年") is None and out.get("峰值年") is not None:
        p = int(out["峰值年"])
        out["史略开始年"] = p
        out["史略结束年"] = p

    out = _enforce_work_dynasty_coords(out, ei=ei, ri=ri, em_rows=em_rows)
    return out, changed


def _needs_dynasty_enforce(entry: dict, *, ei: dict) -> bool:
    """朝代坐标链与母本著作不一致时需强制修正。"""
    work = _work_id(entry)
    if work in WORK_DYNASTY_HINT and _coord_chain_mismatch(entry, work=work, ei=ei):
        return True
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat in {"宗戚", "蕃祚"} and work in WORK_DYNASTY_HINT:
        if not str(entry.get("帝王ID") or "").strip():
            return True
    if work == "04三国志" and not _emperor_in_dynasty(
        ei, _resolve_patron_name(str(entry.get("四级帝王坐标") or "").strip(), ei), "三国"
    ):
        return True
    return False


# 批量误挂常见值：合法三国帝王，但不可作为「已有挂靠即保留」的默认
STICKY_WRONG_SANGUO_PATRONS = frozenset({"吴乌程侯"})


def _sanguo_vol_num(entry: dict) -> int | None:
    for p in entry.get("paragraphs") or []:
        src = str(p.get("source_file") or "")
        m = re.search(r"_(\d{3})_", src)
        if m:
            return int(m.group(1))
        vol = str(p.get("vol") or "").strip()
        if vol.isdigit():
            return int(vol)
    return None


def _infer_sanguo_patron(entry: dict, *, ei: dict) -> str:
    """三国志人物：规则 / 姓前缀 / 魏蜀吴分卷 → 挂靠三国帝王。

    不保留「吴乌程侯」等批量误挂：该名虽属三国，但一期大量蜀魏人物被错挂于此。
    """
    patron = _resolve_patron_name(str(entry.get("四级帝王坐标") or "").strip(), ei)
    if (
        patron
        and patron not in STICKY_WRONG_SANGUO_PATRONS
        and _emperor_in_dynasty(ei, patron, "三国")
    ):
        return patron

    rule_patron = _infer_patron_from_rules(entry)
    if rule_patron:
        resolved = _resolve_patron_name(rule_patron, ei)
        if resolved and _emperor_in_dynasty(ei, resolved, "三国"):
            if resolved not in STICKY_WRONG_SANGUO_PATRONS:
                return resolved

    name = str(entry.get("史略名称") or "").strip()
    if name.startswith("曹"):
        return "曹操"
    if name.startswith("孙"):
        return "吴大帝"
    vol = _sanguo_vol_num(entry)
    if name.startswith("刘") and vol is not None and 31 <= vol <= 45:
        return "蜀昭烈帝"
    if name.startswith("刘"):
        return "蜀昭烈帝"

    text = f"{entry.get('史略简介', '')} {entry.get('原文字句', '')}"
    info, _ = pick_emperor_from_text(text, ei, work_id="04三国志", dynasty_hint="三国")
    if info:
        p = _resolve_patron_name(str(info.get("emperor") or info.get("帝王名称") or "").strip(), ei)
        if (
            p
            and _emperor_in_dynasty(ei, p, "三国")
            and p not in STICKY_WRONG_SANGUO_PATRONS
        ):
            return p

    if vol is not None:
        if 31 <= vol <= 45:
            return "蜀昭烈帝"
        if 46 <= vol <= 65:
            return "吴大帝"
        if 1 <= vol <= 30:
            return "曹操"
    return "曹操"


def backfill_index_file(
    path: Path,
    *,
    ei: dict,
    ri: dict,
    em_rows: list[dict],
    all_entries: list[dict] | None = None,
) -> tuple[list[dict], list[str], list[str]]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    pool = all_entries if all_entries is not None else entries
    logs: list[str] = []
    still_bad: list[str] = []
    for i, entry in enumerate(entries):
        needs_backfill = _entry_incomplete(entry)
        needs_enforce = path == V2_INDEX_03_04 and _needs_dynasty_enforce(entry, ei=ei)
        if not needs_backfill and not needs_enforce:
            continue
        fixed = entry
        changed = False
        if needs_backfill:
            fixed, changed = backfill_entry(entry, all_entries=pool, ei=ei, ri=ri, em_rows=em_rows)
        elif needs_enforce:
            before = json.dumps(fixed, sort_keys=True, ensure_ascii=False)
            fixed = _enforce_work_dynasty_coords(fixed, ei=ei, ri=ri, em_rows=em_rows)
            changed = json.dumps(fixed, sort_keys=True, ensure_ascii=False) != before
        eid = fixed["史略ID"]
        bad = []
        if fixed.get("史略开始年") is None:
            bad.append("year")
        for k in COORD_KEYS:
            if not str(fixed.get(k) or "").strip():
                bad.append(k)
        if bad:
            still_bad.append(f"{eid} ({', '.join(bad)})")
        elif changed:
            logs.append(
                f"{eid} {fixed.get('史略名称')}: "
                f"{fixed.get('四级帝王坐标')} {fixed.get('史略开始年')}~{fixed.get('史略结束年')}"
            )
        entries[i] = fixed
    return entries, logs, still_bad


def main() -> int:
    parser = argparse.ArgumentParser(description="补全缺坐标/年份的 V2 条目")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild-online", action="store_true", default=True)
    parser.add_argument("--import-db", action="store_true", default=True)
    args = parser.parse_args()

    ei = build_emperor_index()
    ri = build_regime_index()
    em_rows = load_emperor_rows(EMPEROR_JSON)

    logs: list[str] = []
    still_bad: list[str] = []
    v2_paths = [V2_INDEX]
    if V2_INDEX_03_04.is_file():
        v2_paths.append(V2_INDEX_03_04)

    for path in v2_paths:
        entries, file_logs, file_bad = backfill_index_file(
            path, ei=ei, ri=ri, em_rows=em_rows
        )
        logs.extend(f"[{path.name}] {line}" for line in file_logs)
        still_bad.extend(f"[{path.name}] {line}" for line in file_bad)
        if not args.dry_run:
            path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"已写回 → {path}")

    print(f"补全成功: {len(logs)}")
    for line in logs:
        print(f"  ✓ {line}")
    if still_bad:
        print(f"仍不完整: {len(still_bad)}")
        for line in still_bad:
            print(f"  ✗ {line}")

    if args.dry_run:
        return 1 if still_bad else 0

    if args.rebuild_online:
        import subprocess

        rc = subprocess.call([sys.executable, str(SCR / "build_online_index.py")])
        if rc != 0:
            return rc

    if args.import_db:
        import subprocess

        rc = subprocess.call(
            [
                sys.executable,
                str(SCR / "import_box_index_json.py"),
                "--json",
                str(ROOT / "data" / "12线上史略索引" / "史略索引_online.json"),
            ]
        )
        if rc != 0:
            return rc

    return 1 if still_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
