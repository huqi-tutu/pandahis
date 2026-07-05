#!/usr/bin/env python3
"""重置指定卷的 jobs / skeleton / progress / 审计块，供重跑标注。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ORCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ORCH_DIR))

from lib import db  # noqa: E402
from lib.config import paths  # noqa: E402

VOL_HEADER_RE = re.compile(r"^##\s*卷(?P<vol>\d{3})\s", re.MULTILINE)


def strip_audit_blocks(audit_text: str, vols: set[str]) -> str:
    matches = list(VOL_HEADER_RE.finditer(audit_text))
    if not matches:
        return audit_text
    keep: list[str] = []
    if matches[0].start() > 0:
        keep.append(audit_text[: matches[0].start()])
    for i, m in enumerate(matches):
        if m.group("vol") in vols:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(audit_text)
        keep.append(audit_text[m.start() : end])
    return "".join(keep).rstrip() + "\n"


def reset_progress_volume(prog: dict, vol: str) -> None:
    vol = vol.zfill(3)
    rec = prog.setdefault("volumes", {}).setdefault(
        vol,
        {
            "skeleton_file": None,
            "volume_name": None,
            "steps": {},
            "overall": "not_started",
            "blocked_reason": None,
        },
    )
    rec["skeleton_file"] = None
    rec["overall"] = "not_started"
    rec["blocked_reason"] = None
    for s in ("1", "2", "3", "4", "5"):
        rec.setdefault("steps", {})[s] = {
            "status": "pending",
            "at": None,
            "detail": None,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--vol", action="append", required=True)
    ap.add_argument(
        "--purge-intermediates",
        action="store_true",
        help="同时删除 annotate_work 下 protagonists.json / blocks.json",
    )
    args = ap.parse_args()
    work = args.work
    vols = {v.zfill(3) for v in args.vol}

    ann = paths()["annotations"]
    aw = paths()["annotate_work"]
    deleted = 0
    for vol in sorted(vols):
        for sk in ann.glob(f"{work}_{vol}_*_skeleton.json"):
            sk.unlink()
            deleted += 1
            print(f"  删除 skeleton: {sk.name}")
        if args.purge_intermediates:
            for name in (
                f"{work}_{vol}_protagonists.json",
                f"{work}_{vol}_blocks.json",
            ):
                fp = aw / name
                if fp.exists():
                    fp.unlink()
                    print(f"  删除中间产物: {name}")

    prog_path = paths()["progress"] / f"{work}_progress.json"
    if prog_path.exists():
        prog = json.loads(prog_path.read_text(encoding="utf-8"))
        for vol in vols:
            reset_progress_volume(prog, vol)
        prog["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prog_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  重置 progress: 卷 {', '.join(sorted(vols))}")

    audit_path = paths()["audit"] / f"{work}_标注审计.md"
    if audit_path.exists():
        text = audit_path.read_text(encoding="utf-8")
        new_text = strip_audit_blocks(text, vols)
        audit_path.write_text(new_text, encoding="utf-8")
        print(f"  清理审计 MD 中卷 {', '.join(sorted(vols))} 区块")

    db.init_schema()
    for vol in sorted(vols):
        n = db.reset_volume_steps(work, vol, through_step="5")
        print(f"  重置 jobs 卷{vol}: {n} 条 → pending")

    db.set_work_status(work, "running", blocked_reason=None, current_vol=None, current_step=None)
    print(f"✅ {work} 卷 {', '.join(sorted(vols))} 已重置（删除 skeleton {deleted} 个）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
