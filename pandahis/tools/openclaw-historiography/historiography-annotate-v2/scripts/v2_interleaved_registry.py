#!/usr/bin/env python3
"""混写卷（interleaved）登记：翻译质检时按人物拼接非连续段。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from paths_config import histograph_paths  # noqa: E402


def registry_path(work: str) -> Path:
    progress_dir = histograph_paths()["progress"]
    progress_dir.mkdir(parents=True, exist_ok=True)
    return progress_dir / f"{work}_混写卷.json"


def load_registry(work: str) -> dict:
    fp = registry_path(work)
    if not fp.is_file():
        return {"work": work, "updated_at": None, "volumes": {}}
    return json.loads(fp.read_text(encoding="utf-8"))


def save_registry(work: str, data: dict) -> Path:
    fp = registry_path(work)
    data = {**data, "work": work, "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fp


def noncontiguous_entry_names(skeleton: dict) -> List[str]:
    names: List[str] = []
    for ent in skeleton.get("entries") or []:
        if not isinstance(ent, dict):
            continue
        paras = ent.get("paragraphs") or []
        if len(paras) >= 2:
            name = (ent.get("史略名称") or "").strip()
            if name:
                names.append(name)
    return names


def detect_texture(
    *,
    protagonists: Optional[dict],
    skeleton: dict,
) -> tuple[str, str]:
    """返回 (texture, reason)。"""
    explicit = ""
    if isinstance(protagonists, dict):
        explicit = (protagonists.get("volume_texture") or "").strip()
    if not explicit:
        explicit = (skeleton.get("volume_texture") or "").strip()

    noncont = noncontiguous_entry_names(skeleton)
    if explicit == "interleaved":
        return "interleaved", "explicit"
    if explicit == "sequential":
        return "sequential", "explicit"
    if noncont:
        return "interleaved", "auto_noncontiguous"
    return "sequential", "auto_contiguous"


def register_volume(
    work: str,
    vol: str,
    *,
    skeleton: dict,
    protagonists: Optional[dict] = None,
    skeleton_file: str = "",
    force: bool = False,
) -> Optional[dict]:
    """若为混写卷则写入清单；sequential 且非 force 则不登记（可清除）。返回登记记录或 None。"""
    vol = vol.zfill(3)
    texture, reason = detect_texture(protagonists=protagonists, skeleton=skeleton)
    reg = load_registry(work)
    volumes = reg.setdefault("volumes", {})

    if texture != "interleaved" and not force:
        if vol in volumes and reason == "explicit":
            # 明确标成 sequential 时移出清单
            volumes.pop(vol, None)
            save_registry(work, reg)
        return None

    noncont = noncontiguous_entry_names(skeleton)
    note = (
        "混写卷：同一人物段落非连续。翻译/质检须按 entry.paragraphs 多段拼接，"
        "勿按卷内段号顺序假定语义连贯。"
    )
    rec: Dict[str, Any] = {
        "volume_name": skeleton.get("volume") or (protagonists or {}).get("volume_name") or "",
        "volume_texture": "interleaved",
        "reason": reason if texture == "interleaved" else "force",
        "noncontiguous_entries": noncont,
        "skeleton_file": skeleton_file
        or (histograph_paths()["annotations"] / f"{work}_{vol}_*_skeleton.json").name,
        "note": note,
        "registered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # 保留手写补充说明
    old = volumes.get(vol) or {}
    if old.get("manual_note"):
        rec["manual_note"] = old["manual_note"]
    volumes[vol] = rec
    save_registry(work, reg)
    return rec


def register_from_disk(work: str, vol: str, *, force: bool = False) -> Optional[dict]:
    vol = vol.zfill(3)
    ann = histograph_paths()["annotations"]
    skins = sorted(ann.glob(f"{work}_{vol}_*_skeleton.json"))
    if not skins:
        raise FileNotFoundError(f"未找到 skeleton: {work} {vol}")
    sk_path = skins[0]
    skeleton = json.loads(sk_path.read_text(encoding="utf-8"))
    pp = histograph_paths()["annotate_work"] / f"{work}_{vol}_protagonists.json"
    protagonists = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else None
    return register_volume(
        work,
        vol,
        skeleton=skeleton,
        protagonists=protagonists,
        skeleton_file=sk_path.name,
        force=force,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="混写卷清单登记/查询")
    ap.add_argument("--work", required=True)
    ap.add_argument("--vol", help="登记单卷；省略则列出清单")
    ap.add_argument("--force", action="store_true", help="强制登记为混写")
    ap.add_argument("--list", action="store_true", help="打印混写卷清单")
    args = ap.parse_args()

    work = args.work.strip()
    if args.vol:
        try:
            rec = register_from_disk(work, args.vol, force=args.force)
        except FileNotFoundError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        fp = registry_path(work)
        if rec:
            print(f"✅ 已登记混写卷 {args.vol.zfill(3)} → {fp}")
            print(json.dumps(rec, ensure_ascii=False, indent=2))
        else:
            print(f"ℹ️  {args.vol.zfill(3)} 非混写（未写入清单）· 清单: {fp}")
        return 0

    reg = load_registry(work)
    vols = reg.get("volumes") or {}
    print(f"混写卷清单 · {work} · {len(vols)} 卷 · {registry_path(work)}")
    for v in sorted(vols.keys()):
        r = vols[v]
        names = "、".join(r.get("noncontiguous_entries") or []) or "—"
        print(f"  {v} {r.get('volume_name')} · 非连续 entry: {names} · {r.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
