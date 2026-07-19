"""从索引召回结果提取「原文出处」（母本著作 · 典籍卷名）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# 01史记_001_五帝本纪第一.txt → 五帝本纪
_SOURCE_FILE_RE = re.compile(r"^\d{2}[^_]+_\d{3}_(.+)\.txt$", re.IGNORECASE)
# 去掉典籍卷名末尾的次序号：五帝本纪第一 → 五帝本纪；卷一百下 → 卷一百（极少见）
_ORDINAL_SUFFIX_RE = re.compile(r"第[一二三四五六七八九十百千零〇两]+(?:上|下)?$")


def native_volume_from_source_file(source_file: str) -> str:
    """
    从拆分原文文件名提取典籍篇名（不含「第X」次序），
    不用排序用的「卷001 / 卷一」。
    """
    name = Path(str(source_file or "").strip()).name
    m = _SOURCE_FILE_RE.match(name)
    if not m:
        return ""
    title = (m.group(1) or "").strip()
    return _strip_volume_ordinal(title)


def _strip_volume_ordinal(title: str) -> str:
    title = str(title or "").strip()
    if not title:
        return ""
    return _ORDINAL_SUFFIX_RE.sub("", title).strip() or title


def display_work_name(work: str) -> str:
    """01史记 → 史记"""
    work = str(work or "").strip()
    if not work:
        return ""
    i = 0
    while i < len(work) and work[i].isdigit():
        i += 1
    return work[i:] or work


def build_source_citation(recalled: Dict[str, Any]) -> str:
    """
    母本出处，供产出字段「原文出处」与小程序浮层展示。

    格式：《著作篇名》，如《史记五帝本纪》（无中间点、无「第X」次序号）。
    典籍卷名取自母本 block/paragraph 的 source_file，
    **不用**索引「主要史料出处」里为排序加的「卷一 / 卷61」。
    注意：索引字段「原文出处」是段落锚点（如 五帝本纪·P1-P8），不得误用。
    """
    parent_work = str(recalled.get("母本著作") or "").strip()

    for block in recalled.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        if str(block.get("role") or "母本") != "母本":
            continue
        cite = _cite_from_block(block, parent_work)
        if cite:
            return cite

    for p in recalled.get("paragraphs") or []:
        if not isinstance(p, dict):
            continue
        if str(p.get("role") or "母本") != "母本":
            continue
        cite = _cite_from_block(p, parent_work)
        if cite:
            return cite

    # 无母本标记时：取首个带 source_file 的 block/paragraph
    for block in list(recalled.get("blocks") or []) + list(recalled.get("paragraphs") or []):
        if not isinstance(block, dict):
            continue
        cite = _cite_from_block(block, parent_work)
        if cite:
            return cite

    return ""


def _cite_from_block(block: Dict[str, Any], parent_work: str) -> str:
    work = display_work_name(str(block.get("work") or parent_work).strip())
    native = native_volume_from_source_file(str(block.get("source_file") or ""))
    if not native:
        # 回退：仅有简写 volume（无「第X」）时仍可用
        native = str(block.get("volume") or "").strip()
    if work and native:
        return f"《{work}{native}》"
    if native:
        return f"《{native}》"
    if work:
        return f"《{work}》"
    return ""


def mother_source_file(recalled: Dict[str, Any]) -> Optional[str]:
    """调试/校验用：返回母本 source_file。"""
    for block in list(recalled.get("blocks") or []) + list(recalled.get("paragraphs") or []):
        if not isinstance(block, dict):
            continue
        if str(block.get("role") or "母本") != "母本":
            continue
        sf = str(block.get("source_file") or "").strip()
        if sf:
            return sf
    return None
