#!/usr/bin/env python3
"""汉书指定卷次质检：字段结构 + 基础内容 + 坐标 + 占位年。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from coordinate_index import (
    COORD_FIELDS,
    migrate_entry_fields,
    normalize_entry_category,
    validate_entry_coordinates,
)
from detail_coords import DETAIL_FIELDS
from emperor_resolve import build_emperor_info_index
from lib_config import VALID_CATS, VALID_PRIORITIES, coerce_year, paths
from shilue_year_resolve import emperor_accession_year, is_shilue_year_placeholder

HIST = paths()["annotations"]

REQUIRED_SKELETON = [
    "史略ID", "史略名称", "史略简介", "原文字句", "史略分类", "主要史料出处",
]
REQUIRED_FINAL = [
    "优先级", "优先级判定理由", "史略开始年", "史略结束年",
    *COORD_FIELDS, *DETAIL_FIELDS,
]


def vol_paths(start: int, end: int) -> List[Path]:
    out: List[Path] = []
    for n in range(start, end + 1):
        vol = f"{n:03d}"
        matches = sorted(HIST.glob(f"02汉书_{vol}_*_skeleton.json"))
        if matches:
            out.append(matches[0])
    return out


def audit_file(path: Path, *, phase: str = "final") -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    vol = path.name.split("_")[1]
    entries = data.get("entries") or []
    eidx = build_emperor_info_index()
    ri = None
    di = None

    field_missing: List[str] = []
    basic_errors: List[str] = []
    coord_errors: List[str] = []
    year_placeholders: List[str] = []
    cat_counter: Counter = Counter()
    issues_detail: List[str] = []

    for i, entry in enumerate(entries):
        migrate_entry_fields(entry)
        prefix = f"[{i + 1}] {entry.get('史略ID', '?')}"
        cat = normalize_entry_category(entry.get("史略分类", ""))
        cat_counter[cat or "?"] += 1

        for key in REQUIRED_SKELETON:
            if not (entry.get(key) or "").strip() if key != "史略简介" else not entry.get(key):
                field_missing.append(f"{prefix} 缺 {key}")

        if phase == "final":
            for key in REQUIRED_FINAL:
                val = entry.get(key)
                if val is None or val == "":
                    field_missing.append(f"{prefix} 缺 {key}")

        intro = entry.get("史略简介", "")
        if intro and len(intro) > 20:
            basic_errors.append(f"{prefix} 简介超20字({len(intro)})")

        cat_raw = entry.get("史略分类", "")
        if cat_raw and cat not in VALID_CATS:
            basic_errors.append(f"{prefix} 非法分类 {cat_raw}")

        pri = entry.get("优先级", "")
        if pri and pri not in VALID_PRIORITIES:
            basic_errors.append(f"{prefix} 非法优先级 {pri}")

        start = coerce_year(entry.get("史略开始年"))
        end = coerce_year(entry.get("史略结束年"))
        if start is not None and end is not None and start > end:
            basic_errors.append(f"{prefix} 年代倒置 {start}>{end}")

        if not (entry.get("原文字句") or "").strip():
            basic_errors.append(f"{prefix} 原文字句为空")

        if phase == "final" and cat in ("事略", "典制") and start is not None and end is not None:
            acc, reign_end, _ = emperor_accession_year(entry, eidx)
            if is_shilue_year_placeholder(start, end, acc, reign_end, data=data, entry=entry):
                year_placeholders.append(
                    f"{prefix} {entry.get('史略名称')} {start}～{end}（疑似占位）"
                )

        if phase == "final":
            from coordinate_index import build_dynasty_index_from_json, build_regime_index
            if ri is None:
                ri = build_regime_index()
                di = build_dynasty_index_from_json()
            for msg in validate_entry_coordinates(entry, emperor_index=eidx, regime_index=ri, dynasty_index=di):
                coord_errors.append(f"{prefix} {msg}")

        # 坐标链一致性：四级帝王与一~三级是否同链
        emp = (entry.get("四级帝王坐标") or "").strip()
        if emp and emp in eidx:
            info = eidx[emp]
            for label, field, expect_key in (
                ("文明", "一级文明坐标", "civilization"),
                ("朝代", "二级朝代坐标", "dynasty"),
                ("政权", "三级政权坐标", "regime"),
            ):
                got = (entry.get(field) or "").strip()
                exp = (info.get(expect_key) or "").strip()
                if exp and got and got != exp:
                    issues_detail.append(
                        f"{prefix} 四级「{emp}」但{label}={got}≠帝王表{exp}"
                    )

    return {
        "vol": vol,
        "file": path.name,
        "volume": data.get("volume", ""),
        "volume_type": data.get("volume_type", ""),
        "entry_count": len(entries),
        "categories": dict(cat_counter),
        "field_missing": field_missing,
        "basic_errors": basic_errors,
        "coord_errors": coord_errors,
        "coord_chain_mismatch": issues_detail,
        "year_placeholders": year_placeholders,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=11)
    parser.add_argument("--end", type=int, default=31)
    args = parser.parse_args()

    results = [audit_file(p) for p in vol_paths(args.start, args.end)]

    total_entries = sum(r["entry_count"] for r in results)
    total_field = sum(len(r["field_missing"]) for r in results)
    total_basic = sum(len(r["basic_errors"]) for r in results)
    total_coord = sum(len(r["coord_errors"]) for r in results)
    total_chain = sum(len(r["coord_chain_mismatch"]) for r in results)
    total_ph = sum(len(r["year_placeholders"]) for r in results)

    print(f"# 汉书 {args.start:03d}–{args.end:03d} 质检摘要\n")
    print(f"| 卷 | 卷名 | 条目 | 缺字段 | 基础错 | 坐标错 | 链不一致 | 占位年 |")
    print(f"|---|---|---:|---:|---:|---:|---:|---:|")
    for r in results:
        print(
            f"| {r['vol']} | {r['volume']} | {r['entry_count']} | "
            f"{len(r['field_missing'])} | {len(r['basic_errors'])} | "
            f"{len(r['coord_errors'])} | {len(r['coord_chain_mismatch'])} | "
            f"{len(r['year_placeholders'])} |"
        )
    print(
        f"\n**合计** {len(results)} 卷 / {total_entries} 条 | "
        f"缺字段 {total_field} | 基础错 {total_basic} | "
        f"坐标错 {total_coord} | 链不一致 {total_chain} | 占位年 {total_ph}\n"
    )

    for r in results:
        problems = (
            r["field_missing"] + r["basic_errors"] + r["coord_errors"]
            + r["coord_chain_mismatch"] + r["year_placeholders"]
        )
        if not problems:
            continue
        print(f"## 卷{r['vol']} {r['volume']} ({r['file']})")
        if r["field_missing"]:
            print("\n### 字段缺失")
            for line in r["field_missing"][:15]:
                print(f"- {line}")
            if len(r["field_missing"]) > 15:
                print(f"- … 另有 {len(r['field_missing']) - 15} 处")
        if r["basic_errors"]:
            print("\n### 基础错误")
            for line in r["basic_errors"][:10]:
                print(f"- {line}")
        if r["coord_errors"]:
            print("\n### 坐标校验")
            for line in r["coord_errors"][:10]:
                print(f"- {line}")
        if r["coord_chain_mismatch"]:
            print("\n### 四级坐标链不一致")
            for line in r["coord_chain_mismatch"][:10]:
                print(f"- {line}")
        if r["year_placeholders"]:
            print("\n### 年代占位")
            for line in r["year_placeholders"][:12]:
                print(f"- {line}")
            if len(r["year_placeholders"]) > 12:
                print(f"- … 另有 {len(r['year_placeholders']) - 12} 条")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
