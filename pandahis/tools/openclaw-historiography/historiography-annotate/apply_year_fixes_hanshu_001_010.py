#!/usr/bin/env python3
"""修正汉书 001–010 共 85 条事略/典制即位年单点占位。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Tuple

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

import sys

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from lib_config import paths

HIST = paths()["annotations"]

# (开始年, 结束年, 是否单点, 依据)
YEAR_FIXES: Dict[str, Tuple[int, int, bool, str]] = {
    # ── 001 高帝纪上 ──
    "HANSHU_001_02": (-209, -209, True, "斩蛇在沛公起兵前，约秦二世元年前后前209"),
    "HANSHU_001_04": (-208, -208, True, "六月立楚怀王，前208"),
    "HANSHU_001_05": (-207, -207, True, "怀王约先入关中者王，前207"),
    "HANSHU_001_06": (-207, -207, True, "二月攻昌邑遇郦食其，前207"),
    "HANSHU_001_07": (-206, -206, True, "元年冬十月入咸阳约法三章，前206"),
    "HANSHU_001_08": (-206, -206, True, "鸿门宴，前206"),
    "HANSHU_001_09": (-206, -206, True, "二月项羽分封汉王，前206"),
    "HANSHU_001_10": (-205, -205, True, "至南郑拜韩信为大将，汉二年，前205"),
    "HANSHU_001_11": (-205, -205, True, "五月还定三秦，汉二年，前205"),
    "HANSHU_001_12": (-205, -205, True, "三月为义帝发丧讨项羽，汉二年，前205"),
    "HANSHU_001_13": (-205, -205, True, "彭城之战，汉二年四月，前205"),
    "HANSHU_001_14": (-204, -203, False, "荥阳成皋对峙，汉二至三年，前204–前203"),
    "HANSHU_001_15": (-204, -204, True, "韩信灭魏，汉三年八月，前204"),
    "HANSHU_001_17": (-204, -204, True, "张良阻立六国后，荥阳期间，前204"),
    "HANSHU_001_18": (-204, -204, True, "陈平反间范增，夏四月，前204"),
    "HANSHU_001_19": (-204, -204, True, "纪信诳楚，五月，前204"),
    "HANSHU_001_20": (-204, -204, True, "成皋之战，前204"),
    "HANSHU_001_21": (-203, -203, True, "韩信破齐，汉四年，前203"),
    "HANSHU_001_22": (-203, -203, True, "广武对峙，前203"),
    "HANSHU_001_23": (-203, -203, True, "春二月立韩信为齐王，前203"),
    "HANSHU_001_24": (-203, -203, True, "鸿沟之约，九月，前203"),
    # ── 002 高帝纪下 ──
    "HANSHU_002_04": (-202, -202, True, "项羽灭后田横自杀，前202"),
    "HANSHU_002_05": (-200, -200, True, "娄敬说都长安，车驾西都，前200"),
    "HANSHU_002_07": (-201, -201, True, "甲申剖符封功臣，前201"),
    "HANSHU_002_08": (-200, -200, True, "白登之围，七年九月，前200"),
    "HANSHU_002_09": (-200, -200, True, "二月至长安治未央宫，前200"),
    "HANSHU_002_12": (-196, -196, True, "十年春正月韩信谋反，前196"),
    "HANSHU_002_13": (-196, -196, True, "三月彭越谋反，前196"),
    "HANSHU_002_14": (-195, -195, True, "秋七月黥布反，前195"),
    "HANSHU_002_15": (-195, -195, True, "过沛大风歌，前195"),
    "HANSHU_002_17": (-195, -195, True, "击布中流矢病甚，前195"),
    "HANSHU_002_18": (-195, -195, True, "夏四月帝崩，前195"),
    "HANSHU_002_19": (-194, -194, True, "令民产子复勿事，前194"),
    "HANSHU_002_20": (-201, -201, True, "二年二月省赋求贤诏，前201"),
    "HANSHU_002_21": (-202, -202, True, "雒阳南宫论三杰，即位初，前202"),
    "HANSHU_002_22": (-196, -196, True, "五月诏封赵佗南粤王，前196"),
    # ── 003 惠帝纪 ──
    "HANSHU_003_02": (-191, -191, True, "皇帝冠除挟书律，惠帝四年三月，前191"),
    "HANSHU_003_03": (-187, -187, True, "举孝弟力田，惠帝七年正月，前187"),
    # ── 005 文帝纪 ──
    "HANSHU_005_03": (-179, -179, True, "除收帑相坐律，文帝二年，前179"),
    "HANSHU_005_04": (-178, -178, True, "开籍田亲耕，前178"),
    "HANSHU_005_05": (-178, -178, True, "除诽谤妖言之罪，前178"),
    "HANSHU_005_06": (-164, -164, True, "济北王兴居反，前164"),
    "HANSHU_005_07": (-175, -175, True, "除盗铸钱令更造四铢，前175"),
    "HANSHU_005_08": (-174, -174, True, "淮南王长谋反废死，前174"),
    "HANSHU_005_09": (-167, -167, True, "除肉刑，前167"),
    "HANSHU_005_10": (-166, -166, True, "除田之租税，前166"),
    "HANSHU_005_12": (-165, -165, True, "举贤良直言极谏，前165"),
    "HANSHU_005_13": (-163, -163, True, "后元年新垣平诈觉，前163"),
    # ── 006 景帝纪 ──
    "HANSHU_006_02": (-154, -154, True, "七国之乱，前154"),
    "HANSHU_006_03": (-150, -150, True, "废太子荣，前150"),
    "HANSHU_006_04": (-149, -149, True, "临江王荣自杀，前149"),
    "HANSHU_006_05": (-143, -143, True, "周亚夫下狱死，前143"),
    "HANSHU_006_06": (-156, -156, True, "令田半租，前156"),
    "HANSHU_006_07": (-156, -156, True, "改磔曰弃市，前156"),
    "HANSHU_006_09": (-144, -144, True, "改诸官名定伪黄金律，前144"),
    "HANSHU_006_10": (-141, -141, True, "景帝崩，前141"),
    # ── 007 武帝纪 ──
    "HANSHU_007_02": (-139, -139, True, "建元元年罢黜百家，前139"),
    "HANSHU_007_03": (-128, -128, True, "元光六年卫青龙城，前128"),
    "HANSHU_007_04": (-127, -127, True, "元朔二年取河南地，前127"),
    "HANSHU_007_07": (-121, -121, True, "元狩二年霍去病出陇西，前121"),
    "HANSHU_007_08": (-121, -121, True, "昆邪王降，元狩二年，前121"),
    "HANSHU_007_10": (-119, -119, True, "漠北决战封狼居胥，元狩四年，前119"),
    "HANSHU_007_11": (-111, -111, True, "元鼎六年平南越，前111"),
    "HANSHU_007_12": (-108, -108, True, "元封三年灭朝鲜，前108"),
    "HANSHU_007_13": (-106, -106, True, "元封五年置刺史部，前106"),
    "HANSHU_007_14": (-104, -104, True, "太初元年征大宛，前104"),
    "HANSHU_007_15": (-99, -99, True, "天汉二年李陵降，前99"),
    "HANSHU_007_16": (-91, -91, True, "征和二年巫蛊之祸，前91"),
    "HANSHU_007_17": (-87, -87, True, "后元二年武帝崩，前87"),
    "HANSHU_007_18": (-110, -110, True, "元封元年封禅泰山，前110"),
    "HANSHU_007_19": (-138, -138, True, "建元二年张骞出使，前138"),
    # ── 008 昭帝纪 ──
    "HANSHU_008_02": (-81, -81, True, "始元六年盐铁之议罢榷酤，前81"),
    "HANSHU_008_03": (-81, -81, True, "始元六年苏武还，前81"),
    "HANSHU_008_04": (-80, -80, True, "元凤元年燕王旦等谋反，前80"),
    "HANSHU_008_05": (-74, -74, True, "元平元年减口赋，前74"),
    # ── 009 宣帝纪 ──
    "HANSHU_009_02": (-74, -74, True, "元平元年迎立宣帝，前74"),
    "HANSHU_009_03": (-68, -68, True, "地节二年废霍后，前68"),
    "HANSHU_009_04": (-72, -72, True, "神爵二年日逐王降，前72"),
    "HANSHU_009_05": (-61, -61, True, "神爵三年赵充国击西羌，前61"),
    "HANSHU_009_06": (-54, -54, True, "五凤四年设常平仓，前54"),
    # ── 010 元帝纪 ──
    "HANSHU_010_02": (-46, -46, True, "初元三年萧望之被迫自杀，前46"),
    "HANSHU_010_03": (-46, -46, True, "初元三年弃珠厓，前46"),
    "HANSHU_010_04": (-42, -42, True, "永光元年冯奉世击西羌，前42"),
    "HANSHU_010_05": (-36, -36, True, "建昭三年陈汤斩郅支，前36"),
    "HANSHU_010_06": (-33, -33, True, "竟宁元年昭君出塞，前33"),
}


def apply_entry(entry: dict, start: int, end: int, single: bool, note: str) -> None:
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    auto = dict(entry.get("_auto_filled") or {})
    auto.pop("_年待LLM", None)
    auto.pop("_年冲突提示", None)
    auto.pop("_年兜底", None)
    auto.pop("_年兜底级别", None)
    auto.pop("_年建议", None)
    auto["_年LLM依据"] = note
    if single:
        auto["_年LLM已确认单点"] = True
    else:
        auto.pop("_年LLM已确认单点", None)
    entry["_auto_filled"] = auto
    needs = [f for f in (entry.get("_needs_llm") or []) if f not in ("史略开始年", "史略结束年")]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)


def main() -> int:
    applied = 0
    missing: list[str] = []
    for path in sorted(HIST.glob("02汉书_*_skeleton.json")):
        vol = path.name.split("_")[1]
        if vol not in {f"{n:03d}" for n in range(1, 11)}:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for entry in data.get("entries", []):
            eid = entry.get("史略ID", "")
            if eid not in YEAR_FIXES:
                continue
            start, end, single, note = YEAR_FIXES[eid]
            apply_entry(entry, start, end, single, note)
            applied += 1
            changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print(f"✅ {path.name}")
    expected = set(YEAR_FIXES)
    for path in sorted(HIST.glob("02汉书_00[1-9]_*_skeleton.json")) + sorted(
        HIST.glob("02汉书_010_*_skeleton.json")
    ):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("entries", []):
            eid = entry.get("史略ID", "")
            if eid in expected:
                expected.discard(eid)
    if expected:
        missing = sorted(expected)
        print(f"⚠️  未找到条目: {missing}")
    print(f"\n共修正 {applied} 条（预期 {len(YEAR_FIXES)} 条）")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
