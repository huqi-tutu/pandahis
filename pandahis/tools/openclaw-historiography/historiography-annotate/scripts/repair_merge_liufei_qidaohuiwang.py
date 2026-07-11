#!/usr/bin/env python3
"""合并 刘肥(GLBL_00173) → 齐悼惠王(GLBL_00214)，删除重复 GLBL，不重排 ID。

用法:
  python3 repair_merge_liufei_qidaohuiwang.py
  python3 repair_merge_liufei_qidaohuiwang.py --dry-run
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DELETE_GLBL = "GLBL_00173"
KEEP_GLBL = "GLBL_00214"
SUPP_EID = "HANSHU_048_01"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _hanshu_048_supplement_block() -> dict:
    return {
        "work": "02汉书",
        "vol": "048",
        "volume": "高五王传",
        "paragraph_from": 2,
        "paragraph_to": 8,
        "source_file": "02二十四史拆分后/02汉书_拆分后/02汉书_048_高五王传第八.txt",
        "index_file": "段落索引/02汉书_048.json",
        "source_entry_id": SUPP_EID,
        "role": "补充",
    }


def repair_index(*, dry_run: bool = False) -> dict:
    data_root = _repo_root() / "data" / "03索引标注条目"
    index_path = data_root / "史略索引_01至02.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") or []

    delete_idx = None
    keep_idx = None
    for i, ent in enumerate(entries):
        eid = ent.get("史略ID")
        if eid == DELETE_GLBL:
            delete_idx = i
        elif eid == KEEP_GLBL:
            keep_idx = i

    if delete_idx is None:
        raise SystemExit(f"未找到待删除条目 {DELETE_GLBL}")
    if keep_idx is None:
        raise SystemExit(f"未找到保留条目 {KEEP_GLBL}")

    deleted = entries.pop(delete_idx)
    if keep_idx > delete_idx:
        keep_idx -= 1
    kept = entries[keep_idx]

    if any(x.get("source_entry_id") == SUPP_EID for x in kept.get("paragraphs") or []):
        raise SystemExit(f"{KEEP_GLBL} 已含 {SUPP_EID}，无需重复合并")

    supp_para = _hanshu_048_supplement_block()
    kept["史略简介"] = "齐悼惠王刘肥"
    kept["paragraphs"] = list(kept.get("paragraphs") or []) + [supp_para]
    kept["source_entries"] = list(kept.get("source_entries") or []) + [
        {"史略ID": SUPP_EID, "role": "补充", "work": "02汉书", "vol": "048"}
    ]
    kept["合并来源"] = list(kept.get("合并来源") or []) + [
        {
            "work": "02汉书",
            "史略ID": SUPP_EID,
            "role": "补充",
            "主要史料出处": "《汉书·卷48·高五王传》",
            "paragraph_count": 1,
        }
    ]
    kept["来源著作"] = sorted({*(kept.get("来源著作") or []), "02汉书"})
    kept["来源条目数"] = len(kept.get("source_entries") or [])
    kept["段落域数"] = len(kept.get("paragraphs") or [])
    kept["六级段落锚点"] = "[P1-P56,P2-P8]"
    kept["宗戚ID"] = kept.get("宗戚ID") or "ZJ_HX_XIHAN_XIHAN_QIDAOHUIWANG"

    entries[keep_idx] = kept
    payload["entries"] = entries
    payload["total_entries"] = len(entries)
    payload["merge_stats"] = dict(payload.get("merge_stats") or {})
    payload["merge_stats"]["global_entries"] = len(entries)
    payload["repair_note"] = (
        f"2026-07-11 合并 {DELETE_GLBL}(刘肥) → {KEEP_GLBL}(齐悼惠王)，"
        "删除重复 GLBL，ID 未重排"
    )
    payload["repaired_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = {
        "deleted_id": DELETE_GLBL,
        "kept_id": KEEP_GLBL,
        "deleted_name": deleted.get("史略名称"),
        "kept_name": kept.get("史略名称"),
        "total_entries": len(entries),
        "dry_run": dry_run,
    }

    if not dry_run:
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["index_path"] = str(index_path)

    return result


def repair_skeleton(*, dry_run: bool = False) -> dict:
    sk_path = _repo_root() / "data" / "03索引标注条目" / "02汉书_048_高五王传第八_skeleton.json"
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    changed = False
    for ent in sk.get("entries") or []:
        if ent.get("史略ID") != SUPP_EID:
            continue
        if ent.get("史略名称") != "齐悼惠王":
            ent["史略名称"] = "齐悼惠王"
            changed = True
        if not ent.get("宗戚ID"):
            ent["宗戚ID"] = "ZJ_HX_XIHAN_XIHAN_QIDAOHUIWANG"
            changed = True

    result = {"skeleton_path": str(sk_path), "changed": changed, "dry_run": dry_run}
    if changed and not dry_run:
        sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-skeleton", action="store_true")
    args = parser.parse_args()

    idx_result = repair_index(dry_run=args.dry_run)
    print("索引修复:", json.dumps(idx_result, ensure_ascii=False, indent=2))

    if not args.skip_skeleton:
        sk_result = repair_skeleton(dry_run=args.dry_run)
        print("skeleton 修复:", json.dumps(sk_result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
