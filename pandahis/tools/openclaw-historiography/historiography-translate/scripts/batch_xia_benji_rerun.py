#!/usr/bin/env python3
"""夏本纪 6 人：清理旧产出并按最新翻译流水线强制重跑。"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TRANSLATE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(TRANSLATE_DIR))

from lib import db, runner  # noqa: E402
from lib.config import load_dotenv, paths  # noqa: E402
from lib.recall import recall_entry  # noqa: E402
from lib.verify import output_path, sanitize_entry_name  # noqa: E402
from lib.work_artifacts import mother_draft_path, plan_path  # noqa: E402

XIA_BENJI_IDS = [
    "GLBL_00096",  # 禹
    "GLBL_00010",  # 启
    "GLBL_00043",  # 太康
    "GLBL_00001",  # 中康
    "GLBL_00047",  # 孔甲
    "GLBL_00067",  # 桀
]


def _clean_entry(entry_id: str, entry_name: str) -> list[str]:
    p = paths()
    out_dir = p["translate_output"]
    work_dir = p["translate_work"]
    removed: list[str] = []
    stem = f"{entry_id}_{sanitize_entry_name(entry_name)}"
    targets = [
        output_path(entry_id, out_dir, entry_name),
        plan_path(entry_id, entry_name, work_dir),
        mother_draft_path(entry_id, entry_name, work_dir),
        work_dir / f".heartbeat_{entry_id}.json",
    ]
    for pat in (
        f"{stem}.chunk-*.json",
        f"{stem}.chunk-*.plan.json",
        f"{stem}.chunk-*.mother.json",
        f"{stem}.*",
    ):
        for fp in work_dir.glob(pat):
            targets.append(fp)
    seen: set[Path] = set()
    for fp in targets:
        if fp in seen or not fp.is_file():
            continue
        seen.add(fp)
        fp.unlink()
        removed.append(str(fp.relative_to(p["root"])))
    db.upsert_job(entry_id, entry_name=entry_name, status="pending", reset_status=True)
    db.update_job(
        entry_id,
        source_fingerprint="",
        output_word_count=0,
        fail_count=0,
        detail="force rerun: 夏本纪",
    )
    return removed


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="夏本纪 6 人强制重译")
    parser.add_argument("--dry-run", action="store_true", help="只清理+打印，不调用 LLM")
    parser.add_argument("--id", action="append", default=[], help="只处理指定 ID")
    args = parser.parse_args()

    ids = args.id or list(XIA_BENJI_IDS)
    db.init_schema()
    runner.bootstrap()

    log_dir = paths()["root"] / "data" / "05工作流中间产物" / "翻译"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"夏本纪6人_rerun_{stamp}.log"
    results: list[dict] = []

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"==== 夏本纪 6 人重译 {stamp} dry={args.dry_run} ====\n")
        print(f"日志 → {log_path}", flush=True)

        for i, entry_id in enumerate(ids, 1):
            try:
                recalled = recall_entry(entry_id)
                name = str(recalled.get("史略名称") or "")
                print(f"\n[{i}/{len(ids)}] {entry_id} {name}", flush=True)
                log.write(f"\n[{i}/{len(ids)}] {entry_id} {name}\n")
                removed = _clean_entry(entry_id, name) if not args.dry_run else []
                for r in removed:
                    log.write(f"  删除 {r}\n")
                print(f"  清理 {len(removed)} 个文件", flush=True)
                if args.dry_run:
                    results.append({"id": entry_id, "name": name, "status": "dry_run"})
                    continue
                rc = runner.run_one(entry_id, use_llm=True)
                if rc == 0:
                    status = "ok"
                elif rc == 2:
                    status = "routed"
                else:
                    status = "error"
                results.append({"id": entry_id, "name": name, "status": status, "rc": rc})
                log.write(f"  → {status} rc={rc}\n")
                icon = "✅" if rc == 0 else ("↪" if rc == 2 else "❌")
                print(f"  → {icon} rc={rc}", flush=True)
            except Exception as ex:
                traceback.print_exc()
                results.append({"id": entry_id, "status": "error", "error": str(ex)})
                log.write(f"  ERROR {ex}\n")

    ok = sum(1 for r in results if r.get("status") == "ok")
    routed = sum(1 for r in results if r.get("status") == "routed")
    err = sum(1 for r in results if r.get("status") == "error")
    print(f"\n=== DONE ok={ok} routed={routed} err={err} log={log_path} ===", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
