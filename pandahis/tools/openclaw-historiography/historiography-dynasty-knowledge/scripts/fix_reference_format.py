#!/usr/bin/env python3
"""统一史略详情文末「参考著作」格式（0 token）。

标准格式（勿用 * 包裹）::

    参考著作：
    1. 《书名·卷篇》
    2. …

用法:
  python3 fix_reference_format.py --dry-run
  python3 fix_reference_format.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SHARED = Path(__file__).resolve().parents[2] / "shared"
sys.path.insert(0, str(SHARED))

from reference_works import normalize_detail_references  # noqa: E402

SCOPES = {
    "translate": ROOT / "data" / "04史料翻译",
    "details": ROOT / "data" / "06朝代知识补全" / "详情",
}


def _fix_file(path: Path, *, apply: bool) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    detail = data.get("翻译详情")
    if not isinstance(detail, str) or "参考著作" not in detail:
        return False
    # 修复误写成字面量 \\n 的历史脏数据
    detail = detail.replace("\\n", "\n")
    new_detail = normalize_detail_references(detail)
    if new_detail == detail:
        return False
    if apply:
        data["翻译详情"] = new_detail
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="统一参考著作节格式")
    parser.add_argument("--scope", choices=["translate", "details", "all"], default="all")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply = args.apply and not args.dry_run

    scopes = list(SCOPES.values()) if args.scope == "all" else [SCOPES[args.scope]]
    changed = 0
    scanned = 0
    for base in scopes:
        if not base.is_dir():
            continue
        for fp in sorted(base.glob("GLBL_*.json")):
            scanned += 1
            if _fix_file(fp, apply=apply):
                changed += 1
                print(f"{'✏️' if apply else '🔍'} {fp.relative_to(ROOT)}")

    mode = "已写入" if apply else "待写入（dry-run）"
    print(f"\n{mode}: {changed}/{scanned} 条含参考著作的文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
