"""翻译任务编排：bootstrap / recall / run / verify。"""

from __future__ import annotations

import json
import os
import re
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
from lib.plan_postprocess import (
    build_plan_skeleton,
    merge_llm_plan_decisions,
    plan_for_enrich_phase,
    plan_for_mother_phase,
)
from lib.prose_sanitize import polish_enrich_file, polish_enrich_file_full, polish_mother_file, sanitize_mother_detail
from lib.attribution import apply_attribution_fixes
from lib.remote_sync import auto_sync_enabled
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
    build_translate_polish_backfill_prompt,
    build_translate_polish_prompt,
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
    load_normalized_plan,
    load_plan,
    mother_draft_path,
    plan_path,
    save_plan,
    verify_plan,
)


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
        v_ok, _ = verify_output(entry_id, recalled, out_dir, plan=plan)
        return v_ok
    v_ok, _ = verify_output(entry_id, recalled, out_dir, plan=plan)
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


def _plan_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PLAN_MAX_RETRIES", "2")))


def _format_plan_retry_feedback(errors: List[str]) -> str:
    from lib.plan_postprocess import MAX_REFERENCE_WORKS

    lines = [f"- {e}" for e in (errors or [])[:12]]
    hint = (
        "修正要点：\n"
        "- 宏观选题两层：①通道检索（非交作业）；②重要性门槛（合法性/制度/战局用人/评价/神话辩伪）；"
        "宁缺毋滥，禁止碎闻神异灌水与为凑通道凑 true；禁止更简平行纪与现代评述。\n"
        "- `外部补全` 禁止空数组；不确定标 false 并写理由。\n"
        "- **禁止**母本同一卷；禁止用雕花凑 `采用:true`。\n"
        "- `采用:true` 须合法补全类型 + 《书·卷》+「与母本关系」写清冲突/另说/背景/异评；"
        "禁止 GLBL_/过渡段/「原文翻译」作出处。\n"
        "- 须有非空 `参考著作` 与 `写作结构`；"
        f"`参考著作` 硬上限 ≤{MAX_REFERENCE_WORKS}，只交最重要的，超限会拒收重试。\n"
    )
    return ("\n".join(lines) + "\n" + hint) if lines else hint.strip()


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
    from lib.external_macro import macro_plan_enabled, plan_external_hunt_enabled

    ok, errors = verify_plan(entry_id, recalled, plan_file)
    if ok:
        ok_load, raw, _ = load_plan(plan_file)
        if ok_load:
            from lib.plan_postprocess import apply_reference_works_cap

            save_plan(plan_file, apply_reference_works_cap(raw), recalled)
        return True, []

    # 默认：plan 不挖外部补全，只程序生成母本清单骨架
    if not plan_external_hunt_enabled():
        if dry_run:
            print(f"🧭 source-plan dry-run（骨架-only，不挖外部补全）→ {plan_file}")
            return False, errors
        return _ensure_source_plan_skeleton(
            entry_id, recalled, plan_file, work_dir=work_dir
        )

    if dry_run:
        if macro_plan_enabled():
            from lib.external_macro import build_external_macro_prompt

            prompt = build_external_macro_prompt(entry_id, recalled)
        else:
            prompt = build_source_plan_prompt(
                entry_id, recalled, recalled_summary(recalled), plan_file
            )
        print(f"🧭 source-plan dry-run → {plan_file}")
        print(f"   plan prompt 约 {len(prompt)} 字符")
        if errors:
            print("   当前计划缺失/无效: " + "; ".join(errors[:3]))
        return False, errors

    if not use_llm:
        return False, errors

    if macro_plan_enabled():
        return _ensure_source_plan_macro(
            entry_id,
            recalled,
            plan_file,
            session_id=session_id,
            work_dir=work_dir,
            initial_errors=errors,
        )

    return _ensure_source_plan_legacy(
        entry_id,
        recalled,
        plan_file,
        session_id=session_id,
        work_dir=work_dir,
        initial_errors=errors,
    )


def _ensure_source_plan_skeleton(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
    *,
    work_dir: Path | None = None,
) -> tuple[bool, List[str]]:
    """plan 只生成母本清单/索引裁决骨架；外部补全交 Phase2。"""
    del work_dir
    from lib.plan_postprocess import (
        apply_reference_works_cap,
        build_plan_skeleton,
        finalize_plan,
    )
    from lib.source_citation import build_source_citation

    print("🧭 source-plan：骨架-only（不挖外部补全，交 Phase2 自补）", flush=True)
    skeleton = build_plan_skeleton(recalled)
    skeleton["史略ID"] = entry_id
    skeleton["外部补全"] = []
    cite = build_source_citation(recalled).strip()
    if cite:
        mother_ref = cite if cite.startswith("《") else f"《{cite}》"
    else:
        mother_ref = str(recalled.get("母本著作") or "母本").strip()
        if mother_ref and not mother_ref.startswith("《"):
            mother_ref = f"《{mother_ref}》"
    skeleton["参考著作"] = [mother_ref] if mother_ref else []
    skeleton["写作结构"] = [
        {"小节": "本传", "说明": "Phase1 母本顺译 → Phase2 润色自挖补充并文末列参考"}
    ]
    skeleton["风险提示"] = [
        "plan 不再选题外部补全；Phase2 可凭史识补充，但凡补充须在文末「参考著作」列出实际用到的书",
        "流畅性不得凌驾时间真实性；禁止把晚年事插到中前期",
    ]
    plan = finalize_plan(skeleton, recalled, id_start=1, external_dedupe_llm=False)
    plan = apply_reference_works_cap(plan)
    save_plan(plan_file, plan, recalled)
    ok, errors = verify_plan(entry_id, recalled, plan_file)
    if ok:
        print(f"   ✅ plan 骨架已落盘（外部补全=0）→ {plan_file.name}", flush=True)
    return ok, errors


def _ensure_source_plan_macro(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
    *,
    session_id: str,
    work_dir: Path | None,
    initial_errors: List[str],
) -> tuple[bool, List[str]]:
    """两步法：宏观选题 → 全书判重 → 挂锚 → 落盘。"""
    from lib.external_dedupe import apply_external_mother_dedupe
    from lib.external_macro import (
        build_decision_from_macro,
        macro_reference_count,
        normalize_macro_external,
        run_anchor_external,
        run_macro_external_select,
    )
    from lib.plan_postprocess import MAX_REFERENCE_WORKS, apply_reference_works_cap

    wd = work_dir or plan_file.parent
    max_retries = _plan_max_retries()
    last_errors = list(initial_errors)
    skeleton = build_plan_skeleton(recalled)

    for attempt in range(max_retries + 1):
        need_feedback = attempt > 0 or any("空数组" in e for e in last_errors)
        label = f"宏观选题 source plan → {plan_file}"
        if attempt:
            label = f"重试宏观选题（{attempt}/{max_retries}）→ {plan_file}"
        print(f"🧭 {label}", flush=True)
        touch_heartbeat(
            wd,
            entry_id,
            stage="plan_macro",
            detail=f"{plan_file.name}" + (f" retry={attempt}" if attempt else ""),
        )
        macro, raw = run_macro_external_select(
            entry_id,
            recalled,
            session_id=f"{session_id}-macro-r{attempt}" if attempt else f"{session_id}-macro",
            retry_feedback=(
                _format_plan_retry_feedback(last_errors) if need_feedback else ""
            ),
        )
        try:
            plan_file.with_suffix(".macro.raw.txt").write_text(raw, encoding="utf-8")
            plan_file.with_suffix(".macro.json").write_text(
                json.dumps(macro, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        external = normalize_macro_external(macro.get("外部补全"))
        n_ext = len(external)
        n_adopt = sum(1 for x in external if x.get("采用") is True)
        print(
            f"   📥 宏观选题: 外部补全={n_ext} 条, 采用={n_adopt} 条, raw_len={len(raw)}",
            flush=True,
        )
        if n_ext <= 0:
            last_errors = ["宏观选题外部补全为空或未解析到"]
            print(f"⚠️ source plan 未通过: {last_errors[0]}", flush=True)
            continue

        n_refs = macro_reference_count(macro, external)
        if n_refs > MAX_REFERENCE_WORKS:
            last_errors = [
                f"参考著作超过硬上限 {MAX_REFERENCE_WORKS} 条（当前 {n_refs}）；"
                f"只返回最重要的 {MAX_REFERENCE_WORKS} 个，勿罗列次要书目"
            ]
            print(f"⚠️ source plan 未通过: {last_errors[0]}", flush=True)
            continue

        # 先并入骨架：禁同卷降级 + 全书母本判重
        draft = merge_llm_plan_decisions(
            skeleton, build_decision_from_macro(entry_id, recalled, macro, external)
        )
        from lib.plan_postprocess import finalize_external

        finalize_external(draft, recalled)
        apply_external_mother_dedupe(
            draft, entry_id=entry_id, use_llm=True
        )
        external = [
            x for x in (draft.get("外部补全") or []) if isinstance(x, dict)
        ]
        n_adopt2 = sum(1 for x in external if x.get("采用") is True)
        print(f"   🔎 判重后采用={n_adopt2} 条", flush=True)

        touch_heartbeat(wd, entry_id, stage="plan_anchor", detail=plan_file.name)
        print("🧭 外部补全挂锚 → 分批嵌入点", flush=True)
        external, anchor_raw = run_anchor_external(
            entry_id,
            recalled,
            external,
            list(skeleton.get("母本逐句清单") or []),
            session_id=f"{session_id}-anchor-r{attempt}" if attempt else f"{session_id}-anchor",
        )
        if anchor_raw:
            try:
                plan_file.with_suffix(".anchor.raw.txt").write_text(
                    anchor_raw, encoding="utf-8"
                )
            except OSError:
                pass

        llm_plan = build_decision_from_macro(entry_id, recalled, macro, external)
        try:
            plan_file.with_suffix(".llm.json").write_text(
                json.dumps(llm_plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        merged = merge_llm_plan_decisions(skeleton, llm_plan)
        # 宏观路径已做一次判重；落盘再跑脚本闸（默认不开二次 LLM）
        save_plan(plan_file, merged, recalled, external_dedupe_llm=False)
        ok, last_errors = verify_plan(entry_id, recalled, plan_file)
        if ok:
            ok_load, accepted, _ = load_plan(plan_file)
            if ok_load:
                save_plan(
                    plan_file,
                    apply_reference_works_cap(accepted),
                    recalled,
                    external_dedupe_llm=False,
                )
            return True, []
        print(
            f"⚠️ source plan 未通过: {last_errors[0] if last_errors else '?'}",
            flush=True,
        )

    return False, last_errors


def _ensure_source_plan_legacy(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
    *,
    session_id: str,
    work_dir: Path | None,
    initial_errors: List[str],
) -> tuple[bool, List[str]]:
    """旧路径：整包 source_plan prompt（TRANSLATE_EXTERNAL_MACRO=0）。"""
    wd = work_dir or plan_file.parent
    max_retries = _plan_max_retries()
    last_errors = list(initial_errors)
    skeleton = build_plan_skeleton(recalled)

    for attempt in range(max_retries + 1):
        need_feedback = attempt > 0 or any("空数组" in e for e in last_errors)
        prompt = build_source_plan_prompt(
            entry_id,
            recalled,
            recalled_summary(recalled),
            plan_file,
            retry_feedback=(
                _format_plan_retry_feedback(last_errors) if need_feedback else ""
            ),
        )
        label = f"生成 source plan → {plan_file}"
        if attempt:
            label = f"重试 source plan（{attempt}/{max_retries}）→ {plan_file}"
        print(f"🧭 {label}", flush=True)
        touch_heartbeat(
            wd,
            entry_id,
            stage="plan",
            detail=f"{plan_file.name}" + (f" retry={attempt}" if attempt else ""),
        )
        _llm_turn(
            wd,
            entry_id,
            "plan",
            prompt,
            session_id=f"{session_id}-r{attempt}" if attempt else session_id,
            timeout_sec=900,
            artifact_paths={"plan": plan_file},
        )
        ok_load, llm_plan, load_errs = load_plan(plan_file)
        if not ok_load:
            last_errors = load_errs or ["plan 落盘失败"]
            continue
        raw_ext = llm_plan.get("外部补全") if isinstance(llm_plan, dict) else None
        raw_cl = llm_plan.get("母本逐句清单") if isinstance(llm_plan, dict) else None
        n_ext = len(raw_ext) if isinstance(raw_ext, list) else -1
        n_cl = len(raw_cl) if isinstance(raw_cl, list) else 0
        print(
            f"   📥 LLM plan 落盘: 外部补全={n_ext} 条, 母本清单={n_cl} 条"
            + ("（长文决策包）" if n_cl == 0 and n_ext >= 0 else ""),
            flush=True,
        )
        try:
            llm_dump = plan_file.with_suffix(".llm.json")
            llm_dump.write_text(
                json.dumps(llm_plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        from lib.plan_postprocess import MAX_REFERENCE_WORKS, apply_reference_works_cap

        raw_refs = llm_plan.get("参考著作") if isinstance(llm_plan, dict) else None
        if isinstance(raw_refs, list):
            seen_refs: List[str] = []
            for r in raw_refs:
                s = str(r or "").strip()
                if s and s not in seen_refs:
                    seen_refs.append(s)
            if len(seen_refs) > MAX_REFERENCE_WORKS:
                last_errors = [
                    f"参考著作超过硬上限 {MAX_REFERENCE_WORKS} 条（当前 {len(seen_refs)}）；"
                    f"只返回最重要的 {MAX_REFERENCE_WORKS} 个，勿罗列次要书目"
                ]
                print(f"⚠️ source plan 未通过: {last_errors[0]}", flush=True)
                continue

        merged = merge_llm_plan_decisions(skeleton, llm_plan)
        save_plan(plan_file, merged, recalled, external_dedupe_llm=True)
        ok, last_errors = verify_plan(entry_id, recalled, plan_file)
        if ok:
            ok_load, accepted, _ = load_plan(plan_file)
            if ok_load:
                save_plan(
                    plan_file,
                    apply_reference_works_cap(accepted),
                    recalled,
                    external_dedupe_llm=False,
                )
            return True, []
        print(
            f"⚠️ source plan 未通过: {last_errors[0] if last_errors else '?'}",
            flush=True,
        )

    return False, last_errors


def _plan_json_for_mother(plan_data: Dict[str, Any]) -> str:
    return json.dumps(plan_for_mother_phase(plan_data), ensure_ascii=False, indent=2)


def _plan_json_for_enrich(plan_data: Dict[str, Any]) -> str:
    return json.dumps(plan_for_enrich_phase(plan_data), ensure_ascii=False, indent=2)


def _phase1_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE1_MAX_RETRIES", "4")))


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


def _phase2_temperature(*, attempt: int = 0, under_rewrite: bool = False) -> float:
    """Phase2 润色温度；誊抄重试只小幅抬温，避免「看官表演感」飙升。"""
    base = float(os.environ.get("TRANSLATE_PHASE2_TEMPERATURE", "0.45"))
    if under_rewrite:
        # 旧逻辑可到 0.85；改为封顶约 0.6，靠提示词/门禁逼改表达而非演戏
        return min(0.62, max(base, 0.5) + 0.03 * max(0, attempt - 1))
    if attempt > 0:
        return min(0.58, base + 0.05 * attempt)
    return base


def _apply_attribution_polish(
    target: Path,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
) -> None:
    """Phase2 落盘后：归因清洗 + 弯引原文改「」+ 本传缺漏退场补全。"""
    if not target.is_file():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    detail = str(data.get("翻译详情") or "")
    fixed, changes = apply_attribution_fixes(detail, recalled, plan_data)
    from lib.citation_mode import apply_quote_style_fixes

    quote_fixed, quote_changes = apply_quote_style_fixes(fixed, plan_data)
    if quote_changes:
        fixed = quote_fixed
        changes = list(changes) + list(quote_changes)
    if not changes:
        return
    data["翻译详情"] = fixed
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"   🔧 归因修复: {', '.join(changes[:4])}", flush=True)


def _rebuild_output_references(
    target: Path,
    recalled: Dict[str, Any],
    plan_data: Dict[str, Any],
) -> None:
    """Phase2 后程序重建文末参考著作（按正文《》；去掉·相关卷占位）。"""
    from lib.phase2_batch import append_reference_section

    if not target.is_file():
        return
    ok, data, _ = load_output_from_path(target)
    if not ok or not data:
        return
    detail = str(data.get("翻译详情") or "").strip()
    if not detail:
        return
    rebuilt = append_reference_section(detail, plan_data, recalled)
    if rebuilt == detail:
        return
    data["翻译详情"] = rebuilt
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("   🔧 已按正文引用重建参考著作", flush=True)


def _phase2_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE2_MAX_RETRIES", "5")))


def _verify_enrich_with_autofix(
    entry_id: str,
    recalled: Dict[str, Any],
    target: Path,
    plan_data: Dict[str, Any],
    *,
    mother_text: str = "",
) -> Tuple[bool, List[str]]:
    """Phase2 质检；落盘后先跑归因脚本清洗再验。"""
    _apply_attribution_polish(target, recalled, plan_data)
    return verify_enrich_draft(
        entry_id, recalled, target, plan=plan_data, mother_text=mother_text
    )


def _try_enrich_landing_patch(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    chapter_target: Path,
    chapter_plan: Dict[str, Any],
    chapter_mother: str,
    label: str,
    session_id: str,
    work_dir: Path,
    slice_errs: List[str],
) -> Tuple[bool, List[str]]:
    """L2 定向补洞：仅补全落地失败时插入缺失句，避免整章重写。"""
    from lib.enrich_landing import (
        apply_landing_inserts,
        build_landing_patch_prompt,
        enrich_patch_max,
        is_landing_only_failure,
        load_detail_from_enrich_file,
        missing_landing_items,
        save_detail_to_enrich_file,
        _extract_json_obj,
    )

    if enrich_patch_max() <= 0 or not is_landing_only_failure(slice_errs):
        return False, slice_errs

    body = load_detail_from_enrich_file(chapter_target)
    missing = missing_landing_items(body, chapter_plan)
    if not missing:
        # 可能是索引书名缺失；L2 暂只处理外部补全逐条
        return False, slice_errs

    last_errs = list(slice_errs)
    for pi in range(enrich_patch_max()):
        patch_file = chapter_target.with_name(
            f"{chapter_target.stem}.patch{pi + 1}.json"
        )
        prompt = build_landing_patch_prompt(
            entry_id=entry_id,
            chapter_body=body,
            missing=missing,
            output_file=patch_file,
        )
        print(
            f"   🩹 Phase2 定向补洞 {label}："
            f"{len(missing)} 条未落地 → {patch_file.name}"
            f"（{pi + 1}/{enrich_patch_max()}）",
            flush=True,
        )
        _llm_turn(
            work_dir,
            entry_id,
            "enrich_patch",
            prompt,
            session_id=f"{session_id}-patch{pi + 1}",
            timeout_sec=300,
            artifact_paths={"output": patch_file},
            temperature=0.2,
        )
        raw = ""
        if patch_file.is_file():
            raw = patch_file.read_text(encoding="utf-8")
        obj = _extract_json_obj(raw)
        if not obj or not isinstance(obj.get("inserts"), list):
            last_errs = [f"{label}：定向补洞未返回 inserts JSON"]
            print(f"   ⚠️ {last_errs[0]}", flush=True)
            continue
        new_body, n = apply_landing_inserts(body, obj.get("inserts") or [])
        if n <= 0:
            last_errs = [f"{label}：定向补洞 marker 未命中正文"]
            print(f"   ⚠️ {last_errs[0]}", flush=True)
            continue
        save_detail_to_enrich_file(chapter_target, entry_id, new_body)
        print(f"   ✅ 定向补洞已插入 {n} 处", flush=True)
        body = new_body
        ok, errs = verify_enrich_batch_slice(
            entry_id,
            recalled,
            chapter_target,
            batch_mother_text=chapter_mother,
            batch_label=label,
            plan=chapter_plan,
        )
        if ok:
            return True, []
        last_errs = errs or last_errs
        missing = missing_landing_items(body, chapter_plan)
        if not missing or not is_landing_only_failure(last_errs):
            break
    return False, last_errs


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

    from lib.longform_compat import join_narrative_parts

    cleaned = [p for p in parts if p.strip()]
    combined = join_narrative_parts(cleaned)
    from lib.citation_mode import apply_quote_style_fixes

    combined, q_changes = apply_quote_style_fixes(combined, plan_data)
    if q_changes:
        print(f"   🔧 合并母本：{', '.join(q_changes)}", flush=True)
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
            from lib.longform_compat import mother_batch_guard_note

            m_ids = [
                str(x.get("编号") or "")
                for x in checklist
                if isinstance(x, dict) and x.get("编号")
            ]
            batch_note = mother_batch_guard_note(batch_label=batch_label, m_ids=m_ids)
        from lib.recalled_window import (
            batch_window_guard_note,
            build_mother_batch_m_payload,
        )

        # Phase1：按本批 M 原文摘句注入（与分批口径一致）；禁止整段灌窗
        window_payload = build_mother_batch_m_payload(
            recalled, checklist if isinstance(checklist, list) else []
        )
        recalled_json = json.dumps(window_payload, ensure_ascii=False, indent=2)
        window_note = batch_window_guard_note(window_payload)
        m_prompt = (
            build_translate_mother_prompt(
                entry_id,
                recalled,
                recalled_json,
                mother_plan_json,
                mother_file,
            )
            + batch_note
            + window_note
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
            print("   🔧 已修正 Phase1 误用书名号", flush=True)
        # 弯引装未译原文 → 自动改「」，避免无意义重试烧批
        try:
            data = json.loads(mother_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            key = "母本顺译" if "母本顺译" in data else "翻译详情"
            body = str(data.get(key) or "")
            from lib.citation_mode import apply_quote_style_fixes

            fixed, q_changes = apply_quote_style_fixes(body, plan_data)
            if q_changes:
                data[key] = fixed
                mother_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"   🔧 引号风格: {', '.join(q_changes)}", flush=True)
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


def _run_phase2_enrich_chaptered(
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
) -> Tuple[bool, List[str], float]:
    """长母本 Phase2：分章 enrich + 上章声口样例，再合并终稿。"""
    from lib.phase2_batch import (
        concatenate_mother_batch_texts,
        build_chapter_enrich_prompt,
        discover_mother_batches,
        extract_voice_sample,
        group_batches_into_chapters,
        merge_enrich_batches,
        phase2_chapter_batch_count,
        style_density_warnings,
    )

    batch_files = discover_mother_batches(mother_file)
    chapters = group_batches_into_chapters(batch_files)
    total = len(chapters)
    per = phase2_chapter_batch_count()
    print(
        f"📖 Phase2 分章说书 {entry_id}：{len(batch_files)} 母本批 → {total} 章"
        f"（每章约 {per} 批；上章声口样例续写）",
        flush=True,
    )
    parts: List[str] = []
    voice_sample = ""
    for ci, chapter_files in enumerate(chapters, start=1):
        # batch 文件名 …-b01.json → 序号与 Phase1 批号一致（1-based 按排序）
        batch_nos: List[int] = []
        for bf in chapter_files:
            m = re.search(r"-b(\d+)\.", bf.name)
            batch_nos.append(int(m.group(1)) if m else (len(batch_nos) + 1))
        chapter_mother = concatenate_mother_batch_texts(chapter_files)
        chapter_target = mother_file.with_name(
            f"{mother_file.stem}-ch{ci:02d}.enrich.json"
        )
        label = f"第 {ci}/{total} 章（b{batch_nos[0]:02d}–b{batch_nos[-1]:02d}）"
        chapter_ok = False
        chapter_errs: List[str] = []
        for attempt in range(_phase2_max_retries() + 1):
            retry_note = ""
            if attempt > 0 and chapter_errs:
                plan_fb = classify_translate_failure(
                    chapter_errs, stage="phase2", fail_count=attempt
                )
                retry_note = (
                    "\n\n--- 上轮 Phase2 质检失败，须修正 ---\n"
                    + format_retry_feedback(plan_fb, chapter_errs)
                )
                if any("誊抄" in e or "改表达" in e or "重合" in e for e in chapter_errs):
                    head = (chapter_mother or "").strip().split("\n\n")[0][:120]
                    retry_note += (
                        "\n\n【改表达 · 硬重试】禁止几乎原样粘贴 Phase1；"
                        "同信息必须换句式与用词（口语/场面/释义旁白），"
                        "目标与母本去虚词 4-gram 重合显著低于 95%。\n"
                        "【覆盖 · 硬】必须从本章母本**开头情节**写起，不得跳章；"
                        f"本章母本首段起句供核对：{head}…"
                    )
                # 经典「」漏嵌时把原文摘句再顶一遍，避免只见白话母本
                if any("经典引用候选" in e or "直角「」" in e for e in chapter_errs):
                    from lib.phase2_batch import (
                        batch_checklist_items,
                        classic_quote_must_embed_note,
                    )

                    _c_items: List[Dict[str, Any]] = []
                    for bn in batch_nos:
                        _c_items.extend(batch_checklist_items(plan_data, bn))
                    retry_note += classic_quote_must_embed_note(_c_items)
            prompt = (
                build_chapter_enrich_prompt(
                    entry_id,
                    recalled,
                    plan_data,
                    chapter_mother,
                    chapter_target,
                    chapter_no=ci,
                    total_chapters=total,
                    batch_nos=batch_nos,
                    include_intro=(ci == 1),
                    voice_sample=voice_sample,
                )
                + retry_note
                + _repair_feedback_suffix()
            )
            print(
                f"⏳ Phase2 说书润色 {entry_id} {label} → {chapter_target.name}"
                + (f"（重试 {attempt}/{_phase2_max_retries()}）" if attempt else ""),
                flush=True,
            )
            under_rw = any(
                "誊抄" in e or "重合" in e for e in (chapter_errs or [])
            )
            _llm_turn(
                work_dir,
                entry_id,
                "enrich",
                prompt,
                session_id=f"{session_id}-enrich-ch{ci}-r{attempt}",
                timeout_sec=900,
                artifact_paths={"output": chapter_target},
                temperature=_phase2_temperature(
                    attempt=attempt, under_rewrite=under_rw
                ),
            )
            if not chapter_target.is_file():
                chapter_errs = [f"Phase2 {label}: LLM 未落盘本章译稿"]
                print(f"⚠️ {chapter_errs[0]}", flush=True)
                continue
            if polish_enrich_file(chapter_target):
                print("   🔧 已自动修正本章模糊出处表述", flush=True)
            from lib.citation_mode import apply_quote_style_fixes_to_file
            from lib.phase2_batch import batch_checklist_items, plan_for_enrich_batch

            q_changes = apply_quote_style_fixes_to_file(chapter_target, plan_data)
            if q_changes:
                print(f"   🔧 引号风格: {', '.join(q_changes)}", flush=True)

            ch_items: List[Dict[str, Any]] = []
            for bn in batch_nos:
                ch_items.extend(batch_checklist_items(plan_data, bn))
            chapter_plan = plan_for_enrich_batch(plan_data, ch_items)
            slice_ok, slice_errs = verify_enrich_batch_slice(
                entry_id,
                recalled,
                chapter_target,
                batch_mother_text=chapter_mother,
                batch_label=label,
                plan=chapter_plan,
            )
            if not slice_ok:
                chapter_errs = slice_errs or [f"Phase2 {label}: 本章质检未通过"]
                patched_ok, patched_errs = _try_enrich_landing_patch(
                    entry_id,
                    recalled,
                    chapter_target=chapter_target,
                    chapter_plan=chapter_plan,
                    chapter_mother=chapter_mother,
                    label=label,
                    session_id=f"{session_id}-enrich-ch{ci}-r{attempt}",
                    work_dir=work_dir,
                    slice_errs=chapter_errs,
                )
                if patched_ok:
                    chapter_body = _load_mother_text(chapter_target)
                    parts.append(chapter_body)
                    voice_sample = extract_voice_sample(chapter_body)
                    chapter_ok = True
                    break
                if patched_errs:
                    chapter_errs = patched_errs
                print(f"⚠️ Phase2 {label} 未通过: {chapter_errs[0]}", flush=True)
                continue
            chapter_body = _load_mother_text(chapter_target)
            parts.append(chapter_body)
            voice_sample = extract_voice_sample(chapter_body)
            chapter_ok = True
            break
        if not chapter_ok:
            return False, chapter_errs or [f"Phase2 {label} 失败"], time.time() - t0

    combined = merge_enrich_batches(entry_id, parts, plan_data, recalled)
    for w in style_density_warnings(combined):
        print(f"   ⚠️ {w}", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"史略ID": entry_id, "翻译详情": combined}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    if polish_enrich_file_full(target):
        print("   🔧 已自动修正模糊出处表述", flush=True)
    _rebuild_output_references(target, recalled, plan_data)
    touch_heartbeat(work_dir, entry_id, stage="verify_enrich")
    e_ok, e_errs = _verify_enrich_with_autofix(
        entry_id, recalled, target, plan_data, mother_text=_load_mother_text(mother_file)
    )
    if not e_ok:
        return False, [f"Phase2: {e}" for e in e_errs], time.time() - t0
    return True, [], time.time() - t0


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
) -> Tuple[bool, List[str], float]:
    """长母本 Phase2（旧路径）：按 Phase1 分批文件逐批 enrich，再合并终稿。"""
    from lib.phase2_batch import (
        build_batch_enrich_prompt,
        discover_mother_batches,
        merge_enrich_batches,
        phase2_batch_char_threshold,
    )

    batches = discover_mother_batches(mother_file)
    total = len(batches)
    print(
        f"📦 Phase2 旧分批补全 {entry_id}：{total} 批"
        f"（母本 >{phase2_batch_char_threshold()} 字；TRANSLATE_PHASE2_MODE=legacy_batch）",
        flush=True,
    )
    parts: List[str] = []
    for bi, batch_file in enumerate(batches, start=1):
        batch_mother = _load_mother_text(batch_file)
        batch_target = batch_file.with_suffix(".enrich.json")
        label = f"第 {bi}/{total} 批"
        batch_ok = False
        batch_errs: List[str] = []
        for attempt in range(_phase2_max_retries() + 1):
            retry_note = ""
            if attempt > 0 and batch_errs:
                plan_fb = classify_translate_failure(
                    batch_errs, stage="phase2", fail_count=attempt
                )
                retry_note = (
                    "\n\n--- 上轮 Phase2 质检失败，须修正 ---\n"
                    + format_retry_feedback(plan_fb, batch_errs)
                )
            prompt = (
                build_batch_enrich_prompt(
                    entry_id,
                    recalled,
                    plan_data,
                    batch_mother,
                    batch_target,
                    batch_no=bi,
                    total_batches=total,
                    include_intro=(bi == 1),
                )
                + retry_note
                + _repair_feedback_suffix()
            )
            print(
                f"⏳ Phase2 补全 {entry_id} {label} → {batch_target.name}"
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
                temperature=_phase2_temperature(),
            )
            if not batch_target.is_file():
                batch_errs = [f"Phase2 {label}: LLM 未落盘本批译稿"]
                print(f"⚠️ {batch_errs[0]}", flush=True)
                continue
            if polish_enrich_file(batch_target):
                print("   🔧 已自动修正本批模糊出处表述", flush=True)
            from lib.citation_mode import apply_quote_style_fixes_to_file
            from lib.phase2_batch import batch_checklist_items, plan_for_enrich_batch

            q_changes = apply_quote_style_fixes_to_file(batch_target, plan_data)
            if q_changes:
                print(f"   🔧 引号风格: {', '.join(q_changes)}", flush=True)

            b_items = batch_checklist_items(plan_data, bi)
            batch_plan = plan_for_enrich_batch(plan_data, b_items)
            slice_ok, slice_errs = verify_enrich_batch_slice(
                entry_id,
                recalled,
                batch_target,
                batch_mother_text=batch_mother,
                batch_label=label,
                plan=batch_plan,
            )
            if not slice_ok:
                batch_errs = slice_errs or [f"Phase2 {label}: 本批质检未通过"]
                patched_ok, patched_errs = _try_enrich_landing_patch(
                    entry_id,
                    recalled,
                    chapter_target=batch_target,
                    chapter_plan=batch_plan,
                    chapter_mother=batch_mother,
                    label=label,
                    session_id=f"{session_id}-enrich-b{bi}-r{attempt}",
                    work_dir=work_dir,
                    slice_errs=batch_errs,
                )
                if patched_ok:
                    batch_body = _load_mother_text(batch_target)
                    parts.append(batch_body)
                    batch_ok = True
                    break
                if patched_errs:
                    batch_errs = patched_errs
                print(f"⚠️ Phase2 {label} 未通过: {batch_errs[0]}", flush=True)
                continue
            batch_body = _load_mother_text(batch_target)
            parts.append(batch_body)
            batch_ok = True
            break
        if not batch_ok:
            return False, batch_errs or [f"Phase2 {label} 失败"], time.time() - t0

    combined = merge_enrich_batches(entry_id, parts, plan_data, recalled)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"史略ID": entry_id, "翻译详情": combined}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    if polish_enrich_file_full(target):
        print("   🔧 已自动修正模糊出处表述", flush=True)
    _rebuild_output_references(target, recalled, plan_data)
    touch_heartbeat(work_dir, entry_id, stage="verify_enrich")
    e_ok, e_errs = _verify_enrich_with_autofix(
        entry_id, recalled, target, plan_data, mother_text=_load_mother_text(mother_file)
    )
    if not e_ok:
        return False, [f"Phase2: {e}" for e in e_errs], time.time() - t0
    return True, [], time.time() - t0


def _phase2_use_legacy_enrich() -> bool:
    """旧「分章+plan 补全」路径；默认关闭，走 polish（长卷可分章 polish）。"""
    raw = (os.environ.get("TRANSLATE_PHASE2_MODE") or "polish").strip().lower()
    return raw in {"enrich", "enrich_legacy", "legacy", "legacy_batch", "batch"}


def _phase2_force_whole_polish() -> bool:
    raw = (os.environ.get("TRANSLATE_PHASE2_MODE") or "polish").strip().lower()
    return raw in {"polish_whole", "whole", "full"}


def _phase2_force_chapter_polish() -> bool:
    raw = (os.environ.get("TRANSLATE_PHASE2_MODE") or "polish").strip().lower()
    return raw in {"polish_chapter", "chapter_polish", "chapter"}


def _phase2_should_chapter_polish(mother_body: str, mother_file: Path) -> bool:
    """长卷默认分章说书润色（同一套 polish 规则切片）。"""
    if _phase2_force_whole_polish():
        return False
    if _phase2_force_chapter_polish():
        return True
    from lib.phase2_batch import discover_mother_batches, phase2_batch_char_threshold

    long_cut = max(
        phase2_batch_char_threshold(),
        int(os.environ.get("TRANSLATE_PHASE2_LONG_MOTHER_CHARS", "8000") or "8000"),
    )
    batches = discover_mother_batches(mother_file)
    return len(mother_body or "") > long_cut and len(batches) >= 2


def _phase2_thin_or_overlap_fail(errs: List[str]) -> bool:
    return any(
        ("偏薄" in e) or ("誊抄" in e) or ("重合" in e) or ("变薄" in e)
        for e in (errs or [])
    )


def _run_phase2_polish_chaptered(
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
    out_dir: Optional[Path] = None,
) -> Tuple[bool, List[str], float]:
    """长母本 Phase2：按章界切母本，逐章 polish（非 enrich 打卡）。"""
    from lib.enrich_landing import load_detail_from_enrich_file
    from lib.openclaw import build_translate_polish_prompt
    from lib.phase2_batch import (
        concatenate_mother_batch_texts,
        discover_mother_batches,
        extract_voice_sample,
        group_batches_into_chapters,
        merge_enrich_batches,
        phase2_chapter_batch_count,
        style_density_warnings,
    )
    from lib.phase3_qa import apply_post_polish_heals, verify_polish_draft_light
    from lib.source_text import build_source_original

    del mother_body
    source_original = build_source_original(recalled)
    batch_files = discover_mother_batches(mother_file)
    chapters = group_batches_into_chapters(batch_files)
    total = len(chapters)
    per = phase2_chapter_batch_count()
    print(
        f"📖 Phase2 分章润色 {entry_id}：{len(batch_files)} 母本批 → {total} 章"
        f"（每章约 {per} 批；同一套 polish 规则 + 上章声口样例）",
        flush=True,
    )
    parts: List[str] = []
    voice_sample = ""
    for ci, chapter_files in enumerate(chapters, start=1):
        batch_nos: List[int] = []
        for bf in chapter_files:
            m = re.search(r"-b(\d+)\.", bf.name)
            batch_nos.append(int(m.group(1)) if m else (len(batch_nos) + 1))
        chapter_mother = concatenate_mother_batch_texts(chapter_files)
        chapter_target = mother_file.with_name(
            f"{mother_file.stem}-ch{ci:02d}.polish.json"
        )
        label = f"第 {ci}/{total} 章（b{batch_nos[0]:02d}–b{batch_nos[-1]:02d}）"
        chapter_ok = False
        chapter_errs: List[str] = []
        for attempt in range(_phase2_max_retries() + 1):
            retry_note = ""
            if attempt > 0 and chapter_errs:
                plan_fb = classify_translate_failure(
                    chapter_errs, stage="phase2", fail_count=attempt
                )
                retry_note = (
                    "\n\n--- 上轮本章润色未通过，请修正（仍只写本章）---\n"
                    + format_retry_feedback(plan_fb, chapter_errs)
                )
                if _phase2_thin_or_overlap_fail(chapter_errs):
                    head = (chapter_mother or "").strip().split("\n\n")[0][:120]
                    retry_note += (
                        "\n\n【加厚·改表达 · 硬重试】禁止近誊抄；"
                        "须明显加讲解/场面/异说，并换句式；"
                        "长卷与母本去虚词 4-gram 重合须显著低于 85%。\n"
                        "【成文洁净 · 硬】保持第三人称历史叙事；"
                        "禁止「看官/听客/上回/下回/今儿个/这位爷/本篇以」；"
                        "自然感来自句法，不来自说书场表演。\n"
                        f"本章母本首段起句供核对：{head}…"
                    )
            e_prompt = (
                build_translate_polish_prompt(
                    entry_id,
                    chapter_mother,
                    chapter_target,
                    source_original=source_original,
                    chapter_no=ci,
                    total_chapters=total,
                    voice_sample=voice_sample,
                    include_intro=(ci == 1),
                    include_epilogue=(ci == total),
                    intro_material=(
                        plan_data.get("前置引入素材")
                        if isinstance(plan_data.get("前置引入素材"), dict)
                        else None
                    ),
                )
                + retry_note
            )
            print(
                f"⏳ Phase2 分章润色 {entry_id} {label} → {chapter_target.name}"
                + (f"（重试 {attempt}/{_phase2_max_retries()}）" if attempt else ""),
                flush=True,
            )
            under_rw = _phase2_thin_or_overlap_fail(chapter_errs)
            _llm_turn(
                work_dir,
                entry_id,
                "enrich",
                e_prompt,
                session_id=f"{session_id}-polish-ch{ci}-r{attempt}",
                timeout_sec=1200,
                artifact_paths={"output": chapter_target},
                temperature=_phase2_temperature(
                    attempt=attempt, under_rewrite=under_rw
                ),
            )
            if not chapter_target.is_file():
                chapter_errs = [f"Phase2 {label}: LLM 未落盘本章译稿"]
                print(f"⚠️ {chapter_errs[0]}", flush=True)
                continue
            if polish_enrich_file(chapter_target):
                print("   🔧 已自动修正本章模糊出处表述", flush=True)
            heals = apply_post_polish_heals(
                chapter_target,
                entry_id,
                plan=plan_data,
                source_original=source_original,
                mother=chapter_mother,
            )
            if heals:
                print(f"   🔧 本章愈合: {', '.join(heals)}", flush=True)
            chapter_body = load_detail_from_enrich_file(chapter_target)
            e_ok, e_errs = verify_polish_draft_light(
                entry_id=entry_id,
                detail=chapter_body if "参考著作" in chapter_body else (chapter_body + "\n\n参考著作\n- 《史记》"),
                mother=chapter_mother,
                source_original=source_original,
                plan=plan_data,
                check_intro=(ci == 1),
                check_epilogue=(ci == total),
            )
            # 分章阶段不做全书基线回归（合并后再检）；非末章不拦参考著作
            e_errs = [
                e
                for e in e_errs
                if "旧优稿" not in e and "关键收束" not in e
            ]
            if ci < total:
                e_errs = [e for e in e_errs if "参考著作" not in e]
            if not e_errs:
                parts.append(chapter_body)
                voice_sample = extract_voice_sample(chapter_body)
                chapter_ok = True
                break
            chapter_errs = e_errs
            print(f"⚠️ Phase2 {label} 未通过: {chapter_errs[0]}", flush=True)
        if not chapter_ok:
            return False, chapter_errs or [f"Phase2 {label} 失败"], time.time() - t0

    combined = merge_enrich_batches(entry_id, parts, plan_data, recalled)
    for w in style_density_warnings(combined):
        print(f"   ⚠️ {w}", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"史略ID": entry_id, "翻译详情": combined}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    if polish_enrich_file_full(target):
        print("   🔧 已自动修正模糊出处表述", flush=True)
    _rebuild_output_references(target, recalled, plan_data)
    heals = apply_post_polish_heals(
        target,
        entry_id,
        plan=plan_data,
        source_original=source_original,
        mother=_load_mother_text(mother_file),
    )
    if heals:
        print(f"   🔧 合并后愈合: {', '.join(heals)}", flush=True)
    detail = _load_mother_text(target)
    full_mother = _load_mother_text(mother_file)
    e_ok, e_errs = verify_polish_draft_light(
        entry_id=entry_id,
        detail=detail,
        mother=full_mother,
        source_original=source_original,
        out_dir=out_dir,
        entry_name=entry_name,
        plan=plan_data,
        check_intro=True,
        check_epilogue=True,
    )
    if not e_ok:
        return False, [f"Phase2: {e}" for e in e_errs], time.time() - t0
    from lib.coverage_ledger import clear_ledger

    clear_ledger(work_dir, entry_id)
    print("   🔧 已清空覆盖账本（成稿相对母本重验，不沿用 Phase1 conveyed）", flush=True)
    return True, [], time.time() - t0


def _run_phase2_polish(
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
    out_dir: Optional[Path] = None,
    allow_chapter_fallback: bool = True,
) -> Tuple[bool, List[str], float]:
    """Phase2 整篇润色：一次喂全文；偏薄/高重合耗尽重试后可降级分章。"""
    from lib.enrich_landing import load_detail_from_enrich_file
    from lib.mother_span import (
        format_span_hole_retry_note,
        locate_span_backfill_slots,
    )
    from lib.phase3_qa import apply_post_polish_heals, verify_polish_draft_light
    from lib.source_text import build_source_original

    source_original = build_source_original(recalled)
    e_errs: List[str] = []
    e_ok = False
    for attempt in range(_phase2_max_retries() + 1):
        span_drop = any("整段漏" in e for e in (e_errs or []))
        if attempt > 0 and span_drop and target.is_file():
            current = load_detail_from_enrich_file(target)
            slots = locate_span_backfill_slots(
                current, mother_body, source_original
            )
            if slots:
                print(
                    f"   🔧 定位到 {len(slots)} 处漏段夹缝，本轮局部补洞（不程序插原文）",
                    flush=True,
                )
                e_prompt = build_translate_polish_backfill_prompt(
                    entry_id,
                    mother_body,
                    current,
                    target,
                    format_span_hole_retry_note(
                        [s.hole for s in slots], slots=slots
                    ),
                )
            else:
                plan_fb = classify_translate_failure(
                    e_errs, stage="phase2", fail_count=attempt
                )
                e_prompt = build_translate_polish_prompt(
                    entry_id,
                    mother_body,
                    target,
                    source_original=source_original,
                    intro_material=(
                        plan_data.get("前置引入素材")
                        if isinstance(plan_data.get("前置引入素材"), dict)
                        else None
                    ),
                ) + (
                    "\n\n--- 上轮 Phase2 未通过，请整篇修正（仍不分章）---\n"
                    + format_retry_feedback(plan_fb, e_errs)
                )
        else:
            retry_note = ""
            if attempt > 0 and e_errs:
                plan_fb = classify_translate_failure(
                    e_errs, stage="phase2", fail_count=attempt
                )
                retry_note = (
                    "\n\n--- 上轮 Phase2 未通过，请整篇修正（仍不分章）---\n"
                    + format_retry_feedback(plan_fb, e_errs)
                )
            e_prompt = (
                build_translate_polish_prompt(
                    entry_id,
                    mother_body,
                    target,
                    source_original=source_original,
                    intro_material=(
                        plan_data.get("前置引入素材")
                        if isinstance(plan_data.get("前置引入素材"), dict)
                        else None
                    ),
                )
                + retry_note
            )
        print(
            f"⏳ Phase2 整篇润色 {entry_id} → {target.name}"
            + (f"（重试 {attempt}/{_phase2_max_retries()}）" if attempt else ""),
            flush=True,
        )
        under_rw = _phase2_thin_or_overlap_fail(e_errs)
        _llm_turn(
            work_dir,
            entry_id,
            "enrich",
            e_prompt,
            session_id=f"{session_id}-polish-r{attempt}",
            timeout_sec=1200,
            artifact_paths={"output": target},
            temperature=_phase2_temperature(attempt=attempt, under_rewrite=under_rw),
        )
        if not target.is_file():
            e_errs = ["Phase2: LLM 未落盘最终译稿"]
            e_ok = False
            print(f"⚠️ Phase2 未通过: {e_errs[0]}", flush=True)
            continue
        if polish_enrich_file_full(target):
            print("   🔧 已自动修正模糊出处表述", flush=True)
        heals = apply_post_polish_heals(
            target,
            entry_id,
            plan=plan_data,
            source_original=source_original,
            mother=mother_body,
        )
        if heals:
            print(f"   🔧 润色后愈合: {', '.join(heals)}", flush=True)
        detail = _load_mother_text(target)
        e_ok, e_errs = verify_polish_draft_light(
            entry_id=entry_id,
            detail=detail,
            mother=mother_body,
            source_original=source_original,
            out_dir=out_dir,
            entry_name=entry_name,
            plan=plan_data,
            check_intro=True,
            check_epilogue=True,
        )
        if e_ok:
            break
        print(f"⚠️ Phase2 未通过: {e_errs[0] if e_errs else '?'}", flush=True)
    if not e_ok:
        # 整篇因偏薄/高重合耗尽 → 自动降级分章重跑一次
        can_fallback = (
            allow_chapter_fallback
            and not _phase2_force_whole_polish()
            and _phase2_thin_or_overlap_fail(e_errs)
            and len(discover_mother_batches_safe(mother_file)) >= 2
        )
        if can_fallback:
            print(
                "↪️ Phase2 整篇因偏薄/近誊抄耗尽重试，自动降级为分章润色…",
                flush=True,
            )
            return _run_phase2_polish_chaptered(
                entry_id,
                recalled,
                plan_data=plan_data,
                mother_body=mother_body,
                mother_file=mother_file,
                target=target,
                session_id=f"{session_id}-chfb",
                work_dir=work_dir,
                entry_name=entry_name,
                t0=t0,
                out_dir=out_dir,
            )
        return False, [f"Phase2: {e}" for e in e_errs], time.time() - t0
    from lib.coverage_ledger import clear_ledger

    clear_ledger(work_dir, entry_id)
    print("   🔧 已清空覆盖账本（成稿相对母本重验，不沿用 Phase1 conveyed）", flush=True)
    return True, [], time.time() - t0


def discover_mother_batches_safe(mother_file: Path) -> List[Path]:
    from lib.phase2_batch import discover_mother_batches

    return discover_mother_batches(mother_file)


def _run_phase3_qa(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_body: str,
    target: Path,
    session_id: str,
    work_dir: Path,
) -> Tuple[bool, List[str]]:
    """Phase3：只质检不重写。报告 → *.qa.md + *.qa.json。"""
    from lib.phase3_qa import (
        build_phase3_qa_prompt,
        merge_qa_report,
        phase3_enabled,
        program_qa_findings,
        _extract_qa_json,
    )

    from lib.source_text import build_source_original

    if not phase3_enabled():
        print("⏭️ Phase3 质检已关闭（TRANSLATE_PHASE3_QA=0）", flush=True)
        return True, []

    detail = _load_mother_text(target)
    prog = program_qa_findings(
        mother=mother_body,
        detail=detail,
        plan=plan_data,
        source_original=build_source_original(recalled),
    )
    qa_json_path = work_dir / f"{target.stem}.qa.json"
    qa_md_path = work_dir / f"{target.stem}.qa.md"
    core = str(recalled.get("母本著作") or recalled.get("母本卷名") or "").strip()
    if core and not core.startswith("《"):
        core = f"《{core}》"
    person = str(recalled.get("史略名称") or "").strip()
    prompt = build_phase3_qa_prompt(
        entry_id=entry_id,
        mother=mother_body,
        detail=detail,
        output_file=qa_md_path,
        program_findings=prog,
        core_source=core,
        person=person,
    )
    print(f"⏳ Phase3 第一轮质检 {entry_id} → {qa_md_path.name}", flush=True)
    touch_heartbeat(work_dir, entry_id, stage="phase3_qa")
    _llm_turn(
        work_dir,
        entry_id,
        "qa",
        prompt,
        session_id=f"{session_id}-qa",
        timeout_sec=900,
        artifact_paths={"markdown": qa_md_path},
        temperature=0.1,
    )
    raw = qa_md_path.read_text(encoding="utf-8") if qa_md_path.is_file() else ""
    # 若误写成 JSON 外壳
    if raw.strip().startswith("{") and "翻译详情" in raw[:80]:
        try:
            outer = json.loads(raw)
            if isinstance(outer, dict) and isinstance(outer.get("翻译详情"), str):
                raw = outer["翻译详情"]
                qa_md_path.write_text(raw + "\n", encoding="utf-8")
        except json.JSONDecodeError:
            pass
    llm_obj = _extract_qa_json(raw)
    report = merge_qa_report(prog, llm_obj)
    report["核心原典"] = core
    report["人物"] = person
    report["qa_md"] = str(qa_md_path)
    qa_json_path.write_text(
        json.dumps(
            {"史略ID": entry_id, "史略名称": recalled.get("史略名称"), **report},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    p0 = [x for x in report.get("问题") or [] if str(x.get("级别")) == "P0"]
    p1 = [x for x in report.get("问题") or [] if str(x.get("级别")) == "P1"]
    print(
        f"{'✅' if report.get('通过') else '📋'} Phase3 质检报告已写入 "
        f"{qa_md_path.name} / {qa_json_path.name}："
        f"P0={len(p0)} P1={len(p1)} 总问题={len(report.get('问题') or [])}",
        flush=True,
    )
    # 默认不因 P0 中断：后续自动 Phase4/5 消化；仅 TRANSLATE_PHASE3_BLOCK_ON_P0=1 且未开自动修复时才硬拦
    auto_repair = (os.environ.get("TRANSLATE_AUTO_REPAIR") or "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    block = (os.environ.get("TRANSLATE_PHASE3_BLOCK_ON_P0") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if report.get("通过") or auto_repair or not p0:
        return True, []
    if not block:
        return True, []
    errs = [
        f"Phase3[{x.get('类别')}]: {x.get('说明')}"
        for x in p0[:6]
    ] or ["Phase3: 质检未通过"]
    return False, errs


def _core_source_person(recalled: Dict[str, Any]) -> Tuple[str, str]:
    core = str(recalled.get("母本著作") or recalled.get("母本卷名") or "").strip()
    if core and not core.startswith("《"):
        core = f"《{core}》"
    person = str(recalled.get("史略名称") or "").strip()
    return core, person


def _run_phase4_repair(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    target: Path,
    session_id: str,
    work_dir: Path,
    accept_all_p0: bool = True,
) -> Tuple[bool, List[str]]:
    """Phase4：按质检清单自动定向修复（无人工确认；列入即修）。"""
    from lib.phase3_qa import (
        build_accepted_issue_text,
        build_phase4_repair_prompt,
        extract_repair_json,
        extract_repaired_body,
        issues_need_repair,
        load_qa_accept,
    )
    from lib.enrich_landing import save_detail_to_enrich_file

    detail = _load_mother_text(target)
    qa_json_path = work_dir / f"{target.stem}.qa.json"
    qa_md_path = work_dir / f"{target.stem}.qa.md"
    if not qa_json_path.is_file():
        return False, ["缺少 Phase3 报告（*.qa.json），请先跑 phase3"]
    qa_json = json.loads(qa_json_path.read_text(encoding="utf-8"))
    qa_md = qa_md_path.read_text(encoding="utf-8") if qa_md_path.is_file() else ""
    if not issues_need_repair(qa_json):
        print("⏭️ Phase4：无待修问题，跳过修复", flush=True)
        return True, []
    accept = load_qa_accept(work_dir / f"{target.stem}.qa.accept.json")
    # 默认自动采纳；accept 文件仅可加额外说明，不再当门禁
    del accept_all_p0  # 保留参数兼容调用方
    issues_text = build_accepted_issue_text(
        qa_md, qa_json, accept, auto=True, include_qa_md=False
    )
    core, _person = _core_source_person(recalled)
    before_path = work_dir / f"{target.stem}.before_repair.json"
    # 每次修复覆盖备份，保证 Phase5 对照的是本轮修复前
    before_path.write_text(
        json.dumps(
            {"史略ID": entry_id, "翻译详情": detail},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    repair_log = work_dir / f"{target.stem}.repair.md"
    prompt = build_phase4_repair_prompt(
        entry_id=entry_id,
        detail=detail,
        core_source=core,
        accepted_issues=issues_text,
        output_file=repair_log,
    )
    print(f"⏳ Phase4 定向修复 {entry_id} → {target.name}", flush=True)
    touch_heartbeat(work_dir, entry_id, stage="phase4_repair")
    _llm_turn(
        work_dir,
        entry_id,
        "repair",
        prompt,
        session_id=f"{session_id}-repair",
        timeout_sec=1200,
        artifact_paths={"markdown": repair_log},
        temperature=0.2,
    )
    raw = repair_log.read_text(encoding="utf-8") if repair_log.is_file() else ""
    new_body = extract_repaired_body(raw)
    if not new_body or len(new_body) < 80:
        return False, ["Phase4: 未解析到 <<<REPAIRED>>> 正文"]
    save_detail_to_enrich_file(target, entry_id, new_body)
    # 立即补回史料原文（save 已尽量保留；此处按召回再钉一次，防空稿）
    try:
        from lib.source_text import attach_source_original

        attach_source_original(target, recalled)
    except Exception as exc:  # noqa: BLE001
        print(f"   ⚠️ Phase4 补挂史料原文失败: {exc}", flush=True)
    meta = extract_repair_json(raw) or {}
    print(
        f"✅ Phase4 已写回成稿；修改条数≈{meta.get('修改条数', '?')} "
        f"改变时间线={meta.get('改变时间线')}",
        flush=True,
    )
    return True, []


def _run_phase5_recheck(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    target: Path,
    session_id: str,
    work_dir: Path,
    mother_body: str = "",
    out_dir: Optional[Path] = None,
    entry_name: str = "",
) -> Tuple[bool, List[str]]:
    """Phase5：修复后复检。建议入库须与程序终检口径一致，不得只凭 LLM 放行。"""
    from lib.phase3_qa import build_phase5_recheck_prompt, extract_recheck_json, verify_polish_draft_light

    after = _load_mother_text(target)
    before_path = work_dir / f"{target.stem}.before_repair.json"
    qa_md_path = work_dir / f"{target.stem}.qa.md"
    qa_json_path = work_dir / f"{target.stem}.qa.json"
    if before_path.is_file():
        before = json.loads(before_path.read_text(encoding="utf-8")).get("翻译详情") or ""
    else:
        before = after
    qa_md = qa_md_path.read_text(encoding="utf-8") if qa_md_path.is_file() else ""
    issue_digest = ""
    if qa_json_path.is_file():
        try:
            from lib.phase3_qa import build_accepted_issue_text

            qa_obj = json.loads(qa_json_path.read_text(encoding="utf-8"))
            issue_digest = build_accepted_issue_text(
                "", qa_obj, auto=True, include_qa_md=False
            )
        except (json.JSONDecodeError, TypeError):
            issue_digest = ""
    core, person = _core_source_person(recalled)
    recheck_path = work_dir / f"{target.stem}.recheck.md"
    prompt = build_phase5_recheck_prompt(
        entry_id=entry_id,
        core_source=core,
        person=person,
        before=before,
        after=after,
        qa_md=qa_md,
        output_file=recheck_path,
        issue_digest=issue_digest,
    )
    print(f"⏳ Phase5 最终复检 {entry_id} → {recheck_path.name}", flush=True)
    touch_heartbeat(work_dir, entry_id, stage="phase5_recheck")
    _llm_turn(
        work_dir,
        entry_id,
        "recheck",
        prompt,
        session_id=f"{session_id}-recheck",
        timeout_sec=900,
        artifact_paths={"markdown": recheck_path},
        temperature=0.1,
    )
    raw = recheck_path.read_text(encoding="utf-8") if recheck_path.is_file() else ""
    obj = extract_recheck_json(raw) or {}

    # 程序门禁：偏薄/近誊抄/基线回退等仍视为未过，不得标建议入库
    prog_errs: List[str] = []
    if mother_body.strip():
        from lib.source_text import build_source_original

        _ok_p, prog_errs = verify_polish_draft_light(
            entry_id=entry_id,
            detail=after,
            mother=mother_body,
            source_original=build_source_original(recalled),
            out_dir=out_dir,
            entry_name=entry_name or str(recalled.get("史略名称") or ""),
            plan=None,
            check_intro=True,
            check_epilogue=True,
        )
        if prog_errs:
            obj["建议入库"] = False
            obj["通过"] = False
            note = "程序终检未过：" + "；".join(prog_errs[:4])
            prev = str(obj.get("摘要") or "").strip()
            obj["摘要"] = f"{prev}｜{note}" if prev else note
            existing = [str(x) for x in (obj.get("未修复P0") or []) if x]
            for e in prog_errs[:6]:
                if e not in existing:
                    existing.append(e)
            obj["未修复P0"] = existing

    recheck_json = work_dir / f"{target.stem}.recheck.json"
    recheck_json.write_text(
        json.dumps({"史略ID": entry_id, **obj}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ok = bool(obj.get("通过") or obj.get("建议入库")) and not prog_errs
    # 仅新增 P0 才硬拦；仅 P1/文风问题改为软过（重质检、轻门禁）
    new_p0 = [x for x in (obj.get("新增P0") or []) if x]
    unfixed_p0 = [x for x in (obj.get("未修复P0") or []) if x]
    print(
        f"{'✅' if ok else '⚠️'} Phase5 复检 "
        f"{'建议入库' if obj.get('建议入库') else '不建议入库'}："
        f"{obj.get('摘要') or ''}",
        flush=True,
    )
    if prog_errs:
        return False, [f"Phase5: {e}" for e in prog_errs[:6]]
    if ok:
        return True, []
    if not new_p0 and not unfixed_p0:
        print("   （无未修复/新增 P0：软通过，详见 recheck 报告）", flush=True)
        return True, []
    errs = [f"Phase5: {x}" for x in (unfixed_p0 or new_p0)[:6]]
    return False, errs or ["Phase5: 复检未通过"]


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
    out_dir: Optional[Path] = None,
) -> Tuple[bool, List[str], float]:
    """Phase2：默认 polish；长卷分章 polish；enrich* 走旧补全路径。"""
    if not _phase2_use_legacy_enrich():
        if _phase2_should_chapter_polish(mother_body, mother_file):
            return _run_phase2_polish_chaptered(
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
                out_dir=out_dir,
            )
        return _run_phase2_polish(
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
            out_dir=out_dir,
            allow_chapter_fallback=True,
        )

    from lib.phase2_batch import (
        discover_mother_batches,
        phase2_batch_char_threshold,
        phase2_mode,
    )

    batch_files = discover_mother_batches(mother_file)
    if len(mother_body) > phase2_batch_char_threshold() and batch_files:
        if phase2_mode() == "legacy_batch":
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
            )
        return _run_phase2_enrich_chaptered(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_file=mother_file,
            target=target,
            session_id=session_id,
            work_dir=work_dir,
            entry_name=entry_name,
            t0=t0,
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
        from lib.recalled_window import (
            batch_window_guard_note,
            build_batch_recalled_payload,
        )

        full_checklist = plan_data.get("母本逐句清单") or []
        window_payload = build_batch_recalled_payload(
            recalled, full_checklist if isinstance(full_checklist, list) else []
        )
        e_prompt = (
            build_translate_enrich_prompt(
                entry_id,
                recalled,
                json.dumps(window_payload, ensure_ascii=False, indent=2),
                enrich_plan_json,
                mother_body,
                target,
            )
            + batch_window_guard_note(window_payload)
            + retry_note
            + _repair_feedback_suffix()
        )
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
            temperature=_phase2_temperature(),
        )
        if not target.is_file():
            e_errs = ["Phase2: LLM 未落盘最终译稿"]
            e_ok = False
            print(f"⚠️ Phase2 未通过: {e_errs[0]}", flush=True)
            continue
        if polish_enrich_file_full(target):
            print("   🔧 已自动修正模糊出处表述", flush=True)
        _rebuild_output_references(target, recalled, plan_data)
        touch_heartbeat(work_dir, entry_id, stage="verify_enrich")
        e_ok, e_errs = _verify_enrich_with_autofix(
            entry_id, recalled, target, plan_data, mother_text=mother_body
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
    """plan + (Phase1 母本 + Phase2 补全) 或 legacy 单次 draft。"""
    plan_ok, plan_errors = ensure_source_plan(
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
    t0 = time.time()
    touch_heartbeat(work_dir, entry_id, stage="start", detail=entry_name)

    if _two_phase_enabled():
        mother_file = mother_draft_path(entry_id, entry_name, work_dir)
        if from_phase == "phase3":
            if not mother_file.is_file() or not target.is_file():
                return False, [
                    "Phase3 需要已有母本与成稿；请先跑完 Phase1+Phase2"
                ], time.time() - t0
            mother_body = _load_mother_text(mother_file)
            ok3, errs3 = _run_phase3_qa(
                entry_id,
                recalled,
                plan_data=plan_data,
                mother_body=mother_body,
                target=target,
                session_id=session_id,
                work_dir=work_dir,
            )
            if not ok3:
                return False, errs3, time.time() - t0
            auto_repair = (os.environ.get("TRANSLATE_AUTO_REPAIR") or "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
            if auto_repair:
                from lib.phase3_qa import issues_need_repair

                qa_json_path = work_dir / f"{target.stem}.qa.json"
                qa_obj: Dict[str, Any] = {}
                if qa_json_path.is_file():
                    try:
                        qa_obj = json.loads(qa_json_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        qa_obj = {}
                if issues_need_repair(qa_obj):
                    ok4, errs4 = _run_phase4_repair(
                        entry_id,
                        recalled,
                        target=target,
                        session_id=session_id,
                        work_dir=work_dir,
                    )
                    if not ok4:
                        return False, errs4, time.time() - t0
                    ok5, errs5 = _run_phase5_recheck(
                        entry_id,
                        recalled,
                        target=target,
                        session_id=session_id,
                        work_dir=work_dir,
                        mother_body=_load_mother_text(mother_file) if mother_file.is_file() else "",
                        out_dir=out_dir,
                        entry_name=entry_name,
                    )
                    if not ok5:
                        return False, errs5, time.time() - t0
                else:
                    print("⏭️ 无待修问题，跳过 Phase4/5", flush=True)
            attach_source_original(
                target, recalled, translation_version=translation_version
            )
            return True, [], time.time() - t0

        if from_phase == "phase4":
            if not target.is_file():
                return False, ["Phase4 需要已有成稿；请先跑完 Phase2"], time.time() - t0
            ok4, errs4 = _run_phase4_repair(
                entry_id,
                recalled,
                target=target,
                session_id=session_id,
                work_dir=work_dir,
            )
            elapsed = time.time() - t0
            if not ok4:
                return False, errs4, elapsed
            # 修复后默认紧跟复检
            ok5, errs5 = _run_phase5_recheck(
                entry_id,
                recalled,
                target=target,
                session_id=session_id,
                work_dir=work_dir,
                        mother_body=_load_mother_text(mother_file) if mother_file.is_file() else "",
                        out_dir=out_dir,
                        entry_name=entry_name,
            )
            if ok5:
                attach_source_original(
                    target, recalled, translation_version=translation_version
                )
            return ok5, errs5, time.time() - t0

        if from_phase == "phase5":
            if not target.is_file():
                return False, ["Phase5 需要已有成稿；请先跑完 Phase4"], time.time() - t0
            ok5, errs5 = _run_phase5_recheck(
                entry_id,
                recalled,
                target=target,
                session_id=session_id,
                work_dir=work_dir,
                        mother_body=_load_mother_text(mother_file) if mother_file.is_file() else "",
                        out_dir=out_dir,
                        entry_name=entry_name,
            )
            elapsed = time.time() - t0
            if ok5:
                attach_source_original(
                    target, recalled, translation_version=translation_version
                )
            return ok5, errs5, elapsed

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
        # mother.json 常为空壳；整篇润色优先用分批母本拼接
        from lib.phase2_batch import (
            concatenate_mother_batch_texts,
            discover_mother_batches,
        )

        batches = discover_mother_batches(mother_file)
        if batches:
            concat = concatenate_mother_batch_texts(batches)
            if len(concat) > len(mother_body):
                mother_body = concat

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
            out_dir=out_dir,
        )
        if not ok2:
            return ok2, errs2, elapsed

        ok3, errs3 = _run_phase3_qa(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_body=mother_body,
            target=target,
            session_id=session_id,
            work_dir=work_dir,
        )
        if not ok3:
            return False, errs3, time.time() - t0

        auto_repair = (os.environ.get("TRANSLATE_AUTO_REPAIR") or "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        if auto_repair:
            from lib.phase3_qa import issues_need_repair

            qa_json_path = work_dir / f"{target.stem}.qa.json"
            qa_obj: Dict[str, Any] = {}
            if qa_json_path.is_file():
                try:
                    qa_obj = json.loads(qa_json_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    qa_obj = {}
            if issues_need_repair(qa_obj):
                ok4, errs4 = _run_phase4_repair(
                    entry_id,
                    recalled,
                    target=target,
                    session_id=session_id,
                    work_dir=work_dir,
                )
                if not ok4:
                    return False, errs4, time.time() - t0
                ok5, errs5 = _run_phase5_recheck(
                    entry_id,
                    recalled,
                    target=target,
                    session_id=session_id,
                    work_dir=work_dir,
                    mother_body=_load_mother_text(mother_file) if mother_file.is_file() else "",
                    out_dir=out_dir,
                    entry_name=entry_name,
                )
                if not ok5:
                    return False, errs5, time.time() - t0
            else:
                print("⏭️ 无待修问题，跳过 Phase4/5", flush=True)

        attach_source_original(target, recalled, translation_version=translation_version)
        return True, [], time.time() - t0
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

    if not from_phase and _should_skip(entry_id, recalled, job, plan_file, out_dir=out_dir):
        print(f"⏭️ 跳过 {entry_id}（产出已有效 fp={fp}）")
        return 0
    if from_phase:
        print(f"🔁 续跑 --from-phase {from_phase}（跳过「产出已有效」短路）", flush=True)

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
    v_ok, v_errs = verify_output(
        entry_id, recalled, out_dir, plan=plan_data if plan_data else None
    )
    if not v_ok:
        # 终检不过则不得保留 Phase5「建议入库」
        recheck_json = work_dir / f"{target.stem}.recheck.json"
        if recheck_json.is_file():
            try:
                robj = json.loads(recheck_json.read_text(encoding="utf-8"))
                if robj.get("建议入库") or robj.get("通过"):
                    robj["建议入库"] = False
                    robj["通过"] = False
                    note = "终检未过，撤销建议入库：" + "；".join(v_errs[:3])
                    prev = str(robj.get("摘要") or "").strip()
                    robj["摘要"] = f"{prev}｜{note}" if prev else note
                    recheck_json.write_text(
                        json.dumps(robj, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    print("   ⚠️ Phase5 建议入库已与终检对齐（撤销）", flush=True)
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        fail = int(job.get("fail_count") or 0) + 1
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
    mode = "chunked" if _use_chunked_pipeline(recalled) else "single"
    db.update_job(
        entry_id,
        status="done",
        source_fingerprint=fp,
        output_word_count=wc,
        detail=f"ok {mode} {elapsed:.0f}s",
    )
    print(f"✅ {entry_id} 完成 {wc} 字 ({mode}, {elapsed:.0f}s) → {out_dir.name}/")
    if not trans_version:
        try:
            agg_path, agg_count = rebuild_aggregate(out_dir)
            print(f"📦 汇总已更新 → {agg_path}（{agg_count} 条）")
        except OSError as exc:
            print(f"⚠️ 汇总更新失败（单条产出已保留）: {exc}")

    if auto_sync_enabled():
        from lib.remote_sync import sync_output_entry

        s_ok, s_msg = sync_output_entry(entry_id, out_dir, entry_name)
        if s_ok:
            print(f"☁️ 已同步线上 DB: {entry_id} — {s_msg}")
        else:
            print(f"⚠️ 线上同步失败（本地产出已保留）: {s_msg}")
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


def verify_cmd(entry_id: str, *, index_path: Path | None = None) -> int:
    recalled = recall_entry(entry_id, index_path=index_path)
    work_dir = _ensure_work_dir()
    p = plan_path(
        entry_id,
        str(recalled.get("史略名称") or ""),
        work_dir,
    )
    plan_ok, plan_data, plan_errs = load_plan(p)
    ok, errs = verify_output(
        entry_id,
        recalled,
        _ensure_output_dir(),
        plan=plan_data if plan_ok else None,
    )
    if not plan_ok:
        errs = plan_errs + errs
        ok = False
    if ok:
        print(f"✅ verify 通过: {entry_id}")
        return 0
    print(f"❌ verify 失败: {entry_id}")
    for e in errs:
        print(f"   · {e}")
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

    out_dir = _ensure_output_dir(index_path=index_path)

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
    print(f"   产出: {paths()['translate_output']}")

    idx_path = Path(idx) if idx else default_index_path()
    if idx_path.is_file():
        index = load_global_index(idx_path)
        entries = index.get("entries") or []
        out_dir = Path(paths()["translate_output"])
        detail_agg = paths()["dynasty_knowledge_detail_aggregate"]
        progress = compute_progress(
            entries,
            translated_ids=load_translated_ids(out_dir),
            dynasty_detail_ids=load_dynasty_detail_ids(detail_agg),
        )
        print()
        print(format_progress_report(progress))
    return 0
