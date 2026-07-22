#!/usr/bin/env python3
"""商朝史略分流：厚史料删译后重跑 translate；薄史料删译后走 dynasty_supplement compose-detail。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TRANSLATE_DIR = SCRIPT_DIR.parent
DK_SCRIPTS = TRANSLATE_DIR.parent / "historiography-dynasty-knowledge" / "scripts"
sys.path.insert(0, str(TRANSLATE_DIR))
sys.path.insert(0, str(DK_SCRIPTS))

from batch_yin_benji_rerun import THICK_IDS, THIN_IDS, _clean_entry  # noqa: E402
from lib import db  # noqa: E402
from lib.config import load_dotenv, paths  # noqa: E402
from lib.recall import recall_entry  # noqa: E402

DYNASTY = "商"


def _export_thin_entries_json() -> Path:
    """将 9 条薄史料从全局索引导出到 商_人物.json，供 compose-detail 读取。"""
    root = paths()["root"]
    idx = json.loads((root / "data/03索引标注条目/史略索引_01至02.json").read_text(encoding="utf-8"))
    thin_set = set(THIN_IDS)
    entries = [e for e in idx["entries"] if e.get("史略ID") in thin_set]
    if len(entries) != len(THIN_IDS):
        found = {e["史略ID"] for e in entries}
        missing = thin_set - found
        raise SystemExit(f"薄史料索引缺失: {missing}")

    out_path = root / "data/06朝代知识补全/索引条目/商_人物.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema": "dynasty-knowledge-entries/v1",
        "朝代": DYNASTY,
        "category": "人物",
        "note": "殷本纪薄史料君王（<100字），由全局索引导出，走朝代知识补全",
        "entries": entries,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 导出薄史料索引 → {out_path}（{len(entries)} 条）", flush=True)
    return out_path


def delete_all_shang_translations() -> int:
    """删除 16 条商朝翻译产出与中间产物，重置任务状态。"""
    removed = 0
    all_ids = list(THICK_IDS) + list(THIN_IDS)
    for entry_id in all_ids:
        try:
            recalled = recall_entry(entry_id)
            name = str(recalled.get("史略名称") or "")
            removed += len(_clean_entry(entry_id, name))
        except Exception as ex:
            print(f"⚠️ 清理 {entry_id} 失败: {ex}", flush=True)
    print(f"🗑️ 已清理翻译产出/中间产物（约 {removed} 个文件）", flush=True)
    return removed


def run_dynasty_research() -> None:
    research = paths()["root"] / "data/05工作流中间产物/朝代知识补全/商_研究报告.md"
    if research.is_file() and research.stat().st_size > 200:
        print(f"↪ 研究报告已存在: {research}", flush=True)
        return
    cmd = [
        sys.executable,
        str(DK_SCRIPTS / "dynasty_supplement.py"),
        "--dynasty",
        DYNASTY,
        "--step",
        "research",
        "--skip-approval",
    ]
    print("📚 生成商朝研究报告…", flush=True)
    subprocess.run(cmd, check=True)


def run_thin_compose_detail(*, dry_run: bool = False) -> list[dict]:
    """9 条薄史料：anchor + compose-detail。"""
    entries_path = _export_thin_entries_json()
    results: list[dict] = []
    for i, entry_id in enumerate(THIN_IDS, 1):
        name = ""
        try:
            recalled = recall_entry(entry_id)
            name = str(recalled.get("史略名称") or "")
            print(f"\n[{i}/{len(THIN_IDS)}] 朝代补全 {entry_id} {name}", flush=True)
            if dry_run:
                results.append({"id": entry_id, "name": name, "status": "dry_run"})
                continue
            for step in ("anchor-research", "compose-detail"):
                cmd = [
                    sys.executable,
                    str(DK_SCRIPTS / "dynasty_supplement.py"),
                    "--dynasty",
                    DYNASTY,
                    "--step",
                    step,
                    "--entry-id",
                    entry_id,
                    "--skip-approval",
                    "--auto-revise",
                ]
                rc = subprocess.run(cmd).returncode
                if rc != 0:
                    results.append({"id": entry_id, "name": name, "status": "error", "step": step})
                    break
            else:
                results.append({"id": entry_id, "name": name, "status": "ok"})
                print(f"  ✅ {entry_id}", flush=True)
        except Exception as ex:
            traceback.print_exc()
            results.append({"id": entry_id, "name": name, "status": "error", "error": str(ex)})
    return results


def rebuild_dynasty_aggregate() -> None:
    from dynasty_supplement import aggregate_details, output_paths  # noqa: E402

    p = output_paths(DYNASTY)
    aggregate_details(p)


def run_thick_translate(*, dry_run: bool = False) -> int:
    from lib import runner  # noqa: E402

    db.init_schema()
    runner.bootstrap()
    rc = 0
    for i, entry_id in enumerate(THICK_IDS, 1):
        recalled = recall_entry(entry_id)
        name = str(recalled.get("史略名称") or "")
        print(f"\n[{i}/{len(THICK_IDS)}] 翻译 {entry_id} {name}", flush=True)
        if dry_run:
            continue
        one_rc = runner.run_one(entry_id, use_llm=True)
        if one_rc not in (0, 2):
            rc = 1
    return rc


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="商朝史略分流编排")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--phase",
        choices=("all", "delete", "thin", "thick"),
        default="all",
        help="all=全流程；delete=仅删译；thin/thick=单跑一支",
    )
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_dir = paths()["root"] / "data/05工作流中间产物/翻译"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"商朝分流_{stamp}.log"
    print(f"日志 → {log_path}", flush=True)

    if args.phase in ("all", "delete"):
        delete_all_shang_translations()
        if args.phase == "delete":
            return 0

    thin_err = 0
    thick_err = 0

    if args.phase in ("all", "thin"):
        run_dynasty_research()
        thin_results = run_thin_compose_detail(dry_run=args.dry_run)
        thin_err = sum(1 for r in thin_results if r.get("status") == "error")
        if not args.dry_run and thin_err == 0:
            try:
                rebuild_dynasty_aggregate()
            except Exception as ex:
                print(f"⚠️ 汇总重建失败: {ex}", flush=True)

    if args.phase in ("all", "thick"):
        thick_err = run_thick_translate(dry_run=args.dry_run)
        if not args.dry_run:
            from lib.runner import rebuild_aggregate  # noqa: E402

            rebuild_aggregate(paths()["translate_output"])

    print(
        f"\n=== DONE thin_err={thin_err} thick_err={thick_err} dry={args.dry_run} ===",
        flush=True,
    )
    return 1 if (thin_err or thick_err) else 0


if __name__ == "__main__":
    raise SystemExit(main())
