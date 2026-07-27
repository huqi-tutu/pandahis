#!/usr/bin/env python3
"""西周《史记》标注史略 20 条：清理本地+线上旧译，按最新翻译流水线强制重跑。

注：GLBL_00130（蔡叔度）、GLBL_00066（杞东楼公）、GLBL_00139（陈胡公满）
已从索引移除或降级为薄标注，不在本批重译范围内。
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TRANSLATE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(TRANSLATE_DIR))

from lib import db, runner  # noqa: E402
from lib.aggregate import rebuild_aggregate  # noqa: E402
from lib.config import load_dotenv, paths  # noqa: E402
from lib.recall import recall_entry  # noqa: E402
from lib.remote_sync import _connect  # noqa: E402
from lib.verify import output_path, sanitize_entry_name  # noqa: E402
from lib.work_artifacts import mother_draft_path, plan_path  # noqa: E402

# 二级朝代坐标=西周，主要史料出处均为《史记》各卷
ZHOU_XI_SHIJI_IDS = [
    "GLBL_00004",  # 卫康叔（世家重标 P1-P4，旧译冲突待重跑）
    "GLBL_00008",  # 古公亶父
    "GLBL_00009",  # 后稷
    "GLBL_00015",  # 周公旦（世家重标 P1-P13，旧译冲突待重跑）
    "GLBL_00016",  # 周共王
    "GLBL_00017",  # 周厉王
    "GLBL_00021",  # 周宣王
    "GLBL_00023",  # 周幽王
    "GLBL_00025",  # 周康王
    "GLBL_00028",  # 周成王
    "GLBL_00030",  # 周文王
    "GLBL_00031",  # 周昭王
    "GLBL_00035",  # 周武王
    "GLBL_00038",  # 周穆王
    "GLBL_00048",  # 季历
    "GLBL_00050",  # 宋微子（世家重标 P1-P3，旧译冲突待重跑）
    "GLBL_00087",  # 燕召公（世家重标 P1-P4，旧译冲突待重跑）
    "GLBL_00128",  # 管叔鲜
    "GLBL_00136",  # 郑桓公
    "GLBL_00222",  # 伯夷
]

# 世家重标后锚点收缩、必须强制清译重跑的条目
CONFLICT_FORCE_RERUN = frozenset({"GLBL_00004", "GLBL_00015", "GLBL_00050", "GLBL_00087"})


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
        detail="force rerun: 西周史记",
    )
    return removed


def _delete_online(ids: list[str]) -> int:
    if not ids:
        return 0
    conn = _connect()
    try:
        with conn.cursor() as cur:
            ph = ",".join(["%s"] * len(ids))
            cur.execute(
                f"DELETE FROM historical_box_detail WHERE box_id IN ({ph})",
                ids,
            )
            deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="西周史记 20 条强制重译")
    parser.add_argument("--dry-run", action="store_true", help="只清理+打印，不调用 LLM")
    parser.add_argument("--id", action="append", default=[], help="只处理指定 ID")
    parser.add_argument("--skip-delete-online", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="跳过已有译稿的清理与线上删除，仅补跑缺失条目",
    )
    args = parser.parse_args()

    ids = args.id or list(ZHOU_XI_SHIJI_IDS)
    db.init_schema()
    runner.bootstrap()
    p = paths()

    log_dir = p["root"] / "data" / "05工作流中间产物" / "翻译"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"西周史记20条_rerun_{stamp}.log"
    results: list[dict] = []

    # 批量清理本地
    print(f"清理本地译稿 {len(ids)} 条…", flush=True)
    for entry_id in ids:
        try:
            recalled = recall_entry(entry_id)
            name = str(recalled.get("史略名称") or "")
            out_fp = output_path(entry_id, p["translate_output"], name)
            if args.resume and entry_id not in CONFLICT_FORCE_RERUN and out_fp.is_file():
                detail = json.loads(out_fp.read_text(encoding="utf-8")).get("翻译详情", "")
                if len(str(detail)) >= 200:
                    print(f"  ⏭ 保留已有译稿 {entry_id} {name}", flush=True)
                    continue
            if not args.dry_run:
                _clean_entry(entry_id, name)
        except Exception as ex:
            print(f"  清理失败 {entry_id}: {ex}", flush=True)

    if not args.dry_run:
        rebuild_aggregate(p["translate_output"])
        print("已重建 史略翻译_汇总.json", flush=True)
        if not args.skip_delete_online and not args.resume:
            n = _delete_online(ids)
            print(f"☁️ 已删除线上 historical_box_detail {n} 条", flush=True)

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"==== 西周史记 20 条重译 {stamp} dry={args.dry_run} ====\n")
        print(f"日志 → {log_path}", flush=True)

        for i, entry_id in enumerate(ids, 1):
            try:
                recalled = recall_entry(entry_id)
                name = str(recalled.get("史略名称") or "")
                print(f"\n[{i}/{len(ids)}] {entry_id} {name}", flush=True)
                log.write(f"\n[{i}/{len(ids)}] {entry_id} {name}\n")
                out_fp = output_path(entry_id, p["translate_output"], name)
                if args.resume and entry_id not in CONFLICT_FORCE_RERUN and out_fp.is_file():
                    detail = json.loads(out_fp.read_text(encoding="utf-8")).get("翻译详情", "")
                    if len(str(detail)) >= 200:
                        results.append({"id": entry_id, "name": name, "status": "skip"})
                        log.write("  → skip (已有译稿)\n")
                        print("  → ⏭ 已有译稿", flush=True)
                        continue
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

    if not args.dry_run:
        rebuild_aggregate(p["translate_output"])
        from lib.remote_sync import sync_output_entry  # noqa: WPS433

        synced = 0
        for entry_id in ids:
            try:
                recalled = recall_entry(entry_id)
                name = str(recalled.get("史略名称") or "")
                ok, msg = sync_output_entry(entry_id, p["translate_output"], name)
                if ok:
                    synced += 1
                else:
                    print(f"  sync skip {entry_id}: {msg}", flush=True)
            except Exception as ex:
                print(f"  sync fail {entry_id}: {ex}", flush=True)
        print(f"☁️ 同步完成 {synced}/{len(ids)} 条", flush=True)

    ok = sum(1 for r in results if r.get("status") == "ok")
    routed = sum(1 for r in results if r.get("status") == "routed")
    err = sum(1 for r in results if r.get("status") == "error")
    print(f"\n=== DONE ok={ok} routed={routed} err={err} log={log_path} ===", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
