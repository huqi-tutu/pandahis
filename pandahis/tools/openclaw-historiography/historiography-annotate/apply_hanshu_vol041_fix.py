#!/usr/bin/env python3
"""重建汉书 041 陈胜项籍传：段落索引 + skeleton + 三字段。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from detail_coords import fill_all_detail_coords
from lib_config import paths
from paragraph_utils import count_source_paragraphs, split_paragraphs, split_mode_for_work

WORK = "02汉书"
VOL = "041"
VOLUME = "陈胜项籍传"
SOURCE_FILE = "02汉书_041_陈胜项籍传第一.txt"
SRC = paths()["sources"] / "02汉书_拆分后" / SOURCE_FILE
OLD_SK = paths()["annotations"] / "02汉书_041_陈胜传_skeleton.json"
NEW_SK = paths()["annotations"] / "02汉书_041_陈胜项籍传_skeleton.json"
IDX_PATH = paths()["paragraph_index"] / f"{WORK}_{VOL}.json"

YEAR_FIXES = {
    "HANSHU_041_01": (-209, -208, False, "秦二世元年起义至下城父被杀，前209–前208"),
    "HANSHU_041_02": (-209, -208, False, "与陈胜共起大泽乡，矫令诛于荥阳，前209–前208"),
    "HANSHU_041_03": (-209, -202, False, "会稽起兵至乌江自刭，前209–前202"),
    "HANSHU_041_04": (-209, -208, True, "定陶之战阵亡，前208"),
}


def rebuild_index() -> List[str]:
    text = SRC.read_text(encoding="utf-8")
    mode = split_mode_for_work(WORK, text)
    paras = split_paragraphs(text, mode)
    data = {
        "work": WORK,
        "vol": VOL,
        "source_file": SOURCE_FILE,
        "source_path": str(SRC.relative_to(paths()["data"])),
        "paragraph_mode": mode,
        "total": len(paras),
        "paragraphs": [{"id": i, "text": t} for i, t in enumerate(paras, 1)],
    }
    IDX_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return paras


def _owner(name: str, category: str = "士臣") -> Dict[str, str]:
    return {"name": name, "category": category}


def build_segment_attribution() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in range(1, 25):
        if p == 1:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "卷首标题"})
        elif p == 24:
            rows.append({"paragraph": p, "owners": [], "exclude_reason": "太史公曰"})
        elif p == 2:
            rows.append({"paragraph": p, "owners": [_owner("陈胜")]})
        elif p == 3:
            rows.append({"paragraph": p, "owners": [_owner("吴广")]})
        elif 4 <= p <= 8:
            rows.append({"paragraph": p, "owners": [_owner("陈胜"), _owner("吴广")]})
        elif 9 <= p <= 12:
            rows.append({"paragraph": p, "owners": [_owner("项籍"), _owner("项梁")]})
        else:
            rows.append({"paragraph": p, "owners": [_owner("项籍")]})
    return rows


def _quote(paras: List[str], lo: int, hi: int, n: int = 120) -> str:
    return "\n".join(paras[lo - 1 : hi])[:n]


def build_entries(paras: List[str]) -> List[Dict[str, Any]]:
    vol = VOLUME
    specs = [
        ("HANSHU_041_01", "陈胜", "士臣", [(2, 2), (4, 8)], "陈胜字涉，阳城人。", "P0",
         "大泽乡首义、建张楚，秦末农民战争标志性人物"),
        ("HANSHU_041_02", "吴广", "士臣", [(3, 3), (4, 8)], "吴广，字叔，阳夏人也。", "P0",
         "与陈胜共起、为假王监军，荥阳战役关键配角"),
        ("HANSHU_041_03", "项籍", "士臣", [(9, 23)], "项籍字羽，下相人也。", "P0",
         "西楚霸王，灭秦分封至垓下，列传后半主轴"),
        ("HANSHU_041_04", "项梁", "士臣", [(9, 12)], "其季父梁，梁父即楚名将项燕者也。", "P1",
         "楚将项燕之后，会稽起兵、立怀王，定陶战死"),
    ]
    entries = []
    for eid, name, cat, ranges, quote, pri, reason in specs:
        q = quote if len(quote) >= 8 else _quote(paras, ranges[0][0], ranges[-1][1])
        intro = q[:18] + ("…" if len(q) > 18 else "")
        prs = [{"volume": vol, "paragraph_from": lo, "paragraph_to": hi} for lo, hi in ranges]
        entries.append({
            "史略ID": eid,
            "史略名称": name,
            "史略分类": cat,
            "史略简介": intro,
            "主要史料出处": f"《汉书·{VOLUME}》",
            "paragraphs": prs,
            "原文字句": q[:120],
            "优先级": pri,
            "优先级判定理由": reason,
        })
    return entries


def apply_years(entries: List[Dict[str, Any]]) -> None:
    for e in entries:
        eid = e["史略ID"]
        if eid not in YEAR_FIXES:
            continue
        start, end, single, note = YEAR_FIXES[eid]
        e["史略开始年"] = start
        e["史略结束年"] = end
        if single:
            e["_年LLM依据"] = note
        else:
            e["_年LLM依据"] = note


def build_skeleton(paras: List[str]) -> Dict[str, Any]:
    return {
        "volume": VOLUME,
        "source_file": SOURCE_FILE,
        "原文路径": f"02二十四史拆分后/02汉书_拆分后/{SOURCE_FILE}",
        "total_paragraphs": len(paras),
        "volume_type": "列传",
        "audit_revision": 1,
        "segment_attribution": build_segment_attribution(),
        "entries": build_entries(paras),
    }


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"缺少原文: {SRC}")
    paras = rebuild_index()
    n, mode, _ = count_source_paragraphs(SRC, WORK)
    print(f"段落索引: {IDX_PATH.name} → {n} 段 (mode={mode})")

    data = build_skeleton(paras)
    apply_years(data["entries"])
    fill_all_detail_coords(data, work_id=WORK, json_path=str(NEW_SK))

    for e in data["entries"]:
        e.setdefault("一级文明坐标", "华夏")
        e.setdefault("二级朝代坐标", "秦" if e["史略名称"] in ("陈胜", "吴广") else "汉")
        e.setdefault("三级政权坐标", "楚" if e["史略名称"] != "项梁" else "楚")
        e.setdefault("四级帝王坐标", "秦二世" if e["史略名称"] in ("陈胜", "吴广") else "楚义帝")

    NEW_SK.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 skeleton: {NEW_SK.name} ({len(data['entries'])} 条)")

    if OLD_SK.is_file() and OLD_SK != NEW_SK:
        OLD_SK.unlink()
        print(f"删除错误命名: {OLD_SK.name}")


if __name__ == "__main__":
    main()
