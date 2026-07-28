#!/usr/bin/env python3
"""回溯补全指定朝代人物关系表中的「好友」类别（保留其他类别，verify 后入库）。"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import relations_lib as rl  # noqa: E402

DEFAULT_DYNASTIES = ("五帝", "夏", "商", "西周")


def _default_mysql() -> dict:
    return {
        "host": "49.235.165.220",
        "port": 3306,
        "user": "histomap_admin",
        "password": "pandahis#666",
        "db": "histomap",
    }


def _load_manifest_entries(dynasty: str, paths: dict) -> list[dict]:
    manifest_path = paths["person_relations"] / f"{dynasty}_关系补全_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(doc.get("completed") or [])


def _update_manifest_entry(manifest_path: Path, eid: str, count: int) -> None:
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in doc.get("completed") or []:
        if row.get("glbl") == eid:
            row["count"] = count
            row["verified_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            break
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="回溯补全「好友」关系并入库")
    parser.add_argument(
        "--dynasty",
        action="append",
        dest="dynasties",
        help=f"朝代，可重复指定（默认: {', '.join(DEFAULT_DYNASTIES)}）",
    )
    parser.add_argument("--skip-if-present", action="store_true", help="已有好友类别则跳过")
    parser.add_argument("--no-sync", action="store_true", help="只写 JSON，不入库")
    args = parser.parse_args()

    dynasties = args.dynasties or list(DEFAULT_DYNASTIES)
    rl.validate_histograph_root()
    rl.ensure_deepseek_v4_pro()
    paths = rl.histograph_paths()
    mysql = None if args.no_sync else _default_mysql()

    mid = paths["person_relations_work"]
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = mid / f"好友回溯_{stamp}.log"
    summary_path = mid / f"好友回溯_summary_{stamp}.json"

    results: list[dict] = []
    total = 0

    for dynasty in dynasties:
        entries = _load_manifest_entries(dynasty, paths)
        manifest_path = paths["person_relations"] / f"{dynasty}_关系补全_manifest.json"
        print(f"\n=== {dynasty} · {len(entries)} 人 ===", flush=True)
        for i, row in enumerate(entries, 1):
            total += 1
            eid = str(row.get("glbl", "")).strip()
            name = str(row.get("name", "")).strip()
            out = paths["person_relations"] / str(row.get("file", "")).strip()
            prefix = f"[{dynasty} {i}/{len(entries)}] {eid} {name}"
            try:
                if not out.is_file():
                    raise FileNotFoundError(out)
                before = json.loads(out.read_text(encoding="utf-8"))
                fri_before = sum(1 for r in before if r.get("关系类别") == "好友")
                if args.skip_if_present and fri_before:
                    print(f"{prefix} ⏭ 已有好友 {fri_before} 条", flush=True)
                    results.append(
                        {"dynasty": dynasty, "id": eid, "name": name, "status": "skip", "fri": fri_before}
                    )
                    continue

                print(f"{prefix} →", flush=True)
                rl.backfill_category_one(
                    category="好友",
                    entry_id=eid,
                    revise_on_fail=True,
                    sync_db=not args.no_sync,
                    mysql=mysql,
                    skip_if_present=args.skip_if_present,
                )
                after = json.loads(out.read_text(encoding="utf-8"))
                fri_after = sum(1 for r in after if r.get("关系类别") == "好友")
                _update_manifest_entry(manifest_path, eid, len(after))
                print(f"    ✅ 好友 {fri_before}→{fri_after}，合计 {len(after)} 条", flush=True)
                results.append(
                    {
                        "dynasty": dynasty,
                        "id": eid,
                        "name": name,
                        "status": "ok",
                        "fri_before": fri_before,
                        "fri_after": fri_after,
                        "count": len(after),
                    }
                )
            except Exception as ex:
                print(f"    ❌ {ex}", flush=True)
                traceback.print_exc()
                results.append(
                    {"dynasty": dynasty, "id": eid, "name": name, "status": "error", "error": str(ex)}
                )

    ok = [x for x in results if x["status"] in ("ok", "skip")]
    err = [x for x in results if x["status"] == "error"]
    added_fri = sum(x.get("fri_after", 0) - x.get("fri_before", 0) for x in results if x["status"] == "ok")
    summary = {
        "stamp": stamp,
        "dynasties": dynasties,
        "total": total,
        "ok": len(ok),
        "err": len(err),
        "friend_records_added": added_fri,
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n=== DONE total={total} ok={len(ok)} err={len(err)} 新增好友={added_fri} ===", flush=True)
    print(f"summary → {summary_path}", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
