#!/usr/bin/env python3
"""汉书质检剩余问题一次性修复。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ANN = ROOT / "data" / "03索引标注条目"
PI = ANN / "段落索引"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

JI_YEARS = {
    "001": ("汉高祖", -202, -195, "据《汉书·高帝纪》，刘邦于公元前202年即皇帝位，公元前195年崩，葬长陵。"),
    "002": ("汉高祖", -202, -195, "据《汉书·高帝纪》，刘邦于公元前202年即皇帝位，公元前195年崩，葬长陵。"),
    "003": ("汉惠帝", -195, -188, "据《汉书·惠帝纪》，刘盈于公元前195年即位，公元前188年崩，葬安陵。"),
    "004": ("吕太后", -241, -180, "据《汉书·高后纪》及《史记》，吕后约生于公元前241年，惠帝崩后临朝称制，吕后八年（前180年）崩。"),
    "005": ("汉文帝", -180, -157, "据《汉书·文帝纪》，刘恒于公元前180年即位，公元前157年崩，葬霸陵。"),
    "006": ("汉景帝", -157, -141, "据《汉书·景帝纪》，刘启于公元前157年即位，公元前141年崩，葬阳陵。"),
    "007": ("汉武帝", -141, -87, "据《汉书·武帝纪》，刘彻于公元前141年即位，公元前87年崩，葬茂陵。"),
    "008": ("汉昭帝", -87, -74, "据《汉书·昭帝纪》，刘弗陵于公元前87年即位，公元前74年崩，葬平陵。"),
    "009": ("汉宣帝", -74, -49, "据《汉书·宣帝纪》，刘询于公元前74年即位，公元前49年崩，葬杜陵。"),
    "010": ("汉元帝", -49, -33, "据《汉书·元帝纪》，刘奭于公元前49年即位，公元前33年崩，葬渭陵。"),
    "011": ("汉成帝", -33, -7, "据《汉书·成帝纪》，刘骜于公元前33年即位，公元前7年崩，葬延陵。"),
    "012": ("汉哀帝", -7, -1, "据《汉书·哀帝纪》，刘欣于公元前7年即位，公元前1年崩，葬义陵。"),
    "013": ("汉平帝", -1, 5, "据《汉书·平帝纪》，刘衎于公元前1年即位，公元5年崩，葬康陵。"),
}


def para_text(vol: str, pid: int) -> str:
    data = json.loads((PI / f"02汉书_{vol}.json").read_text(encoding="utf-8"))
    for p in data["paragraphs"]:
        if p.get("id") == pid:
            return p.get("text", "")
    return ""


def quote_from_para(text: str, min_len: int = 20) -> str:
    t = re.sub(r"[\s\u200b\u3000]+", "", text)
    return t[: max(min_len, 60)] if len(t) >= min_len else t


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fix_ji_volumes() -> None:
    for vol, (name, start, end, basis) in JI_YEARS.items():
        matches = sorted(ANN.glob(f"02汉书_{vol}_*_skeleton.json"))
        if not matches:
            continue
        path = matches[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        for e in data.get("entries", []):
            if e.get("史略名称") != name:
                continue
            e["史略开始年"] = start
            e["史略结束年"] = end
            af = dict(e.get("_auto_filled") or {})
            af.pop("_年待LLM", None)
            af["_年LLM依据"] = basis
            e["_auto_filled"] = af
        kp = dict(data.get("knowledge_provenance") or {})
        kp["step4"] = {"source": "llm", "at": NOW}
        data["knowledge_provenance"] = kp
        save(path, data)


def fix_044() -> None:
    path = ANN / "02汉书_044_韩彭英卢吴传第四_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for seg in data["segment_attribution"]:
        if seg.get("paragraph") == 25:
            for ow in seg.get("owners") or []:
                if ow.get("name") == "吴芮":
                    ow["category"] = "武将"
    save(path, data)


def fix_046() -> None:
    path = ANN / "02汉书_046_楚元王传第六_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e.get("史略ID") == "HANSHU_046_01":
            e["五级细坐标"] = "汉书·卷046·宗戚·01"
    save(path, data)


def fix_053() -> None:
    path = ANN / "02汉书_053_郦陆朱刘叔孙传第十三_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e.get("史略ID") != "HANSHU_053_03":
            continue
        e["四级帝王坐标"] = "汉文帝"
        e["帝王ID"] = "DW_HX_XIHAN_XIHAN_HANWENDI"
        af = dict(e.get("_auto_filled") or {})
        af["_坐标主轴说明"] = "朱建主要事迹在吕后临朝时助陈平安刘，然卒于文帝三年；文臣四级坐标取卒年所在之君汉文帝。"
        e["_auto_filled"] = af
    save(path, data)


def fix_116() -> None:
    path = ANN / "02汉书_116_王莽传第六十九中_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    pt = para_text("116", 3)
    for e in data["entries"]:
        if e.get("史略ID") == "HANSHU_116_01":
            e["原文字句"] = quote_from_para(pt)
    save(path, data)


def fix_092() -> None:
    path = ANN / "02汉书_092_宣元六王传第五十_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    pt = para_text("092", 3)
    for e in data["entries"]:
        if e.get("史略ID") == "HANSHU_092_06":
            e["原文字句"] = quote_from_para(pt)
    save(path, data)


def main() -> None:
    fix_044()
    fix_046()
    fix_053()
    fix_116()
    fix_092()
    fix_ji_volumes()
    print("done: 044/046/053/116/092 + 001-013")


if __name__ == "__main__":
    main()
