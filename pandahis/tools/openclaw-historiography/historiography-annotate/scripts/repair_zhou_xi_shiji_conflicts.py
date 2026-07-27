#!/usr/bin/env python3
"""修复西周史记世家重标后的严重冲突与索引未同步项。

处理范围：
1. 从 GLBL 索引移除薄标注条目（杞东楼公、陈胡公满），写入薄标注注册表并保留 published_glbl_id
2. 清理孤儿/过期译稿（蔡叔度等）
3. 清理严重冲突条目旧译稿，待按新锚点重译（卫康叔、周公旦、宋微子、燕召公）
4. 重建 史略翻译_汇总.json

用法:
  python3 repair_zhou_xi_shiji_conflicts.py --dry-run
  python3 repair_zhou_xi_shiji_conflicts.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ANNOTATE = _SCRIPTS.parent
_TRANSLATE = _ANNOTATE.parent / "historiography-translate"
if str(_ANNOTATE) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE))
if str(_TRANSLATE) not in sys.path:
    sys.path.insert(0, str(_TRANSLATE))

from source_thickness import thin_registry_path  # noqa: E402

# 薄标注：应从 GLBL 索引移除
DOWNGRADE_GLBL = {
    "GLBL_00066": "杞东楼公",
    "GLBL_00139": "陈胡公满",
}

# 已删 GLBL、仅清译稿
ORPHAN_GLBL = {
    "GLBL_00130": "蔡叔度",
}

# 索引已更新、旧译锚点冲突，清译后待重跑
CONFLICT_RERUN_GLBL = {
    "GLBL_00004": "卫康叔",
    "GLBL_00015": "周公旦",
    "GLBL_00050": "宋微子",
    "GLBL_00087": "燕召公",
}

# 薄标注注册表 skeleton 史略ID → published_glbl_id
THIN_SKELETON_TO_GLBL = {
    "SHIJI_036_01": "GLBL_00066",
    "SHIJI_036_10": "GLBL_00139",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _backup(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, bak)
    return bak


def _remove_glbl_entries(index_path: Path, ids: set[str], *, dry_run: bool) -> list[dict[str, Any]]:
    doc = json.loads(index_path.read_text(encoding="utf-8"))
    removed: list[dict[str, Any]] = []
    kept: list[dict] = []
    for ent in doc.get("entries") or []:
        gid = str(ent.get("史略ID") or "")
        if gid in ids:
            removed.append({"glbl_id": gid, "name": ent.get("史略名称")})
            continue
        kept.append(ent)
    if not dry_run:
        doc["entries"] = kept
        doc["total_entries"] = len(kept)
        ms = dict(doc.get("merge_stats") or {})
        ms["global_entries"] = len(kept)
        doc["merge_stats"] = ms
        doc["repair_note"] = (
            "2026-07-25 西周史记世家冲突修复："
            f"降级移除 {len(removed)} 条 GLBL"
        )
        doc["repaired_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        index_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed


def _update_thin_registry(
    reg_path: Path,
    downgrade_snapshot: dict[str, dict],
    *,
    dry_run: bool,
) -> list[str]:
    """为薄标注条目补充 published_glbl_id 与降级元数据。"""
    doc = {"schema": "thin_annotation_deferred/v1", "entries": []}
    if reg_path.is_file():
        doc = json.loads(reg_path.read_text(encoding="utf-8"))
    entries: list[dict] = list(doc.get("entries") or [])
    by_eid = {str(e.get("史略ID")): i for i, e in enumerate(entries)}
    updated: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for skeleton_eid, glbl_id in THIN_SKELETON_TO_GLBL.items():
        snap = downgrade_snapshot.get(glbl_id)
        if skeleton_eid in by_eid:
            idx = by_eid[skeleton_eid]
            rec = dict(entries[idx])
            rec["published_glbl_id"] = glbl_id
            rec["defer_reason"] = "jiashi_reannotate_thin_downgrade"
            rec["audit_note"] = (
                f"世家重标后母本仅 {rec.get('source_char_count', '?')} 字 < 100，"
                f"自 GLBL 降级；原 {glbl_id}"
            )
            rec["recommended_action"] = "defer_to_dynasty_supplement"
            rec["offline_at"] = now
            rec["online_status"] = "pending_offline"
            if snap:
                rec["downgrade_snapshot"] = {
                    "六级段落锚点": snap.get("六级段落锚点"),
                    "paragraphs": snap.get("paragraphs"),
                }
            entries[idx] = rec
            updated.append(f"{skeleton_eid} → published_glbl_id={glbl_id}")
        elif snap:
            rec = {
                "defer_reason": "jiashi_reannotate_thin_downgrade",
                "source_char_count": 0,
                "recommended_path": "dynasty_knowledge_supplement",
                "published_glbl_id": glbl_id,
                "史略ID": skeleton_eid,
                "史略名称": snap.get("史略名称"),
                "史略分类": snap.get("史略分类"),
                "朝代ID": snap.get("朝代ID"),
                "二级朝代坐标": snap.get("二级朝代坐标"),
                "主要史料出处": snap.get("主要史料出处"),
                "paragraphs": snap.get("paragraphs") or [],
                "audit_note": f"世家重标薄标注，自 {glbl_id} 降级",
                "recommended_action": "defer_to_dynasty_supplement",
                "offline_at": now,
                "online_status": "pending_offline",
            }
            entries.append(rec)
            updated.append(f"new {skeleton_eid} published_glbl_id={glbl_id}")

    if not dry_run:
        doc["entries"] = entries
        doc["entry_count"] = len(entries)
        doc["updated_at"] = now
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated


def _clean_translation_artifacts(
    root: Path,
    entry_id: str,
    entry_name: str,
    *,
    archive: bool,
    dry_run: bool,
) -> list[str]:
    from lib.verify import output_path, sanitize_entry_name  # noqa: E402
    from lib.work_artifacts import mother_draft_path, plan_path  # noqa: E402

    out_dir = root / "data" / "04史料翻译"
    work_dir = root / "data" / "05工作流中间产物" / "翻译"
    archive_dir = root / "data" / "05工作流中间产物" / "薄标注待补全" / "archived_translations"
    stem = f"{entry_id}_{sanitize_entry_name(entry_name)}"
    targets: list[Path] = [
        output_path(entry_id, out_dir, entry_name),
        plan_path(entry_id, entry_name, work_dir),
        mother_draft_path(entry_id, entry_name, work_dir),
        work_dir / f".heartbeat_{entry_id}.json",
        work_dir / f"{entry_id}.repair.json",
        work_dir / f"{entry_id}_rerun.log",
        work_dir / f"{entry_id}_repair.log",
        work_dir / f"{entry_id}_repair_exec.log",
    ]
    for pat in (
        f"{stem}.chunk-*.json",
        f"{stem}.chunk-*.plan.json",
        f"{stem}.chunk-*.mother.json",
        f"{stem}.*",
        f"{entry_id}*",
    ):
        for fp in work_dir.glob(pat):
            if fp.is_file():
                targets.append(fp)

    removed: list[str] = []
    seen: set[Path] = set()
    for fp in targets:
        if fp in seen or not fp.is_file():
            continue
        seen.add(fp)
        if dry_run:
            removed.append(str(fp.relative_to(root)))
            continue
        if archive:
            archive_dir.mkdir(parents=True, exist_ok=True)
            dst = archive_dir / fp.name
            if dst.is_file():
                dst = archive_dir / f"{fp.stem}_{datetime.now().strftime('%H%M%S')}{fp.suffix}"
            shutil.move(str(fp), str(dst))
            removed.append(str(dst.relative_to(root)))
        else:
            fp.unlink()
            removed.append(str(fp.relative_to(root)))
    return removed


def _rebuild_aggregate(root: Path, *, dry_run: bool) -> tuple[int, int]:
    from lib.aggregate import rebuild_aggregate  # noqa: E402

    out_dir = root / "data" / "04史料翻译"
    if dry_run:
        agg = json.loads((out_dir / "史略翻译_汇总.json").read_text(encoding="utf-8"))
        return len(agg.get("entries") or []), len(agg.get("entries") or [])
    _, count = rebuild_aggregate(out_dir)
    return count, count


def _snapshot_glbl(index_path: Path, glbl_id: str) -> dict[str, Any] | None:
    doc = json.loads(index_path.read_text(encoding="utf-8"))
    for ent in doc.get("entries") or []:
        if ent.get("史略ID") == glbl_id:
            return {
                "史略名称": ent.get("史略名称"),
                "史略分类": ent.get("史略分类"),
                "朝代ID": ent.get("朝代ID"),
                "二级朝代坐标": ent.get("二级朝代坐标"),
                "主要史料出处": ent.get("主要史料出处"),
                "六级段落锚点": ent.get("六级段落锚点"),
                "paragraphs": ent.get("paragraphs") or [],
            }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="修复西周史记世家冲突与索引未同步")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = _repo_root()
    index_path = root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    reg_path = thin_registry_path(root)
    log_dir = root / "data" / "05工作流中间产物" / "薄标注待补全"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"zhou_xi_shiji_conflict_repair_{stamp}.json"

    report: dict[str, Any] = {
        "schema": "zhou_xi_shiji_conflict_repair/v1",
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": args.dry_run,
        "downgrade_removed": [],
        "thin_registry_updated": [],
        "translation_cleaned": {},
        "aggregate_count": None,
    }

    # 1. 快照待降级条目
    downgrade_snap: dict[str, dict] = {}
    for gid in DOWNGRADE_GLBL:
        snap = _snapshot_glbl(index_path, gid)
        if snap:
            downgrade_snap[gid] = snap

    # 2. 从 GLBL 移除薄标注
    if not args.dry_run and downgrade_snap:
        _backup(index_path)
    removed = _remove_glbl_entries(index_path, set(DOWNGRADE_GLBL), dry_run=args.dry_run)
    report["downgrade_removed"] = removed
    print(f"GLBL 降级移除 {len(removed)} 条: {[r['glbl_id'] for r in removed]}")

    # 3. 更新薄标注注册表
    thin_upd = _update_thin_registry(reg_path, downgrade_snap, dry_run=args.dry_run)
    report["thin_registry_updated"] = thin_upd
    print(f"薄标注注册表更新 {len(thin_upd)} 条")

    # 4. 清理译稿
    all_clean: dict[str, list[str]] = {}
    for gid, name in {**ORPHAN_GLBL, **DOWNGRADE_GLBL, **CONFLICT_RERUN_GLBL}.items():
        archived = gid in ORPHAN_GLBL or gid in DOWNGRADE_GLBL
        files = _clean_translation_artifacts(
            root, gid, name, archive=archived, dry_run=args.dry_run
        )
        all_clean[gid] = files
        print(f"  清理 {gid} {name}: {len(files)} 个文件{' (归档)' if archived else ''}")

    report["translation_cleaned"] = {k: len(v) for k, v in all_clean.items()}

    # 5. 重建汇总
    if not args.dry_run:
        before_agg = json.loads(
            (root / "data" / "04史料翻译" / "史略翻译_汇总.json").read_text(encoding="utf-8")
        )
        before_n = len(before_agg.get("entries") or [])
        _, after_n = _rebuild_aggregate(root, dry_run=False)
        report["aggregate_count"] = {"before": before_n, "after": after_n}
        print(f"史略翻译_汇总.json: {before_n} → {after_n}")
    else:
        print("(dry-run) 跳过重建汇总")

    if not args.dry_run:
        log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n✅ 日志 → {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
