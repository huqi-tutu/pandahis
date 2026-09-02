"""D 前置：enrich gap ledger + 索引补充程序 seed。"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from lib.plan_postprocess import inject_index_supplements_plan
from lib.verify import _source_char_len


def _body_without_refs(detail: str) -> str:
    return detail.split("参考著作", 1)[0].strip()


def _paragraph_count(text: str) -> int:
    return len([p for p in text.split("\n\n") if p.strip()])


def _mother_char_len(recalled: Dict[str, Any]) -> int:
    parts: List[str] = []
    for block in recalled.get("blocks") or []:
        if not isinstance(block, dict) or str(block.get("role") or "母本") != "母本":
            continue
        text = str(block.get("text") or "").strip()
        if text:
            parts.append(text)
            continue
        for para in block.get("paragraphs") or []:
            t = str(para.get("text") or "").strip()
            if t:
                parts.append(t)
    return _source_char_len("\n".join(parts))


def build_enrich_gap_ledger(
    baseline_detail: str,
    plan_data: Dict[str, Any],
    recalled: Dict[str, Any],
) -> Dict[str, Any]:
    """基于 C 初稿与 recall 生成 D 前缺口清单（程序，供 enrich plan LLM）。"""
    body = _body_without_refs(baseline_detail)
    body_len = len(re.sub(r"\s+", "", body))
    mother_len = _mother_char_len(recalled)
    thin_ratio = float(os.environ.get("TRANSLATE_ENRICH_THIN_RATIO", "1.5"))
    thin = bool(mother_len > 0 and body_len < int(mother_len * thin_ratio))

    gaps: List[Dict[str, Any]] = []
    checklist = plan_data.get("母本逐句清单") or []
    if isinstance(checklist, list):
        for item in checklist:
            if not isinstance(item, dict):
                continue
            grain = str(item.get("引用粒度") or item.get("母本提示") or "")
            mid = str(item.get("编号") or "")
            must = item.get("必现词") or []
            anchor = ""
            if isinstance(must, list) and must:
                anchor = str(must[0] or "")
            elif isinstance(must, str):
                anchor = must
            if "parallel_cluster" in grain or "appraisal" in grain or "genealogy" in grain:
                snippet = anchor[:12] if anchor else ""
                has_quote = "「" in body or "『" in body
                if snippet and snippet not in body and not has_quote:
                    gaps.append(
                        {
                            "类型": "句群引用待补",
                            "M": mid,
                            "说明": f"引用粒度 {grain}，初稿未见典型引号摘句，D 须考虑引原文后释",
                            "初稿锚点": snippet,
                        }
                    )

    for block in recalled.get("blocks") or []:
        if not isinstance(block, dict) or str(block.get("role") or "") != "补充":
            continue
        work = str(block.get("work") or "")
        text = str(block.get("text") or "")[:80]
        if text and text[:20] not in body:
            gaps.append(
                {
                    "类型": "索引补充未呈现",
                    "出处": work,
                    "说明": "recall 补充 block 尚未在初稿出现，须在 enrich plan 中规划引入或异说",
                    "初稿锚点": body.split("\n\n")[0][:40] if body else "开篇",
                }
            )

    min_adopt = max(0, int(os.environ.get("TRANSLATE_ENRICH_MIN_ADOPT", "2"))) if thin else 0
    if thin:
        gaps.insert(
            0,
            {
                "类型": "初稿偏薄",
                "说明": (
                    f"初稿正文 {body_len} 字 < 母本×{thin_ratio}={int(mother_len * thin_ratio)}；"
                    f"enrich plan 须规划 ≥{min_adopt} 条采用:true 的背景/细节/异说（非重复初稿）"
                ),
            },
        )

    return {
        "初稿字数": body_len,
        "母本字数": mother_len,
        "初稿段落数": _paragraph_count(body),
        "初稿偏薄": thin,
        "建议最少外部补全": min_adopt,
        "缺口项": gaps,
    }


def seed_index_supplements_for_enrich(
    plan: Dict[str, Any], recalled: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """程序 seed 索引补充（enrich plan 前）；返回 seed 列表供合并。"""
    scratch = dict(plan)
    scratch["索引补充处理"] = []
    inject_index_supplements_plan(scratch, recalled)
    seeded = scratch.get("索引补充处理") or []
    return [x for x in seeded if isinstance(x, dict)]


def merge_enrich_plan_with_seed(
    merged: Dict[str, Any],
    raw_llm: Dict[str, Any],
    *,
    seed_index: List[Dict[str, Any]],
    gap_ledger: Dict[str, Any],
) -> Dict[str, Any]:
    """LLM plan 与程序 seed / gap 合并。"""
    merged["外部补全"] = list(raw_llm.get("外部补全") or [])
    llm_index = [x for x in (raw_llm.get("索引补充处理") or []) if isinstance(x, dict)]
    by_src: Dict[str, Dict[str, Any]] = {}
    for item in seed_index + llm_index:
        src = str(item.get("出处") or "")
        if src:
            by_src[src] = item
    merged["索引补充处理"] = list(by_src.values())
    for k in ("参考著作", "写作结构", "D阶段插入风格"):
        if k in raw_llm and raw_llm.get(k) is not None:
            merged[k] = raw_llm[k]
    merged["_enrich_gap_ledger"] = gap_ledger
    return merged
