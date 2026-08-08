#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 V2 缺详情的条目写入 06 朝代索引，供 compose-detail 使用。"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
DETAILS_DIR = DATA / "06朝代知识补全" / "详情"
ENTRIES_DIR = DATA / "06朝代知识补全" / "索引条目"

PERSON_CATS = frozenset(
    {"君王", "诸侯", "宗戚", "文臣", "武将", "后妃", "宦官", "方士", "其他人物", "蕃祚", "庶众"}
)
NON_PERSON_CATS = frozenset({"事略", "典制", "论著"})

TOOLS = ROOT / "tools" / "openclaw-historiography"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_online_index import (  # noqa: E402
    build_emperor_name_index,
    normalize_supplement_entry,
)


def has_detail(eid: str) -> bool:
    return any(DETAILS_DIR.glob(f"{eid}_*.json"))


def entries_path(dynasty: str, category: str) -> Path:
    if category in NON_PERSON_CATS:
        return ENTRIES_DIR / f"{dynasty}_事略典制论著.json"
    return ENTRIES_DIR / f"{dynasty}_人物.json"


def discover_missing(dynasties: list[str]) -> list[dict]:
    v2 = json.loads(V2_INDEX.read_text(encoding="utf-8"))
    out: list[dict] = []
    for e in v2:
        dynasty = str(e.get("二级朝代坐标") or "")
        if dynasty not in dynasties:
            continue
        eid = str(e.get("史略ID") or "").strip()
        if not eid or has_detail(eid):
            continue
        out.append(e)
    return out


def should_update_existing(existing: dict, v2_row: dict) -> bool:
    """06 已有模型补全条目且 V2 仅为镜像时不覆盖索引。"""
    if existing.get("_v2迁移补全"):
        return True
    src06 = str(existing.get("史略来源") or "")
    srcv2 = str(v2_row.get("史略来源") or "")
    if src06 == "模型补全" and srcv2 == "模型补全":
        return False
    return srcv2 == "史料提取"


def upsert_entries(
    dynasty: str,
    rows: list[dict],
    *,
    dry_run: bool,
) -> dict:
    emperors_by_name, emperors_by_id = build_emperor_name_index()
    by_file: dict[Path, dict[str, dict]] = {}
    added: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for src in rows:
        eid = str(src["史略ID"])
        cat = str(src.get("史略分类") or "其他人物")
        path = entries_path(dynasty, cat)
        if path not in by_file:
            if path.is_file():
                doc = json.loads(path.read_text(encoding="utf-8"))
            else:
                doc = {
                    "schema_version": 1,
                    "朝代": dynasty,
                    "entries": [],
                }
            by_file[path] = {
                "doc": doc,
                "by_id": {str(e["史略ID"]): e for e in doc.get("entries") or []},
            }
        bucket = by_file[path]
        existing = bucket["by_id"].get(eid)
        if existing and not should_update_existing(existing, src):
            skipped.append(eid)
            continue
        row = normalize_supplement_entry(deepcopy(src), emperors_by_name, emperors_by_id)
        row["史略ID"] = eid
        row["_v2迁移补全"] = True
        if existing:
            bucket["by_id"][eid] = row
            updated.append(eid)
        else:
            bucket["by_id"][eid] = row
            added.append(eid)

    if not dry_run:
        for path, bucket in by_file.items():
            doc = bucket["doc"]
            doc["entries"] = sorted(
                bucket["by_id"].values(), key=lambda e: str(e.get("史略ID", ""))
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "files": [str(p.relative_to(DATA)) for p in by_file],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V2 缺详情 → 06 索引")
    parser.add_argument("--dynasty", action="append", required=True, help="春秋 / 战国，可重复")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = discover_missing(args.dynasty)
    if not rows:
        print("无待写入条目")
        return 0

    by_dynasty: dict[str, list[dict]] = {}
    for e in rows:
        by_dynasty.setdefault(str(e["二级朝代坐标"]), []).append(e)

    summary = {}
    for dynasty, drows in by_dynasty.items():
        summary[dynasty] = upsert_entries(dynasty, drows, dry_run=args.dry_run)

    report = {
        "dynasties": args.dynasty,
        "total_missing_detail": len(rows),
        "by_dynasty": summary,
    }
    out = DATA / "05工作流中间产物" / f"prepare_v2_{'_'.join(args.dynasty)}_report.json"
    if not args.dry_run:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
