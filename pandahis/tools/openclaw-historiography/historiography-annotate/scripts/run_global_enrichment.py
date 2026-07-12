#!/usr/bin/env python3
"""全局史略 enrichment：优先级 → 峰值 → 人物标签。

卷级 Step4 不再写入优先级；本脚本为全局索引 SSOT 批处理入口。

用法:
  python3 run_global_enrichment.py
  python3 run_global_enrichment.py --index /path/to/史略索引_01至02.json
  python3 run_global_enrichment.py --skip-priority --skip-peak
  python3 run_global_enrichment.py --dry-run
  python3 run_global_enrichment.py --dynasty-id CD_HX_XIHAN
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ANNOTATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INDEX = (
    REPO_ROOT / "data" / "03索引标注条目" / "史略索引_01至02.json"
)


def _run(cmd: list[str], label: str) -> None:
    print(f"\n{'=' * 60}\n▶ {label}\n{'=' * 60}", flush=True)
    proc = subprocess.run(cmd, cwd=str(ANNOTATE_DIR))
    if proc.returncode != 0:
        raise SystemExit(f"{label} 失败 (exit {proc.returncode})")


def main() -> None:
    ap = argparse.ArgumentParser(description="全局史略 enrichment 批处理")
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-priority", action="store_true")
    ap.add_argument("--skip-peak", action="store_true")
    ap.add_argument("--skip-tag", action="store_true")
    ap.add_argument("--force-tag", action="store_true")
    ap.add_argument("--dynasty-id", default=None)
    ap.add_argument("--no-llm", action="store_true", help="峰值/标签仅规则层（调试用）")
    args = ap.parse_args()

    index = args.index.resolve()
    if not index.is_file():
        raise SystemExit(f"索引不存在: {index}")

    py = sys.executable
    llm_flag: list[str] = [] if args.no_llm else ["--llm"]

    if not args.skip_priority:
        pri_cmd = [py, str(ANNOTATE_DIR / "dynasty_priority.py"), str(index), *llm_flag]
        if args.dry_run:
            pri_cmd.append("--dry-run")
        if args.dynasty_id:
            pri_cmd.extend(["--dynasty-id", args.dynasty_id])
        _run(pri_cmd, "1/3 朝代全局优先级 (dynasty_priority)")

    if not args.skip_peak:
        peak_cmd = [py, str(ANNOTATE_DIR / "peak_year.py"), str(index), *llm_flag]
        if args.dry_run:
            peak_cmd.append("--dry-run")
        if args.dynasty_id:
            peak_cmd.extend(["--dynasty-id", args.dynasty_id])
        _run(peak_cmd, "2/3 峰值年 (peak_year)")

    if not args.skip_tag:
        tag_cmd = [py, str(ANNOTATE_DIR / "person_tag.py"), str(index)]
        if args.no_llm:
            pass
        else:
            tag_cmd.append("--llm")
        if args.dry_run:
            tag_cmd.append("--dry-run")
        if args.force_tag:
            tag_cmd.append("--force")
        if args.dynasty_id:
            tag_cmd.extend(["--dynasty-id", args.dynasty_id])
        _run(tag_cmd, "3/3 人物标签 (person_tag)")

    print("\n✅ 全局 enrichment 完成", flush=True)
    print(
        "下一步: python3 scripts/import_box_index_json.py "
        f"（或 --enrichment-only 增量写 DB）",
        flush=True,
    )


if __name__ == "__main__":
    main()
