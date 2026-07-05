#!/usr/bin/env python3
"""为史记 031–089 待填/误用帝王在位年的人物写入学界主流生卒。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Tuple

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"

# (开始年, 结束年, 是否单点, 依据)
YEAR_FIXES: Dict[str, Tuple[int, int, bool, str]] = {
    "SHIJI_062_02": (-725, -645, False, "管仲生卒学界主流约前725–前645"),
    "SHIJI_072_01": (-330, -251, False, "魏冉穰侯秦昭襄时专权，卒前251"),
    "SHIJI_076_02": (-310, -250, False, "虞卿赵相，活跃战国晚期"),
    "SHIJI_077_01": (-274, -243, False, "信陵君封君至卒，学界约前274–前243"),
    "SHIJI_079_01": (-290, -255, False, "范睢入秦相秦至被逐，卒约前255"),
    "SHIJI_079_02": (-285, -248, False, "蔡泽继范睢相秦，活跃期约前285–前248"),
    "SHIJI_080_01": (-344, -279, False, "乐毅生卒学界主流"),
    "SHIJI_081_01": (-327, -259, False, "廉颇生卒约前327–前259"),
    "SHIJI_081_02": (-329, -259, False, "蔺相如生卒约前329–前259"),
    "SHIJI_082_01": (-370, -279, False, "田单复齐，活跃期约前370–前279"),
    "SHIJI_083_01": (-210, -140, False, "邹阳汉文景间游诸侯"),
    "SHIJI_086_01": (-540, -515, False, "专诸刺王僚前515"),
    "SHIJI_086_02": (-690, -670, False, "曹沫春秋柯会盟前后活跃期"),
    # 修正：生卒勿与楚考烈王在位年完全一致
    "SHIJI_078_01": (-314, -238, False, "黄歇生年不详约前314，卒前238（令尹被诛）"),
    # 089 与 PERSON_PATCH 活跃期对齐
    "SHIJI_089_01": (-270, -202, False, "张耳生年约前270，卒前202"),
    "SHIJI_089_02": (-270, -204, False, "陈馀生年约前270，卒前204"),
}

STALE_REF_CLEAN = {
    "SHIJI_089_01": "主轴帝王已确认为汉高祖",
    "SHIJI_089_02": "主轴帝王已确认为汉高祖",
}

SPINDLE_RATIONALES: Dict[str, str] = {
    "SHIJI_062_02": "本卷以辅齐桓公称霸、改革内政为主线，主轴挂齐桓公；早年事公子纠见前段事略。",
    "SHIJI_072_01": "本卷以穰侯秦昭襄时专权为主线，主轴挂秦昭襄王；惠文王时入秦见前段事略。",
    "SHIJI_076_02": "本卷以虞卿说赵孝成、谋卿相为主线，主轴挂赵孝成王；早年游说见共段事略。",
    "SHIJI_077_01": "本卷以魏安釐王朝窃符救赵为主线，主轴挂魏安釐王；留赵及高祖祠墓见共段事略。",
    "SHIJI_079_01": "本卷以范睢相秦昭王为主线，主轴挂秦昭襄王；魏须贾折辱见共段事略。",
    "SHIJI_079_02": "本卷以蔡泽继范睢相秦为主线，主轴挂秦昭襄王；入秦说昭王见共段事略。",
    "SHIJI_080_01": "本卷以燕昭王连五国伐齐为主线，主轴挂燕昭王；报惠王书见共段事略。",
    "SHIJI_081_01": "本卷以廉颇赵惠文时伐齐抗秦为主线，主轴挂赵惠文王；后仕楚见共段事略。",
    "SHIJI_081_02": "本卷以蔺相如完璧归赵、渑池会为主线，主轴挂赵惠文王；与廉颇共卷事略。",
    "SHIJI_082_01": "本卷以田单即墨复齐为主线，主轴挂齐襄王；守城复国见本卷事略。",
    "SHIJI_083_01": "本卷以邹阳梁孝王朝游说辩难为主线，主轴挂梁孝王；汉文景间事见共段事略。",
}


def apply_entry(entry: dict, start: int, end: int, single: bool, note: str) -> None:
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    af = dict(entry.get("_auto_filled") or {})
    af.pop("_年待LLM", None)
    af["_年LLM依据"] = note
    if single:
        af["_死亡年锚定"] = True
        af.pop("_年LLM已确认单点", None)
    else:
        af.pop("_死亡年锚定", None)
        af.pop("_年LLM已确认单点", None)
    entry["_auto_filled"] = af
    needs = [f for f in (entry.get("_needs_llm") or []) if f not in (
        "史略开始年", "史略结束年",
    )]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)


def main() -> int:
    logs: list[str] = []
    for vol in range(31, 90):
        for path in sorted(ANN.glob(f"01史记_{vol:03d}_*_skeleton.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for entry in data.get("entries", []):
                eid = entry.get("史略ID", "")
                spec = YEAR_FIXES.get(eid)
                if spec:
                    start, end, single, note = spec
                    apply_entry(entry, start, end, single, note)
                    logs.append(f"{eid} {entry.get('史略名称')} → {start}～{end}")
                    changed = True
                if eid in STALE_REF_CLEAN:
                    af = dict(entry.get("_auto_filled") or {})
                    if "黄帝" in af.get("_主轴参考", ""):
                        af["_主轴参考"] = STALE_REF_CLEAN[eid]
                        entry["_auto_filled"] = af
                        logs.append(f"{eid} 清理黄帝主轴参考")
                        changed = True
                text = SPINDLE_RATIONALES.get(eid)
                if text:
                    af = dict(entry.get("_auto_filled") or {})
                    af["_坐标主轴说明"] = text
                    entry["_auto_filled"] = af
                    logs.append(f"{eid} 补主轴说明")
                    changed = True
            if changed:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
    print(f"已更新 {len(logs)} 处:")
    for ln in logs:
        print(f"  · {ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
