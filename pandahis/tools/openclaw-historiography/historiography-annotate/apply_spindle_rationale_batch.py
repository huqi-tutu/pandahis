#!/usr/bin/env python3
"""批量写入跨时期士臣/民录的 _auto_filled._坐标主轴说明。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

from lib_config import (  # noqa: E402
    PERSON_SPINDLE_RATIONALE_MIN_LEN,
    detect_cross_regime_person,
    normalize_entry_category,
    person_spindle_rationale,
    paths,
    validate_person_spindle_rationale_batch,
)

# 史略ID → _坐标主轴说明（29 条待补）
SPINDLE_RATIONALES: dict[str, str] = {
    "SHIJI_071_01": "本卷叙樗里子事秦惠王至卒，主轴挂秦惠王；入周事在武王朝见共段事略。",
    "SHIJI_071_03": "本卷叙甘茂始事秦惠王，主轴挂秦惠王；武王伐宜阳及昭王奔齐见共段事略。",
    "SHIJI_073_01": "本卷以秦昭朝长平灭赵为主线，主轴挂秦昭王；活跃期取学界前294–前257。",
    "SHIJI_073_05": "本卷叙王翦灭楚等始皇朝事，主轴挂秦始皇；王离钜鹿败在二世朝见共段事略。",
    "SHIJI_074_05": "本卷以齐威王朝谏辩为主线，主轴挂齐威王；见梁惠王事见共段事略。",
    "SHIJI_075_01": "本卷以齐湣王朝相印为主线，主轴挂齐湣王；秦昭王时鸡鸣狗盗等见共段事略。",
    "SHIJI_075_08": "本卷以冯驩事孟尝君为主线，主轴挂齐湣王；活跃期取学界前310–前279。",
    "SHIJI_076_07": "本卷以虞卿说赵孝成、谋卿相为主线，主轴挂赵孝成王；活跃期取学界前310–前250。",
    "SHIJI_077_01": "本卷以魏安釐王朝窃符救赵为主线，主轴挂魏安釐王；留赵及高祖祠墓见共段事略。",
    "SHIJI_078_01": "本卷以考烈王朝令尹执政为主线，主轴挂楚考烈王；顷襄王时说秦见共段事略。",
    "SHIJI_079_01": "本卷以范睢相秦昭王为主线，主轴挂秦昭王；魏须贾折辱见共段事略。",
    "SHIJI_080_01": "本卷以燕昭王连五国伐齐为主线，主轴挂燕昭王；报惠王书见共段事略。",
    "SHIJI_084_01": "本卷以怀王朝左徒被疏为主线，主轴挂楚怀王；自沈顷襄王朝见共段事略。",
    "SHIJI_087_01": "本卷以始皇朝李斯相业为主线，主轴挂秦始皇帝；二世督责与被诛见共段事略。",
    "SHIJI_088_01": "本卷以始皇朝筑长城逐戎为主线，主轴挂秦始皇帝；沙丘蒙冤在二世朝见共段事略。",
    "SHIJI_095_01": "本卷以随高祖定天下封侯为主线，主轴挂汉高祖；活跃期取学界前242–前189。",
    "SHIJI_099_01": "本卷以高祖朝和亲献策为主线，主轴挂汉高祖；活跃期取学界前210–前180。",
    "SHIJI_099_02": "本卷以随从高祖至定礼仪为主线，主轴挂汉高祖；惠帝朝定宗庙仪法见共段事略。",
    "SHIJI_100_01": "本卷以楚汉间勇名及汉初受封为主线，主轴挂汉高祖；惠帝、文帝时事见共段事略。",
    "SHIJI_101_01": "本卷以文帝朝直谏闻名为主线，主轴挂汉文帝；景帝朝说诛晁错见共段事略。",
    "SHIJI_102_01": "本卷以文帝朝廷尉执法为主线，主轴挂汉文帝；活跃期取学界前180–前150。",
    "SHIJI_104_01": "本卷以高祖朝起事为主线，主轴挂汉高祖；文帝、景帝时事见共段事略。",
    "SHIJI_105_01": "本卷以战国行医传说为主线，周平王为年代兜底；活跃期取传说前407–前310。",
    "SHIJI_107_01": "本卷以景帝朝灌婴封魏其侯为主线，主轴挂汉景帝；武帝朝廷辩案见共段事略。",
    "SHIJI_107_03": "本卷与窦婴同传，主轴挂汉景帝；武帝朝使酒骂座见共段事略。",
    "SHIJI_110_01": "本卷以武帝朝对匈政策为主线，主轴挂汉武帝；平城之围在高祖朝见共段事略。",
    "SHIJI_112_02": "本卷以武帝朝推恩令等为主线，主轴挂汉武帝；活跃期取学界前140–前100。",
    "SHIJI_113_01": "本卷以武帝朝征南越为主线，主轴挂汉武帝；赵佗自立在秦末见共段事略。",
    "SHIJI_114_01": "本卷以武帝朝平东越为主线，主轴挂汉武帝；闽越围东瓯等汉初事见共段事略。",
    "SHIJI_115_01": "本卷以武帝朝击朝鲜为主线，主轴挂汉武帝；卫满建国在汉初见共段事略。",
    "SHIJI_116_01": "本卷以武帝朝开西南夷为主线，主轴挂汉武帝；庄蹻王滇在先楚见共段事略。",
    "SHIJI_117_01": "本卷以武帝朝作赋通西南夷为主线，主轴挂汉武帝；景帝朝琴挑卓文君见共段事略。",
}


def apply_to_skeleton(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for entry in data.get("entries", []):
        eid = entry.get("史略ID", "")
        text = SPINDLE_RATIONALES.get(eid)
        if not text:
            continue
        auto = dict(entry.get("_auto_filled") or {})
        auto["_坐标主轴说明"] = text
        auto.pop("_坐标主轴待说明", None)
        entry["_auto_filled"] = auto
        needs = [n for n in (entry.get("_needs_llm") or []) if n != "_坐标主轴说明"]
        if needs:
            entry["_needs_llm"] = needs
        else:
            entry.pop("_needs_llm", None)
        changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    ann = paths()["annotations"]
    total = 0
    touched: list[str] = []
    for path in sorted(ann.glob("01史记_*_skeleton.json")):
        n = apply_to_skeleton(path)
        if n:
            total += n
            touched.append(path.name)
    print(f"写入 {total} 条 _坐标主轴说明，涉及 {len(touched)} 卷")
    for name in touched:
        print(f"  · {name}")

    # 复检待补
    pending = 0
    for path in sorted(ann.glob("01史记_*_skeleton.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        for entry in entries:
            cat = normalize_entry_category(entry.get("史略分类", ""))
            if cat not in ("士臣", "民录"):
                continue
            if not detect_cross_regime_person(entry, entries):
                continue
            if len(person_spindle_rationale(entry)) < PERSON_SPINDLE_RATIONALE_MIN_LEN:
                pending += 1
                print(f"  ⚠️ 仍缺: {entry.get('史略ID')} {entry.get('史略名称')}")
        issues = validate_person_spindle_rationale_batch(entries)
        for msg in issues:
            print(f"  ❌ {path.name}: {msg}")

    if pending:
        print(f"\n仍待补 {pending} 条")
        return 1
    print("\n✅ 01史记 跨时期主轴说明已全部补齐")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
