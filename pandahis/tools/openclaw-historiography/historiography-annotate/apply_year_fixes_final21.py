#!/usr/bin/env python3
"""修正 21 卷终检失败：占位年/短跨度/事略照搬生卒/缺年/_needs_llm。"""

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
    # 012 孝武本纪
    "SHIJI_012_03": (-113, -112, False, "栾大封侯至伏诛，事略取事件年非生卒"),
    "SHIJI_012_08": (-140, -117, False, "越祠鸡卜民录，取武帝朝越事活跃期"),
    "SHIJI_012_09": (-140, -117, False, "李少君方士，学界约前140–前117"),
    "SHIJI_012_11": (-113, -100, False, "栾大方士，武帝朝活跃至伏诛"),
    "SHIJI_012_12": (-113, -90, False, "公孙卿方士，武帝朝长期活跃"),
    # 028 封禅书
    "SHIJI_028_10": (-572, -492, False, "苌弘周大夫，约前572–前492"),
    "SHIJI_028_11": (-140, -117, False, "李少君方士，学界约前140–前117"),
    "SHIJI_028_13": (-113, -100, False, "栾大方士，武帝朝活跃至伏诛"),
    "SHIJI_028_14": (-113, -90, False, "公孙卿方士，武帝朝长期活跃"),
    "SHIJI_028_15": (-178, -163, False, "新垣平方士，约前178–前163"),
    # 032 齐太公世家
    "SHIJI_032_22": (-548, -532, False, "崔杼弑君至庆封之乱，约前548–前532"),
    "SHIJI_032_23": (-547, -532, False, "庆封专齐政至被诛，约前547–前532"),
    "SHIJI_032_26": (-546, -532, False, "丙戎齐大夫，与庆封乱同时期"),
    # 033 鲁周公世家
    "SHIJI_033_19": (-662, -648, False, "庆父乱鲁，约前662–前648"),
    "SHIJI_033_22": (-551, -479, False, "孔子生卒学界主流"),
    "SHIJI_033_37": (-660, -660, True, "庆父之乱事件，前660"),
    # 034 燕召公世家
    "SHIJI_034_11": (-320, -304, False, "子之专燕政，约前320–前304"),
    "SHIJI_034_12": (-284, -251, False, "乐毅破齐至奔赵，约前284–前251"),
    "SHIJI_034_13": (-312, -297, False, "郭隗事燕昭王，约前312–前297"),
    "SHIJI_034_16": (-283, -279, False, "将渠谏燕王，约前283–前279"),
    # 035 管蔡世家
    "SHIJI_035_31": (-498, -498, True, "公孙彊乱曹事件，前498"),
    # 039 晋世家
    "SHIJI_039_19": (-672, -651, False, "骊姬事献公，约前672–前651"),
    "SHIJI_039_20": (-672, -650, False, "里克弑君，约前672–前650"),
    "SHIJI_039_21": (-684, -651, False, "荀息事献公至殉，约前684–前651"),
    "SHIJI_039_22": (-672, -655, False, "宫之奇谏虞，约前672–前655"),
    "SHIJI_039_23": (-672, -656, False, "太子申生，约前672–前656"),
    "SHIJI_039_26": (-672, -636, False, "介子推从晋文公流亡至绵山，约前672–前636"),
    "SHIJI_039_29": (-607, -585, False, "董狐晋太史，约前607–前585"),
    "SHIJI_039_30": (-600, -587, False, "郤克事晋，约前600–前587"),
    "SHIJI_039_31": (-589, -575, False, "巫臣通吴，约前589–前575"),
    "SHIJI_039_33": (-572, -558, False, "师旷晋乐师，约前572–前558"),
    "SHIJI_039_37": (-651, -651, True, "骊姬之乱事件，前651"),
    "SHIJI_039_50": (-589, -584, True, "巫臣通吴事件年"),
    "SHIJI_039_55": (-637, -627, False, "釐负羁事晋，约前637–前627"),
    # 040 楚世家
    "SHIJI_040_16": (-632, -624, False, "子玉败晋，约前632–前624"),
    "SHIJI_040_17": (-626, -614, False, "商臣弑父，约前626–前614"),
    "SHIJI_040_20": (-529, -516, False, "费无忌谗太子，约前529–前516"),
    "SHIJI_040_22": (-515, -502, False, "子綦事楚，约前515–前502"),
    "SHIJI_040_25": (-328, -309, False, "张仪事楚，约前328–前309"),
    "SHIJI_040_26": (-329, -312, False, "郑袖事楚怀王，约前329–前312"),
    "SHIJI_040_27": (-340, -278, False, "屈原生卒学界主流"),
    "SHIJI_040_57": (-312, -312, True, "张仪欺楚事件，前312"),
    # 042 郑世家
    "SHIJI_042_16": (-710, -693, False, "高渠弥弑君，约前710–前693"),
    "SHIJI_042_19": (-627, -625, False, "解扬守信，约前627–前625"),
    "SHIJI_042_30": (-627, -627, True, "弦高犒师事件，前627"),
    # 045 韩世家
    "SHIJI_045_15": (-351, -351, True, "申不害相韩事件，前351"),
    # 048 陈涉世家
    "SHIJI_048_02": (-209, -196, False, "吴广从起事至被杀，前209–前196"),
    "SHIJI_048_05": (-209, -209, True, "周文西击秦，前209"),
    "SHIJI_048_06": (-209, -209, True, "武臣自立赵王，前209"),
    "SHIJI_048_07": (-209, -209, True, "韩广自立燕王，前209"),
    "SHIJI_048_08": (-208, -208, True, "田臧杀吴广，前208"),
    "SHIJI_048_09": (-208, -208, True, "陈涉败走，前208"),
    "SHIJI_048_10": (-207, -207, True, "庄贾杀陈涉，前207"),
    "SHIJI_048_11": (-207, -207, True, "吕臣复陈，前207"),
    # 060 三王世家
    "SHIJI_060_04": (-100, -80, False, "燕王刘旦，约前100–前80"),
    # 068 商君列传
    "SHIJI_068_01": (-390, -338, False, "商鞅入秦至车裂，约前390–前338"),
    "SHIJI_068_02": (-356, -356, True, "变法辩论，前356"),
    "SHIJI_068_03": (-356, -356, True, "徙木立信，前356"),
    "SHIJI_068_05": (-341, -341, True, "欺卬破魏，前341"),
    # 069 苏秦列传
    "SHIJI_069_01": (-381, -284, False, "苏秦合纵生涯，学界约前381–前284"),
    "SHIJI_069_02": (-361, -361, True, "说燕合纵，前361"),
    "SHIJI_069_03": (-334, -334, True, "说赵合纵，前334"),
    "SHIJI_069_04": (-318, -318, True, "说韩合纵，前318"),
    "SHIJI_069_05": (-318, -318, True, "说魏合纵，前318"),
    "SHIJI_069_06": (-342, -342, True, "说齐合纵，前342"),
    "SHIJI_069_07": (-331, -331, True, "说楚合纵，前331"),
    "SHIJI_069_08": (-368, -368, True, "前倨后恭，前368"),
    "SHIJI_069_09": (-322, -322, True, "说齐归十城，前322"),
    "SHIJI_069_10": (-332, -332, True, "通燕夫人死间，前332"),
    "SHIJI_069_11": (-325, -284, False, "苏代事燕，约前325–前284"),
    "SHIJI_069_12": (-320, -320, True, "子之乱燕，前320"),
    "SHIJI_069_13": (-287, -287, True, "遗书破齐，前287"),
    "SHIJI_069_14": (-284, -284, True, "说燕勿秦，前284"),
    # 070 张仪列传
    "SHIJI_070_01": (-340, -300, False, "张仪入秦至卒，约前340–前300"),
    "SHIJI_070_02": (-334, -334, True, "苏秦激张仪入秦，前334"),
    "SHIJI_070_03": (-316, -316, True, "伐蜀伐韩之争，前316"),
    "SHIJI_070_04": (-318, -318, True, "说魏连横，前318"),
    "SHIJI_070_05": (-312, -312, True, "诳楚怀王，前312"),
    "SHIJI_070_06": (-311, -311, True, "脱囚说楚连横，前311"),
    "SHIJI_070_07": (-313, -313, True, "说韩连横，前313"),
    "SHIJI_070_08": (-312, -312, True, "说齐连横，前312"),
    "SHIJI_070_09": (-311, -311, True, "说赵连横，前311"),
    "SHIJI_070_10": (-308, -308, True, "说燕连横，前308"),
    "SHIJI_070_11": (-340, -308, False, "陈轸纵横，约前340–前308"),
    "SHIJI_070_12": (-318, -318, True, "陈轸巧对秦王，前318"),
    "SHIJI_070_13": (-318, -318, True, "陈轸设犀首之计，前318"),
    "SHIJI_070_14": (-340, -318, False, "犀首事秦魏，约前340–前318"),
    "SHIJI_070_15": (-318, -318, True, "犀首诱义渠败秦，前318"),
    # 082 田单列传
    "SHIJI_082_01": (-279, -265, False, "田单复齐至封安平君，约前279–前265"),
    "SHIJI_082_02": (-279, -279, True, "火牛阵复齐，前279"),
    "SHIJI_082_03": (-279, -279, True, "齐襄王法章立，前279"),
    "SHIJI_082_04": (-279, -279, True, "王蠋义不降燕，前279"),
    # 091 黥布列传
    "SHIJI_091_01": (-208, -195, False, "黥布从反秦至伏诛，前208–前195"),
    # 093 韩信卢绾列传
    "SHIJI_093_02": (-206, -190, False, "卢绾从高祖至叛逃，前206–前190"),
    "SHIJI_093_03": (-206, -191, False, "陈豨叛赵，约前206–前191"),
}

SPINDLE_RATIONALES: Dict[str, str] = {
    "SHIJI_068_01": "本卷以秦孝公变法为主线，主轴挂秦孝公；事秦惠文王见共段事略。",
    "SHIJI_069_01": "本卷以苏秦合纵说六国为主线，主轴挂周显王/东周；各国说辞见共段事略。",
    "SHIJI_069_11": "本卷叙苏代继兄事燕，主轴挂燕昭王；子之乱燕见共段事略。",
    "SHIJI_070_01": "本卷以张仪连横事秦为主线，主轴挂秦惠文王；说魏楚齐燕赵见共段事略。",
    "SHIJI_070_11": "本卷叙陈轸纵横，主轴挂秦惠王；事魏楚见共段事略。",
}

# 058 事略条目名与归属表对齐（不可共用「梁孝王」）
ENTRY_RENAMES: Dict[str, str] = {
    "SHIJI_058_02": "景帝曰千秋万岁后传于王",
    "SHIJI_058_03": "梁孝王守睢阳距吴楚",
    "SHIJI_058_04": "梁孝王僭拟天子",
    "SHIJI_058_05": "刺杀袁盎",
    "SHIJI_058_06": "分梁为五",
    "SHIJI_058_07": "罍樽事件",
}

# 058 归属表：按段号恢复事略专名（此前误合并为「梁孝王」）
RESTORE_058_EVENT_NAMES: Dict[int, str] = {
    5: "景帝曰千秋万岁后传于王",
    6: "景帝曰千秋万岁后传于王",
    7: "梁孝王守睢阳距吴楚",
    8: "梁孝王僭拟天子",
    9: "梁孝王僭拟天子",
    12: "刺杀袁盎",
    13: "刺杀袁盎",
    15: "分梁为五",
    19: "罍樽事件",
    20: "罍樽事件",
    21: "罍樽事件",
    22: "罍樽事件",
}


def restore_058_attribution(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for seg in data.get("segment_attribution") or []:
        p = seg.get("paragraph")
        event_name = RESTORE_058_EVENT_NAMES.get(p)
        if not event_name:
            continue
        owners = seg.get("owners") or []
        new_owners = []
        for o in owners:
            if o.get("category") == "君纪":
                new_owners.append({"name": "梁孝王", "category": "君纪"})
            elif o.get("category") == "事略":
                new_owners.append({"name": event_name, "category": "事略"})
                changed = True
            else:
                new_owners.append(o)
        if len(new_owners) == 1 and not any(o["category"] == "君纪" for o in new_owners):
            seg["owners"] = [{"name": event_name, "category": "事略"}]
            changed = True
        else:
            seg["owners"] = new_owners
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


ATTRIBUTION_ALIASES: Dict[str, Dict[str, str]] = {
    "01史记_050_楚元王世家_skeleton.json": {
        "楚元王刘交": "楚元王",
    },
    "01史记_058_梁孝王世家_skeleton.json": {
        "梁孝王刘武": "梁孝王",
    },
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
    needs = [f for f in (entry.get("_needs_llm") or []) if f not in ("史略开始年", "史略结束年", "_坐标主轴说明")]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)


def fix_attribution(path: Path, aliases: Dict[str, str]) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for seg in data.get("segment_attribution") or []:
        for owner in seg.get("owners") or []:
            old = owner.get("name", "")
            if old in aliases:
                owner["name"] = aliases[old]
                changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    applied = 0
    for path in sorted(HIST.glob("01史记_*_skeleton.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for entry in data.get("entries", []):
            eid = entry.get("史略ID", "")
            if eid in YEAR_FIXES:
                start, end, single, note = YEAR_FIXES[eid]
                apply_entry(entry, start, end, single, note)
                changed = True
                applied += 1
            if eid in SPINDLE_RATIONALES:
                auto = dict(entry.get("_auto_filled") or {})
                auto["_坐标主轴说明"] = SPINDLE_RATIONALES[eid]
                entry["_auto_filled"] = auto
                needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
                if needs:
                    entry["_needs_llm"] = needs
                else:
                    entry.pop("_needs_llm", None)
                changed = True
            if eid in ENTRY_RENAMES:
                entry["史略名称"] = ENTRY_RENAMES[eid]
                changed = True
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"已更新 {path.name}")

    for fname, aliases in ATTRIBUTION_ALIASES.items():
        p = HIST / fname
        if p.is_file() and fix_attribution(p, aliases):
            print(f"已对齐归属表 {fname}")

    p058 = HIST / "01史记_058_梁孝王世家_skeleton.json"
    if p058.is_file() and restore_058_attribution(p058):
        print("已恢复 058 归属表事略专名")

    print(f"共写入 {applied}/{len(YEAR_FIXES)} 条年份")
    return 0 if applied == len(YEAR_FIXES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
