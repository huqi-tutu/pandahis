#!/usr/bin/env python3
"""一次性：修正 067 仲尼弟子列传 30 条士臣批量占位年（-522～-479）。"""

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

# (开始年, 结束年, 是否单点, 依据)
YEAR_FIXES: Dict[str, Tuple[int, int, bool, str]] = {
    "SHIJI_067_01": (-521, -481, False, "颜回少孔子三十岁，41岁卒，学界约前521–前481"),
    "SHIJI_067_02": (-536, -487, False, "闵子骞生卒约"),
    "SHIJI_067_03": (-544, -479, False, "冉伯牛生卒约"),
    "SHIJI_067_04": (-543, -474, False, "冉雍生卒约"),
    "SHIJI_067_05": (-552, -470, False, "冉有生卒约"),
    "SHIJI_067_06": (-542, -480, False, "子路少孔子九岁，结缨而死前480"),
    "SHIJI_067_07": (-522, -476, False, "宰予生卒约"),
    "SHIJI_067_08": (-520, -420, False, "子贡生卒约"),
    "SHIJI_067_09": (-506, -443, False, "子游生卒约"),
    "SHIJI_067_10": (-507, -420, False, "子夏生卒约"),
    "SHIJI_067_11": (-503, -480, False, "子张生卒约"),
    "SHIJI_067_12": (-505, -436, False, "曾参生卒约"),
    "SHIJI_067_13": (-512, -470, False, "澹台灭明生卒约"),
    "SHIJI_067_14": (-528, -448, False, "宓不齐生卒约"),
    "SHIJI_067_15": (-515, -430, False, "原宪生卒约"),
    "SHIJI_067_16": (-530, -470, False, "公冶长生卒约"),
    "SHIJI_067_17": (-540, -468, False, "南宫括生卒约"),
    "SHIJI_067_18": (-548, -475, False, "公皙哀生卒约"),
    "SHIJI_067_19": (-518, -468, False, "曾蒧生卒约"),
    "SHIJI_067_20": (-550, -481, False, "颜无繇颜回父，生卒约"),
    "SHIJI_067_21": (-520, -458, False, "商瞿生卒约"),
    "SHIJI_067_22": (-521, -478, False, "高柴少孔子三十岁，生卒约"),
    "SHIJI_067_23": (-538, -472, False, "漆彫开生卒约"),
    "SHIJI_067_24": (-546, -475, False, "公伯缭生卒约"),
    "SHIJI_067_25": (-549, -474, False, "司马耕生卒约"),
    "SHIJI_067_26": (-541, -469, False, "樊须生卒约"),
    "SHIJI_067_27": (-532, -471, False, "有若生卒约"),
    "SHIJI_067_28": (-519, -473, False, "公西赤生卒约"),
    "SHIJI_067_29": (-534, -466, False, "巫马施生卒约"),
    "SHIJI_067_30": (-540, -465, False, "梁鳣颜幸等群弟子，取活跃期约"),
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
    path = HIST / "01史记_067_仲尼弟子列传_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    applied = 0
    for entry in data.get("entries", []):
        eid = entry.get("史略ID", "")
        if eid not in YEAR_FIXES:
            continue
        start, end, single, note = YEAR_FIXES[eid]
        apply_entry(entry, start, end, single, note)
        applied += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {applied}/{len(YEAR_FIXES)} 条")
    return 0 if applied == len(YEAR_FIXES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
