#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条运行 V2 compose-detail（仅不满足顺译条件的条目；不含西汉）。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = DATA / "05工作流中间产物"
QUEUE = WORK / "v2_compose_queue.json"
CHECKPOINT = WORK / "v2_compose_checkpoint.json"
DETAILS_DIR = DATA / "06朝代知识补全" / "详情"
DK_SCRIPTS = (
    ROOT
    / "tools"
    / "openclaw-historiography"
    / "historiography-dynasty-knowledge"
    / "scripts"
)

sys.path.insert(0, str(ROOT / "scripts"))
from v2_detail_routing import has_06  # noqa: E402


def load_checkpoint() -> dict:
    if CHECKPOINT.is_file():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {"done": [], "failed": [], "paused": False}


def save_checkpoint(state: dict) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_compose(dynasty: str, eid: str, log: Path) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        str(DK_SCRIPTS / "dynasty_supplement.py"),
        "--dynasty",
        dynasty,
        "--step",
        "compose-detail",
        "--entry-id",
        eid,
    ]
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n===== {datetime.now(timezone.utc).isoformat()} compose {dynasty} {eid} =====\n")
        fh.flush()
        proc = subprocess.run(cmd, cwd=str(DK_SCRIPTS), stdout=fh, stderr=subprocess.STDOUT)
    if proc.returncode == 0 and has_06(eid):
        return True, "ok"
    return False, f"exit={proc.returncode}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-queue", action="store_true", help="调用 build_v2_detail_queues.py")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.rebuild_queue:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_v2_detail_queues.py")], check=True)

    if not QUEUE.is_file():
        print("缺少 compose 队列，请先: python3 scripts/build_v2_detail_queues.py", file=sys.stderr)
        return 1

    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    state = load_checkpoint()
    if state.get("paused"):
        print("compose 队列处于暂停状态；如需继续请先清除 checkpoint 中 paused 或重建队列")
        return 1

    done = set(state.get("done") or [])
    failed_map = {x["史略ID"]: x for x in state.get("failed") or []}
    pending = [r for r in queue if r["史略ID"] not in done and not has_06(r["史略ID"])]
    if args.limit:
        pending = pending[: args.limit]

    if not pending:
        print(f"无待 compose 条目（队列 {len(queue)}，已完成 {len(done)}）")
        return 0

    log = WORK / "朝代知识补全" / "v2_compose_queue.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        for i, row in enumerate(pending[:10], 1):
            print(f"  [{i}] {row['史略ID']} {row['史略名称']} ({row['二级朝代坐标']})")
        return 0

    ok_n = 0
    for i, row in enumerate(pending, 1):
        eid = row["史略ID"]
        dynasty = row["二级朝代坐标"]
        name = row.get("史略名称") or ""
        print(f"[{i}/{len(pending)}] compose-detail {eid} {name} ({dynasty})")
        ok, msg = run_compose(dynasty, eid, log)
        if ok:
            done.add(eid)
            failed_map.pop(eid, None)
            ok_n += 1
            print(f"  ✅ {eid}")
        else:
            failed_map[eid] = {"史略ID": eid, "史略名称": name, "error": msg}
            print(f"  ❌ {eid} — {msg}")
        state["done"] = sorted(done)
        state["failed"] = list(failed_map.values())
        save_checkpoint(state)

    print(f"compose 完成 {ok_n}/{len(pending)} | checkpoint → {CHECKPOINT}")
    return 0 if ok_n == len(pending) else 1


if __name__ == "__main__":
    raise SystemExit(main())
