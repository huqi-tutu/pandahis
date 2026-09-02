#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 03至04 索引中朝代ID与二级朝代坐标分裂（后汉书误挂三国）。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCR = ROOT / "scripts"
V2_INDEX_03_04 = ROOT / "data" / "10新标注条目" / "史略索引_03至04.json"
ONLINE_INDEX = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"

sys.path.insert(0, str(ROOT / "tools/openclaw-historiography/historiography-annotate"))
sys.path.insert(0, str(SCR))

from backfill_incomplete_entries import (  # noqa: E402
    EMPEROR_JSON,
    HOUHANSHU_COORD_DEFAULTS,
    SANGUO_COORD_DEFAULTS,
    WORK_DYNASTY_HINT,
    _build_donghan_era_patron,
    _coord_chain_mismatch,
    _enforce_work_dynasty_coords,
    _work_id,
)
from coordinate_index import build_regime_index  # noqa: E402
from emperor_year_align import load_emperor_rows  # noqa: E402
from fill_fields import build_emperor_index  # noqa: E402


def count_mismatch(entries: list[dict], *, ei: dict) -> dict[str, int]:
    stats = {"total": 0, "donghan_wrong": 0, "sanguo_wrong": 0}
    for e in entries:
        work = _work_id(e)
        if work not in WORK_DYNASTY_HINT:
            continue
        if not _coord_chain_mismatch(e, work=work, ei=ei):
            continue
        stats["total"] += 1
        if work == "03后汉书":
            stats["donghan_wrong"] += 1
        else:
            stats["sanguo_wrong"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="修复 03至04 坐标链分裂")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-sync", action="store_true", help="跳过 rebuild + MySQL")
    args = parser.parse_args()

    if not V2_INDEX_03_04.is_file():
        raise SystemExit(f"缺少索引: {V2_INDEX_03_04}")

    ei = build_emperor_index()
    ri = build_regime_index()
    em_rows = load_emperor_rows(EMPEROR_JSON)
    era_patrons = _build_donghan_era_patron(em_rows)

    entries = json.loads(V2_INDEX_03_04.read_text(encoding="utf-8"))
    before = count_mismatch(entries, ei=ei)
    print(f"修复前错位: {before['total']}（后汉书 {before['donghan_wrong']}，三国志 {before['sanguo_wrong']}）")

    logs: list[str] = []
    for i, entry in enumerate(entries):
        work = _work_id(entry)
        if work not in WORK_DYNASTY_HINT:
            continue
        if not _coord_chain_mismatch(entry, work=work, ei=ei):
            continue
        fixed = _enforce_work_dynasty_coords(
            dict(entry),
            ei=ei,
            ri=ri,
            em_rows=em_rows,
            era_patrons=era_patrons,
        )
        if _coord_chain_mismatch(fixed, work=work, ei=ei):
            logs.append(f"仍错位 {fixed.get('史略ID')} {fixed.get('史略名称')}")
        else:
            logs.append(
                f"✓ {fixed.get('史略ID')} {fixed.get('史略名称')}: "
                f"{fixed.get('四级帝王坐标')} / {fixed.get('朝代ID')}"
            )
        entries[i] = fixed

    after = count_mismatch(entries, ei=ei)
    print(f"修复后错位: {after['total']}")

    if args.dry_run:
        for line in logs[:20]:
            print(line)
        if len(logs) > 20:
            print(f"... 另有 {len(logs) - 20} 条")
        return 1 if after["total"] else 0

    V2_INDEX_03_04.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写回 → {V2_INDEX_03_04}")

    for line in logs[:15]:
        print(line)
    if len(logs) > 15:
        print(f"... 共修复 {len(logs)} 条")

    if after["total"]:
        print("❌ 仍有未修复条目")
        for line in logs:
            if line.startswith("仍错位"):
                print(line)
        return 1

    # 二次：清除后汉书误挂三国后残留的年份（>=220）并兜底
    year_fixed = 0
    for i, entry in enumerate(entries):
        if _work_id(entry) != "03后汉书":
            continue
        sy = entry.get("史略开始年")
        if sy is not None and int(sy) >= 220:
            entry["史略开始年"] = None
            entry["史略结束年"] = None
            emp = ei.get(str(entry.get("四级帝王坐标") or ""))
            from person_year_fallback import apply_person_year_fallback, write_fallback_years_to_entry, entry_has_complete_years
            if not entry_has_complete_years(entry):
                nsy, ney, level, note = apply_person_year_fallback(entry, emperor_info=emp)
                if nsy is not None:
                    write_fallback_years_to_entry(entry, nsy, ney, level, note)
            entries[i] = entry
            year_fixed += 1
    if year_fixed:
        print(f"年份纠偏: {year_fixed} 条（清除>=220后重兜底）")

    if args.dry_run:
        return 0

    V2_INDEX_03_04.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写回 → {V2_INDEX_03_04}")

    for line in logs[:15]:
        print(line)
    if len(logs) > 15:
        print(f"... 共修复坐标 {len(logs)} 条")

    if args.no_sync:
        return 0

    subprocess.run([sys.executable, str(SCR / "build_online_index.py")], check=True, cwd=str(ROOT))
    subprocess.run(
        [
            sys.executable,
            str(SCR / "import_box_index_json.py"),
            "--json",
            str(ONLINE_INDEX),
        ],
        check=True,
        cwd=str(ROOT),
    )
    print("✅ 线上索引 + historical_box 已同步")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
