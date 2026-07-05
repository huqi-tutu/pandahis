"""从 recalled 母本 block 抽取逐句清单基准。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List


def _split_sentences(text: str) -> List[str]:
    """按句号分句；引号/对话内的 。不拆分。"""
    parts: List[str] = []
    buf: List[str] = []
    in_quote = False
    for ch in text:
        buf.append(ch)
        if ch in "“\"「":
            in_quote = True
        elif ch in "”\"」":
            in_quote = False
        if ch == "。" and not in_quote:
            seg = "".join(buf).strip()
            if seg:
                parts.append(seg)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts if parts else [text.strip()]


def extract_mother_sentences(recalled: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按句号分句（引号内不拆）；保留段落锚点。"""
    out: List[Dict[str, Any]] = []
    idx = 0
    for block in recalled.get("blocks") or []:
        if block.get("role") != "母本":
            continue
        work = str(block.get("work") or "")
        vol = str(block.get("vol") or "")
        volume = str(block.get("volume") or "")
        for para in block.get("paragraphs") or []:
            pid = para.get("id")
            text = str(para.get("text") or "").strip()
            if not text:
                continue
            parts = _split_sentences(text)
            for part in parts:
                idx += 1
                out.append(
                    {
                        "序号": idx,
                        "段落": f"{work} 卷{vol} {volume} P{pid}",
                        "原文摘句": part,
                    }
                )
    return out


def mother_sentence_count(recalled: Dict[str, Any]) -> int:
    sents = extract_mother_sentences(recalled)
    return max(len(sents), 1)


def plan_min_sentence_ratio() -> float:
    return float(os.environ.get("TRANSLATE_PLAN_MIN_RATIO", "0.95"))


# 母本摘句中应保留的原词锚点（verify / plan 必现词）
_MUST_STOP = frozenset(
    "之乎者也矣焉於于以而则乃若其吾汝尔彼此何谁孰哉兮耶欤耳盖夫且尚又及与为在是有非无已于是然后".split()
)
_MUST_GENERIC = frozenset(
    "黄帝轩辕神农尧舜禹启汤文武诸侯百姓万民天下天子帝王".split()
)


def extract_must_phrases(orig: str, *, max_phrases: int = 6) -> List[str]:
    """从母本摘句提取硬锚点：数字、引号内原文、X氏专名、原文连续片段。"""
    out: List[str] = []
    seen: set[str] = set()

    def _add(w: str) -> None:
        w = w.strip()
        if len(w) < 2 or w in _MUST_STOP or w in _MUST_GENERIC:
            return
        if w not in seen:
            seen.add(w)
            out.append(w)

    for num in re.findall(r"\d+", orig):
        _add(num)
    for m in re.finditer(r"[\u4e00-\u9fff]{2,8}氏", orig):
        _add(m.group(0))
    for m in re.finditer(r"[「『\"]([^」』\"]{2,12})[」』\"]", orig):
        _add(m.group(1))
    for m in re.finditer(r"[\u4e00-\u9fff]{3,6}", orig):
        seg = m.group(0)
        if any(seg in x for x in seen):
            continue
        _add(seg)
    if len(out) < max_phrases:
        for chunk in re.split(r"[，。、；：]", orig):
            chunk = chunk.strip()
            if 2 <= len(chunk) <= 4:
                _add(re.sub(r"[之乎者也矣焉]", "", chunk))
    return out[:max_phrases]


def checklist_sentence_violations(checklist: List[Dict[str, Any]]) -> List[str]:
    """每条清单的「原文摘句」只能含一个句号级分句（与 _split_sentences 一致，引号内 。不计）。"""
    errors: List[str] = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("编号") or item.get("id") or "?")
        orig = str(item.get("原文摘句") or item.get("text") or "").strip()
        if not orig:
            errors.append(f"{sid} 缺少「原文摘句」")
            continue
        parts = _split_sentences(orig)
        if len(parts) > 1:
            errors.append(
                f"{sid} 合并了 {len(parts)} 条母本句，须拆成独立编号（{orig[:40]}…）"
            )
    return errors
