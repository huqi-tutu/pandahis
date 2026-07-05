#!/usr/bin/env python3
"""一次性：修正 077/113–118/121/123 占位年或民录/士臣活跃跨度。"""

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
    # 077 魏公子列传
    "SHIJI_077_01": (-274, -243, False, "封信陵君至卒，学界约前274–前243"),
    "SHIJI_077_02": (-265, -265, True, "魏安釐王时博局识赵猎，史无详年取安釐王中期"),
    "SHIJI_077_03": (-258, -258, True, "虚左迎侯生，窃符救赵数年前"),
    "SHIJI_077_04": (-257, -257, True, "秦围邯郸窃符救赵，前257"),
    "SHIJI_077_05": (-257, -257, True, "侯生北乡自刭，与窃符救赵同时"),
    "SHIJI_077_06": (-256, -256, True, "救赵后留赵辞封，前256"),
    "SHIJI_077_07": (-255, -255, True, "留赵期间从毛薛游"),
    "SHIJI_077_08": (-247, -247, True, "归国五国破秦于河外，前247"),
    "SHIJI_077_09": (-243, -243, True, "秦反间废信陵君，同年饮酒卒前243"),
    "SHIJI_077_10": (-195, -195, True, "高祖十二年从击黥布还置守冢，前195"),
    # 116 西南夷列传
    "SHIJI_116_01": (-340, -111, False, "民录叙事跨度：庄蹻王滇至汉平西南夷"),
    "SHIJI_116_03": (-135, -135, True, "建元六年唐蒙通夜郎，前135"),
    "SHIJI_116_04": (-111, -111, True, "元鼎六年南越反汉平西南夷，前111"),
    # 113–115 民族志民录跨度
    "SHIJI_113_01": (-210, -111, False, "民录叙事跨度：赵佗立南越至汉平南越"),
    "SHIJI_113_03": (-111, -111, True, "元鼎六年汉平南越，前111"),
    "SHIJI_114_01": (-200, -110, False, "民录叙事跨度：秦汉间东越至汉平东越"),
    "SHIJI_115_01": (-300, -108, False, "民录叙事跨度：古朝鲜至汉击卫氏朝鲜"),
    "SHIJI_115_03": (-108, -108, True, "元封三年汉击朝鲜灭卫氏，前108"),
    # 117–123 士臣跨度
    "SHIJI_117_01": (-179, -117, False, "司马相如生卒学界主流"),
    "SHIJI_118_01": (-196, -174, False, "封淮南王至流放绝食死，前196–前174"),
    "SHIJI_118_05": (-178, -122, False, "封衡山王至元狩伏诛，前178–前122"),
    "SHIJI_121_05": (-270, -160, False, "伏生秦博士至文帝求尚书，约前270–前160"),
    "SHIJI_123_01": (-139, -114, False, "张骞通西域至卒，前139–前114"),
    # 079 范睢事略占位年
    "SHIJI_079_02": (-275, -275, True, "须贾折辱范睢在魏，约前275"),
    "SHIJI_079_03": (-270, -270, True, "范睢亡魏入秦，约前270"),
    "SHIJI_079_04": (-270, -270, True, "范睢离宫激秦昭王，约前270"),
    "SHIJI_079_05": (-268, -268, True, "范睢说远交近攻，约前268"),
    "SHIJI_079_06": (-266, -266, True, "范睢说废四贵，约前266"),
    "SHIJI_079_07": (-265, -265, True, "范睢折辱须贾迫魏齐，约前265"),
    "SHIJI_079_08": (-265, -265, True, "秦昭王诱平原君索魏齐，约前265"),
    # 086 豫让刺赵襄子
    "SHIJI_086_06": (-451, -451, True, "豫让漆身吞炭刺赵襄子，智伯亡后约前451"),
    # 100 丁公
    "SHIJI_100_05": (-206, -202, False, "彭城西释高祖前206，项王灭后被斩前202"),
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
    applied = 0
    for path in sorted(HIST.glob("01史记_*_skeleton.json")):
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
            print(f"已更新 {path.name}")

    print(f"共写入 {applied}/{len(YEAR_FIXES)} 条")
    return 0 if applied == len(YEAR_FIXES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
