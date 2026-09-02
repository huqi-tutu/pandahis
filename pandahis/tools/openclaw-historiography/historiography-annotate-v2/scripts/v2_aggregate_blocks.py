#!/usr/bin/env python3
"""Step1b-β：primary_subjects.json + protagonists.json → blocks.json（机械合并）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_ANNOTATE = _ROOT / "historiography-annotate"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ANNOTATE) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE))

from paths_config import histograph_paths  # noqa: E402

VALID_EXCLUDE_REASONS = frozenset(
    {"卷首标题", "太史公曰", "论赞", "赞曰", "评曰", "共段总述", "世系链", "其他"}
)


def _annotate_work() -> Path:
    p = histograph_paths()["annotate_work"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def primary_subjects_path(work: str, vol: str) -> Path:
    return _annotate_work() / f"{work}_{vol.zfill(3)}_primary_subjects.json"


def blocks_path(work: str, vol: str) -> Path:
    return _annotate_work() / f"{work}_{vol.zfill(3)}_blocks.json"


def protagonists_path(work: str, vol: str) -> Path:
    return _annotate_work() / f"{work}_{vol.zfill(3)}_protagonists.json"


def _paragraph_index_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    paths = histograph_paths()
    fp = paths["paragraph_index"] / f"{work}_{vol}.json"
    if fp.is_file():
        return fp
    raise FileNotFoundError(f"段落索引不存在: {work} vol {vol}")


def _para_text_map(index: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for item in index.get("paragraphs") or []:
        if not isinstance(item, dict):
            continue
        pid = int(item.get("paragraph") or item.get("id") or 0)
        text = (item.get("text") or "").strip()
        if pid > 0:
            out[pid] = text
    return out


def _open_phrase(text: str, min_len: int = 6) -> str:
    t = (text or "").strip()
    if len(t) >= min_len:
        return t[: min(40, len(t))]
    return t + ("。" * max(0, min_len - len(t)))


def _protagonist_map(manifest: dict) -> Tuple[Dict[str, str], List[str]]:
    names: List[str] = []
    cats: Dict[str, str] = {}
    for item in manifest.get("protagonists") or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        cats[name] = (item.get("category") or "君王").strip()
    return cats, names


def _classify_row(
    row: dict,
    prot_names: frozenset[str],
) -> Tuple[str, str]:
    """返回 (kind, key)：kind=block|exclude；key=人名或 exclude_reason。"""
    subj = (row.get("primary_subject") or "").strip()
    disp = (row.get("disposition") or "block").strip()
    ex = (row.get("exclude_reason") or "").strip()

    if disp == "exclude" or subj in VALID_EXCLUDE_REASONS or subj == "世系链":
        reason = ex or (subj if subj in VALID_EXCLUDE_REASONS else "世系链")
        if reason not in VALID_EXCLUDE_REASONS:
            reason = "世系链"
        return "exclude", reason

    if subj in prot_names:
        return "block", subj

    # 非 Top 主轴 → 世系链
    return "exclude", "世系链"


def aggregate_blocks(
    primary: dict,
    manifest: dict,
    index: dict,
    *,
    work: str,
    vol: str,
) -> dict:
    total = int(index.get("total") or primary.get("total_paragraphs") or 0)
    para_text = _para_text_map(index)
    cat_map, prot_list = _protagonist_map(manifest)
    prot_names = frozenset(prot_list)

    rows = sorted(
        (r for r in (primary.get("paragraphs") or []) if isinstance(r, dict)),
        key=lambda r: int(r.get("paragraph") or 0),
    )
    if len(rows) != total:
        raise ValueError(f"primary_subjects 段数 {len(rows)} ≠ 索引 {total}")

    classified: List[Tuple[int, str, str]] = []
    for row in rows:
        pid = int(row["paragraph"])
        kind, key = _classify_row(row, prot_names)
        text = (para_text.get(pid) or "").strip()
        if text.startswith("评曰"):
            kind, key = "exclude", "评曰"
        classified.append((pid, kind, key))

    excludes: List[dict] = []
    blocks: List[dict] = []

    def flush_run(start: int, end: int, kind: str, key: str) -> None:
        if start <= 0 or end < start:
            return
        if kind == "exclude":
            excludes.append(
                {
                    "paragraph_from": start,
                    "paragraph_to": end,
                    "exclude_reason": key,
                }
            )
        else:
            pf, pt = start, end
            blocks.append(
                {
                    "name": key,
                    "category": cat_map.get(key, "君王"),
                    "paragraph_from": pf,
                    "paragraph_to": pt,
                    "boundary_evidence": {
                        "open_paragraph": pf,
                        "open_phrase": _open_phrase(para_text.get(pf, "")),
                        "close_paragraph": pt,
                        "close_note": f"Step1b-β 自 primary_subjects 合并 P{pf}–P{pt}",
                    },
                }
            )

    if not classified:
        raise ValueError("primary_subjects 为空")

    run_start = classified[0][0]
    run_kind, run_key = classified[0][1], classified[0][2]
    prev_p = run_start

    for pid, kind, key in classified[1:]:
        if kind == run_kind and key == run_key and pid == prev_p + 1:
            prev_p = pid
            continue
        flush_run(run_start, prev_p, run_kind, run_key)
        run_start = pid
        prev_p = pid
        run_kind, run_key = kind, key
    flush_run(run_start, prev_p, run_kind, run_key)

    subtype = (manifest.get("volume_subtype") or manifest.get("narrative_mode") or "").strip()

    # 世系交接双挂：primary_subjects.co_owner + primary_subject 均为 Top 主轴
    multi_owner_segments: List[dict] = []
    for row in rows:
        pid = int(row.get("paragraph") or 0)
        primary = (row.get("primary_subject") or "").strip()
        co = (row.get("co_owner") or "").strip()
        if not co or primary not in prot_names or co not in prot_names:
            continue
        if primary == co:
            continue
        # 顺序：前君（co_owner）→ 后君（primary_subject）；若标注反了仍按字母稳定
        owners = [
            {"name": co, "category": cat_map.get(co, "君王")},
            {"name": primary, "category": cat_map.get(primary, "君王")},
        ]
        multi_owner_segments.append({"paragraph": pid, "owners": owners})

    return {
        "work": work,
        "vol": vol.zfill(3),
        "total_paragraphs": total,
        "volume_subtype": subtype,
        "derived_from": primary_subjects_path(work, vol).name,
        "excludes": excludes,
        "blocks": blocks,
        "multi_owner_segments": multi_owner_segments,
    }


def write_blocks_from_primary(
    work: str,
    vol: str,
    *,
    primary_file: Optional[Path] = None,
    protagonists_file: Optional[Path] = None,
    output: Optional[Path] = None,
) -> Path:
    vol = vol.zfill(3)
    pf = primary_file or primary_subjects_path(work, vol)
    mf = protagonists_file or protagonists_path(work, vol)
    if not pf.is_file():
        raise FileNotFoundError(f"primary_subjects 不存在: {pf}")
    if not mf.is_file():
        raise FileNotFoundError(f"protagonists 不存在: {mf}")

    primary = json.loads(pf.read_text(encoding="utf-8"))
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    index = json.loads(_paragraph_index_path(work, vol).read_text(encoding="utf-8"))

    draft = aggregate_blocks(primary, manifest, index, work=work, vol=vol)
    out = output or blocks_path(work, vol)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Step1b-β primary_subjects → blocks")
    ap.add_argument("--work", required=True)
    ap.add_argument("--vol", required=True)
    ap.add_argument("--primary", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    try:
        out = write_blocks_from_primary(
            args.work.strip(),
            args.vol.zfill(3),
            primary_file=args.primary,
            output=args.output,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    draft = json.loads(out.read_text(encoding="utf-8"))
    n_b = len(draft.get("blocks") or [])
    n_e = len(draft.get("excludes") or [])
    print(f"✅ blocks → {out} · {n_b} 块 · {n_e} exclude")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
