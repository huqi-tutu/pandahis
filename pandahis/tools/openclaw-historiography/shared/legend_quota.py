"""传说/二手表述层配额：无《》锚点的「据说/传说/有人说」等统一走频次控制，禁止喧宾夺主。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 无《》锚点的二手表述触发词（原 legend + vague_citation 并集，统一配额）
LEGEND_TRIGGERS: tuple[str, ...] = (
    "传说",
    "相传",
    "据说",
    "后世常说",
    "口传",
    "附会",
    "异说",
    "有人说",
    "有传言说",
    "有资料说",
    "历史上认为",
    "一般认为",
    "后世认为",
    "有观点认为",
)

# 兼容旧 import：prose_sanitize 等仍可从 vague_citation 引用
UNANCHORED_ATTRIBUTION_TRIGGERS: tuple[str, ...] = (
    "有人说",
    "有传言说",
    "有资料说",
    "历史上认为",
    "一般认为",
    "后世认为",
    "有观点认为",
)

# 固定搭配 / 文献层 framing：其中的子串不计入传说触发
LEGEND_TRIGGER_EXEMPT: tuple[str, ...] = (
    "口耳相传",
    "口传相传",
    "神话传说",
    "民间传说",
    "后世传说",
    "传说时代",
)

# 有书名即视为文献层，该句不计入传说触发
_BOOK = re.compile(r"《[^》]+》")

LEGEND_TRIGGER_MAX_DEFAULT = 5
LEGEND_TRIGGER_MAX_P3 = 7
LEGEND_MAX_CONSECUTIVE_PARAGRAPHS = 1
LEGEND_CHAR_RATIO_MAX = 0.20


@dataclass
class LegendQuotaMetrics:
    trigger_count: int
    legend_paragraph_count: int
    max_consecutive_legend_paragraphs: int
    legend_char_ratio: float
    first_sourced_paragraph_index: int | None
    first_legend_paragraph_index: int | None


def _strip_refs(text: str) -> str:
    for marker in ("*参考著作*", "参考著作"):
        if marker in text:
            return text.split(marker, 1)[0]
    return text


def _paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", _strip_refs(text or ""))
    return [p.strip() for p in parts if p.strip()]


def _sentence_has_legend_trigger(sentence: str) -> bool:
    if _BOOK.search(sentence):
        return False
    scratch = sentence
    for phrase in LEGEND_TRIGGER_EXEMPT:
        scratch = scratch.replace(phrase, "")
    return any(t in scratch for t in LEGEND_TRIGGERS)


def _paragraph_is_legend_heavy(paragraph: str) -> bool:
    sentences = re.split(r"(?<=[。！？\n])", paragraph)
    hits = sum(1 for s in sentences if s.strip() and _sentence_has_legend_trigger(s))
    if hits >= 2:
        return True
    if hits == 1 and len(paragraph) >= 80 and not _BOOK.search(paragraph):
        return True
    return False


def _paragraph_has_sourced_anchor(paragraph: str) -> bool:
    if _BOOK.search(paragraph):
        return True
    for token in ("史载", "史书", "太史公", "本纪", "据史", "按《"):
        if token in paragraph:
            return True
    return False


def analyze_legend_quota(text: str) -> LegendQuotaMetrics:
    paras = _paragraphs(text)
    trigger_count = 0
    legend_para_flags: list[bool] = []
    first_sourced: int | None = None
    first_legend: int | None = None
    legend_chars = 0
    total_chars = sum(len(p) for p in paras)

    for idx, para in enumerate(paras):
        if _paragraph_has_sourced_anchor(para) and first_sourced is None:
            first_sourced = idx
        is_legend = _paragraph_is_legend_heavy(para)
        legend_para_flags.append(is_legend)
        if is_legend and first_legend is None:
            first_legend = idx
        if is_legend:
            legend_chars += len(para)
        for sent in re.split(r"(?<=[。！？\n])", para):
            if sent.strip() and _sentence_has_legend_trigger(sent):
                trigger_count += 1

    max_consec = 0
    streak = 0
    for flag in legend_para_flags:
        if flag:
            streak += 1
            max_consec = max(max_consec, streak)
        else:
            streak = 0

    ratio = (legend_chars / total_chars) if total_chars else 0.0
    return LegendQuotaMetrics(
        trigger_count=trigger_count,
        legend_paragraph_count=sum(1 for f in legend_para_flags if f),
        max_consecutive_legend_paragraphs=max_consec,
        legend_char_ratio=ratio,
        first_sourced_paragraph_index=first_sourced,
        first_legend_paragraph_index=first_legend,
    )


def legend_quota_verify_issues(
    text: str,
    *,
    priority: str = "P1",
) -> list[tuple[str, str, str]]:
    """返回 (code, message, severity)。"""
    m = analyze_legend_quota(text)
    issues: list[tuple[str, str, str]] = []
    cap = LEGEND_TRIGGER_MAX_P3 if priority == "P3" else LEGEND_TRIGGER_MAX_DEFAULT
    if m.trigger_count > cap:
        issues.append(
            (
                "legend_dominance",
                f"无《》二手表述触发词 {m.trigger_count} 处 > 上限 {cap}"
                f"（传说/据说/有人说等宜克制，不可当家）",
                "error",
            )
        )
    if m.max_consecutive_legend_paragraphs > LEGEND_MAX_CONSECUTIVE_PARAGRAPHS:
        issues.append(
            (
                "legend_dominance",
                f"连续 {m.max_consecutive_legend_paragraphs} 段以传说/二手表述为主叙事"
                f"（上限 {LEGEND_MAX_CONSECUTIVE_PARAGRAPHS} 段）",
                "error",
            )
        )
    if m.legend_char_ratio > LEGEND_CHAR_RATIO_MAX:
        issues.append(
            (
                "legend_ratio",
                f"传说层篇幅约 {m.legend_char_ratio:.0%} > 参考上限 {LEGEND_CHAR_RATIO_MAX:.0%}（仅 warn，不阻断）",
                "warn",
            )
        )
    return issues
