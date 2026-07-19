"""Kimi 硬史实意见 → DeepSeek 精准改稿（非整篇重写）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import dynasty_supplement_lib as dkl


@dataclass
class FactualEdit:
    original: str
    revised: str
    error_index: int = 0
    applied: bool = False
    note: str = ""
    target: str = "any"  # body | refs | any

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "revised": self.revised,
            "error_index": self.error_index,
            "applied": self.applied,
            "note": self.note,
            "target": self.target,
        }


@dataclass
class FixResult:
    edits: list[FactualEdit] = field(default_factory=list)
    text_before: str = ""
    text_after: str = ""
    all_applied: bool = False
    refs_sync_ok: bool = True
    issues: list[str] = field(default_factory=list)
    fix_round: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dynasty-knowledge-factual-fix/v1",
            "fix_round": self.fix_round,
            "all_applied": self.all_applied,
            "refs_sync_ok": self.refs_sync_ok,
            "issues": self.issues,
            "edits": [e.to_dict() for e in self.edits],
        }


def split_body_and_refs(detail_text: str) -> tuple[str, str]:
    raw = str(detail_text or "")
    marker = "*参考著作"
    if marker in raw:
        idx = raw.index(marker)
        return raw[:idx].rstrip(), raw[idx:].strip()
    if "参考著作" in raw:
        idx = raw.index("参考著作")
        return raw[:idx].rstrip(), raw[idx:].strip()
    return raw.rstrip(), ""


def join_body_and_refs(body: str, refs: str) -> str:
    body = body.rstrip()
    if not refs:
        return body
    return body + "\n\n" + refs.strip()


def _citation_tokens(text: str) -> list[str]:
    """从错误描述/引文中提取可能需在正文+参考著作同步的片段。"""
    tokens: list[str] = []
    for m in re.finditer(r"《[^》]+》", text):
        tokens.append(m.group())
    for m in re.finditer(r"《[^》]+·[^》]+》", text):
        tokens.append(m.group())
    return list(dict.fromkeys(tokens))


def citation_sync_requirements(
    factual_errors: list[dict[str, str]],
) -> list[dict[str, str]]:
    """每条错误的 wrong/right 典籍 token，用于改后校验。"""
    reqs: list[dict[str, str]] = []
    for i, err in enumerate(factual_errors, 1):
        blob = " ".join(
            str(err.get(k) or "") for k in ("quote", "reason", "fix_hint")
        )
        cites = _citation_tokens(blob)
        if not cites:
            continue
        wrong = cites[0]
        right = ""
        for c in _citation_tokens(str(err.get("fix_hint") or "")):
            if c != wrong:
                right = c
                break
        if wrong:
            reqs.append({"error_index": str(i), "wrong": wrong, "right": right})
    return reqs


def validate_citation_sync(
    full_text: str,
    factual_errors: list[dict[str, str]],
    edits: list[FactualEdit],
) -> tuple[bool, list[str]]:
    """改后：已应用的 edit 须 original 消失、revised 出现。"""
    del factual_errors
    issues: list[str] = []
    for edit in edits:
        if not edit.applied:
            issues.append(f"edit #{edit.error_index} 未应用")
            continue
        if edit.original in full_text:
            issues.append(
                f"替换后仍含原文（#{edit.error_index}）: {edit.original[:50]}…"
            )
        if edit.revised not in full_text:
            issues.append(
                f"替换后未见修正文（#{edit.error_index}）: {edit.revised[:50]}…"
            )
    ok = not issues and bool(edits) and all(e.applied for e in edits)
    return ok, issues


def build_factual_fix_prompt(
    entry: dict[str, Any],
    detail_text: str,
    factual_errors: list[dict[str, str]],
    *,
    fix_round: int = 1,
) -> str:
    body, refs = split_body_and_refs(detail_text)
    errors_json = json.dumps(factual_errors, ensure_ascii=False, indent=2)
    full_for_edit = join_body_and_refs(body, refs)
    refs_block = (
        f"\n## 参考著作段（须与正文典籍名/篇名保持一致）\n{refs}\n"
        if refs
        else "\n（无成稿参考著作段）\n"
    )
    return f"""你是史实纠错编辑。以下详情**整体可用**，只需按 Kimi 事实核查意见做**精准、最小改动**（第 {fix_round} 轮改稿）。

## 任务性质（与从零撰写完全不同）
- 这是**改错**，不是写新稿
- 只修 Kimi 列出的硬史实问题；**其余句子尽量一字不改**
- **禁止**：整篇重写、调整段落顺序、合并/拆分段落、润色未涉错句子

## 条目
{json.dumps({k: entry.get(k) for k in ('史略ID', '史略名称', '史略分类')}, ensure_ascii=False, indent=2)}

## 当前成稿正文
{body}
{refs_block}
## Kimi 须修正项（逐条处理）
{errors_json}

## 改稿纪律
1. `original` 必须是下方「完整成稿」中**可逐字搜到**的连续片段（15–120 字为宜）
2. `revised` 只修正史实错误，句式与篇幅尽量接近 original
3. 每条 Kimi 错误至少一条 edit；`error_index` 从 1 起
4. **典籍名/篇名错误**：正文与**参考著作段必须同步修改**（各一条 edit，`target` 分别为 body / refs）
5. **史料原文**：经典句须保留直角引号「」内的原文，只改错字/篇名；**禁止**把「」原文改成弯引号或纯白话
6. `target` 取值：`body`（仅正文）、`refs`（仅参考著作）、`any`（全文首次匹配）
6. 只输出 JSON

## 完整成稿（供 original 逐字匹配）
{full_for_edit}

只输出 JSON：
{{
  "edits": [
    {{"original": "…", "revised": "…", "error_index": 1, "target": "body|refs|any", "note": ""}}
  ]
}}"""


def parse_fix_response(text: str) -> list[FactualEdit]:
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError("fix-detail 输出非 JSON")
    out: list[FactualEdit] = []
    for row in data.get("edits") or []:
        if not isinstance(row, dict):
            continue
        orig = str(row.get("original") or "").strip()
        rev = str(row.get("revised") or "").strip()
        if not orig or not rev or orig == rev:
            continue
        target = str(row.get("target") or "any").lower()
        if target not in ("body", "refs", "any"):
            target = "any"
        out.append(
            FactualEdit(
                original=orig,
                revised=rev,
                error_index=int(row.get("error_index") or 0),
                note=str(row.get("note") or "")[:200],
                target=target,
            )
        )
    if not out:
        raise RuntimeError("fix-detail 未返回有效 edits")
    return out


def apply_factual_edits_to_full_text(
    detail_text: str,
    edits: list[FactualEdit],
    *,
    fix_round: int = 0,
) -> FixResult:
    """在完整成稿（正文+参考著作）上应用替换。"""
    result = FixResult(edits=edits, text_before=detail_text, fix_round=fix_round)
    text = detail_text
    issues: list[str] = []

    indexed: list[tuple[int, FactualEdit]] = []
    for edit in edits:
        pos = text.find(edit.original)
        if pos == -1:
            issues.append(
                f"未找到片段（#{edit.error_index}, {edit.target}）: "
                f"{edit.original[:50]}…"
            )
            indexed.append((10**9, edit))
        else:
            indexed.append((pos, edit))

    for _pos, edit in sorted(indexed, key=lambda x: x[0], reverse=True):
        if edit.original not in text:
            continue
        text = text.replace(edit.original, edit.revised, 1)
        edit.applied = True

    result.text_after = text
    result.issues = list(dict.fromkeys(issues))
    result.all_applied = all(e.applied for e in edits) and not issues
    return result


def apply_factual_edits(body: str, edits: list[FactualEdit]) -> FixResult:
    """兼容旧调用：仅正文。"""
    return apply_factual_edits_to_full_text(body, edits)
