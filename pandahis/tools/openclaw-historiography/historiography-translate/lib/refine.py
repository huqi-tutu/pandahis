"""局部更新翻译：按 scope 重跑指定片段，不全量重写。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.attribution import apply_attribution_fixes
from lib.config import default_index_path, paths
from lib.openclaw import (
    build_translate_enrich_prompt,
    build_translate_mother_prompt,
    run_agent_turn,
)
from lib.plan_postprocess import finalize_plan, plan_for_enrich_phase, plan_for_mother_phase
from lib.recall import recall_entry
from lib.runner import _ensure_work_dir
from lib.verify import load_output, resolve_output_path, verify_output
from lib.work_artifacts import mother_draft_path, plan_path


SCOPE_CHOICES = ("intro", "mother", "tail", "full", "attribution")


def _split_body_refs(detail: str) -> Tuple[str, str]:
    if "*参考著作*" in detail:
        body, ref = detail.split("*参考著作*", 1)
        return body.strip(), "*参考著作*" + ref
    if "参考著作" in detail:
        parts = detail.rsplit("参考著作", 1)
        return parts[0].strip(), "参考著作" + parts[1]
    return detail.strip(), ""


def _intro_paragraphs(body: str, n: int = 2) -> str:
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return "\n\n".join(paras[:n])


def _tail_paragraphs(body: str, n: int = 2) -> str:
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if len(paras) <= n:
        return body
    return "\n\n".join(paras[-n:])


def merge_refined_detail(
    original: str,
    refined: str,
    *,
    scope: str,
) -> str:
    orig_body, orig_refs = _split_body_refs(original)
    new_body, new_refs = _split_body_refs(refined)

    if scope == "intro":
        orig_paras = [p.strip() for p in orig_body.split("\n\n") if p.strip()]
        new_paras = [p.strip() for p in new_body.split("\n\n") if p.strip()]
        if len(orig_paras) <= 2:
            merged_body = new_body
        else:
            merged_body = "\n\n".join([*new_paras[:2], *orig_paras[2:]])
    elif scope == "tail":
        orig_paras = [p.strip() for p in orig_body.split("\n\n") if p.strip()]
        new_paras = [p.strip() for p in new_body.split("\n\n") if p.strip()]
        keep_n = max(1, len(orig_paras) - len(new_paras))
        merged_body = "\n\n".join([*orig_paras[:keep_n], *new_paras])
    else:
        merged_body = new_body

    refs = new_refs or orig_refs
    return merged_body + ("\n\n" + refs if refs else "")


def _extract_json(text: str) -> Dict[str, Any] | None:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s : e + 1] if s != -1 and e > s else None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def refine_entry(
    entry_id: str,
    *,
    scope: str = "full",
    instructions: str = "",
    index_path: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
    use_llm: bool = True,
) -> Tuple[bool, str]:
    if scope not in SCOPE_CHOICES and not scope.startswith("mother"):
        return False, f"未知 scope: {scope}"

    idx = index_path or default_index_path()
    recalled = recall_entry(entry_id, index_path=idx)
    entry_name = str(recalled.get("史略名称") or "")
    out_dir = output_dir or paths()["translate_output"]
    ok, data, errs = load_output(entry_id, out_dir, entry_name)
    if not ok:
        return False, "; ".join(errs)

    work_dir = _ensure_work_dir()
    pf = plan_path(entry_id, entry_name, work_dir)
    plan: Dict[str, Any] = {}
    if pf.is_file():
        plan = json.loads(pf.read_text(encoding="utf-8"))
    plan = finalize_plan(plan, recalled)

    detail = str(data.get("翻译详情") or "")

    if scope == "attribution":
        fixed, changes = apply_attribution_fixes(detail, recalled, plan)
        if dry_run:
            return True, f"dry-run attribution: {changes}"
        data["翻译详情"] = fixed
        target = resolve_output_path(entry_id, out_dir, entry_name)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True, f"归因修复: {changes}"

    if not use_llm:
        return False, "非 attribution scope 需要 LLM（去掉 --no-llm）"

    mother_file = mother_draft_path(entry_id, entry_name, work_dir)
    mother_text = ""
    if mother_file.is_file():
        md = json.loads(mother_file.read_text(encoding="utf-8"))
        mother_text = str(md.get("母本顺译") or "")

    output_file = resolve_output_path(entry_id, out_dir, entry_name)
    recalled_json = json.dumps(recalled, ensure_ascii=False, indent=2)
    plan_json = json.dumps(
        plan_for_enrich_phase(plan) if scope in ("intro", "tail", "full") else plan_for_mother_phase(plan),
        ensure_ascii=False,
        indent=2,
    )

    extra = (
        f"\n\n## 局部更新 scope: {scope}\n"
        f"## 用户意见\n{instructions or '按最新规则优化，避免引入与母本重复、压缩碎引号、禁释通识字'}\n"
        f"## 当前正文片段（待改）\n"
        f"{_intro_paragraphs(detail.split('*参考著作*')[0], 3) if scope == 'intro' else detail[:2500]}\n"
    )

    if scope.startswith("mother"):
        prompt = build_translate_mother_prompt(
            entry_id,
            recalled,
            recalled_json,
            plan_json,
            mother_file,
        ) + extra
    else:
        prompt = build_translate_enrich_prompt(
            entry_id,
            recalled,
            recalled_json,
            plan_json,
            mother_text or detail,
            output_file,
        ) + extra

    if dry_run:
        return True, f"dry-run refine {scope}: prompt {len(prompt)} 字"

    session_id = f"refine-{entry_id}-{scope}"
    result = run_agent_turn(prompt, session_id=session_id, timeout_sec=900)
    raw = str(result.get("result") or "").strip()
    obj = _extract_json(raw)
    if not obj:
        return False, "LLM 未返回有效 JSON"

    if scope.startswith("mother") and obj.get("母本顺译"):
        mother_file.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return True, f"已更新母本顺译 → {mother_file}；请 run-one --from-phase phase2"

    new_detail = str(obj.get("翻译详情") or "").strip()
    if not new_detail:
        return False, "refine 输出缺少翻译详情"

    merged = merge_refined_detail(detail, new_detail, scope=scope)
    merged, _ = apply_attribution_fixes(merged, recalled, plan)
    data["翻译详情"] = merged
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    v_ok, v_errs = verify_output(entry_id, recalled, out_dir, plan=plan)
    if not v_ok:
        return True, f"已写回但 verify 有警告: {'; '.join(v_errs[:3])}"
    return True, f"refine {scope} 完成 → {output_file}"
