"""分块译文与计划合并为最终产出。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.chunking import ChunkSpec, chunk_body_path, chunk_plan_path
from lib.work_artifacts import load_plan


_REF_SECTION_RE = re.compile(r"\n\*参考著作[：:]\*[\s\S]*$", re.MULTILINE)


def _strip_ref_section(text: str) -> str:
    return _REF_SECTION_RE.sub("", text).strip()


def _dedupe_refs(refs: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for ref in refs:
        r = str(ref).strip()
        if not r or r in seen:
            continue
        seen.add(r)
        out.append(r)
    return out


def collect_reference_works(plans: List[Dict[str, Any]]) -> List[str]:
    refs: List[str] = []
    for plan in plans:
        for ref in plan.get("参考著作") or []:
            if isinstance(ref, str):
                refs.append(ref)
        for item in plan.get("外部补全") or []:
            if isinstance(item, dict) and item.get("采用") is not False:
                src = item.get("出处")
                if isinstance(src, str):
                    refs.append(src)
    return _dedupe_refs(refs)


def merge_chunk_plans(
    entry_id: str,
    recalled: Dict[str, Any],
    specs: List[ChunkSpec],
    work_dir: Path,
    entry_name: str,
) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    plans: List[Dict[str, Any]] = []
    for spec in specs:
        p = chunk_plan_path(entry_id, entry_name, work_dir, spec.chunk_id)
        ok, data, errs = load_plan(p)
        if not ok:
            errors.extend(errs)
            continue
        plans.append(data)

    if errors:
        return {}, errors

    checklist: List[Dict[str, Any]] = []
    supplements: List[Dict[str, Any]] = []
    external: List[Dict[str, Any]] = []
    structure: List[Dict[str, Any]] = []
    risks: List[str] = []

    for plan in plans:
        checklist.extend(plan.get("母本逐句清单") or [])
        supplements.extend(plan.get("索引补充处理") or [])
        external.extend(plan.get("外部补全") or [])
        for sec in plan.get("写作结构") or []:
            if isinstance(sec, dict):
                structure.append(sec)
        for r in plan.get("风险提示") or []:
            if isinstance(r, str) and r not in risks:
                risks.append(r)

    merged = {
        "史略ID": entry_id,
        "史略名称": recalled.get("史略名称"),
        "母本著作": recalled.get("母本著作"),
        "分块合并": True,
        "chunk_count": len(specs),
        "母本逐句清单": checklist,
        "索引补充处理": supplements,
        "外部补全": external,
        "写作结构": structure or [{"小节": "全文", "覆盖母本": ["见各分块"]}],
        "参考著作": collect_reference_works(plans),
        "风险提示": risks,
    }
    return merged, []


def merge_chunk_bodies(
    entry_id: str,
    entry_name: str,
    specs: List[ChunkSpec],
    work_dir: Path,
    reference_works: List[str],
) -> Tuple[str, List[str]]:
    errors: List[str] = []
    parts: List[str] = []
    for spec in specs:
        path = chunk_body_path(entry_id, entry_name, work_dir, spec.chunk_id)
        if not path.is_file():
            errors.append(f"缺少分块正文 chunk-{spec.chunk_id:02d}: {path}")
            continue
        body = _strip_ref_section(path.read_text(encoding="utf-8"))
        if not body.strip():
            errors.append(f"分块正文为空 chunk-{spec.chunk_id:02d}")
            continue
        parts.append(body.strip())

    if errors:
        return "", errors

    detail = "\n\n".join(parts)
    refs = _dedupe_refs(reference_works)
    if refs:
        lines = "\n".join(f"{i}. {r}" for i, r in enumerate(refs, start=1))
        detail = f"{detail}\n\n*参考著作：*\n{lines}"
    return detail, []


def write_final_output(
    entry_id: str,
    detail: str,
    output_file: Path,
    *,
    source_original: str | None = None,
    source_citation: str | None = None,
) -> None:
    payload: Dict[str, Any] = {"史略ID": entry_id, "翻译详情": detail}
    if source_original is not None:
        payload["史料原文"] = source_original
    if source_citation:
        payload["原文出处"] = source_citation
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
