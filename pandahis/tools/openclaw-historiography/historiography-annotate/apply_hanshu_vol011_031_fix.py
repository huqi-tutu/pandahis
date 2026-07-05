#!/usr/bin/env python3
"""批量修复汉书 011–031：三字段 + 年代 + 坐标 + 个别原文。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from detail_coords import fill_all_detail_coords
from emperor_resolve import work_id_from_skeleton

import sys

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from lib_config import paths

HIST = paths()["annotations"]
VOLS = tuple(f"{n:03d}" for n in range(11, 32))

# (开始年, 结束年, 是否单点, 依据)
YEAR_FIXES: Dict[str, Tuple[int, int, bool, str]] = {
    # ── 011 成帝纪 ──
    "HANSHU_011_02": (-16, -16, True, "永始元年五月封王莽为新都侯，前16"),
    "HANSHU_011_03": (-18, -18, True, "鸿嘉二年六月立赵飞燕为皇后，前18"),
    "HANSHU_011_04": (-10, -10, True, "绥和元年夏四月改官制，前10"),
    # ── 012 哀帝纪 ──
    "HANSHU_012_02": (-7, -7, True, "建平元年六月诏罢乐府，前7"),
    "HANSHU_012_03": (-7, -7, True, "建平元年限田令，前7"),
    "HANSHU_012_05": (-2, -2, True, "元寿元年三月董贤为大司马，前2"),
    # ── 013 平帝纪 ──
    "HANSHU_013_01": (-1, 5, False, "平帝即位前1年至崩前5，与帝王表一致"),
    "HANSHU_013_02": (1, 1, True, "元始元年赐号安汉公，公元1年"),
    "HANSHU_013_03": (1, 1, True, "元始元年夏安汉公奏车服立学官，公元1年"),
    "HANSHU_013_04": (4, 4, True, "元始四年夏加号宰衡，约公元4年"),
    # ── 021 百官公卿表 ──
    "HANSHU_021_02": (1, 1, True, "元始间百官公卿制度整理，取新莽前夜为单点锚"),
    # ── 023 律历志上 ──
    "HANSHU_023_02": (-104, -104, True, "太初律度量衡整理，前104"),
    # ── 024 律历志下 ──
    "HANSHU_024_02": (9, 9, True, "刘歆《世经》成于王莽始建国，公元9年"),
    # ── 025 礼乐志 ──
    "HANSHU_025_02": (79, 79, True, "班固《汉书·礼乐志》成书语境，约79年"),
    "HANSHU_025_03": (79, 79, True, "班固《汉书·礼乐志》成书语境，约79年"),
    # ── 026 刑法志 ──
    "HANSHU_026_02": (-167, -167, True, "文帝除肉刑为汉刑法史关键节点，前167"),
    # ── 027 食货志上 ──
    "HANSHU_027_02": (9, 9, True, "新莽王田令等食货改制节点，公元9年"),
    # ── 028 食货志下 ──
    "HANSHU_028_02": (9, 9, True, "新莽货币改制节点，公元9年"),
    # ── 029 郊祀志上 ──
    "HANSHU_029_02": (-110, -110, True, "元封元年封禅，武帝郊祀制度高峰，前110"),
    # ── 030 郊祀志下 ──
    "HANSHU_030_01": (9, 9, True, "新莽郊祀改制节点，公元9年"),
    # ── 031 天文志 ──
    "HANSHU_031_01": (79, 79, True, "班固《汉书·天文志》序，约79年"),
    "HANSHU_031_02": (79, 79, True, "星官占验志体，取班固成书语境单点锚"),
}

COORD_FIXES: Dict[str, Tuple[str, str, str, str, str]] = {
    # 文明, 朝代, 政权, 帝王, 依据
    "HANSHU_024_02": ("华夏", "新", "新", "王莽", "刘歆《世经》成于新莽时期"),
    "HANSHU_025_02": ("华夏", "东汉", "东汉", "汉章帝", "班固《礼乐志》成书语境"),
    "HANSHU_025_03": ("华夏", "东汉", "东汉", "汉章帝", "班固《礼乐志》成书语境"),
    "HANSHU_031_01": ("华夏", "东汉", "东汉", "汉章帝", "《天文志》成书于班固撰汉书时期，约章帝年间"),
    "HANSHU_031_02": ("华夏", "东汉", "东汉", "汉章帝", "志书主体与班固成书语境一致"),
}

TEXT_FIXES: Dict[str, Tuple[str, str]] = {
    "HANSHU_024_01": (
        "日法八十一。元始黄钟初九自乘，一龠之数，得日法。",
        "原引「统母」节首句，补全历算原文",
    ),
}

PRIORITY_REASON_FIXES: Dict[str, str] = {
    "HANSHU_011_01": "西汉成帝本纪，元帝至成帝间国政与后妃外戚主线",
    "HANSHU_011_02": "王莽入仕封侯，外戚专权关键节点",
    "HANSHU_011_03": "赵飞燕立后，成帝后期政治标志",
    "HANSHU_011_04": "成帝官制改革，公卿制度重要变动",
    "HANSHU_012_01": "西汉哀帝本纪，短祚而改制频仍",
    "HANSHU_012_02": "罢乐府，哀帝裁减奢费代表诏令",
    "HANSHU_012_03": "限田令，西汉末年土地政策尝试",
    "HANSHU_012_04": "夏贺良改元，政治谶纬影响皇位",
    "HANSHU_012_05": "董贤专宠，哀帝晚期政局核心",
    "HANSHU_013_01": "平帝本纪，王莽专权下西汉尾声",
    "HANSHU_013_02": "安汉公封号，王莽篡汉前关键步骤",
    "HANSHU_013_03": "元始元年制度与学官改革",
    "HANSHU_013_04": "宰衡之号与明堂礼制，王莽权位再升",
    "HANSHU_031_01": "天文志总论，星占与政变关系",
    "HANSHU_031_02": "星官体系与占验实例，志书主体",
}


def apply_year(entry: dict, start: int, end: int, single: bool, note: str) -> None:
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    auto = dict(entry.get("_auto_filled") or {})
    for k in ("_年待LLM", "_年冲突提示", "_年兜底", "_年兜底级别", "_年建议"):
        auto.pop(k, None)
    auto["_年LLM依据"] = note
    if single:
        auto["_年LLM已确认单点"] = True
    else:
        auto.pop("_年LLM已确认单点", None)
    entry["_auto_filled"] = auto


def apply_coords(entry: dict, civ: str, dyn: str, reg: str, emp: str, note: str) -> None:
    entry["一级文明坐标"] = civ
    entry["二级朝代坐标"] = dyn
    entry["三级政权坐标"] = reg
    entry["四级帝王坐标"] = emp
    auto = dict(entry.get("_auto_filled") or {})
    auto["_坐标LLM依据"] = note
    entry["_auto_filled"] = auto


def main() -> int:
    year_n = coord_n = text_n = pri_n = detail_n = 0
    for vol in VOLS:
        paths = sorted(HIST.glob(f"02汉书_{vol}_*_skeleton.json"))
        if not paths:
            print(f"⚠️  卷{vol} 无 skeleton")
            continue
        path = paths[0]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        work_id = work_id_from_skeleton(data, str(path))
        for entry in data.get("entries") or []:
            eid = entry.get("史略ID", "")
            if eid in YEAR_FIXES:
                s, e, single, note = YEAR_FIXES[eid]
                apply_year(entry, s, e, single, note)
                year_n += 1
                changed = True
            if eid in COORD_FIXES:
                civ, dyn, reg, emp, note = COORD_FIXES[eid]
                apply_coords(entry, civ, dyn, reg, emp, note)
                coord_n += 1
                changed = True
            if eid in TEXT_FIXES:
                text, note = TEXT_FIXES[eid]
                entry["原文字句"] = text
                auto = dict(entry.get("_auto_filled") or {})
                auto["_原文补全"] = note
                entry["_auto_filled"] = auto
                text_n += 1
                changed = True
            if eid in PRIORITY_REASON_FIXES:
                entry["优先级判定理由"] = PRIORITY_REASON_FIXES[eid]
                pri_n += 1
                changed = True
        n = fill_all_detail_coords(data, work_id=work_id, json_path=str(path))
        detail_n += n
        changed = True
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"✅ {path.name} ({len(data.get('entries') or [])} 条)")
    print(
        f"\n完成：年代 {year_n} | 坐标 {coord_n} | 原文 {text_n} | "
        f"优先级理由 {pri_n} | 三字段 {detail_n} 条"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
