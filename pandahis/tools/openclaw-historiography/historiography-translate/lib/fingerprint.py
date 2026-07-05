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
