#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 V2 迁移的 3 条商代君王写入 06 人物索引，供 compose-detail 使用。"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
ENTRIES_PATH = DATA / "06朝代知识补全" / "索引条目" / "商_人物.json"

TARGET_IDS = ("GLBL_00044", "GLBL_00045", "GLBL_00054")

TOOLS = ROOT / "tools" / "openclaw-historiography"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_online_index import (  # noqa: E402
    build_emperor_name_index,
    normalize_supplement_entry,
)


def main() -> None:
    v2_by = {e["史略ID"]: e for e in json.loads(V2_INDEX.read_text(encoding="utf-8"))}
    doc = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))
    by_id = {str(e["史略ID"]): e for e in doc.get("entries") or []}

    emperors_by_name, emperors_by_id = build_emperor_name_index()
    added, updated = [], []

    for eid in TARGET_IDS:
        src = v2_by.get(eid)
        if not src:
            raise SystemExit(f"V2 缺少 {eid}")
        row = normalize_supplement_entry(deepcopy(src), emperors_by_name, emperors_by_id)
        row["史略ID"] = eid
        row["_v2迁移补全"] = True
        if eid in by_id:
            by_id[eid] = row
            updated.append(eid)
        else:
            by_id[eid] = row
            added.append(eid)

    doc["entries"] = sorted(by_id.values(), key=lambda e: str(e["史略ID"]))
    ENTRIES_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"商_人物.json: +{len(added)} ~{len(updated)} | ids={TARGET_IDS}")


if __name__ == "__main__":
    main()
