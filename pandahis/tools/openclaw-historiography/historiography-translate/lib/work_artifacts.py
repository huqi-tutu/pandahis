"""翻译中间产物：source plan / coverage sidecar。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.mother_sentences import (
    checklist_sentence_violations,
    extract_mother_sentences,
    mother_sentence_count,
    plan_min_sentence_ratio,
)
from lib.plan_postprocess import finalize_plan, validate_external_items
from lib.verify import sanitize_entry_name


def artifact_stem(entry_id: str, entry_name: str) -> str:
    return f"{entry_id}_{sanitize_entry_name(entry_name)}"


def plan_path(entry_id: str, entry_name: str, work_dir: Path) -> Path:
    return work_dir / f"{artifact_stem(entry_id, entry_name)}.plan.json"


def mother_draft_path(entry_id: str, entry_name: str, work_dir: Path) -> Path:
    return work_dir / f"{artifact_stem(entry_id, entry_name)}.mother.json"


def load_plan(path: Path) -> Tuple[bool, Dict[str, Any], List[str]]:
    if not path.is_file():
        return False, {}, [f"缺少 source plan: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {}, [f"source plan JSON 解析失败: {exc}"]
    return True, data, []


def load_normalized_plan(
    path: Path,
    recalled: Dict[str, Any] | None = None,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    ok, raw, errors = load_plan(path)
    if not ok:
        return False, {}, errors
    return True, finalize_plan(normalize_plan(raw, recalled), recalled), []


def normalize_plan(
    plan: Dict[str, Any],
    recalled: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """将 LLM 产出的 plan 规范为 verify 可接受的结构（不可变拷贝）。"""
    from llm.artifacts import unwrap_plan_payload

    out: Dict[str, Any] = unwrap_plan_payload(dict(plan))
    if recalled and not out.get("母本著作"):
        out["母本著作"] = recalled.get("母本著作")
    if recalled and not out.get("史略ID"):
        out["史略ID"] = recalled.get("史略ID")
    if recalled and not out.get("史略名称"):
        out["史略名称"] = recalled.get("史略名称")

    checklist = out.get("母本逐句清单") or []
    if isinstance(checklist, list):
        normed: List[Dict[str, Any]] = []
        for item in checklist:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if "编号" not in row and row.get("id"):
                row["编号"] = row["id"]
            if "原文摘句" not in row:
                row["原文摘句"] = (
                    row.get("text")
                    or row.get("原文")
                    or row.get("句子")
                    or ""
                )
            elif not str(row.get("原文摘句") or "").strip():
                row["原文摘句"] = (
                    row.get("text")
                    or row.get("原文")
                    or row.get("句子")
                    or ""
                )
            if "信息点" not in row and row.get("回译"):
                row["信息点"] = str(row["回译"]).strip()
            if "信息点" not in row and row.get("句子") and not row.get("原文摘句"):
                row["信息点"] = str(row.get("句子")).strip()
            normed.append(row)
        out["母本逐句清单"] = normed

    sup = out.get("索引补充处理")
    if isinstance(sup, dict):
        entries = sup.get("entries") or []
        if entries:
            out["索引补充处理"] = entries
        else:
            out["索引补充处理"] = [
                {
                    "处理": "去重不用",
                    "理由": str(sup.get("summary") or "本分块无索引补充"),
                }
            ]
    elif sup is None:
        out["索引补充处理"] = []

    ext = out.get("外部补全") or []
    if isinstance(ext, list):
        normed_ext: List[Dict[str, Any]] = []
        for item in ext:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if "母本锚点" not in row and row.get("锚点"):
                anchor = str(row["锚点"])
                row["母本锚点"] = (
                    anchor if anchor.endswith(("前", "后")) else f"{anchor} 后"
                )
            if "主题" not in row:
                row["主题"] = str(row.get("内容") or row.get("主题") or "")[:120]
            if "采用" not in row:
                row["采用"] = False
            normed_ext.append(row)
        out["外部补全"] = normed_ext

    structure = out.get("写作结构")
    if isinstance(structure, str) and structure.strip():
        out["写作结构"] = [{"小节": "本分块结构", "说明": structure.strip()}]
    elif not structure:
        out["写作结构"] = [{"小节": "本分块", "覆盖母本": ["见母本逐句清单"]}]
    elif isinstance(structure, dict):
        out["写作结构"] = [structure]

    refs = out.get("参考著作")
    if not isinstance(refs, list) or not refs:
        mother = str(out.get("母本著作") or "")
        if mother:
            out["参考著作"] = [f"{mother}·相关卷"]

    return out


def save_plan(path: Path, plan: Dict[str, Any], recalled: Dict[str, Any] | None = None, *, id_start: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = finalize_plan(normalize_plan(plan, recalled), recalled, id_start=id_start)
    for k in ("翻译详情", "content", "result", "output"):
        normalized.pop(k, None)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def mother_sentence_count(recalled: Dict[str, Any]) -> int:
    """兼容旧调用；与 extract_mother_sentences 一致。"""
    return max(len(extract_mother_sentences(recalled)), 1)


def verify_plan(
    entry_id: str,
    recalled: Dict[str, Any],
    path: Path,
) -> Tuple[bool, List[str]]:
    ok, plan, errors = load_plan(path)
    if not ok:
        return False, errors
    plan = finalize_plan(normalize_plan(plan, recalled), recalled, id_start=1)

    if plan.get("史略ID") != entry_id:
        errors.append(f"source plan 史略ID 不一致: {plan.get('史略ID')!r}")

    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        errors.append("source plan 缺少「母本逐句清单」")
    else:
        expected = len(extract_mother_sentences(recalled))
        min_required = max(1, int(expected * plan_min_sentence_ratio()))
        if len(checklist) < min_required:
            errors.append(
                f"母本逐句清单过少: {len(checklist)} < 母本 {expected} 句的 "
                f"{plan_min_sentence_ratio():.0%}（至少 {min_required} 条）"
            )
        errors.extend(checklist_sentence_violations(checklist))

    refs = plan.get("参考著作") or []
    if not isinstance(refs, list) or not refs:
        errors.append("source plan 缺少「参考著作」")

    supplements = plan.get("索引补充处理") or []
    supplement_blocks = [
        b for b in (recalled.get("blocks") or []) if b.get("role") == "补充"
    ]
    if supplement_blocks and not isinstance(supplements, list):
        errors.append("source plan「索引补充处理」必须为数组")
    if supplement_blocks and isinstance(supplements, list) and not supplements:
        errors.append("有索引补充 block，但 source plan 未说明补充处理")

    external = plan.get("外部补全") or []
    if isinstance(external, list):
        for i, item in enumerate(external):
            if not isinstance(item, dict):
                errors.append(f"外部补全[{i}] 不是对象")
                continue
            if item.get("采用") is False:
                continue
            if not item.get("出处"):
                errors.append(f"外部补全[{i}] 缺少「出处」")
    else:
        errors.append("source plan「外部补全」必须为数组")

    structure = plan.get("写作结构") or []
    if not isinstance(structure, list) or not structure:
        errors.append("source plan 缺少「写作结构」")

    errors.extend(validate_external_items(plan))

    return len(errors) == 0, errors


def verify_chunk_plan(
    entry_id: str,
    recalled_chunk: Dict[str, Any],
    path: Path,
    *,
    sentence_id_start: int,
    sentence_id_end: int,
) -> Tuple[bool, List[str]]:
    """分块计划校验：清单覆盖本分块母本句。"""
    ok, plan, errors = load_plan(path)
    if not ok:
        return False, errors

    plan = finalize_plan(
        normalize_plan(plan, recalled_chunk),
        recalled_chunk,
        id_start=sentence_id_start,
    )

    if plan.get("史略ID") != entry_id:
        errors.append(f"分块 plan 史略ID 不一致: {plan.get('史略ID')!r}")

    checklist = plan.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        errors.append("分块 plan 缺少「母本逐句清单」")
    else:
        expected = len(extract_mother_sentences(recalled_chunk))
        min_required = max(1, int(expected * plan_min_sentence_ratio()))
        if len(checklist) < min_required:
            errors.append(
                f"分块清单过少: {len(checklist)} < 本分块母本 {expected} 句的 "
                f"{plan_min_sentence_ratio():.0%}（至少 {min_required} 条）"
            )
        errors.extend(checklist_sentence_violations(checklist))
        first = str((checklist[0] or {}).get("编号") or (checklist[0] or {}).get("id") or "")
        last = str((checklist[-1] or {}).get("编号") or "")
        exp_first = f"M{sentence_id_start:03d}"
        exp_last = f"M{sentence_id_end:03d}"
        if first and not first.startswith("M"):
            errors.append(f"分块清单编号格式异常: {first}")
        if first and first != exp_first and sentence_id_start > 1:
            errors.append(f"分块清单应从 {exp_first} 起，实际 {first}")

    structure = plan.get("写作结构") or []
    if not isinstance(structure, list) or not structure:
        errors.append("分块 plan 缺少「写作结构」")

    return len(errors) == 0, errors
