"""源文本指纹（幂等跳过）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def source_fingerprint(recalled: Dict[str, Any]) -> str:
    parts: list[str] = []
    for block in recalled.get("blocks") or []:
        work = block.get("work", "")
        vol = block.get("vol", "")
        role = block.get("role", "")
        for para in block.get("paragraphs") or []:
            parts.append(
                f"{role}|{work}|{vol}|{para.get('id')}|{para.get('text', '')}"
            )
    payload = "\n".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def output_fingerprint(data: Dict[str, Any]) -> str:
    detail = data.get("翻译详情") or ""
    eid = data.get("史略ID") or ""
    return hashlib.sha256(f"{eid}\n{detail}".encode("utf-8")).hexdigest()[:16]


def recalled_summary(recalled: Dict[str, Any], *, compact: bool = True) -> str:
    """召回摘要；compact=True 时不重复输出 block.text。"""
    blocks_out: List[Dict[str, Any]] = []
    for b in recalled.get("blocks") or []:
        item: Dict[str, Any] = {
            "role": b.get("role"),
            "work": b.get("work"),
            "vol": b.get("vol"),
            "volume": b.get("volume"),
            "paragraph_from": b.get("paragraph_from"),
            "paragraph_to": b.get("paragraph_to"),
            "paragraph_count": b.get("paragraph_count"),
            "paragraphs": [
                {"id": p.get("id"), "text": p.get("text")}
                for p in b.get("paragraphs") or []
            ],
        }
        if not compact:
            item["text"] = b.get("text")
        blocks_out.append(item)

    payload: Dict[str, Any] = {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "block_count": recalled.get("block_count"),
        "paragraph_count": recalled.get("paragraph_count"),
        "blocks": blocks_out,
    }
    chunk = recalled.get("_chunk")
    if chunk:
        payload["_chunk"] = chunk
    return json.dumps(payload, ensure_ascii=False, indent=2)


def recalled_summary_for_plan(recalled: Dict[str, Any], *, head_paras: int = 2) -> str:
    """长文 plan 用：只保留卷元数据 + 每块首尾段摘要，避免全文挤占输出预算。"""
    blocks_out: List[Dict[str, Any]] = []
    for b in recalled.get("blocks") or []:
        paras = [p for p in (b.get("paragraphs") or []) if isinstance(p, dict)]
        sample: List[Dict[str, Any]] = []
        for p in paras[:head_paras]:
            text = str(p.get("text") or "")
            sample.append({"id": p.get("id"), "text": text[:120] + ("…" if len(text) > 120 else "")})
        if len(paras) > head_paras * 2:
            sample.append({"id": "…", "text": f"（中间省略 {len(paras) - head_paras * 2} 段）"})
        for p in paras[-head_paras:] if len(paras) > head_paras else []:
            if sample and sample[-1].get("id") == p.get("id"):
                continue
            text = str(p.get("text") or "")
            sample.append({"id": p.get("id"), "text": text[:120] + ("…" if len(text) > 120 else "")})
        blocks_out.append(
            {
                "role": b.get("role"),
                "work": b.get("work"),
                "vol": b.get("vol"),
                "volume": b.get("volume"),
                "paragraph_from": b.get("paragraph_from"),
                "paragraph_to": b.get("paragraph_to"),
                "paragraph_count": b.get("paragraph_count") or len(paras),
                "paragraphs_sample": sample,
            }
        )
    payload: Dict[str, Any] = {
        "史略ID": recalled.get("史略ID"),
        "史略名称": recalled.get("史略名称"),
        "母本著作": recalled.get("母本著作"),
        "block_count": recalled.get("block_count"),
        "paragraph_count": recalled.get("paragraph_count"),
        "blocks": blocks_out,
        "_note": "长文 plan 压缩召回：完整原文在 Phase1/2 按批注入；此处只供跨书选题",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
