#!/usr/bin/env python3
"""将 skeleton / 条目索引 / 全局史略索引中的帝王ID 与 reference/帝王.json 对齐。"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parent
if str(SKILL) not in sys.path:
    sys.path.insert(0, str(SKILL))

from coordinate_index import coords_and_ids_from_emperor, load_emperor_records
from lib_config import paths

DEFAULT_ANNOT = paths()["annotations"]


def build_name_index() -> dict[str, dict]:
    return {r["emperor"]: r for r in load_emperor_records()}


def sync_entry(entry: dict, by_name: dict[str, dict]) -> list[str]:
    logs: list[str] = []
    coord = (entry.get("四级帝王坐标") or "").strip()
    if not coord:
        return logs

    info = by_name.get(coord)
    if not info:
        logs.append(f"WARN 帝王表无「{coord}」({entry.get('史略ID')})")
        return logs

    new_id = info["id"]
    old_id = (entry.get("帝王ID") or "").strip()
    if old_id != new_id:
        logs.append(f"帝王ID {old_id} → {new_id} ({coord})")

    coords = coords_and_ids_from_emperor(info)
    for field, val in coords.items():
        if val and entry.get(field) != val:
            entry[field] = val

    return logs


def sync_file(path: Path, by_name: dict[str, dict], backup_dir: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    entries = data.get("entries")
    if not entries:
        return []

    logs: list[str] = []
    for entry in entries:
        for line in sync_entry(entry, by_name):
            logs.append(f"{path.name} [{entry.get('史略ID')}] {line}")

    if not logs:
        return []

    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return logs


def main() -> int:
    annot = DEFAULT_ANNOT
    if not annot.is_dir():
        print(f"❌ 标注目录不存在: {annot}")
        return 1

    by_name = build_name_index()
    targets = sorted(annot.glob("*_skeleton.json")) + sorted(annot.glob("*_条目索引.json"))
    global_idx = annot / "史略索引_01至02.json"
    if global_idx.is_file():
        targets.append(global_idx)

    backup_dir = annot / f"_backup_emperor_id_sync_{datetime.now():%Y%m%d_%H%M%S}"
    all_logs: list[str] = []
    touched = 0
    for path in targets:
        rel_logs = sync_file(path, by_name, backup_dir)
        if rel_logs:
            touched += 1
            all_logs.extend(rel_logs)

    print(f"✅ 修正 {len(all_logs)} 处，涉及 {touched} 个文件")
    print(f"   备份: {backup_dir}")
    for line in all_logs:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
