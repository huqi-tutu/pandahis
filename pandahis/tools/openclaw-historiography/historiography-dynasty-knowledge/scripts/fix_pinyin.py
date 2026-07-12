#!/usr/bin/env python3
"""就地清洗详情中的通识误标拼音（无需重跑 compose-detail）。

规则 SSOT：dynasty_supplement_lib.clean_over_pinyin（继承翻译规则七）

用法：
  python3 fix_pinyin.py --id-range 561 585          # 预览
  python3 fix_pinyin.py --id-range 561 585 --apply  # 写回 JSON
  python3 fix_pinyin.py --file path/to/GLBL_xxx.json --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
OPENCLAW_ROOT = SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(OPENCLAW_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from paths_config import (  # noqa: E402
    DIR_DYNASTY_KNOWLEDGE,
    SUBDIR_DYNASTY_KNOWLEDGE_DETAILS,
    get_histograph_root,
)

import dynasty_supplement_lib as dkl  # noqa: E402

ROOT = get_histograph_root()
DETAILS_DIR = ROOT / "data" / DIR_DYNASTY_KNOWLEDGE / SUBDIR_DYNASTY_KNOWLEDGE_DETAILS


def glbl_num(path: Path) -> int | None:
    m = re.search(r"GLBL_(\d+)", path.name)
    return int(m.group(1)) if m else None


def process_file(path: Path, *, apply: bool) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    raw = str(doc.get("翻译详情", ""))
    cleaned, changes = dkl.clean_over_pinyin(raw)
    if not changes:
        return []
    if apply:
        doc["翻译详情"] = cleaned
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [f"{path.name}: {c}" for c in changes]


def main() -> int:
    parser = argparse.ArgumentParser(description="清洗详情通识误标拼音")
    parser.add_argument("--id-range", nargs=2, type=int, metavar=("FROM", "TO"))
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="写回文件（默认仅预览）")
    args = parser.parse_args()

    paths: list[Path] = list(args.file)
    if args.id_range:
        lo, hi = args.id_range
        for p in sorted(DETAILS_DIR.glob("GLBL_*.json")):
            n = glbl_num(p)
            if n is not None and lo <= n <= hi:
                paths.append(p)

    if not paths:
        print("未指定文件或 ID 范围", file=sys.stderr)
        return 1

    total_changes = 0
    touched = 0
    for path in sorted(set(paths)):
        if not path.is_file():
            print(f"跳过（不存在）: {path}", file=sys.stderr)
            continue
        changes = process_file(path, apply=args.apply)
        if changes:
            touched += 1
            total_changes += len(changes)
            for line in changes:
                print(line)

    mode = "已写回" if args.apply else "预览"
    print(f"\n{mode}：{touched} 个文件，{total_changes} 处替换")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
