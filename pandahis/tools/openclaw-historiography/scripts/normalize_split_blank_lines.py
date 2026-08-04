#!/usr/bin/env python3
"""去除拆分后原文中的纯空白行，使 txt 行号与段落索引段号对齐。

仅删除 ``strip()`` 后为空的行，不改动任何非空行内容（含行首空格）。
段落切分本就以「非空行」为准（paragraph_mode=line）；空白行不应占段号。

用法:
  python3 normalize_split_blank_lines.py --work 02汉书 --dry-run
  python3 normalize_split_blank_lines.py --work 02汉书 --rebuild-index
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANNOTATE = ROOT / "historiography-annotate"
ORCH = ROOT / "historiography-orchestrator"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ANNOTATE))
sys.path.insert(0, str(ORCH))

from paths_config import resolve_split_dir  # noqa: E402
from paragraph_utils import count_source_paragraphs, split_paragraphs, split_mode_for_work  # noqa: E402
from lib.config import get_work_config, paths  # noqa: E402
from lib.paragraph_index import build_index_for_file, list_volume_files, write_index  # noqa: E402


def normalize_text(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    kept = [ln for ln in lines if ln.strip()]
    removed = len(lines) - len(kept)
    normalized = "\n".join(kept)
    if text.endswith("\n"):
        normalized += "\n"
    return normalized, removed


def verify_paragraphs_unchanged(src: Path, work: str, before: str, after: str) -> None:
    mode = split_mode_for_work(work, before)
    old_paras = split_paragraphs(before, mode)
    new_paras = split_paragraphs(after, mode)
    if old_paras != new_paras:
        raise RuntimeError(
            f"{src.name}: 去空白行后段落内容变化 "
            f"({len(old_paras)} → {len(new_paras)} 段)，已中止"
        )


def process_work(work: str, *, dry_run: bool, rebuild_index: bool) -> int:
    cfg = get_work_config(work)
    split_dir = resolve_split_dir(cfg["split_dir"])
    mode = cfg.get("paragraph_mode") or split_mode_for_work(work)
    changed_files: list[tuple[Path, int]] = []

    for vol, fp in list_volume_files(work):
        text = fp.read_text(encoding="utf-8")
        normalized, removed = normalize_text(text)
        if removed <= 0:
            continue
        verify_paragraphs_unchanged(fp, work, text, normalized)
        changed_files.append((fp, removed))
        if not dry_run:
            fp.write_text(normalized, encoding="utf-8")

    print(f"\n📚 {work} · 模式={mode}")
    if not changed_files:
        print("✅ 无需处理（无纯空白行）")
    else:
        action = "将修改" if dry_run else "已修改"
        print(f"{'🔍' if dry_run else '✅'} {action} {len(changed_files)} 个文件：")
        for fp, n in changed_files[:20]:
            print(f"   · {fp.name}（删除 {n} 行空白）")
        if len(changed_files) > 20:
            print(f"   … 另有 {len(changed_files) - 20} 个")

    if dry_run or not rebuild_index:
        return 0

    idx_dir = paths()["paragraph_index"]
    for vol, fp in list_volume_files(work):
        idx_path = idx_dir / f"{work}_{vol}.json"
        old_idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.is_file() else None
        new_idx = build_index_for_file(work, vol, fp, mode)
        if old_idx:
            old_texts = [p["text"] for p in old_idx.get("paragraphs", [])]
            new_texts = [p["text"] for p in new_idx.get("paragraphs", [])]
            if old_texts != new_texts:
                raise RuntimeError(f"{idx_path.name}: 重建后段落文本与旧索引不一致")
        write_index(work, vol, new_idx)
    print(f"✅ 已重建段落索引 → {idx_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="去除拆分原文纯空白行并对齐段落索引")
    parser.add_argument("--work", default="02汉书", help="著作前缀，如 02汉书")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="写回 txt 后重建段落索引（段文本须与旧索引一致）",
    )
    args = parser.parse_args()
    return process_work(args.work, dry_run=args.dry_run, rebuild_index=args.rebuild_index)


if __name__ == "__main__":
    raise SystemExit(main())
