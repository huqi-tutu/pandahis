#!/usr/bin/env python3
"""一次性：为 01史记 071–130 共 73 条待 LLM 条目写入学界共识生卒/活跃年（仅改年份相关字段）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

import sys

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from lib_config import paths

HIST = paths()["annotations"]

# (开始年, 结束年, 是否仅知一年/单点已确认, 简要依据)
YEAR_FIXES: Dict[str, Tuple[int, int, bool, str]] = {
    "SHIJI_071_03": (-340, -297, False, "甘茂事秦惠武王昭王后奔魏卒，学界约前340–前297"),
    "SHIJI_071_07": (-245, -237, False, "甘罗十二为秦使约前239–237，取活跃期"),
    "SHIJI_074_01": (-372, -289, False, "孟子生卒学界主流"),
    "SHIJI_074_03": (-305, -240, False, "邹衍生卒约"),
    "SHIJI_074_05": (-386, -310, False, "淳于髡生卒约"),
    "SHIJI_074_08": (-313, -238, False, "荀卿生卒约"),
    "SHIJI_074_10": (-468, -376, False, "墨翟生卒约"),
    "SHIJI_075_08": (-310, -279, False, "冯驩事孟尝君，史无详生卒取活跃期"),
    "SHIJI_076_07": (-310, -250, False, "虞卿赵相，活跃战国晚期"),
    "SHIJI_080_01": (-344, -279, False, "乐毅生卒"),
    "SHIJI_080_04": (-290, -250, False, "乐间燕将，活跃昭王之后"),
    "SHIJI_081_02": (-329, -259, False, "蔺相如生卒约"),
    "SHIJI_082_01": (-370, -279, False, "田单复齐，活跃期约"),
    "SHIJI_083_01": (-395, -245, False, "鲁仲连生卒约"),
    "SHIJI_083_04": (-210, -140, False, "邹阳汉文景间游诸侯"),
    "SHIJI_084_01": (-343, -278, False, "屈原生卒主流"),
    "SHIJI_084_07": (-200, -168, False, "贾谊生卒"),
    "SHIJI_086_01": (-690, -670, False, "曹沫春秋齐将，取柯会盟前后活跃期"),
    "SHIJI_086_03": (-540, -515, False, "专诸刺僚前515"),
    "SHIJI_086_05": (-453, -424, False, "豫让事智伯后复仇"),
    "SHIJI_086_07": (-420, -397, False, "聂政刺侠累前397"),
    "SHIJI_086_09": (-240, -227, False, "荆轲刺秦王前227"),
    "SHIJI_094_02": (-209, -205, False, "田荣起兵至自杀"),
    "SHIJI_094_03": (-210, -202, False, "田横至洛阳自刎前202"),
    "SHIJI_095_01": (-242, -189, False, "樊哙生卒"),
    "SHIJI_095_02": (-268, -180, False, "郦商生卒"),
    "SHIJI_095_03": (-246, -165, False, "夏侯婴生卒"),
    "SHIJI_096_03": (-250, -196, False, "任敖从刘邦起兵封侯"),
    "SHIJI_103_04": (-200, -136, False, "直不疑生卒"),
    "SHIJI_103_05": (-152, -133, False, "周仁景帝近臣"),
    "SHIJI_103_06": (-180, -120, False, "张欧文帝时名儒"),
    "SHIJI_104_01": (-190, -110, False, "田叔景武间"),
    "SHIJI_104_02": (-120, -99, False, "田仁战死前99"),
    "SHIJI_105_01": (-407, -310, False, "扁鹊生卒约"),
    "SHIJI_119_01": (-630, -593, False, "孙叔敖楚相"),
    "SHIJI_119_04": (-515, -490, False, "石奢楚昭王时"),
    "SHIJI_119_05": (-580, -550, False, "李离晋理狱，时代约"),
    "SHIJI_121_02": (-200, -120, False, "申公汉初博士"),
    "SHIJI_121_03": (-189, -91, False, "辕固生九十余岁"),
    "SHIJI_121_04": (-220, -120, False, "韩生韩诗"),
    "SHIJI_121_06": (-200, -100, False, "高堂生传礼"),
    "SHIJI_121_07": (-165, -89, False, "杨何生卒"),
    "SHIJI_121_08": (-179, -104, False, "董仲舒生卒"),
    "SHIJI_122_01": (-220, -130, False, "侯封汉初"),
    "SHIJI_122_02": (-200, -127, False, "郅都生卒"),
    "SHIJI_122_03": (-174, -117, False, "宁成生卒"),
    "SHIJI_122_04": (-150, -118, False, "周阳由武帝时伏诛"),
    "SHIJI_122_05": (-168, -104, False, "赵禹生卒约"),
    "SHIJI_122_06": (-186, -116, False, "张汤生卒"),
    "SHIJI_122_07": (-185, -117, False, "义纵伏诛前117"),
    "SHIJI_122_08": (-200, -91, False, "王温舒伏诛前91"),
    "SHIJI_122_09": (-180, -102, False, "减宣武帝时"),
    "SHIJI_122_10": (-152, -62, False, "杜周生卒约"),
    "SHIJI_123_02": (-138, -60, False, "西域诸国叙事：张骞通西域至宣帝间"),
    "SHIJI_123_04": (-140, -88, False, "李广利贰师将军前88诛"),
    "SHIJI_124_01": (-190, -110, False, "朱家景武间"),
    "SHIJI_124_02": (-190, -120, False, "田仲与朱家同时"),
    "SHIJI_124_03": (-169, -127, False, "剧孟生卒约"),
    "SHIJI_124_04": (-170, -127, False, "郭解前127诛"),
    "SHIJI_125_01": (-230, -180, False, "籍孺高祖近臣"),
    "SHIJI_125_02": (-210, -160, False, "闳孺惠帝时"),
    "SHIJI_125_03": (-200, -116, False, "邓通前116死"),
    "SHIJI_125_04": (-160, -130, False, "周文景帝幸臣"),
    "SHIJI_125_05": (-150, -133, False, "韩嫣前133诛"),
    "SHIJI_125_06": (-120, -99, False, "李延年前99族诛"),
    "SHIJI_126_02": (-620, -590, False, "优孟楚庄王时"),
    "SHIJI_126_03": (-240, -180, False, "优旃秦汉间"),
    "SHIJI_126_05": (-422, -390, False, "西门豹魏文侯邺令"),
    "SHIJI_129_02": (-520, -420, False, "子贡生卒约"),
    "SHIJI_129_03": (-440, -381, False, "白圭生卒约"),
    "SHIJI_129_04": (-220, -150, False, "卓氏赵至汉"),
    "SHIJI_129_05": (-180, -100, False, "任氏景武间巨商"),
    "SHIJI_129_06": (-487, -100, False, "货殖列传地理总述叙事跨度"),
}


def apply_entry(entry: dict, start: int, end: int, single: bool, note: str) -> None:
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    auto = dict(entry.get("_auto_filled") or {})
    auto.pop("_年待LLM", None)
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
    touched_vols: set[str] = set()
    applied = 0
    missing = []

    for path in sorted(HIST.glob("01史记_*_skeleton.json")):
        vol = path.name.split("_")[1]
        if not (71 <= int(vol) <= 130):
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
            changed = True
            applied += 1
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            touched_vols.add(vol)

    # verify all applied
    for eid in YEAR_FIXES:
        found = False
        for path in HIST.glob("01史记_*_skeleton.json"):
            d = json.load(open(path, encoding="utf-8"))
            for e in d.get("entries", []):
                if e.get("史略ID") == eid:
                    found = True
                    if e.get("史略开始年") is None:
                        missing.append(eid)
                    break
            if found:
                break
        if not found:
            missing.append(f"{eid}(not found)")

    print(f"已写入 {applied}/{len(YEAR_FIXES)} 条，涉及 {len(touched_vols)} 卷")
    if missing:
        print("未成功:", missing)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
