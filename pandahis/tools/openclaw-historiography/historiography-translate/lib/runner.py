"""翻译任务编排：bootstrap / recall / run / verify。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib import db
from lib.config import (
    default_index_path,
    paths,
    resolve_output_dir,
    translation_version_for_output_dir,
)
from lib.plan_postprocess import plan_for_enrich_phase, plan_for_mother_phase
from lib.prose_sanitize import polish_enrich_file, polish_enrich_file_full, polish_mother_file, sanitize_mother_detail
from lib.attribution import apply_attribution_fixes
from lib.stall_watch import (
    diagnose_stall,
    is_stalled,
    read_heartbeat,
    stall_threshold_sec,
    touch_heartbeat,
)
from lib.mother_sentences import extract_mother_sentences
from lib.fingerprint import recalled_summary, source_fingerprint
from lib.index_filter import filter_pending_jobs
from lib.translate_scope import (
    compute_progress,
    format_progress_report,
    is_translate_required,
    load_dynasty_detail_ids,
    load_translated_ids,
)
from lib.openclaw import (
    build_source_plan_prompt,
    build_translate_enrich_prompt,
    build_translate_mother_prompt,
    build_translate_prompt,
    make_session_id,
    run_agent_turn,
)
from lib.recall import RecallError, load_global_index, recall_entry
from lib.source_text import attach_source_original, build_source_original
from lib.aggregate import rebuild_aggregate
from lib.chunk_runner import run_chunked_pipeline, should_use_chunked_flow
from lib.chunking import build_chunk_specs, needs_chunked_mode
from lib.verify import (
    collect_must_phrase_misses,
    load_output,
    output_path,
    verify_enrich_batch_slice,
    verify_enrich_draft,
    verify_mother_draft,
    verify_output,
    verify_source_thickness,
)
from lib.repair_ticket import save_repair_ticket
from shared.qa_repair import classify_translate_failure, format_retry_feedback
from lib.work_artifacts import (
    baseline_draft_path,
    load_normalized_plan,
    load_plan,
    mother_draft_path,
    plan_path,
    save_plan,
    verify_plan,
)
from lib.pipeline_abcd import abcd_pipeline_enabled, run_abcd_baseline, baseline_body_for_enrich
from lib.pipeline_streamlined import streamlined_pipeline_enabled, run_streamlined_pipeline
from lib.coverage_plan import ensure_coverage_ledger, ensure_enrich_plan, plan_json_for_phase_d


def _ensure_output_dir(
    *,
    index_path: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    return resolve_output_dir(index_path=index_path, output_dir=output_dir)


def _dynasty_detail_aggregate_path() -> Path | None:
    """查找朝代知识详情汇总 JSON（与 translate 共用 historical_box_detail 表）。"""
    from pathlib import Path

    # 从 translate_output 反推数据根目录
    out = paths()["translate_output"]  # e.g. data/04史料翻译
    candidate = Path(out.parent, "06朝代知识补全", "详情", "朝代知识详情_汇总.json")
    return candidate if candidate.is_file() else None


def _ensure_work_dir() -> Path:
    work = paths()["translate_work"]
    work.mkdir(parents=True, exist_ok=True)
    return work


def _plan_json_text(path: Path) -> str:
    ok, data, _ = load_plan(path)
    if not ok:
        return "{}"
    return json.dumps(data, ensure_ascii=False, indent=2)


def bootstrap(*, index_path: Path | None = None, force: bool = False) -> int:
    db.init_schema()
    idx_path = index_path or default_index_path()
    index = load_global_index(idx_path)
    entries = index.get("entries") or []
    created = 0
    skipped_supplement = 0
    for e in entries:
        eid = e.get("史略ID")
        if not eid:
            continue
        if not is_translate_required(e):
            skipped_supplement += 1
            continue
        paras = e.get("paragraphs") or []
        para_count = int(e.get("段落域数") or 0)
        if not para_count and paras:
            para_count = sum(
                int(p.get("paragraph_to", 0)) - int(p.get("paragraph_from", 0)) + 1
                for p in paras
            )
        db.upsert_job(
            eid,
            entry_name=e.get("史略名称") or "",
            priority=e.get("优先级") or "",
            block_count=len(paras),
            paragraph_count=para_count,
            status="pending" if force else None,
            reset_status=force,
        )
        created += 1
    db.set_meta("index_path", str(idx_path))
    db.set_meta("index_entry_count", str(len(entries)))
    print(
        f"✅ bootstrap: {created} 条翻译任务 ← {idx_path}"
        f"（跳过朝代补全 {skipped_supplement} 条）"
    )
    return created


def cmd_recall(entry_id: str, *, index_path: Path | None = None) -> Dict[str, Any]:
    recalled = recall_entry(entry_id, index_path=index_path)
    fp = source_fingerprint(recalled)
    print(
        f"📎 {recalled['史略ID']} {recalled['史略名称']} "
        f"({recalled['block_count']} 域 / {recalled['paragraph_count']} 段) "
        f"fp={fp}"
    )
    for b in recalled["blocks"]:
        print(
            f"  [{b['role']}] {b['work']} 卷{b['vol']} "
            f"{b.get('volume', '')} P{b['paragraph_from']}-P{b['paragraph_to']}"
        )
    if needs_chunked_mode(recalled):
        specs = build_chunk_specs(recalled)
        print(f"  📦 将启用分块模式: {len(specs)} 块")
    return recalled


def _guard_plan_inflation(
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
) -> List[str]:
    """plan 清单须与 recall 分句一一对应，否则禁止进入 Phase1/2。"""
    expected = len(extract_mother_sentences(recalled))
    actual = len(plan_data.get("母本逐句清单") or [])
    if expected and actual != expected:
        return [
            f"plan 清单条数与 recall 不一致: {actual} != {expected}（疑似 plan 膨胀/缩水，已阻断）"
        ]
    return []


def _should_skip(
    entry_id: str,
    recalled: Dict[str, Any],
    job: Optional[Dict[str, Any]],
    plan_file: Path,
    *,
    out_dir: Path,
) -> bool:
    fp = source_fingerprint(recalled)
    entry_name = str(
        recalled.get("史略名称") or (job.get("entry_name") if job else "") or ""
    )
    ok, data, _ = load_output(entry_id, out_dir, entry_name)
    if not ok:
        return False
    plan_ok, plan, _ = load_plan(plan_file)
    if not plan_ok:
        return False
    if job and job.get("source_fingerprint") == fp and job.get("status") == "done":
        v_ok, _, _ = verify_output(entry_id, recalled, out_dir, plan=plan)
        return v_ok
    v_ok, _, _ = verify_output(entry_id, recalled, out_dir, plan=plan)
    if v_ok:
        wc = len((data.get("翻译详情") or ""))
        db.update_job(
            entry_id,
            status="done",
            source_fingerprint=fp,
            output_word_count=wc,
            detail="skipped: valid output exists",
        )
        return True
    return False


def ensure_source_plan(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
    *,
    session_id: str,
    work_dir: Path | None = None,
    dry_run: bool = False,
    use_llm: bool = True,
) -> tuple[bool, List[str]]:
    ok, errors = verify_plan(entry_id, recalled, plan_file)
    if ok:
        ok_load, raw, _ = load_plan(plan_file)
        if ok_load:
            save_plan(plan_file, raw, recalled)
        return True, []

    prompt = build_source_plan_prompt(
        entry_id, recalled, recalled_summary(recalled), plan_file
    )
    if dry_run:
        print(f"🧭 source-plan dry-run → {plan_file}")
        print(f"   plan prompt 约 {len(prompt)} 字符")
        if errors:
            print("   当前计划缺失/无效: " + "; ".join(errors[:3]))
        return False, errors

    if not use_llm:
        return False, errors

    print(f"🧭 生成 source plan → {plan_file}", flush=True)
    wd = work_dir or plan_file.parent
    touch_heartbeat(wd, entry_id, stage="plan", detail=str(plan_file.name))
    _llm_turn(
        wd,
        entry_id,
        "plan",
        prompt,
        session_id=session_id,
        timeout_sec=900,
        artifact_paths={"plan": plan_file},
    )
    ok_load, plan_data, _ = load_plan(plan_file)
    if ok_load:
        save_plan(plan_file, plan_data, recalled)
    return verify_plan(entry_id, recalled, plan_file)


def _plan_json_for_mother(plan_data: Dict[str, Any]) -> str:
    return json.dumps(plan_for_mother_phase(plan_data), ensure_ascii=False, indent=2)


def _plan_json_for_enrich(plan_data: Dict[str, Any]) -> str:
    return json.dumps(plan_for_enrich_phase(plan_data), ensure_ascii=False, indent=2)


def _phase1_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE1_MAX_RETRIES", "2")))


def _repair_feedback_suffix() -> str:
    fb = (os.environ.get("TRANSLATE_REPAIR_FEEDBACK") or "").strip()
    if not fb:
        return ""
    return f"\n\n--- 修复工单反馈（须逐项修正）---\n{fb}\n"


def _record_translate_failure(
    entry_id: str,
    entry_name: str,
    *,
    stage: str,
    errors: List[str],
    work_dir: Path,
    fail_count: int,
) -> Tuple[int, Any]:
    """写 repair 工单并返回 (exit_code, plan)。exit_code: 2=转线, 1=失败。"""
    plan = classify_translate_failure(errors, stage=stage, fail_count=fail_count)
    ticket = save_repair_ticket(
        work_dir,
        entry_id=entry_id,
        entry_name=entry_name,
        stage=stage,
        errors=errors,
        plan=plan,
        fail_count=fail_count,
    )
    print(f"📋 修复工单 → {ticket.name}（{plan.root_cause} / {plan.disposition}）", flush=True)
    if plan.disposition == "route_pipeline":
        print(f"↪ 转线：{plan.route_to or 'dynasty_supplement'}", flush=True)
        if plan.next_command:
            print(f"   建议：{plan.next_command}", flush=True)
        return 2, plan
    print(
        f"💡 将自动重试：{plan.disposition} / {plan.action}"
        + (f"（{plan.root_cause}）" if plan.root_cause else ""),
        flush=True,
    )
    return 1, plan


def _phase1_retry_temperature() -> float:
    return float(os.environ.get("TRANSLATE_PHASE1_RETRY_TEMPERATURE", "0.4"))


def _apply_attribution_polish(
    target: Path,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
) -> None:
    """Phase2 落盘后：归因清洗 + 本传缺漏退场补全。"""
    if not target.is_file():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    detail = str(data.get("翻译详情") or "")
    fixed, changes = apply_attribution_fixes(detail, recalled, plan_data)
    if not changes:
        return
    data["翻译详情"] = fixed
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   🔧 成稿后处理: {', '.join(changes[:5])}", flush=True)


def _phase2_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE2_MAX_RETRIES", "3")))


def _verify_enrich_with_autofix(
    entry_id: str,
    recalled: Dict[str, Any],
    target: Path,
    plan_data: Dict[str, Any],
    *,
    baseline_detail: str = "",
) -> Tuple[bool, List[str]]:
    """Phase2 质检；落盘后先跑归因脚本清洗再验。"""
    _apply_attribution_polish(target, recalled, plan_data)
    return verify_enrich_draft(
        entry_id,
        recalled,
        target,
        plan=plan_data,
        baseline_detail=baseline_detail,
    )


def _mother_batch_size() -> int:
    """M 清单超过此数则 Phase1 分批顺译；0 表示关闭分批。"""
    return max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def _write_mother_draft(path: Path, entry_id: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"史略ID": entry_id, "母本顺译": body}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _run_phase1_mother(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str]]:
    """Phase1 母本顺译；M 过多时自动分批。"""
    checklist = plan_data.get("母本逐句清单") or []
    batch_size = _mother_batch_size()
    if not isinstance(checklist, list) or batch_size <= 0 or len(checklist) <= batch_size:
        return _run_phase1_mother_single(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_file=mother_file,
            work_dir=work_dir,
            session_id=session_id,
        )

    parts: List[str] = []
    batches = [
        checklist[i : i + batch_size] for i in range(0, len(checklist), batch_size)
    ]
    print(
        f"📦 Phase1 分批顺译 {entry_id}：{len(checklist)} 句 → {len(batches)} 批",
        flush=True,
    )
    for bi, batch_items in enumerate(batches, start=1):
        batch_plan = {**plan_data, "母本逐句清单": batch_items}
        batch_file = mother_file.with_name(
            f"{mother_file.stem}-b{bi:02d}{mother_file.suffix}"
        )
        sid0 = batch_items[0].get("编号") if batch_items else "?"
        sid1 = batch_items[-1].get("编号") if batch_items else "?"
        label = f"第 {bi}/{len(batches)} 批（{sid0}–{sid1}）"
        ok, errs = _run_phase1_mother_single(
            entry_id,
            recalled,
            plan_data=batch_plan,
            mother_file=batch_file,
            work_dir=work_dir,
            session_id=f"{session_id}-mother-b{bi}",
            batch_label=label,
        )
        if not ok:
            return False, [f"Phase1 {label}: {e}" for e in errs]
        parts.append(_load_mother_text(batch_file))

    combined = "\n\n".join(p for p in parts if p.strip())
    _write_mother_draft(mother_file, entry_id, sanitize_mother_detail(combined))
    touch_heartbeat(work_dir, entry_id, stage="verify_mother")
    return verify_mother_draft(entry_id, recalled, mother_file, plan=plan_data)


def _run_phase1_mother_single(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_file: Path,
    work_dir: Path,
    session_id: str,
    batch_label: str = "",
) -> Tuple[bool, List[str]]:
    mother_plan_json = _plan_json_for_mother(plan_data)
    verify_plan_data = {"母本逐句清单": plan_data.get("母本逐句清单") or []}
    m_errs: List[str] = []
    mother_detail = ""
    checklist = plan_data.get("母本逐句清单") or []
    max_retries = 2 if len(checklist) > 40 else _phase1_max_retries()  # D: 长条目最多重试2次
    for attempt in range(max_retries + 1):
        retry_note = ""
        if attempt > 0 and m_errs:
            plan = classify_translate_failure(m_errs, stage="phase1", fail_count=attempt)
            miss_lines = collect_must_phrase_misses(
                mother_detail, verify_plan_data, batch_mode=bool(batch_label)
            )
            retry_note = (
                "\n\n--- 上轮 Phase1 质检失败，须逐项修正 ---\n"
                + format_retry_feedback(plan, m_errs)
            )
            if miss_lines:
                retry_note += (
                    "\n\n--- 以下原词须在译文中自然出现（写入白话叙述即可）---\n"
                    + "\n".join(miss_lines)
                )
        batch_note = ""
        if batch_label:
            batch_note = (
                f"\n\n--- {batch_label}：只译下列 M 清单，保留句序与原词锚点 ---\n"
            )
        m_prompt = (
            build_translate_mother_prompt(
                entry_id,
                recalled,
                recalled_summary(recalled),
                mother_plan_json,
                mother_file,
            )
            + batch_note
            + retry_note
            + _repair_feedback_suffix()
        )
        title = batch_label or f"Phase1 母本顺译 {entry_id} → {mother_file.name}"
        print(
            title + (f"（重试 {attempt}/{max_retries}）" if attempt else ""),
            flush=True,
        )
        _llm_turn(
            work_dir,
            entry_id,
            "mother",
            m_prompt,
            session_id=f"{session_id}-r{attempt}",
            timeout_sec=900,
            artifact_paths={"output": mother_file},
            temperature=_phase1_retry_temperature() if attempt > 0 else None,
        )
        if not mother_file.is_file():
            return False, ["Phase1: LLM 未落盘母本顺译"]
        if polish_mother_file(mother_file):
            print("   🔧 已校正 Phase1 引号形态", flush=True)
        mother_detail = _load_mother_text(mother_file)
        touch_heartbeat(
            work_dir, entry_id, stage="verify_mother", detail=batch_label or ""
        )
        m_ok, m_errs = verify_mother_draft(
            entry_id,
            recalled,
            mother_file,
            plan=verify_plan_data,
            batch_mode=bool(batch_label),
            batch_label=batch_label,
        )
        if m_ok:
            if batch_label:
                touch_heartbeat(
                    work_dir, entry_id, stage="mother_batch_done", detail=batch_label
                )
            return True, []
        print(f"⚠️ Phase1 未通过: {m_errs[0] if m_errs else '?'}", flush=True)
        if batch_label and attempt < max_retries:
            from lib.coverage_info import build_coverage_units
            from lib.coverage_ledger import clear_ledger_labels

            labels = [u.label for u in build_coverage_units(checklist)]
            clear_ledger_labels(work_dir, entry_id, labels)
    return False, [f"Phase1: {e}" for e in m_errs]


def _llm_turn(
    work_dir: Path,
    entry_id: str,
    stage: str,
    prompt: str,
    *,
    session_id: str,
    timeout_sec: int,
    artifact_paths: Dict[str, Path] | None = None,
    temperature: float | None = None,
) -> None:
    touch_heartbeat(work_dir, entry_id, stage=f"llm_{stage}", detail=session_id)
    run_agent_turn(
        prompt,
        session_id=session_id,
        timeout_sec=timeout_sec,
        artifact_paths=artifact_paths,
        temperature=temperature,
    )
    touch_heartbeat(work_dir, entry_id, stage=f"done_{stage}")


def _check_stall_or_warn(work_dir: Path, entry_id: str, entry_name: str) -> None:
    stalled, msg = is_stalled(work_dir, entry_id)
    if not stalled:
        return
    print(f"⚠️ 卡顿检测: {msg}", flush=True)
    for hint in diagnose_stall(work_dir, entry_id, entry_name)[:5]:
        print(f"   · {hint}", flush=True)


def _two_phase_enabled() -> bool:
    return os.environ.get("TRANSLATE_TWO_PHASE", "1") != "0"


def _use_chunked_pipeline(recalled: Dict[str, Any]) -> bool:
    """两阶段默认优先；仅 TRANSLATE_USE_CHUNK=1 时长条目走分块叙述模式。"""
    if _two_phase_enabled() and os.environ.get("TRANSLATE_USE_CHUNK", "0") != "1":
        return False
    return should_use_chunked_flow(recalled)


def _run_phase2_enrich_batched(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_file: Path,
    target: Path,
    session_id: str,
    work_dir: Path,
    entry_name: str,
    t0: float,
    baseline_file: Path | None = None,
) -> Tuple[bool, List[str], float]:
    """长稿 D 阶段：按 baseline 整篇段落分批 enrich，再合并终稿。"""
    from lib.phase2_batch import (
        batch_context_prefix,
        build_baseline_batch_enrich_prompt,
        build_batch_enrich_prompt,
        discover_mother_batches,
        merge_enrich_batches,
        phase2_batch_char_threshold,
        split_detail_paragraph_batches,
    )
    from lib.pipeline_abcd import baseline_body_for_enrich

    threshold = phase2_batch_char_threshold()
    use_baseline = bool(baseline_file and baseline_file.is_file())
    baseline_detail = baseline_body_for_enrich(baseline_file) if use_baseline else ""

    if use_baseline:
        batch_texts = split_detail_paragraph_batches(baseline_detail, threshold)
        batch_specs: List[tuple[str, Path, str]] = []
        for bi, text in enumerate(batch_texts, start=1):
            batch_target = baseline_file.with_name(
                f"{baseline_file.stem}-d-b{bi:02d}.enrich.json"
            )
            batch_specs.append((text, batch_target, f"第 {bi}/{len(batch_texts)} 批"))
        mode_label = "baseline 整篇"
    else:
        batches = discover_mother_batches(mother_file)
        batch_specs = [
            (
                _load_mother_text(batch_file),
                batch_file.with_suffix(".enrich.json"),
                f"第 {bi}/{len(batches)} 批",
            )
            for bi, batch_file in enumerate(batches, start=1)
        ]
        mode_label = "母本"

    total = len(batch_specs)
    print(
        f"📦 D 分批 enrich {entry_id}：{total} 批"
        f"（{mode_label} >{threshold} 字，避免单次输出截断）",
        flush=True,
    )
    parts: List[str] = []
    prev_batch = ""
    for bi, (batch_text, batch_target, label) in enumerate(batch_specs, start=1):
        batch_ok = False
        batch_errs: List[str] = []
        if batch_target.is_file():
            slice_ok, slice_errs = verify_enrich_batch_slice(
                entry_id,
                recalled,
                batch_target,
                batch_mother_text=batch_text,
                batch_label=label,
            )
            if slice_ok:
                print(
                    f"⏭️ D {label} 沿用已有 {batch_target.name}",
                    flush=True,
                )
                parts.append(_load_mother_text(batch_target))
                prev_batch = batch_text
                continue
        for attempt in range(_phase2_max_retries() + 1):
            retry_note = ""
            if attempt > 0 and batch_errs:
                plan_fb = classify_translate_failure(
                    batch_errs, stage="phase2", fail_count=attempt
                )
                retry_note = (
                    "\n\n--- 上轮 D 质检失败，须修正 ---\n"
                    + format_retry_feedback(plan_fb, batch_errs)
                )
            if use_baseline:
                ctx = batch_context_prefix(prev_batch) if bi > 1 else ""
                prompt = (
                    build_baseline_batch_enrich_prompt(
                        entry_id,
                        recalled,
                        plan_data,
                        batch_text,
                        batch_target,
                        batch_no=bi,
                        total_batches=total,
                        context_prefix=ctx,
                    )
                    + retry_note
                    + _repair_feedback_suffix()
                )
            else:
                prompt = (
                    build_batch_enrich_prompt(
                        entry_id,
                        recalled,
                        plan_data,
                        batch_text,
                        batch_target,
                        batch_no=bi,
                        total_batches=total,
                        include_intro=(bi == 1),
                    )
                    + retry_note
                    + _repair_feedback_suffix()
                )
            print(
                f"⏳ D enrich {entry_id} {label} → {batch_target.name}"
                + (f"（重试 {attempt}/{_phase2_max_retries()}）" if attempt else ""),
                flush=True,
            )
            _llm_turn(
                work_dir,
                entry_id,
                "enrich",
                prompt,
                session_id=f"{session_id}-enrich-b{bi}-r{attempt}",
                timeout_sec=900,
                artifact_paths={"output": batch_target},
            )
            if not batch_target.is_file():
                batch_errs = [f"D {label}: LLM 未落盘本批译稿"]
                print(f"⚠️ {batch_errs[0]}", flush=True)
                continue
            if polish_enrich_file(batch_target):
                print("   🔧 已自动修正本批模糊出处表述", flush=True)
            slice_ok, slice_errs = verify_enrich_batch_slice(
                entry_id,
                recalled,
                batch_target,
                batch_mother_text=batch_text,
                batch_label=label,
            )
            if not slice_ok:
                batch_errs = slice_errs or [f"D {label}: 本批质检未通过"]
                print(f"⚠️ D {label} 未通过: {batch_errs[0]}", flush=True)
                continue
            parts.append(_load_mother_text(batch_target))
            prev_batch = batch_text
            batch_ok = True
            break
        if not batch_ok:
            return False, batch_errs or [f"D {label} 失败"], time.time() - t0

    combined = merge_enrich_batches(entry_id, parts, plan_data, recalled)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"史略ID": entry_id, "翻译详情": combined}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    if polish_enrich_file_full(target):
        print("   🔧 已自动修正模糊出处表述", flush=True)
    touch_heartbeat(work_dir, entry_id, stage="verify_enrich")
    e_ok, e_errs = _verify_enrich_with_autofix(
        entry_id, recalled, target, plan_data, baseline_detail=baseline_detail
    )
    if not e_ok:
        return False, [f"Phase2: {e}" for e in e_errs], time.time() - t0
    return True, [], time.time() - t0


def _run_phase2_enrich(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_body: str,
    mother_file: Path,
    target: Path,
    session_id: str,
    work_dir: Path,
    entry_name: str,
    t0: float,
    baseline_file: Path | None = None,
) -> Tuple[bool, List[str], float]:
    """Phase2/D 知识增强 + 前置质检 + 重试。"""
    from lib.phase2_batch import (
        discover_mother_batches,
        phase2_batch_char_threshold,
        split_detail_paragraph_batches,
    )

    threshold = phase2_batch_char_threshold()
    enrich_source = mother_body
    if baseline_file and baseline_file.is_file():
        enrich_source = baseline_body_for_enrich(baseline_file)

    if len(enrich_source) > threshold:
        if baseline_file and baseline_file.is_file():
            batches = split_detail_paragraph_batches(enrich_source, threshold)
            if len(batches) > 1:
                return _run_phase2_enrich_batched(
                    entry_id,
                    recalled,
                    plan_data=plan_data,
                    mother_file=mother_file,
                    target=target,
                    session_id=session_id,
                    work_dir=work_dir,
                    entry_name=entry_name,
                    t0=t0,
                    baseline_file=baseline_file,
                )
        batch_files = discover_mother_batches(mother_file)
        if batch_files:
            return _run_phase2_enrich_batched(
                entry_id,
                recalled,
                plan_data=plan_data,
                mother_file=mother_file,
                target=target,
                session_id=session_id,
                work_dir=work_dir,
                entry_name=entry_name,
                t0=t0,
                baseline_file=baseline_file,
            )
    enrich_plan_json = _plan_json_for_enrich(plan_data)
    e_errs: List[str] = []
    e_ok = False
    for attempt in range(_phase2_max_retries() + 1):
        retry_note = ""
        if attempt > 0 and e_errs:
            plan_fb = classify_translate_failure(e_errs, stage="phase2", fail_count=attempt)
            retry_note = (
                "\n\n--- 上轮 Phase2 质检失败，须修正 ---\n"
                + format_retry_feedback(plan_fb, e_errs)
            )
        e_prompt = build_translate_enrich_prompt(
            entry_id,
            recalled,
            recalled_summary(recalled),
            enrich_plan_json,
            enrich_source,
            target,
        ) + retry_note + _repair_feedback_suffix()
        print(
            f"⏳ Phase2 补全成稿 {entry_id} → {target.name}"
            + (f"（重试 {attempt}/{_phase2_max_retries()}）" if attempt else ""),
            flush=True,
        )
        _llm_turn(
            work_dir,
            entry_id,
            "enrich",
            e_prompt,
            session_id=f"{session_id}-enrich-r{attempt}",
            timeout_sec=900,
            artifact_paths={"output": target},
        )
        if not target.is_file():
            e_errs = ["Phase2: LLM 未落盘最终译稿"]
            e_ok = False
            print(f"⚠️ Phase2 未通过: {e_errs[0]}", flush=True)
            continue
        if polish_enrich_file_full(target):
            print("   🔧 已自动修正模糊出处表述", flush=True)
        touch_heartbeat(work_dir, entry_id, stage="verify_enrich")
        bl_detail = ""
        if baseline_file and baseline_file.is_file():
            bl_detail = baseline_body_for_enrich(baseline_file)
        e_ok, e_errs = _verify_enrich_with_autofix(
            entry_id, recalled, target, plan_data, baseline_detail=bl_detail
        )
        if e_ok:
            break
        print(f"⚠️ Phase2 未通过: {e_errs[0] if e_errs else '?'}", flush=True)
    if not e_ok:
        return False, [f"Phase2: {e}" for e in e_errs], time.time() - t0
    return True, [], time.time() - t0


def _run_single_pass(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_file: Path,
    target: Path,
    session_id: str,
    out_dir: Path,
    entry_name: str,
    work_dir: Path,
    use_llm: bool = True,
    from_phase: str | None = None,
    translation_version: str | None = None,
) -> Tuple[bool, List[str], float]:
    """plan + ABCD 或 legacy Phase1/Phase2 或单次 draft。"""
    t0 = time.time()
    touch_heartbeat(work_dir, entry_id, stage="start", detail=entry_name)

    if _two_phase_enabled() and streamlined_pipeline_enabled():
        ok, errs = run_streamlined_pipeline(
            entry_id,
            recalled,
            plan_file=plan_file,
            target=target,
            work_dir=work_dir,
            entry_name=entry_name,
            session_id=session_id,
            use_llm=use_llm,
            from_phase=from_phase,
        )
        if not ok:
            return False, errs, time.time() - t0
        attach_source_original(target, recalled, translation_version=translation_version)
        plan_ok, plan_data, _ = load_plan(plan_file)
        _apply_attribution_polish(target, recalled, plan_data if plan_ok else {})
        return True, [], time.time() - t0

    if _two_phase_enabled() and abcd_pipeline_enabled():
        mother_file = mother_draft_path(entry_id, entry_name, work_dir)
        baseline_file = baseline_draft_path(entry_id, entry_name, work_dir)
        fp = from_phase or ""
        if fp == "phase2":
            fp = "phase_d"

        if fp not in ("phase_d", "phase2"):
            bl_ok, bl_errs, plan_data = run_abcd_baseline(
                entry_id,
                recalled,
                plan_file=plan_file,
                work_dir=work_dir,
                entry_name=entry_name,
                session_id=session_id,
                use_llm=use_llm,
                from_phase=fp or None,
            )
            if not bl_ok:
                return False, bl_errs, time.time() - t0
        else:
            _, plan_data, _ = load_normalized_plan(plan_file, recalled)
            if not baseline_file.is_file():
                return False, ["缺少 baseline 成稿，无法 D 阶段 enrich"], time.time() - t0
            print(f"⏭️ 跳过 A/B/C（沿用 {baseline_file.name}）", flush=True)

        baseline_body = baseline_body_for_enrich(baseline_file)
        ep_ok, plan_data, ep_errs = ensure_enrich_plan(
            entry_id,
            recalled,
            plan_file,
            baseline_body=baseline_body,
            work_dir=work_dir,
            session_id=session_id,
            use_llm=use_llm,
            baseline_file=baseline_file,
        )
        if not ep_ok:
            return False, ep_errs, time.time() - t0

        ok2, errs2, elapsed = _run_phase2_enrich(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_body=baseline_body,
            mother_file=mother_file,
            target=target,
            session_id=session_id,
            work_dir=work_dir,
            entry_name=entry_name,
            t0=t0,
            baseline_file=baseline_file,
        )
        if not ok2:
            from lib.baseline_promote import baseline_fallback_enabled, write_baseline_from_file

            if baseline_fallback_enabled():
                print(
                    "⚠️ D 阶段未通过，降级发布 baseline（baseline_ready）",
                    flush=True,
                )
                write_baseline_from_file(
                    target,
                    baseline_file,
                    entry_id,
                    translation_version=translation_version or "baseline_ready",
                    phase2_errors=errs2,
                )
                attach_source_original(
                    target,
                    recalled,
                    translation_version=translation_version or "baseline_ready",
                )
                return True, [
                    "baseline_ready: D 未通过，已发布 baseline；可 --from-phase phase_d 续跑"
                ], elapsed
            return ok2, errs2, elapsed
        attach_source_original(
            target,
            recalled,
            translation_version=translation_version or "abcd_enriched",
        )
        return True, [], elapsed

    plan_ok, plan_data, plan_errors = ensure_coverage_ledger(
        entry_id,
        recalled,
        plan_file,
        session_id=f"{session_id}-plan",
        work_dir=work_dir,
        use_llm=use_llm,
    )
    if not plan_ok:
        return False, plan_errors, 0.0

    _, plan_data, _ = load_normalized_plan(plan_file, recalled)
    inflate_errs = _guard_plan_inflation(recalled, plan_data)
    if inflate_errs:
        return False, inflate_errs, 0.0

    if _two_phase_enabled():
        mother_file = mother_draft_path(entry_id, entry_name, work_dir)
        skip_phase1 = from_phase == "phase2"

        if skip_phase1:
            if not mother_file.is_file():
                return False, ["缺少 Phase1 母本顺译，无法 --from-phase phase2"], time.time() - t0
            touch_heartbeat(work_dir, entry_id, stage="verify_mother")
            m_ok, m_errs = verify_mother_draft(
                entry_id, recalled, mother_file, plan=plan_data
            )
            if not m_ok:
                return False, [f"母本顺译未通过: {e}" for e in m_errs], time.time() - t0
            print(f"⏭️ 跳过 Phase1（沿用 {mother_file.name}）", flush=True)
        else:
            if not mother_file.is_file():
                from lib.coverage_ledger import clear_ledger

                clear_ledger(work_dir, entry_id)
            m_ok, m_errs = _run_phase1_mother(
                entry_id,
                recalled,
                plan_data=plan_data,
                mother_file=mother_file,
                work_dir=work_dir,
                session_id=session_id,
            )
            if not m_ok:
                return False, m_errs, time.time() - t0

        mother_body = _load_mother_text(mother_file)
        ok2, errs2, elapsed = _run_phase2_enrich(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_body=mother_body,
            mother_file=mother_file,
            target=target,
            session_id=session_id,
            work_dir=work_dir,
            entry_name=entry_name,
            t0=t0,
        )
        if not ok2:
            from lib.baseline_promote import baseline_fallback_enabled, write_baseline_from_mother

            if baseline_fallback_enabled():
                print(
                    "⚠️ Phase2 未通过，降级发布母本顺译（baseline_ready）",
                    flush=True,
                )
                write_baseline_from_mother(
                    target,
                    entry_id,
                    mother_body,
                    translation_version=translation_version or "baseline_mother",
                    phase2_errors=errs2,
                )
                attach_source_original(
                    target,
                    recalled,
                    translation_version=translation_version or "baseline_mother",
                )
                return True, [
                    "baseline_ready: Phase2 未通过，已发布母本顺译；可后续 --from-phase phase2 补全"
                ], elapsed
            return ok2, errs2, elapsed
        attach_source_original(target, recalled, translation_version=translation_version)
        return True, [], elapsed
    else:
        plan_json = json.dumps(plan_data, ensure_ascii=False, indent=2) if plan_data else "{}"
        prompt = build_translate_prompt(
            entry_id,
            recalled,
            recalled_summary(recalled),
            plan_json,
            target,
        )
        print(
            f"⏳ 翻译 {entry_id} {recalled['史略名称']} → {target}\n"
            f"   session={session_id}\n"
            f"   source_plan={plan_file}",
            flush=True,
        )
        _llm_turn(
            work_dir,
            entry_id,
            "draft",
            prompt,
            session_id=session_id,
            timeout_sec=900,
            artifact_paths={"output": target},
        )
        if not target.is_file():
            return False, ["LLM 未落盘译稿"], time.time() - t0

    attach_source_original(target, recalled, translation_version=translation_version)
    return True, [], time.time() - t0


def _load_mother_text(mother_file: Path) -> str:
    ok, data, _ = load_output_from_path(mother_file)
    if ok:
        text = (data.get("母本顺译") or data.get("翻译详情") or "").strip()
        if text:
            return text
    if mother_file.is_file():
        return mother_file.read_text(encoding="utf-8").strip()
    return ""


def load_output_from_path(
    fp: Path,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    if not fp.is_file():
        return False, {}, [f"缺少文件: {fp}"]
    try:
        return True, json.loads(fp.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return False, {}, [f"JSON 解析失败: {exc}"]


def run_one(
    entry_id: str,
    *,
    index_path: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
    recall_only: bool = False,
    use_llm: bool = True,
    from_phase: str | None = None,
) -> int:
    db.init_schema()
    job = db.get_job(entry_id)
    if not job:
        bootstrap(index_path=index_path)
        job = db.get_job(entry_id)
    if not job:
        print(f"⚠️ 索引中无 {entry_id}")
        return 1

    try:
        recalled = recall_entry(entry_id, index_path=index_path)
    except RecallError as exc:
        db.update_job(entry_id, status="failed", detail=str(exc))
        print(f"❌ recall 失败: {exc}")
        return 1

    fp = source_fingerprint(recalled)
    out_dir = _ensure_output_dir(index_path=index_path, output_dir=output_dir)
    trans_version = translation_version_for_output_dir(out_dir)
    work_dir = _ensure_work_dir()
    entry_name = str(recalled.get("史略名称") or job.get("entry_name") or "")
    target = output_path(entry_id, out_dir, entry_name)
    plan_file = plan_path(entry_id, entry_name, work_dir)

    thin_errs = verify_source_thickness(recalled)
    if thin_errs and use_llm and not dry_run and not recall_only:
        fail = int(job.get("fail_count") or 0)
        rc, plan = _record_translate_failure(
            entry_id,
            entry_name,
            stage="recall_thickness",
            errors=thin_errs,
            work_dir=work_dir,
            fail_count=fail,
        )
        db.update_job(
            entry_id,
            status="routed" if rc == 2 else "failed",
            detail=f"{plan.root_cause}: {thin_errs[0]}",
        )
        return rc

    if _should_skip(entry_id, recalled, job, plan_file, out_dir=out_dir):
        print(f"⏭️ 跳过 {entry_id}（产出已有效 fp={fp}）")
        return 0

    if recall_only:
        print(recalled_summary(recalled))
        return 0

    if dry_run:
        plan_session = make_session_id(entry_id, int(job["id"]))
        if _use_chunked_pipeline(recalled):
            ok, errs = run_chunked_pipeline(
                entry_id,
                recalled,
                work_dir=work_dir,
                out_dir=out_dir,
                entry_name=entry_name,
                target=target,
                session_id=plan_session,
                dry_run=True,
                use_llm=False,
            )
            print(f"📝 dry-run {entry_id}（分块）→ {target}")
            if errs:
                print("   " + "\n   ".join(errs[:3]))
            return 0
        ensure_source_plan(
            entry_id,
            recalled,
            plan_file,
            session_id=f"{plan_session}-plan",
            work_dir=work_dir,
            dry_run=True,
            use_llm=False,
        )
        plan_json = _plan_json_text(plan_file)
        if _two_phase_enabled():
            mother_file = mother_draft_path(entry_id, entry_name, work_dir)
            mp = build_translate_mother_prompt(
                entry_id,
                recalled,
                recalled_summary(recalled),
                plan_json,
                mother_file,
            )
            ep = build_translate_enrich_prompt(
                entry_id,
                recalled,
                recalled_summary(recalled),
                plan_json,
                "（Phase1 母本顺译全文）",
                target,
            )
            print(f"📝 dry-run {entry_id}（两阶段）→ {target}")
            print(f"   Phase1 prompt 约 {len(mp)} 字符 → {mother_file.name}")
            print(f"   Phase2 prompt 约 {len(ep)} 字符")
        else:
            prompt = build_translate_prompt(
                entry_id,
                recalled,
                recalled_summary(recalled),
                plan_json,
                target,
            )
            print(f"📝 dry-run {entry_id} → {target}")
            print(f"   draft prompt 约 {len(prompt)} 字符")
        return 0

    if not use_llm:
        print(f"⚠️ 未启用 LLM，跳过 {entry_id}")
        return 0

    session_id = make_session_id(entry_id, int(job["id"]))
    from lib.run_ledger import new_run, preserve_candidate, save, update

    run_manifest = new_run(
        work_dir,
        entry_id,
        formal_target=target,
        source_fingerprint=fp,
    )
    save(run_manifest)
    db.update_job(
        entry_id,
        status="running",
        session_id=session_id,
        started_at=db.utc_now(),
        source_fingerprint=fp,
    )

    elapsed = 0.0
    try:
        if _use_chunked_pipeline(recalled):
            ok, errs = run_chunked_pipeline(
                entry_id,
                recalled,
                work_dir=work_dir,
                out_dir=out_dir,
                entry_name=entry_name,
                target=target,
                session_id=session_id,
                use_llm=use_llm,
                translation_version=trans_version,
            )
        else:
            ok, errs, elapsed = _run_single_pass(
                entry_id,
                recalled,
                plan_file=plan_file,
                target=target,
                session_id=session_id,
                out_dir=out_dir,
                entry_name=entry_name,
                work_dir=work_dir,
                use_llm=use_llm,
                from_phase=from_phase,
                translation_version=trans_version,
            )
    except RuntimeError as exc:
        fail = int(job.get("fail_count") or 0) + 1
        db.update_job(entry_id, status="failed", fail_count=fail, detail=str(exc)[-500:])
        print(f"❌ LLM 失败: {exc}")
        return 1

    if not ok:
        fail = int(job.get("fail_count") or 0) + 1
        stage = "verify"
        update(
            run_manifest,
            phase=stage,
            status="pending_recovery",
            next_action="retry_full",
            error="; ".join(errs[:3]),
        )
        preserve_candidate(run_manifest, target if target.is_file() else mother_draft_path(
            entry_id, entry_name, work_dir
        ))
        rc, plan = _record_translate_failure(
            entry_id,
            entry_name,
            stage=stage,
            errors=errs,
            work_dir=work_dir,
            fail_count=fail,
        )
        db.update_job(
            entry_id,
            status="routed" if rc == 2 else "failed",
            fail_count=fail,
            detail=f"repair:{plan.root_cause}",
        )
        print(f"❌ 翻译未通过:\n   " + "\n   ".join(errs))
        return rc

    _, plan_data, _ = load_normalized_plan(plan_file, recalled)
    is_baseline = any(str(e).startswith("baseline_ready") for e in errs)
    coverage_report = is_baseline or str(
        os.environ.get("TRANSLATE_COVERAGE_VERIFY", "report")
    ).strip().lower() in {"report", "warn", "ticket", "1", "true", "yes"}
    v_ok, v_errs, v_tickets = verify_output(
        entry_id,
        recalled,
        out_dir,
        plan=plan_data if plan_data else None,
        coverage="report" if coverage_report else "strict",
        verify_mode="baseline" if is_baseline else "full",
    )
    if v_ok and v_tickets:
        from lib.repair_ticket import save_open_issues_ticket

        ticket = save_open_issues_ticket(
            work_dir,
            entry_id=entry_id,
            entry_name=entry_name,
            stage="verify_open_issues",
            issues=v_tickets,
        )
        if ticket:
            print(
                f"📋 软质检工单 → {ticket.name}（{len(v_tickets)} 项，不阻断出队）",
                flush=True,
            )
    if not v_ok:
        fail = int(job.get("fail_count") or 0) + 1
        update(
            run_manifest,
            phase="verify_final",
            status="pending_recovery",
            next_action="retry_phase2" if is_baseline else "retry_full",
            error="; ".join(v_errs[:3]),
        )
        preserve_candidate(run_manifest, target)
        rc, plan = _record_translate_failure(
            entry_id,
            entry_name,
            stage="verify_final",
            errors=v_errs,
            work_dir=work_dir,
            fail_count=fail,
        )
        db.update_job(
            entry_id,
            status="routed" if rc == 2 else "failed",
            fail_count=fail,
            detail=f"repair:{plan.root_cause}",
        )
        print(f"❌ verify 未通过:\n   " + "\n   ".join(v_errs))
        return rc

    _, data, _ = load_output(entry_id, out_dir, entry_name)
    wc = len((data.get("翻译详情") or ""))
    if not is_baseline:
        from lib.promote_output import stamp_pending_review

        stamp_pending_review(target)
    mode = "chunked" if _use_chunked_pipeline(recalled) else "single"
    job_status = "baseline_ready" if is_baseline else "done"
    job_detail = (
        f"baseline_ready {mode} {elapsed:.0f}s"
        if is_baseline
        else f"ok {mode} {elapsed:.0f}s"
    )
    db.update_job(
        entry_id,
        status=job_status,
        source_fingerprint=fp,
        output_word_count=wc,
        detail=job_detail,
    )
    if is_baseline:
        print(
            f"✅ {entry_id} baseline_ready {wc} 字（母本顺译，Phase2 待补）"
            f" ({mode}, {elapsed:.0f}s) → {out_dir.name}/"
        )
    else:
        print(f"✅ {entry_id} 完成 {wc} 字 ({mode}, {elapsed:.0f}s) → {out_dir.name}/")
    preserve_candidate(run_manifest, target)
    update(
        run_manifest,
        phase="phase2" if not is_baseline else "phase1",
        status="promoted" if not is_baseline else "baseline_ready",
        next_action="done" if not is_baseline else "retry_phase2",
    )
    run_manifest["formal_promoted"] = True
    save(run_manifest)
    if not trans_version and not is_baseline:
        try:
            agg_path, agg_count = rebuild_aggregate(out_dir)
            print(f"📦 汇总已更新 → {agg_path}（{agg_count} 条）")
        except OSError as exc:
            print(f"⚠️ 汇总更新失败（单条产出已保留）: {exc}")
    elif is_baseline:
        print("📦 baseline 跳过汇总更新（enrich 后再 aggregate）", flush=True)

    print(
        f"📌 产出已落盘（未自动同步）。人工确认后: python3 translate.py promote --id {entry_id} [--sync]",
        flush=True,
    )
    return 0


def retry_failed_cmd(
    *,
    dynasty: Optional[str] = None,
    priority: Optional[str] = None,
    index_path: Path | None = None,
) -> int:
    """将 failed 且无有效产出的任务重置为 pending；有成稿的标为 done。"""
    db.init_schema()
    idx_path = index_path or default_index_path()
    out_dir = _ensure_output_dir()
    work_dir = _ensure_work_dir()

    failed = filter_pending_jobs(
        db.list_jobs(status="failed", priority=priority, limit=5000),
        dynasty=dynasty,
        index_path=idx_path,
    )
    if not failed:
        scope = f"朝代={dynasty} " if dynasty else ""
        print(f"📭 无 failed 任务可重试（{scope}priority={priority or '全部'}）")
        return 0

    reset = 0
    synced = 0
    for job in failed:
        eid = job["entry_id"]
        name = str(job.get("entry_name") or "")
        try:
            recalled = recall_entry(eid, index_path=idx_path)
        except RecallError:
            db.update_job(eid, status="pending", detail="retry: recall ok next run")
            reset += 1
            continue

        entry_name = str(recalled.get("史略名称") or name)
        plan_file = plan_path(eid, entry_name, work_dir)
        if _should_skip(eid, recalled, job, plan_file):
            synced += 1
            continue

        db.update_job(
            eid,
            status="pending",
            detail="retry: reset from failed",
            fail_count=int(job.get("fail_count") or 0),
        )
        reset += 1

    scope = f"朝代={dynasty} " if dynasty else ""
    print(
        f"🔄 重试准备: {scope}重置 pending {reset} 条，"
        f"已有成稿同步 done {synced} 条"
    )
    return 0


def run_batch(
    *,
    max_jobs: int = 1,
    from_id: Optional[str] = None,
    priority: Optional[str] = None,
    dynasty: Optional[str] = None,
    single_source_only: bool = False,
    index_path: Path | None = None,
    dry_run: bool = False,
    recall_only: bool = False,
    use_llm: bool = True,
    retry_failed: bool = False,
) -> int:
    db.init_schema()
    idx_path = index_path or default_index_path()
    if db.count_jobs() == 0:
        bootstrap(index_path=idx_path)

    if retry_failed:
        retry_failed_cmd(
            dynasty=dynasty,
            priority=priority,
            index_path=idx_path,
        )

    pending = filter_pending_jobs(
        db.list_jobs(
            status="pending",
            priority=priority,
            single_source_only=single_source_only,
            limit=5000,
        ),
        dynasty=dynasty,
        from_id=from_id,
        index_path=idx_path,
    )
    if dynasty and not pending:
        print(f"📭 无 pending 任务（朝代={dynasty}）")
        return 0
    if dynasty:
        print(f"🏷️ 朝代筛选: {dynasty}，待处理 {len(pending)} 条")

    ran = 0
    rc = 0
    for job in pending:
        if ran >= max_jobs:
            break
        code = run_one(
            job["entry_id"],
            index_path=idx_path,
            dry_run=dry_run,
            recall_only=recall_only,
            use_llm=use_llm,
        )
        if code != 0:
            rc = code
        ran += 1
    if ran == 0 and not dynasty:
        print("📭 无 pending 任务")
    return rc


def verify_cmd(
    entry_id: str,
    *,
    index_path: Path | None = None,
    output_dir: Path | None = None,
) -> int:
    recalled = recall_entry(entry_id, index_path=index_path)
    work_dir = _ensure_work_dir()
    p = plan_path(
        entry_id,
        str(recalled.get("史略名称") or ""),
        work_dir,
    )
    plan_ok, plan_data, plan_errs = load_plan(p)
    ok, errs, tickets = verify_output(
        entry_id,
        recalled,
        _ensure_output_dir(index_path=index_path, output_dir=output_dir),
        plan=plan_data if plan_ok else None,
    )
    if not plan_ok:
        errs = plan_errs + errs
        ok = False
    if ok:
        print(f"✅ verify 通过: {entry_id}")
        for t in tickets:
            print(f"   ⚠️ 工单: {t}")
        return 0
    print(f"❌ verify 失败: {entry_id}")
    for e in errs:
        print(f"   · {e}")
    for t in tickets:
        print(f"   ⚠️ 工单: {t}")
    return 1


def aggregate_cmd() -> int:
    out_dir = _ensure_output_dir()
    try:
        agg_path, count = rebuild_aggregate(out_dir)
    except OSError as exc:
        print(f"❌ 汇总失败: {exc}")
        return 1
    print(f"📦 汇总 → {agg_path}（{count} 条）")
    return 0


def watch_cmd(entry_id: str, *, index_path: Path | None = None) -> int:
    """检查条目是否卡顿并输出诊断。"""
    work_dir = _ensure_work_dir()
    entry_name = ""
    try:
        recalled = recall_entry(entry_id, index_path=index_path or default_index_path())
        entry_name = str(recalled.get("史略名称") or "")
    except RecallError as exc:
        print(f"❌ recall 失败: {exc}")
        return 1
    stalled, msg = is_stalled(work_dir, entry_id)
    hb = read_heartbeat(work_dir, entry_id)
    if hb:
        print(f"💓 心跳: {hb.get('updated_iso')} stage={hb.get('stage')}")
    if stalled:
        print(f"⚠️ {msg}")
        for hint in diagnose_stall(work_dir, entry_id, entry_name):
            print(f"   · {hint}")
        return 1
    print(f"✅ {entry_id} 未超过 {stall_threshold_sec()}s 无心跳")
    return 0


def sync_cmd(
    entry_id: str | None = None,
    *,
    all_from_aggregate: bool = False,
    dry_run: bool = False,
    index_path: Path | None = None,
) -> int:
    """同步单条产出或汇总 JSON 到线上 historical_box_detail。"""
    from lib.remote_sync import sync_all_box_details, sync_all_from_aggregate, sync_output_entry
    from lib.aggregate import aggregate_path

    out_dir = _ensure_output_dir()

    if all_from_aggregate:
        agg = aggregate_path(out_dir)
        # 同时带上朝代知识补全汇总，避免 prune 误删
        dk_agg = _dynasty_detail_aggregate_path()
        ok, msg = sync_all_box_details(
            translate_json=agg,
            dynasty_detail_json=dk_agg,
            dry_run=dry_run,
            prune_orphans=True,
        )
        if ok:
            print(f"☁️ {msg}")
            return 0
        print(f"❌ 全量同步失败: {msg}")
        return 1

    if not entry_id:
        print("❌ 请指定 --id 或 --all")
        return 1

    entry_name = ""
    try:
        recalled = recall_entry(entry_id, index_path=index_path or default_index_path())
        entry_name = str(recalled.get("史略名称") or "")
    except RecallError:
        pass

    ok, msg = sync_output_entry(entry_id, out_dir, entry_name, dry_run=dry_run)
    if ok:
        print(f"☁️ {entry_id}: {msg}")
        return 0
    print(f"❌ {entry_id} 同步失败: {msg}")
    return 1


def promote_cmd(
    entry_id: str,
    *,
    index_path: Path | None = None,
    output_dir: Path | None = None,
    version: str | None = None,
    note: str = "",
    sync: bool = False,
    dry_run: bool = False,
) -> int:
    """人工确认后 promote 至 11/_versions；可选 --sync 同步线上。"""
    from lib.promote_output import promote_from_output_dir

    out_dir = _ensure_output_dir(index_path=index_path, output_dir=output_dir)
    entry_name = ""
    try:
        recalled = recall_entry(entry_id, index_path=index_path or default_index_path())
        entry_name = str(recalled.get("史略名称") or "")
    except RecallError:
        pass

    versions_root = out_dir / "_versions"
    ok, msg, _target = promote_from_output_dir(
        entry_id,
        out_dir,
        versions_root=versions_root,
        entry_name=entry_name,
        version=version,
        note=note,
    )
    if not ok:
        print(f"❌ promote 失败: {msg}")
        return 1
    print(f"✅ {msg}")
    if sync:
        return sync_cmd(entry_id, index_path=index_path, dry_run=dry_run)
    return 0


def print_status() -> int:
    db.init_schema()
    total = db.count_jobs()
    done = db.count_jobs("done")
    pending = db.count_jobs("pending")
    failed = db.count_jobs("failed")
    print(f"\n📋 史略翻译任务队列")
    print(f"   任务: done {done}/{total}  pending {pending}  failed {failed}")
    idx = db.get_meta("index_path")
    if idx:
        print(f"   索引: {idx}")
    out_dir = _ensure_output_dir(
        index_path=Path(idx) if idx else None,
    )
    print(f"   产出: {out_dir}")

    idx_path = Path(idx) if idx else default_index_path()
    if idx_path.is_file():
        index = load_global_index(idx_path)
        entries = index.get("entries") or []
        detail_agg = paths()["dynasty_knowledge_detail_aggregate"]
        progress = compute_progress(
            entries,
            translated_ids=load_translated_ids(out_dir),
            dynasty_detail_ids=load_dynasty_detail_ids(detail_agg),
        )
        print()
        print(format_progress_report(progress))
    return 0
