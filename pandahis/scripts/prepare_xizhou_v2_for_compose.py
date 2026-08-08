#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 V2 缺详情的西周条目写入 06 人物索引，供 compose-detail 使用。"""

from __future__ import annotations

import json
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
ENTRIES_PATH = DATA / "06朝代知识补全" / "索引条目" / "西周_人物.json"
DETAILS_DIR = DATA / "06朝代知识补全" / "详情"
ANCHORS_DIR = DATA / "06朝代知识补全" / "锚点"

# 06 旧 ID → V2 对齐 ID（已有详情，仅 remap）
REMAP_DETAIL: dict[str, str] = {
    "GLBL_00806": "GLBL_01118",  # 晋唐叔虞
}

TOOLS = ROOT / "tools" / "openclaw-historiography"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_online_index import (  # noqa: E402
    build_emperor_name_index,
    normalize_supplement_entry,
)


def has_detail_for_id(eid: str) -> bool:
    return any(DETAILS_DIR.glob(f"{eid}_*.json"))


def remap_detail_assets(old_id: str, new_id: str, name: str) -> None:
    old_detail = DETAILS_DIR / f"{old_id}_{name}.json"
    new_detail = DETAILS_DIR / f"{new_id}_{name}.json"
    if old_detail.is_file() and not new_detail.is_file():
        doc = json.loads(old_detail.read_text(encoding="utf-8"))
        doc["史略ID"] = new_id
        new_detail.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    old_anchor = ANCHORS_DIR / f"{old_id}.json"
    new_anchor = ANCHORS_DIR / f"{new_id}.json"
    if old_anchor.is_file() and not new_anchor.is_file():
        doc = json.loads(old_anchor.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            doc["史略ID"] = new_id
        new_anchor.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def discover_missing_v2_xizhou() -> list[str]:
    v2 = json.loads(V2_INDEX.read_text(encoding="utf-8"))
    ids: list[str] = []
    for e in v2:
        if e.get("二级朝代坐标") != "西周":
            continue
        eid = str(e.get("史略ID", "")).strip()
        if not eid or has_detail_for_id(eid):
            continue
        ids.append(eid)
    return sorted(ids)


def main() -> int:
    v2_by = {e["史略ID"]: e for e in json.loads(V2_INDEX.read_text(encoding="utf-8"))}
    target_ids = discover_missing_v2_xizhou()
    if not target_ids:
        print("无待补全 V2 西周条目")
        return 0

    doc = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))
    by_id = {str(e["史略ID"]): e for e in doc.get("entries") or []}
    emperors_by_name, emperors_by_id = build_emperor_name_index()

    added: list[str] = []
    updated: list[str] = []
    remapped: list[str] = []
    compose_pending: list[str] = []

    compose_skip = frozenset(REMAP_DETAIL.values())

    for old_id, new_id in REMAP_DETAIL.items():
        if not has_detail_for_id(new_id) and new_id in v2_by:
            src = v2_by[new_id]
            name = str(src.get("史略名称") or "").strip()
            remap_detail_assets(old_id, new_id, name)
            if old_id in by_id:
                del by_id[old_id]
            row = normalize_supplement_entry(deepcopy(src), emperors_by_name, emperors_by_id)
            row["史略ID"] = new_id
            row["_v2迁移补全"] = True
            by_id[new_id] = row
            remapped.append(f"{old_id}→{new_id}")

    for eid in target_ids:
        if eid in compose_skip:
            continue
        if has_detail_for_id(eid):
            continue
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
        compose_pending.append(eid)

    doc["entries"] = sorted(by_id.values(), key=lambda e: str(e.get("史略ID", "")))
    ENTRIES_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "added": added,
        "updated": updated,
        "remapped": remapped,
        "compose_pending": compose_pending,
        "total_compose": len(compose_pending),
    }
    out = DATA / "05工作流中间产物" / "prepare_xizhou_v2_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
