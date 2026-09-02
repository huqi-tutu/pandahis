#!/usr/bin/env python3
"""后汉书×三国志一期标注人物标签批量补全：03至04 索引 → person_tag --llm → 回写 → 重建线上 → MySQL enrichment。"""

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
DEFAULT_INDEX = ROOT / "data" / "10新标注条目" / "史略索引_03至04.json"
ONLINE_INDEX = ROOT / "data" / "12线上史略索引" / "史略索引_online.json"
WORK_DIR = ROOT / "data" / "05工作流中间产物" / "朝代知识补全"
LOG_DIR = WORK_DIR / "logs"

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

from person_tag import TAG, annotate, is_eligible, mark_for_retag  # noqa: E402

TAG_FIELDS = (TAG, "人物标签判定理由", "人物标签置信度", "_auto_filled")
DYNASTY_CHOICES = ("东汉", "三国", "all")


def load_entries(index_path: Path) -> tuple[list[dict], bool]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data, True
    entries = data.get("entries")
    if isinstance(entries, list):
        return entries, False
    raise SystemExit(f"索引格式不支持: {index_path}")


def save_entries(index_path: Path, entries: list[dict], *, is_list: bool, meta_key: str) -> None:
    if is_list:
        index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["entries"] = entries
    data[meta_key] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_targets(
    entries: list[dict],
    *,
    dynasty: str,
    only_missing: bool,
    category: str | None,
) -> list[dict]:
    dynasties = set(DYNASTY_CHOICES) - {"all"}
    if dynasty != "all":
        dynasties = {dynasty}
    out: list[dict] = []
    for e in entries:
        if str(e.get("二级朝代坐标") or "").strip() not in dynasties:
            continue
        if not is_eligible(e):
            continue
        if category and str(e.get("史略分类", "")).strip() != category:
            continue
        if only_missing and str(e.get(TAG, "")).strip():
            continue
        out.append(e)
    return out


def rebuild_online() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_online_index.py")],
        check=True,
        cwd=str(ROOT),
    )


def sync_mysql_enrichment() -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "import_box_index_json.py"),
            "--json",
            str(ONLINE_INDEX),
            "--enrichment-only",
        ],
        check=True,
        cwd=str(ROOT),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="03至04 东汉/三国人物标签批量补全")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--dynasty", choices=DYNASTY_CHOICES, default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-mysql", action="store_true", help="跳过 rebuild online + MySQL enrichment")
    parser.add_argument("--force", action="store_true", help="清除指纹/留空标记后重标")
    parser.add_argument("--only-missing", action="store_true", default=True)
    parser.add_argument("--category", default=None, help="仅处理指定史略分类")
    args = parser.parse_args()

    index_path = args.index
    if not index_path.is_file():
        raise SystemExit(f"缺少索引: {index_path}")

    entries, is_list = load_entries(index_path)
    work = select_targets(
        entries,
        dynasty=args.dynasty,
        only_missing=args.only_missing,
        category=args.category,
    )
    missing = sum(1 for e in work if not str(e.get(TAG, "")).strip())
    print(f"索引: {index_path}")
    print(f"朝代: {args.dynasty}")
    print(f"本次处理: {len(work)} 条，其中无标签: {missing}")

    if args.dry_run:
        from person_tag import is_fresh  # noqa: WPS433

        pending = len(work) if args.force else sum(1 for e in work if not is_fresh(e))
        print(f"DRY-RUN: 待标注约 {pending} 条")
        return 0

    if not work:
        print("无需处理")
        return 0

    if args.force:
        for e in work:
            mark_for_retag(e)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = args.dynasty.replace("all", "东汉三国")
    batch_path = WORK_DIR / f"{slug}_person_tag_{ts}.json"
    batch_doc = {
        "schema": "person-tag-rerun/v1",
        "source": "03至04",
        "dynasty": args.dynasty,
        "entries": work,
    }

    def checkpoint() -> None:
        batch_doc["entries"] = work
        batch_path.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        save_entries(index_path, entries, is_list=is_list, meta_key=f"{slug}_person_tag_batch_at")

    stats = annotate(work, use_llm=True, force=args.force, on_batch_done=checkpoint)
    save_entries(index_path, entries, is_list=is_list, meta_key=f"{slug}_person_tag_batch_at")
    batch_doc["entries"] = work
    batch_path.write_text(json.dumps(batch_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("人物标签标注:", stats)
    print(f"批次快照: {batch_path}")

    still_missing = sum(1 for e in work if not str(e.get(TAG, "")).strip())
    print(f"本批无标签: {still_missing}/{len(work)}")

    if not args.no_mysql:
        print("重建线上索引…")
        rebuild_online()
        print("同步 MySQL enrichment…")
        sync_mysql_enrichment()
        print("✅ 线上索引 + MySQL enrichment 已同步")

    return 0 if still_missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
