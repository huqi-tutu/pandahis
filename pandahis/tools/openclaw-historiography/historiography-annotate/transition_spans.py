"""过渡段落子句切分：退场/即位句归属校验（标注与翻译共用）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# 退场：X崩/薨/卒（可含葬地）
_EXIT_SENT_RE = re.compile(
    r"^[^。；]*?(?P<who>[\u4e00-\u9fff]{1,6})(?P<verb>崩|薨|卒)[^。；]*(?:葬[^。；]*)?[。；]?$"
)
# 即位：是为帝Y / Y立
_ACCESSION_SENT_RE = re.compile(
    r"(?:是为|乃为|是为帝|立，是为)(?P<who>[\u4e00-\u9fff]{1,6})"
)


def split_sentences(text: str) -> List[str]:
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
        parts.append(tail if tail.endswith("。") else tail + "。")
    return parts if parts else [text.strip()]


def _normalize_name(name: str) -> str:
    n = (name or "").strip()
    for prefix in ("帝", "王", "公", "侯"):
        if n.startswith(prefix) and len(n) > 1:
            return n[len(prefix) :]
    return n


def _names_match(a: str, b: str) -> bool:
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def classify_sentence(sentence: str, subject: str) -> str:
    """返回 span_type: subject | foreign_exit | foreign_accession | neutral."""
    s = sentence.strip()
    if not s:
        return "neutral"

    m_exit = _EXIT_SENT_RE.match(s)
    if m_exit:
        who = m_exit.group("who")
        if _names_match(who, subject):
            return "subject"
        return "foreign_exit"

    m_acc = _ACCESSION_SENT_RE.search(s)
    if m_acc:
        who = m_acc.group("who")
        if _names_match(who, subject):
            return "subject"
        if not _names_match(who, subject):
            return "foreign_accession"

    if subject and subject in s:
        return "subject"
    return "neutral"


def split_paragraph_spans(text: str, subject: str) -> List[Dict[str, str]]:
    return [
        {"text": s, "span_type": classify_sentence(s, subject), "owner": subject}
        for s in split_sentences(text)
    ]


def filter_text_for_subject(text: str, subject: str) -> Tuple[str, List[Dict[str, str]]]:
    """保留本传主相关子句；foreign_exit 抽出供跨条补全。"""
    kept: List[str] = []
    foreign_exits: List[Dict[str, str]] = []
    for span in split_paragraph_spans(text, subject):
        st = span["span_type"]
        if st == "foreign_exit":
            foreign_exits.append(span)
            continue
        if st in ("subject", "neutral", "foreign_accession"):
            kept.append(span["text"])
    return "".join(kept), foreign_exits


def find_exit_events_in_text(text: str, expected_subject: str) -> List[str]:
    """找出文本中属于 expected_subject 的退场句。"""
    found: List[str] = []
    for s in split_sentences(text):
        m = _EXIT_SENT_RE.match(s.strip())
        if m and _names_match(m.group("who"), expected_subject):
            found.append(s.strip())
    return found


def validate_entry_exit_attribution(entry: Dict[str, Any]) -> List[str]:
    """标注 gate：本传主退场句不应只出现在他人条目。"""
    errors: List[str] = []
    name = str(entry.get("史略名称") or entry.get("四级帝王坐标") or "").strip()
    if not name or str(entry.get("史略分类") or "") != "君王":
        return errors

    orig = str(entry.get("原文字句") or "").strip()
    if not orig:
        return errors

    # 本条目应含自己的退场（若母本有）；若含他人退场展开则警告
    for s in split_sentences(orig):
        m = _EXIT_SENT_RE.match(s.strip())
        if not m:
            continue
        who = m.group("who")
        if not _names_match(who, name):
            errors.append(
                f"退场句「{s[:24]}…」主角为{who}，不应作为{name}条目的母本开篇"
            )
    return errors


def apply_recall_subject_filter(recalled: Dict[str, Any]) -> Dict[str, Any]:
    """翻译召回后：按传主过滤过渡句，并记录缺漏退场。"""
    subject = str(recalled.get("史略名称") or "").strip()
    if not subject:
        return recalled

    out = dict(recalled)
    blocks: List[Dict[str, Any]] = []
    missing_exits: List[Dict[str, str]] = []

    for block in recalled.get("blocks") or []:
        nb = dict(block)
        new_paras: List[Dict[str, Any]] = []
        filtered_texts: List[str] = []
        for para in block.get("paragraphs") or []:
            text = str(para.get("text") or "")
            filtered, foreign = filter_text_for_subject(text, subject)
            for fe in foreign:
                missing_exits.append(
                    {
                        "text": fe["text"],
                        "来源段": f"P{para.get('id')}",
                        "归属": _EXIT_SENT_RE.match(fe["text"].strip()).group("who")
                        if _EXIT_SENT_RE.match(fe["text"].strip())
                        else "",
                    }
                )
            if filtered.strip():
                new_paras.append({**para, "text": filtered.strip()})
                filtered_texts.append(filtered.strip())
        nb["paragraphs"] = new_paras
        nb["text"] = "\n".join(filtered_texts)
        if new_paras:
            blocks.append(nb)

    out["blocks"] = blocks
    out["text"] = "\n".join(
        b.get("text", "") for b in blocks if b.get("text")
    )
    if missing_exits:
        out["_filtered_foreign_exits"] = missing_exits
    return out


def inject_exit_supplements(
    recalled: Dict[str, Any],
    *,
    index_entries: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """若本传主母本缺退场句，从全索引相邻条目或同卷过渡段补入。"""
    subject = str(recalled.get("史略名称") or "").strip()
    if not subject:
        return recalled

    mother_text = ""
    for block in recalled.get("blocks") or []:
        if block.get("role") == "母本":
            mother_text += str(block.get("text") or "")

    if find_exit_events_in_text(mother_text, subject):
        return recalled

    supplements: List[Dict[str, str]] = []

    # 1) 同卷过渡段：从其他条目原文字句中提取本传主退场句
    if index_entries:
        for entry in index_entries:
            orig = str(entry.get("原文字句") or "")
            for sent in find_exit_events_in_text(orig, subject):
                if sent not in mother_text:
                    supplements.append(
                        {
                            "text": sent,
                            "来源": f"{entry.get('史略ID')}·过渡段",
                            "插入位置": "tail",
                        }
                    )

    # 2) 召回过滤时剥离的外人退场（供交叉补全，不写入本条目）
    # 本传主条目只采纳 who==subject 的退场句

    if not supplements:
        return recalled

    # 去重
    seen: set[str] = set()
    deduped: List[Dict[str, str]] = []
    for s in supplements:
        t = s["text"]
        if t not in seen:
            seen.add(t)
            deduped.append(s)

    out = dict(recalled)
    out["本传缺漏补全"] = deduped
    return out
