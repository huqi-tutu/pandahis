"""Phase2 分批补全：长母本单次输出超限时分批 enrich 再合并。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.fingerprint import recalled_summary
from lib.m_anchor import anchor_hits_batch, batch_m_numbers
from lib.openclaw import build_translate_enrich_prompt
from lib.plan_postprocess import plan_for_enrich_phase


def phase2_batch_char_threshold() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE2_BATCH_CHARS", "10000")))


def _mother_batch_pattern(mother_file: Path) -> re.Pattern[str]:
    """仅匹配 Phase1 母本批 mother-bNN.json，排除 .enrich.json 等衍生文件。"""
    stem = re.escape(mother_file.stem)
    return re.compile(rf"^{stem}-b(\d+)\.json$", re.IGNORECASE)


def discover_mother_batches(mother_file: Path) -> List[Path]:
    pattern = _mother_batch_pattern(mother_file)
    numbered: List[Tuple[int, Path]] = []
    for path in mother_file.parent.iterdir():
        if not path.is_file():
            continue
        match = pattern.match(path.name)
        if match:
            numbered.append((int(match.group(1)), path))
    return [path for _, path in sorted(numbered, key=lambda item: item[0])]


def _mother_batch_size() -> int:
    return max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def plan_for_enrich_batch(
    plan_data: Dict[str, Any],
    batch_items: List[Dict[str, Any]],
    *,
    batch_index: int = 1,
    batch_total: int = 1,
) -> Dict[str, Any]:
    """本批 M 清单 + 锚点落在本批的外部补全/索引补充。"""
    batch_nums = batch_m_numbers(batch_items)
    checklist = plan_data.get("母本逐句清单") or []
    base = plan_for_enrich_phase(plan_data)
    ext = [
        x
        for x in base.get("外部补全") or []
        if isinstance(x, dict)
        and anchor_hits_batch(
            str(x.get("母本锚点") or ""),
            batch_nums,
            checklist=checklist if isinstance(checklist, list) else None,
            batch_index=batch_index,
            batch_total=batch_total,
        )
    ]
    idx = [
        x
        for x in base.get("索引补充处理") or []
        if isinstance(x, dict)
        and anchor_hits_batch(
            str(x.get("锚点") or x.get("母本锚点") or ""),
            batch_nums,
            checklist=checklist if isinstance(checklist, list) else None,
            batch_index=batch_index,
            batch_total=batch_total,
        )
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
    """成稿拼接参考著作：母本卷为首 + 正文《》去重顺序（不再依赖 plan 列表）。"""
    from lib.final_polish import finalize_translation_detail

    _ = plan_data
    body = detail.split("参考著作", 1)[0].rstrip()
    # 装配阶段先只拼参考著作；引号校正在归因/终检链路再跑一遍亦可
    finalized, _ = finalize_translation_detail(body, recalled, plan=plan_data)
    return finalized.rstrip()


def split_detail_paragraph_batches(detail: str, char_threshold: int) -> List[str]:
    """将 baseline/成稿按段落分批（不含参考著作节）。"""
    body = detail.split("参考著作", 1)[0].strip()
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        return []
    batches: List[List[str]] = []
    current: List[str] = []
    current_len = 0
    for para in paras:
        plen = len(para)
        if current and current_len + plen + 2 > char_threshold:
            batches.append(current)
            current = [para]
            current_len = plen
        else:
            current.append(para)
            current_len += plen + 2
    if current:
        batches.append(current)
    return ["\n\n".join(chunk) for chunk in batches]


def batch_context_prefix(prev_batch_text: str) -> str:
    """上一批末段作衔接上下文（仅 prompt，不进入合并输出）。"""
    paras = [p.strip() for p in prev_batch_text.split("\n\n") if p.strip()]
    if not paras:
        return ""
    tail = paras[-1]
    return (
        "【上文末段（仅供衔接，勿重复输出）】\n"
        f"{tail}\n\n---\n\n"
    )


def plan_for_enrich_batch_by_draft(
    plan_data: Dict[str, Any], batch_text: str
) -> Dict[str, Any]:
    """按初稿锚点筛选本批 enrich plan。"""
    base = plan_for_enrich_phase(plan_data)

    def _anchor_in_batch(item: Dict[str, Any]) -> bool:
        anchor = str(
            item.get("初稿锚点") or item.get("母本锚点") or item.get("锚点") or ""
        ).strip()
        if not anchor:
            return False
        snippet = anchor[:40].strip()
        if snippet and snippet in batch_text:
            return True
        for line in anchor.split("\n"):
            line = line.strip()
            if len(line) >= 8 and line in batch_text:
                return True
        return False

    ext = [
        x
        for x in base.get("外部补全") or []
        if isinstance(x, dict) and _anchor_in_batch(x)
    ]
    idx = [
        x
        for x in base.get("索引补充处理") or []
        if isinstance(x, dict) and _anchor_in_batch(x)
    ]
    return {**base, "外部补全": ext, "索引补充处理": idx}


def baseline_batch_mode_note(*, batch_no: int, total: int) -> str:
    lines = [
        "",
        "---",
        f"【D 分批 enrich】第 {batch_no}/{total} 批",
        "本批须 enrich **C 初稿对应段落**（含引入/正文/结尾中落在本批的部分），"
        "按 plan 插入延伸内容；勿写参考著作节。",
        "输出 JSON 的「翻译详情」**仅含本批 enrich 后的段落**，程序合并各批后统一添加参考著作。",
    ]
    return "\n".join(lines) + "\n"


def build_baseline_batch_enrich_prompt(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
    batch_text: str,
    output_file: Path,
    *,
    batch_no: int,
    total_batches: int,
    context_prefix: str = "",
) -> str:
    batch_plan = plan_for_enrich_batch_by_draft(plan_data, batch_text)
    mother_for_prompt = context_prefix + batch_text
    prompt = build_translate_enrich_prompt(
        entry_id,
        recalled,
        recalled_summary(recalled),
        json.dumps(batch_plan, ensure_ascii=False, indent=2),
        mother_for_prompt,
        output_file,
    )
    return prompt + baseline_batch_mode_note(batch_no=batch_no, total=total_batches)


def split_baseline_zones(detail: str) -> Tuple[str, str, str]:
    """intro, core, tail（不含参考著作节）。"""
    body = detail.split("参考著作", 1)[0].strip()
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        return "", "", ""
    if len(paras) == 1:
        return paras[0], "", ""
    if len(paras) == 2:
        return paras[0], "", paras[1]
    intro, tail = paras[0], paras[-1]
    core = "\n\n".join(paras[1:-1])
    return intro, core, tail


def merge_d_with_baseline_shell(
    baseline_detail: str,
    enriched_core: str,
    plan_data: Dict[str, Any],
    recalled: Dict[str, Any],
) -> str:
    """D 分批 enrich 后，用 C 阶段引入/结尾壳组装终稿。"""
    intro, _, tail = split_baseline_zones(baseline_detail)
    chunks = [p for p in (intro, enriched_core.strip(), tail) if p.strip()]
    body = "\n\n".join(chunks)
    return append_reference_section(body, plan_data, recalled)


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
