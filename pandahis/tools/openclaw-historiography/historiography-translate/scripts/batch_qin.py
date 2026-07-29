#!/usr/bin/env python3
"""秦朝史略批量翻译（跳过已有译稿，逐条串行，自动 aggregate + sync）。"""

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
from lib.verify import output_path  # noqa: E402

DYNASTY = "秦"


def _already_done(entry_id: str, name: str, out_dir: Path) -> bool:
    fp = output_path(entry_id, out_dir, name)
    if not fp.is_file():
        return False
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        return len(str(doc.get("翻译详情") or "")) >= 200
    except (OSError, json.JSONDecodeError):
        return False


def _missing_jobs(p: dict) -> list[dict]:
    from lib.config import default_index_path  # noqa: WPS433
    from lib.recall import load_global_index  # noqa: WPS433

    index = load_global_index(default_index_path())
    entries = [
        e
        for e in (index.get("entries") or [])
        if e.get("二级朝代坐标") == DYNASTY
    ]
    entries.sort(key=lambda e: str(e.get("史略ID") or ""))

    out: list[dict] = []
    for e in entries:
        entry_id = str(e.get("史略ID") or "").strip()
        name = str(e.get("史略名称") or "").strip()
        if not entry_id:
            continue
        if _already_done(entry_id, name, p["translate_output"]):
            continue
        out.append({"entry_id": entry_id, "entry_name": name})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="秦朝史略批量翻译")
    parser.add_argument(
        "--id",
        action="append",
        default=[],
        help="只处理指定史略ID（可重复）；省略则跑全部缺译",
    )
    args = parser.parse_args()
    only_ids = {str(x).strip() for x in args.id if str(x).strip()}

    load_dotenv()
    db.init_schema()
    runner.bootstrap()
    p = paths()

    runner.retry_failed_cmd(dynasty=DYNASTY)

    log_dir = p["root"] / "data" / "05工作流中间产物" / "翻译" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / "秦_translate_batch.log"
    summary_path = p["root"] / "data" / "05工作流中间产物" / "翻译" / f"秦_batch_summary_{stamp}.json"

    pending = _missing_jobs(p)
    if only_ids:
        pending = [j for j in pending if str(j.get("entry_id") or "") in only_ids]
        missing = only_ids - {str(j.get("entry_id") or "") for j in pending}
        if missing:
            print(f"⚠️ 下列 ID 已有成稿或不在秦朝缺译中，跳过: {sorted(missing)}", flush=True)
    print(f"秦朝待译: {len(pending)} 条", flush=True)

    results: list[dict] = []
    ok = routed = err = skip = 0

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n==== 秦批量翻译 {stamp} pending={len(pending)} ====\n")

        for i, job in enumerate(pending, 1):
            entry_id = str(job.get("entry_id") or "").strip()
            try:
                recalled = recall_entry(entry_id)
                name = str(recalled.get("史略名称") or job.get("entry_name") or "")
            except Exception as ex:
                print(f"[{i}/{len(pending)}] ❌ {entry_id} recall失败: {ex}", flush=True)
                log.write(f"[{i}] {entry_id} recall ERROR {ex}\n")
                results.append({"id": entry_id, "status": "error", "error": str(ex)})
                err += 1
                continue

            if _already_done(entry_id, name, p["translate_output"]):
                print(f"[{i}/{len(pending)}] ⏭ {entry_id} {name}", flush=True)
                log.write(f"[{i}] ⏭ {entry_id} {name}\n")
                db.update_job(entry_id, status="done", detail="skip: 已有译稿")
                results.append({"id": entry_id, "name": name, "status": "skip"})
                skip += 1
                continue

            print(f"[{i}/{len(pending)}] → {entry_id} {name} …", flush=True)
            log.write(f"[{i}] → {entry_id} {name}\n")
            try:
                rc = runner.run_one(entry_id, use_llm=True)
                if rc == 0:
                    status = "ok"
                    ok += 1
                elif rc == 2:
                    status = "routed"
                    routed += 1
                else:
                    status = "error"
                    err += 1
                results.append({"id": entry_id, "name": name, "status": status, "rc": rc})
                icon = "✅" if rc == 0 else ("↪" if rc == 2 else "❌")
                print(f"    {icon} rc={rc}", flush=True)
                log.write(f"    {icon} rc={rc}\n")
            except Exception as ex:
                traceback.print_exc()
                results.append({"id": entry_id, "name": name, "status": "error", "error": str(ex)})
                err += 1
                log.write(f"    ERROR {ex}\n")

    rebuild_aggregate(p["translate_output"])
    print("已重建 史略翻译_汇总.json", flush=True)

    from lib.remote_sync import sync_output_entry  # noqa: WPS433

    synced = 0
    for r in results:
        if r.get("status") != "ok":
            continue
        eid = r["id"]
        try:
            recalled = recall_entry(eid)
            name = str(recalled.get("史略名称") or "")
            ok_sync, _ = sync_output_entry(eid, p["translate_output"], name)
            if ok_sync:
                synced += 1
        except Exception:
            pass
    print(f"☁️ 本批同步 {synced} 条", flush=True)

    summary = {
        "stamp": stamp,
        "dynasty": DYNASTY,
        "pending_start": len(pending),
        "ok": ok,
        "routed": routed,
        "skip": skip,
        "err": err,
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"\n=== DONE ok={ok} routed={routed} skip={skip} err={err} ===\n"
        f"log → {log_path}\nsummary → {summary_path}",
        flush=True,
    )
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
