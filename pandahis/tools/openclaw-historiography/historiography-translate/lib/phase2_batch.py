"""Phase2 分批补全：长母本单次输出超限时分批 enrich 再合并。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.fingerprint import recalled_summary
from lib.openclaw import build_translate_enrich_prompt
from lib.plan_postprocess import plan_for_enrich_phase


def phase2_batch_char_threshold() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE2_BATCH_CHARS", "10000")))


def discover_mother_batches(mother_file: Path) -> List[Path]:
    pattern = f"{mother_file.stem}-b*{mother_file.suffix}"
    return sorted(mother_file.parent.glob(pattern))


def _mother_batch_size() -> int:
    return max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def _m_numbers_from_text(text: str) -> set[int]:
    return {int(m) for m in re.findall(r"M(\d+)", str(text))}


def _anchor_in_batch(anchor: str, batch_nums: set[int]) -> bool:
    nums = _m_numbers_from_text(anchor)
    if not nums:
        return False
    return bool(nums & batch_nums)


def plan_for_enrich_batch(plan_data: Dict[str, Any], batch_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """本批 M 清单 + 锚点落在本批的外部补全/索引补充。"""
    batch_nums = _m_numbers_from_text(
        " ".join(str(x.get("编号") or "") for x in batch_items)
    )
    base = plan_for_enrich_phase(plan_data)
    ext = [
        x
        for x in base.get("外部补全") or []
        if isinstance(x, dict)
        and _anchor_in_batch(str(x.get("母本锚点") or ""), batch_nums)
    ]
    idx = [
        x
        for x in base.get("索引补充处理") or []
        if isinstance(x, dict)
        and _anchor_in_batch(str(x.get("锚点") or x.get("母本锚点") or ""), batch_nums)
    ]
    return {
        **base,
        "母本逐句清单": batch_items,
        "外部补全": ext,
        "索引补充处理": idx,
    }


def batch_checklist_items(plan_data: Dict[str, Any], batch_index: int) -> List[Dict[str, Any]]:
    checklist = plan_data.get("母本逐句清单") or []
    if not isinstance(checklist, list):
        return []
    size = _mother_batch_size()
    if size <= 0:
        return []
    start = (batch_index - 1) * size
    return checklist[start : start + size]


def batch_mode_note(*, batch_no: int, total: int, include_intro: bool) -> str:
    lines = [
        "",
        "---",
        f"【分批补全模式】第 {batch_no}/{total} 批",
    ]
    if include_intro:
        lines.append(
            "本批须在文首写前置引入（笼统定位，自然进入正文），再接本批母本段的补全正文。"
        )
    else:
        lines.append("本批勿写前置引入，只写本批母本段的补全正文。")
    lines.append(
        "输出 JSON 的「翻译详情」仅含本批正文（已穿插本批相关他书补全），"
        "勿写参考著作节；程序合并各批后统一添加。"
    )
    return "\n".join(lines) + "\n"


def append_reference_section(detail: str, plan_data: Dict[str, Any], recalled: Dict[str, Any]) -> str:
    refs: List[str] = []
    mother_work = str(recalled.get("母本著作") or plan_data.get("母本著作") or "")
    if mother_work:
        refs.append(f"《{mother_work}》")
    for item in plan_data.get("参考著作") or []:
        text = str(item).strip()
        if text and text not in refs:
            refs.append(text)
    for item in plan_data.get("外部补全") or []:
        if not isinstance(item, dict) or item.get("采用") is not True:
            continue
        src = str(item.get("出处") or "").strip()
        if src and src not in refs:
            refs.append(src)
    body = detail.rstrip()
    if not refs:
        return body
    lines = "\n".join(f"{i}. {r}" for i, r in enumerate(refs, start=1))
    return f"{body}\n\n参考著作：\n{lines}"


def merge_enrich_batches(
    entry_id: str,
    parts: List[str],
    plan_data: Dict[str, Any],
    recalled: Dict[str, Any],
) -> str:
    body = "\n\n".join(p.strip() for p in parts if p and p.strip())
    return append_reference_section(body, plan_data, recalled)


def build_batch_enrich_prompt(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
    mother_text: str,
    output_file: Path,
    *,
    batch_no: int,
    total_batches: int,
    include_intro: bool,
) -> str:
    batch_items = batch_checklist_items(plan_data, batch_no)
    batch_plan = plan_for_enrich_batch(plan_data, batch_items)
    prompt = build_translate_enrich_prompt(
        entry_id,
        recalled,
        recalled_summary(recalled),
        json.dumps(batch_plan, ensure_ascii=False, indent=2),
        mother_text,
        output_file,
    )
    return prompt + batch_mode_note(
        batch_no=batch_no,
        total=total_batches,
        include_intro=include_intro,
    )
