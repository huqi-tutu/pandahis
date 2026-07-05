#!/usr/bin/env python3
"""对齐《汉书》jobs / progress 与 skeleton 真实质检状态，并重置 Step4 续跑队列。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ORCH))

from lib import db, gates  # noqa: E402
from lib.config import paths  # noqa: E402
from lib.paragraph_index import list_volume_files  # noqa: E402
from lib.work_runner import _skip_volume_reason  # noqa: E402

WORK = "02汉书"
STEPS = ("1", "2", "3", "4")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _entries_complete(sk_path: Path) -> bool:
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    if not entries:
        return True
    formal = (
        "优先级",
        "优先级判定理由",
        "史略开始年",
        "史略结束年",
        "四级帝王坐标",
    )
    for e in entries:
        if e.get("_needs_llm"):
            return False
        for f in formal:
            v = e.get(f)
            if v is None or (isinstance(v, str) and not v.strip()):
                return False
    prov = (data.get("knowledge_provenance") or {}).get("step4")
    return bool(prov)


def _prepare_step4_retry(sk_path: Path) -> None:
    gates.step4_restore_scratch(sk_path)
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    prov = data.get("knowledge_provenance") or {}
    if prov.pop("step4", None) is not None:
        data["knowledge_provenance"] = prov
        sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify_volume(work: str, vol: str) -> str:
    skip = _skip_volume_reason(work, vol)
    if skip:
        return "skip"
    sk = gates.skeleton_path(work, vol)
    if sk is None or not sk.exists():
        return "no_skeleton"
    ok2, _ = gates.verify_step(work, vol, "2")
    if not ok2:
        return "redo_step1"
    ok3, _ = gates.verify_step(work, vol, "3")
    if not ok3:
        return "redo_step3"
    ok4, _ = gates.verify_step4_final(sk)
    if ok4 and _entries_complete(sk):
        return "complete"
    return "redo_step4"


def apply_reconcile(work: str, vol: str, kind: str, *, dry_run: bool) -> str:
    vol = vol.zfill(3)
    if kind == "skip":
        if not dry_run:
            db.skip_volume_jobs(work, vol, _skip_volume_reason(work, vol) or "skip", force=True)
        return "skip"

    if kind == "no_skeleton":
        if not dry_run:
            db.reset_volume_steps(work, vol, through_step="4")
        return "reset_all_pending"

    sk = gates.skeleton_path(work, vol)
    assert sk is not None

    if kind == "complete":
        if not dry_run:
            db.mark_volume_steps_done(work, vol, "4")
        return "mark_all_done"

    if kind == "redo_step4":
        if not dry_run:
            db.mark_volume_steps_done(work, vol, "3")
            db.reset_volume_step(work, vol, "4")
            _prepare_step4_retry(sk)
        return "step4_pending"

    if kind == "redo_step3":
        if not dry_run:
            db.mark_volume_steps_done(work, vol, "2")
            db.reset_volume_steps(work, vol, through_step="3")
            db.reset_volume_step(work, vol, "4")
        return "redo_from_step3"

    # redo_step1
    if not dry_run:
        db.reset_volume_steps(work, vol, through_step="3")
        db.reset_volume_step(work, vol, "4")
        _prepare_step4_retry(sk)
    return "redo_from_step1"


def sync_progress(work: str, vols: list[str]) -> None:
    prog_path = paths()["progress"] / f"{work}_progress.json"
    if prog_path.exists():
        prog = json.loads(prog_path.read_text(encoding="utf-8"))
    else:
        prog = {"work": work, "volumes": {}}

    ann = paths()["annotations"]
    for vol in vols:
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
        sk_matches = sorted(ann.glob(f"{work}_{vol}_*_skeleton.json"))
        if sk_matches:
            rec["skeleton_file"] = sk_matches[0].name
            try:
                rec["volume_name"] = json.loads(sk_matches[0].read_text()).get("volume")
            except (json.JSONDecodeError, OSError):
                pass
        for step in STEPS:
            j = db.get_job(work, vol, step)
            st = j["status"] if j else "pending"
            rec.setdefault("steps", {})[step] = {
                "status": st,
                "at": j.get("finished_at") if j else None,
                "detail": (j.get("detail") or "")[:500] if j else None,
            }
        steps = rec.get("steps", {})
        if all(steps.get(s, {}).get("status") == "done" for s in STEPS):
            rec["overall"] = "done"
        elif any(steps.get(s, {}).get("status") == "failed" for s in STEPS):
            rec["overall"] = "failed"
        elif steps.get("1", {}).get("status") == "done":
            rec["overall"] = "in_progress"
        else:
            rec["overall"] = "not_started"
        rec["blocked_reason"] = None

    prog["updated_at"] = utc_now()
    prog_path.parent.mkdir(parents=True, exist_ok=True)
    prog_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="汉书 pipeline 对齐 + Step4 队列重置")
    ap.add_argument("--work", default=WORK)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-sync-progress", action="store_true")
    args = ap.parse_args()
    work = args.work

    db.init_schema()
    vols = [v for v, _ in list_volume_files(work)]
    counts: dict[str, int] = {}

    print(f"{'[dry-run] ' if args.dry_run else ''}对齐 {work} 共 {len(vols)} 卷…")
    for vol in sorted(vols, key=lambda x: int(x)):
        kind = classify_volume(work, vol)
        action = apply_reconcile(work, vol, kind, dry_run=args.dry_run)
        counts[kind] = counts.get(kind, 0) + 1
        if kind not in ("skip",) or args.dry_run:
            print(f"  {vol}  {kind:14s} → {action}")

    print("\n汇总:")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")

    if not args.dry_run:
        if not args.no_sync_progress:
            sync_progress(work, vols)
            print(f"\n✅ progress 已同步 → {paths()['progress'] / f'{work}_progress.json'}")
        db.set_work_status(work, "running", blocked_reason=None)
        print(f"✅ {work} 状态 → running，可 hist run-work --work {work} --one-volume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
