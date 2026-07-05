#!/usr/bin/env python3
"""批量清空汉书无 _年LLM依据 的占位年，重置 Step4 待 LLM 重考订。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANN = ORCH.parent / "historiography-annotate"
sys.path.insert(0, str(ANN))
sys.path.insert(0, str(ORCH))

from hanshu_step4_hardening import clear_entries_without_year_basis  # noqa: E402

from lib import db, gates  # noqa: E402

WORK = "02汉书"
SKEL_DIR = ORCH.parents[2] / "data" / "03索引标注条目"


def list_hanshu_vols() -> list[str]:
    vols: list[str] = []
    for sk in sorted(SKEL_DIR.glob(f"{WORK}_*_skeleton.json")):
        m = re.match(rf"{re.escape(WORK)}_(\d{{3}})_", sk.name)
        if m:
            vols.append(m.group(1))
    return vols


def repair_vol(vol: str, *, dry_run: bool = False) -> tuple[int, list[str]]:
    vol = vol.zfill(3)
    matches = sorted(SKEL_DIR.glob(f"{WORK}_{vol}_*_skeleton.json"))
    if not matches:
        return 0, [f"卷{vol} 无 skeleton"]
    sk = matches[0]
    data = json.loads(sk.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    n, logs = clear_entries_without_year_basis(entries, force_all_without_basis=True)
    if not n:
        return 0, [f"卷{vol} 无需清空"]
    if dry_run:
        return n, logs
    data["entries"] = entries
    prov = data.get("knowledge_provenance") or {}
    prov.pop("step4", None)
    data["knowledge_provenance"] = prov
    sk.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    db.init_schema()
    db.mark_volume_steps_done(WORK, vol, "3")
    db.reset_volume_step(WORK, vol, "4")
    gates.step4_restore_scratch(sk)
    return n, logs


def main() -> int:
    ap = argparse.ArgumentParser(description="汉书缺考订依据年份清空 + Step4 重置")
    ap.add_argument("vols", nargs="*", help="卷号；缺省处理全部已有 skeleton")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    vols = [v.zfill(3) for v in args.vols] if args.vols else list_hanshu_vols()
    total = 0
    touched = 0
    for vol in vols:
        n, logs = repair_vol(vol, dry_run=args.dry_run)
        if n:
            touched += 1
            total += n
            print(f"\n=== 卷{vol} cleared={n} ===")
            for ln in logs[:12]:
                print(f"  {ln}")
            if len(logs) > 12:
                print(f"  …共 {len(logs)} 条")
    print(
        f"\n合计：{touched} 卷 / 清空 {total} 条"
        f"{'（dry-run）' if args.dry_run else ''}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
