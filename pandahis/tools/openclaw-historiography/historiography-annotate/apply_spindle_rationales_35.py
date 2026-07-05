#!/usr/bin/env python3
"""批量写入 35 条跨时期 _坐标主轴说明；外戚按册立之君修正坐标。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from coordinate_index import build_regime_index, coords_and_ids_from_emperor
from emperor_resolve import build_emperor_info_index

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"

SPINDLE_RATIONALES: dict[str, str] = {
    "SHIJI_009_01": "宗戚以册封之君为准：吕雉为汉高祖皇后；惠帝朝临朝称制见共段事略。",
    "SHIJI_047_01": "本卷以仕鲁为司空、司寇及周游列国前在鲁事为主线，主轴挂鲁定公；去齐晋楚事见共段事略。",
    "SHIJI_049_01": "宗戚以册封之君为准：卫子夫为汉武帝皇后，主轴挂汉武帝。",
    "SHIJI_049_02": "宗戚以册封之君为准：王娡为汉景帝妃，册封与入宫均在景帝世；武帝朝尊太后事见共段事略。",
    "SHIJI_049_03": "宗戚以册封之君为准：窦姬在文帝朝册立为皇后；景帝朝为太后、武帝朝为太皇太后见共段事略。",
    "SHIJI_049_04": "宗戚以册封之君为准：薄姬为汉文帝生母，尊宠在文帝朝；景帝朝仍为太后见共段事略。",
    "SHIJI_049_05": "外戚以册立之君为准：本卷以文帝朝薄太后尊宠为主线，主轴挂汉文帝；景帝朝仍尊太后见共段事略。",
    "SHIJI_055_01": "本卷以佐汉定策、运筹楚汉为主线，主轴挂汉高祖；惠帝朝卒及留侯传世见共段事略。",
    "SHIJI_056_01": "本卷以楚汉间说郦生、代韩信相及平诸吕前仕汉为主线，主轴挂汉高祖；文帝世卒见共段事略。",
    "SHIJI_057_01": "本卷以从高祖定天下、太尉诛吕为主线，主轴挂汉高祖；文帝朝为相见共段事略。",
    "SHIJI_059_01": "外戚以册立之君为准：本卷以儿姁侍景帝、生赵王为主线，主轴挂汉景帝；武帝朝王孙事见共段事略。",
    "SHIJI_059_04": "外戚以册立之君为准：本卷以程姬侍景帝、生长沙王为主线，主轴挂汉景帝；五宗支系见共段事略。",
    "SHIJI_059_05": "外戚以册立之君为准：本卷以贾夫人侍景帝、生中山王为主线，主轴挂汉景帝；五宗支系见共段事略。",
    "SHIJI_062_01": "本卷以相齐景公、晏子春秋事为主线，主轴挂齐景公；历灵公至后嗣见共段事略。",
    "SHIJI_063_01": "本卷以春秋末周室东迁背景下著道论为主线，主轴挂周敬王；年代传说性强见共段事略。",
    "SHIJI_063_02": "本卷以入秦献法、相始皇统一为主线，主轴挂秦始皇；二世朝被诛见共段事略。",
    "SHIJI_064_01": "本卷以齐景公时司马穰苴斩庄贾、振军旅为主线，主轴挂齐景公；传说年代见共段事略。",
    "SHIJI_065_01": "本卷后半叙吴起相魏武侯并卒于楚，主轴挂魏武侯；事鲁及楚见共段事略。",
    "SHIJI_066_01": "本卷以奔吴、辅阖闾伐楚报仇为主线，主轴挂吴王阖闾；夫差时终见共段事略。",
    "SHIJI_067_01": "本卷以子夏居河西设教、为魏文侯师为主线，主轴挂魏文侯；早年从孔子见共段事略。",
    "SHIJI_067_02": "本卷以从孔子周游、存鲁乱齐为主线，主轴挂鲁定公；后仕卫越见共段事略。",
    "SHIJI_067_03": "本卷以从孔子、仕卫蒲将军为主线，主轴挂鲁定公；殉难于孔门见共段事略。",
    "SHIJI_067_04": "本卷以仕鲁为司寇、堕三都为主线，主轴挂鲁定公；周游列国见共段事略。",
    "SHIJI_067_05": "本卷以颜回从孔子在鲁学门为主线，主轴挂鲁定公；早卒于孔门见共段事略。",
    "SHIJI_068_01": "本卷以商鞅变法、相秦孝公为主线，主轴挂秦孝公；惠文王朝诛见共段事略。",
    "SHIJI_069_01": "本卷以合五国伐齐、报齐怨为主线，主轴挂燕昭王；早年说秦见共段事略。",
    "SHIJI_070_01": "本卷以连横事秦、相惠文王为主线，主轴挂秦惠文王；武王昭襄朝事见共段事略。",
    "SHIJI_071_01": "本卷叙樗里子事秦惠王至卒，主轴挂秦惠文王；入周事在武王朝见共段事略。",
    "SHIJI_073_02": "本卷以秦昭朝长平灭赵为主线，主轴挂秦昭襄王；武安君事功见共段事略。",
    "SHIJI_074_01": "本卷以游梁惠王、滕文公间说仁义为主线，主轴挂梁惠王；他国见共段事略。",
    "SHIJI_074_02": "本卷以赵孝成王时卿相、著书终老为主线，主轴挂赵孝成王；历齐燕见共段事略。",
    "SHIJI_075_01": "本卷以相齐湣王、合从伐秦为主线，主轴挂齐湣王；秦昭王时事见共段事略。",
    "SHIJI_076_01": "本卷以赵孝成王时卿相、长平后事为主线，主轴挂赵孝成王；早年事见共段事略。",
    "SHIJI_084_01": "本卷以怀王朝左徒被疏、自沈为主线，主轴挂楚怀王；顷襄王朝见共段事略。",
    "SHIJI_084_02": "本卷以文帝朝太傅、论政疏为主线，主轴挂汉文帝；早年仕文帝前见共段事略。",
    "SHIJI_087_01": "本卷以始皇朝李斯相业为主线，主轴挂秦始皇；二世督责与被诛见共段事略。",
    "SHIJI_088_01": "本卷以始皇朝筑长城逐戎为主线，主轴挂秦始皇；沙丘蒙冤在二世朝见共段事略。",
}

# 外戚：册立之君 → 四级帝王（与 SPINDLE_RATIONALES 同步修正）
CONSORT_PATRON: dict[str, str] = {
    "SHIJI_009_01": "汉高祖",
    "SHIJI_049_02": "汉景帝",
    "SHIJI_049_03": "汉文帝",
    "SHIJI_049_04": "汉文帝",
}


def apply_coord(entry: dict, patron: str, emperor_index: dict) -> None:
    if patron not in emperor_index:
        return
    info = emperor_index[patron]
    regime_index = build_regime_index()
    entry.update(coords_and_ids_from_emperor(info, regime_index))


def main() -> int:
    emperor_index = build_emperor_info_index()
    logs: list[str] = []
    touched = set()

    for vol in range(1, 90):
        for path in sorted(ANN.glob(f"01史记_{vol:03d}_*_skeleton.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for entry in data.get("entries", []):
                eid = entry.get("史略ID", "")
                text = SPINDLE_RATIONALES.get(eid)
                patron = CONSORT_PATRON.get(eid)
                if patron:
                    old = (entry.get("四级帝王坐标") or "").strip()
                    apply_coord(entry, patron, emperor_index)
                    if old != patron:
                        logs.append(f"坐标 {eid} {old} → {patron}")
                        changed = True
                if text:
                    af = dict(entry.get("_auto_filled") or {})
                    af["_坐标主轴说明"] = text
                    af.pop("_坐标主轴待说明", None)
                    entry["_auto_filled"] = af
                    needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
                    if needs:
                        entry["_needs_llm"] = needs
                    else:
                        entry.pop("_needs_llm", None)
                    logs.append(f"说明 {eid}")
                    changed = True
                    touched.add(eid)
            if changed:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    print(f"写入 {len(touched)} 条说明，坐标修正 {sum(1 for l in logs if l.startswith('坐标'))} 处")
    for ln in logs:
        print(f"  · {ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
