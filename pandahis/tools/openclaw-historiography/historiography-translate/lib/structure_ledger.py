"""结构账本：把母本段落变成不可打乱的事件链（S001→S…）。

程序从 Phase1 母本段落生成，供 Phase2 注入与顺序/覆盖门禁。
不替代 mother_span 漏段检测；补的是「顺序锁 + 回合身份」。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from lib.mother_span import analyze_mother_spans, strip_reference_section


@dataclass(frozen=True)
class StructureSegment:
    id: str
    span_index: int
    anchors: Tuple[str, ...]
    event_preview: str
    sequence_lock: int
    event_key: str
    occurrence: int


def _preview(text: str, *, limit: int = 36) -> str:
    s = re.sub(r"\s+", " ", str(text or "").strip())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _event_key(anchors: Sequence[str], preview: str) -> str:
    base = "／".join(anchors[:3]) if anchors else preview[:24]
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    label = re.sub(r"[^\w\u4e00-\u9fff]+", "", base)[:18] or "seg"
    return f"{label}-{digest}"


def build_structure_ledger(
    mother: str,
    source_original: str = "",
    *,
    max_segments: int = 220,
) -> List[StructureSegment]:
    """按母本 ``\\n\\n`` 段落生成结构单元（仅含有专名锚点的段进账本）。"""
    spans = analyze_mother_spans(mother, source_original)
    keyed: List[StructureSegment] = []
    occ_count: Dict[str, int] = {}
    seq = 0
    for sp in spans:
        if not sp.primaries and not sp.names:
            continue
        seq += 1
        if seq > max_segments:
            break
        anchors = tuple(list(sp.primaries[:4]) or list(sp.names[:3]))
        preview = _preview(sp.text)
        key = _event_key(anchors, preview)
        occ = occ_count.get(key, 0) + 1
        occ_count[key] = occ
        keyed.append(
            StructureSegment(
                id=f"S{seq:03d}",
                span_index=sp.index,
                anchors=anchors,
                event_preview=preview,
                sequence_lock=seq,
                event_key=key,
                occurrence=occ,
            )
        )
    return keyed


def format_structure_ledger(
    mother: str,
    source_original: str = "",
    *,
    max_segments: int = 180,
) -> str:
    all_segs = build_structure_ledger(
        mother, source_original, max_segments=max(max_segments, 10_000)
    )
    segs = all_segs[:max_segments]
    lines = [
        "结构账本（顺序锁：须按 S001→S… 推进；可改写措辞，禁止跳号重排或整段删情节）：",
    ]
    for seg in segs:
        anchors = "／".join(seg.anchors) if seg.anchors else "（弱锚点）"
        occ = f" · 第{seg.occurrence}次" if seg.occurrence > 1 else ""
        lines.append(
            f"{seg.id} [lock={seg.sequence_lock}] {anchors}{occ}｜{seg.event_preview}"
        )
    if len(all_segs) > max_segments:
        lines.append(
            f"…共 {len(all_segs)} 个结构单元（上表截断至 {max_segments}）"
        )
    return "\n".join(lines)


def structure_order_warnings(
    detail: str,
    mother: str,
    source_original: str = "",
) -> List[str]:
    """软检：成稿中锚点首次出现顺序相对结构账本是否明显倒挂。

    仅作警告线索，不单独硬失败（漏段仍由 mother_span 硬拦）。
    """
    segs = build_structure_ledger(mother, source_original)
    body = strip_reference_section(detail)
    if not segs or len(body) < 80:
        return []
    positions: List[Tuple[str, int, str]] = []
    for seg in segs:
        pos = -1
        hit = ""
        for a in seg.anchors:
            if len(a) < 2:
                continue
            i = body.find(a)
            if i >= 0 and (pos < 0 or i < pos):
                pos = i
                hit = a
        if pos >= 0:
            positions.append((seg.id, pos, hit))
    inversions = 0
    samples: List[str] = []
    for i in range(1, len(positions)):
        prev_id, prev_pos, _ = positions[i - 1]
        cur_id, cur_pos, hit = positions[i]
        if cur_pos + 20 < prev_pos:
            inversions += 1
            if len(samples) < 4:
                samples.append(f"{prev_id}→{cur_id}（锚点「{hit}」偏前）")
    if inversions >= 3:
        return [
            "结构顺序疑似倒挂 "
            + f"（≥{inversions} 处；例：{'；'.join(samples)}）。"
            + "须按结构账本 S 序推进，禁止为流畅重排事件。"
        ]
    return []
