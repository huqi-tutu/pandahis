"""母本锚点：统一 M 编号；P 锚仅在 plan 归一化阶段使用。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

_TAIL_RE = re.compile(r"\btail\b", re.I)


def m_id_to_num(m_id: str) -> int | None:
    m = re.search(r"M(\d+)", str(m_id or ""), re.I)
    return int(m.group(1)) if m else None


def extract_para_id(paragraph_field: str) -> int | None:
    m = re.search(r"\bP(\d+)\b", str(paragraph_field or ""), re.I)
    return int(m.group(1)) if m else None


def batch_m_numbers(batch_items: List[Dict[str, Any]]) -> Set[int]:
    out: Set[int] = set()
    for item in batch_items:
        n = m_id_to_num(str(item.get("编号") or ""))
        if n is not None:
            out.add(n)
    return out


def build_para_to_m_map(checklist: List[Dict[str, Any]]) -> Dict[int, List[int]]:
    """段落 P id → 该段内 M 编号列表（升序）。"""
    mapping: Dict[int, List[int]] = {}
    for item in checklist:
        if not isinstance(item, dict):
            continue
        pid = extract_para_id(str(item.get("段落") or ""))
        mid = m_id_to_num(str(item.get("编号") or ""))
        if pid is None or mid is None:
            continue
        mapping.setdefault(pid, []).append(mid)
    for pid in mapping:
        mapping[pid] = sorted(set(mapping[pid]))
    return mapping


def parse_anchor_m_refs(anchor: str) -> Set[int]:
    """解析锚点中的 M 编号（含 M001–M009 范围）。"""
    text = str(anchor or "")
    refs: Set[int] = set()
    for m in re.finditer(r"M(\d+)\s*[–—\-]\s*M(\d+)", text, re.I):
        lo, hi = int(m.group(1)), int(m.group(2))
        refs.update(range(min(lo, hi), max(lo, hi) + 1))
    for m in re.finditer(r"M(\d+)", text, re.I):
        refs.add(int(m.group(1)))
    return refs


def parse_anchor_p_refs(anchor: str) -> Set[int]:
    refs: Set[int] = set()
    text = str(anchor or "")
    for m in re.finditer(r"P(\d+)\s*[–—\-]\s*P(\d+)", text, re.I):
        lo, hi = int(m.group(1)), int(m.group(2))
        refs.update(range(min(lo, hi), max(lo, hi) + 1))
    for m in re.finditer(r"P(\d+)", text, re.I):
        refs.add(int(m.group(1)))
    return refs


def _anchor_position_hint(anchor: str) -> str:
    text = str(anchor or "")
    if re.search(r"前|之前", text):
        return "before"
    if re.search(r"后|之后", text):
        return "after"
    return "in"


def p_refs_to_m_refs(p_refs: Set[int], para_map: Dict[int, List[int]]) -> Set[int]:
    out: Set[int] = set()
    for pid in p_refs:
        ms = para_map.get(pid) or []
        out.update(ms)
    return out


def normalize_mother_anchor(
    anchor: str,
    checklist: List[Dict[str, Any]],
) -> str:
    """将 P 锚 / 混合锚归一为 M 锚语法（无法映射则原样返回）。"""
    raw = str(anchor or "").strip()
    if not raw or _TAIL_RE.search(raw):
        return raw

    para_map = build_para_to_m_map(checklist)
    m_refs = parse_anchor_m_refs(raw)
    p_refs = parse_anchor_p_refs(raw)

    if p_refs and para_map:
        p_ms = p_refs_to_m_refs(p_refs, para_map)
        if p_ms:
            pos = _anchor_position_hint(raw)
            lo, hi = min(p_ms), max(p_ms)
            if pos == "after":
                return f"M{hi:03d}后"
            if pos == "before":
                return f"M{lo:03d}前"
            if lo == hi:
                return f"M{lo:03d}"
            return f"M{lo:03d}–M{hi:03d}"

    if m_refs:
        pos = _anchor_position_hint(raw)
        lo, hi = min(m_refs), max(m_refs)
        if pos == "after" and len(m_refs) == 1:
            return f"M{lo:03d}后"
        if pos == "before" and len(m_refs) == 1:
            return f"M{lo:03d}前"
        if lo == hi:
            return f"M{lo:03d}"
        return f"M{lo:03d}–M{hi:03d}"

    return raw


def normalize_plan_mother_anchors(plan: Dict[str, Any]) -> None:
    """就地归一 plan 中所有母本锚点为 M 语法。"""
    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list):
        return

    for item in plan.get("外部补全") or []:
        if not isinstance(item, dict):
            continue
        for key in ("母本锚点", "初稿锚点"):
            if item.get(key):
                item[key] = normalize_mother_anchor(str(item[key]), checklist)

    for item in plan.get("索引补充处理") or []:
        if not isinstance(item, dict):
            continue
        for key in ("母本锚点", "锚点"):
            if item.get(key):
                item[key] = normalize_mother_anchor(str(item[key]), checklist)


def anchor_hits_batch(
    anchor: str,
    batch_nums: Set[int],
    *,
    checklist: List[Dict[str, Any]] | None = None,
    batch_index: int = 1,
    batch_total: int = 1,
) -> bool:
    """锚点是否应在本批成稿落地。"""
    raw = str(anchor or "").strip()
    if not raw:
        return False
    if _TAIL_RE.search(raw):
        return batch_index == batch_total

    refs = parse_anchor_m_refs(raw)
    if not refs and checklist:
        p_refs = parse_anchor_p_refs(raw)
        if p_refs:
            refs = p_refs_to_m_refs(p_refs, build_para_to_m_map(checklist))

    if not refs:
        return False
    return bool(refs & batch_nums)


def mother_para_ids_for_batch(batch_items: List[Dict[str, Any]]) -> Set[int]:
    ids: Set[int] = set()
    for item in batch_items:
        pid = extract_para_id(str(item.get("段落") or ""))
        if pid is not None:
            ids.add(pid)
    return ids
