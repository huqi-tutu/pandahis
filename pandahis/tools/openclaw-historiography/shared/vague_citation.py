"""模糊出处检测：禁止无典籍锚点的「据说/相传」等；同句含《》书名则允许。"""

from __future__ import annotations

import re

# 触发词（出现即检查同句是否有《》）
# 传说/相传/据说 改由 shared/legend_quota.py 检主次，不在此拦
VAGUE_CITATION_TRIGGERS: tuple[str, ...] = (
    "有人说",
    "有资料说",
    "历史上认为",
    "一般认为",
    "后世认为",
    "有观点认为",
)

# 固定搭配：其中的「相传/传说」不视为模糊出处（保留供其他模块引用）
VAGUE_CITATION_COMPOUND_OK: tuple[str, ...] = (
    "口耳相传",
    "口传相传",
    "神话传说",
    "民间传说",
    "后世传说",
    "传说时代",
)

_BOOK_TITLE = re.compile(r"《[^》]+》")


def _strip_refs_section(text: str) -> str:
    for marker in ("*参考著作*", "参考著作"):
        if marker in text:
            return text.split(marker, 1)[0]
    return text


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？\n])", text)
    return [p for p in parts if p.strip()]


def _trigger_active_in_sentence(sentence: str, trigger: str) -> bool:
    if trigger not in sentence:
        return False
    if trigger not in ("据说", "相传", "传说"):
        return True
    scratch = sentence
    for phrase in VAGUE_CITATION_COMPOUND_OK:
        scratch = scratch.replace(phrase, "")
    return trigger in scratch


def detect_unanchored_vague_citations(text: str) -> list[str]:
    """返回 error 消息列表；同句已有《书名》则放行。"""
    body = _strip_refs_section(text or "")
    errors: list[str] = []
    seen: set[str] = set()
    for sentence in _split_sentences(body):
        sent = sentence.strip()
        if not sent:
            continue
        if _BOOK_TITLE.search(sent):
            continue
        for trigger in VAGUE_CITATION_TRIGGERS:
            if not _trigger_active_in_sentence(sent, trigger):
                continue
            key = f"{trigger}:{sent[:48]}"
            if key in seen:
                continue
            seen.add(key)
            snippet = sent[:60] + ("…" if len(sent) > 60 else "")
            errors.append(
                f"无锚点模糊出处「{trigger}」: {snippet}"
                "（须改为「《书名·卷》载…」或删除）"
            )
            break
    return errors
