"""verify-detail 可机械修复的格式问题（0 token）。

当前覆盖：
- refs_volume_mismatch：参考著作与正文《母书·卷篇》对齐
- source_curved_quote：《书名》后弯引号改直角引号「」
- nested_corner_quote：「"…"」去掉内层引号
"""

from __future__ import annotations

import re
from typing import Any

from shared.reference_works import (
    format_reference_section,
    parse_reference_section,
    reference_volume_mismatch_issues,
    strip_reference_section,
    _extract_volume_citations,
    _volume_sets_by_mother,
)
from shared.source_citation import (
    _CITE_THEN_CURVED,
    fix_nested_corner_ascii_quotes,
)

AUTO_FIXABLE_VERIFY_CODES = frozenset(
    {
        "refs_volume_mismatch",
        "source_curved_quote",
        "nested_corner_quote",
    }
)


def fix_curved_quotes_after_citation(body: str) -> tuple[str, int]:
    """《…》载/说… 后的弯引号 "…" → 「…」。"""
    changes = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal changes
        full = m.group(0)
        inner = m.group(1)
        for o, c in (('"', '"'), ("\u201c", "\u201d")):
            old = f"{o}{inner}{c}"
            if old in full:
                changes += 1
                return full.replace(old, f"「{inner}」")
        return full

    return _CITE_THEN_CURVED.sub(_repl, body), changes


def sync_reference_volumes_to_body(detail: str) -> tuple[str, int]:
    """参考著作中与正文同母书的卷篇，只保留正文实际引用的卷篇。"""
    if "参考著作" not in detail:
        return detail, 0
    body = strip_reference_section(detail)
    body_m = _volume_sets_by_mother(_extract_volume_citations(body))
    refs = parse_reference_section(detail)
    if not body_m:
        return detail, 0

    kept: list[str] = []
    dropped = 0
    for ref in refs:
        inner = ref.strip("《》")
        if "·" not in inner:
            kept.append(ref)
            continue
        mother, vol = inner.split("·", 1)
        mother, vol = mother.strip(), vol.strip()
        if mother not in body_m:
            kept.append(ref)
            continue
        if vol in body_m[mother]:
            kept.append(ref)
        else:
            dropped += 1

    if dropped == 0:
        return detail, 0
    new_detail = f"{body.rstrip()}\n\n{format_reference_section(kept)}"
    return new_detail, dropped


def autofix_detail_format(
    detail_text: str,
    entry: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """返回 (新全文, 已修复 issue code 列表)。entry 保留供后续扩展。"""
    _ = entry
    fixes: list[str] = []
    body = strip_reference_section(detail_text)
    refs = parse_reference_section(detail_text)

    new_body, n_curved = fix_curved_quotes_after_citation(body)
    if n_curved:
        fixes.append("source_curved_quote")

    new_body, n_nested = fix_nested_corner_ascii_quotes(new_body)
    if n_nested:
        fixes.append("nested_corner_quote")

    if refs:
        working = f"{new_body.rstrip()}\n\n{format_reference_section(refs)}"
    else:
        working = new_body

    new_detail, n_vol = sync_reference_volumes_to_body(working)
    if n_vol:
        fixes.append("refs_volume_mismatch")

    if not fixes:
        return detail_text, []
    return new_detail, fixes


def can_autofix_verify_errors(issues: list[Any]) -> bool:
    """是否全部为可机械修复的 error。"""
    errors = [i for i in issues if getattr(i, "severity", "error") == "error"]
    if not errors:
        return False
    codes = {getattr(i, "code", "") for i in errors}
    return codes.issubset(AUTO_FIXABLE_VERIFY_CODES)


def detail_passes_volume_check(detail: str) -> bool:
    return not reference_volume_mismatch_issues(detail)
