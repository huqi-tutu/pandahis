#!/usr/bin/env python3
"""v2 Step1b：blocks.json → skeleton.json（含 multi_owner_segments 覆盖）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_ANNOTATE = _ROOT / "historiography-annotate"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ANNOTATE) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE))

from expand_blocks import expand_blocks, merge_entry_paragraphs  # noqa: E402
from paragraph_utils import classify_paragraph_header  # noqa: E402
from paths_config import histograph_paths  # noqa: E402

WORK_ENTRY_PREFIX: Dict[str, str] = {
    "01史记": "SHIJI",
    "01A尚书": "SHANGSHU",
    "02汉书": "HANSHU",
    "03后汉书": "HOUHANSHU",
}


def _paragraph_index_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    paths = histograph_paths()
    names = (f"{work}_{vol}.json",)
    for base in (paths["paragraph_index"], paths["annotations_v1"] / "段落索引"):
        for name in names:
            candidate = base / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"段落索引不存在: {work} vol {vol}")


def _load_index(work: str, vol: str) -> dict:
    return json.loads(_paragraph_index_path(work, vol).read_text(encoding="utf-8"))


def _annotate_work() -> Path:
    p = histograph_paths()["annotate_work"]
    p.mkdir(parents=True, exist_ok=True)
    return p


def _blocks_path(work: str, vol: str) -> Path:
    return _annotate_work() / f"{work}_{vol.zfill(3)}_blocks.json"


def _protagonists_path(work: str, vol: str) -> Path:
    return _annotate_work() / f"{work}_{vol.zfill(3)}_protagonists.json"


def _skeleton_path(work: str, vol: str, index: dict) -> Path:
    vol = vol.zfill(3)
    src = (index.get("source_file") or f"{work}_{vol}.txt").strip()
    stem = Path(src).stem
    return histograph_paths()["annotations"] / f"{stem}_skeleton.json"


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


def _volume_display_name(work: str, vol: str, index: dict) -> str:
    src = (index.get("source_file") or "").strip()
    stem = Path(src).stem if src else f"{work}_{vol.zfill(3)}"
    prefix = f"{work}_{vol.zfill(3)}_"
    name = stem[len(prefix) :] if stem.startswith(prefix) else stem
    return re.sub(r"第[一二三四五六七八九十百零]+(?:章|节|卷)?$", "", name)


def _merge_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged: List[Tuple[int, int]] = [ranges[0]]
    for pf, pt in ranges[1:]:
        lpf, lpt = merged[-1]
        if pf <= lpt + 1:
            merged[-1] = (lpf, max(lpt, pt))
        else:
            merged.append((pf, pt))
    return merged


def _entry_opening_quote(para_text: Dict[int, str], ranges: List[Tuple[int, int]]) -> str:
    if not ranges:
        return ""
    pf, _ = ranges[0]
    text = para_text.get(pf, "")
    return text[:200] if len(text) > 200 else text


def _detect_exclude_paragraphs(para_text: Dict[int, str], work: str) -> List[Tuple[int, int, str]]:
    """single/fanzuo 机械 exclude：卷首标题 + 论赞类。"""
    excludes: List[Tuple[int, int, str]] = []
    if not para_text:
        return excludes
    p1 = (para_text.get(1, "") or "").strip()
    max_pid = max(para_text)
    # 汉书：连续卷首标题行（如 P1「卷十一」+ P2「哀帝纪第十一」）
    if work.startswith("02汉书"):
        pid = 1
        while pid <= min(3, max_pid):
            text = (para_text.get(pid, "") or "").strip()
            if classify_paragraph_header(text) == "卷首标题":
                excludes.append((pid, pid, "卷首标题"))
                pid += 1
            else:
                break
    elif p1 in {"【原文】", "原文"} or (len(p1) <= 6 and p1.startswith("【") and p1.endswith("】")):
        excludes.append((1, 1, "卷首标题"))
    elif re.search(r"卷[一二三四五六七八九十百零\d]+", p1) and classify_paragraph_header(p1) == "卷首标题":
        excludes.append((1, 1, "卷首标题"))
    covered: set[int] = set()
    for pf, pt, _ in excludes:
        for p in range(pf, pt + 1):
            covered.add(p)
    for pid, text in sorted(para_text.items()):
        if pid in covered:
            continue
        head = (text or "")[:80]
        head_s = head.strip()
        if "太史公曰" in head:
            excludes.append((pid, pid, "太史公曰"))
            covered.add(pid)
            for next_pid in range(pid + 1, max_pid + 1):
                if next_pid not in covered:
                    excludes.append((next_pid, next_pid, "论赞"))
                    covered.add(next_pid)
        elif head_s.startswith("褚先生曰"):
            # 褚少孙补论 + 其后引文（如贾生《过秦论》）→ 论赞块
            excludes.append((pid, pid, "论赞"))
            covered.add(pid)
            for next_pid in range(pid + 1, max_pid + 1):
                if next_pid not in covered:
                    excludes.append((next_pid, next_pid, "论赞"))
                    covered.add(next_pid)
        elif head.startswith("赞曰") or "赞曰：" in head[:20]:
            # 赞曰后仍有长叙事段 → 不归 exclude（如《扬雄传》下 P37 自序式传记）
            has_following_narrative = any(
                next_pid not in covered
                and len((para_text.get(next_pid) or "").strip()) > 80
                and not (para_text.get(next_pid) or "").strip()[:24].startswith(
                    ("论曰", "赞曰", "太史公曰")
                )
                for next_pid in range(pid + 1, max_pid + 1)
            )
            if not has_following_narrative:
                excludes.append((pid, pid, "赞曰"))
                covered.add(pid)
        elif head.startswith("论曰") or "论曰：" in head[:20]:
            excludes.append((pid, pid, "论赞"))
            covered.add(pid)
    return excludes


def _mechanical_open_phrase(text: str) -> str:
    t = (text or "").strip()
    if len(t) >= 6:
        return t[: min(40, len(t))]
    # 短于 6 字不得用句号补齐（会触发 BOUNDARY_PHRASE）；调用方应先 exclude 该段
    return t


def _contiguous_runs(paragraphs: List[int]) -> List[tuple[int, int]]:
    if not paragraphs:
        return []
    runs: List[tuple[int, int]] = []
    start = prev = paragraphs[0]
    for p in paragraphs[1:]:
        if p == prev + 1:
            prev = p
        else:
            runs.append((start, prev))
            start = prev = p
    runs.append((start, prev))
    return runs


def build_mechanical_blocks(protagonists: dict, index: dict, work: str) -> dict:
    total = int(index["total"])
    para_text = _para_text_map(index)
    mode = (protagonists.get("narrative_mode") or "single").strip()
    plist = protagonists.get("protagonists") or []
    if not plist:
        raise ValueError("protagonists 为空")

    excludes_raw = _detect_exclude_paragraphs(para_text, work)
    excluded: set[int] = set()
    excludes: List[dict] = []
    for pf, pt, reason in excludes_raw:
        excludes.append({"paragraph_from": pf, "paragraph_to": pt, "exclude_reason": reason})
        for p in range(pf, pt + 1):
            excluded.add(p)

    narrative = [p for p in range(1, total + 1) if p not in excluded]
    if not narrative:
        raise ValueError("无叙事段可归属")

    item = plist[0]
    name = (item.get("name") or "").strip()
    cat = (item.get("category") or "君王").strip()
    runs = _contiguous_runs(narrative)
    blocks = []
    for pf, pt in runs:
        blocks.append(
            {
                "name": name,
                "category": cat,
                "paragraph_from": pf,
                "paragraph_to": pt,
                "boundary_evidence": {
                    "open_paragraph": pf,
                    "open_phrase": _mechanical_open_phrase(para_text.get(pf, "")),
                    "close_paragraph": pt,
                    "close_note": "single/fanzuo 机械整卷",
                },
            }
        )
    return {
        "work": work,
        "vol": protagonists.get("vol"),
        "total_paragraphs": total,
        "volume_subtype": protagonists.get("volume_subtype") or mode,
        "excludes": excludes,
        "blocks": blocks,
        "multi_owner_segments": [],
    }


def apply_multi_owner(
    attribution: List[dict], draft: dict
) -> List[dict]:
    overrides = {
        int(item["paragraph"]): item
        for item in (draft.get("multi_owner_segments") or [])
        if isinstance(item, dict) and item.get("paragraph")
    }
    if not overrides:
        return attribution

    out: List[dict] = []
    for row in attribution:
        pid = int(row["paragraph"])
        if pid in overrides:
            ov = overrides[pid]
            owners = ov.get("owners") or []
            out.append({"paragraph": pid, "owners": owners})
        else:
            out.append(row)
    return out


def expand_to_skeleton(
    work: str,
    vol: str,
    *,
    blocks_file: Path | None = None,
    skeleton_out: Path | None = None,
) -> Path:
    vol = vol.zfill(3)
    index = _load_index(work, vol)
    bp = blocks_file or _blocks_path(work, vol)
    if not bp.exists():
        raise FileNotFoundError(f"blocks 不存在: {bp}")

    draft = json.loads(bp.read_text(encoding="utf-8"))
    draft["total_paragraphs"] = int(index["total"])

    attribution, expand_errs = expand_blocks(draft)
    if expand_errs:
        raise ValueError("expand_blocks:\n" + "\n".join(expand_errs))

    attribution = apply_multi_owner(attribution, draft)

    para_text = _para_text_map(index)
    volume_name = _volume_display_name(work, vol, index)
    src_file = (index.get("source_file") or f"{work}_{vol}.txt").strip()
    prefix = WORK_ENTRY_PREFIX.get(work, "ENT")
    vol_num = int(vol)

    # entries 以 attribution 为准（含 multi_owner 交接双挂），blocks 仅作分类回退
    cat_by_name: Dict[str, str] = {}
    for blk in draft.get("blocks") or []:
        if isinstance(blk, dict) and blk.get("name"):
            cat_by_name[(blk.get("name") or "").strip()] = (blk.get("category") or "君王").strip()
    for item in draft.get("multi_owner_segments") or []:
        if not isinstance(item, dict):
            continue
        for o in item.get("owners") or []:
            if isinstance(o, dict) and o.get("name"):
                cat_by_name.setdefault(
                    (o.get("name") or "").strip(),
                    (o.get("category") or "君王").strip(),
                )

    pids_by_name: Dict[str, List[int]] = {}
    for row in attribution:
        pid = int(row.get("paragraph") or 0)
        if pid <= 0:
            continue
        for o in row.get("owners") or []:
            if not isinstance(o, dict):
                continue
            name = (o.get("name") or "").strip()
            if not name:
                continue
            if o.get("category"):
                cat_by_name.setdefault(name, (o.get("category") or "君王").strip())
            pids_by_name.setdefault(name, []).append(pid)

    # 保底：attribution 未覆盖时仍用 blocks（merge_entry_paragraphs）
    if not pids_by_name:
        raw_entries = merge_entry_paragraphs(draft, attribution)
        for raw in raw_entries:
            name = (raw.get("史略名称") or "").strip()
            cat = (raw.get("史略分类") or "君王").strip()
            for blk in raw.get("paragraphs") or []:
                fr = int(blk.get("paragraph_from") or 0)
                to = int(blk.get("paragraph_to") or fr)
                pids_by_name.setdefault(name, []).extend(range(fr, to + 1))
            cat_by_name.setdefault(name, cat)

    # 稳定顺序：按 blocks 出现序，再补 multi_owner 独有名
    ordered_names: List[str] = []
    for blk in draft.get("blocks") or []:
        n = (blk.get("name") or "").strip()
        if n and n not in ordered_names and n in pids_by_name:
            ordered_names.append(n)
    for n in pids_by_name:
        if n not in ordered_names:
            ordered_names.append(n)

    entries: List[dict] = []
    for i, name in enumerate(ordered_names, start=1):
        cat = cat_by_name.get(name, "君王")
        pids = sorted(set(p for p in pids_by_name.get(name, []) if p > 0))
        if not pids:
            continue
        ranges = _merge_ranges([(p, p) for p in pids])
        quote = _entry_opening_quote(para_text, ranges)
        entries.append(
            {
                "史略ID": f"{prefix}_{vol}_{i:02d}",
                "史略名称": name,
                "史略简介": name,
                "原文字句": quote,
                "史略分类": cat,
                "主要史料出处": f"《史记·卷{vol_num}·{volume_name}》"
                if work == "01史记"
                else f"《{work}·卷{vol_num}·{volume_name}》",
                "paragraphs": [
                    {"volume": volume_name, "paragraph_from": pf, "paragraph_to": pt}
                    for pf, pt in ranges
                ],
            }
        )

    protagonists: Dict[str, Any] = {}
    pp = _protagonists_path(work, vol)
    if pp.is_file():
        try:
            protagonists = json.loads(pp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            protagonists = {}

    texture = (protagonists.get("volume_texture") or draft.get("volume_texture") or "").strip()
    # 任一 entry 多段非连续 → 视为混写（除非显式 sequential）
    if texture != "sequential":
        if any(len(e.get("paragraphs") or []) >= 2 for e in entries):
            texture = "interleaved"
        elif not texture:
            texture = "sequential"

    skeleton: Dict[str, Any] = {
        "volume": volume_name,
        "source_file": src_file,
        "total_paragraphs": int(index["total"]),
        "volume_type": "纪传叙事",
        "volume_subtype": draft.get("volume_subtype") or protagonists.get("volume_subtype"),
        "volume_texture": texture,
        "segment_attribution": attribution,
        "entries": entries,
    }
    if texture == "interleaved":
        skeleton["translation_qa_hint"] = (
            "混写卷：人物段落非连续。翻译质检须按 entries[].paragraphs 多段拼接，"
            "勿按卷内段号顺序假定语义连贯。"
        )

    out = skeleton_out or _skeleton_path(work, vol, index)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        from v2_interleaved_registry import register_volume  # same dir

        rec = register_volume(
            work,
            vol,
            skeleton=skeleton,
            protagonists=protagonists,
            skeleton_file=out.name,
        )
        if rec:
            print(f"📌 已登记混写卷 → {histograph_paths()['progress'] / f'{work}_混写卷.json'}")
    except Exception as exc:  # noqa: BLE001 — 登记失败不阻断 skeleton
        print(f"⚠️ 混写卷登记跳过: {exc}", file=sys.stderr)

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="v2 blocks → skeleton")
    ap.add_argument("--work", required=True)
    ap.add_argument("--vol", required=True)
    ap.add_argument("--blocks", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument(
        "--mechanical",
        action="store_true",
        help="single/fanzuo：从 protagonists 机械生成 blocks 再展开",
    )
    args = ap.parse_args()

    work = args.work.strip()
    vol = args.vol.zfill(3)

    if args.mechanical:
        pp = _protagonists_path(work, vol)
        if not pp.exists():
            print(f"❌ protagonists 不存在: {pp}", file=sys.stderr)
            return 1
        protagonists = json.loads(pp.read_text(encoding="utf-8"))
        index = _load_index(work, vol)
        draft = build_mechanical_blocks(protagonists, index, work)
        bp = _blocks_path(work, vol)
        bp.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"📝 机械 blocks → {bp}")

    try:
        out = expand_to_skeleton(work, vol, blocks_file=args.blocks, skeleton_out=args.output)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    print(f"✅ skeleton → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
