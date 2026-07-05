"""从召回结果构建产出 JSON 的「史料原文」字段。"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def _block_payload(block: Dict[str, Any], *, default_role: str = "母本") -> Dict[str, Any]:
    paras = block.get("paragraphs") or []
    joined = block.get("text") or "\n".join(
        str(p.get("text") or "") for p in paras
    )
    return {
        "role": block.get("role") or default_role,
        "work": block.get("work") or "",
        "vol": block.get("vol") or "",
        "volume": block.get("volume") or "",
        "source_file": block.get("source_file") or "",
        "paragraph_from": block.get("paragraph_from"),
        "paragraph_to": block.get("paragraph_to"),
        "paragraphs": [
            {"id": p.get("id"), "text": p.get("text") or ""}
            for p in paras
        ],
        "text": joined,
    }


def build_source_original(recalled: Dict[str, Any]) -> Dict[str, Any]:
    """
    构建「史料原文」：仅段落索引召回的母本与索引补充，不含 LLM 外部补全。
    """
    blocks_out: List[Dict[str, Any]] = []
    raw_blocks = recalled.get("blocks")

    if raw_blocks:
        for block in raw_blocks:
            role = str(block.get("role") or "母本")
            if role not in ("母本", "补充"):
                continue
            blocks_out.append(_block_payload(block))
    else:
        paras = recalled.get("paragraphs") or []
        if paras:
            blocks_out.append(
                {
                    "role": "母本",
                    "work": recalled.get("work") or "",
                    "vol": recalled.get("vol") or "",
                    "volume": recalled.get("volume") or "",
                    "source_file": recalled.get("source_file") or "",
                    "paragraph_from": recalled.get("paragraph_from"),
                    "paragraph_to": recalled.get("paragraph_to"),
                    "paragraphs": [
                        {"id": p.get("id"), "text": p.get("text") or ""}
                        for p in paras
                    ],
                    "text": recalled.get("text")
                    or "\n".join(str(p.get("text") or "") for p in paras),
                }
            )

    full_text = "\n".join(
        b.get("text") or "" for b in blocks_out if (b.get("text") or "").strip()
    )
    return {
        "说明": "段落索引召回原文；不含模型外部补全",
        "blocks": blocks_out,
        "text": full_text,
    }


def source_original_fingerprint(source_original: Dict[str, Any]) -> str:
    """用于 verify：对比召回与产出中的史料原文是否一致。"""
    return json.dumps(source_original, ensure_ascii=False, sort_keys=True)


def attach_source_original(output_file, recalled: Dict[str, Any]) -> None:
    """将「史料原文」写入产出 JSON（编排器调用，不由 LLM 生成）。"""
    from pathlib import Path

    path = Path(output_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["史料原文"] = build_source_original(recalled)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
