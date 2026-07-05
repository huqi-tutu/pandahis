#!/usr/bin/env python3
"""汉书质检 P0/P1 批量修复（061/043/112/044/045/046/002-013/分卷原文字句）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
ANN = ROOT / "data" / "03索引标注条目"
PI = ANN / "段落索引"
EMP = Path(__file__).resolve().parent.parent / "reference" / "帝王.json"

EMPEROR_YEARS = {
    "汉高祖": (-202, -195),
    "汉惠帝": (-195, -188),
    "汉文帝": (-180, -157),
    "汉景帝": (-157, -141),
    "汉武帝": (-141, -87),
    "汉昭帝": (-87, -74),
    "汉宣帝": (-74, -49),
    "汉元帝": (-49, -33),
    "汉成帝": (-33, -7),
    "汉哀帝": (-7, -1),
    "汉平帝": (-1, 5),
    "吕太后": (-188, -180),  # 临朝称制
}

EMPEROR_IDS = {
    "秦始皇": "DW_HX_QIN_QIN_QINSHIHUANG",
    "汉高祖": "DW_HX_XIHAN_XIHAN_HANGAOZU",
}


def para_text(vol: str, pid: int) -> str:
    data = json.loads((PI / f"02汉书_{vol}.json").read_text(encoding="utf-8"))
    for p in data["paragraphs"]:
        if p.get("id") == pid:
            return p.get("text", "")
    return ""


def quote_from_para(text: str, min_len: int = 12) -> str:
    t = re.sub(r"[\s\u200b\u3000]+", "", text)
    return t[: max(min_len, 20)] if len(t) >= min_len else t


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fix_061() -> None:
    path = ANN / "02汉书_061_贾邹枚路传第二十一_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = {
        "贾山": (2, 6),
        "邹阳": (7, 15),
        "枚乘": (16, 19),
        "路温舒": (20, 22),
    }
    for seg in data["segment_attribution"]:
        p = seg.get("paragraph")
        if not p or seg.get("exclude_reason"):
            continue
        for name, (a, b) in blocks.items():
            if a <= p <= b:
                seg["owners"] = [{"name": name, "category": "文臣"}]
                break
    id_map = {
        "HANSHU_061_02": "贾山",
        "HANSHU_061_04": "邹阳",
        "HANSHU_061_01": "枚乘",
        "HANSHU_061_03": "路温舒",
    }
    for e in data["entries"]:
        name = id_map.get(e["史略ID"])
        if not name:
            continue
        a, b = blocks[name]
        pt = para_text("061", a)
        e["paragraphs"] = [{"volume": "贾邹枚路传", "paragraph_from": a, "paragraph_to": b}]
        e["原文字句"] = quote_from_para(pt)
        e["六级段落锚点"] = f"[P{a}-P{b}]"
        e["原文出处"] = f"贾邹枚路传·P{a}-P{b}"
    save(path, data)


def fix_043() -> None:
    path = ANN / "02汉书_043_魏豹田儋韩王信传第三_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = {"魏豹": (2, 2), "田儋": (3, 6), "韩王信": (7, 9)}
    coords = {
        "魏豹": ("秦始皇", "秦", "CD_HX_QIN", "ZQ_HX_QIN_QIN", EMPEROR_IDS["秦始皇"]),
        "田儋": ("秦始皇", "秦", "CD_HX_QIN", "ZQ_HX_QIN_QIN", EMPEROR_IDS["秦始皇"]),
        "韩王信": ("汉高祖", "西汉", "CD_HX_XIHAN", "ZQ_HX_XIHAN_XIHAN", EMPEROR_IDS["汉高祖"]),
    }
    for seg in data["segment_attribution"]:
        p = seg.get("paragraph")
        if not p or seg.get("exclude_reason"):
            continue
        for name, (a, b) in blocks.items():
            if a <= p <= b:
                seg["owners"] = [{"name": name, "category": "武将"}]
                break
    for e in data["entries"]:
        name = e["史略名称"]
        a, b = blocks[name]
        emp, regime, did, rid, dwid = coords[name]
        pt = para_text("043", a)
        e["paragraphs"] = [{"volume": "魏豹田儋韩王信传", "paragraph_from": a, "paragraph_to": b}]
        e["原文字句"] = quote_from_para(pt)
        e["四级帝王坐标"] = emp
        e["三级政权坐标"] = regime
        e["二级朝代坐标"] = regime if regime != "秦" else "秦"
        e["朝代ID"] = did
        e["政权ID"] = rid
        e["帝王ID"] = dwid
        e["六级段落锚点"] = f"[P{a}-P{b}]"
        e["原文出处"] = f"魏豹田儋韩王信传·P{a}-P{b}"
        af = e.setdefault("_auto_filled", {})
        af["_坐标主轴说明"] = f"{name}事迹主轴在{emp}时期，四级帝王取册封/命官之君{emp}。"
    save(path, data)


def fix_112_lvtaihou() -> None:
    path = ANN / "02汉书_112_外戚传第六十七上_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e.get("史略名称") != "吕太后":
            continue
        e["四级帝王坐标"] = "汉高祖"
        e["帝王ID"] = EMPEROR_IDS["汉高祖"]
        e["三级政权坐标"] = "西汉"
        af = e.setdefault("_auto_filled", {})
        af["_坐标主轴说明"] = "吕后为汉高祖皇后，册封于高祖；四级帝王取册封之君汉高祖。"
    save(path, data)


def fix_004_lvtaihou() -> None:
    path = ANN / "02汉书_004_高后纪第三_skeleton.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data.get("entries") or []:
        if e.get("史略名称") == "吕太后":
            e["四级帝王坐标"] = "汉高祖"
            e["帝王ID"] = EMPEROR_IDS["汉高祖"]
            e["史略开始年"] = -188
            e["史略结束年"] = -180
            e.pop("_needs_llm", None)
    save(path, data)


def fix_044_wurui() -> None:
    path = ANN / "02汉书_044_韩彭英卢吴传第四_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e.get("史略名称") != "吴芮":
            continue
        e["史略分类"] = "武将"
        e["四级帝王坐标"] = "汉高祖"
        e["帝王ID"] = EMPEROR_IDS["汉高祖"]
        e["三级政权坐标"] = "西汉"
        e["五级细坐标"] = re.sub(r"君王", "武将", e.get("五级细坐标", ""))
        af = e.setdefault("_auto_filled", {})
        af["_坐标主轴说明"] = "吴芮封长沙王于高祖五年，四级帝王取册封之君汉高祖。"
    for m in data.get("protagonists_manifest") or []:
        if m.get("name") == "吴芮":
            m["category"] = "武将"
    save(path, data)


def fix_045_jingwang() -> None:
    path = ANN / "02汉书_045_荆燕吴传第五_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e.get("史略名称") == "荆王":
            e["三级政权坐标"] = "西汉"
            e["政权ID"] = "ZQ_HX_XIHAN_XIHAN"
    save(path, data)


def fix_046_liujiao() -> None:
    path = ANN / "02汉书_046_楚元王传第六_skeleton.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for seg in data["segment_attribution"]:
        for o in seg.get("owners") or []:
            if o.get("name") == "楚元王":
                o["name"] = "刘交"
    for e in data["entries"]:
        if e.get("史略名称") == "楚元王":
            e["史略名称"] = "刘交"
            if e.get("史略简介") == "刘交":
                e["史略简介"] = "楚元王刘交，高祖同父少弟，封楚王。"
    for m in data.get("protagonists_manifest") or []:
        if m.get("name") == "刘交":
            m["category"] = "宗戚"
    save(path, data)


def fix_ji_years() -> None:
    vol_emperor = {
        "002": "汉高祖",
        "003": "汉惠帝",
        "004": "吕太后",
        "005": "汉文帝",
        "006": "汉景帝",
        "007": "汉武帝",
        "008": "汉昭帝",
        "009": "汉宣帝",
        "010": "汉元帝",
        "011": "汉成帝",
        "012": "汉哀帝",
        "013": "汉平帝",
    }
    for vol, emp_name in vol_emperor.items():
        matches = list(ANN.glob(f"02汉书_{vol}_*_skeleton.json"))
        if not matches:
            continue
        path = matches[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        sy, ey = EMPEROR_YEARS[emp_name]
        for e in data.get("entries") or []:
            e["史略开始年"] = sy
            e["史略结束年"] = ey
            if emp_name == "吕太后":
                e["四级帝王坐标"] = "汉高祖"
                e["帝王ID"] = EMPEROR_IDS["汉高祖"]
            e.pop("_needs_llm", None)
            llm = e.get("_needs_llm")
            if isinstance(llm, list):
                e["_needs_llm"] = [x for x in llm if x not in ("史略开始年", "史略结束年")]
                if not e["_needs_llm"]:
                    e.pop("_needs_llm")
        save(path, data)


def fix_split_volume_quotes() -> None:
    fixes = {
        "100": 3,
        "108": 3,
        "109": 3,
        "110": 3,
        "111": 3,
        "113": 3,
        "117": 3,
        "118": 3,
        "119": 3,
    }
    for vol, pid in fixes.items():
        matches = list(ANN.glob(f"02汉书_{vol}_*_skeleton.json"))
        if not matches:
            continue
        path = matches[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        pt = para_text(vol, pid)
        if not pt or len(pt) < 12:
            continue
        for e in data.get("entries") or []:
            quote = (e.get("原文字句") or "").strip()
            if re.match(r"^[\u4e00-\u9fff]{0,6}传第", quote) or quote.startswith("卷") or "传第六" in quote[:12]:
                e["原文字句"] = quote_from_para(pt, 20)
        save(path, data)


def main() -> None:
    fix_061()
    fix_043()
    fix_112_lvtaihou()
    fix_004_lvtaihou()
    fix_044_wurui()
    fix_045_jingwang()
    fix_046_liujiao()
    fix_ji_years()
    fix_split_volume_quotes()
    print("repair_hanshu_qa_batch done")


if __name__ == "__main__":
    main()
