"""著作级编排：bootstrap → gold → 逐卷四步（标注→格式→审计→补全）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from lib.config import ANNOTATE_DIR, PIPELINE_DIR, get_work_config, paths

sys.path.insert(0, str(PIPELINE_DIR))
from hist_gates import (  # noqa: E402
    PIPELINE_STEPS,
    clear_active_job,
    repair_mode,
    write_active_job,
)
from lib.adapters.openclaw import (
    audit_markdown_path,
    build_protagonist_prompt,
    build_step_prompt,
    expected_skeleton_path,
    make_session_id,
    run_agent_turn,
)
from llm.config import PROVIDER_DEEPSEEK, get_provider_name  # noqa: E402
from lib import db, events
from lib import gates
from lib import audit_repair
from lib import confirmations
from lib import evidence_repair
from lib import hezhuan_repair
from lib import decisions
from lib import blocks_workflow
from lib import protagonist_workflow
from lib import artifact_invalidate
from lib import failure_classifier
from lib import repair_registry
from lib import step4_spindle_llm
from lib.paragraph_index import bootstrap_indexes, list_volume_files

sys.path.insert(0, str(ANNOTATE_DIR))
from knowledge_provenance import stamp_provenance  # noqa: E402

STEPS = list(PIPELINE_STEPS)
LLM_STEPS = {"1", "4"}


def _run_lock_path(work: str) -> Path:
    lock_dir = paths()["locks"]
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"run-{work}.lock"


def _acquire_run_lock(work: str) -> None:
    """同一著作禁止并行 run-work（避免多卷同时 LLM 标注）。"""
    p = _run_lock_path(work)
    if p.exists():
        try:
            pid = int(p.read_text(encoding="utf-8").strip().split()[0])
            os.kill(pid, 0)
            raise RuntimeError(
                f"⛔ 已有 run-work 在跑（pid {pid}）。"
                f"请待其结束，勿多开进程同时标注。"
            )
        except ProcessLookupError:
            p.unlink(missing_ok=True)
        except ValueError:
            p.unlink(missing_ok=True)
    p.write_text(f"{os.getpid()}\n", encoding="utf-8")


def _release_run_lock(work: str) -> None:
    p = _run_lock_path(work)
    if not p.exists():
        return
    try:
        if int(p.read_text(encoding="utf-8").strip().split()[0]) == os.getpid():
            p.unlink()
    except (ValueError, OSError):
        pass


def _pipeline_init_scan(work: str) -> None:
    subprocess.run(
        [
            sys.executable,
            str(PIPELINE_DIR / "run_volume_pipeline.py"),
            "init",
            "--work",
            work,
            "--scan",
        ],
        check=False,
    )


def bootstrap(work: str) -> List[str]:
    cfg = get_work_config(work)
    events.log("bootstrap_start", work=work)
    vols = bootstrap_indexes(work)
    db.init_schema()
    db.upsert_work(work, cfg.get("title", work), status="bootstrapping", volume_count=len(vols))
    db.ensure_jobs(work, vols, STEPS)
    db.retire_reference_step_jobs(work)
    _pipeline_init_scan(work)
    gold = cfg.get("gold_volumes", [])
    if gold and not db.get_work(work).get("gold_approved"):
        db.set_work_status(work, "gold_review")
    else:
        db.set_work_status(work, "running")
    events.log("bootstrap_done", work=work, volumes=len(vols))
    return vols


def _verify_feedback_from_job(job: Optional[dict]) -> str:
    """上次 verify 失败原因，供 Step3/4 重试 prompt 注入。"""
    if not job:
        return ""
    detail = job.get("detail") or ""
    if detail.startswith("verify_feedback:"):
        return detail[len("verify_feedback:") :].strip()
    return ""


def _apply_failure_recovery(
    work: str,
    vol: str,
    step: str,
    err_str: str,
    fail_count: int,
) -> tuple[Optional[str], bool]:
    """失败时：分类 → 脚本修复 → 失效缓存。返回 (retry_detail, repaired_bypass)."""
    plan = failure_classifier.classify_failure(
        step, err_str, work=work, vol=vol, fail_count=fail_count
    )

    if plan.try_volume_repair:
        repaired, repair_msg = repair_registry.try_volume_repair(work, vol)
        if repaired:
            print(f"🔧 卷级返工：{repair_msg}", flush=True)
            events.log(
                "volume_repair_ok",
                work=work,
                vol=vol,
                step=step,
                root_cause=plan.root_cause,
            )
            return "repair_bypass:volume_repair", True

    if plan.try_blocks_autofix and work.startswith("01史记"):
        from lib import shiji_autofix

        repaired, repair_msg = shiji_autofix.repair_step1_blocks(work, vol)
        if repaired:
            print(f"🔧 Step1 blocks 脚本修复：{repair_msg}", flush=True)
            return "repair_bypass:blocks_autofix", True

    if work.startswith("02汉书") and any(
        k in err_str
        for k in ("卷首标题", "篇内小标题", "不得设 owners", "须 exclude_reason=")
    ):
        from lib import hanshu_autofix

        repaired, repair_msg = hanshu_autofix.repair_and_requeue_verify(work, vol)
        if repaired:
            print(f"🔧 汉书头段脚本修复：{repair_msg}", flush=True)
            events.log("hanshu_header_autofix", work=work, vol=vol, detail=repair_msg)
            return "repair_bypass:verify_only", True

    if plan.invalidate:
        for ln in artifact_invalidate.invalidate_for_failure_plan(work, vol, plan):
            print(f"🔧 {ln}", flush=True)

    feedback = failure_classifier.format_verify_feedback(plan, err_str)
    return f"verify_feedback:{feedback[:2800]}", False


def _rollback_to_step1(
    work: str,
    vol: str,
    from_step: str,
    job_id: int,
    err_str: str,
    fail_count: int,
    *,
    through_step: str,
    event_name: str,
    redo_step1a: bool = False,
) -> None:
    """Step2/4 硬检未过：清 blocks+skeleton（主轴类再清 protagonists），打回 Step1。"""
    plan = failure_classifier.classify_failure(
        from_step, err_str, work=work, vol=vol, fail_count=fail_count
    )
    for ln in artifact_invalidate.invalidate_for_step2_rollback(
        work,
        vol,
        err_str,
        redo_step1a=redo_step1a or plan.redo_step1a,
    ):
        print(f"🔧 {ln}", flush=True)
    db.reset_volume_steps(work, vol, through_step=through_step)
    j1 = db.get_job(work, vol, "1")
    if j1:
        db.update_job(
            j1["id"],
            detail=(
                "verify_feedback:"
                + failure_classifier.format_verify_feedback(plan, err_str)[:2800]
            ),
        )
    db.update_job(
        job_id,
        status="pending",
        finished_at=None,
        started_at=None,
        session_id=None,
        fail_count=fail_count,
        detail=None,
    )
    events.log(
        event_name,
        work=work,
        vol=vol,
        from_step=from_step,
        attempt=fail_count,
        root_cause=plan.root_cause,
    )
    print(
        f"↩ 卷{vol} Step{from_step} 未过 ({fail_count})，"
        f"打回 Step1 重标 blocks（{plan.root_cause}）",
        flush=True,
    )
    for ln in err_str.splitlines():
        s = ln.strip()
        if s.startswith("❌") or "卷首标题" in s or "合传" in s or "缺少" in s:
            print(f"   {s}", flush=True)


def _handle_step2_verify_failure(
    work: str,
    vol: str,
    job_id: int,
    err_str: str,
    fail_count: int,
    max_retries: int,
) -> tuple[Optional[str], bool]:
    """Step2 失败时优先尝试 verify-only 修复，避免机械错误反复打回 Step1。"""
    ref_only = gates.is_step2_emperor_reference_only_error(err_str)
    if ref_only:
        retry_detail = f"verify_feedback:{err_str[:1800]}"
        print(
            f"⚠️ 卷{vol} Step2 帝王表/君王名问题 ({fail_count}/{max_retries})，"
            f"不打回 Step1；请补 reference/帝王.json 或帝王待补录.json 后重试",
            flush=True,
        )
        for ln in err_str.splitlines():
            s = ln.strip()
            if "不在帝王" in s or "应改为帝王表" in s or s.startswith("❌"):
                print(f"   {s}", flush=True)
        return retry_detail, False

    retry_detail, bypass = _apply_failure_recovery(work, vol, "2", err_str, fail_count)
    if bypass:
        return retry_detail, False

    max_s1 = gates.max_retries_per_step(work, "1")
    if fail_count < max_s1 and "未找到 skeleton" not in err_str:
        _rollback_to_step1(
            work,
            vol,
            "2",
            job_id,
            err_str,
            fail_count,
            through_step="2",
            event_name="step2_rollback_step1",
        )
        return None, True
    return retry_detail, False


def _ensure_protagonist_manifest(
    work: str,
    vol: str,
    job_id: int,
    job: Optional[dict],
    idx: dict,
) -> None:
    """Step1a：LLM 据著作+卷名理解主轴；脚本 identity_gate 为第二道校验。"""
    if not protagonist_workflow.use_protagonist_phase(work):
        return
    feedback = _verify_feedback_from_job(job)
    pp = protagonist_workflow.protagonists_path(work, vol)
    if feedback and protagonist_workflow.protagonist_retry_needed(feedback):
        if pp.exists():
            pp.unlink()
            print(
                f"↩ 卷{vol} 主轴相关失败，已删除 protagonists.json，强制重跑 Step1a",
                flush=True,
            )
        blocks_workflow.blocks_path(work, vol).unlink(missing_ok=True)
        sk = gates.skeleton_path(work, vol)
        if sk is not None:
            sk.unlink(missing_ok=True)
    # 先尝试对已有 protagonists 做别名归一；归一后能过就不必重跑 LLM
    if pp.exists():
        norm_logs = protagonist_workflow.normalize_protagonists_file(work, vol)
        if norm_logs:
            print(f"🔧 Step1a 主轴别名归一：{'; '.join(norm_logs)}", flush=True)
        ok, msg = protagonist_workflow.protagonists_valid(work, vol, idx)
        if ok:
            print(f"✅ Step1a 主轴理解已就绪：{msg}", flush=True)
            return
    cfg = get_work_config(work)
    agent = cfg.get("openclaw_agent", "hist-worker")
    session_id = make_session_id(work, vol, "1a", job_id)
    prompt = build_protagonist_prompt(work, vol, idx)
    if protagonist_workflow.protagonist_retry_needed(feedback):
        prompt += (
            "\n\n---\n"
            "【上轮主轴理解/双重校验未过 — 须修正 protagonists 后重跑 Step1a】\n"
            f"{feedback}\n\n"
            "重新据卷名+常识判断主轴；君王须查帝王.json 标准名。"
        )
    t0 = time.time()
    events.log(
        "llm_start",
        work=work,
        vol=vol,
        step="1a",
        session_id=session_id,
    )
    print(
        f"⏳ LLM Step1a 主轴理解 卷{vol} → agent={agent} session={session_id}",
        flush=True,
    )
    result = run_agent_turn(
        prompt,
        agent_id=agent,
        session_id=session_id,
        timeout_sec=300,
        artifact_paths={"protagonists": pp},
    )
    elapsed = time.time() - t0
    events.log(
        "llm_end",
        work=work,
        vol=vol,
        step="1a",
        elapsed_sec=round(elapsed, 1),
    )
    if not pp.exists():
        snippet = str(result.get("result") or result.get("raw", ""))[:400]
        raise RuntimeError(
            "Step1a 后未落盘 protagonists JSON。"
            f" 回复摘要: {snippet}"
        )
    ok, msg = protagonist_workflow.protagonists_valid(work, vol, idx)
    if not ok:
        raise RuntimeError(f"Step1a 主轴理解未过 identity_gate:\n{msg}")
    print(f"✅ Step1a 主轴理解：{msg}", flush=True)


def _stamp_llm_provenance(work: str, vol: str, step: str, session_id: Optional[str] = None) -> None:
    sk = gates.skeleton_path(work, vol)
    if not sk or not sk.is_file():
        return
    stamp_provenance(sk, step, source="llm", session_id=session_id)


def _stamp_skip_provenance(work: str, vol: str, reason: str) -> None:
    sk = gates.skeleton_path(work, vol)
    if not sk or not sk.is_file():
        return
    stamp_provenance(sk, "1", source="skip_non_narrative", reason=reason)
    stamp_provenance(sk, "4", source="skip_non_narrative", reason="无叙事条目")


def _run_llm_step(
    work: str,
    vol: str,
    step: str,
    job_id: int,
    job: Optional[dict] = None,
    *,
    use_blocks: bool = False,
) -> None:
    cfg = get_work_config(work)
    agent = cfg.get("openclaw_agent", "hist-worker")
    idx = gates.load_paragraph_index(work, vol)
    if step == "1":
        _ensure_protagonist_manifest(work, vol, job_id, job, idx)
    session_id = make_session_id(work, vol, step, job_id)
    prompt = build_step_prompt(work, vol, step, idx, use_blocks=use_blocks)
    feedback = _verify_feedback_from_job(job)
    if feedback and step == "1":
        if "原文挑战" in feedback or "原文字句" in feedback:
            prompt += (
                "\n\n---\n"
                "【上轮 Step1 原文挑战未通过 — 必须修正 skeleton 后重跑】\n"
                f"{feedback}\n\n"
                "注意：篇内小标题行（如「西域传第六十六上」）须标 exclude_reason=篇内小标题，"
                "须为四类人物之一；每条 entry 开篇段的「原文字句」须从段落索引逐字摘录段首"
                "（≥12字），与 segment_attribution 一致并落盘。"
            )
        elif (
            "blocks" in feedback.lower()
            or "total_paragraphs" in feedback
            or "未覆盖" in feedback
            or "expand" in feedback.lower()
        ):
            prompt += (
                "\n\n---\n"
                "【上轮 Step1 blocks 未过 — 须修正 blocks 草稿】\n"
                f"{feedback}\n\n"
                f"本卷共 {idx['total']} 段（段落索引 SSOT）；"
                "`total_paragraphs` 必须等于该数；"
                "blocks + excludes 须覆盖 P1～P{idx['total']} 每一段，不得遗漏。"
            )
        elif (
            "人物身份门" in feedback
            or "exclude 内容门" in feedback
            or "南汉高祖" in feedback
            or "孝文皇帝" in feedback
            or "双重校验" in feedback
            or "主轴理解" in feedback
        ):
            prompt += (
                "\n\n---\n"
                "【上轮 Step1 人物身份/双重校验/exclude 未过 — 须修正 blocks】\n"
                f"{feedback}\n\n"
                "史记拆分 txt 无卷首标题行；P1 须读段落索引正文再标。"
                "本纪开篇「X者，Y之子也」归主轴，非世系链。"
                "blocks/entries 的 name+category 须与 protagonists.json 完全一致。"
            )
        elif (
            "blocks" in feedback.lower()
            or "total_paragraphs" in feedback
            or "未覆盖" in feedback
            or "expand" in feedback.lower()
        ):
            prompt += (
                "\n\n---\n"
                "【上轮 Step1 blocks 未过 — 须修正 blocks 草稿】\n"
                f"{feedback}\n\n"
                f"本卷共 {idx['total']} 段（段落索引 SSOT）；"
                "`total_paragraphs` 必须等于该数；"
                f"blocks + excludes 须覆盖 P1～P{idx['total']} 每一段，不得遗漏。"
            )
        else:
            prompt += (
                "\n\n---\n"
                "【上轮 Step2 skeleton 硬检未通过 — 必须修正 skeleton 后重跑 Step1】\n"
                f"{feedback}\n\n"
                "注意：合传卷名中每位核心人物须有独立 **士臣** 或 **君王** 或 **庶众** 或 **宗戚** 条目；"
                "禁止把卷名相邻简称作史略名（如张陈/王周、张周/赵任/申屠、郦陆/朱刘/叔孙、万石/卫直/周张）；"
                "四姓合传按姓氏各建一条（张陈王周→张良、陈平等）；"
                "五段合传用全名或通行称呼（如张苍、郦食其、万石君石奋）；"
                "禁止添加「合传解析器兼容条目」类假士臣；"
                "二人合传则史略名称=全名（如陈胜、项籍）。"
                "segment_attribution 与 entries 须一致并落盘。"
            )
    elif feedback and step == "3":
        prompt += (
            "\n\n---\n"
            "【上轮 Step3 verify 未通过 — 必须按下列项修正审计 MD 后重跑】\n"
            f"{feedback}\n\n"
            "注意：段落覆盖清单须 **每段一行**（P1…P{total}），禁止「省略中间行」；"
            "六条声明块关键词须齐全；结论须含「✅ 修正后通过」。"
        )
    timeout = 900 if step == "1" else 600
    t0 = time.time()
    db.update_job(job_id, status="running", session_id=session_id, started_at=db.utc_now())
    events.log("llm_start", work=work, vol=vol, step=step, session_id=session_id)
    print(
        f"⏳ LLM Step{step} 卷{vol} → agent={agent} session={session_id}\n"
        f"   预计 5–15 分钟无输出属正常；勿用 agents_list 判断 worker；勿 kill 进程",
        flush=True,
    )
    artifact_paths = None
    if step == "1":
        if use_blocks:
            artifact_paths = {"blocks": blocks_workflow.blocks_path(work, vol)}
        else:
            artifact_paths = {"skeleton": expected_skeleton_path(work, vol, idx)}
    elif step == "3":
        artifact_paths = {"markdown_append": audit_markdown_path(work)}
    result = run_agent_turn(
        prompt,
        agent_id=agent,
        session_id=session_id,
        timeout_sec=timeout,
        artifact_paths=artifact_paths,
    )
    elapsed = time.time() - t0
    events.log("llm_end", work=work, vol=vol, step=step, elapsed_sec=round(elapsed, 1))
    if step in ("1", "3"):
        hard_floor = gates.llm_step_hard_floor(work)
        if elapsed < hard_floor:
            written = result.get("written_artifacts") or []
            if written:
                events.log(
                    "duration_fast_ok",
                    work=work,
                    vol=vol,
                    step=step,
                    elapsed_sec=round(elapsed, 1),
                    hard_floor_sec=hard_floor,
                    artifacts=written,
                )
                print(
                    f"⚠️ Step{step} 用时 {elapsed:.1f}s < {hard_floor}s，"
                    f"但已落盘 {len(written)} 个产物，继续 verify",
                    flush=True,
                )
            else:
                events.log(
                    "duration_hard_fail",
                    work=work,
                    vol=vol,
                    step=step,
                    elapsed_sec=round(elapsed, 1),
                    hard_floor_sec=hard_floor,
                )
                raise decisions.DurationHardFail(
                    step,
                    elapsed,
                    hard_floor,
                    detail=str(result.get("result") or result.get("raw", ""))[:1500],
                )
        min_sec = (
            gates.min_step1_duration(work, vol)
            if step == "1"
            else gates.min_step3_duration(work, vol)
        )
        if min_sec > 0 and elapsed < min_sec:
            events.log(
                "duration_anomaly",
                work=work,
                vol=vol,
                step=step,
                elapsed_sec=round(elapsed, 1),
                min_sec=min_sec,
                severity="warn",
            )
            print(
                f"⚠️ Step{step} 用时 {elapsed:.0f}s < 建议 {min_sec}s"
                f"（仅告警；≥{hard_floor}s 不因用时失败，主门控为 verify）",
                flush=True,
            )
    detail = str(result.get("result") or result.get("raw", ""))[:1500]
    if step == "1":
        if use_blocks:
            bp = blocks_workflow.blocks_path(work, vol)
            if not bp.exists():
                snippet = str(result.get("result") or result.get("raw", ""))[:400]
                raise RuntimeError(
                    "Step1 blocks 后 worker 未落盘 blocks JSON。"
                    f" 回复摘要: {snippet}"
                )
            norm_logs = blocks_workflow.normalize_blocks_file(bp)
            if norm_logs:
                print(f"🔧 blocks 规范化: {'; '.join(norm_logs)}", flush=True)
            if protagonist_workflow.use_protagonist_phase(work):
                ok_dual, dual_msg = protagonist_workflow.validate_dual(work, vol, idx)
                if not ok_dual:
                    raise RuntimeError(f"Step1 双重校验失败:\n{dual_msg}")
                print(f"✅ Step1 双重校验：{dual_msg}", flush=True)
            sk = blocks_workflow.expand_blocks_to_skeleton(work, vol, idx, blocks_file=bp)
            print(f"🔧 blocks → skeleton: {sk.name}", flush=True)
        else:
            sk = gates.skeleton_path(work, vol)
            if not sk:
                snippet = str(result.get("result") or result.get("raw", ""))[:400]
                raise RuntimeError(
                    "Step1 后 worker 未落盘 skeleton。"
                    f" 请确认 hist-worker 已写 JSON 到史料标注目录，勿仅回复「已完成」。"
                    f" 回复摘要: {snippet}"
                )
            if protagonist_workflow.use_protagonist_phase(work):
                sk_data = json.loads(sk.read_text(encoding="utf-8"))
                ok_dual, dual_msg = protagonist_workflow.validate_dual_skeleton(
                    work, vol, sk_data, index=idx
                )
                if not ok_dual:
                    raise RuntimeError(f"Step1 双重校验失败:\n{dual_msg}")
                print(f"✅ Step1 双重校验：{dual_msg}", flush=True)
    if step == "1":
        _stamp_llm_provenance(work, vol, step, session_id=session_id)
    db.update_job(job_id, detail=detail)


def _step4_correction_prompt(
    job: Optional[dict],
    *,
    year_issues: list,
    missing_report: str,
) -> str:
    """Step4 LLM 须修正项（verify 反馈 + 年代硬检 + 缺字段）。"""
    parts: list[str] = []
    feedback = _verify_feedback_from_job(job)
    if feedback:
        parts.append("【上轮 check_format / verify 未通过 — 必须逐项修正】\n" + feedback)
    if year_issues:
        parts.append(
            "【年代质量硬检 — 禁止批量占位，须逐条考订史略开始年/史略结束年】\n"
            + "\n".join(f"- {x}" for x in year_issues)
        )
    if missing_report and missing_report.strip():
        parts.append(missing_report.strip())
    body = "\n\n".join(parts)
    if not body:
        return ""
    if get_provider_name() == PROVIDER_DEEPSEEK:
        fix_hint = (
            "修正要求：在**完整 skeleton JSON** 上按史略ID 逐条修改正式字段；"
            "每条人物的年份须据原文字句与关联君主在位期独立考订，"
            "禁止多条共用同一 -188～-180 式占位区间；"
            "修改后在回复中输出**单个** ```json 代码块（整份 skeleton）。"
            "禁止删除 _auto_filled / _needs_llm。"
        )
    else:
        fix_hint = (
            "修正要求：打开 skeleton JSON，按史略ID 逐条修改正式字段；"
            "每条人物的年份须据原文字句与关联君主在位期独立考订，"
            "禁止多条共用同一 -188～-180 式占位区间；修改后落盘。"
            "禁止删除 _auto_filled / _needs_llm。"
        )
    return body + "\n\n---\n" + fix_hint


def _run_step4(work: str, vol: str, job_id: int, job: Optional[dict] = None) -> None:
    """Step4：脚本 prepare → LLM 补缺 → 脚本 verify/finalize → check_format final。"""
    sk = gates.skeleton_path(work, vol)
    if not sk:
        raise RuntimeError("Step4 前未找到 skeleton")

    ok, msg = gates.step4_prepare(sk)
    if not ok:
        raise RuntimeError(f"step4 prepare 失败:\n{msg}")
    print("✅ Step4 prepare（fill_fields + merge-auto）", flush=True)

    if work.startswith("02汉书"):
        n_clr, clr_logs = gates.step4_hanshu_clear_placeholder_years(sk)
        if n_clr:
            for ln in clr_logs[:8]:
                print(f"   📌 清空占位年生卒: {ln}", flush=True)

    ok, _ = gates.step4_verify_fields(sk, require_clean=False)
    year_issues = gates.step4_year_quality_issues(sk)
    feedback = _verify_feedback_from_job(job)
    cfg = get_work_config(work)
    sk_data = json.loads(sk.read_text(encoding="utf-8"))
    has_entries = bool(sk_data.get("entries"))

    # 《史记》Step4：LLM 前先脚本兜底（坐标/年份/主轴说明）
    if work.startswith("01史记"):
        n_fb, fb_logs = gates.step4_shiji_person_fallback(sk, work, vol)
        if n_fb:
            for ln in fb_logs:
                print(f"   📌 Step4 预修复: {ln}", flush=True)
            ok, _ = gates.step4_verify_fields(sk, require_clean=False)
            year_issues = gates.step4_year_quality_issues(sk)

    force_llm = (not ok) or bool(year_issues) or bool(feedback)
    if cfg.get("force_step4_llm") and has_entries:
        force_llm = True

    if not force_llm:
        if has_entries and cfg.get("require_llm_knowledge"):
            raise RuntimeError(
                f"{work} 叙事卷 Step4 须经 LLM 考订年份/坐标（force_step4_llm）"
            )
        if not has_entries:
            _stamp_skip_provenance(work, vol, "无叙事条目")
        print("✅ Step4 字段已齐全，跳过 LLM", flush=True)
    else:
        if ok and (year_issues or feedback):
            why = []
            if year_issues:
                why.append(f"年代占位 {len(year_issues)} 项")
            if feedback:
                why.append("上轮 verify 未过")
            print(
                f"⚠️ Step4 强制 LLM 修正（{', '.join(why)}）",
                flush=True,
            )
        missing = gates.step4_missing_report(sk) if not ok else ""
        correction = _step4_correction_prompt(
            job, year_issues=year_issues, missing_report=missing
        )
        cfg = get_work_config(work)
        agent = cfg.get("openclaw_agent", "hist-worker")
        idx = gates.load_paragraph_index(work, vol)
        session_id = make_session_id(work, vol, "4", job_id)
        entries = sk_data.get("entries") or []
        spindle_only = (
            work.startswith("02汉书")
            and step4_spindle_llm.spindle_only_missing(entries)
            and not year_issues
        )

        if spindle_only:
            db.update_job(
                job_id, status="running", session_id=session_id, started_at=db.utc_now()
            )
            events.log(
                "llm_start",
                work=work,
                vol=vol,
                step="4",
                session_id=session_id,
                mode="spindle_only",
            )
            print(f"⏳ LLM Step4 卷{vol} → 专写主轴说明（小 prompt）", flush=True)
            step4_spindle_llm.run_spindle_llm_supplement(
                work, vol, sk, session_id=session_id
            )
            events.log(
                "step4_artifacts_written",
                work=work,
                vol=vol,
                artifacts=[str(sk)],
                mode="spindle_only",
            )
            _stamp_llm_provenance(work, vol, "4", session_id=session_id)
        else:
            base = build_step_prompt(work, vol, "4", idx)
            prompt = base + "\n\n" + (correction or missing or "见 skeleton 中 _needs_llm")
            prompt += (
                "\n\n⚠️ 禁止删除 _auto_filled / _needs_llm。"
                "只补/改正式字段。临时字段由编排器脚本 finalize 删除。"
            )
            db.update_job(job_id, status="running", session_id=session_id, started_at=db.utc_now())
            events.log("llm_start", work=work, vol=vol, step="4", session_id=session_id)
            print(f"⏳ LLM Step4 卷{vol} → 修正字段/年份", flush=True)
            if year_issues:
                for ln in year_issues[:6]:
                    print(f"   {ln}", flush=True)
            sk_path = gates.skeleton_path(work, vol) or expected_skeleton_path(work, vol, idx)
            t0 = time.time()
            result = run_agent_turn(
                prompt,
                agent_id=agent,
                session_id=session_id,
                timeout_sec=600,
                artifact_paths={"skeleton": sk_path},
            )
            elapsed = time.time() - t0
            written = result.get("written_artifacts") or []
            events.log(
                "llm_end",
                work=work,
                vol=vol,
                step="4",
                elapsed_sec=round(elapsed, 1),
                artifacts=written or None,
            )
            db.update_job(job_id, detail=str(result.get("result") or "")[:1500])
            if not written:
                sk_retry = json.loads(sk.read_text(encoding="utf-8"))
                if work.startswith("02汉书") and step4_spindle_llm.spindle_only_missing(
                    sk_retry.get("entries") or []
                ):
                    print(
                        "⚠️ 整卷 skeleton 未落盘，改走主轴说明专写 LLM",
                        flush=True,
                    )
                    step4_spindle_llm.run_spindle_llm_supplement(
                        work, vol, sk, session_id=session_id
                    )
                    events.log(
                        "step4_artifacts_written",
                        work=work,
                        vol=vol,
                        artifacts=[str(sk)],
                        mode="spindle_fallback",
                    )
                else:
                    raise RuntimeError(
                        "Step4 LLM 未落盘 skeleton：回复中缺少完整 ```json 代码块"
                        "（须含 segment_attribution + entries）。"
                        "禁止仅用 Markdown 列表 + STEP4_DONE。"
                    )
            else:
                events.log(
                    "step4_artifacts_written",
                    work=work,
                    vol=vol,
                    artifacts=written,
                )
            _stamp_llm_provenance(work, vol, "4", session_id=session_id)

        ok, recon_msg = gates.step4_reconcile(sk)
        if ok:
            print("✅ Step4 reconcile（帝王表坐标链对齐）", flush=True)
        else:
            print(f"⚠️ Step4 reconcile 失败:\n{recon_msg[-800:]}", flush=True)

        still = gates.step4_priority_gap_count(sk)
        if still:
            print(
                f"⚠️ LLM 未写入 {still} 条君王优先级，"
                f"reconcile 已按段数脚本补缺（可人工改 skeleton 后重跑 Step4）",
                flush=True,
            )

        ok, msg = gates.step4_verify_fields(sk, require_clean=False)
        if not ok:
            payload = gates.step4_collect_decisions(sk)
            if payload.get("items"):
                decisions.resolve_coord_conflict_interactive(
                    work,
                    vol,
                    sk,
                    payload,
                    verify_fn=gates.step4_verify_fields,
                    reconcile_fn=gates.step4_reconcile,
                )
            else:
                if work == "01史记":
                    n_fb, fb_logs = gates.step4_shiji_person_fallback(sk, work, vol)
                    if n_fb:
                        for ln in fb_logs:
                            print(f"   📌 Step4 fallback: {ln}", flush=True)
                        ok, msg = gates.step4_verify_fields(sk, require_clean=False)
                if not ok:
                    gates.step4_restore_scratch(sk)
                    raise RuntimeError(
                        f"verify step4 失败:\nStep4 LLM 后字段仍缺失（已恢复 _auto_filled 供重试）:\n{msg}"
                    )

    # LLM 跳过或完成后、finalize 前再加固一轮（PATCH/考订字段）
    if work.startswith("01史记"):
        n_fb, fb_logs = gates.step4_shiji_person_fallback(sk, work, vol)
        if n_fb:
            for ln in fb_logs:
                print(f"   📌 Step4 finalize 前加固: {ln}", flush=True)

    # Step4d：峰值年（年份终态后、finalize 前；独立于 Step4 主 LLM）
    sk_data = json.loads(sk.read_text(encoding="utf-8"))
    if sk_data.get("entries"):
        cfg = get_work_config(work)
        use_peak_llm = cfg.get("step4_peak_llm", True)
        _peak_stats, peak_logs = gates.step4_peak_year(sk, use_llm=use_peak_llm)
        for ln in peak_logs:
            print(f"   📌 {ln}", flush=True)
        ok_peak, peak_msg = gates.step4_peak_verify(sk)
        if not ok_peak:
            gates.step4_restore_scratch(sk)
            raise RuntimeError(f"verify step4 失败:\n峰值年硬校验:\n{peak_msg}")
        print("✅ Step4 峰值年标注完成", flush=True)

    ok, msg = gates.step4_finalize(sk)
    if not ok:
        gates.step4_restore_scratch(sk)
        raise RuntimeError(f"verify step4 失败:\nstep4 finalize 失败:\n{msg}")
    print("✅ Step4 finalize（脚本删除临时字段）", flush=True)

    # finalize 后补考订字段（防 LLM/finalize 遗漏）
    if work.startswith("01史记"):
        n_fb, fb_logs = gates.step4_shiji_person_fallback(sk, work, vol)
        if n_fb:
            for ln in fb_logs:
                print(f"   📌 Step4 finalize 后加固: {ln}", flush=True)

    ok, msg = gates.verify_step4_final(sk)
    if not ok and work.startswith("01史记"):
        print("⚠️ check_format final 未过，尝试脚本自动修复…", flush=True)
        recovered, rec_logs = gates.step4_recover_before_fail(sk, work, vol)
        for ln in rec_logs:
            print(f"   📌 {ln}", flush=True)
        if recovered:
            ok, msg = True, "recovered"
    if not ok:
        gates.step4_restore_scratch(sk)
        raise RuntimeError(f"verify step4 失败:\ncheck_format final:\n{msg}")
    print("✅ check_format --phase final 通过", flush=True)


def _run_verify_phase(work: str, vol: str, step: str, job_id: int) -> None:
    """Step 硬检（verify / 段落索引等）。"""
    if step == "1":
        sk = gates.skeleton_path(work, vol)
        if not sk:
            raise RuntimeError("Step1 后未找到 skeleton 文件")
        ok, msg = gates.verify_paragraph_index(work, vol, sk)
        if not ok:
            raise RuntimeError(msg)

    if step == "2":
        sk = gates.skeleton_path(work, vol)
        if sk:
            repaired, repair_msg = hezhuan_repair.strip_bogus_hezhuan_entries(
                work, vol, skeleton_path=sk
            )
            if repaired:
                events.log("hezhuan_bogus_strip", work=work, vol=vol, detail=repair_msg)
                print(f"🔧 {repair_msg}", flush=True)
            ok_prep, prep_msg = gates.step2_prepare(sk)
            if ok_prep and prep_msg and "无需补" not in prep_msg:
                events.log("step2_emperor_supplement", work=work, vol=vol, detail=prep_msg)
                print(f"🔧 {prep_msg}", flush=True)

    if step == "3":
        sk = gates.skeleton_path(work, vol)
        if sk:
            ok_audit, audit_msg = gates.step3_write_audit_block(work, vol, sk)
            if ok_audit:
                events.log("step3_audit_block", work=work, vol=vol, detail=audit_msg)
                print(f"🔧 {audit_msg}", flush=True)
            else:
                repaired, repair_msg = audit_repair.sync_audit_paragraph_table(
                    work, vol, skeleton_path=sk
                )
                if repaired:
                    events.log("audit_paragraph_sync", work=work, vol=vol, detail=repair_msg)
                    print(f"🔧 {repair_msg}", flush=True)
                elif not ok_audit:
                    print(f"⚠️ Step3 审计块写入失败:\n{audit_msg[-400:]}", flush=True)

    ok, msg = gates.verify_step(work, vol, step)
    if not ok:
        if step == "3" and "退回" in msg:
            n = db.reset_volume_steps(work, vol, through_step="3")
            events.log("step3_reject_reset", work=work, vol=vol, jobs_reset=n)
            print(
                f"↩ Step3 打回：已重置卷{vol} Step1–3 共 {n} 个 job 为 pending",
                flush=True,
            )
        raise RuntimeError(f"verify step{step} 失败:\n{msg}")

    db.update_job(job_id, status="done", finished_at=db.utc_now(), fail_count=0)
    events.log("job_done", work=work, vol=vol, step=step)


def _skip_llm_after_duration_bypass(job: dict) -> bool:
    d = job.get("detail") or ""
    return (
        d.startswith("duration_bypass:verify_only")
        or d.startswith("repair_bypass:verify_only")
        or d.startswith("repair_bypass:volume_repair")
        or d.startswith("repair_bypass:blocks_autofix")
    )


def _try_mechanical_step1b(
    work: str, vol: str, idx: dict, job_id: int
) -> bool:
    """single/fanzuo 机械划块并展开 skeleton；hezhuan 亦支持机械划块。"""
    if not protagonist_workflow.use_protagonist_phase(work):
        return False
    manifest = protagonist_workflow.load_protagonists(work, vol)
    if not manifest:
        return False
    bp = blocks_workflow.blocks_path(work, vol)
    if not bp.exists():
        mech_ok, mech_msg = blocks_workflow.try_mechanical_blocks_from_manifest(
            work, vol, idx, manifest=manifest
        )
        if mech_ok:
            print(f"📐 Step1b 机械划块：{mech_msg}", flush=True)
        elif mech_msg and "非 single/fanzuo" not in mech_msg:
            print(f"⚠️ 机械划块未用：{mech_msg}", flush=True)
            if str(work).startswith("02汉书"):
                from lib.hanshu_hezhuan_autofix import try_repair_hanshu_hezhuan_step1

                rep_ok, rep_msg = try_repair_hanshu_hezhuan_step1(
                    work, vol, idx, manifest=manifest
                )
                if rep_ok:
                    print(f"🔧 汉书合传自动划块：{rep_msg}", flush=True)
                else:
                    return False
            else:
                return False
        else:
            return False
    if not bp.exists():
        return False
    ok_blk, blk_msg = blocks_workflow.blocks_valid(bp, idx)
    if not ok_blk:
        return False
    dual_ok, dual_msg = protagonist_workflow.validate_dual(work, vol, idx)
    if not dual_ok:
        print(f"⚠️ 机械划块双重校验未过：{dual_msg}", flush=True)
        return False
    try:
        blocks_workflow.expand_blocks_to_skeleton(work, vol, idx, blocks_file=bp)
        ok, sk_msg = gates.step1_skeleton_valid(work, vol)
        if not ok:
            return False
        events.log("step1_mechanical_blocks", work=work, vol=vol, detail=blk_msg)
        print(
            f"✅ Step1 跳过 LLM（机械划块）：{blk_msg} · {dual_msg} → {sk_msg}",
            flush=True,
        )
        db.update_job(
            job_id,
            status="running",
            detail=f"skip_llm mechanical: {blk_msg}",
            started_at=db.utc_now(),
        )
        _stamp_llm_provenance(work, vol, "1")
        return True
    except ValueError as exc:
        print(f"⚠️ 机械划块展开失败：{exc}", flush=True)
        return False


def _run_llm_phase(work: str, vol: str, step: str, job_id: int, job: dict) -> None:
    if step in ("1", "3") and _skip_llm_after_duration_bypass(job):
        print(
            f"✅ Step{step} 用时已放行，跳过 LLM 直接 verify",
            flush=True,
        )
        db.update_job(job_id, status="running", detail="duration_bypass:done")
        return

    if step == "1":
        feedback = _verify_feedback_from_job(job)
        sk_early = gates.skeleton_path(work, vol)
        if sk_early and sk_early.is_file():
            from lib.skeleton_seal import load_skeleton_sealed

            j4 = db.get_job(work, vol, "4")
            if j4 and j4.get("status") == "done" and load_skeleton_sealed(sk_early):
                print(
                    f"⏭ 卷{vol} Step4 已封板，跳过 Step1 LLM/expand",
                    flush=True,
                )
                db.update_job(
                    job_id,
                    status="running",
                    detail="skip_llm: step4_sealed",
                    started_at=db.utc_now(),
                )
                return
        if feedback and "未找到 skeleton" in feedback:
            db.update_job(job_id, detail=None)
            feedback = ""
        idx = gates.load_paragraph_index(work, vol)
        use_blocks = blocks_workflow.use_blocks_step1(work, int(idx["total"]))
        sk = gates.skeleton_path(work, vol)
        if sk:
            repaired, repair_msg = evidence_repair.repair_step1_evidence(
                work, vol, skeleton_path=sk
            )
            if repaired:
                events.log("evidence_repair", work=work, vol=vol, detail=repair_msg)
                print(f"🔧 Step1 证据修复：{repair_msg}", flush=True)
        if use_blocks:
            bp = blocks_workflow.blocks_path(work, vol)
            if not bp.exists() and _try_mechanical_step1b(work, vol, idx, job_id):
                return
            if bp.exists():
                ok_blk, blk_msg = blocks_workflow.blocks_valid(bp, idx)
                dual_ok = True
                dual_msg = ""
                if ok_blk and protagonist_workflow.use_protagonist_phase(work):
                    ok_p, p_msg = protagonist_workflow.protagonists_valid(work, vol, idx)
                    if not ok_p:
                        ok_blk = False
                        blk_msg = f"缺少有效 protagonists: {p_msg}"
                    else:
                        dual_ok, dual_msg = protagonist_workflow.validate_dual(
                            work, vol, idx
                        )
                        if not dual_ok:
                            ok_blk = False
                            blk_msg = dual_msg
                if ok_blk:
                    try:
                        blocks_workflow.expand_blocks_to_skeleton(work, vol, idx, blocks_file=bp)
                        ok, sk_msg = gates.step1_skeleton_valid(work, vol)
                        if ok:
                            events.log("step1_blocks_expand", work=work, vol=vol, detail=blk_msg)
                            print(
                                f"✅ Step1 跳过 LLM（blocks+主轴已就绪）：{blk_msg}"
                                + (f" · {dual_msg}" if dual_msg else "")
                                + f" → {sk_msg}",
                                flush=True,
                            )
                            db.update_job(
                                job_id,
                                status="running",
                                detail=f"skip_llm blocks: {blk_msg}",
                                started_at=db.utc_now(),
                            )
                            return
                    except ValueError as exc:
                        print(f"⚠️ blocks 展开失败，将重跑 LLM blocks：{exc}", flush=True)
            print(
                f"📦 长卷 Step1（{idx['total']} 段）→ blocks 模式，禁止全量 skeleton LLM",
                flush=True,
            )
            _run_llm_step(work, vol, step, job_id, job, use_blocks=True)
            return
        if _try_mechanical_step1b(work, vol, idx, job_id):
            return
        if repair_mode() and not feedback:
            cfg = get_work_config(work)
            if not cfg.get("require_llm_knowledge"):
                ok, sk_msg = gates.step1_skeleton_valid(work, vol)
                if ok:
                    ok_full, _ = gates.verify_step(work, vol, "1")
                    if ok_full:
                        events.log("step1_skip_llm", work=work, vol=vol, skeleton=sk_msg)
                        print(
                            f"✅ Step1 跳过 LLM（HIST_REPAIR=1）：{sk_msg} 已通过 verify",
                            flush=True,
                        )
                        db.update_job(
                            job_id,
                            status="running",
                            detail=f"skip_llm: {sk_msg}",
                            started_at=db.utc_now(),
                        )
                        return
        _run_llm_step(work, vol, step, job_id, job)
        return

    if step == "4":
        _run_step4(work, vol, job_id, job)
        return

    if step == "3":
        sk = gates.skeleton_path(work, vol)
        if not sk:
            raise RuntimeError("Step3 前缺少 skeleton")
        ok, msg = gates.step3_write_audit_block(work, vol, sk)
        if not ok:
            raise RuntimeError(f"Step3 审计块生成失败:\n{msg}")
        events.log("step3_script_audit", work=work, vol=vol, detail=msg)
        print(f"✅ Step3 脚本审计（skeleton → 审计 MD）", flush=True)
        db.update_job(
            job_id,
            status="running",
            detail=f"skip_llm: {msg[:200]}",
            started_at=db.utc_now(),
        )
        return

    _run_llm_step(work, vol, step, job_id, job)


def _manifest_skip_reason(work: str, vol: str) -> Optional[str]:
    """Step1a manifest 已标 narrative_mode=skip 时整卷跳过。"""
    if not protagonist_workflow.use_protagonist_phase(work):
        return None
    manifest = protagonist_workflow.load_protagonists(work, vol)
    if not manifest:
        return None
    from lib.volume_manifest import infer_narrative_mode

    if infer_narrative_mode(manifest) != "skip":
        return None
    reason = (manifest.get("skip_reason") or "").strip()
    vname = (manifest.get("volume_name") or "").strip()
    if reason:
        return reason[:200]
    if vname:
        return f"非叙事卷「{vname}」（manifest skip）"
    return "非叙事卷（manifest skip）"


def _skip_volume_reason(work: str, vol: str) -> Optional[str]:
    """表/书/志卷或 manifest skip → 整卷 skip。"""
    manifest_reason = _manifest_skip_reason(work, vol)
    if manifest_reason:
        return manifest_reason
    from lib.volume_manifest import skip_reason_from_volume_name

    cfg = get_work_config(work)
    try:
        idx = gates.load_paragraph_index(work, vol)
    except Exception:
        return None
    name = blocks_workflow.volume_display_name(work, vol, idx)
    reason = skip_reason_from_volume_name(name)
    if not reason:
        return None
    if name.endswith("表") and not cfg.get("skip_table_volumes", True):
        return None
    if name.endswith("书") and not cfg.get("skip_book_volumes", True):
        return None
    if name.endswith("志") and not cfg.get("skip_zhizhi_volumes", True):
        return None
    return reason


def _preflight_skip_non_narrative_volumes(work: str) -> int:
    """跑批前批量跳过表/书/志卷，含已误入队部分完成的卷；志书若已有占位 entries 则脚本清空。"""
    from lib.paragraph_index import list_volume_files

    total = 0
    for item in list_volume_files(work):
        vol = item[0] if isinstance(item, tuple) else str(item)
        reason = _skip_volume_reason(work, vol)
        if not reason:
            continue
        sk = gates.skeleton_path(work, vol)
        if sk and sk.exists():
            try:
                data = json.loads(sk.read_text(encoding="utf-8"))
                if data.get("entries"):
                    idx = gates.load_paragraph_index(work, vol)
                    vname = blocks_workflow.volume_display_name(work, vol, idx)
                    ok, msg = repair_registry.repair_skip_narrative_volume(
                        work, vol, idx, vname
                    )
                    if ok:
                        print(f"🔧 {msg}", flush=True)
                        total += 1
                        continue
            except (json.JSONDecodeError, OSError, FileNotFoundError):
                pass
        n = db.skip_volume_jobs(work, vol, reason, force=True)
        if n:
            print(f"⏭ 卷{vol} 整卷跳过（{reason}），已标记 {n} 个 job", flush=True)
            events.log("volume_skipped", work=work, vol=vol, reason=reason, force=True)
            total += n
    return total


def _require_prior_step_done(work: str, vol: str, step: str) -> None:
    """Step2+ 须前一步 done/skipped；禁止 Step1 failed 仍跑 Step2–4。"""
    reason = db.step_dependency_block_reason(work, vol, step)
    if reason:
        raise RuntimeError(f"卷{vol} Step{step} 前置条件不满足：{reason}")


def _require_skeleton_for_step(work: str, vol: str, step: str) -> None:
    """Step2+ 须有 skeleton；缺失时纠正误标 done 的 Step1，避免空跑 Step2。"""
    if step not in ("2", "3", "4"):
        return
    if gates.skeleton_path(work, vol):
        return
    j1 = db.get_job(work, vol, "1")
    if j1 and j1["status"] == "done":
        db.update_job(
            j1["id"],
            status="pending",
            finished_at=None,
            started_at=None,
            detail=None,
        )
    raise RuntimeError(
        f"卷{vol} Step{step} 前置条件不满足：尚无 skeleton，须先完成 Step1（LLM blocks → expand）"
    )


def _run_job(work: str, job: dict) -> None:
    vol = job["vol"]
    step = job["step"]
    job_id = job["id"]
    skip_reason = _skip_volume_reason(work, vol)
    if skip_reason:
        n = db.skip_volume_jobs(work, vol, skip_reason, force=True)
        events.log("volume_skipped", work=work, vol=vol, reason=skip_reason)
        print(f"⏭ 卷{vol} 整卷跳过（{skip_reason}），已标记 {n} 个 job 为 skipped", flush=True)
        return
    duration_bypass_active = step in ("1", "3") and _skip_llm_after_duration_bypass(job)
    events.log("job_start", work=work, vol=vol, step=step, job_id=job_id)
    db.set_work_status(work, db.get_work(work)["status"], current_vol=vol, current_step=step)
    write_active_job(work, vol, step, job_id=job_id)

    try:
        _require_prior_step_done(work, vol, step)
        _require_skeleton_for_step(work, vol, step)
        if step in LLM_STEPS:
            try:
                _run_llm_phase(work, vol, step, job_id, job)
            except decisions.DurationHardFail as e:
                action = decisions.handle_duration_hard_fail(
                    work, vol, step, job_id, job, e
                )
                if action in ("retry", "pause"):
                    return
                # bypass → 继续 verify

        _run_verify_phase(work, vol, step, job_id)
    except decisions.DecisionRequired as e:
        db.update_job(
            job_id,
            status="pending",
            finished_at=None,
            started_at=None,
            session_id=None,
            detail=e.summary[:2000],
        )
        db.set_work_status(work, "awaiting_decision", blocked_reason=e.summary[:500])
        events.log(
            "awaiting_decision",
            work=work,
            vol=vol,
            step=step,
            decision_file=str(e.decision_path),
        )
        print(e.summary, flush=True)
        if not e.interactive:
            print(
                f"\n已暂停。在终端执行 hist run-work --work {work} 将弹出选项继续。",
                flush=True,
            )
        return
    except Exception as e:
        cfg = get_work_config(work)
        max_retries = gates.max_retries_per_step(work, step)
        fail_count = int(job.get("fail_count") or 0) + 1
        db.update_job(
            job_id,
            status="failed",
            finished_at=db.utc_now(),
            fail_count=fail_count,
            detail=str(e)[:2000],
        )
        events.log(
            "job_failed",
            work=work,
            vol=vol,
            step=step,
            error=str(e)[:500],
            fail_count=fail_count,
        )
        if fail_count < max_retries:
            retry_detail = None
            if duration_bypass_active:
                retry_detail = "duration_bypass:verify_only"
            elif step == "3" and "verify step3" in str(e).lower():
                err_str = str(e)
                para_keywords = ("段落覆盖", "省略", "行，少于", "行明显多于", "范围压缩")
                if any(k in err_str for k in para_keywords):
                    repaired, repair_msg = audit_repair.sync_audit_paragraph_table(
                        work, vol
                    )
                    if repaired:
                        print(
                            f"🔧 {repair_msg}，跳过 LLM 直接重试 verify",
                            flush=True,
                        )
                        retry_detail = "repair_bypass:verify_only"
                    else:
                        retry_detail = f"verify_feedback:{err_str[:1800]}"
                else:
                    retry_detail = f"verify_feedback:{err_str[:1800]}"
            elif step == "4" and "verify step4" in str(e).lower():
                err_str = str(e)
                plan = failure_classifier.classify_failure(
                    "4", err_str, work=work, vol=vol, fail_count=fail_count
                )
                if failure_classifier.should_rollback_from_step4(plan, "4"):
                    _rollback_to_step1(
                        work,
                        vol,
                        "4",
                        job_id,
                        err_str,
                        fail_count,
                        through_step="3",
                        event_name="step4_rollback_step1",
                    )
                    return
                retry_detail, bypass = _apply_failure_recovery(
                    work, vol, step, err_str, fail_count
                )
                if bypass:
                    pass
            elif step == "1" and not retry_detail:
                err_str = str(e)
                if "verify step1" in err_str.lower():
                    repaired, repair_msg = evidence_repair.repair_step1_evidence(work, vol)
                    if repaired:
                        print(f"🔧 {repair_msg}，跳过 LLM 直接重试 verify", flush=True)
                        retry_detail = "repair_bypass:verify_only"
                    else:
                        retry_detail, _ = _apply_failure_recovery(
                            work, vol, step, err_str, fail_count
                        )
                        print(
                            f"⚠️ 卷{vol} Step1 原文挑战未过 ({fail_count}/{max_retries})，"
                            f"将把结构化失败原因注入 LLM 自动重试",
                            flush=True,
                        )
                else:
                    retry_detail, _ = _apply_failure_recovery(
                        work, vol, step, err_str, fail_count
                    )
            elif step == "2" and "verify step2" in str(e).lower():
                err_str = str(e)
                retry_detail, rolled_back = _handle_step2_verify_failure(
                    work, vol, job_id, err_str, fail_count, max_retries
                )
                if rolled_back:
                    return
            db.update_job(
                job_id,
                status="pending",
                finished_at=None,
                started_at=None,
                session_id=None,
                **({"detail": retry_detail} if retry_detail else {}),
            )
            events.log(
                "job_retry_scheduled",
                work=work,
                vol=vol,
                step=step,
                attempt=fail_count,
                max_retries=max_retries,
                duration_bypass=duration_bypass_active,
            )
            if duration_bypass_active:
                bypass_kind = "用时" if (job.get("detail") or "").startswith(
                    "duration_bypass"
                ) else "段落表脚本修复"
                print(
                    f"⚠️ 卷{vol} Step{step} verify 失败 ({fail_count}/{max_retries})，"
                    f"将重试 verify（{bypass_kind}已放行，跳过 LLM）",
                    flush=True,
                )
            elif step == "3":
                print(
                    f"⚠️ 卷{vol} Step3 审计未通过 ({fail_count}/{max_retries})，"
                    f"将把失败原因注入 LLM 自动重试",
                    flush=True,
                )
                # 打印可读的失败摘要（避免用户只看到空行）
                err_lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()][-6:]
                for ln in err_lines:
                    print(f"   {ln}", flush=True)
            elif step == "4":
                print(
                    f"⚠️ 卷{vol} Step4 质检未通过 ({fail_count}/{max_retries})，"
                    f"将把失败原因注入 LLM 自动重试",
                    flush=True,
                )
                err_lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()][-8:]
                for ln in err_lines:
                    print(f"   {ln}", flush=True)
            elif step == "1":
                print(
                    f"⚠️ 卷{vol} Step1 失败 ({fail_count}/{max_retries})，将自动重试",
                    flush=True,
                )
                err_lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()][-8:]
                for ln in err_lines:
                    print(f"   {ln}", flush=True)
            else:
                print(
                    f"⚠️ 卷{vol} Step{step} 失败 ({fail_count}/{max_retries})，将自动重试",
                    flush=True,
                )
            return
        if step == "3":
            repaired, repair_msg = audit_repair.sync_audit_paragraph_table(work, vol)
            if repaired:
                events.log("audit_paragraph_sync_last_chance", work=work, vol=vol)
                print(f"🔧 熔断前最后修复：{repair_msg}", flush=True)
                ok, msg = gates.verify_step(work, vol, "3")
                if ok:
                    db.update_job(
                        job_id,
                        status="done",
                        finished_at=db.utc_now(),
                        fail_count=0,
                        detail=None,
                    )
                    events.log("job_done", work=work, vol=vol, step=step)
                    print(f"✅ 卷{vol} Step3 脚本修复后 verify 通过", flush=True)
                    return
        if step == "1" and work.startswith("01史记"):
            from lib import shiji_autofix

            repaired, repair_msg = shiji_autofix.repair_step1_blocks(work, vol)
            if repaired:
                events.log("shiji_blocks_autofix", work=work, vol=vol, detail=repair_msg)
                print(f"🔧 熔断前 blocks 修复：{repair_msg}", flush=True)
                db.update_job(
                    job_id,
                    status="pending",
                    fail_count=0,
                    detail="repair_bypass:blocks_autofix",
                )
                db.set_work_status(work, "running", blocked_reason=None)
                print(f"✅ 卷{vol} Step1 blocks 已脚本修复，将重试", flush=True)
                return
        if step == "4" and work.startswith("01史记"):
            from lib import shiji_autofix

            repaired, repair_msg = shiji_autofix.repair_step4_shiji(work, vol)
            if repaired:
                events.log("shiji_step4_autofix", work=work, vol=vol, detail=repair_msg)
                print(f"🔧 熔断前 Step4 修复：{repair_msg}", flush=True)
                db.update_job(
                    job_id,
                    status="done",
                    finished_at=db.utc_now(),
                    fail_count=0,
                    detail=None,
                )
                events.log("job_done", work=work, vol=vol, step=step)
                print(f"✅ 卷{vol} Step4 脚本修复后通过", flush=True)
                return
        if step == "4" and work.startswith("02汉书"):
            from lib import hanshu_autofix

            repaired, repair_msg = hanshu_autofix.try_recover_hanshu_step4(work, vol)
            if repaired:
                events.log("hanshu_step4_autofix", work=work, vol=vol, detail=repair_msg)
                print(f"🔧 熔断前 Step4 修复：{repair_msg}", flush=True)
                db.update_job(
                    job_id,
                    status="done",
                    finished_at=db.utc_now(),
                    fail_count=0,
                    detail=None,
                )
                events.log("job_done", work=work, vol=vol, step=step)
                print(f"✅ 卷{vol} Step4 脚本修复后通过", flush=True)
                return
        db.set_work_status(work, "paused", blocked_reason=str(e)[:500])
        events.log(
            "retry_exhausted",
            work=work,
            vol=vol,
            step=step,
            fail_count=fail_count,
        )
        if decisions.is_duration_hard_fail_msg(str(e)) and step in ("1", "3"):
            print(
                f"⏸ 卷{vol} Step{step} 用时过短，已连续失败 {fail_count} 次。",
                flush=True,
            )
            print(
                f"   在终端执行: hist run-work --work {work}",
                flush=True,
            )
            print(
                "   将弹出选项：放行继续 verify（你自行质检）/ 重试 LLM / 暂停",
                flush=True,
            )
        else:
            if step == "3":
                print(
                    f"⏸ 卷{vol} Step3 已重试 {fail_count} 次仍未通过，著作 paused。"
                    f" 执行 hist resume --work {work} 后 run-work 将继续自动重试"
                    f"（失败原因会注入 LLM prompt）",
                    flush=True,
                )
            elif step == "4":
                print(
                    f"⏸ 卷{vol} Step4 已重试 {fail_count} 次仍未通过，著作 paused。"
                    f" 执行 hist resume --work {work} 后 run-work 将继续自动重试"
                    f"（年份/坐标错误会注入 LLM prompt）",
                    flush=True,
                )
            else:
                print(
                    f"⏸ 卷{vol} Step{step} 已失败 {fail_count} 次，著作 paused。"
                    f" 修复后: hist resume --work {work}",
                    flush=True,
                )
        raise
    finally:
        clear_active_job()


def _gold_pending(work: str) -> bool:
    w = db.get_work(work)
    if not w:
        return False
    if w.get("gold_approved"):
        return False
    cfg = get_work_config(work)
    return bool(cfg.get("gold_volumes")) and w["status"] == "gold_review"


def run_work(
    work: str,
    *,
    max_jobs: Optional[int] = None,
    one_volume: bool = False,
    stop_on_fail: bool = True,
) -> int:
    """跑一本书；返回 exit code。one_volume=True 时仅完成一卷 Step1–4 后停止。"""
    if one_volume and max_jobs is None:
        max_jobs = len(STEPS)
    try:
        _acquire_run_lock(work)
    except RuntimeError as e:
        print(str(e), flush=True)
        return 1
    try:
        return _run_work_locked(
            work,
            max_jobs=max_jobs,
            one_volume=one_volume,
            stop_on_fail=stop_on_fail,
        )
    finally:
        _release_run_lock(work)


def _run_work_locked(
    work: str,
    *,
    max_jobs: Optional[int] = None,
    one_volume: bool = False,
    stop_on_fail: bool = True,
) -> int:
    cfg = get_work_config(work)
    w = db.get_work(work)
    if not w:
        bootstrap(work)
        w = db.get_work(work)
    db.retire_reference_step_jobs(work)
    _preflight_skip_non_narrative_volumes(work)

    if w["status"] == "awaiting_decision":
        if not decisions.try_resume_duration_decision(work):
            if not decisions.try_resume_awaiting_decision(work):
                return 1
        w = db.get_work(work)

    if w["status"] == "paused":
        if decisions.is_duration_hard_fail_msg(w.get("blocked_reason") or ""):
            if decisions.try_resume_duration_decision(work):
                w = db.get_work(work)
            else:
                return 1
        elif confirmations.interactive_resume_from_user_pause(work):
            w = db.get_work(work)
        else:
            return 1

    if _gold_pending(work):
        gold_vols = cfg.get("gold_volumes", [])
        for gv in gold_vols:
            gv = str(gv).zfill(3)
            for step in STEPS:
                job = _find_or_create_pending(work, gv, step)
                if job and job["status"] == "pending":
                    try:
                        _run_job(work, job)
                    except Exception:
                        if stop_on_fail:
                            print(f"❌ 金标卷 {gv} 失败。修复后 hist approve-gold --work {work} 前请先 retry")
                            return 1
                    refreshed = _find_or_create_pending(work, gv, step)
                    if not refreshed or refreshed["status"] != "done":
                        print(
                            f"⏸ 金标卷 {gv} Step{step} 未完成，"
                            f"先修本步再跑（不继续 Step{int(step)+1}…）",
                            flush=True,
                        )
                        break
        if not all(_vol_steps_done(work, gv) for gv in [str(g).zfill(3) for g in gold_vols]):
            pending_steps = []
            for gv in [str(g).zfill(3) for g in gold_vols]:
                with db.connect() as conn:
                    rows = conn.execute(
                        "SELECT step, status FROM jobs WHERE work_id=? AND vol=? AND status!='done' ORDER BY step",
                        (work, gv),
                    ).fetchall()
                pending_steps.extend([f"卷{gv} Step{r['step']}({r['status']})" for r in rows])
            print(f"⏸ 金标卷未全部完成。待完成：{', '.join(pending_steps) or '未知'}")
            print(f"   全部 done 后将弹出金标确认选项。", flush=True)
            return 0
        if confirmations.interactive_gold_checkpoint(work):
            approve_gold(work)
            w = db.get_work(work)
        else:
            return 0

    if w["status"] == "work_review" and not w.get("work_approved"):
        if confirmations.interactive_work_review_checkpoint(work):
            approve_work(work)
            return 0
        return 0

    if w["status"] == "done" or w.get("work_approved"):
        if w["status"] != "done":
            db.set_work_status(work, "done")
        print(f"✅ {work} 已是 done（已封板）", flush=True)
        return 0

    if w["status"] not in ("running", "bootstrapping"):
        if w["status"] == "queued":
            db.set_work_status(work, "running")
        elif w["status"] == "done":
            print(f"✅ {work} 已是 done")
            return 0
        elif w["status"] == "work_review" and w.get("work_approved"):
            db.set_work_status(work, "done")
            print(f"✅ {work} 已是 done（已封板）")
            return 0

    db.set_work_status(work, "running")
    jobs_run = 0
    batch_vol: Optional[str] = None
    while True:
        if max_jobs is not None and jobs_run >= max_jobs:
            break
        job = db.next_pending_job(work)
        if not job:
            break
        if one_volume:
            if batch_vol is None:
                batch_vol = job["vol"]
            elif job["vol"] != batch_vol:
                print(
                    f"⏸ 卷{batch_vol} 本批 {jobs_run} 步已完成，"
                    f"下卷 {job['vol']} 留待下次 run-work",
                    flush=True,
                )
                break
        cfg_gold = [str(g).zfill(3) for g in cfg.get("gold_volumes", [])]
        if _gold_pending(work) and job["vol"] not in cfg_gold:
            break
        try:
            _run_job(work, job)
            jobs_run += 1
        except Exception as e:
            print(f"❌ job 失败: {work} 卷{job['vol']} Step{job['step']}: {e}")
            if stop_on_fail:
                failed_left = db.count_jobs(work, "failed")
                if failed_left > 0:
                    return 1

    pending = db.count_jobs(work, "pending")
    failed = db.count_jobs(work, "failed")
    if pending == 0 and failed == 0:
        w = db.get_work(work)
        if w and w.get("work_approved"):
            print(f"✅ {work} 已封板", flush=True)
            return 0
        db.set_work_status(work, "work_review")
        if confirmations.interactive_work_review_checkpoint(work):
            approve_work(work)
        else:
            print(f"📋 {work} 全部卷步完成，进入 work_review")
    else:
        blocked = db.count_blocked_pending_jobs(work)
        print(f"📊 {work} pending={pending} failed={failed}", end="")
        if blocked:
            print(f" 门禁等待={blocked}", end="")
        print(flush=True)
    return 0


def _find_or_create_pending(work: str, vol: str, step: str) -> Optional[dict]:
    db.init_schema()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE work_id=? AND vol=? AND step=?",
            (work, vol, step),
        ).fetchone()
        return dict(row) if row else None


def _vol_steps_done(work: str, vol: str) -> bool:
    placeholders = ",".join("?" * len(STEPS))
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT status FROM jobs WHERE work_id=? AND vol=? AND step IN ({placeholders})",
            (work, vol, *STEPS),
        ).fetchall()
    return bool(rows) and all(r["status"] == "done" for r in rows)


def reset_work(work: str) -> int:
    """删除全书 skeleton、清空 progress/审计，jobs 重置，从金标卷重跑。"""
    cfg = get_work_config(work)
    events.log("reset_start", work=work)

    ann = paths()["annotations"]
    deleted = 0
    for sk in sorted(ann.glob(f"{work}_*_skeleton.json")):
        sk.unlink()
        deleted += 1

    prog = paths()["progress"] / f"{work}_progress.json"
    if prog.exists():
        prog.unlink()

    audit = paths()["audit"] / f"{work}_标注审计.md"
    title = cfg.get("title", work)
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(f"# {title} 标注审计\n\n", encoding="utf-8")

    clear_active_job()
    db.init_schema()
    db.reset_jobs(work)
    db.set_work_status(
        work,
        "gold_review",
        gold_approved=0,
        work_approved=0,
        blocked_reason=None,
        current_vol=None,
        current_step=None,
    )

    vols = bootstrap_indexes(work)
    db.upsert_work(work, title, status="gold_review", volume_count=len(vols))
    db.ensure_jobs(work, vols, STEPS)
    db.retire_reference_step_jobs(work)

    events.log("reset_done", work=work, skeletons_deleted=deleted, volumes=len(vols))
    print(f"✅ 已重置 {work}（{title}）")
    print(f"   删除 skeleton: {deleted} 个")
    print(f"   卷数: {len(vols)}  jobs: 全部 pending")
    print(f"   金标: 待确认（金标卷 {cfg.get('gold_volumes', ['001'])}）")
    print(f"   下一步: hist run-work --work {work} --max-jobs 1")
    return deleted


def approve_gold(work: str) -> None:
    db.set_work_status(work, "running", gold_approved=1)
    events.log("gold_approved", work=work)
    print(f"✅ {work} 金标已通过，可 hist run-work --work {work}")


def approve_work(work: str) -> None:
    subprocess.run(
        [sys.executable, str(ANNOTATE_DIR / "merge_volumes.py"), work],
        check=False,
    )
    db.set_work_status(work, "done", work_approved=1)
    events.log("work_approved", work=work)
    print(f"✅ {work} 已封板 (merge 已触发)")


def resume(work: str) -> None:
    w = db.get_work(work)
    if not w:
        raise SystemExit(f"未知著作: {work}")

    blocked = w.get("blocked_reason") or ""
    if w["status"] in ("paused", "awaiting_decision") and decisions.is_duration_hard_fail_msg(
        blocked
    ):
        print(
            f"⏸ {work} 因 Step 用时过短暂停（卷{w.get('current_vol')} Step{w.get('current_step')}）",
            flush=True,
        )
        if decisions.try_resume_duration_decision(work):
            print(f"▶ 下一步: hist run-work --work {work}", flush=True)
            return
        print(
            f"仍暂停。可随时执行: hist run-work --work {work}  再次选择放行/重试",
            flush=True,
        )
        return

    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE jobs SET status='pending', detail=NULL, session_id=NULL,
                   started_at=NULL, finished_at=NULL, fail_count=0
            WHERE work_id=? AND status IN ('failed', 'running')
            """,
            (work,),
        )
    next_status = confirmations.status_after_user_pause(work)
    db.set_work_status(work, next_status, blocked_reason=None)
    events.log("resume", work=work)
    print(f"▶ {work} 已 resume（状态 → {next_status}）")


def decide(work: str, vol: str, choice: str, *, continue_run: bool = False) -> int:
    """应用 Step4 坐标决策后恢复跑批。"""
    w = db.get_work(work)
    if not w:
        raise SystemExit(f"未知著作: {work}")
    vol = vol.zfill(3)
    sk = gates.skeleton_path(work, vol)
    if not sk:
        raise SystemExit(f"未找到卷{vol} skeleton")
    doc = decisions.load_decision_file(work, vol)
    if not doc:
        print(f"⚠️ 无待决策文件（可能已处理）: {decisions.decision_path(work, vol)}")
    n, logs = decisions.apply_decision(work, vol, choice, skeleton=sk)
    for line in logs[:12]:
        print(f"  · {line}")
    print(f"✅ 已应用决策「{choice}」: {n} 条坐标更新 → {sk.name}")
    db.set_work_status(work, "running", blocked_reason=None, current_vol=vol, current_step="4")
    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE jobs SET status='pending', fail_count=0, detail=NULL,
                   session_id=NULL, started_at=NULL, finished_at=NULL
            WHERE work_id=? AND vol=? AND step='4'
            """,
            (work, vol),
        )
    events.log("decision_applied", work=work, vol=vol, choice=choice, changed=n)
    if continue_run:
        return run_work(work, max_jobs=1)
    print(f"▶ 下一步: hist run-work --work {work}")
    return 0
