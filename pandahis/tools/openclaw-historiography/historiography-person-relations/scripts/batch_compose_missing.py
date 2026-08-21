#!/usr/bin/env python3
"""串行补全指定人物或某朝代尚无有效关系表的人物。"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
OPENCLAW = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(OPENCLAW))

import relations_lib as rl  # noqa: E402


def _mysql(args: argparse.Namespace) -> dict | None:
    if not args.mysql_host:
        return None
    return {
        "host": args.mysql_host,
        "port": args.mysql_port,
        "user": args.mysql_user,
        "password": args.mysql_password or "",
        "db": args.mysql_db,
    }


def _needs_compose(paths: dict, name: str) -> bool:
    fp = paths["person_relations"] / f"{name}关系表.json"
    if not fp.is_file():
        return True
    try:
        rows = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    # 已有合法 JSON 数组即视为完成（含空表 []：史料确无可挂关系）
    return not isinstance(rows, list)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dynasty", default=None, help="补全该朝缺失关系表的人物")
    ap.add_argument("--id", action="append", default=[], help="指定 GLBL（可多次）")
    ap.add_argument("--name", action="append", default=[], help="指定史略名称（可多次）")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    ap.add_argument("--no-skip-existing", action="store_true")
    ap.add_argument("--mysql-host", default="49.235.165.220")
    ap.add_argument("--mysql-port", type=int, default=3306)
    ap.add_argument("--mysql-user", default="histomap_admin")
    ap.add_argument("--mysql-password", default="pandahis#666")
    ap.add_argument("--mysql-db", default="histomap")
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()
    skip = args.skip_existing and not args.no_skip_existing

    rl.validate_histograph_root()
    paths = rl.histograph_paths()
    mysql = _mysql(args) if args.sync else None

    jobs: list[tuple[str | None, str | None]] = []
    for eid in args.id:
        jobs.append((eid, None))
    for name in args.name:
        jobs.append((None, name))
    if args.dynasty:
        for e in rl.list_dynasty_persons(args.dynasty):
            jobs.append((str(e.get("史略ID") or "").strip(), None))

    if not jobs:
        print("无任务：请提供 --dynasty / --id / --name", file=sys.stderr)
        return 2

    report: dict = {
        "started": datetime.now(timezone.utc).isoformat(),
        "ok": [],
        "skip": [],
        "fail": [],
    }
    report_path = args.report or (
        paths["root"]
        / "data/05工作流中间产物/人物关系补全"
        / f"batch_compose_{args.dynasty or 'custom'}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    for i, (eid, name) in enumerate(jobs, 1):
        try:
            entry = rl.find_entry(entry_id=eid, name=name)
        except Exception as exc:
            report["fail"].append({"id": eid, "name": name, "error": str(exc)})
            print(f"[{i}/{len(jobs)}] resolve FAIL {eid or name}: {exc}")
            continue
        subject = str(entry.get("史略名称") or "").strip()
        geid = str(entry.get("史略ID") or "").strip()
        if skip and not _needs_compose(paths, subject):
            report["skip"].append({"id": geid, "name": subject})
            print(f"[{i}/{len(jobs)}] skip existing {geid} {subject}")
            continue
        print(f"\n[{i}/{len(jobs)}] compose {geid} {subject} …")
        t0 = time.time()
        try:
            fp = rl.compose_one(
                entry_id=geid,
                sync_db=args.sync,
                mysql=mysql,
            )
            report["ok"].append(
                {
                    "id": geid,
                    "name": subject,
                    "file": str(fp) if fp else None,
                    "sec": round(time.time() - t0, 1),
                }
            )
            print(f"OK {geid} {subject} ({time.time()-t0:.0f}s)")
        except Exception as exc:
            report["fail"].append(
                {
                    "id": geid,
                    "name": subject,
                    "error": str(exc)[:800],
                    "sec": round(time.time() - t0, 1),
                }
            )
            print(f"FAIL {geid} {subject}: {exc}")
            traceback.print_exc()
        report["updated"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # refresh manifests for involved dynasties
    dynasties = set()
    if args.dynasty:
        dynasties.add(args.dynasty)
    for item in report["ok"]:
        try:
            e = rl.find_entry(entry_id=item["id"])
            dynasties.add(str(e.get("二级朝代坐标") or "").strip())
        except Exception:
            pass
    for d in sorted(x for x in dynasties if x):
        mf = rl.write_dynasty_manifest(d)
        print(f"manifest {mf}")

    print(
        f"\nDONE ok={len(report['ok'])} skip={len(report['skip'])} "
        f"fail={len(report['fail'])} report={report_path}"
    )
    return 0 if not report["fail"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
