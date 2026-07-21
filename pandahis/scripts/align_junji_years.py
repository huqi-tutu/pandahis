#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量将朝代知识补全人物索引中的君王年份对齐帝王.json，并可选写回主索引。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DK_INDEX = ROOT / "data" / "06朝代知识补全" / "索引条目"
INDEX_MAIN = ROOT / "data" / "03索引标注条目" / "史略索引_01至02.json"

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from emperor_year_align import align_junji_entries  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dynasty_id_from_filename(path: Path) -> str | None:
    name = path.stem
    if name.startswith("夏_"):
        return "CD_HX_XIA"
    if name.startswith("五帝_"):
        return "CD_HX_WUDI"
    return None


def merge_into_main_index(changed_ids: set[str]) -> int:
    if not changed_ids or not INDEX_MAIN.is_file():
        return 0
    main = load_json(INDEX_MAIN)
    entries: list[dict] = main.get("entries") or []
    by_id = {str(e.get("史略ID", "")): i for i, e in enumerate(entries)}
    updated = 0
    for path in sorted(DK_INDEX.glob("*_人物.json")):
        doc = load_json(path)
        for entry in doc.get("entries") or []:
            eid = str(entry.get("史略ID", ""))
            if eid not in changed_ids or eid not in by_id:
                continue
            entries[by_id[eid]] = entry
            updated += 1
    if updated:
        main["entries"] = entries
        save_json(INDEX_MAIN, main)
    return updated


def process_file(path: Path, *, dry_run: bool) -> tuple[int, list[str]]:
    doc = load_json(path)
    entries = doc.get("entries") or []
    dynasty_id = dynasty_id_from_filename(path)
    aligned, changes = align_junji_entries(entries, dynasty_id=dynasty_id, force=True)
    if changes and not dry_run:
        doc["entries"] = aligned
        save_json(path, doc)
    changed_ids = {c.split()[0] for c in changes if c.split()}
    return len(changes), changes


def main() -> int:
    parser = argparse.ArgumentParser(description="君王年份对齐帝王.json")
    parser.add_argument("--file", type=Path, help="指定单个 *_人物.json")
    parser.add_argument("--dry-run", action="store_true", help="只打印变更，不写文件")
    parser.add_argument("--merge-main", action="store_true", help="同步写回史略主索引")
    args = parser.parse_args()

    targets = [args.file] if args.file else sorted(DK_INDEX.glob("*_人物.json"))
    total = 0
    all_changed_ids: set[str] = set()
    for path in targets:
        if not path.is_file():
            print(f"跳过（不存在）: {path}", file=sys.stderr)
            continue
        n, changes = process_file(path, dry_run=args.dry_run)
        total += n
        for line in changes:
            all_changed_ids.add(line.split()[0])
            print(line)
        if n:
            print(f"{'[dry-run] ' if args.dry_run else ''}{path.name}: {n} 处对齐")
        else:
            print(f"{path.name}: 无需修改")

    if args.merge_main and not args.dry_run and all_changed_ids:
        n = merge_into_main_index(all_changed_ids)
        print(f"主索引已更新 {n} 条")

    print(f"合计 {'将' if args.dry_run else '已'}对齐 {total} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
