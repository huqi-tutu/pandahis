#!/usr/bin/env python3
"""修复 skeleton 中误标的 exclude 段落（太史公曰续段、叙事误 exclude 等）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from exclude_content_gate import validate_skeleton_excludes
from paragraph_utils import resolve_source_file, split_paragraphs

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"

# skeleton 文件名 → 修复函数
TARGETS = [
    "01史记_038_宋微子世家第八_skeleton.json",
    "01史记_046_田敬仲完世家第十六_skeleton.json",
    "01史记_047_孔子世家第十七_skeleton.json",
    "01史记_055_留侯世家第二十五_skeleton.json",
    "01史记_056_陈丞相世家第二十六_skeleton.json",
    "01史记_057_绛侯周勃世家第二十七_skeleton.json",
    "01史记_058_梁孝王世家第二十八_skeleton.json",
    "01史记_059_五宗世家第二十九_skeleton.json",
]


def _row_map(data: dict) -> Dict[int, dict]:
    return {int(r["paragraph"]): r for r in data.get("segment_attribution") or []}


def _set_exclude(row: dict, reason: str) -> None:
    row["owners"] = []
    row["exclude_reason"] = reason


def _set_owner(row: dict, name: str, category: str) -> None:
    row["owners"] = [{"name": name, "category": category}]
    row.pop("exclude_reason", None)


def _entry_by_id(data: dict, eid: str) -> Optional[dict]:
    for e in data.get("entries") or []:
        if e.get("史略ID") == eid:
            return e
    return None


def _sync_entry_span(entry: dict, p_from: int, p_to: int) -> None:
    prs = entry.get("paragraphs") or []
    if not prs:
        return
    prs[0]["paragraph_from"] = p_from
    prs[0]["paragraph_to"] = p_to
    vol = prs[0].get("volume", "")
    entry["六级段落锚点"] = f"[P{p_from}-P{p_to}]"
    entry["原文出处"] = f"{vol}·P{p_from}-P{p_to}" if vol else f"P{p_from}-P{p_to}"


def _sync_entry_split(
    entry: dict,
    ranges: List[Tuple[int, int]],
) -> None:
    vol = (entry.get("paragraphs") or [{}])[0].get("volume", "")
    entry["paragraphs"] = [
        {"volume": vol, "paragraph_from": a, "paragraph_to": b} for a, b in ranges
    ]
    anchor = ",".join(f"[P{a}-P{b}]" for a, b in ranges)
    entry["六级段落锚点"] = anchor
    entry["原文出处"] = ",".join(
        f"{vol}·P{a}-P{b}" if vol else f"P{a}-P{b}" for a, b in ranges
    )


def fix_038(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if rows[64].get("exclude_reason") == "太史公曰":
        _set_exclude(rows[64], "其他")
        logs.append("P64 太史公曰续段 → 其他")
    return logs


def fix_046(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if rows[76].get("exclude_reason") == "太史公曰":
        _set_exclude(rows[76], "其他")
        logs.append("P76 太史公曰续段 → 其他")
    return logs


def fix_047(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if rows[107].get("exclude_reason") == "太史公曰":
        _set_owner(rows[107], "孔子", "士臣")
        logs.append("P107 孔氏后裔世系 → 归孔子")
    entry = _entry_by_id(data, "SHIJI_047_01")
    if entry:
        _sync_entry_span(entry, 1, 107)
        logs.append("孔子 entry → P1-P107")
    return logs


def fix_055(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if not rows[42].get("exclude_reason"):
        _set_exclude(rows[42], "太史公曰")
        logs.append("P42 起笔太史公曰，改 exclude")
    if rows[43].get("exclude_reason") == "太史公曰":
        _set_exclude(rows[43], "其他")
        logs.append("P43 论赞续段 → 其他")
    entry = _entry_by_id(data, "SHIJI_055_01")
    if entry:
        _sync_entry_span(entry, 1, 41)
        logs.append("张良 entry → P1-P41")
    return logs


def fix_056(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if rows[39].get("exclude_reason") == "太史公曰":
        _set_exclude(rows[39], "其他")
        logs.append("P39 论赞续段 → 其他")
    return logs


def fix_057(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if not rows[32].get("exclude_reason"):
        _set_exclude(rows[32], "太史公曰")
        logs.append("P32 起笔太史公曰，改 exclude")
    if rows[33].get("exclude_reason") == "太史公曰":
        _set_exclude(rows[33], "其他")
        logs.append("P33 论赞续段 → 其他")
    entry = _entry_by_id(data, "SHIJI_057_01")
    if entry:
        _sync_entry_span(entry, 1, 31)
        logs.append("周勃 entry → P1-P31")
    return logs


def fix_058(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if not rows[27].get("exclude_reason"):
        _set_exclude(rows[27], "太史公曰")
        logs.append("P27 起笔太史公曰，改 exclude")
    for p in (36, 37):
        if rows[p].get("exclude_reason") == "太史公曰":
            _set_owner(rows[p], "梁孝王", "君王")
            logs.append(f"P{p} 褚先生补叙叙事 → 归梁孝王")
    entry = _entry_by_id(data, "SHIJI_058_01")
    if entry:
        _sync_entry_split(entry, [(1, 26), (28, 37)])
        logs.append("梁孝王 entry → P1-P26,P28-P37（P27 太史公曰）")
    return logs


def fix_059(data: dict) -> List[str]:
    logs: List[str] = []
    rows = _row_map(data)
    if rows[46].get("exclude_reason") == "太史公曰":
        _set_owner(rows[46], "儿姁", "宗戚")
        logs.append("P46 儿姁宗支收束 → 归儿姁")
    entry = _entry_by_id(data, "SHIJI_059_01")
    if entry:
        _sync_entry_span(entry, 31, 46)
        logs.append("儿姁 entry → P31-P46")
    return logs


FIXERS: Dict[str, Callable[[dict], List[str]]] = {
    "01史记_038_宋微子世家第八_skeleton.json": fix_038,
    "01史记_046_田敬仲完世家第十六_skeleton.json": fix_046,
    "01史记_047_孔子世家第十七_skeleton.json": fix_047,
    "01史记_055_留侯世家第二十五_skeleton.json": fix_055,
    "01史记_056_陈丞相世家第二十六_skeleton.json": fix_056,
    "01史记_057_绛侯周勃世家第二十七_skeleton.json": fix_057,
    "01史记_058_梁孝王世家第二十八_skeleton.json": fix_058,
    "01史记_059_五宗世家第二十九_skeleton.json": fix_059,
}


def _para_text(skeleton_path: Path, data: dict) -> Dict[int, str]:
    src = resolve_source_file(data, skeleton_path)
    paras = split_paragraphs(src.read_text(encoding="utf-8"), mode="line")
    return {i + 1: t.strip() for i, t in enumerate(paras)}


def repair_file(path: Path) -> Tuple[bool, List[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fixer = FIXERS.get(path.name)
    if not fixer:
        return False, [f"无修复器: {path.name}"]
    logs = fixer(data)
    if not logs:
        return False, ["无需修改"]

    para_text = _para_text(path, data)
    ok, msg = validate_skeleton_excludes(data, para_text, work_id="01史记")
    if not ok:
        return False, logs + [msg.split("\n")[0]]

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, logs


def main() -> int:
    all_logs: List[str] = []
    failed = 0
    for name in TARGETS:
        path = ANN / name
        if not path.exists():
            print(f"跳过（不存在）: {name}")
            continue
        ok, logs = repair_file(path)
        if ok:
            print(f"✓ {name}")
            for ln in logs:
                print(f"    · {ln}")
            all_logs.extend(logs)
        else:
            failed += 1
            print(f"✗ {name}: {logs[-1] if logs else '失败'}")
    print(f"\n共修复 {len(TARGETS) - failed} 卷")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
