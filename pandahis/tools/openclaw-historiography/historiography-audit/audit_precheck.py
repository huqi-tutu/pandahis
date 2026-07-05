#!/usr/bin/env python3
"""
Step 3 预检：可脚本化的审计指标

用法:
  python3 audit_precheck.py <skeleton.json> [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ANNOTATE_DIR = Path(__file__).resolve().parent.parent / "historiography-annotate"
sys.path.insert(0, str(ANNOTATE_DIR))

from hezhuan_attribution_gate import (  # noqa: E402
    load_paragraph_text_map,
    validate_segment_ownership,
)
from lib_config import (  # noqa: E402
    PERSON_CATS,
    VOLUME_TYPE_THRESHOLDS,
    detect_sandwich_excludes,
    detect_volume_type,
    entry_owner_set,
    owner_key,
)

errors: List[str] = []
warnings: List[str] = []
infos: List[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"  ❌ {msg}")


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"  ⚠️ {msg}")


def info(msg: str) -> None:
    infos.append(msg)
    print(f"  ℹ️ {msg}")


def report_id_gaps(data: dict, entries: list) -> List[int]:
    import re

    gaps: List[int] = []
    seq_nums: List[int] = []
    for e in entries:
        eid = e.get("史略ID", "")
        m = re.search(r"_(\d{3})_(\d{2})$", eid)
        if m:
            seq_nums.append(int(m.group(2)))
    if not seq_nums:
        return gaps
    seq_nums.sort()
    for i in range(seq_nums[0], seq_nums[-1] + 1):
        if i not in seq_nums:
            gaps.append(i)
    if gaps:
        deleted = (data.get("audit_revision") or {}).get("deleted_entry_ids", [])
        info(f"ID 序号空号（保留策略）: {gaps}" + (f"，已记录删除: {deleted}" if deleted else ""))
    return gaps


def check_orphan_owners(data: dict, owners: Set[Tuple[str, str]]) -> None:
    for row in data.get("segment_attribution", []):
        p = row.get("paragraph")
        for o in row.get("owners", []):
            key = owner_key(o.get("name", ""), o.get("category", ""))
            if key not in owners:
                err(f"段{p}: 归属 [{o.get('name')}] {o.get('category')} 在 entries 中不存在")


def check_single_owner_per_segment(data: dict, json_path: Path) -> None:
    para_text = load_paragraph_text_map(data, json_path)
    for msg in validate_segment_ownership(data, para_text):
        err(msg)


def check_legacy_categories(entries: list) -> None:
    legacy = {"事略", "典制", "民录", "论著", "君纪", "著作", "思想"}
    for e in entries:
        cat = (e.get("史略分类") or "").strip()
        if cat in legacy:
            err(f"[{e.get('史略ID')}] 含已废弃分类「{cat}」，须用君王/士臣/庶众/宗戚 重标")


def build_density_report(data: dict) -> Dict[str, Any]:
    n = data.get("total_paragraphs", 0)
    entries = data.get("entries", [])
    m = len(entries)
    ratio = round(m / n, 4) if n else 0

    vol_type, source = detect_volume_type(
        data.get("volume", ""),
        data.get("source_file", ""),
        data.get("volume_type"),
    )
    divisor = VOLUME_TYPE_THRESHOLDS.get(vol_type)
    threshold = round(n / divisor, 2) if divisor else None

    if threshold is None:
        density_result = "豁免"
    elif m >= threshold:
        density_result = "通过"
    else:
        density_result = "触发复核"
        warn(f"反密度: {m} 条 < 阈值 {threshold}（{n}/{divisor}），需逐段复核漏标")

    if m > n / 3:
        warn(f"密度警示: {m} 条 > N/3={n/3:.1f}，需逐条复核")

    return {
        "total_paragraphs": n,
        "entry_count": m,
        "density_ratio": ratio,
        "volume_type": vol_type,
        "volume_type_source": source,
        "threshold_divisor": divisor,
        "threshold_value": threshold,
        "density_result": density_result,
        "density_line": (
            f"密度：{n}段 {m}条 比率={ratio} 卷类型={vol_type} "
            f"阈值={f'{n}/{divisor}={threshold}' if threshold else '不设阈'} "
            f"结果={density_result}"
        ),
    }


def build_person_checklist(entries: list) -> Dict[str, Any]:
    by_cat: Dict[str, List[str]] = {c: [] for c in PERSON_CATS}
    for e in entries:
        cat = e.get("史略分类", "")
        if cat in by_cat:
            by_cat[cat].append(e.get("史略名称", ""))
    return {
        "by_category": by_cat,
        "note": "合传主人公、分类优先级须 LLM 按人物标注规则复核",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 3 审计预检（确定性指标）")
    parser.add_argument("json_path")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args()

    path = Path(args.json_path)
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n🔍 Step 3 预检: {data.get('volume', '未知卷')}")

    entries = data.get("entries", [])
    owners = entry_owner_set(entries)

    print("\n  📊 密度与卷类型")
    density = build_density_report(data)
    print(f"  {density['density_line']}")

    print("\n  🔗 归属一致性")
    check_orphan_owners(data, owners)
    check_single_owner_per_segment(data, path)
    check_legacy_categories(entries)
    for msg in detect_sandwich_excludes(data):
        warn(msg)

    print("\n  🔢 ID 空号")
    report_id_gaps(data, entries)

    checklist = build_person_checklist(entries)

    report = {
        "volume": data.get("volume"),
        "precheck_passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "density": density,
        "checklist_for_llm": checklist,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if errors:
        print(f"\n⛔ 预检失败 {len(errors)} 项 — 修正 JSON 并重跑后再审计")
        sys.exit(1)

    print(f"\n✅ 预检通过（{len(warnings)} 警告供 LLM 语义审计参考）")
    sys.exit(0)


if __name__ == "__main__":
    main()
