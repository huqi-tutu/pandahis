#!/usr/bin/env python3
"""按最新坐标/年份规则复核史记 031–089 逐条史略。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from coordinate_index import (
    COORD_FIELDS,
    COORD_ID_FIELDS,
    build_dynasty_index_from_json,
    build_regime_index,
    migrate_entry_fields,
    validate_entry_coordinates,
)
from emperor_resolve import build_emperor_info_index
from lib_config import (
    coerce_year,
    detect_cross_regime_person,
    normalize_entry_category,
    person_spindle_rationale,
    validate_entry_years,
    validate_person_spindle_rationale_batch,
    validate_year_quality,
)

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"

# 外戚册立之君 / 宗戚配偶轴（已知应挂轴）
CONSORT_PATRON: Dict[str, str] = {
    "SHIJI_009_01": "汉高祖",  # 吕太后，高祖皇后
    "SHIJI_049_01": "汉武帝",  # 卫子夫，武帝皇后
    "SHIJI_049_02": "汉景帝",  # 王太后（王娡），景帝妃
    "SHIJI_049_03": "汉文帝",  # 窦太后，文帝皇后
    "SHIJI_049_04": "汉文帝",  # 薄太后，文帝生母
    "SHIJI_049_05": "汉文帝",
    "SHIJI_059_01": "汉景帝",
    "SHIJI_059_04": "汉景帝",
    "SHIJI_059_05": "汉景帝",
}

# 士臣主轴帝王（人工规则锚点，用于明显误挂检测）
PERSON_PATRON_HINT: Dict[str, str] = {
    "SHIJI_078_01": "楚考烈王",
    "SHIJI_087_01": "秦始皇",
    "SHIJI_088_01": "秦始皇",
    "SHIJI_055_01": "汉高祖",
    "SHIJI_056_01": "汉高祖",
    "SHIJI_057_01": "汉高祖",
}

CLEAR_YEARS_EIDS: set[str] = set()  # 已填学界主流年，不再要求清空

Issue = Tuple[str, str, str]  # severity, eid, message


def _paths_031_089() -> List[Path]:
    out: List[Path] = []
    for vol in range(31, 90):
        out.extend(sorted(ANN.glob(f"01史记_{vol:03d}_*_skeleton.json")))
    return out


def _audit_person_emperor_reign_years(entry: dict, emperor_index: dict) -> List[str]:
    """人物生卒与四级帝王在位年完全一致 → 疑似帝王在位年替代生卒。"""
    cat = normalize_entry_category(entry.get("史略分类", ""))
    if cat not in ("士臣", "庶众", "宗戚"):
        return []
    eid = entry.get("史略ID", "")
    if eid in CLEAR_YEARS_EIDS:
        return []  # 已清空待 LLM
    emp = (entry.get("四级帝王坐标") or "").strip()
    info = emperor_index.get(emp)
    if not info:
        return []
    es, ee = coerce_year(entry.get("史略开始年")), coerce_year(entry.get("史略结束年"))
    rs, re = info.get("start_year"), info.get("end_year")
    if es is None or ee is None or rs is None or re is None:
        return []
    if es == int(rs) and ee == int(re) and es != ee:
        return [f"生卒 {es}～{ee} 与四级帝王「{emp}」在位年完全一致，疑似帝王在位年替代生卒"]
    return []


def audit_volume(path: Path, emperor_index: dict, regime_index: dict, dynasty_index: dict) -> List[Issue]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    for e in entries:
        migrate_entry_fields(e)

    issues: List[Issue] = []
    vol = path.name

    for entry in entries:
        eid = entry.get("史略ID", "?")
        name = entry.get("史略名称", "?")

        for msg in validate_entry_coordinates(
            entry,
            emperor_index=emperor_index,
            regime_index=regime_index,
            dynasty_index=dynasty_index,
        ):
            issues.append(("ERROR", eid, msg))

        for msg in validate_entry_years(entry):
            issues.append(("ERROR", eid, msg))

        for msg in validate_person_spindle_rationale_batch([entry]):
            _ = msg
        # batch per entry below

        for msg in _audit_person_emperor_reign_years(entry, emperor_index):
            issues.append(("WARN", eid, msg))

        if eid in CONSORT_PATRON:
            expect = CONSORT_PATRON[eid]
            actual = (entry.get("四级帝王坐标") or "").strip()
            if actual != expect:
                issues.append((
                    "ERROR", eid,
                    f"外戚册立之君应为「{expect}」，现为「{actual}」",
                ))

        if eid in PERSON_PATRON_HINT:
            expect = PERSON_PATRON_HINT[eid]
            actual = (entry.get("四级帝王坐标") or "").strip()
            if actual != expect:
                issues.append((
                    "WARN", eid,
                    f"主轴帝王建议「{expect}」，现为「{actual}」",
                ))

        if eid in CLEAR_YEARS_EIDS:
            if entry.get("史略开始年") is not None or entry.get("史略结束年") is not None:
                issues.append(("ERROR", eid, "应清空生卒待 LLM，但仍存在年份"))
            needs = set(entry.get("_needs_llm") or [])
            if "史略开始年" not in needs or "史略结束年" not in needs:
                issues.append(("WARN", eid, "待 LLM 条目缺少 _needs_llm 年字段标记"))

        reason = detect_cross_regime_person(entry, entries)
        if reason and len(person_spindle_rationale(entry)) < 8:
            issues.append(("ERROR", eid, f"跨时期缺 _坐标主轴说明：{reason}"))

    for msg in validate_year_quality(entries):
        eid = msg.split("]")[0].replace("[", "")
        issues.append(("WARN", eid, msg))

    for msg in validate_person_spindle_rationale_batch(entries):
        eid = msg.split("]")[0].replace("[", "") if "]" in msg else "?"
        issues.append(("ERROR", eid, msg))

    return issues


def main() -> int:
    emperor_index = build_emperor_info_index()
    regime_index = build_regime_index()
    dynasty_index = build_dynasty_index_from_json()
    paths = _paths_031_089()
    if not paths:
        print("未找到 031–089 skeleton")
        return 1

    all_issues: List[Issue] = []
    by_sev: Dict[str, int] = defaultdict(int)
    entry_count = 0

    for path in paths:
        vol_issues = audit_volume(path, emperor_index, regime_index, dynasty_index)
        data = json.loads(path.read_text(encoding="utf-8"))
        entry_count += len(data.get("entries") or [])
        for iss in vol_issues:
            all_issues.append(iss)
            by_sev[iss[0]] += 1

    print(f"复核范围: 史记 031–089，{len(paths)} 卷，{entry_count} 条史略")
    print(f"问题: ERROR {by_sev['ERROR']}，WARN {by_sev['WARN']}")

    if not all_issues:
        print("\n✓ 全部通过")
        return 0

    print("\n--- ERROR ---")
    for sev, eid, msg in sorted(all_issues):
        if sev != "ERROR":
            continue
        print(f"  [{eid}] {msg}")

    print("\n--- WARN ---")
    for sev, eid, msg in sorted(all_issues):
        if sev != "WARN":
            continue
        print(f"  [{eid}] {msg}")

    return 1 if by_sev["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
