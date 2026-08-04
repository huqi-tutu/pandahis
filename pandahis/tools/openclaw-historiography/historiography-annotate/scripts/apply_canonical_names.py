#!/usr/bin/env python3
"""将 SSOT 已确认的标准名写入 skeleton（史略名称 + segment_attribution）。

仅处理 史略异名表.json 中已有映射的名称；不触碰待 LLM 队列条目。

用法:
  python3 apply_canonical_names.py
  python3 apply_canonical_names.py --dry-run
  python3 apply_canonical_names.py --dir data/10新标注条目
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

import sys

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from canonical_resolve import resolve_display_name, load_alias_table  # noqa: E402


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _approved_renames() -> Dict[str, str]:
    """raw → display，SSOT 异名表全部 old→canonical 映射。"""
    cfg = load_alias_table()
    out: Dict[str, str] = {}
    for alias, canonical in (cfg.get("global") or {}).items():
        a, c = str(alias).strip(), str(canonical).strip()
        if a and c and a != c:
            out[a] = c
    for given, full in (cfg.get("功臣标准名") or {}).items():
        g, f = str(given).strip(), str(full).strip()
        if g and f and g != f:
            out[g] = f
    for given, full in (cfg.get("宗戚标准名") or {}).items():
        g, f = str(given).strip(), str(full).strip()
        if g and f and g != f:
            out[g] = f
    return out


def _sync_skeleton(data: dict, renames: Dict[str, str]) -> Tuple[int, List[str]]:
    changes: List[str] = []
    count = 0

    for entry in data.get("entries") or []:
        old = str(entry.get("史略名称") or "").strip()
        if not old:
            continue
        new = renames.get(old) or resolve_display_name(old, category=str(entry.get("史略分类") or ""))
        if new and new != old and (old in renames or new != old):
            # 仅当 SSOT 有直接映射或 resolve 给出不同复合名
            direct = renames.get(old)
            if direct and direct != old:
                entry["史略名称"] = direct
                intro = str(entry.get("史略简介") or "").strip()
                if intro == old or not intro:
                    entry["史略简介"] = direct
                changes.append(f"entry {entry.get('史略ID')}: {old} → {direct}")
                count += 1

    for seg in data.get("segment_attribution") or []:
        for owner in seg.get("owners") or []:
            old = str(owner.get("name") or "").strip()
            if old in renames:
                owner["name"] = renames[old]
                count += 1

    return count, changes


def apply_to_dir(target: Path, *, dry_run: bool = False) -> dict:
    renames = _approved_renames()
    total_files = 0
    total_changes = 0
    log: List[str] = []

    for fp in sorted(target.glob("*_skeleton.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        n, changes = _sync_skeleton(data, renames)
        if n:
            total_files += 1
            total_changes += n
            log.extend([f"{fp.name}: {c}" for c in changes])
            if not dry_run:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"files": total_files, "changes": total_changes, "log": log}


def apply_to_glbl_index(index_path: Path, *, dry_run: bool = False) -> dict:
    """将标准名写入 史略索引_01至02.json（数组格式）。"""
    renames = _approved_renames()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"期望 JSON 数组: {index_path}")

    changes: List[str] = []
    count = 0
    for entry in data:
        old = str(entry.get("史略名称") or "").strip()
        if old not in renames:
            continue
        new = renames[old]
        entry["史略名称"] = new
        intro = str(entry.get("史略简介") or "").strip()
        if intro == old or not intro:
            entry["史略简介"] = new
        if str(entry.get("四级帝王坐标") or "").strip() == old:
            entry["四级帝王坐标"] = new
        changes.append(f"{entry.get('史略ID')}: {old} → {new}")
        count += 1

    if count and not dry_run:
        index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"changes": count, "log": changes}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dir", default="", help="相对 repo 的 skeleton 目录")
    args = parser.parse_args()

    root = _repo_root()
    dirs = []
    if args.dir:
        dirs.append(root / args.dir)
    else:
        dirs.append(root / "data" / "10新标注条目")
        dirs.append(root / "data" / "03索引标注条目")

    for d in dirs:
        if not d.is_dir():
            continue
        r = apply_to_dir(d, dry_run=args.dry_run)
        print(f"\n{d.relative_to(root)}: {r['files']} files, {r['changes']} renames")
        for line in r["log"][:30]:
            print(f"  {line}")
        if len(r["log"]) > 30:
            print(f"  ... +{len(r['log']) - 30} more")

    glbl_path = root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    if glbl_path.is_file() and not args.dir:
        gr = apply_to_glbl_index(glbl_path, dry_run=args.dry_run)
        print(f"\n{glbl_path.relative_to(root)}: {gr['changes']} renames")
        for line in gr["log"][:30]:
            print(f"  {line}")
        if len(gr["log"]) > 30:
            print(f"  ... +{len(gr['log']) - 30} more")


if __name__ == "__main__":
    main()
