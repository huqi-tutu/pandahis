"""详情外部 LLM 交叉审校（档三）：逐段 JSON 输出，脚本校验段数。"""

from __future__ import annotations

import json
from typing import Any

from llm.review_provider import run_review_turn

import dynasty_supplement_lib as dkl


def split_detail_paragraphs(body: str) -> list[str]:
    return dkl.split_detail_paragraphs(body)


def build_review_prompt(
    entry: dict[str, Any],
    detail_text: str,
    *,
    anchor: dict[str, Any] | None = None,
) -> str:
    paragraphs = split_detail_paragraphs(detail_text)
    numbered = "\n\n".join(
        f"[P{i}] {para}" for i, para in enumerate(paragraphs)
    )
    anchor_block = ""
    if anchor:
        anchor_block = f"\n## 锚点\n{json.dumps(anchor, ensure_ascii=False, indent=2)}\n"

    return f"""你是历史内容质检员。审校以下朝代知识补全详情，逐段输出 JSON（temperature=0 纪律）。

## 条目
{json.dumps({k: entry.get(k) for k in ('史略ID', '史略名称', '史略分类', '优先级', '主要史料出处')}, ensure_ascii=False, indent=2)}
{anchor_block}
## 正文（共 {len(paragraphs)} 段）
{numbered}

## 审校要点
1. 过程禁编：无史料支撑的心理活动、对话、细节不可当作史实
2. 核心列举：制度/人物/事件列举须与锚点或主要史料一致
3. 异说处理：传说/后世附会须标注，不可与正史混写
4. 禁词与 AI 腔
5. 注音：除白名单外不应出现

只输出 JSON：
{{
  "paragraph_count": {len(paragraphs)},
  "paragraph_reviews": [
    {{"paragraph_index": 0, "verdict": "pass|warn|fail", "issues": ["..."], "suggested_fix": "..."}}
  ],
  "overall_verdict": "pass|warn|fail",
  "summary": "..."
}}

paragraph_reviews 长度必须等于 {len(paragraphs)}。"""


def parse_review_response(text: str, expected_paragraphs: int) -> dict[str, Any]:
    data = dkl.extract_json_object(text)
    if not data:
        raise RuntimeError("审校输出非 JSON")
    reviews = data.get("paragraph_reviews") or []
    if len(reviews) != expected_paragraphs:
        raise RuntimeError(
            f"审校段数不匹配: 期望 {expected_paragraphs}，实际 {len(reviews)}"
        )
    return data


def run_detail_review(
    entry: dict[str, Any],
    detail: dict[str, Any],
    *,
    anchor: dict[str, Any] | None = None,
    timeout_sec: int = 900,
) -> dict[str, Any]:
    """调用独立审校模型（Kimi），返回解析后的审校 JSON。"""
    body = str(detail.get("翻译详情") or "")
    paragraphs = split_detail_paragraphs(body)
    if not paragraphs:
        raise RuntimeError("详情正文为空，无法审校")

    prompt = build_review_prompt(entry, body, anchor=anchor)
    raw = run_review_turn(
        prompt,
        session_id=f"dk-rev-{entry.get('史略ID')}-",
        timeout_sec=timeout_sec,
    )
    return parse_review_response(str(raw.get("result", "")), len(paragraphs))
