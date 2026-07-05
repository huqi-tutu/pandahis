#!/usr/bin/env python3
"""一次性修复 001–089：078 坐标、14 条帝王年人物、089 生卒、君王年与帝王表对齐。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from coordinate_index import build_regime_index, coords_and_ids_from_emperor
from emperor_resolve import build_emperor_info_index
from lib_config import coerce_year, normalize_entry_category

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"

# ② 生卒=帝王在位全程，清空交 LLM（078 单独处理）
CLEAR_YEARS_EIDS = {
    "SHIJI_062_02",  # 管仲
    "SHIJI_072_01",  # 魏冉
    "SHIJI_076_02",  # 虞卿
    "SHIJI_077_01",  # 魏无忌
    "SHIJI_079_01", "SHIJI_079_02",  # 范睢蔡泽
    "SHIJI_080_01",  # 乐毅
    "SHIJI_081_01", "SHIJI_081_02",
    "SHIJI_082_01",  # 田单
    "SHIJI_083_01",  # 邹阳
    "SHIJI_086_01", "SHIJI_086_02",  # 专诸曹沫
}

# ① 078 黄歇：坐标 + 学界近似生卒（令尹楚考烈世，卒前238）
HUANGXIE = {
    "eid": "SHIJI_078_01",
    "patron": "楚考烈王",
    "start": -262,
    "end": -238,
    "rationale": "本卷以令尹事楚考烈王执政为主线，四级帝王取楚考烈王；顷襄王时说秦见前段事略。",
}

# ③ 089 学界近似全生卒（生年不详取约数，卒年据史）
ZHANGER_CHENGYU = {
    "SHIJI_089_01": {"name": "张耳", "start": -270, "end": -202},
    "SHIJI_089_02": {"name": "陈馀", "start": -270, "end": -204},
}


def _ensure_auto(entry: dict) -> dict:
    af = dict(entry.get("_auto_filled") or {})
    entry["_auto_filled"] = af
    return af


def _add_needs(entry: dict, *fields: str) -> None:
    needs = list(entry.get("_needs_llm") or [])
    for f in fields:
        if f not in needs:
            needs.append(f)
    entry["_needs_llm"] = needs


def fix_huangxie(entry: dict, emperor_index: dict) -> bool:
    if entry.get("史略ID") != HUANGXIE["eid"]:
        return False
    info = emperor_index[HUANGXIE["patron"]]
    regime_index = build_regime_index()
    entry.update(coords_and_ids_from_emperor(info, regime_index))
    entry["史略开始年"] = HUANGXIE["start"]
    entry["史略结束年"] = HUANGXIE["end"]
    af = _ensure_auto(entry)
    af["_坐标主轴说明"] = HUANGXIE["rationale"]
    entry["_needs_llm"] = [n for n in (entry.get("_needs_llm") or []) if n not in (
        "史略开始年", "史略结束年", "四级帝王坐标",
        "三级政权坐标", "二级朝代坐标", "一级文明坐标",
        "文明ID", "朝代ID", "政权ID", "帝王ID", "_坐标主轴说明",
    )]
    if not entry["_needs_llm"]:
        entry.pop("_needs_llm", None)
    return True


def clear_person_years(entry: dict) -> bool:
    eid = entry.get("史略ID", "")
    if eid not in CLEAR_YEARS_EIDS:
        return False
    entry.pop("史略开始年", None)
    entry.pop("史略结束年", None)
    _add_needs(entry, "史略开始年", "史略结束年")
    af = _ensure_auto(entry)
    af["_年待LLM"] = "须据史学界主流观点填写生卒，勿用帝王在位年替代"
    return True


def fix_zhanger_chengyu(entry: dict) -> bool:
    eid = entry.get("史略ID", "")
    spec = ZHANGER_CHENGYU.get(eid)
    if not spec:
        return False
    entry["史略开始年"] = spec["start"]
    entry["史略结束年"] = spec["end"]
    af = _ensure_auto(entry)
    af.pop("_年待LLM", None)
    entry["_needs_llm"] = [n for n in (entry.get("_needs_llm") or []) if n not in (
        "史略开始年", "史略结束年",
    )]
    if not entry["_needs_llm"]:
        entry.pop("_needs_llm", None)
    return True


def sync_junwang_years(entry: dict, emperor_index: dict) -> bool:
    if normalize_entry_category(entry.get("史略分类", "")) != "君王":
        return False
    emp = (entry.get("四级帝王坐标") or entry.get("史略名称") or "").strip()
    if emp not in emperor_index:
        return False
    info = emperor_index[emp]
    es, ee = info.get("start_year"), info.get("end_year")
    if es is None or ee is None:
        return False
    cur_s = coerce_year(entry.get("史略开始年"))
    cur_e = coerce_year(entry.get("史略结束年"))
    if cur_s == es and cur_e == ee:
        return False
    entry["史略开始年"] = int(es)
    entry["史略结束年"] = int(ee)
    af = _ensure_auto(entry)
    af["_年修正"] = f"君王年与帝王表对齐：{cur_s}～{cur_e} → {es}～{ee}"
    return True


def main() -> int:
    emperor_index = build_emperor_info_index()
    logs: list[str] = []

    for vol in range(1, 90):
        vz = f"{vol:03d}"
        for path in sorted(ANN.glob(f"01史记_{vz}_*_skeleton.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for entry in data.get("entries", []):
                if fix_huangxie(entry, emperor_index):
                    logs.append(f"① {path.name} 黄歇 坐标→楚考烈王 生卒{HUANGXIE['start']}～{HUANGXIE['end']}")
                    changed = True
                if clear_person_years(entry):
                    logs.append(f"② {path.name} {entry.get('史略ID')} 清空生卒→LLM")
                    changed = True
                if fix_zhanger_chengyu(entry):
                    logs.append(f"③ {path.name} {entry.get('史略ID')} 生卒已设学界近似")
                    changed = True
                if sync_junwang_years(entry, emperor_index):
                    logs.append(
                        f"⑤ {path.name} {entry.get('史略ID')} {entry.get('史略名称')} "
                        f"君王年←帝王表"
                    )
                    changed = True
            if changed:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    print(f"共修改 {len(logs)} 处:\n")
    for ln in logs:
        print(f"  {ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
