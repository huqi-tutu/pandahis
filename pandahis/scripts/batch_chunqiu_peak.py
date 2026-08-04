#!/usr/bin/env python3
"""春秋峰值年批量补全：全局索引 → peak_year --llm → 回写 → MySQL enrichment。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "openclaw-historiography"
ANNOTATE = TOOLS / "historiography-annotate"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ANNOTATE))

# 加载 LLM 环境变量（与 dynasty_supplement 一致）
_env = TOOLS / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        import os
        os.environ.setdefault(key.strip(), val.strip())

from peak_year import annotate, filter_entries_by_dynasty  # noqa: E402
from paths_config import histograph_paths  # noqa: E402

CHUNQIU_DYNASTY_ID = "CD_HX_CHUNQIU"
WORK_DIR = ROOT / "data/05工作流中间产物/朝代知识补全"
LOG_DIR = WORK_DIR / "logs"


def load_global_entries(index_path: Path) -> tuple[list[dict], bool]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, True
    entries = data.get("entries")
    if isinstance(entries, list):
        return entries, False
    raise SystemExit("全局索引格式不支持")


def save_global_entries(index_path: Path, entries: list[dict], *, is_list: bool) -> None:
    if is_list:
        index_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["entries"] = entries
    data["chunqiu_peak_batch_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_peak_fields(all_entries: list[dict], work: list[dict]) -> int:
    by_id = {str(e.get("史略ID", "")).strip(): e for e in work}
    changed = 0
    for i, e in enumerate(all_entries):
        eid = str(e.get("史略ID", "")).strip()
        src = by_id.get(eid)
        if not src:
            continue
        for key in ("峰值年", "峰值原因", "峰值类型", "峰值置信度", "_auto_filled"):
            if src.get(key) != e.get(key):
                changed += 1
                break
        all_entries[i] = {**e, **{k: src[k] for k in ("峰值年", "峰值原因", "峰值类型", "峰值置信度", "_auto_filled") if k in src}}
    return changed


def sync_mysql(index_path: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "import_box_index_json.py"),
        "--json",
        str(index_path),
        "--enrichment-only",
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="春秋峰值年批量补全")
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-mysql", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    paths = histograph_paths()
    index_path = args.index or paths["global_index"]
    entries, is_list = load_global_entries(index_path)
    work = filter_entries_by_dynasty(entries, CHUNQIU_DYNASTY_ID)
    missing = sum(1 for e in work if e.get("峰值年") is None)
    print(f"索引: {index_path}")
    print(f"春秋条目: {len(work)}，缺峰值年: {missing}")

    if args.dry_run:
        stats = annotate(work, use_llm=True, force=args.force)
        print("dry-run stats:", stats)
        return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_path = WORK_DIR / f"春秋_peak_batch_{ts}.json"
    batch_doc = {"schema": "peak-batch/v1", "朝代ID": CHUNQIU_DYNASTY_ID, "entries": work}

    def checkpoint() -> None:
        batch_doc["entries"] = work
        batch_path.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        merge_peak_fields(entries, work)
        save_global_entries(index_path, entries, is_list=is_list)

    stats = annotate(work, use_llm=True, force=args.force, on_batch_done=checkpoint)
    merge_peak_fields(entries, work)
    save_global_entries(index_path, entries, is_list=is_list)
    batch_doc["entries"] = work
    batch_path.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("峰值年标注:", stats)
    print(f"批次快照: {batch_path}")

    if not args.no_mysql:
        sync_mysql(index_path)
        print("✅ MySQL enrichment 已同步")

    still_missing = sum(1 for e in work if e.get("峰值年") is None)
    print(f"春秋峰值覆盖: {len(work) - still_missing}/{len(work)}")
    return 0 if still_missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
