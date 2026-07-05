#!/usr/bin/env python3
"""帝王缺口扫描、别名对齐、待补录合并。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from emperor_resolve import (
    align_skeleton_emperors,
    auto_supplement_emperors_from_skeleton,
    build_emperor_info_index,
    collect_unresolved_junji,
    merge_dynasty_supplements,
    merge_regime_supplements,
    merge_supplements_into_emperor_json,
    resolve_emperor_label,
    work_id_from_volume,
)
from lib_config import paths


def scan_junji_gaps(paths_list: list[Path]) -> int:
    eidx = build_emperor_info_index()
    missing: dict[str, list[str]] = {}
    resolvable: dict[str, str] = {}

    for fp in paths_list:
        data = json.loads(fp.read_text(encoding="utf-8"))
        work_id = work_id_from_volume(data.get("volume", ""))
        for entry in data.get("entries", []):
            if entry.get("史略分类") != "君纪":
                continue
            name = (entry.get("史略名称") or "").strip()
            if name in eidx:
                continue
            info, method = resolve_emperor_label(name, work_id=work_id, emperor_index=eidx)
            if info:
                resolvable[name] = f"{info['emperor']} ({method})"
            else:
                missing.setdefault(name, []).append(fp.name)

    print(f"\n📊 君纪缺口扫描（{len(paths_list)} 卷）")
    if resolvable:
        print(f"\n✅ 可别名解析（{len(resolvable)}）：")
        for k, v in sorted(resolvable.items()):
            print(f"   {k} → {v}")

    if missing:
        print(f"\n❌ 确需补录（{len(missing)}）：")
        for k, files in sorted(missing.items()):
            print(f"   {k}（如 {files[0]}）")
    else:
        print("\n✅ 无确需补录项")

    return len(missing)


def align_files(paths_list: list[Path], *, dry_run: bool) -> int:
    total = 0
    for fp in paths_list:
        data = json.loads(fp.read_text(encoding="utf-8"))
        data, changes = align_skeleton_emperors(data)
        unresolved = collect_unresolved_junji(data)
        if not changes and not unresolved:
            continue
        print(f"\n📄 {fp.name}")
        for c in changes[:20]:
            print(f"   · {c}")
        if len(changes) > 20:
            print(f"   … 另有 {len(changes) - 20} 处")
        if unresolved:
            print(f"   ⚠️  仍无法解析 {len(unresolved)} 项")
            for u in unresolved[:5]:
                print(f"      {u}")
        if changes and not dry_run:
            fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("   ✅ 已写入")
        elif changes:
            print("   (dry-run)")
        total += len(changes)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="帝王名解析 / 缺口 / 补录")
    parser.add_argument("paths", nargs="*", help="skeleton 文件或目录")
    parser.add_argument("--work", help="如 01史记")
    parser.add_argument("--scan", action="store_true", help="扫描君纪缺口")
    parser.add_argument("--align", action="store_true", help="别名对齐君纪名与坐标")
    parser.add_argument("--apply-supplements", action="store_true", help="合并帝王待补录.json")
    parser.add_argument("--apply-regime", action="store_true", help="补录西楚政权等")
    parser.add_argument(
        "--auto-from-skeleton",
        action="store_true",
        help="从 skeleton 自动补录/修补帝王.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.apply_supplements or args.apply_regime:
        if args.apply_regime:
            n, logs = merge_regime_supplements()
            n2, logs2 = merge_dynasty_supplements()
            for line in logs + logs2:
                print(line)
        if args.apply_supplements:
            n, logs = merge_supplements_into_emperor_json(dry_run=args.dry_run)
            print(f"补录帝王 {n} 条")
            for line in logs:
                print(f"  {line}")
        return 0

    files: list[Path] = []
    if args.work:
        ann = paths()["annotations"]
        files.extend(sorted(ann.glob(f"{args.work}_*_skeleton.json")))

    for p in args.paths:
        pp = Path(p)
        if pp.is_dir():
            files.extend(sorted(pp.glob("*_skeleton.json")))
        elif pp.is_file():
            files.append(pp)

    if not files:
        print("未指定 skeleton 文件", file=sys.stderr)
        return 1

    if args.scan:
        return 1 if scan_junji_gaps(files) else 0
    if args.auto_from_skeleton:
        for fp in files:
            data = json.loads(fp.read_text(encoding="utf-8"))
            added, patched, logs = auto_supplement_emperors_from_skeleton(
                data, dry_run=args.dry_run
            )
            print(f"\n📄 {fp.name}: 新增 {added}，修补 {patched}")
            for line in logs:
                print(f"   {line}")
        return 0
    if args.align:
        align_files(files, dry_run=args.dry_run)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
