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
    "黄帝轩辕神农尧舜禹启汤文武诸侯百姓万民天下天子帝王"
    "公侯伯子男君王后妃太子太师太傅太保大夫将军大臣国人君子小人".split()
)
_BOUNDARY_PUNCT = frozenset("，。、；：！？,")


def _plain_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_midword_fragment(phrase: str, orig: str) -> bool:
    """短语是否为原文中间截断的 n-gram 碎片（首尾未落在句读边界）。"""
    p = str(phrase).strip()
    if len(p) < 2:
        return True
    orig_plain = _plain_text(orig)
    if p not in orig_plain:
        return False
    idx = 0
    while True:
        pos = orig_plain.find(p, idx)
        if pos < 0:
            return True
        start_ok = pos == 0 or orig_plain[pos - 1] in _BOUNDARY_PUNCT
        end_pos = pos + len(p)
        end_ok = end_pos == len(orig_plain) or orig_plain[end_pos] in _BOUNDARY_PUNCT
        if start_ok and end_ok:
            return False
        idx = pos + 1


def extract_must_phrases(orig: str, *, max_phrases: int = 4) -> List[str]:
    """从母本摘句提取硬锚点：数字、引号内原文、X氏专名、句读边界短语。上限降为4，减少冗余锚点。"""
    out: List[str] = []
    seen: set[str] = set()

    def _add(w: str) -> None:
        w = w.strip()
        if len(w) < 2 or w in _MUST_STOP or w in _MUST_GENERIC:
            return
        if is_midword_fragment(w, orig):
            return
        if w not in seen:
            seen.add(w)
            out.append(w)

    for num in re.findall(r"\d+", orig):
        _add(num)
    for m in re.finditer(r"[\u4e00-\u9fff]{2,8}氏", orig):
        _add(m.group(0))
    for m in re.finditer(r"[「『\"“]([^」』\"”]{2,16})[」』\"”]", orig):
        _add(m.group(1))
    for m in re.finditer(
        r"[\u4e00-\u9fff]{2,6}(?:公|侯|王|伯|子|尚|挚)",
        orig,
    ):
        _add(m.group(0))
    for chunk in re.split(r"[，。、；：]", orig):
        chunk = re.sub(r"[之乎者也矣焉]", "", chunk.strip())
        if 2 <= len(chunk) <= 12:
            _add(chunk)
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
