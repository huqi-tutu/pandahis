#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补全 V2/线上索引中缺少年份与四级坐标 ID 的条目，写回 V2 全局索引并重建 online。

用法：
  python3 scripts/backfill_incomplete_entries.py
  python3 scripts/backfill_incomplete_entries.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANN = ROOT / "tools/openclaw-historiography/historiography-annotate"
SCR = ROOT / "scripts"
V2_INDEX = ROOT / "data" / "10新标注条目" / "史略索引_史记汉书.json"
EMPEROR_JSON = ROOT / "data" / "01历史坐标数据" / "帝王.json"

sys.path.insert(0, str(ANN))
sys.path.insert(0, str(SCR))

from fill_fields import build_emperor_index, migrate_entry_fields, reconcile_entries_coord_ids  # noqa: E402
from coordinate_index import build_regime_index, coords_and_ids_from_emperor  # noqa: E402
from person_year_fallback import (  # noqa: E402
    apply_person_year_fallback,
    entry_has_complete_years,
    write_fallback_years_to_entry,
)
from emperor_resolve import pick_emperor_from_text  # noqa: E402
from emperor_year_align import junji_reign_years, load_emperor_rows, parse_emperor_year  # noqa: E402
from shiji_person_fallback import lookup_person_patch, resolve_person_fallback  # noqa: E402
from category_v3 import normalize_entry_category  # noqa: E402

# 扩展：按 paragraphs.source_entry_id 补年（合并 apply_llm_year_fixes_73 与汉书条目）
SOURCE_YEAR_FIXES: dict[str, tuple[int, int, str]] = {
    "SHIJI_055_01": (-250, -186, "张良生卒约前250–前186"),
    "SHIJI_054_01": (-190, -190, "曹参卒年单点（峰值年）"),
    "SHIJI_053_01": (-210, -193, "萧何生卒主流"),
    "SHIJI_056_01": (-250, -178, "陈平生卒主流"),
    "SHIJI_057_01": (-242, -169, "周勃生卒主流"),
    "SHIJI_052_04": (-180, -157, "刘将闾封齐孝王，文帝间"),
    "SHIJI_052_05": (-157, -141, "刘次景封济北王，景帝间"),
    "SHIJI_034_01": (-1046, -1043, "召公奭辅周初"),
    "SHIJI_038_04": (-1092, -1076, "微子启商末"),
    "SHIJI_077_01": (-276, -243, "信陵君魏无忌活跃期"),
    "SHIJI_129_04": (-180, -100, "任氏景武间巨商"),
    "SHIJI_128_01": (-180, -120, "卫平景武间"),
    "SHIJI_063_02": (-342, -301, "庄子与齐宣王同时代"),
    "SHIJI_041_01": (-496, -448, "范蠡事越"),
    "SHIJI_074_02": (-305, -240, "邹衍生卒约"),
    "SHIJI_045_01": (-576, -576, "韩厥晋景公时"),
    "SHIJI_057_02": (-180, -157, "周亚夫文帝景帝间"),
    "SHIJI_065_02": (-380, -316, "孙膑战国齐将"),
    "SHIJI_081_02": (-229, -229, "李牧单点（赵将）"),
    "SHIJI_081_04": (-265, -260, "赵奢活跃赵武灵王惠文王间"),
    "SHIJI_093_03": (-202, -195, "陈豨汉初反"),
    "SHIJI_039_01": (-1042, -1040, "唐叔虞封晋"),
    "SHIJI_043_04": (-298, -266, "赵惠文王在位"),
    "SHIJI_042_05": (-529, -514, "郑定公在位"),
    "SHIJI_046_02": (-374, -357, "齐桓公午在位"),
    "HANSHU_048_03": (-194, -180, "刘友赵幽王，惠帝至吕后间"),
    "HANSHU_048_04": (-194, -181, "刘恢赵共王"),
    "HANSHU_113_05": (-7, -1, "孝哀丁姬，哀帝后"),
    "HANSHU_074_05": (-74, -74, "昌邑王刘贺在位27日"),
    "HANSHU_046_02": (-178, -154, "楚王刘戊景帝吴楚之乱"),
    "HANSHU_046_03": (-77, -8, "刘向成哀间"),
    "HANSHU_046_04": (-53, 23, "刘歆新莽间"),
    "HANSHU_078_04": (-33, 33, "王䜣元帝时外戚"),
    "HANSHU_104_02": (-120, -99, "田仁"),
    "HANSHU_105_04": (-180, -120, "王孟"),
    "HANSHU_104_05": (-180, -120, "罗裒"),
    "HANSHU_105_05": (-180, -120, "薛况"),
    "HANSHU_104_04": (-180, -100, "蜀卓氏"),
    "HANSHU_109_02": (-203, -111, "南越/两粤政权跨度"),
    "HANSHU_110_01": (-138, -60, "西域诸国叙事：张骞至宣帝间"),
}

# 四级帝王锚点（source_entry_id 或 GLBL）
PATRON_BY_SOURCE: dict[str, str] = {
    "HANSHU_048_03": "吕太后",
    "HANSHU_048_04": "吕太后",
    "HANSHU_113_05": "汉哀帝",
    "HANSHU_074_05": "汉昭帝",
    "HANSHU_046_02": "汉景帝",
    "HANSHU_046_03": "汉成帝",
    "HANSHU_046_04": "王莽",
    "HANSHU_109_02": "汉武帝",
    "HANSHU_110_01": "汉武帝",
    "SHIJI_065_02": "吴王阖闾",
    "SHIJI_081_02": "赵惠文王",
    "SHIJI_081_04": "赵惠文王",
    "SHIJI_074_02": "齐宣王",
    "SHIJI_104_02": "汉武帝",
    "SHIJI_129_04": "汉武帝",
    "SHIJI_128_01": "汉武帝",
}

COORD_KEYS = ("文明ID", "朝代ID", "政权ID", "帝王ID")


def _source_entry_id(entry: dict) -> str:
    for p in entry.get("paragraphs") or []:
        sid = str(p.get("source_entry_id") or "").strip()
        if sid:
            return sid
    return ""


def _work_id(entry: dict) -> str:
    for p in entry.get("paragraphs") or []:
        if p.get("work"):
            return str(p["work"])
    src = str(entry.get("主要史料出处") or "")
    if "汉书" in src:
        return "02汉书"
    if "史记" in src:
        return "01史记"
    return ""


def _core_person_name(name: str) -> str:
    name = (name or "").strip()
    for prefix in (
        "留侯", "平阳侯", "酂侯", "户牖侯", "绛侯",
        "昌邑王", "楚王", "赵幽王", "赵共王",
    ):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _entry_incomplete(entry: dict) -> bool:
    sy = entry.get("史略开始年")
    peak = entry.get("峰值年")
    if sy is None and peak is None:
        return True
    return any(not str(entry.get(k) or "").strip() for k in COORD_KEYS)


def _apply_coords_from_patron(entry: dict, patron: str, ei: dict, ri: dict) -> None:
    if patron not in ei:
        return
    info = ei[patron]
    entry.update(coords_and_ids_from_emperor(info, ri))
    entry["四级帝王坐标"] = patron


def _apply_zhuhou(entry: dict, ei: dict, ri: dict, em_rows: list[dict]) -> dict:
    name = str(entry.get("史略名称") or "").strip()
    if name in ei:
        _apply_coords_from_patron(entry, name, ei, ri)
        row = next((r for r in em_rows if r.get("帝王名称") == name), None)
        if row:
            rs, re = junji_reign_years(row)
            if rs is not None:
                entry["史略开始年"] = rs
            if re is not None:
                entry["史略结束年"] = re
    return entry


def _apply_years_from_source(entry: dict) -> bool:
    sid = _source_entry_id(entry)
    fix = SOURCE_YEAR_FIXES.get(sid)
    if not fix:
        return False
    start, end, note = fix
    entry["史略开始年"] = start
    entry["史略结束年"] = end
    af = dict(entry.get("_auto_filled") or {})
    af["_年兜底级别"] = "补全脚本"
    af["_年LLM依据"] = note
    entry["_auto_filled"] = af
    return True


def backfill_entry(entry: dict, *, all_entries: list[dict], ei: dict, ri: dict, em_rows: list[dict]) -> tuple[dict, bool]:
    out = deepcopy(entry)
    if not _entry_incomplete(out):
        return out, False

    migrate_entry_fields(out)
    changed = True
    cat = normalize_entry_category(out.get("史略分类", ""))
    sid = _source_entry_id(out)

    _apply_years_from_source(out)

    if cat == "诸侯":
        _apply_zhuhou(out, ei, ri, em_rows)
        return out, changed

    # 坐标：patch / source patron / 文本推断
    patron = PATRON_BY_SOURCE.get(sid)
    if not patron:
        patch = lookup_person_patch(_core_person_name(str(out.get("史略名称") or "")))
        if patch:
            patron = patch["patron"]
    if not patron:
        wid = _work_id(out)
        text = f"{out.get('史略简介', '')} {out.get('原文字句', '')}"
        info, _ = pick_emperor_from_text(text, ei, work_id=wid)
        if info:
            patron = info.get("emperor") or info.get("帝王名称")
    if not patron and cat != "蕃祚":
        data = {"entries": all_entries, "volume": sid.rsplit("_", 1)[0] if sid else ""}
        fb = resolve_person_fallback(out, data, ei, work_id=_work_id(out) or "01史记")
        if fb:
            out.update(fb["coords"])
            out["四级帝王坐标"] = fb["patron"]
            if out.get("史略开始年") is None and fb.get("start") is not None:
                out["史略开始年"] = fb["start"]
                out["史略结束年"] = fb["end"]
            reconcile_entries_coord_ids([out])
            return out, changed

    if patron:
        _apply_coords_from_patron(out, patron, ei, ri)

    if cat == "蕃祚" and not patron:
        _apply_coords_from_patron(out, "汉武帝", ei, ri)

    reconcile_entries_coord_ids([out])

    if not entry_has_complete_years(out):
        emp = ei.get(str(out.get("四级帝王坐标") or ""))
        sy, ey, level, note = apply_person_year_fallback(out, emperor_info=emp)
        if sy is not None:
            write_fallback_years_to_entry(out, sy, ey, level, note)

    if out.get("史略开始年") is None and out.get("峰值年") is not None:
        p = int(out["峰值年"])
        out["史略开始年"] = p
        out["史略结束年"] = p

    return out, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="补全缺坐标/年份的 V2 条目")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild-online", action="store_true", default=True)
    parser.add_argument("--import-db", action="store_true", default=True)
    args = parser.parse_args()

    entries = json.loads(V2_INDEX.read_text(encoding="utf-8"))
    ei = build_emperor_index()
    ri = build_regime_index()
    em_rows = load_emperor_rows(EMPEROR_JSON)

    logs: list[str] = []
    still_bad: list[str] = []
    for i, entry in enumerate(entries):
        if not _entry_incomplete(entry):
            continue
        fixed, changed = backfill_entry(entry, all_entries=entries, ei=ei, ri=ri, em_rows=em_rows)
        if not changed:
            continue
        eid = fixed["史略ID"]
        bad = []
        if fixed.get("史略开始年") is None:
            bad.append("year")
        for k in COORD_KEYS:
            if not str(fixed.get(k) or "").strip():
                bad.append(k)
        if bad:
            still_bad.append(f"{eid} ({', '.join(bad)})")
        else:
            logs.append(
                f"{eid} {fixed.get('史略名称')}: "
                f"{fixed.get('四级帝王坐标')} {fixed.get('史略开始年')}~{fixed.get('史略结束年')}"
            )
        entries[i] = fixed

    print(f"补全成功: {len(logs)}")
    for line in logs:
        print(f"  ✓ {line}")
    if still_bad:
        print(f"仍不完整: {len(still_bad)}")
        for line in still_bad:
            print(f"  ✗ {line}")

    if args.dry_run:
        return 1 if still_bad else 0

    V2_INDEX.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写回 → {V2_INDEX}")

    if args.rebuild_online:
        import subprocess

        rc = subprocess.call([sys.executable, str(SCR / "build_online_index.py")])
        if rc != 0:
            return rc

    if args.import_db:
        import subprocess

        rc = subprocess.call(
            [
                sys.executable,
                str(SCR / "import_box_index_json.py"),
                "--json",
                str(ROOT / "data" / "12线上史略索引" / "史略索引_online.json"),
            ]
        )
        if rc != 0:
            return rc

    return 1 if still_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
