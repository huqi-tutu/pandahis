#!/usr/bin/env python3
"""批量修复指定卷：帝王别名、Step4 坐标、审计块、progress。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANN = ORCH.parent / "historiography-annotate"
PIPE = ORCH.parent / "historiography-pipeline"
sys.path.insert(0, str(ANN))
sys.path.insert(0, str(PIPE))

from lib_config import paths  # noqa: E402
from emperor_resolve import (  # noqa: E402
    align_skeleton_emperors,
    build_alias_to_canonical,
    build_emperor_info_index,
    resolve_emperor_label,
    volume_junji_emperors,
    work_id_from_volume,
)
from coordinate_index import coords_from_emperor, migrate_entry_fields  # noqa: E402
from fill_fields import fill_entries, merge_all_entries, verify_step4, finalize_entries  # noqa: E402
from lib_config import build_dynasty_index, build_emperor_index, load_regime_index  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fix_taishi_excludes(data: dict, para_map: dict) -> int:
    n = 0
    for row in data.get("segment_attribution", []):
        pid = int(row.get("paragraph", 0))
        text = para_map.get(pid, "")
        if "太史公曰" in text and row.get("exclude_reason") == "其他":
            row["exclude_reason"] = "太史公曰"
            row["owners"] = []
            n += 1
    return n


def entry_paragraph_ids(entry: dict) -> list[int]:
    ids: list[int] = []
    for p in entry.get("paragraphs") or []:
        fr = int(p.get("paragraph_from") or 0)
        to = int(p.get("paragraph_to") or fr)
        if fr > 0:
            ids.extend(range(fr, to + 1))
    return ids


def nearest_junji_for_entry(entry: dict, data: dict, junji: set[str]) -> str | None:
    """共段无君纪时，向前后邻段找最近君纪。"""
    pids = entry_paragraph_ids(entry)
    if not pids:
        return None
    segs = {int(s["paragraph"]): s for s in data.get("segment_attribution", [])}
    lo, hi = min(pids), max(pids)
    total = int(data.get("total_paragraphs") or hi)
    for pid in range(lo, 0, -1):
        row = segs.get(pid) or {}
        for o in row.get("owners") or []:
            if o.get("category") == "君纪" and o.get("name") in junji:
                return o["name"]
    for pid in range(hi, total + 1):
        row = segs.get(pid) or {}
        for o in row.get("owners") or []:
            if o.get("category") == "君纪" and o.get("name") in junji:
                return o["name"]
    return None


def junji_from_entry_segments(entry: dict, data: dict, junji: set[str]) -> str | None:
    """从段落归属找与本 entry 共段的君纪主轴。"""
    name = (entry.get("史略名称") or "").strip()
    counts: dict[str, int] = {}
    for row in data.get("segment_attribution", []):
        owners = row.get("owners") or []
        names = {o.get("name") for o in owners}
        if name not in names:
            continue
        for o in owners:
            if o.get("category") == "君纪" and o.get("name") in junji:
                n = o["name"]
                counts[n] = counts.get(n, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def pick_volume_primary(junji: set[str]) -> str | None:
    """无共段君纪时的卷级主轴兜底。"""
    for preferred in (
        "吕太后", "汉高祖", "周武王", "周襄王", "周平王",
        "古公亶父", "黄帝", "尧", "夏禹", "成汤",
    ):
        if preferred in junji:
            return preferred
    return sorted(junji)[0] if junji else None


def align_all_emperor_coords(data: dict) -> list[str]:
    """所有条目的四级帝王坐标走别名表，非君纪落本卷君纪主轴。"""
    changes: list[str] = []
    work_id = work_id_from_volume(data.get("volume", ""))
    amap = build_alias_to_canonical()
    eidx = build_emperor_info_index()
    junji = volume_junji_emperors(data)
    fallback = pick_volume_primary(junji)

    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        coord = (entry.get("四级帝王坐标") or "").strip()
        cat = entry.get("史略分类", "")

        if coord:
            info, method = resolve_emperor_label(
                coord, work_id=work_id, alias_map=amap, emperor_index=eidx
            )
            if info and info["emperor"] != coord:
                for k, v in coords_from_emperor(info).items():
                    entry[k] = v
                changes.append(
                    f"{entry.get('史略ID')} 坐标 {coord}→{info['emperor']} ({method})"
                )
                coord = info["emperor"]

        needs_align = cat in ("事略", "典制", "论著", "民录", "士臣") and coord and coord not in junji
        if needs_align and junji:
            primary = (
                junji_from_entry_segments(entry, data, junji)
                or nearest_junji_for_entry(entry, data, junji)
                or fallback
            )
            if primary:
                info = eidx.get(primary)
                if info:
                    for k, v in coords_from_emperor(info).items():
                        entry[k] = v
                    changes.append(
                        f"{entry.get('史略ID')} 主轴外坐标 {coord}→{primary}"
                    )

    return changes


def fill_missing_regime_from_emperor(data: dict) -> int:
    """四级坐标已有但缺三级政权时，从帝王表补全。"""
    eidx = build_emperor_info_index()
    n = 0
    for entry in data.get("entries", []):
        migrate_entry_fields(entry)
        if (entry.get("三级政权坐标") or "").strip():
            continue
        coord = (entry.get("四级帝王坐标") or "").strip()
        if not coord:
            continue
        info = eidx.get(coord)
        if info:
            for k, v in coords_from_emperor(info).items():
                if k == "三级政权坐标" or not entry.get(k):
                    entry[k] = v
            n += 1
    return n


def repair_skeleton(sk_path: Path, para_map: dict) -> dict:
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    ts = fix_taishi_excludes(data, para_map)
    data, c1 = align_skeleton_emperors(data)
    c2 = align_all_emperor_coords(data)

    emperor_index = build_emperor_info_index()
    dynasty_index = build_dynasty_index()
    regime_index = load_regime_index()
    work_id = work_id_from_volume(data.get("volume", ""))

    entries = fill_entries(
        data.get("entries", []),
        emperor_index,
        dynasty_index,
        regime_index,
        work_id=work_id,
    )
    merge_all_entries(
        entries,
        data=data,
        emperor_index=emperor_index,
        dynasty_index=dynasty_index,
        regime_index=regime_index,
        work_id=work_id,
    )
    regime_n = fill_missing_regime_from_emperor(data)
    data["entries"] = entries

    # 删除临时字段（等同 finalize 前清理）
    for e in entries:
        e.pop("_auto_filled", None)
        e.pop("_needs_llm", None)

    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "taishi": ts,
        "align": len(c1) + len(c2),
        "regime": regime_n,
        "path": str(sk_path),
    }


def build_audit(work: str, vol: str, sk_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(PIPE / "build_audit_block.py"),
            "--work",
            work,
            "--vol",
            vol,
            "--skeleton",
            str(sk_path),
        ],
        check=True,
    )


def update_progress_step(work: str, vol: str, step: str, ok: bool, detail: str) -> None:
    prog_path = paths()["progress"] / f"{work}_progress.json"
    prog = json.loads(prog_path.read_text(encoding="utf-8"))
    vol = vol.zfill(3)
    rec = prog.setdefault("volumes", {}).setdefault(
        vol,
        {"steps": {}, "overall": "in_progress"},
    )
    rec.setdefault("steps", {})[step] = {
        "status": "done" if ok else "failed",
        "at": utc_now(),
        "detail": detail[:2000],
    }
    steps = rec["steps"]
    if all(steps.get(s, {}).get("status") == "done" for s in ("1", "2", "3", "4", "5")):
        rec["overall"] = "done"
    elif any(steps.get(s, {}).get("status") == "failed" for s in steps):
        rec["overall"] = "in_progress"
    else:
        rec["overall"] = "in_progress"
    rec["blocked_reason"] = None
    prog["updated_at"] = utc_now()
    prog_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_vol(work: str, vol: str, step: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env["HIST_REPAIR"] = "1"
    p = subprocess.run(
        [
            sys.executable,
            str(PIPE / "run_volume_pipeline.py"),
            "verify",
            "--work",
            work,
            "--vol",
            vol,
            "--step",
            step,
            "--force-order",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    out = (p.stdout or "") + (p.stderr or "")
    line = out.strip().split("\n")[-1] if out.strip() else ""
    return p.returncode == 0, out[-2500:]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="批量修复卷：坐标、审计块、verify")
    ap.add_argument("--vols", nargs="+", default=[f"{i:03d}" for i in range(1, 5)])
    ap.add_argument("--work", default="01史记")
    args = ap.parse_args()

    work = args.work
    vols = [v.zfill(3) for v in args.vols]
    root = paths()

    for vol in vols:
        print(f"\n{'='*50}\n卷 {vol}")
        sks = sorted(root["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
        if not sks:
            print("  ⚠️ 无 skeleton")
            continue
        sk = sks[0]
        idx = json.loads((root["paragraph_index"] / f"{work}_{vol}.json").read_text(encoding="utf-8"))
        para_map = {int(p["id"]): p["text"] for p in idx["paragraphs"]}

        info = repair_skeleton(sk, para_map)
        print(
            f"  skeleton: 太史公曰 {info['taishi']} | 帝王对齐 {info['align']} | "
            f"补三级政权 {info['regime']}"
        )

        build_audit(work, vol, sk)
        print("  审计块已生成")

        all_ok = True
        for step in ("1", "2", "3", "4", "5"):
            ok, msg = verify_vol(work, vol, step)
            sym = "✅" if ok else "❌"
            print(f"  {sym} verify step{step}")
            if not ok:
                all_ok = False
                print(msg[-800:])
            update_progress_step(
                work, vol, step, ok,
                msg.strip().split("\n")[-1] if ok else msg[-500:],
            )

        if all_ok:
            prog_path = paths()["progress"] / f"{work}_progress.json"
            prog = json.loads(prog_path.read_text(encoding="utf-8"))
            rec = prog["volumes"][vol]
            rec["overall"] = "done"
            rec["blocked_reason"] = None
            prog["updated_at"] = utc_now()
            prog_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n✅ 批量修复完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
