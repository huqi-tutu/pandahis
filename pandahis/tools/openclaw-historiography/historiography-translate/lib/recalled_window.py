"""分批翻译时的 recalled 原文窗口。

Phase1（母本顺译）：按本批 M 的「原文摘句」注入（可与段落分组展示），
与「按 M 分批」口径一致；禁止再按段落全文灌窗（否则批界落在段中会双写）。

Phase2（补全）：仍可用段落窗 ``build_batch_recalled_payload``（前后各 N 段上下文）。

成稿分段按叙事场景合段，禁止「一条 M → 一段」。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Sequence, Tuple

from lib.fingerprint import recalled_summary

_PARA_REF_RE = re.compile(r"P(\d+)\s*$", re.IGNORECASE)

ZONE_BEFORE = "context_before"
ZONE_MUST = "must_translate"
ZONE_AFTER = "context_after"

_WINDOW_INSTRUCTION = (
    "【原文窗口 · 硬约束】"
    "下方 blocks 中每段带 zone："
    f"`{ZONE_MUST}`=本批须翻译/须处理的原文；"
    f"`{ZONE_BEFORE}`/`{ZONE_AFTER}`=仅供理解上下文（指代、未完事件、勿在批末硬收束）。"
    f"**禁止**把 `{ZONE_BEFORE}`/`{ZONE_AFTER}` 的情节写入译文或「翻译详情」；"
    f"输出信息范围严格对应 `{ZONE_MUST}` 与本批 source_plan 清单。"
)


def context_radius() -> int:
    return max(0, int(os.environ.get("TRANSLATE_CONTEXT_PARAS", "3")))


def parse_paragraph_ids_from_checklist(items: Sequence[Dict[str, Any]]) -> List[int]:
    """按清单出现顺序去重提取段落号（如 … P5 → 5）。"""
    out: List[int] = []
    seen: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        m = _PARA_REF_RE.search(str(item.get("段落") or ""))
        if not m:
            continue
        pid = int(m.group(1))
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out


def flatten_mother_paragraphs(recalled: Dict[str, Any]) -> List[Dict[str, Any]]:
    """母本段落扁平序列（全书阅读顺序）。"""
    flat: List[Dict[str, Any]] = []
    for block in recalled.get("blocks") or []:
        if block.get("role") != "母本":
            continue
        meta = {
            "work": block.get("work"),
            "vol": block.get("vol"),
            "volume": block.get("volume"),
        }
        for para in block.get("paragraphs") or []:
            try:
                pid = int(para.get("id"))
            except (TypeError, ValueError):
                continue
            text = str(para.get("text") or "").strip()
            if not text:
                continue
            flat.append({**meta, "id": pid, "text": text})
    return flat


def _span_indices(flat: List[Dict[str, Any]], batch_pids: Sequence[int]) -> Tuple[int, int] | None:
    want = set(batch_pids)
    if not want or not flat:
        return None
    indices = [i for i, p in enumerate(flat) if int(p["id"]) in want]
    if not indices:
        return None
    return min(indices), max(indices)


def _zone_paragraphs(
    paras: List[Dict[str, Any]], zone: str
) -> List[Dict[str, Any]]:
    return [
        {
            "id": p["id"],
            "text": p["text"],
            "zone": zone,
            "work": p.get("work"),
            "vol": p.get("vol"),
            "volume": p.get("volume"),
        }
        for p in paras
    ]


def _group_into_blocks(
    zoned: List[Dict[str, Any]], *, role: str
) -> List[Dict[str, Any]]:
    """按 (zone, work, vol) 连续分组，便于阅读。"""
    if not zoned:
        return []
    blocks: List[Dict[str, Any]] = []
    cur_key: Tuple[Any, ...] | None = None
    cur_paras: List[Dict[str, Any]] = []
    cur_meta: Dict[str, Any] = {}

    def flush() -> None:
        nonlocal cur_paras, cur_meta, cur_key
        if not cur_paras:
            return
        ids = [int(p["id"]) for p in cur_paras]
        blocks.append(
            {
                "role": role,
                "zone": cur_paras[0]["zone"],
                "work": cur_meta.get("work"),
                "vol": cur_meta.get("vol"),
                "volume": cur_meta.get("volume"),
                "paragraph_from": min(ids),
                "paragraph_to": max(ids),
                "paragraph_count": len(cur_paras),
                "paragraphs": [
                    {"id": p["id"], "text": p["text"], "zone": p["zone"]}
                    for p in cur_paras
                ],
            }
        )
        cur_paras = []
        cur_key = None

    for p in zoned:
        key = (p["zone"], p.get("work"), p.get("vol"))
        if cur_key is None:
            cur_key = key
            cur_meta = {
                "work": p.get("work"),
                "vol": p.get("vol"),
                "volume": p.get("volume"),
            }
        elif key != cur_key:
            flush()
            cur_key = key
            cur_meta = {
                "work": p.get("work"),
                "vol": p.get("vol"),
                "volume": p.get("volume"),
            }
        cur_paras.append(p)
    flush()
    return blocks


def _supplement_blocks_in_window(
    recalled: Dict[str, Any], window_pids: set[int]
) -> List[Dict[str, Any]]:
    """窗口内相关的补充域（非整卷灌入）。"""
    if not window_pids:
        return []
    out: List[Dict[str, Any]] = []
    for block in recalled.get("blocks") or []:
        role = str(block.get("role") or "")
        if role == "母本":
            continue
        paras_in: List[Dict[str, Any]] = []
        for para in block.get("paragraphs") or []:
            try:
                pid = int(para.get("id"))
            except (TypeError, ValueError):
                continue
            if pid not in window_pids:
                continue
            text = str(para.get("text") or "").strip()
            if not text:
                continue
            # zone 由调用方按 must_pids 重标
            paras_in.append({"id": pid, "text": text, "zone": ZONE_BEFORE})
        if not paras_in:
            # 无逐段命中时：若 block 段号区间与窗口相交则整块带上
            try:
                pf = int(block.get("paragraph_from") or 0)
                pt = int(block.get("paragraph_to") or pf)
            except (TypeError, ValueError):
                continue
            if not window_pids.intersection(range(pf, pt + 1)):
                continue
            raw_paras = block.get("paragraphs") or []
            if not raw_paras:
                continue
            paras_in = [
                {
                    "id": p.get("id"),
                    "text": str(p.get("text") or ""),
                    "zone": ZONE_BEFORE,
                }
                for p in raw_paras
                if str(p.get("text") or "").strip()
            ]
        if not paras_in:
            continue
        out.append(
            {
                "role": role or "补充",
                "zone": "supplement_window",
                "work": block.get("work"),
                "vol": block.get("vol"),
                "volume": block.get("volume"),
                "paragraph_from": block.get("paragraph_from"),
                "paragraph_to": block.get("paragraph_to"),
                "paragraph_count": len(paras_in),
                "paragraphs": paras_in,
                "note": "补充域仅供本批锚点选用；禁止扩写为全传",
            }
        )
    return out


def build_batch_recalled_payload(
    recalled: Dict[str, Any],
    batch_items: Sequence[Dict[str, Any]],
    *,
    radius: int | None = None,
    include_supplements: bool = True,
) -> Dict[str, Any]:
    """构造带 zone 的 recalled 窗口；无法解析段落时回退全书摘要结构。"""
    r = context_radius() if radius is None else max(0, radius)
    flat = flatten_mother_paragraphs(recalled)
    batch_pids = parse_paragraph_ids_from_checklist(batch_items)
    span = _span_indices(flat, batch_pids)

    if span is None:
        # 无段落锚点：保持全书（短条/异常 plan），避免空输入
        fallback = json.loads(recalled_summary(recalled))
        fallback["window_mode"] = "full_fallback"
        fallback["window_instruction"] = (
            "未能从本批清单解析段落号，已提供全书 recalled；仍只按本批 source_plan 翻译。"
        )
        return fallback

    lo, hi = span
    before = flat[max(0, lo - r) : lo]
    must = flat[lo : hi + 1]
    after = flat[hi + 1 : hi + 1 + r]

    must_pids = {int(p["id"]) for p in must}
    # 补充：must 用 must_translate；落在前后文的用 context
    zoned_mother = (
        _zone_paragraphs(before, ZONE_BEFORE)
        + _zone_paragraphs(must, ZONE_MUST)
        + _zone_paragraphs(after, ZONE_AFTER)
    )
    blocks = _group_into_blocks(zoned_mother, role="母本")

    window_pids = {int(p["id"]) for p in before + must + after}
    if include_supplements:
        for sb in _supplement_blocks_in_window(recalled, window_pids):
            # 重标：段落 id 在 must → must_translate，否则 context_before
            fixed = []
            for p in sb.get("paragraphs") or []:
                try:
                    pid = int(p.get("id"))
                except (TypeError, ValueError):
                    fixed.append({**p, "zone": ZONE_BEFORE})
                    continue
                z = ZONE_MUST if pid in must_pids else (
                    ZONE_AFTER if after and pid >= int(after[0]["id"]) else ZONE_BEFORE
                )
                fixed.append({**p, "zone": z})
            sb = {**sb, "paragraphs": fixed}
            blocks.append(sb)

    return {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "window_mode": "batch_context",
        "window_instruction": _WINDOW_INSTRUCTION,
        "context_radius": r,
        "must_translate_paragraph_ids": sorted(must_pids),
        "context_before_paragraph_ids": [int(p["id"]) for p in before],
        "context_after_paragraph_ids": [int(p["id"]) for p in after],
        "block_count": len(blocks),
        "paragraph_count": len(zoned_mother),
        "blocks": blocks,
    }


def recalled_batch_window_json(
    recalled: Dict[str, Any],
    batch_items: Sequence[Dict[str, Any]],
    *,
    radius: int | None = None,
    include_supplements: bool = True,
) -> str:
    payload = build_batch_recalled_payload(
        recalled,
        batch_items,
        radius=radius,
        include_supplements=include_supplements,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


_M_WINDOW_INSTRUCTION = (
    "【原文窗口 · 按 M 句级 · 硬约束】"
    "本批只顺译 must_sentences / must_by_paragraph 中列出的「原文摘句」；"
    "禁止按段落全文翻译，禁止把同段未列入本批的邻句一并译出。"
    "成稿分段按叙事场景：同段/同事件的多条 M 须合写成连贯段落；"
    "**禁止「一条 M → 一个段落」**；也禁止把本批拆成一句一段的对照体。"
)


def _paragraph_id_from_item(item: Dict[str, Any]) -> int | None:
    para = str(item.get("段落") or "")
    m = _PARA_REF_RE.search(para.strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def build_mother_batch_m_payload(
    recalled: Dict[str, Any],
    batch_items: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Phase1 专用：按本批 M 注入原文摘句（按所属 P 分组），不再灌段落全文。

    分批以 M 为边界；原文窗口必须同口径，否则批界落在段中时整段进两批 → 情节双写。
    输出仍按叙事段合写，不要求「一条 M 一段」。
    """
    items = [it for it in batch_items if isinstance(it, dict) and it.get("编号")]
    if not items:
        raise ValueError("batch_items 为空，无法构建 M 句级原文窗口")

    must_sentences: List[Dict[str, Any]] = []
    for it in items:
        mid = str(it.get("编号") or "").strip()
        pid = _paragraph_id_from_item(it)
        must_sentences.append(
            {
                "编号": mid,
                "段落": str(it.get("段落") or "").strip(),
                "paragraph_id": pid,
                "原文摘句": str(it.get("原文摘句") or "").strip(),
                "引用粒度": str(it.get("引用粒度") or "").strip(),
                "经典引用候选": bool(it.get("经典引用候选")),
                "zone": "must_translate",
            }
        )

    must_m_ids = [r["编号"] for r in must_sentences if r["编号"]]

    # 按原文段落分组：提示模型同组合段，而非一句一段
    by_para: Dict[str, List[Dict[str, Any]]] = {}
    para_order: List[str] = []
    for row in must_sentences:
        pid = row.get("paragraph_id")
        key = f"P{pid}" if pid is not None else (row.get("段落") or "未知段")
        if key not in by_para:
            by_para[key] = []
            para_order.append(key)
        by_para[key].append(
            {
                "编号": row["编号"],
                "原文摘句": row["原文摘句"],
                "经典引用候选": row["经典引用候选"],
            }
        )

    must_by_paragraph = [
        {
            "段落键": key,
            "sentence_count": len(by_para[key]),
            "sentences": by_para[key],
            "合段提示": "本组多条 M 属同一原文段/连续场景，译文宜合写成连贯叙事段，禁止一条 M 一段。",
        }
        for key in para_order
    ]

    return {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "母本": recalled.get("母本"),
        "window_mode": "m_sentences",
        "window_instruction": _M_WINDOW_INSTRUCTION,
        "must_sentences": must_sentences,
        "must_by_paragraph": must_by_paragraph,
        "must_m_ids": must_m_ids,
        "must_m_count": len(must_m_ids),
        # 显式清空段落窗字段，防止下游误当成「整段 must」
        "must_translate": [],
        "context_before": [],
        "context_after": [],
        "must_translate_paragraph_ids": [],
        "context_before_paragraph_ids": [],
        "context_after_paragraph_ids": [],
        "blocks": [],
    }


def batch_window_guard_note(payload: Dict[str, Any] | None = None) -> str:
    """附加在 Phase1/Phase2 prompt 末尾的窗口纪律。"""
    if payload and payload.get("window_mode") == "m_sentences":
        must_m = payload.get("must_m_ids") or []
        groups = payload.get("must_by_paragraph") or []
        lines = [
            "",
            "---",
            "【原文窗口纪律 · 按 M 句级】",
            str(payload.get("window_instruction") or _M_WINDOW_INSTRUCTION),
        ]
        if must_m:
            preview = "、".join(must_m[:8])
            if len(must_m) > 8:
                preview += f"…共{len(must_m)}条"
            lines.append(f"本批 must_sentences：{preview}。")
        if groups:
            gdesc = "；".join(
                f"{g.get('段落键')}×{g.get('sentence_count')}句"
                for g in groups
                if isinstance(g, dict)
            )
            lines.append(f"按原文段分组：{gdesc}。同组合写，禁止一条 M 一段。")
        lines.append(
            "禁止整段灌译；未列入 must_sentences 的同段邻句一律不译。"
        )
        return "\n".join(lines) + "\n"

    must = []
    before = []
    after = []
    if payload:
        must = payload.get("must_translate_paragraph_ids") or []
        before = payload.get("context_before_paragraph_ids") or []
        after = payload.get("context_after_paragraph_ids") or []
    lines = [
        "",
        "---",
        "【原文窗口纪律】",
        _WINDOW_INSTRUCTION,
    ]
    if must:
        lines.append(
            "本批 must_translate 段："
            + "、".join(f"P{x}" for x in must)
            + "。"
        )
    if before or after:
        bits = []
        if before:
            bits.append("上文 " + "、".join(f"P{x}" for x in before))
        if after:
            bits.append("下文 " + "、".join(f"P{x}" for x in after))
        lines.append(
            "上下文（" + "；".join(bits) + "）只帮助衔接，"
            "不得译出、不得写成短版预告或重讲。"
        )
    return "\n".join(lines) + "\n"
