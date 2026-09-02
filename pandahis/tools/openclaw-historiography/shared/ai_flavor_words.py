"""AI 腔 / 书面腔词表与频次硬检（翻译 verify + 朝代 verify-detail 共用）。"""

from __future__ import annotations

# 翻译规则 + 朝代撰写规范并集（按长度降序，避免子串误计时可另行处理）
AI_FLAVOR_WORDS: tuple[str, ...] = (
    "历史终将证明",
    "值得注意的是",
    "翻开新篇章",
    "毫无疑问",
    "综上所述",
    "历史长河",
    "时代洪流",
    "命运齿轮",
    "由此可见",
    "众所周知",
    "与此同时",
    "拉开序幕",
    "此外",
    "堪称",
    "可谓",
    "不啻",
    "则是",
    "注定",
    "必然",
)

# 兼容旧名
FORBIDDEN_PROSE_WORDS = AI_FLAVOR_WORDS

# 出现次数 >= FAIL_AT 即 error（即单篇最多允许 FAIL_AT - 1 次）
AI_FLAVOR_WORD_FAIL_AT = 5


def ai_flavor_word_counts(body: str) -> tuple[dict[str, int], int]:
    """返回 (各词出现次数, 全文合计)。"""
    counts: dict[str, int] = {}
    total = 0
    for word in AI_FLAVOR_WORDS:
        n = body.count(word)
        if n:
            counts[word] = n
            total += n
    return counts, total


def ai_flavor_verify_issues(body: str) -> list[tuple[str, str, str]]:
    """(code, message, severity) — severity 固定 error。"""
    counts, total = ai_flavor_word_counts(body)
    issues: list[tuple[str, str, str]] = []
    limit = AI_FLAVOR_WORD_FAIL_AT - 1
    for word, n in counts.items():
        if n >= AI_FLAVOR_WORD_FAIL_AT:
            issues.append(
                (
                    "ai_flavor_word",
                    f"AI 腔词「{word}」出现 {n} 次 ≥ {AI_FLAVOR_WORD_FAIL_AT}（单篇最多 {limit} 次）",
                    "error",
                )
            )
    if total >= AI_FLAVOR_WORD_FAIL_AT:
        detail = "、".join(f"「{w}」×{n}" for w, n in counts.items())
        issues.append(
            (
                "ai_flavor_total",
                f"AI 腔词全文合计 {total} 次 ≥ {AI_FLAVOR_WORD_FAIL_AT}（单篇最多 {limit} 次；{detail}）",
                "error",
            )
        )
    return issues


def strip_ai_flavor_excess(body: str) -> tuple[str, list[str]]:
    """脚本降 AI 腔词频：单词与全文合计均压到硬检阈值以下。"""
    text = str(body or "")
    if not text.strip():
        return text, []
    changes: list[str] = []
    per_word_cap = AI_FLAVOR_WORD_FAIL_AT - 1

    for word in sorted(AI_FLAVOR_WORDS, key=len, reverse=True):
        while text.count(word) > per_word_cap:
            idx = text.rfind(word)
            if idx < 0:
                break
            text = text[:idx] + text[idx + len(word) :]
            changes.append(f"删余「{word}」")

    _counts, total = ai_flavor_word_counts(text)
    while total >= AI_FLAVOR_WORD_FAIL_AT:
        counts, _ = ai_flavor_word_counts(text)
        if not counts:
            break
        word = max(counts, key=lambda w: (counts[w], len(w)))
        idx = text.rfind(word)
        if idx < 0:
            break
        text = text[:idx] + text[idx + len(word) :]
        changes.append(f"降合计删「{word}」")
        _counts, total = ai_flavor_word_counts(text)

    return text, changes
