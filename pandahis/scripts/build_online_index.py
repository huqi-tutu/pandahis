#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建线上史略索引：V2 提取 + 06 朝代知识补全（不写 V1）。

合并规则（按 史略ID）：
  1. V2 条目优先（史记汉书 + 03至04 一期标注）；同 ID 在 06 中的重复拷贝丢弃。
  2. 仅存在于 06 的条目并入（含春秋人物 GLBL_01021–01086 共 66 条）。
  3. V1 不参与合并。

产出：data/12线上史略索引/史略索引_online.json
报告：data/12线上史略索引/merge_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
V2_INDEX_03_04 = DATA / "10新标注条目" / "史略索引_03至04.json"
DK_ENTRIES = DATA / "06朝代知识补全" / "索引条目"
OUT_DIR = DATA / "12线上史略索引"
OUT_INDEX = OUT_DIR / "史略索引_online.json"
OUT_REPORT = OUT_DIR / "merge_report.json"
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
from entry_source import infer_entry_source, normalize_entry_source  # noqa: E402
from category_normalize import normalize_entries  # noqa: E402

# 同 ID 时以 V2 为准（实测 11 条，06 为人物包内重复镜像）
V2_WINS_OVER_06_IDS = frozenset({
    "GLBL_00103",  # 秦始皇
    "GLBL_00221",  # 优旃
    "GLBL_00230",  # 卓氏
    "GLBL_00249",  # 陈胜
    "GLBL_00271",  # 公仪休
    "GLBL_00297",  # 吕不韦
    "GLBL_00368",  # 李斯
    "GLBL_00479",  # 韩非
    "GLBL_00522",  # 王翦
    "GLBL_00524",  # 田儋
    "GLBL_00532",  # 蒙恬
})

CHUNQIU_PERSON_ID_MIN = 1021
CHUNQIU_PERSON_ID_MAX = 1086

JUNWANG_EMPEROR_ID: dict[str, str] = {
    "炎帝": "DW_HX_WUDI_WUDI_YANDI",
    "少昊": "DW_HX_WUDI_WUDI_SHAOHAO",
}


def parse_year(raw: str | int | None) -> int | None:
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


def glbl_num(entry_id: str) -> int | None:
    parts = str(entry_id).split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def load_v2_entries() -> list[dict]:
    rows: list[dict] = []
    for path in (V2_INDEX, V2_INDEX_03_04):
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(doc, list):
            rows.extend(doc)
        elif isinstance(doc, dict):
            rows.extend(doc.get("entries") or [])
    return rows


def load_dk_entries() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(DK_ENTRIES.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            rows.append(deepcopy(e))
    return rows


def build_emperor_name_index() -> tuple[dict[str, dict], dict[str, dict]]:
    return build_emperor_indexes(load_emperor_rows(EMPEROR_JSON))


def normalize_supplement_entry(
    entry: dict,
    emperors_by_name: dict[str, dict],
    emperors_by_id: dict[str, dict],
) -> dict:
    """06 模型补全条目入库前规范化（与 sync_incremental 对齐）。"""
    e = deepcopy(entry)
    e.setdefault("母本著作", "朝代补全")
    e.setdefault("来源著作", ["朝代补全"])
    e.setdefault("来源条目数", 1)
    e.setdefault("段落域数", 0)
    e.setdefault("paragraphs", [])
    e.setdefault("史略来源", "模型补全")

    name = str(e.get("史略名称", "")).strip()
    cat = str(e.get("史略分类", "")).strip()

    if cat == "君王" and not e.get("帝王ID"):
        e["四级帝王坐标"] = name
        e["帝王ID"] = JUNWANG_EMPEROR_ID.get(name, "")

    emp_name = str(e.get("四级帝王坐标") or "").strip()
    emp_row = emperors_by_name.get(emp_name)
    if emp_row and not e.get("帝王ID"):
        e["帝王ID"] = emp_row["帝王ID"]
        e["四级帝王坐标"] = emp_row["帝王名称"]

    e, _ = align_junji_entry_years(
        e, by_name=emperors_by_name, by_id=emperors_by_id, force=True
    )

    if e.get("史略开始年") is None:
        e["史略开始年"] = parse_year(e.get("峰值年"))
    if e.get("史略结束年") is None:
        e["史略结束年"] = e.get("史略开始年")

    if e.get("史略开始年") is None:
        dynasty = str(e.get("朝代ID", ""))
        e["史略开始年"] = -2600 if dynasty == "CD_HX_WUDI" else -2000
    if e.get("史略结束年") is None:
        e["史略结束年"] = e["史略开始年"]

    e.setdefault("四级帝王坐标", emp_name or (name if cat == "君王" else ""))
    if not e.get("帝王ID"):
        if cat == "君王":
            e["帝王ID"] = JUNWANG_EMPEROR_ID.get(name, f"STUB_{e['史略ID']}")
        elif emp_row:
            e["帝王ID"] = emp_row["帝王ID"]
        else:
            e["帝王ID"] = f"STUB_{e['史略ID']}"

    return normalize_entry_source(e)


def merge_online_index() -> tuple[list[dict], dict]:
    v2_list = load_v2_entries()
    dk_list = load_dk_entries()
    emperors_by_name, emperors_by_id = build_emperor_name_index()

    by_id: dict[str, dict] = {}
    for e in v2_list:
        eid = str(e["史略ID"])
        by_id[eid] = normalize_entry_source(deepcopy(e))

    skipped_06_same_id: list[str] = []
    added_from_06: list[str] = []
    chunqiu_person_added: list[str] = []

    for e in dk_list:
        eid = str(e["史略ID"])
        if eid in by_id:
            skipped_06_same_id.append(eid)
            continue
        normalized = normalize_supplement_entry(e, emperors_by_name, emperors_by_id)
        by_id[eid] = normalized
        added_from_06.append(eid)
        num = glbl_num(eid)
        if num is not None and CHUNQIU_PERSON_ID_MIN <= num <= CHUNQIU_PERSON_ID_MAX:
            chunqiu_person_added.append(eid)

    merged = sorted(by_id.values(), key=lambda x: str(x["史略ID"]))
    merged, cat_log = normalize_entries(merged)

    overlap = set(skipped_06_same_id)
    report = {
        "schema": "online-index-merge-report/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "v2_index": str(V2_INDEX),
            "v2_index_03_04": str(V2_INDEX_03_04),
            "dk_entries_dir": str(DK_ENTRIES),
        },
        "counts": {
            "v2_input": len(v2_list),
            "v2_shiji_hanshu": sum(
                1 for e in v2_list if str(e.get("史略ID", "")) <= "GLBL_01121"
            ),
            "v2_03_04": sum(
                1 for e in v2_list if str(e.get("史略ID", "")) >= "GLBL_01122"
            ),
            "dk_input": len(dk_list),
            "merged_total": len(merged),
            "skipped_06_same_id_as_v2": len(skipped_06_same_id),
            "added_from_06_only": len(added_from_06),
            "chunqiu_person_1021_1086": len(chunqiu_person_added),
        },
        "v2_wins_over_06_ids": sorted(overlap),
        "v2_wins_expected": sorted(V2_WINS_OVER_06_IDS),
        "v2_wins_expected_missing": sorted(V2_WINS_OVER_06_IDS - overlap),
        "chunqiu_person_ids": sorted(chunqiu_person_added),
        "chunqiu_person_expected_count": CHUNQIU_PERSON_ID_MAX - CHUNQIU_PERSON_ID_MIN + 1,
        "category_junwang_to_zhuhou": cat_log,
        "category_junwang_to_zhuhou_count": len(cat_log),
    }
    return merged, report


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 V2+06 线上史略索引")
    parser.add_argument("--dry-run", action="store_true", help="只打印统计，不写文件")
    args = parser.parse_args()

    merged, report = merge_online_index()

    print(f"V2 输入: {report['counts']['v2_input']}")
    print(f"06 输入: {report['counts']['dk_input']}")
    print(f"合并总数: {report['counts']['merged_total']}")
    print(f"06 同 ID 被 V2 覆盖: {report['counts']['skipped_06_same_id_as_v2']}")
    print(f"06 独占并入: {report['counts']['added_from_06_only']}")
    print(f"春秋人物 01021–01086: {report['counts']['chunqiu_person_1021_1086']}")
    if report.get("category_junwang_to_zhuhou_count"):
        print(f"分类修正 君王→诸侯: {report['category_junwang_to_zhuhou_count']} 条")

    if report["v2_wins_expected_missing"]:
        print("警告: 预期 V2 优先 ID 未在 06 中出现:", report["v2_wins_expected_missing"])

    expected_cq = report["chunqiu_person_expected_count"]
    actual_cq = report["counts"]["chunqiu_person_1021_1086"]
    if actual_cq != expected_cq:
        print(f"警告: 春秋人物期望 {expected_cq} 条，实际并入 {actual_cq} 条")

    if args.dry_run:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUT_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已写入 → {OUT_INDEX}")
    print(f"报告 → {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
