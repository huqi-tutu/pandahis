#!/usr/bin/env python3
"""《史记》Step1 blocks 草稿自动修复：exclude 误标、段落未覆盖。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from exclude_content_gate import validate_exclude_for_paragraph, validate_blocks_excludes
from expand_blocks import expand_blocks

_GAP_RE = re.compile(r"P(\d+) 未覆盖")


def _paragraph_text_map(index: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for row in index.get("paragraphs") or []:
        pid = int(row.get("id") or 0)
        if pid:
            out[pid] = (row.get("text") or "").strip()
    return out


def _merge_adjacent_excludes(excludes: List[dict]) -> List[dict]:
    if not excludes:
        return []
    items = sorted(
        (
            int(x["paragraph_from"]),
            int(x["paragraph_to"]),
            (x.get("exclude_reason") or "").strip(),
        )
        for x in excludes
    )
    merged: List[dict] = []
    pf, pt, reason = items[0]
    for nf, nt, nr in items[1:]:
        if nr == reason and nf == pt + 1:
            pt = nt
        else:
            merged.append(
                {"paragraph_from": pf, "paragraph_to": pt, "exclude_reason": reason}
            )
            pf, pt, reason = nf, nt, nr
    merged.append({"paragraph_from": pf, "paragraph_to": pt, "exclude_reason": reason})
    return merged


def _covered_and_excluded(draft: dict) -> Tuple[set, set]:
    excluded: set = set()
    for ex in draft.get("excludes") or []:
        pf = int(ex.get("paragraph_from") or 0)
        pt = int(ex.get("paragraph_to") or pf)
        for p in range(pf, pt + 1):
            excluded.add(p)
    covered: set = set()
    for blk in draft.get("blocks") or []:
        pf = int(blk.get("paragraph_from") or 0)
        pt = int(blk.get("paragraph_to") or pf)
        for p in range(pf, pt + 1):
            covered.add(p)
    return covered, excluded


def repair_excludes(
    draft: dict,
    para_text: Dict[int, str],
    *,
    work_id: str = "01史记",
) -> List[str]:
    """移除误标 exclude，补全真实太史公曰段。"""
    logs: List[str] = []
    total = int(draft.get("total_paragraphs") or 0)
    taishi_ps = {
        p
        for p in range(1, total + 1)
        if para_text.get(p, "").startswith("太史公曰")
    }

    kept: List[dict] = []
    for ex in draft.get("excludes") or []:
        if not isinstance(ex, dict):
            continue
        pf = int(ex.get("paragraph_from") or 0)
        pt = int(ex.get("paragraph_to") or pf)
        reason = (ex.get("exclude_reason") or "").strip()
        drop = False
        for p in range(pf, pt + 1):
            errs = validate_exclude_for_paragraph(
                p, para_text.get(p, ""), reason, work_id=work_id
            )
            if errs:
                logs.append(f"移除误标 exclude P{p}={reason!r}")
                drop = True
        if not drop:
            kept.append(dict(ex))

    for p in sorted(taishi_ps):
        if any(
            int(ex["paragraph_from"]) <= p <= int(ex["paragraph_to"])
            for ex in kept
        ):
            continue
        kept.append(
            {
                "paragraph_from": p,
                "paragraph_to": p,
                "exclude_reason": "太史公曰",
            }
        )
        logs.append(f"补标太史公曰 P{p}")

    draft["excludes"] = _merge_adjacent_excludes(kept)
    return logs


def _split_blocks_from_excludes(draft: dict) -> List[str]:
    """叙事块不得与 exclude 重叠。"""
    logs: List[str] = []
    excluded: set = set()
    for ex in draft.get("excludes") or []:
        pf = int(ex.get("paragraph_from") or 0)
        pt = int(ex.get("paragraph_to") or pf)
        for p in range(pf, pt + 1):
            excluded.add(p)
    for blk in draft.get("blocks") or []:
        pf = int(blk.get("paragraph_from") or 0)
        pt = int(blk.get("paragraph_to") or pf)
        name = (blk.get("name") or "").strip()
        while pf <= pt and pf in excluded:
            pf += 1
        if pf > pt:
            logs.append(f"块 {name} 与 exclude 完全重叠，待人工处理")
            continue
        if pf != int(blk.get("paragraph_from") or 0):
            blk["paragraph_from"] = pf
            logs.append(f"块 {name} 起段调整为 P{pf}（避开 exclude）")
    return logs


def extend_blocks_fill_gaps(draft: dict) -> List[str]:
    """未覆盖段并入前一叙事块（同卷合传常见漏段）。"""
    logs: List[str] = []
    total = int(draft.get("total_paragraphs") or 0)
    if total <= 0:
        return logs
    blocks = list(draft.get("blocks") or [])
    if not blocks:
        return logs

    _, excluded = _covered_and_excluded(draft)

    changed = True
    while changed:
        changed = False
        covered, excluded = _covered_and_excluded(draft)
        blocks.sort(key=lambda b: int(b.get("paragraph_from") or 0))
        for p in range(1, total + 1):
            if p in covered or p in excluded:
                continue
            target = None
            for blk in blocks:
                if int(blk.get("paragraph_to") or 0) == p - 1:
                    target = blk
                    break
            if not target:
                prior = [
                    b
                    for b in blocks
                    if int(b.get("paragraph_to") or 0) < p
                ]
                if prior:
                    target = max(prior, key=lambda b: int(b.get("paragraph_to") or 0))
            if target:
                name = (target.get("name") or "").strip()
                target["paragraph_to"] = p
                logs.append(f"延伸块 {name} → P{p}")
                changed = True
                break
    draft["blocks"] = blocks
    return logs


def repair_blocks_draft(
    draft: dict,
    para_text: Dict[int, str],
    *,
    work_id: str = "01史记",
) -> Tuple[bool, List[str]]:
    """就地修复 blocks 草稿；返回 (是否改动, 日志)。"""
    logs: List[str] = []
    before = json.dumps(draft, ensure_ascii=False, sort_keys=True)

    logs.extend(repair_excludes(draft, para_text, work_id=work_id))
    logs.extend(_split_blocks_from_excludes(draft))
    logs.extend(extend_blocks_fill_gaps(draft))

    _, expand_errs = expand_blocks(draft)
    for err in expand_errs:
        m = _GAP_RE.search(err)
        if m:
            logs.extend(extend_blocks_fill_gaps(draft))
            break

    ok_ex, _ = validate_blocks_excludes(draft, para_text, work_id=work_id)
    if not ok_ex:
        logs.extend(repair_excludes(draft, para_text, work_id=work_id))

    after = json.dumps(draft, ensure_ascii=False, sort_keys=True)
    return before != after, logs


def try_repair_blocks_file(
    blocks_path: Path,
    index: dict,
    *,
    work_id: str = "01史记",
) -> Tuple[bool, List[str]]:
    if not blocks_path.exists():
        return False, ["blocks 文件不存在"]
    try:
        draft = json.loads(blocks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"JSON 解析失败: {exc}"]

    total = int(index.get("total") or 0)
    if total:
        draft["total_paragraphs"] = total
    para_text = _paragraph_text_map(index)
    changed, logs = repair_blocks_draft(draft, para_text, work_id=work_id)
    if not changed:
        return False, logs or ["无需修改"]

    _, expand_errs = expand_blocks(draft)
    if expand_errs:
        return False, logs + [f"仍有问题: {expand_errs[0]}"]

    ok_ex, ex_msg = validate_blocks_excludes(draft, para_text, work_id=work_id)
    if not ok_ex:
        return False, logs + [ex_msg.split("\n")[0]]

    blocks_path.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True, logs
