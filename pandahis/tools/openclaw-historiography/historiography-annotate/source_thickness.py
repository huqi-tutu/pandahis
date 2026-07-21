"""史料厚度门：段落索引计字、母本 swap、merge 拒收判定。

SSOT：reference/史料厚度门规则.md
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from recall_paragraphs import load_paragraph_index, recall_range

THIN_SOURCE_THRESHOLD = 100
THIN_WARN_THRESHOLD = 100

_HAN_RE = re.compile(r"[\u4e00-\u9fff]")


def count_source_chars(text: str) -> int:
    """计汉字数（与厚度门 SSOT 一致）。"""
    return len(_HAN_RE.findall(text or ""))


def count_paragraph_range_chars(work: str, vol: str, para_from: int, para_to: int, *, index_root: Path | None = None) -> int:
    """按段落索引闭区间累加汉字数。"""
    idx = load_paragraph_index(work, str(vol).zfill(3))
    total = 0
    for _pid, text in recall_range(idx, int(para_from), int(para_to)):
        total += count_source_chars(text)
    return total


def count_source_dict_chars(src: dict[str, Any], *, index_root: Path | None = None) -> int:
    """单卷 skeleton source（merge 内部结构）计字。"""
    work, vol = src["work"], src["vol"]
    entry = src.get("entry") or {}
    total = 0
    for pg in entry.get("paragraphs") or []:
        pf = int(pg.get("paragraph_from", 0))
        pt = int(pg.get("paragraph_to", 0))
        if pf < 1 or pt < 1:
            continue
        total += count_paragraph_range_chars(work, vol, pf, pt, index_root=index_root)
    return total


def count_group_total_chars(sources: list[dict[str, Any]], *, index_root: Path | None = None) -> int:
    return sum(count_source_dict_chars(s, index_root=index_root) for s in sources)


def should_defer_glbl(sources: list[dict[str, Any]], *, index_root: Path | None = None) -> tuple[bool, int, str]:
    """
    返回 (是否拒收 GLBL, 合计汉字数, 原因码)。
    合计 < 阈值一律拒收（君王无例外）。
    """
    total = count_group_total_chars(sources, index_root=index_root)
    if total >= THIN_SOURCE_THRESHOLD:
        return False, total, ""
    return True, total, "thin_source_total_under_100"


def apply_thickness_mub_swap(sources: list[dict[str, Any]], *, index_root: Path | None = None) -> list[dict[str, Any]]:
    """规则 R2：rank 第一源（母本候选）<100 且另有 ≥100 源 → 升格为母本。"""
    if len(sources) < 2:
        return list(sources)
    ranked = list(sources)
    main_chars = count_source_dict_chars(ranked[0], index_root=index_root)
    if main_chars >= THIN_SOURCE_THRESHOLD:
        return ranked
    best_idx = None
    best_chars = main_chars
    for i, src in enumerate(ranked[1:], start=1):
        n = count_source_dict_chars(src, index_root=index_root)
        if n >= THIN_SOURCE_THRESHOLD and n > best_chars:
            best_idx = i
            best_chars = n
    if best_idx is None:
        return ranked
    swapped = list(ranked)
    swapped[0], swapped[best_idx] = swapped[best_idx], swapped[0]
    return swapped


def build_deferred_record(
    sources: list[dict[str, Any]],
    *,
    total_chars: int,
    reason: str,
) -> dict[str, Any]:
    """薄标注待补全注册表单条。"""
    primary = sources[0]
    entry = primary.get("entry") or {}
    source_refs = []
    for s in sources:
        source_refs.append(
            {
                "史略ID": s.get("eid"),
                "work": s.get("work"),
                "vol": s.get("vol"),
                "vol_name": s.get("vol_name"),
                "source_char_count": count_source_dict_chars(s),
                "skeleton_path": s.get("skeleton_path"),
            }
        )
    return {
        "defer_reason": reason,
        "source_char_count": total_chars,
        "recommended_path": "dynasty_knowledge_supplement",
        "史略ID": primary.get("eid"),
        "史略名称": entry.get("史略名称") or primary.get("name"),
        "史略分类": entry.get("史略分类") or primary.get("cat"),
        "朝代ID": entry.get("朝代ID") or "",
        "二级朝代坐标": entry.get("二级朝代坐标") or "",
        "主要史料出处": entry.get("主要史料出处") or "",
        "paragraphs": entry.get("paragraphs") or [],
        "skeleton_path": primary.get("skeleton_path"),
        "merge_sources": source_refs,
    }


def thin_registry_path(histograph_root: Path) -> Path:
    return histograph_root / "data" / "05工作流中间产物" / "薄标注待补全" / "registry.json"


def count_recalled_block_han(recalled_block: dict[str, Any]) -> int:
    total = 0
    for para in recalled_block.get("paragraphs") or []:
        total += count_source_chars(str(para.get("text") or ""))
    return total


def count_glbl_entry_han(entry: dict[str, Any]) -> dict[str, int]:
    """对已发布 GLBL 条目按 paragraphs[] 计汉字（母本/补充/合计）。"""
    from recall_paragraphs import recall_paragraph_block

    mother_work = str(entry.get("母本著作") or "").strip()
    total = mother = supplement = 0
    for block in entry.get("paragraphs") or []:
        rb = recall_paragraph_block(block)
        n = count_recalled_block_han(rb)
        total += n
        role = str(block.get("role") or "").strip()
        if not role:
            role = "母本" if str(block.get("work") or "") == mother_work else "补充"
        if role == "母本":
            mother += n
        else:
            supplement += n
    return {"total": total, "mother": mother, "supplement": supplement}


def classify_glbl_thickness(entry: dict[str, Any]) -> dict[str, Any]:
    """
    对已发布 GLBL 条目做厚度分类（只读，不改 ID）。
    返回计数字段 + verdict + recommended_action。
    """
    source_kind = str(entry.get("史略来源") or "史料提取").strip()
    if source_kind not in ("史料提取", "") or str(entry.get("母本著作") or "") == "朝代补全":
        return {
            "verdict": "skip_not_phase1",
            "recommended_action": "none",
            "reason": "非一期史料提取条目",
            "total": 0,
            "mother": 0,
            "supplement": 0,
        }

    if not entry.get("paragraphs"):
        return {
            "verdict": "error_no_paragraphs",
            "recommended_action": "manual_review",
            "reason": "无 paragraphs，无法计字",
            "total": 0,
            "mother": 0,
            "supplement": 0,
        }

    try:
        counts = count_glbl_entry_han(entry)
    except Exception as exc:
        return {
            "verdict": "error_recall_failed",
            "recommended_action": "manual_review",
            "reason": str(exc),
            "total": 0,
            "mother": 0,
            "supplement": 0,
        }

    total = counts["total"]
    mother = counts["mother"]
    supplement = counts["supplement"]

    if total >= THIN_SOURCE_THRESHOLD:
        action = "keep_translate"
        if mother < THIN_SOURCE_THRESHOLD and supplement >= THIN_SOURCE_THRESHOLD:
            verdict = "pass_swap_recommended"
            reason = f"合计{total}字达标，但母本仅{mother}字（历史 merge 未 swap）"
        else:
            verdict = "pass"
            reason = f"合计{total}字 ≥ {THIN_SOURCE_THRESHOLD}"
        return {**counts, "verdict": verdict, "recommended_action": action, "reason": reason}

    return {
        **counts,
        "verdict": "downgrade_recommended",
        "recommended_action": "defer_to_dynasty_supplement",
        "reason": f"合计{total}字 < {THIN_SOURCE_THRESHOLD}，建议降级：停止翻译/线上以朝代补全替代",
    }

