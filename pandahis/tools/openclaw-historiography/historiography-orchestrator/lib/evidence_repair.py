"""Step1 原文挑战脚本修复：篇内小标题排除 + 开篇原文字句对齐段落索引。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from lib.config import ANNOTATE_DIR, paths

sys.path.insert(0, str(ANNOTATE_DIR))
from paragraph_utils import is_volume_title_paragraph, is_part_subtitle_paragraph  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "historiography-pipeline"))
from evidence_verify import challenge_substring  # noqa: E402

# 篇内小标题识别见 paragraph_utils.is_part_subtitle_paragraph


def _paragraph_map(work: str, vol: str) -> Dict[int, str]:
    from lib import gates

    idx = gates.load_paragraph_index(work, vol)
    return {int(p["id"]): str(p.get("text") or "") for p in idx.get("paragraphs") or []}


def _is_subtitle_paragraph(text: str) -> bool:
    if is_volume_title_paragraph(text):
        return True
    return is_part_subtitle_paragraph(text)


def _entry_opening_paragraph(entry: dict) -> int | None:
    prs = entry.get("paragraphs") or []
    if not prs:
        return None
    pids: List[int] = []
    for p in prs:
        if not isinstance(p, dict):
            continue
        pf = p.get("paragraph_from")
        if pf is None and p.get("paragraph") is not None:
            pf = p.get("paragraph")
        if pf is None:
            continue
        pids.append(int(pf))
    return min(pids) if pids else None


def repair_step1_evidence(
    work: str,
    vol: str,
    *,
    skeleton_path: Path | None = None,
) -> Tuple[bool, str]:
    """修复篇内小标题误归属 + 开篇原文字句与段首对齐。"""
    vol = vol.zfill(3)
    sk_path = skeleton_path or _find_skeleton(work, vol)
    if not sk_path:
        return False, "未找到 skeleton"

    data = json.loads(sk_path.read_text(encoding="utf-8"))
    para_map = _paragraph_map(work, vol)
    msgs: List[str] = []

    # 1) 篇内小标题 → 排除段
    for seg in data.get("segment_attribution") or []:
        pid = int(seg["paragraph"])
        text = para_map.get(pid, "")
        if not _is_subtitle_paragraph(text):
            continue
        if seg.get("exclude_reason") or not (seg.get("owners") or []):
            continue
        seg["owners"] = []
        seg["exclude_reason"] = "篇内小标题"
        msgs.append(f"P{pid}→篇内小标题")

    # 2) 条目开篇段：若为小标题则后移；同步原文字句
    for entry in data.get("entries") or []:
        op = _entry_opening_paragraph(entry)
        if op is None:
            continue
        prs = entry.get("paragraphs") or []
        if op in para_map and _is_subtitle_paragraph(para_map[op]):
            new_from = op + 1
            total = int(data.get("total_paragraphs") or 0)
            while new_from <= total and _is_subtitle_paragraph(para_map.get(new_from, "")):
                new_from += 1
            if new_from <= total:
                new_prs: List[dict] = []
                for p in prs:
                    if not isinstance(p, dict):
                        new_prs.append(p)
                        continue
                    pf = p.get("paragraph_from")
                    if pf is None:
                        new_prs.append(p)
                        continue
                    row = dict(p)
                    if int(pf) == op:
                        row["paragraph_from"] = new_from
                    new_prs.append(row)
                entry["paragraphs"] = new_prs
                op = new_from
                msgs.append(f"{entry.get('史略名称')} 开篇段→P{new_from}")

        text = para_map.get(op, "")
        if not text.strip():
            continue
        challenge = challenge_substring(text)
        quote = re.sub(r"\s+", "", str(entry.get("原文字句") or ""))
        if challenge and challenge not in quote:
            entry["原文字句"] = text.strip()[:80]
            msgs.append(f"{entry.get('史略名称')} 原文字句←P{op}")

    if not msgs:
        return False, "无需修复"

    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, "；".join(msgs[:6]) + (f" 等{len(msgs)}项" if len(msgs) > 6 else "")


def _find_skeleton(work: str, vol: str) -> Path | None:
    matches = sorted(paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None
