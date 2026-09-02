#!/usr/bin/env python3
"""按人工口径收束《三国志》若干卷条目范围。

004 魏陈留王自 P65 起，P61–P64 归高贵乡公
007 张邈不取，P2–P13 归吕布（P14 陈登附传不取）
009 P5 韩浩/史涣不取；补夏侯尚 P31–P37
016 P12–P29 归杜恕（P28 不归杜畿）
019 萧怀王熊段太短不取（原误标曹彪）
020 只取曹昂、曹冲、曹彪
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

_ROOT = Path(__file__).resolve().parents[2]
_ANNOTATE = _ROOT / "historiography-annotate"
_V2 = Path(__file__).resolve().parent
for p in (_ROOT, _ANNOTATE, _V2):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ["HIST_ANNOTATE_TRACK"] = "v2"

from paths_config import histograph_paths  # noqa: E402
from v2_aggregate_blocks import write_blocks_from_primary  # noqa: E402
from v2_expand_to_skeleton import expand_to_skeleton  # noqa: E402

WORK = "04三国志"


def _dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _row_map(primary: dict) -> Dict[int, dict]:
    return {int(r["paragraph"]): r for r in primary.get("paragraphs") or []}


def set_block(primary: dict, pids: Iterable[int], name: str) -> None:
    rows = _row_map(primary)
    for pid in pids:
        row = rows[pid]
        row["primary_subject"] = name
        row["disposition"] = "block"
        row.pop("exclude_reason", None)


def set_exclude(primary: dict, pids: Iterable[int], reason: str) -> None:
    rows = _row_map(primary)
    for pid in pids:
        row = rows[pid]
        row["primary_subject"] = reason
        row["disposition"] = "exclude"
        row["exclude_reason"] = reason


def drop_protagonists(manifest: dict, names: Iterable[str]) -> None:
    drop = {n.strip() for n in names}
    manifest["protagonists"] = [
        p for p in (manifest.get("protagonists") or []) if (p.get("name") or "").strip() not in drop
    ]


def upsert_protagonist(
    manifest: dict,
    *,
    name: str,
    category: str,
    rationale: str,
    after: str | None = None,
) -> None:
    existing = [p for p in (manifest.get("protagonists") or []) if (p.get("name") or "").strip() == name]
    payload = {"name": name, "category": category, "rationale": rationale}
    if existing:
        existing[0].update(payload)
        return
    items: List[dict] = list(manifest.get("protagonists") or [])
    if after:
        for i, p in enumerate(items):
            if (p.get("name") or "").strip() == after:
                items.insert(i + 1, payload)
                manifest["protagonists"] = items
                return
    items.append(payload)
    manifest["protagonists"] = items


def _paths(vol: str) -> tuple[Path, Path]:
    paths = histograph_paths()
    work_dir = paths["annotate_work"]
    return work_dir / f"{WORK}_{vol}_primary_subjects.json", work_dir / f"{WORK}_{vol}_protagonists.json"


def repair_004() -> None:
    vol = "004"
    pf, mf = _paths(vol)
    primary = _load(pf)
    set_block(primary, range(61, 65), "魏高贵乡公")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    # protagonists 不变


def repair_007() -> None:
    vol = "007"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    drop_protagonists(manifest, ["张邈"])
    set_block(primary, range(2, 14), "吕布")
    set_exclude(primary, [14], "世系链")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)


def repair_009() -> None:
    vol = "009"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    upsert_protagonist(
        manifest,
        name="夏侯尚",
        category="武将",
        rationale="渊从子，文帝亲友，都督南方；本卷独立开传，原误挂夏侯渊。",
        after="夏侯渊",
    )
    set_block(primary, range(2, 5), "夏侯惇")
    set_exclude(primary, [5], "世系链")
    set_block(primary, range(6, 11), "夏侯渊")
    set_block(primary, range(31, 38), "夏侯尚")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)


def repair_016() -> None:
    vol = "016"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    upsert_protagonist(
        manifest,
        name="杜恕",
        category="文臣",
        rationale="畿子，字务伯，本卷自「恕字务伯」起独立长传（含奏议），P28 封恕子预亦属恕传收束。",
        after="杜畿",
    )
    set_block(primary, range(7, 12), "杜畿")
    set_block(primary, range(12, 30), "杜恕")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)


def repair_019() -> None:
    vol = "019"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    drop_protagonists(manifest, ["曹彪"])
    set_exclude(primary, [32], "世系链")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)


def repair_020() -> None:
    vol = "020"
    pf, mf = _paths(vol)
    primary = _load(pf)
    manifest = _load(mf)
    manifest["protagonists"] = [
        {
            "name": "曹昂",
            "category": "宗戚",
            "rationale": "丰愍王昂，随太祖南征为张绣所害，本卷武帝诸子中独立成传。",
        },
        {
            "name": "曹冲",
            "category": "宗戚",
            "rationale": "邓哀王冲，称象等独立长叙事；任城/陈思另卷，本卷武帝诸子中事迹最著。",
        },
        {
            "name": "曹彪",
            "category": "宗戚",
            "rationale": "楚王彪，封徙与嘉平谋泄长叙事。",
        },
    ]
    set_block(primary, [3], "曹昂")
    set_block(primary, [5], "曹冲")
    set_exclude(primary, [9, 10, 14, 24], "世系链")
    set_block(primary, [16], "曹彪")
    primary["method"] = "manual_repair"
    _dump(pf, primary)
    _dump(mf, manifest)


def rebuild(vol: str) -> None:
    write_blocks_from_primary(WORK, vol)
    out = expand_to_skeleton(WORK, vol)
    print(f"  skeleton → {out}")


def main() -> int:
    repairs = {
        "004": repair_004,
        "007": repair_007,
        "009": repair_009,
        "016": repair_016,
        "019": repair_019,
        "020": repair_020,
    }
    vols = sys.argv[1:] or list(repairs)
    for vol in vols:
        vol = vol.zfill(3)
        if vol not in repairs:
            print(f"跳过未知卷 {vol}", file=sys.stderr)
            continue
        print(f"== {WORK} {vol}")
        repairs[vol]()
        rebuild(vol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
