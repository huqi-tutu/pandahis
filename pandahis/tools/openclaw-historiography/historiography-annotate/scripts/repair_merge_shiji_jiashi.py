#!/usr/bin/env python3
"""史记世家 031–060 增量 merge（保留既有 GLBL ID，禁止全量重排）。

用法:
  python3 repair_merge_shiji_jiashi.py --dry-run
  python3 repair_merge_shiji_jiashi.py
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS = Path(__file__).resolve().parent
_ANNOTATE = _SCRIPTS.parent
if str(_ANNOTATE) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from merge_global_entries import (  # noqa: E402
    COPY_FIELDS,
    _build_glbl_entry,
    _canonical_name,
    _extract_kaoding_yiju,
    _merge_anchor,
    _paragraph_blocks,
)
from preview_merge_shiji_jiashi import (  # noqa: E402
    JIASHI_VOLS,
    _find_glbl_match,
    _load_jiashi_skeleton_sources,
    _max_glbl_num,
    build_preview,
)
from source_thickness import build_deferred_record, should_defer_glbl, thin_registry_path  # noqa: E402

# 分类迁移：保留原 GLBL ID，只更新字段
CATEGORY_MIGRATION_GLBL: Dict[str, str] = {
    "周勃": "GLBL_00507",
}

OBSOLETE_DELETE = {"GLBL_00130", "GLBL_00473"}  # 蔡叔度、韩厥；周勃走迁移

ENRICHMENT_PRESERVE = [
    "峰值年",
    "峰值原因",
    "峰值类型",
    "峰值置信度",
    "人物标签",
    "人物标签判定理由",
    "人物标签置信度",
    "_auto_filled",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _backup(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, bak)
    return bak


def _find_glbl_flexible(
    glbl_entries: List[dict],
    canonical: str,
    cat: str,
) -> Optional[dict]:
    if canonical in CATEGORY_MIGRATION_GLBL:
        gid = CATEGORY_MIGRATION_GLBL[canonical]
        for ent in glbl_entries:
            if ent.get("史略ID") == gid:
                return ent
    matches = _find_glbl_match(glbl_entries, canonical, cat)
    return matches[0] if matches else None


def _non_jiashi_paragraphs(ent: dict) -> List[dict]:
    out = []
    for p in ent.get("paragraphs") or []:
        if p.get("work") == "01史记" and str(p.get("vol", "")).zfill(3) in JIASHI_VOLS:
            continue
        out.append(copy.deepcopy(p))
    return out


def _non_jiashi_source_entries(ent: dict) -> List[dict]:
    out = []
    for se in ent.get("source_entries") or []:
        if se.get("work") == "01史记" and str(se.get("vol", "")).zfill(3) in JIASHI_VOLS:
            continue
        out.append(copy.deepcopy(se))
    return out


def _non_jiashi_merge_sources(ent: dict) -> List[dict]:
    out = []
    for ms in ent.get("合并来源") or []:
        if ms.get("work") == "01史记" and str(ms.get("vol", "")).zfill(3) in JIASHI_VOLS:
            continue
        out.append(copy.deepcopy(ms))
    return out


def _build_shiji_sources(group: List[dict]) -> List[dict]:
    """按卷号排序的多 block 源列表。"""
    return sorted(group, key=lambda s: (s["vol"], s["eid"]))


def _glbl_from_group(
    glbl_id: str,
    group: List[dict],
    existing: Optional[dict] = None,
) -> dict:
    ranked = _build_shiji_sources(group)
    fresh = _build_glbl_entry(glbl_id, ranked, ranked=ranked)

    if existing and _non_jiashi_paragraphs(existing):
        shiji_paras: List[dict] = []
        for src in ranked:
            shiji_paras.extend(_paragraph_blocks(src, "母本"))
        hanshu_paras = _non_jiashi_paragraphs(existing)
        fresh["paragraphs"] = shiji_paras + hanshu_paras

        shiji_se = [
            {"史略ID": s["eid"], "role": "主要", "work": s["work"], "vol": s["vol"]}
            for s in ranked
        ]
        fresh["source_entries"] = shiji_se + _non_jiashi_source_entries(existing)

        shiji_ms = []
        for s in ranked:
            blocks = _paragraph_blocks(s, "母本")
            shiji_ms.append(
                {
                    "work": s["work"],
                    "史略ID": s["eid"],
                    "role": "主要",
                    "主要史料出处": s["entry"].get("主要史料出处", ""),
                    "paragraph_count": len(blocks),
                }
            )
        fresh["合并来源"] = shiji_ms + _non_jiashi_merge_sources(existing)
        fresh["来源著作"] = sorted({*(fresh.get("来源著作") or []), *{p["work"] for p in hanshu_paras}})
        fresh["来源条目数"] = len(fresh["source_entries"])
        fresh["段落域数"] = len(fresh["paragraphs"])
        if len(fresh["来源著作"]) > 1:
            all_ranked = ranked + [
                {
                    "work": se["work"],
                    "vol": se["vol"],
                    "entry": {"paragraphs": []},
                    "eid": se["史略ID"],
                }
                for se in _non_jiashi_source_entries(existing)
            ]
            fresh["六级段落锚点"] = f"[{_merge_anchor(all_ranked)}]"

    if existing:
        for field in ENRICHMENT_PRESERVE:
            if field in existing and existing[field] not in (None, "", {}):
                fresh[field] = copy.deepcopy(existing[field])
        # 考订依据：保留峰值相关，更新年/坐标若 skeleton 有
        kaoding = _extract_kaoding_yiju(ranked[0]["entry"])
        if kaoding:
            merged_kd = dict(existing.get("考订依据") or {})
            merged_kd.update(kaoding)
            fresh["考订依据"] = merged_kd
        elif existing.get("考订依据"):
            fresh["考订依据"] = copy.deepcopy(existing["考订依据"])

    fresh["史略ID"] = glbl_id
    fresh["史略来源"] = existing.get("史略来源", "史料提取") if existing else "史料提取"
    return fresh


def _group_sources(sources: List[dict]) -> Dict[Tuple[str, str], List[dict]]:
    from collections import defaultdict

    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for s in sources:
        groups[(s["canonical"], s["cat"])].append(s)
    return groups


def apply_merge(*, dry_run: bool = False) -> dict[str, Any]:
    data_root = _repo_root() / "data" / "03索引标注条目"
    index_path = data_root / "史略索引_01至02.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    entries: List[dict] = payload.get("entries") or []
    by_id = {e["史略ID"]: i for i, e in enumerate(entries)}

    sources = _load_jiashi_skeleton_sources(data_root)
    groups = _group_sources(sources)

    stats = {
        "updated": [],
        "created": [],
        "deleted": [],
        "thin_added": 0,
        "dry_run": dry_run,
    }
    thin_new: List[dict] = []
    next_id = _max_glbl_num(entries) + 1
    touched_ids: set[str] = set()

    for (canonical, cat), group in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])):
        defer, total_chars, reason = should_defer_glbl(_build_shiji_sources(group))
        if defer:
            thin_new.append(
                build_deferred_record(
                    _build_shiji_sources(group),
                    total_chars=total_chars,
                    reason=reason or "thin_source_total_under_100",
                )
            )
            continue

        existing = _find_glbl_flexible(entries, canonical, cat)
        if existing:
            gid = existing["史略ID"]
            new_ent = _glbl_from_group(gid, group, existing=existing)
            entries[by_id[gid]] = new_ent
            touched_ids.add(gid)
            stats["updated"].append({"glbl_id": gid, "name": new_ent["史略名称"], "cat": cat})
        else:
            gid = f"GLBL_{next_id:05d}"
            next_id += 1
            new_ent = _glbl_from_group(gid, group)
            entries.append(new_ent)
            by_id[gid] = len(entries) - 1
            touched_ids.add(gid)
            stats["created"].append({"glbl_id": gid, "name": new_ent["史略名称"], "cat": cat})

    # 删除淘汰条目（不含已迁移的周勃）
    for gid in OBSOLETE_DELETE:
        if gid not in by_id:
            continue
        if gid in touched_ids:
            continue
        idx = by_id[gid]
        name = entries[idx].get("史略名称")
        entries.pop(idx)
        stats["deleted"].append({"glbl_id": gid, "name": name})
        # rebuild by_id
        by_id = {e["史略ID"]: i for i, e in enumerate(entries)}

    payload["entries"] = entries
    payload["total_entries"] = len(entries)
    payload["merge_stats"] = dict(payload.get("merge_stats") or {})
    payload["merge_stats"]["global_entries"] = len(entries)
    payload["repair_note"] = (
        "2026-07-25 史记世家031-060增量merge：保留GLBL ID，"
        f"更新{len(stats['updated'])}、新增{len(stats['created'])}、删除{len(stats['deleted'])}"
    )
    payload["repaired_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 薄标注注册表
    reg_path = thin_registry_path(_repo_root())
    reg_doc = {"schema": "thin_annotation_deferred/v1", "entries": []}
    if reg_path.is_file():
        reg_doc = json.loads(reg_path.read_text(encoding="utf-8"))
    existing_eids = {e.get("史略ID") for e in reg_doc.get("entries") or []}
    added_thin = 0
    for rec in thin_new:
        eid = rec.get("史略ID")
        if eid in existing_eids:
            continue
        reg_doc.setdefault("entries", []).append(rec)
        existing_eids.add(eid)
        added_thin += 1
    reg_doc["entry_count"] = len(reg_doc.get("entries") or [])
    reg_doc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats["thin_added"] = added_thin
    stats["total_entries"] = len(entries)

    if not dry_run:
        _backup(index_path)
        index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        if added_thin > 0 or thin_new:
            _backup(reg_path)
            reg_path.write_text(json.dumps(reg_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stats["index_path"] = str(index_path)
        stats["registry_path"] = str(reg_path)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = apply_merge(dry_run=args.dry_run)
    preview = build_preview()
    print(json.dumps({**stats, "preview_summary": preview["summary"]}, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("\n(dry-run，未写入文件)")
    else:
        print(f"\n✅ 已写入 {stats.get('index_path')}")
        print(f"   薄标注新增 {stats['thin_added']} 条 → {stats.get('registry_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
