#!/usr/bin/env python3
"""原文挑战 + 审计表一致性：可脚本验证的「读过原文」证据门。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from semantic_audit_verify import select_block_for_volume, split_volume_blocks

CHALLENGE_MIN_LEN = 12
DEFAULT_SPOT_COUNT = 8

PARA_ROW_FULL_RE = re.compile(
    r"^\|\s*P(\d+)\s*\|\s*([^|]+)\|",
    re.MULTILINE,
)


def spot_paragraph_ids(work: str, vol: str, total: int, k: int = DEFAULT_SPOT_COUNT) -> List[int]:
    """确定性抽样段号（可复现，便于 debug）。"""
    if total <= 0:
        return []
    k = min(k, total)
    seed = hashlib.sha256(f"{work}:{vol.zfill(3)}:spot_v1".encode()).hexdigest()
    order = list(range(1, total + 1))
    state = int(seed[:16], 16)
    for i in range(total - 1, 0, -1):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    return sorted(order[:k])


def challenge_substring(paragraph_text: str, *, min_len: int = CHALLENGE_MIN_LEN) -> str:
    """段首连续子串（与原文字句摘录习惯一致）。"""
    raw = re.sub(r"\s+", "", paragraph_text or "")
    if len(raw) <= min_len:
        return raw
    return raw[:min_len]


def _paragraph_index_map(index: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for item in index.get("paragraphs") or []:
        pid = int(item.get("id") or item.get("paragraph") or 0)
        if pid:
            out[pid] = str(item.get("text") or "")
    return out


def _fmt_owners(seg: dict) -> str:
    if seg.get("exclude_reason"):
        return f"排除（{seg['exclude_reason']}）"
    parts = []
    for o in seg.get("owners") or []:
        parts.append(f"{o.get('name', '?')}({o.get('category', '?')})")
    return " + ".join(parts) if parts else "—"


def _entry_key(entry: dict) -> Tuple[str, str]:
    return (str(entry.get("史略名称") or entry.get("name") or ""), str(entry.get("史略分类") or ""))


def _paragraph_blocks(entry: dict) -> List[dict | int | str]:
    """entries.paragraphs 应为对象数组；兼容检测整数列表误格式。"""
    return list(entry.get("paragraphs") or [])


def _entry_canonical_start(entry: dict) -> int | None:
    """条目叙事开篇段：所有 paragraphs 区间里最小的 paragraph_from。"""
    starts: List[int] = []
    for block in _paragraph_blocks(entry):
        if isinstance(block, int):
            if block > 0:
                starts.append(block)
            continue
        if isinstance(block, dict):
            lo = int(block.get("paragraph_from") or block.get("from") or 0)
            if lo > 0:
                starts.append(lo)
    return min(starts) if starts else None


def _validate_skeleton_schema(skeleton: dict) -> List[str]:
    """Step1 前置：拒绝 LLM 非标准字段，避免 verify 崩溃。"""
    errors: List[str] = []
    attr = skeleton.get("segment_attribution") or []
    if attr and isinstance(attr[0], dict):
        row0 = attr[0]
        if "owners" not in row0 and ("entry_name" in row0 or "attribution_type" in row0):
            errors.append(
                "segment_attribution 须用 owners[{name,category}]，"
                "不得用 entry_name/attribution_type/entry_id"
            )
        if "owners" not in row0 and not row0.get("exclude_reason"):
            errors.append("segment_attribution 每段须有 owners 或 exclude_reason")
    entries = skeleton.get("entries") or []
    if entries and isinstance(entries[0], dict):
        e0 = entries[0]
        if "史略名称" not in e0 and "entry_name" in e0:
            errors.append("entries 须用 史略名称/史略ID，不得用 entry_name/entry_id")
        prs = e0.get("paragraphs") or []
        if prs and isinstance(prs[0], int):
            errors.append(
                "entries.paragraphs 须为 {paragraph_from, paragraph_to} 对象数组，"
                "不得为整数列表"
            )
    return errors


def _entry_starts_at(entry: dict, para_id: int) -> bool:
    """该段是否为条目的开篇段（仅最小 paragraph_from，非每个区间起点）。"""
    return _entry_canonical_start(entry) == para_id


def verify_skeleton_spot_check(
    work: str,
    vol: str,
    skeleton: dict,
    *,
    paragraph_index: dict,
    spot_count: int = DEFAULT_SPOT_COUNT,
) -> Tuple[bool, List[str]]:
    """
    Step1 证据门：
    1) 抽样段 segment_attribution 完整且 owner 有对应 entry
    2) 若该段是某 entry 的**开篇段**（最小 paragraph_from），原文字句须含段首子串
       （多区间条目只对开篇核对；后续区间仅由 segment_attribution 覆盖）
    """
    _ = work
    schema_errs = _validate_skeleton_schema(skeleton)
    if schema_errs:
        return False, schema_errs

    total = int(skeleton.get("total_paragraphs") or paragraph_index.get("total") or 0)
    para_map = _paragraph_index_map(paragraph_index)
    spots = spot_paragraph_ids(work, vol, total, spot_count)
    segs = {int(s["paragraph"]): s for s in skeleton.get("segment_attribution") or []}
    entry_keys: Set[Tuple[str, str]] = {_entry_key(e) for e in skeleton.get("entries") or []}
    errors: List[str] = []

    for pid in spots:
        seg = segs.get(pid)
        if not seg:
            errors.append(f"P{pid} 缺少 segment_attribution 行")
            continue
        if seg.get("exclude_reason"):
            continue
        for o in seg.get("owners") or []:
            key = (str(o.get("name", "")), str(o.get("category", "")))
            if key not in entry_keys:
                errors.append(f"P{pid} 归属 {key[0]}({key[1]}) 无对应 entry")

    for pid in spots:
        text = para_map.get(pid, "")
        if not text.strip():
            continue
        challenge = challenge_substring(text)
        if not challenge:
            continue
        starters = [e for e in skeleton.get("entries") or [] if _entry_starts_at(e, pid)]
        if not starters:
            continue
        for entry in starters:
            quote = re.sub(r"\s+", "", str(entry.get("原文字句") or ""))
            if challenge not in quote:
                errors.append(
                    f"P{pid} entry「{entry.get('史略名称')}」原文字句与段首不符"
                    f"（须含「{challenge[:16]}…」）"
                )

    return len(errors) == 0, errors


def _parse_audit_table(block_text: str) -> Dict[int, str]:
    rows: Dict[int, str] = {}
    for m in PARA_ROW_FULL_RE.finditer(block_text):
        rows[int(m.group(1))] = m.group(2).strip()
    return rows


_ATTR_SEP_RE = re.compile(r"[+、,，]")


def _normalize_attr(s: str) -> str:
    """比较归属串：去空白；多归属统一用 + 连接（、与 + 等价）。"""
    s = re.sub(r"\s+", "", s or "")
    if not s or s == "—":
        return s
    if s.startswith("排除"):
        return s
    parts = [p for p in _ATTR_SEP_RE.split(s) if p]
    if len(parts) <= 1:
        return s
    return "+".join(parts)


def verify_audit_table_matches_skeleton(
    block_text: str,
    skeleton: dict,
) -> Tuple[bool, List[str]]:
    """审计段落表归属列须与 skeleton segment_attribution 一致。"""
    table = _parse_audit_table(block_text)
    segs = {int(s["paragraph"]): s for s in skeleton.get("segment_attribution") or []}
    total = int(skeleton.get("total_paragraphs") or 0)
    errors: List[str] = []
    if len(table) < total:
        errors.append(f"段落覆盖表仅 {len(table)} 行，少于 {total}")
    for pid in range(1, total + 1):
        if pid not in table:
            errors.append(f"段落覆盖表缺 P{pid}")
            continue
        expected = _fmt_owners(segs.get(pid, {}))
        actual = table[pid]
        if _normalize_attr(expected) != _normalize_attr(actual):
            errors.append(f"P{pid} 归属不一致：表「{actual}」≠ skeleton「{expected}」")
    return len(errors) == 0, errors


def verify_audit_mentions_spots(
    audit_block_text: str,
    spots: List[int],
) -> Tuple[bool, List[str]]:
    """Step3：准入过程/段落表须显式提及抽样段号 P{n}。"""
    errors: List[str] = []
    for pid in spots:
        if not re.search(rf"\bP{pid}\b", audit_block_text):
            errors.append(f"审计块未显式提及 P{pid}（须在段落表或准入过程中出现）")
    return len(errors) == 0, errors


def verify_step1_evidence(
    work: str,
    vol: str,
    skeleton_path: Path,
    paragraph_index: dict,
    *,
    spot_count: int = DEFAULT_SPOT_COUNT,
) -> Tuple[bool, str]:
    skeleton = json.loads(skeleton_path.read_text(encoding="utf-8"))
    ok, errs = verify_skeleton_spot_check(
        work, vol, skeleton, paragraph_index=paragraph_index, spot_count=spot_count
    )
    if ok:
        return True, f"原文挑战通过（{spot_count} 段抽样：归属 + 开篇原文字句）"
    return False, "Step1 原文挑战未通过：\n" + "\n".join(f"  - {e}" for e in errs)


def verify_step3_evidence(
    work: str,
    vol: str,
    skeleton: dict,
    audit_text: str,
    paragraph_index: dict,
    *,
    spot_count: int = DEFAULT_SPOT_COUNT,
) -> Tuple[bool, str]:
    blocks = split_volume_blocks(audit_text)
    block, issues = select_block_for_volume(blocks, vol, skeleton.get("volume", ""))
    all_errs = list(issues)
    if block is None:
        return False, "\n".join(all_errs)

    total = int(skeleton.get("total_paragraphs") or 0)
    spots = spot_paragraph_ids(work, vol, total, spot_count)

    _, table_errs = verify_audit_table_matches_skeleton(block.text, skeleton)
    all_errs.extend(table_errs)

    _, mention_errs = verify_audit_mentions_spots(block.text, spots)
    all_errs.extend(mention_errs)

    if all_errs:
        header = f"卷{vol.zfill(3)} Step3 证据门未通过："
        return False, header + "\n" + "\n".join(f"  - {e}" for e in all_errs)

    return True, f"审计表与 skeleton 一致；抽样段号 {spot_count} 处已显式提及"
