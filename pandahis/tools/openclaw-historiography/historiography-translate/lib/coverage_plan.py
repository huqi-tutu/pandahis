"""Coverage ledger（程序 M 清单）与 enrich plan（D 前置，基于 C 初稿重写）。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.enrich_gap import (
    build_enrich_gap_ledger,
    merge_enrich_plan_with_seed,
    seed_index_supplements_for_enrich,
)
from lib.fingerprint import recalled_summary
from lib.openclaw import build_enrich_plan_prompt, run_agent_turn
from lib.plan_postprocess import finalize_plan, plan_for_enrich_phase
from lib.source_citation import display_work_name, native_volume_from_source_file
from lib.stall_watch import touch_heartbeat
from lib.work_artifacts import load_normalized_plan, load_plan, save_plan, verify_plan


def ab_split_required(recalled: Dict[str, Any], plan_data: Dict[str, Any]) -> bool:
    """超过阈值则 A/B 拆分，否则合并为单次 AB。"""
    checklist = plan_data.get("母本逐句清单") or []
    m_count = len(checklist) if isinstance(checklist, list) else 0
    m_threshold = max(1, int(os.environ.get("TRANSLATE_AB_SPLIT_M", "15")))
    if m_count > m_threshold:
        return True
    chars = 0
    for block in recalled.get("blocks") or []:
        if block.get("role") != "母本":
            continue
        for para in block.get("paragraphs") or []:
            chars += len(str(para.get("text") or ""))
    char_threshold = max(1000, int(os.environ.get("TRANSLATE_AB_SPLIT_CHARS", "4000")))
    return chars > char_threshold


def build_coverage_ledger(recalled: Dict[str, Any]) -> Dict[str, Any]:
    """程序生成 A/B 阶段用的 coverage ledger（无 LLM 外部补全）。"""
    entry_id = str(recalled.get("史略ID") or "")
    name = str(recalled.get("史略名称") or "")
    mother_work = str(recalled.get("母本著作") or "")
    ref = _mother_reference(recalled, mother_work)

    plan: Dict[str, Any] = {
        "史略ID": entry_id,
        "史略名称": name,
        "母本著作": mother_work,
        "母本逐句清单": [],
        "外部补全": [],
        "索引补充处理": [],
        "写作结构": [{"小节": "全篇", "覆盖母本": ["见母本逐句清单"]}],
        "参考著作": [ref] if ref else [],
        "_ledger_meta": {"source": "programmatic", "phase": "coverage"},
    }
    return finalize_plan(plan, recalled, skip_index_inject=True)


def _mother_reference(recalled: Dict[str, Any], mother_work: str) -> str:
    src = str(recalled.get("主要史料出处") or "").strip()
    if src.startswith("《") and src.endswith("》"):
        return src
    for block in recalled.get("blocks") or []:
        if block.get("role") != "母本":
            continue
        work = display_work_name(str(block.get("work") or mother_work))
        vol = str(block.get("volume") or "").strip()
        if not vol:
            vol = native_volume_from_source_file(str(block.get("source_file") or ""))
        if work and vol:
            return f"《{work}·{vol}》"
        if work:
            return f"《{work}》"
    core = display_work_name(mother_work)
    return f"《{core}》" if core else ""


def ensure_coverage_ledger(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """落盘 coverage ledger；M 清单与 recall 不一致则重建。"""
    if plan_file.is_file():
        ok, plan_data, _ = load_normalized_plan(plan_file, recalled)
        if ok and not _ledger_needs_rebuild(plan_data, recalled):
            return True, plan_data, []

    ledger = build_coverage_ledger(recalled)
    save_plan(plan_file, ledger, recalled)
    ok, plan_data, errs = load_normalized_plan(plan_file, recalled)
    if not ok:
        return False, {}, errs
    v_ok, v_errs = verify_plan(entry_id, recalled, plan_file)
    return v_ok, plan_data, v_errs


def _ledger_needs_rebuild(plan_data: Dict[str, Any], recalled: Dict[str, Any]) -> bool:
    from lib.mother_sentences import extract_mother_sentences

    expected = len(extract_mother_sentences(recalled))
    actual = len(plan_data.get("母本逐句清单") or [])
    return bool(expected and actual != expected)


def ensure_enrich_plan(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
    *,
    baseline_body: str,
    work_dir: Path,
    session_id: str,
    use_llm: bool = True,
    baseline_file: Path | None = None,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """baseline 后：基于 C 初稿**重写** enrich plan（清空旧外部补全）。"""
    ok, ledger, errs = load_normalized_plan(plan_file, recalled)
    if not ok:
        return False, {}, errs

    if not use_llm:
        return True, ledger, []

    gap_ledger = build_enrich_gap_ledger(baseline_body, ledger, recalled)
    seed_index = seed_index_supplements_for_enrich(ledger, recalled)
    gap_path = plan_file.with_suffix(".enrich-gap.json")
    gap_path.write_text(
        __import__("json").dumps(gap_ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    prompt = build_enrich_plan_prompt(
        entry_id,
        recalled,
        recalled_summary(recalled),
        baseline_body,
        plan_file,
        baseline_file=baseline_file,
        gap_ledger=gap_ledger,
        seed_index=seed_index,
    )
    print(f"🧭 重写 enrich plan（D 前置，基于 C 初稿）→ {plan_file.name}", flush=True)
    touch_heartbeat(work_dir, entry_id, stage="enrich_plan")
    run_agent_turn(
        prompt,
        session_id=f"{session_id}-enrich-plan",
        timeout_sec=900,
        artifact_paths={"plan": plan_file},
    )

    ok_load, raw, _ = load_plan(plan_file)
    if not ok_load:
        return False, {}, ["enrich plan LLM 未落盘"]

    merged = dict(ledger)
    merged["外部补全"] = []
    merged["索引补充处理"] = []
    merged = merge_enrich_plan_with_seed(
        merged,
        raw,
        seed_index=seed_index,
        gap_ledger=gap_ledger,
    )
    save_plan(plan_file, merged, recalled, skip_index_inject=True)
    ok, plan_data, errs = load_normalized_plan(plan_file, recalled)
    return ok, plan_data, errs


def plan_json_for_phase_a(plan_data: Dict[str, Any]) -> str:
    import json

    from lib.plan_postprocess import plan_for_mother_phase

    return json.dumps(plan_for_mother_phase(plan_data), ensure_ascii=False, indent=2)


def plan_json_for_phase_d(plan_data: Dict[str, Any]) -> str:
    import json

    return json.dumps(plan_for_enrich_phase(plan_data), ensure_ascii=False, indent=2)
