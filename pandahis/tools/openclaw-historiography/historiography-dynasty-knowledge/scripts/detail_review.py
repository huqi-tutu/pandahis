"""详情外部 LLM 事实核查（Kimi）：仅查硬史实错误/幻觉，不做逐段文体审校。"""

from __future__ import annotations

import json
from typing import Any

from llm.review_provider import run_review_turn

import dynasty_supplement_lib as dkl

REVIEW_SCHEMA_V2 = "dynasty-knowledge-review/v2"


def build_review_prompt(
    entry: dict[str, Any],
    detail_text: str,
    *,
    anchor: dict[str, Any] | None = None,  # noqa: ARG001 — 保留签名兼容，不注入 prompt
    review_rules: str = "",  # noqa: ARG001
) -> str:
    body = dkl.strip_detail_body(detail_text)
    name = str(entry.get("史略名称") or "")
    cat = str(entry.get("史略分类") or "")
    return f"""你是历史事实核查员。通读以下白话详情，**仅**判断是否存在明显的「硬史实性错误」。

## 背景（仅供理解主题，不是对照清单）
- 条目：{name}
- 分类：{cat}

## 正文
{body}

## 判定依据
运用你已有的史学通识与常见史料知识。**不要求**对照项目索引、「主要史料出处」字段、锚点或任何固定书单。跨文献引用、索引未列的典籍名，本身不是问题。

## 仅报告以下类型
1. 明显与通识史实相悖（人物、时代、事件归属、因果、典籍内容张冠李戴）
2. 无常见史料支撑的具体细节（对话、心理、战术过程等），且正文**未**标明传说/异说/后世附会
3. 传说、神话、后世附会被当作信史叙述
4. 正文内部前后矛盾

## 不报告
- 文笔、结构、可读性、段落顺序、legend 比例
- 「某书未出现在索引/主出处中」
- 合理的异说分述，或已有「传说/据…载/后世附会」等 framing 的内容
- 有争议的史学歧见（除非正文把明显错误一侧当家史写死）

只输出 JSON：
{{
  "has_factual_errors": false,
  "factual_errors": [
    {{"quote": "正文问题句摘录", "reason": "为何是硬史实错误", "fix_hint": "修改方向一句"}}
  ],
  "summary": "一句总评"
}}

若无硬错误：`has_factual_errors` 为 false，`factual_errors` 为空数组。"""


def normalize_review(data: dict[str, Any]) -> dict[str, Any]:
    """统一为 v2；兼容旧版 paragraph_reviews。"""
    if "factual_errors" in data or "has_factual_errors" in data:
        errors = [
            {
                "quote": str(e.get("quote") or "")[:300],
                "reason": str(e.get("reason") or "")[:500],
                "fix_hint": str(e.get("fix_hint") or "")[:300],
            }
            for e in (data.get("factual_errors") or [])
            if isinstance(e, dict) and (e.get("quote") or e.get("reason"))
        ]
        has = bool(data.get("has_factual_errors")) or bool(errors)
        return {
            "has_factual_errors": has,
            "factual_errors": errors,
            "summary": str(data.get("summary") or ""),
            "overall_verdict": "fail" if has else "pass",
        }

    reviews = data.get("paragraph_reviews") or []
    errors: list[dict[str, str]] = []
    for pr in reviews:
        if not isinstance(pr, dict):
            continue
        if str(pr.get("verdict") or "").lower() != "fail":
            continue
        for issue in pr.get("issues") or []:
            errors.append(
                {
                    "quote": "",
                    "reason": str(issue),
                    "fix_hint": str(pr.get("suggested_fix") or ""),
                }
            )
    has = bool(errors) or str(data.get("overall_verdict") or "").lower() == "fail"
    return {
        "has_factual_errors": has,
        "factual_errors": errors,
        "summary": str(data.get("summary") or ""),
        "overall_verdict": "fail" if has else str(data.get("overall_verdict") or "pass"),
    }


def parse_review_response(text: str, expected_paragraphs: int = 0) -> dict[str, Any]:
    del expected_paragraphs  # v2 不校验段数
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError("审校输出非 JSON")
    return normalize_review(data)


def factual_errors_as_revise_issues(review: dict[str, Any]) -> list[str]:
    """供 compose-revise 注入的修订清单。"""
    lines: list[str] = []
    for i, err in enumerate(review.get("factual_errors") or [], 1):
        if not isinstance(err, dict):
            continue
        quote = str(err.get("quote") or "").strip()
        reason = str(err.get("reason") or "").strip()
        fix = str(err.get("fix_hint") or "").strip()
        parts = [f"Kimi事实核查#{i}"]
        if quote:
            parts.append(f"问题句：{quote}")
        if reason:
            parts.append(f"原因：{reason}")
        if fix:
            parts.append(f"改法：{fix}")
        if len(parts) > 1:
            lines.append("；".join(parts))
    return lines


def run_detail_review(
    entry: dict[str, Any],
    detail: dict[str, Any],
    *,
    anchor: dict[str, Any] | None = None,
    review_rules: str = "",
    prompt: str | None = None,
    timeout_sec: int = 600,
) -> dict[str, Any]:
    """调用 Kimi 做通识史实核查，返回 v2 审校 JSON。"""
    body = str(detail.get("翻译详情") or "")
    if not dkl.strip_detail_body(body):
        raise RuntimeError("详情正文为空，无法审校")

    if prompt is None:
        prompt = build_review_prompt(entry, body, anchor=anchor, review_rules=review_rules)
    raw = run_review_turn(
        prompt,
        session_id=f"dk-rev-{entry.get('史略ID')}-",
        timeout_sec=timeout_sec,
    )
    return parse_review_response(str(raw.get("result", "")))
