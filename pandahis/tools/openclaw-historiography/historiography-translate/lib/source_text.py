"""从召回结果构建产出 JSON 的「史料原文」字段。"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from lib.source_citation import build_source_citation


def build_source_original(recalled: Dict[str, Any]) -> str:
    """
    构建「史料原文」：仅段落索引召回的母本与索引补充原文全文拼接，不含 LLM 外部补全。
    返回纯文本字符串。
    """
    texts: List[str] = []
    raw_blocks = recalled.get("blocks")

    if raw_blocks:
        for block in raw_blocks:
            role = str(block.get("role") or "母本")
            if role not in ("母本", "补充"):
                continue
            block_text = block.get("text") or ""
            if not block_text:
                paras = block.get("paragraphs") or []
                block_text = "\n".join(str(p.get("text") or "") for p in paras)
            if block_text.strip():
                texts.append(block_text)
    else:
        paras = recalled.get("paragraphs") or []
        if paras:
            full = recalled.get("text") or "\n".join(
                str(p.get("text") or "") for p in paras
            )
            if full.strip():
                texts.append(full)

    return "\n".join(texts)


def source_original_fingerprint(text: str) -> str:
    """用于 verify：对比召回与产出中的史料原文是否一致。"""
    return text


def attach_source_original(output_file, recalled: Dict[str, Any]) -> None:
    """将「史料原文」「原文出处」写入产出 JSON（编排器调用，不由 LLM 生成）。"""
    from pathlib import Path

    path = Path(output_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["史料原文"] = build_source_original(recalled)
    citation = build_source_citation(recalled)
    if citation:
        data["原文出处"] = citation
    else:
        data.pop("原文出处", None)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
