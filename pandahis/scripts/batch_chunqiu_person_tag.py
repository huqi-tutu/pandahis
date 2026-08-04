#!/usr/bin/env python3
"""春秋人物标签批量补全：全局索引 → person_tag --llm → 回写 → MySQL enrichment。"""

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

_env = TOOLS / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        import os

        os.environ.setdefault(key.strip(), val.strip())

from person_tag import TAG, annotate, filter_by_dynasty, is_eligible, mark_for_retag  # noqa: E402
from paths_config import histograph_paths  # noqa: E402

CHUNQIU_DYNASTY_ID = "CD_HX_CHUNQIU"
WORK_DIR = ROOT / "data/05工作流中间产物/朝代知识补全"
LOG_DIR = WORK_DIR / "logs"
TAG_FIELDS = (TAG, "人物标签判定理由", "人物标签置信度", "_auto_filled")


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
        index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["entries"] = entries
    data["chunqiu_person_tag_batch_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_tag_fields(all_entries: list[dict], work: list[dict]) -> None:
    by_id = {str(e.get("史略ID", "")).strip(): e for e in work}
    for i, e in enumerate(all_entries):
        eid = str(e.get("史略ID", "")).strip()
        src = by_id.get(eid)
        if not src:
            continue
        merged = dict(e)
        for key in TAG_FIELDS:
            if key in src:
                merged[key] = src[key]
        all_entries[i] = merged


def sync_mysql(index_path: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "import_box_index_json.py"),
        "--json",
        str(index_path),
        "--enrichment-only",
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


EXCLUDE_MANUAL_DEFAULT = frozenset({
    "卫庄公", "晋平公", "楚昭王", "鲁哀公", "齐灵公", "陈湣公", "郑成公", "燕庄公",
})


def select_targets(
    entries: list[dict],
    *,
    only_missing: bool,
    exclude_names: set[str],
    category: str | None,
) -> list[dict]:
    work = filter_by_dynasty(entries, CHUNQIU_DYNASTY_ID)
    out: list[dict] = []
    for e in work:
        if not is_eligible(e):
            continue
        if category and str(e.get("史略分类", "")).strip() != category:
            continue
        name = str(e.get("史略名称", "")).strip()
        if name in exclude_names:
            continue
        if only_missing and str(e.get(TAG, "")).strip():
            continue
        out.append(e)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="春秋人物标签批量补全")
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-mysql", action="store_true")
    parser.add_argument("--force", action="store_true", help="清除指纹/留空标记后重标")
    parser.add_argument("--only-missing", action="store_true", help="仅处理当前无标签条目")
    parser.add_argument(
        "--exclude-names",
        default=",".join(sorted(EXCLUDE_MANUAL_DEFAULT)),
        help="跳过的史略名称（逗号分隔），默认排除人工裁定8条",
    )
    parser.add_argument("--category", default=None, help="仅处理指定史略分类，如 诸侯")
    args = parser.parse_args()

    paths = histograph_paths()
    index_path = args.index or paths["global_index"]
    entries, is_list = load_global_entries(index_path)
    exclude = {x.strip() for x in args.exclude_names.split(",") if x.strip()}
    if args.only_missing or exclude or args.category:
        work = select_targets(
            entries,
            only_missing=True,
            exclude_names=exclude,
            category=args.category,
        )
    else:
        work = [e for e in filter_by_dynasty(entries, CHUNQIU_DYNASTY_ID) if is_eligible(e)]

    missing = sum(1 for e in work if not str(e.get(TAG, "")).strip())
    print(f"索引: {index_path}")
    print(f"本次处理: {len(work)} 条，其中无标签: {missing}")
    if exclude:
        print(f"排除: {', '.join(sorted(exclude))}")

    if args.dry_run:
        from person_tag import is_fresh  # noqa: WPS433

        pending = len(work) if args.force else sum(1 for e in work if not is_fresh(e))
        print(f"DRY-RUN: 待标注约 {pending} 条")
        return 0

    if args.force:
        for e in work:
            mark_for_retag(e)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_path = WORK_DIR / f"春秋_person_tag_rerun_{ts}.json"
    batch_doc = {"schema": "person-tag-rerun/v1", "朝代ID": CHUNQIU_DYNASTY_ID, "entries": work}

    def checkpoint() -> None:
        batch_doc["entries"] = work
        batch_path.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save_global_entries(index_path, entries, is_list=is_list)

    stats = annotate(work, use_llm=True, force=args.force, on_batch_done=checkpoint)
    save_global_entries(index_path, entries, is_list=is_list)
    batch_doc["entries"] = work
    batch_path.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("人物标签标注:", stats)
    print(f"批次快照: {batch_path}")

    still_missing = sum(1 for e in work if not str(e.get(TAG, "")).strip())
    print(f"本批无标签: {still_missing}/{len(work)}")

    if not args.no_mysql:
        sync_mysql(index_path)
        print("✅ MySQL enrichment 已同步")

    return 0 if still_missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
