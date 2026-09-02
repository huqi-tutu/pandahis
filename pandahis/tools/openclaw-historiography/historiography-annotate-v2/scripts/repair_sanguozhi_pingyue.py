#!/usr/bin/env python3
"""把《三国志》「评曰」从条目/事略中剔除。

1. 拆开粘在叙事末句后的「评曰」（如 009）
2. 单传卷机械重展 skeleton（评曰 exclude）
3. 其余卷：评曰起笔段若仍有 owner，改为 exclude
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parents[2]
_ANNOTATE = _ROOT / "historiography-annotate"
_V2 = Path(__file__).resolve().parent
for p in (_ROOT, _ANNOTATE, _V2):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from paragraph_utils import split_glued_pingyue  # noqa: E402
from paths_config import histograph_paths  # noqa: E402
from v2_aggregate_blocks import write_blocks_from_primary  # noqa: E402
from v2_expand_to_skeleton import expand_to_skeleton  # noqa: E402

WORK = "04三国志"
SINGLE_VOLS = ("001", "002", "003", "032", "033", "035", "047", "058")


def _dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _para_items(index: dict) -> List[dict]:
    items = index.get("paragraphs") or []
    return [x for x in items if isinstance(x, dict)]


def _pid(item: dict) -> int:
    return int(item.get("id") or item.get("paragraph") or 0)


def split_glued_in_index_and_source(vol: str) -> List[str]:
    logs: List[str] = []
    paths = histograph_paths()
    idx_path = paths["paragraph_index"] / f"{WORK}_{vol}.json"
    if not idx_path.is_file():
        idx_path = paths["paragraph_index"] / f"{WORK}_{vol}.json"
    if not idx_path.is_file():
        return [f"{vol}: 无段落索引"]

    index = json.loads(idx_path.read_text(encoding="utf-8"))
    items = _para_items(index)
    glued: List[Tuple[int, dict, List[str]]] = []
    for item in items:
        pid = _pid(item)
        text = (item.get("text") or "").strip()
        parts = split_glued_pingyue(text)
        if parts:
            glued.append((pid, item, parts))
    if not glued:
        return logs

    src_rel = (index.get("source_path") or index.get("source_file") or "").strip()
    src_path: Path | None = None
    if src_rel:
        candidate = paths["data"] / src_rel
        if candidate.is_file():
            src_path = candidate
        else:
            by_name = paths["sources"] / Path(src_rel).name
            if by_name.is_file():
                src_path = by_name
    if src_path is None:
        src_file = (index.get("source_file") or "").strip()
        matches = list(paths["sources"].glob(f"**/{src_file}")) if src_file else []
        if matches:
            src_path = matches[0]

    # 只处理末段粘连，避免中间插入导致后续段号全移
    last_pid = max(_pid(x) for x in items)
    for pid, item, parts in glued:
        if pid != last_pid:
            logs.append(f"{vol}: P{pid} 评曰粘连但不在末段，跳过以免改段号")
            continue
        before, after = parts
        item["text"] = before
        items.append({"id": last_pid + 1, "text": after})
        index["total"] = last_pid + 1
        index["paragraphs"] = items
        _dump(idx_path, index)
        logs.append(f"{vol}: 段落索引 P{pid} 拆出 P{last_pid + 1} 评曰")

        if src_path and src_path.is_file():
            raw = src_path.read_text(encoding="utf-8")
            old = before + after
            if old in raw:
                raw = raw.replace(old, before + "\n" + after, 1)
                src_path.write_text(raw, encoding="utf-8")
                logs.append(f"{vol}: 原文已拆行 {src_path.name}")
            elif after in raw:
                idx = raw.find(after)
                if idx > 0 and raw[idx - 1] != "\n":
                    raw = raw[:idx] + "\n" + raw[idx:]
                    src_path.write_text(raw, encoding="utf-8")
                    logs.append(f"{vol}: 原文在评曰前插入换行")
                else:
                    logs.append(f"{vol}: 原文评曰已独立成行")
            else:
                logs.append(f"{vol}: 原文未改（needle miss）")
    return logs


def _exclude_pingyue_in_skeleton(skel: dict, ping_pids: List[int]) -> bool:
    changed = False
    attr = skel.get("segment_attribution") or []
    for row in attr:
        if not isinstance(row, dict):
            continue
        pid = int(row.get("paragraph") or 0)
        if pid not in ping_pids:
            continue
        if row.get("owners"):
            row["owners"] = []
            row["exclude_reason"] = "评曰"
            changed = True
        elif not (row.get("exclude_reason") or "").strip():
            row["exclude_reason"] = "评曰"
            changed = True
    ping_set = set(ping_pids)
    for entry in skel.get("entries") or []:
        ranges = entry.get("paragraphs") or []
        new_ranges: List[dict] = []
        for pr in ranges:
            if not isinstance(pr, dict):
                continue
            pf = int(pr.get("paragraph_from") or 0)
            pt = int(pr.get("paragraph_to") or pf)
            hit = [p for p in range(pf, pt + 1) if p in ping_set]
            if not hit:
                new_ranges.append(pr)
                continue
            changed = True
            # 从区间两端剥掉评曰段
            keep = [p for p in range(pf, pt + 1) if p not in ping_set]
            if not keep:
                continue
            start = keep[0]
            prev = keep[0]
            for p in keep[1:]:
                if p == prev + 1:
                    prev = p
                    continue
                new_ranges.append(
                    {**pr, "paragraph_from": start, "paragraph_to": prev}
                )
                start = prev = p
            new_ranges.append({**pr, "paragraph_from": start, "paragraph_to": prev})
        entry["paragraphs"] = new_ranges
    return changed


def _exclude_pingyue_in_blocks(draft: dict, ping_pids: List[int]) -> bool:
    changed = False
    ping_set = set(ping_pids)
    excludes = list(draft.get("excludes") or [])
    covered: set[int] = set()
    for ex in excludes:
        if not isinstance(ex, dict):
            continue
        pf = int(ex.get("paragraph_from") or 0)
        pt = int(ex.get("paragraph_to") or pf)
        for p in range(pf, pt + 1):
            covered.add(p)
        if any(pf <= p <= pt for p in ping_pids):
            if (ex.get("exclude_reason") or "").strip() not in {"评曰", "论赞"}:
                ex["exclude_reason"] = "评曰"
                changed = True
    for pid in ping_pids:
        if pid not in covered:
            excludes.append(
                {"paragraph_from": pid, "paragraph_to": pid, "exclude_reason": "评曰"}
            )
            covered.add(pid)
            changed = True
    draft["excludes"] = excludes
    blocks = []
    for blk in draft.get("blocks") or []:
        if not isinstance(blk, dict):
            continue
        pf = int(blk.get("paragraph_from") or 0)
        pt = int(blk.get("paragraph_to") or pf)
        if not any(pf <= p <= pt for p in ping_pids):
            blocks.append(blk)
            continue
        changed = True
        ev = dict(blk.get("boundary_evidence") or {})
        new_pt = pt
        while new_pt >= pf and new_pt in ping_set:
            new_pt -= 1
        new_pf = pf
        while new_pf <= new_pt and new_pf in ping_set:
            new_pf += 1
        if new_pt < new_pf:
            continue
        blk = dict(blk)
        blk["paragraph_from"] = new_pf
        blk["paragraph_to"] = new_pt
        if ev:
            ev["close_paragraph"] = new_pt
            blk["boundary_evidence"] = ev
        blocks.append(blk)
    draft["blocks"] = blocks
    return changed


def repair_volume(vol: str, *, mechanical_singles: bool) -> List[str]:
    logs: List[str] = []
    logs.extend(split_glued_in_index_and_source(vol))
    paths = histograph_paths()
    idx_path = paths["paragraph_index"] / f"{WORK}_{vol}.json"
    if not idx_path.is_file():
        idx_path = paths["paragraph_index"] / f"{WORK}_{vol}.json"
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    ping_pids = [
        _pid(item)
        for item in _para_items(index)
        if (item.get("text") or "").strip().startswith("评曰")
    ]

    prot_path = paths["annotate_work"] / f"{WORK}_{vol}_protagonists.json"
    mode = ""
    if prot_path.is_file():
        mode = (
            json.loads(prot_path.read_text(encoding="utf-8")).get("narrative_mode") or ""
        ).strip()

    if mechanical_singles and vol in SINGLE_VOLS and mode == "single":
        from v2_expand_to_skeleton import (  # local import for mechanical rebuild
            _blocks_path,
            _load_index,
            _protagonists_path,
            build_mechanical_blocks,
        )

        protagonists = json.loads(_protagonists_path(WORK, vol).read_text(encoding="utf-8"))
        idx = _load_index(WORK, vol)
        draft = build_mechanical_blocks(protagonists, idx, WORK)
        bp = _blocks_path(WORK, vol)
        _dump(bp, draft)
        out = expand_to_skeleton(WORK, vol, blocks_file=bp)
        logs.append(f"{vol}: 单传机械重展 → {out.name}")
        return logs

    primary_path = paths["annotate_work"] / f"{WORK}_{vol}_primary_subjects.json"
    split_happened = any("拆出" in x for x in logs)
    if split_happened and primary_path.is_file():
        primary = json.loads(primary_path.read_text(encoding="utf-8"))
        rows = [r for r in (primary.get("paragraphs") or []) if isinstance(r, dict)]
        by_pid = {int(r.get("paragraph") or 0): r for r in rows}
        total = int(index.get("total") or 0)
        for pid in ping_pids:
            leftover = pid - 1
            prev = by_pid.get(leftover - 1) or {}
            if leftover in by_pid and (by_pid[leftover].get("disposition") == "exclude"):
                if (prev.get("disposition") or "block") == "block" and prev.get("primary_subject"):
                    by_pid[leftover]["primary_subject"] = prev.get("primary_subject")
                    by_pid[leftover]["disposition"] = "block"
                    by_pid[leftover].pop("exclude_reason", None)
            row = by_pid.get(pid) or {"paragraph": pid}
            row["paragraph"] = pid
            row["primary_subject"] = "评曰"
            row["disposition"] = "exclude"
            row["exclude_reason"] = "评曰"
            row.pop("co_owner", None)
            by_pid[pid] = row
        primary["paragraphs"] = [by_pid[p] for p in sorted(by_pid)]
        if total:
            primary["total_paragraphs"] = total
        _dump(primary_path, primary)
        write_blocks_from_primary(WORK, vol)
        expand_to_skeleton(WORK, vol)
        logs.append(f"{vol}: 拆段后重聚合 blocks / skeleton")
        return logs

    # hezhuan / 已有 blocks：只剥评曰
    blk_path = paths["annotate_work"] / f"{WORK}_{vol}_blocks.json"
    if blk_path.is_file() and ping_pids:
        draft = json.loads(blk_path.read_text(encoding="utf-8"))
        if _exclude_pingyue_in_blocks(draft, ping_pids):
            _dump(blk_path, draft)
            logs.append(f"{vol}: blocks 已剔除评曰 {ping_pids}")
        if primary_path.is_file():
            primary = json.loads(primary_path.read_text(encoding="utf-8"))
            changed = False
            rows = primary.get("paragraphs") or []
            have = {int(r.get("paragraph") or 0) for r in rows if isinstance(r, dict)}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                pid = int(row.get("paragraph") or 0)
                if pid in ping_pids and (
                    row.get("disposition") != "exclude"
                    or (row.get("exclude_reason") or "") not in {"评曰", "论赞"}
                ):
                    row["primary_subject"] = "评曰"
                    row["disposition"] = "exclude"
                    row["exclude_reason"] = "评曰"
                    row.pop("co_owner", None)
                    changed = True
            total = int(index.get("total") or 0)
            for pid in ping_pids:
                if pid not in have:
                    rows.append(
                        {
                            "paragraph": pid,
                            "primary_subject": "评曰",
                            "disposition": "exclude",
                            "exclude_reason": "评曰",
                        }
                    )
                    changed = True
            if changed:
                primary["paragraphs"] = sorted(
                    rows, key=lambda r: int(r.get("paragraph") or 0)
                )
                if total:
                    primary["total_paragraphs"] = total
                _dump(primary_path, primary)
                logs.append(f"{vol}: primary_subjects 已标评曰 exclude")

    sk_matches = list(paths["annotations"].glob(f"{WORK}_{vol}_*_skeleton.json"))
    if sk_matches and ping_pids:
        sk_path = sk_matches[0]
        skel = json.loads(sk_path.read_text(encoding="utf-8"))
        if int(skel.get("total_paragraphs") or 0) != int(index.get("total") or 0):
            skel["total_paragraphs"] = int(index.get("total") or 0)
        if _exclude_pingyue_in_skeleton(skel, ping_pids):
            _dump(sk_path, skel)
            logs.append(f"{vol}: skeleton 已剔除评曰 {ping_pids}")
    return logs


def main() -> int:
    ap = argparse.ArgumentParser(description="三国志评曰不入条目")
    ap.add_argument("--vol", help="只修一卷（三位卷号）")
    args = ap.parse_args()
    vols = [args.vol.zfill(3)] if args.vol else [f"{i:03d}" for i in range(1, 66)]
    n_log = 0
    for vol in vols:
        idx = histograph_paths()["paragraph_index"] / f"{WORK}_{vol}.json"
        if not idx.is_file() and not (
            histograph_paths()["paragraph_index"] / f"{WORK}_{vol}.json"
        ).is_file():
            continue
        logs = repair_volume(vol, mechanical_singles=True)
        for line in logs:
            print(line)
            n_log += 1
    if n_log == 0:
        print("无需修改（评曰均已 exclude 或不存在）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
