"""详情正文史料引用纪律：原文须用直角引号「」并配译述（对齐一期翻译详录）。"""

from __future__ import annotations

import re
from typing import Any

# 弯引号（含 ASCII 与 Unicode 弯引）
_CURVED_OPEN = '"\u201c'
_CURVED_CLOSE = '"\u201d'

# 《书名》后「载/记/写/云/曰…」+ 弯引号 → 疑似史料原文误标（术语性短引号、他书对话不在此列）
_CITE_THEN_CURVED = re.compile(
    rf"《[^》]+》[^「『」』]{{0,25}}"
    rf"(?:载|记|写|云|曰|谓|称|原文|原话|说)[^「」]{{0,10}}"
    rf"[{re.escape(_CURVED_OPEN)}]([^{re.escape(_CURVED_CLOSE)}]{{4,}})[{re.escape(_CURVED_CLOSE)}]"
)

# 「"…"」/「"…"」→ 应去掉内层史记对话标点
_NESTED_CORNER_ASCII = re.compile(r'「["\u201c]([^」]+?)["\u201d]」')


def _snippet_anchor(snippet: str, min_len: int = 6) -> str:
    """摘句中用于检索的连续子串（去标点）。"""
    s = re.sub(r"\s+", "", snippet.strip())
    s = re.sub(r"[，。、；：！？「」『』""''…—\-]", "", s)
    if len(s) <= min_len:
        return s
    return s[: min(len(s), 12)]


def curved_quote_after_source_citation_issues(body: str) -> list[tuple[str, str, str]]:
    """《书名》引出后直接用弯引号包裹史料内容 → error（应改「」并译述）。

    豁免：他书对话（如《孟子》载…"公孙丑问…"）、术语性短引号不在此列。
    """
    issues: list[tuple[str, str, str]] = []
    for m in _CITE_THEN_CURVED.finditer(body):
        snippet = m.group(1).strip()[:24]
        issues.append(
            (
                "source_curved_quote",
                f"《…》引用后使用弯引号「{snippet}…」，史料原文须改直角引号「」并配白话译述",
                "error",
            )
        )
    return issues


def nested_corner_ascii_quote_issues(body: str) -> list[tuple[str, str, str]]:
    """「"原文"」双层嵌套 → error（内层史记引号应去掉）。"""
    issues: list[tuple[str, str, str]] = []
    for m in _NESTED_CORNER_ASCII.finditer(body):
        snippet = m.group(1).strip()[:24]
        issues.append(
            (
                "nested_corner_quote",
                f"直角引号内嵌套弯引号：「{snippet}…」，应写作「{snippet}…」",
                "error",
            )
        )
    return issues


def fix_nested_corner_ascii_quotes(body: str) -> tuple[str, int]:
    """「"…"」→「…」。"""

    changes = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal changes
        changes += 1
        return f"「{m.group(1)}」"

    return _NESTED_CORNER_ASCII.sub(_repl, body), changes


def verified_snippet_quote_issues(
    body: str,
    bibliography_plan: dict[str, Any] | None,
) -> list[tuple[str, str, str]]:
    """书目 plan 中 verified 原文摘句须出现在正文「」内。"""
    issues: list[tuple[str, str, str]] = []
    if not bibliography_plan:
        return issues
    corner_blocks = re.findall(r"「([^」]+)」", body)
    corner_text = "".join(corner_blocks)
    for src in bibliography_plan.get("候选著作") or []:
        if not isinstance(src, dict):
            continue
        if not src.get("采用", True):
            continue
        if not src.get("snippet_verified"):
            continue
        snippet = str(src.get("原文摘句") or "").strip()
        if len(snippet) < 4:
            continue
        anchor = _snippet_anchor(snippet)
        if not anchor:
            continue
        if anchor in corner_text or anchor in body:
            if anchor not in corner_text:
                cite = src.get("出处") or "?"
                issues.append(
                    (
                        "verified_snippet_not_quoted",
                        f"{cite} 的 verified 摘句未用「」标出原文（须「摘句」+译述）",
                        "warn",
                    )
                )
        else:
            cite = src.get("出处") or "?"
            issues.append(
                (
                    "verified_snippet_missing",
                    f"{cite} 的 verified 摘句未写入正文（须「摘句」+译述）",
                    "warn",
                )
            )
    return issues


def corner_quote_density_issues(
    body: str,
    *,
    priority: str = "P1",
) -> list[tuple[str, str, str]]:
    """高优先级条目：有较多典籍引用时，应有一定密度「」原文。"""
    if priority not in ("P0", "P1"):
        return []
    cite_count = len(re.findall(r"《[^》]+》", body))
    corner_count = len(re.findall(r"「[^」]+」", body))
    if cite_count >= 5 and corner_count == 0:
        return [
            (
                "missing_source_quotes",
                f"正文引用典籍 {cite_count} 处但无「」原文摘引；经典描述须「原文」+译述",
                "warn",
            )
        ]
    return []


def source_citation_verify_issues(
    body: str,
    *,
    bibliography_plan: dict[str, Any] | None = None,
    priority: str = "P1",
) -> list[tuple[str, str, str]]:
    issues: list[tuple[str, str, str]] = []
    issues.extend(curved_quote_after_source_citation_issues(body))
    issues.extend(nested_corner_ascii_quote_issues(body))
    issues.extend(verified_snippet_quote_issues(body, bibliography_plan))
    issues.extend(corner_quote_density_issues(body, priority=priority))
    return issues
