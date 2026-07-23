#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将商朝朝代知识补全二期条目（GLBL_00649–00694）并入全局索引（仅本地 JSON）。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DK_BASE = DATA / "06朝代知识补全"
INDEX_MAIN = DATA / "03索引标注条目" / "史略索引_01至02.json"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"
TOOLS = ROOT / "tools" / "openclaw-historiography"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from emperor_year_align import (  # noqa: E402
    align_junji_entry_years,
    build_emperor_indexes,
    load_emperor_rows,
)

SHANG_DYNASTY_ID = "CD_HX_SHANG"
REGIME_SHANG = "ZQ_HX_SHANG_SHANG"
ID_MIN = 649
ID_MAX = 694


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def glbl_num(entry_id: str) -> int | None:
    parts = str(entry_id).split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def load_shang_new_entries() -> list[dict]:
    entries: list[dict] = []
    for fname in ("商_事略典制论著.json", "商_人物.json"):
        path = DK_BASE / "索引条目" / fname
        if not path.is_file():
            continue
        for e in load_json(path).get("entries") or []:
            num = glbl_num(str(e.get("史略ID", "")))
            if num is not None and ID_MIN <= num <= ID_MAX:
                entries.append(e)
    entries.sort(key=lambda x: str(x.get("史略ID", "")))
    return entries


def build_shang_emperor_index() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = [
        r
        for r in load_emperor_rows(EMPEROR_JSON)
        if str(r.get("朝代ID", "")).strip() == SHANG_DYNASTY_ID
    ]
    return build_emperor_indexes(rows)


def parse_year(raw) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "-":
        return None
    if s.startswith("约"):
        s = s[1:]
    try:
        return int(s)
    except ValueError:
        return None


def normalize_entry(
    entry: dict,
    emperors_by_name: dict[str, dict],
    emperors_by_id: dict[str, dict],
) -> dict:
    e = deepcopy(entry)
    e["朝代ID"] = SHANG_DYNASTY_ID
    e["政权ID"] = REGIME_SHANG
    e.setdefault("三级政权坐标", "商")
    e.setdefault("一级文明坐标", "华夏")
    e.setdefault("二级朝代坐标", "商")
    e.setdefault("文明ID", "HX")
    e.setdefault("母本著作", "朝代补全")
    e.setdefault("来源著作", ["朝代补全"])
    e.setdefault("来源条目数", 1)
    e.setdefault("段落域数", 0)
    e.setdefault("paragraphs", [])
    e.setdefault("史略来源", "模型补全")

    name = str(e.get("史略名称", "")).strip()
    cat = str(e.get("史略分类", "")).strip()

    if cat == "君王" and not str(e.get("四级帝王坐标") or "").strip():
        e["四级帝王坐标"] = name

    emp_name = str(e.get("四级帝王坐标") or "").strip()
    emp_row = emperors_by_name.get(emp_name)

    e, _ = align_junji_entry_years(
        e,
        by_name=emperors_by_name,
        by_id=emperors_by_id,
        force=True,
    )

    if e.get("史略开始年") is None:
        e["史略开始年"] = parse_year(e.get("峰值年")) or parse_year(e.get("史略结束年"))
    if e.get("史略结束年") is None:
        e["史略结束年"] = e.get("史略开始年")

    if not str(e.get("帝王ID") or "").strip():
        if emp_row:
            e["帝王ID"] = emp_row["帝王ID"]
            e["四级帝王坐标"] = emp_row["帝王名称"]
        elif cat == "君王":
            e["帝王ID"] = f"STUB_{e['史略ID']}"
        else:
            e["帝王ID"] = f"STUB_{e['史略ID']}"

    eid = str(e.get("史略ID", ""))
    e.setdefault("母本史略ID", f"DYKN_商_{eid}")
    return e


def merge_into_main_index(entries: list[dict], *, dry_run: bool) -> tuple[int, int]:
    doc = load_json(INDEX_MAIN)
    main_entries: list[dict] = doc.get("entries") or []
    by_id = {str(e.get("史略ID", "")): i for i, e in enumerate(main_entries)}
    added, updated = 0, 0
    for e in entries:
        eid = str(e["史略ID"])
        if eid in by_id:
            if dry_run:
                updated += 1
            else:
                main_entries[by_id[eid]] = e
                updated += 1
        else:
            if not dry_run:
                main_entries.append(e)
                by_id[eid] = len(main_entries) - 1
            added += 1
    if not dry_run:
        doc["entries"] = main_entries
        save_json(INDEX_MAIN, doc)
    return added, updated


def main() -> int:
    parser = argparse.ArgumentParser(description="商朝二期补全 → 全局索引（本地）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    raw = load_shang_new_entries()
    if len(raw) != 46:
        print(f"⚠️ 预期 46 条，实际 {len(raw)} 条（GLBL_{ID_MIN:05d}–{ID_MAX:05d}）")

    missing_peak = [e["史略ID"] for e in raw if e.get("峰值年") is None]
    if missing_peak:
        print(
            f"⚠️ 缺峰值年 {len(missing_peak)} 条（建议先 enrich-all）："
            f" {', '.join(missing_peak[:6])}{'…' if len(missing_peak) > 6 else ''}"
        )

    by_name, by_id = build_shang_emperor_index()
    entries = [normalize_entry(e, by_name, by_id) for e in raw]

    if args.dry_run:
        added, updated = merge_into_main_index(entries, dry_run=True)
        print(f"[dry-run] 将新增 {added} 条，更新 {updated} 条")
        return 0

    if not args.no_backup:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup = INDEX_MAIN.with_name(f"史略索引_01至02.json.bak_{ts}")
        shutil.copy2(INDEX_MAIN, backup)
        print(f"已备份 → {backup.name}")

    added, updated = merge_into_main_index(entries, dry_run=False)
    print(f"✅ 全局索引合并完成：新增 {added} 条，更新 {updated} 条（共处理 {len(entries)} 条）")

    # 校验
    doc = load_json(INDEX_MAIN)
    in_global = sum(
        1
        for e in doc.get("entries") or []
        if str(e.get("二级朝代坐标", "")) == "商"
        and (n := glbl_num(str(e.get("史略ID", "")))) is not None
        and ID_MIN <= n <= ID_MAX
    )
    print(f"校验：全局索引中商朝二期新条 = {in_global}/46")
    return 0 if in_global == 46 else 1


if __name__ == "__main__":
    raise SystemExit(main())
