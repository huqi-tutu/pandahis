"""从召回结果构建产出 JSON 的「史料原文」字段。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from lib.source_citation import build_source_citation


def build_source_original_from_index_entry(entry: dict, data_root: Path | None = None) -> str:
    """从索引条目的 paragraphs 元数据 + 段落索引文件组装母本原文。"""
    root = data_root or Path(__file__).resolve().parents[3] / "data"
    para_dir = root / "03索引标注条目" / "段落索引"
    texts: List[str] = []
    for block in entry.get("paragraphs") or []:
        index_file = str(block.get("index_file") or "").replace("段落索引/", "")
        if not index_file:
            continue
        path = para_dir / index_file
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        para_map = {int(p["id"]): str(p.get("text") or "") for p in doc.get("paragraphs") or [] if p.get("id")}
        p_from = int(block.get("paragraph_from") or 0)
        p_to = int(block.get("paragraph_to") or p_from)
        for pn in range(p_from, p_to + 1):
            t = para_map.get(pn, "").strip()
            if t:
                texts.append(t)
    return "\n".join(texts)


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


def attach_source_original(
    output_file,
    recalled: Dict[str, Any],
    *,
    translation_version: str | None = None,
) -> None:
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
    if translation_version:
        data["翻译版本"] = translation_version
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def stamp_translation_version(output_file, translation_version: str) -> None:
    """为已落盘产出补写翻译版本（repair/legacy 路径）。"""
    path = Path(output_file)
    if not path.is_file() or not translation_version:
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("翻译版本") == translation_version:
        return
    data["翻译版本"] = translation_version
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
