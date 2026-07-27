"""从 recalled 母本 block 抽取逐句清单基准。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from lib.gloss_rules import L0_GLOSS_WORDS, is_l0_word

MAX_MUST_PHRASES = 4
# 必现词字数：只抽 1–3 字短锚点（4 字易成硬锚点误拦白话意译）；氏名 ≤5
MIN_MUST_CHAR = 1
MAX_MUST_CHAR = 3
MAX_MUST_CHAR_CLAN = 5  # X氏专名例外


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
    if len(p) < MIN_MUST_CHAR:
        return True
    # 单字不做「词中截断」判定，交由 L0/虚词过滤
    if len(p) == 1:
        return False
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


def _trim_l0_edges(phrase: str) -> str:
    """去掉短语首尾的单字 L0 通识文言（如「康王卒」→「康王」）。"""
    w = phrase.strip()
    if not w or is_l0_word(w):
        return ""
    changed = True
    while changed and len(w) >= 2:
        changed = False
        if len(w) > 2 and w[-1] in L0_GLOSS_WORDS:
            w = w[:-1]
            changed = True
        if len(w) > 2 and w[0] in L0_GLOSS_WORDS:
            w = w[1:]
            changed = True
    return w.strip()


def _iter_clan_names(text: str) -> List[str]:
    """提取 X氏 专名（2–4 字 + 氏，总长 ≤ MAX_MUST_CHAR_CLAN），避免贪婪正则吞整句。"""
    found: List[str] = []
    seen: set[str] = set()
    for i, ch in enumerate(text):
        if ch != "氏":
            continue
        for n in range(3, MAX_MUST_CHAR_CLAN + 1):
            start = i - n + 1
            if start < 0:
                continue
            phrase = text[start : i + 1]
            if len(phrase) != n or phrase[-1] != "氏":
                continue
            if not all("\u4e00" <= c <= "\u9fff" for c in phrase):
                continue
            if phrase not in seen:
                seen.add(phrase)
                found.append(phrase)
            break
    return found


def _max_len_for(phrase: str) -> int:
    return MAX_MUST_CHAR_CLAN if phrase.endswith("氏") else MAX_MUST_CHAR


def _within_must_length(phrase: str) -> bool:
    w = phrase.strip()
    return len(w) >= MIN_MUST_CHAR and len(w) <= _max_len_for(w)


def _reject_must_phrase(phrase: str, orig: str, *, clause_level: bool = False) -> bool:
    """True = 不应作为必现词。"""
    w = phrase.strip()
    if len(w) < MIN_MUST_CHAR:
        return True
    if not _within_must_length(w):
        return True
    if is_l0_word(w):
        return True
    if w in _MUST_STOP or w in _MUST_GENERIC:
        return True
    if not clause_level and is_midword_fragment(w, orig):
        return True
    return False


def extract_must_phrases(orig: str, *, max_phrases: int = MAX_MUST_PHRASES) -> List[str]:
    """从母本摘句程序化提取短锚点（1–3 字，氏名 ≤5）；落盘覆盖 LLM 填写。"""
    out: List[str] = []
    seen: set[str] = set()

    def _add(raw: str, *, clause_level: bool = False, allow_kernels: bool = True) -> None:
        if len(out) >= max_phrases:
            return
        w = _trim_l0_edges(raw)
        w = re.sub(r"[。．\.、，；：！？!?\s\"\"''「」『』“”]", "", w)
        if not w:
            return
        # 必须是原文连续子串（数字除外），避免「国属害」这类截断碎片
        if not re.fullmatch(r"\d+", w):
            orig_plain = _plain_text(orig)
            if w not in orig_plain:
                if allow_kernels and len(raw.strip()) > MAX_MUST_CHAR:
                    _add_kernels_from_segment(raw)
                return
        if not _within_must_length(w):
            if allow_kernels:
                _add_kernels_from_segment(raw)
            return
        if _reject_must_phrase(w, orig, clause_level=clause_level):
            return
        if w not in seen:
            seen.add(w)
            out.append(w)

    def _add_kernels_from_segment(segment: str) -> None:
        """长分句块不整段入选，只抽数字/氏/称号/≤3 字子片段。"""
        for num in re.findall(r"\d+", segment):
            _add(num, allow_kernels=False)
        for clan in _iter_clan_names(segment):
            _add(clan, clause_level=True, allow_kernels=False)
        for m in re.finditer(
            r"[\u4e00-\u9fff]{1,3}(?:公|侯|王|伯|子|尚|挚)",
            segment,
        ):
            _add(m.group(0), clause_level=True, allow_kernels=False)
        for part in re.split(r"[、；]", segment):
            part = re.sub(r"[之乎者也矣焉]", "", part.strip())
            if not part:
                continue
            trimmed = _trim_l0_edges(part)
            if MIN_MUST_CHAR <= len(trimmed) <= MAX_MUST_CHAR and (
                len(trimmed) == 1 or trimmed[0] not in "於于之其而"
            ):
                _add(part, clause_level=True, allow_kernels=False)

    for num in re.findall(r"\d+", orig):
        _add(num, allow_kernels=False)
    for clan in _iter_clan_names(orig):
        _add(clan, clause_level=True, allow_kernels=False)
    for m in re.finditer(r"[「『\"“]([^」』\"”]{2,16})[」』\"”]", orig):
        inner = m.group(1).strip()
        trimmed_inner = _trim_l0_edges(inner)
        if _within_must_length(trimmed_inner):
            _add(inner, clause_level=True, allow_kernels=False)
        else:
            _add_kernels_from_segment(inner)
            for part in re.split(r"[，、；]", inner):
                _add(part, clause_level=True, allow_kernels=False)
    for m in re.finditer(
        r"[\u4e00-\u9fff]{1,3}(?:公|侯|王|伯|子|尚|挚)",
        orig,
    ):
        _add(m.group(0), clause_level=True, allow_kernels=False)
    for chunk in re.split(r"[，。、；：]", orig):
        chunk = re.sub(r"[之乎者也矣焉]", "", chunk.strip())
        if len(chunk) < 2:
            continue
        trimmed = _trim_l0_edges(chunk)
        if MIN_MUST_CHAR <= len(trimmed) <= MAX_MUST_CHAR and (
            len(trimmed) == 1 or trimmed[0] not in "於于之其而"
        ):
            _add(chunk, clause_level=True, allow_kernels=False)
        else:
            _add_kernels_from_segment(chunk)
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
