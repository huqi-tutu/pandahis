#!/usr/bin/env python3
"""商朝人物关系批量补全（逐人串行，跳过已 verify 通过的条目）。"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import relations_lib as rl  # noqa: E402

DYNASTY = "商"


def _default_mysql() -> dict:
    return {
        "host": "49.235.165.220",
        "port": 3306,
        "user": "histomap_admin",
        "password": "pandahis#666",
        "db": "histomap",
    }


def _already_done(entry: dict, paths: dict) -> bool:
    subject = str(entry.get("史略名称", "")).strip()
    out = rl.output_path(paths, subject)
    if not out.is_file():
        return False
    ok, _ = rl.run_verify(out, strict=True)
    return ok


def main() -> int:
    rl.validate_histograph_root()
    rl.ensure_deepseek_v4_pro()
    paths = rl.histograph_paths()
    mid = paths["person_relations_work"]
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = mid / f"商_relations_batch_summary_{stamp}.json"
    manifest_path = paths["person_relations"] / "商_关系补全_manifest.json"

    persons = rl.list_dynasty_persons(DYNASTY)
    mysql = _default_mysql()
    print(f"商朝人物 {len(persons)} 人（蕃祚不建关系表）", flush=True)

    results: list[dict] = []
    completed: list[dict] = []

    for i, e in enumerate(persons, 1):
        eid = str(e.get("史略ID", "")).strip()
        name = str(e.get("史略名称", "")).strip()
        out = rl.output_path(paths, name)

        if _already_done(e, paths):
            count = len(json.loads(out.read_text(encoding="utf-8")))
            print(f"[{i}/{len(persons)}] ⏭ {eid} {name} ({count} 条)", flush=True)
            try:
                rl.import_json_file(out, entry_id=eid, mysql=mysql)
                print(f"    ☁️ 已同步入库", flush=True)
            except Exception as ex:
                print(f"    ⚠️ 入库失败: {ex}", flush=True)
            results.append({"id": eid, "name": name, "status": "skip", "count": count})
            completed.append(
                {
                    "glbl": eid,
                    "name": name,
                    "file": out.name,
                    "count": count,
                    "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                }
            )
            continue

        print(f"[{i}/{len(persons)}] → {eid} {name} …", flush=True)
        try:
            rl.compose_one(entry_id=eid, revise_on_fail=True, sync_db=True, mysql=mysql)
            count = len(json.loads(out.read_text(encoding="utf-8")))
            print(f"    ✅ {eid} {name} {count} 条已入库", flush=True)
            results.append({"id": eid, "name": name, "status": "ok", "count": count})
            completed.append(
                {
                    "glbl": eid,
                    "name": name,
                    "file": out.name,
                    "count": count,
                    "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                }
            )
        except Exception as ex:
            print(f"    ❌ {eid} {name}: {ex}", flush=True)
            traceback.print_exc()
            results.append({"id": eid, "name": name, "status": "error", "error": str(ex)})

    err = [x for x in results if x["status"] == "error"]
    ok = [x for x in results if x["status"] in ("ok", "skip")]
    print(f"\n=== DONE ok/skip={len(ok)} err={len(err)} ===", flush=True)

    manifest = {
        "dynasty": DYNASTY,
        "completed": completed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest → {manifest_path}", flush=True)

    summary = {"stamp": stamp, "dynasty": DYNASTY, "total": len(persons), "results": results}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"summary → {summary_path}", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
