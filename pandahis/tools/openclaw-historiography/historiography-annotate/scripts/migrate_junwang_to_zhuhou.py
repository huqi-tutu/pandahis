#!/usr/bin/env python3
"""v4 迁移：史记诸侯世家 + 秦本纪国君 君王 → 诸侯（保留 GLBL_ID）。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

# 《史记》诸侯世袭世家 031–046
SHIJI_JIASHI_VOLS: Set[str] = {f"{v:03d}" for v in range(31, 47)}

# 秦本纪 vol 005：始皇以前为诸侯，始皇/二世保持君王
SHIJI_QIN_BENJI_VOL = "005"
QIN_JUNWANG_NAMES: Set[str] = {"秦始皇", "秦二世"}

# 灰区：强制保持君王（本纪级共主）
FORCE_JUNWANG_NAMES: Set[str] = {
    "项羽",
    "王莽",
    "秦始皇",
    "秦二世",
}


def _entry_vols(entry: dict) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for p in entry.get("paragraphs") or []:
        work = str(p.get("work") or "").strip()
        vol = str(p.get("vol") or "").strip().zfill(3)
        if work and vol:
            out.append((work, vol))
    return out


def should_migrate_entry(entry: dict) -> Tuple[bool, str]:
    """判定 GLBL / skeleton entry 是否 君王→诸侯。"""
    cat = (entry.get("史略分类") or "").strip()
    if cat not in ("君王", "君纪"):
        return False, "not_junwang"
    name = (entry.get("史略名称") or "").strip()
    if name in FORCE_JUNWANG_NAMES:
        return False, "force_junwang"
    vols = _entry_vols(entry)
    if not vols:
        return False, "no_vol"
    for work, vol in vols:
        if work == "01史记" and vol in SHIJI_JIASHI_VOLS:
            return True, "jiashi"
        if work == "01史记" and vol == SHIJI_QIN_BENJI_VOL and name not in QIN_JUNWANG_NAMES:
            return True, "qin_gong"
    return False, "stay_junwang"


def _patch_category_fields(obj: dict, *, dry_run: bool) -> bool:
    """就地改 史略分类 / category / 五级细坐标。"""
    changed = False
    for key in ("史略分类",):
        if (obj.get(key) or "").strip() in ("君王", "君纪"):
            if not dry_run:
                obj[key] = "诸侯"
            changed = True
    if (obj.get("category") or "").strip() in ("君王", "君纪"):
        if not dry_run:
            obj["category"] = "诸侯"
        changed = True
    wj = (obj.get("五级细坐标") or "").strip()
    if wj and "·君王·" in wj:
        if not dry_run:
            obj["五级细坐标"] = wj.replace("·君王·", "·诸侯·")
        changed = True
    return changed


def migrate_skeleton_file(path: Path, *, dry_run: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    vol_m = re.search(r"_(\d{3})_", path.name)
    vol = vol_m.group(1) if vol_m else ""
    is_jiashi = vol in SHIJI_JIASHI_VOLS
    is_qin = vol == SHIJI_QIN_BENJI_VOL

    for entry in data.get("entries") or []:
        ok, _ = should_migrate_entry(entry)
        if not ok and is_jiashi and (entry.get("史略分类") or "").strip() in ("君王", "君纪"):
            ok = True
        if not ok and is_qin and (entry.get("史略分类") or "").strip() in ("君王", "君纪"):
            name = (entry.get("史略名称") or "").strip()
            if name not in QIN_JUNWANG_NAMES:
                ok = True
        if ok and _patch_category_fields(entry, dry_run=dry_run):
            n += 1
    for block in data.get("blocks") or []:
        cat = (block.get("category") or "").strip()
        if cat in ("君王", "君纪") and is_jiashi and _patch_category_fields(block, dry_run=dry_run):
            n += 1
    for seg in data.get("segment_attribution") or []:
        for owner in seg.get("owners") or []:
            cat = (owner.get("category") or "").strip()
            if cat in ("君王", "君纪") and is_jiashi and _patch_category_fields(owner, dry_run=dry_run):
                n += 1
    for p in data.get("protagonists") or []:
        cat = (p.get("category") or "").strip()
        if cat in ("君王", "君纪") and is_jiashi and _patch_category_fields(p, dry_run=dry_run):
            n += 1
    if n and not dry_run:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def migrate_global_index(path: Path, *, dry_run: bool) -> Dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stats = {"migrated": 0, "skipped": 0, "by_reason": {}}
    for entry in data.get("entries") or []:
        ok, reason = should_migrate_entry(entry)
        if not ok:
            stats["skipped"] += 1
            continue
        if _patch_category_fields(entry, dry_run=dry_run):
            stats["migrated"] += 1
            stats["by_reason"][reason] = stats["by_reason"].get(reason, 0) + 1
    if stats["migrated"] and not dry_run:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def migrate_tree(data_root: Path, *, dry_run: bool) -> dict:
    sk_dir = data_root / "data" / "03索引标注条目"
    glbl = sk_dir / "史略索引_01至02.json"
    sk_changed = 0
    sk_files = 0
    for fp in sorted(sk_dir.glob("01史记_*_skeleton.json")):
        m = re.search(r"_(\d{3})_", fp.name)
        if not m:
            continue
        vol = m.group(1)
        if vol not in SHIJI_JIASHI_VOLS and vol != SHIJI_QIN_BENJI_VOL:
            continue
        n = migrate_skeleton_file(fp, dry_run=dry_run)
        if n:
            sk_changed += n
            sk_files += 1
    glbl_stats = migrate_global_index(glbl, dry_run=dry_run) if glbl.is_file() else {}
    return {
        "dry_run": dry_run,
        "skeleton_field_changes": sk_changed,
        "skeleton_files": sk_files,
        "glbl": glbl_stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="v4 君王→诸侯增量迁移")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="pandahis/pandahis 数据根目录",
    )
    parser.add_argument("--execute", action="store_true", help="写入文件（默认 dry-run）")
    args = parser.parse_args()
    result = migrate_tree(args.root, dry_run=not args.execute)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
