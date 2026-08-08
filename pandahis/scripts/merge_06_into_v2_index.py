#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 06 朝代知识补全中「V1 模型补全未入 V2」(376) + 「06 独占」(66) 共 442 条并入 V2 索引。

规则：
  - 已有 V2 同 ID 条目保留 V2 版本（11 条跳过）
  - 仅追加 06 中目标 ID，不覆盖现有 V2
  - 06 中 V1 史料提取重复镜像（48 条）不在本次范围

产出：data/10新标注条目/史略索引_史记汉书.json
报告：data/05工作流中间产物/merge_06_into_v2_report.json
"""

from __future__ import annotations

import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
V1_INDEX = DATA / "03索引标注条目" / "史略索引_01至02.json"
DK_ENTRIES = DATA / "06朝代知识补全" / "索引条目"
OUT_REPORT = DATA / "05工作流中间产物" / "merge_06_into_v2_report.json"
EMPEROR_JSON = DATA / "01历史坐标数据" / "帝王.json"

TOOLS = ROOT / "tools" / "openclaw-historiography"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_online_index import (  # noqa: E402
    build_emperor_name_index,
    load_dk_entries,
    normalize_supplement_entry,
)
from category_normalize import normalize_entries  # noqa: E402
from entry_source import normalize_entry_source  # noqa: E402


def load_v2() -> list[dict]:
    return json.loads(V2_INDEX.read_text(encoding="utf-8"))


def load_v1_by_id() -> dict[str, dict]:
    rows = json.loads(V1_INDEX.read_text(encoding="utf-8"))
    return {str(e["史略ID"]): e for e in rows}


def target_ids(v2_ids: set[str], v1_by: dict[str, dict], ids06: set[str]) -> set[str]:
    v1_model = {
        eid for eid, e in v1_by.items() if e.get("史略来源") == "模型补全"
    }
    only06 = ids06 - set(v1_by)
    return (v1_model - v2_ids) | (only06 - v2_ids)


def main() -> None:
    v2_list = load_v2()
    v1_by = load_v1_by_id()
    dk_list = load_dk_entries()
    emperors_by_name, emperors_by_id = build_emperor_name_index()

    ids06 = {str(e["史略ID"]) for e in dk_list}
    v2_ids = {str(e["史略ID"]) for e in v2_list}
    want = target_ids(v2_ids, v1_by, ids06)

    by_id: dict[str, dict] = {}
    for e in v2_list:
        eid = str(e["史略ID"])
        by_id[eid] = normalize_entry_source(deepcopy(e))

    dk_by_id = {str(e["史略ID"]): e for e in dk_list}
    added: list[str] = []
    skipped_not_in_06: list[str] = []
    skipped_already_v2: list[str] = []

    for eid in sorted(want):
        if eid in by_id:
            skipped_already_v2.append(eid)
            continue
        src = dk_by_id.get(eid)
        if not src:
            skipped_not_in_06.append(eid)
            continue
        normalized = normalize_supplement_entry(src, emperors_by_name, emperors_by_id)
        by_id[eid] = normalized
        added.append(eid)

    merged = sorted(by_id.values(), key=lambda x: str(x["史略ID"]))
    merged, cat_log = normalize_entries(merged)

    backup = V2_INDEX.with_suffix(".json.bak")
    shutil.copy2(V2_INDEX, backup)
    V2_INDEX.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        "schema": "merge-06-into-v2/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "v2_before": len(v2_list),
        "v2_after": len(merged),
        "target_count": len(want),
        "added_from_06": len(added),
        "skipped_already_v2": skipped_already_v2,
        "skipped_not_in_06": skipped_not_in_06,
        "added_ids": added,
        "category_normalize": cat_log,
        "backup": str(backup),
    }
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"V2: {len(v2_list)} -> {len(merged)} (+{len(added)})")
    print(f"Report: {OUT_REPORT}")


if __name__ == "__main__":
    main()
