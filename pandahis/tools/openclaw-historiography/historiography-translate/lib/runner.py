"""翻译任务编排：bootstrap / recall / run / verify。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib import db
from lib.config import default_index_path, paths
from lib.plan_postprocess import plan_for_enrich_phase, plan_for_mother_phase
from lib.prose_sanitize import polish_enrich_file, polish_mother_file, sanitize_mother_detail
from lib.remote_sync import auto_sync_enabled
from lib.stall_watch import (
    diagnose_stall,
    is_stalled,
    read_heartbeat,
    stall_threshold_sec,
    touch_heartbeat,
)
from lib.fingerprint import recalled_summary, source_fingerprint
from lib.index_filter import filter_pending_jobs
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
    load_output,
    output_path,
    verify_enrich_draft,
    verify_mother_draft,
    verify_output,
)
from lib.work_artifacts import (
    load_normalized_plan,
    load_plan,
    mother_draft_path,
    plan_path,
    save_plan,
    verify_plan,
)


def _ensure_output_dir() -> Path:
    out = paths()["translate_output"]
    out.mkdir(parents=True, exist_ok=True)
    return out


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
    for e in entries:
        eid = e.get("史略ID")
        if not eid:
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
    print(f"✅ bootstrap: {created} 条任务 ← {idx_path}")
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


def _should_skip(
    entry_id: str,
    recalled: Dict[str, Any],
    job: Optional[Dict[str, Any]],
    plan_file: Path,
) -> bool:
    fp = source_fingerprint(recalled)
    out_dir = _ensure_output_dir()
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


def _phase2_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE2_MAX_RETRIES", "2")))


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
    for attempt in range(_phase1_max_retries() + 1):
        retry_note = ""
        if attempt > 0 and m_errs:
            retry_note = (
                "\n\n--- 上轮 Phase1 质检失败，须逐项修正 ---\n"
                + "\n".join(f"- {e}" for e in m_errs[:12])
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
        )
        title = batch_label or f"Phase1 母本顺译 {entry_id} → {mother_file.name}"
        print(
            title + (f"（重试 {attempt}/{_phase1_max_retries()}）" if attempt else ""),
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
        )
        if not mother_file.is_file():
            return False, ["Phase1: LLM 未落盘母本顺译"]
        if polish_mother_file(mother_file):
            print("   🔧 已修正 Phase1 误用书名号", flush=True)
        touch_heartbeat(work_dir, entry_id, stage="verify_mother")
        m_ok, m_errs = verify_mother_draft(
            entry_id,
            recalled,
            mother_file,
            plan=verify_plan_data,
            batch_mode=bool(batch_label),
        )
        if m_ok:
            return True, []
        print(f"⚠️ Phase1 未通过: {m_errs[0] if m_errs else '?'}", flush=True)
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
) -> None:
    touch_heartbeat(work_dir, entry_id, stage=f"llm_{stage}", detail=session_id)
    run_agent_turn(
        prompt,
        session_id=session_id,
        timeout_sec=timeout_sec,
        artifact_paths=artifact_paths,
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


def _run_phase2_enrich(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_body: str,
    target: Path,
    session_id: str,
    work_dir: Path,
    entry_name: str,
    t0: float,
) -> Tuple[bool, List[str], float]:
    """Phase2 补全 + 前置质检 + 重试。"""
    enrich_plan_json = _plan_json_for_enrich(plan_data)
    e_errs: List[str] = []
    e_ok = False
    for attempt in range(_phase2_max_retries() + 1):
        retry_note = ""
        if attempt > 0 and e_errs:
            retry_note = (
                "\n\n--- 上轮 Phase2 质检失败，须修正 ---\n"
                + "\n".join(f"- {e}" for e in e_errs[:12])
            )
        e_prompt = build_translate_enrich_prompt(
            entry_id,
            recalled,
            recalled_summary(recalled),
            enrich_plan_json,
            mother_body,
            target,
        ) + retry_note
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
            return False, ["Phase2: LLM 未落盘最终译稿"], time.time() - t0
        if polish_enrich_file(target):
            print("   🔧 已自动修正模糊出处表述", flush=True)
        touch_heartbeat(work_dir, entry_id, stage="verify_enrich")
        e_ok, e_errs = verify_enrich_draft(
            entry_id, recalled, target, plan=plan_data
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
    t0 = time.time()
    touch_heartbeat(work_dir, entry_id, stage="start", detail=entry_name)

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
            target=target,
            session_id=session_id,
            work_dir=work_dir,
            entry_name=entry_name,
            t0=t0,
        )
        if not ok2:
            return ok2, errs2, elapsed
        attach_source_original(target, recalled)
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

    attach_source_original(target, recalled)
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
    out_dir = _ensure_output_dir()
    work_dir = _ensure_work_dir()
    entry_name = str(recalled.get("史略名称") or job.get("entry_name") or "")
    target = output_path(entry_id, out_dir, entry_name)
    plan_file = plan_path(entry_id, entry_name, work_dir)

    if _should_skip(entry_id, recalled, job, plan_file):
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
            )
    except RuntimeError as exc:
        fail = int(job.get("fail_count") or 0) + 1
        db.update_job(entry_id, status="failed", fail_count=fail, detail=str(exc)[-500:])
        print(f"❌ LLM 失败: {exc}")
        return 1

    if not ok:
        fail = int(job.get("fail_count") or 0) + 1
        db.update_job(
            entry_id,
            status="failed",
            fail_count=fail,
            detail="; ".join(errs),
        )
        print(f"❌ 翻译未通过:\n   " + "\n   ".join(errs))
        return 1

    _, plan_data, _ = load_normalized_plan(plan_file, recalled)
    v_ok, v_errs = verify_output(
        entry_id, recalled, out_dir, plan=plan_data if plan_data else None
    )
    if not v_ok:
        fail = int(job.get("fail_count") or 0) + 1
        db.update_job(
            entry_id,
            status="failed",
            fail_count=fail,
            detail="; ".join(v_errs),
        )
        print(f"❌ verify 未通过:\n   " + "\n   ".join(v_errs))
        return 1

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
    print(f"✅ {entry_id} 完成 {wc} 字 ({mode}, {elapsed:.0f}s)")
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
    from lib.remote_sync import sync_all_from_aggregate, sync_output_entry
    from lib.aggregate import aggregate_path

    out_dir = _ensure_output_dir()

    if all_from_aggregate:
        agg = aggregate_path(out_dir)
        ok, msg = sync_all_from_aggregate(agg, dry_run=dry_run, prune_orphans=True)
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
    print(f"\n📋 史略翻译")
    print(f"   任务: done {done}/{total}  pending {pending}  failed {failed}")
    idx = db.get_meta("index_path")
    if idx:
        print(f"   索引: {idx}")
    print(f"   产出: {paths()['translate_output']}")
    return 0
