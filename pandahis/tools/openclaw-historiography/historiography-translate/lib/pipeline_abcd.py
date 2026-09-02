"""ABCD 翻译流水线：A 结构 → B 文风 → C 成篇 baseline → D enrich。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.coverage_plan import (
    ab_split_required,
    ensure_coverage_ledger,
    plan_json_for_phase_a,
)
from lib.baseline_assemble import load_baseline_parts, write_baseline_file
from lib.batch_split import batched_mother_checklist
from lib.plan_batch_filter import batch_plan_json_for_prompt
from lib.draft_parse import extract_draft_body
from lib.fingerprint import recalled_summary
from lib.openclaw import (
    build_translate_ab_merged_prompt,
    build_translate_assemble_prompt,
    build_translate_structural_prompt,
    build_translate_style_prompt,
    run_agent_turn,
)
from lib.prose_sanitize import polish_mother_file, sanitize_mother_detail
from lib.stall_watch import touch_heartbeat
from lib.verify import (
    verify_baseline_draft,
    verify_mother_draft,
    verify_structural_draft,
    verify_style_retains_structural,
)
from lib.work_artifacts import (
    baseline_draft_path,
    mother_draft_path,
    structural_draft_path,
)
from shared.qa_repair import classify_translate_failure, format_retry_feedback


def abcd_pipeline_enabled() -> bool:
    if os.environ.get("TRANSLATE_PIPELINE", "streamlined").strip().lower() == "streamlined":
        return False
    if os.environ.get("TRANSLATE_ABCD_PIPELINE", "0") == "0":
        return False
    return os.environ.get("TRANSLATE_TWO_PHASE", "1") != "0"


def _mother_batch_size() -> int:
    return max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def _phase_a_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE_A_MAX_RETRIES", "2")))


def _phase_b_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE_B_MAX_RETRIES", "2")))


def _phase_c_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_PHASE_C_MAX_RETRIES", "2")))


def _load_body_field(path: Path, *keys: str) -> str:
    if not path.is_file():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    return extract_draft_body(data, *keys)


def _write_draft(path: Path, entry_id: str, field: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({field: body, "史略ID": entry_id}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _llm_turn(
    work_dir: Path,
    entry_id: str,
    stage: str,
    prompt: str,
    *,
    session_id: str,
    output_path: Path,
    timeout_sec: int = 900,
) -> None:
    touch_heartbeat(work_dir, entry_id, stage=f"llm_{stage}")
    run_agent_turn(
        prompt,
        session_id=session_id,
        timeout_sec=timeout_sec,
        artifact_paths={"output": output_path},
    )
    touch_heartbeat(work_dir, entry_id, stage=f"done_{stage}")


def _run_phase_a_or_b(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    work_dir: Path,
    session_id: str,
    phase: str,
    merged_path: Path,
    merged_field: str,
    load_field: str,
    structural_file: Path | None = None,
) -> Tuple[bool, List[str]]:
    batches = batched_mother_checklist(plan_data)
    parts: List[str] = []

    if len(batches) > 1:
        print(f"📦 {phase} 分批 {entry_id}：{len(batches)} 批", flush=True)

    max_retries = _phase_a_max_retries() if phase == "A" else _phase_b_max_retries()

    for bi, batch_items in enumerate(batches, start=1):
        batch_path = merged_path.with_name(
            f"{merged_path.stem}-b{bi:02d}{merged_path.suffix}"
        )
        sid0 = batch_items[0].get("编号") if batch_items else "?"
        sid1 = batch_items[-1].get("编号") if batch_items else "?"
        label = f"{phase} 第 {bi}/{len(batches)} 批（{sid0}–{sid1}）"
        verify_plan_data = {"母本逐句清单": batch_items}
        batch_plan_json = batch_plan_json_for_prompt(
            plan_data,
            batch_items,
            batch_index=bi,
            batch_total=len(batches),
        )
        errs: List[str] = []

        for attempt in range(max_retries + 1):
            retry_note = ""
            if attempt > 0 and errs:
                fb = classify_translate_failure(
                    errs, stage="phase1" if phase == "A" else "phase_b", fail_count=attempt
                )
                retry_note = (
                    "\n\n--- 上轮质检失败，须修正 ---\n"
                    + format_retry_feedback(fb, errs)
                )
            batch_note = f"\n\n--- {label}：只处理下列 M 清单 ---\n" if len(batches) > 1 else ""

            if phase == "A":
                prompt = build_translate_structural_prompt(
                    entry_id,
                    recalled,
                    recalled_summary(recalled),
                    batch_plan_json,
                    batch_path,
                )
            else:
                a_batch_text = ""
                if structural_file is not None:
                    a_batch = structural_file.with_name(
                        f"{structural_file.stem}-b{bi:02d}{structural_file.suffix}"
                    )
                    a_batch_text = _load_body_field(a_batch, "结构顺译")
                prev_tail = ""
                if bi > 1 and parts:
                    prev_paras = parts[-1].split("\n\n")
                    prev_tail = "\n\n".join(prev_paras[-2:]) if prev_paras else parts[-1]
                ctx_blocks = [t for t in (a_batch_text, prev_tail) if t.strip()]
                ctx = "\n\n---\n\n".join(ctx_blocks)
                prompt = build_translate_style_prompt(
                    entry_id,
                    recalled,
                    recalled_summary(recalled),
                    batch_plan_json,
                    ctx,
                    batch_path,
                )
            prompt += batch_note + retry_note

            print(label + (f"（重试 {attempt}/{max_retries}）" if attempt else ""), flush=True)
            _llm_turn(
                work_dir,
                entry_id,
                phase.lower(),
                prompt,
                session_id=f"{session_id}-{phase.lower()}-b{bi}-r{attempt}",
                output_path=batch_path,
            )
            if not batch_path.is_file():
                errs = [f"{label}: LLM 未落盘"]
                continue
            if phase == "B" and polish_mother_file(batch_path):
                print("   🔧 已校正 B 阶段引号形态", flush=True)

            detail = _load_body_field(batch_path, load_field, "翻译详情")
            touch_heartbeat(work_dir, entry_id, stage=f"verify_{phase.lower()}", detail=label)
            if phase == "A":
                ok, errs = verify_structural_draft(
                    entry_id,
                    recalled,
                    batch_path,
                    plan=verify_plan_data,
                    batch_mode=True,
                    batch_label=label,
                )
            else:
                ok, errs = verify_mother_draft(
                    entry_id,
                    recalled,
                    batch_path,
                    plan=verify_plan_data,
                    batch_mode=True,
                    batch_label=label,
                )
            if ok:
                parts.append(detail)
                break
            print(f"⚠️ {label} 未通过: {errs[0] if errs else '?'}", flush=True)
        else:
            return False, [f"{label}: {e}" for e in errs]

    combined = sanitize_mother_detail("\n\n".join(p for p in parts if p.strip()))
    _write_draft(merged_path, entry_id, merged_field, combined)
    touch_heartbeat(work_dir, entry_id, stage=f"verify_{phase.lower()}")
    if phase == "A":
        return verify_structural_draft(entry_id, recalled, merged_path, plan=plan_data)
    ok, errs = verify_mother_draft(entry_id, recalled, merged_path, plan=plan_data)
    if ok and structural_file and structural_file.is_file():
        a_text = _load_body_field(structural_file, "结构顺译")
        ok2, errs2 = verify_style_retains_structural(a_text, combined)
        if not ok2:
            return False, errs2
    return ok, errs


def run_phase_a(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    structural_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str]]:
    return _run_phase_a_or_b(
        entry_id,
        recalled,
        plan_data=plan_data,
        work_dir=work_dir,
        session_id=session_id,
        phase="A",
        merged_path=structural_file,
        merged_field="结构顺译",
        load_field="结构顺译",
    )


def run_phase_b(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    structural_file: Path,
    mother_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str]]:
    if not _load_body_field(structural_file, "结构顺译"):
        return False, ["缺少 A 阶段结构顺译"]
    return _run_phase_a_or_b(
        entry_id,
        recalled,
        plan_data=plan_data,
        work_dir=work_dir,
        session_id=session_id,
        phase="B",
        merged_path=mother_file,
        merged_field="母本顺译",
        load_field="母本顺译",
        structural_file=structural_file,
    )


def run_phase_ab_merged(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str]]:
    """短篇：AB 合并一次落盘 mother.json。"""
    from lib.openclaw import build_translate_ab_merged_prompt

    plan_json = plan_json_for_phase_a(plan_data)
    max_retries = _phase_b_max_retries()
    errs: List[str] = []
    for attempt in range(max_retries + 1):
        retry_note = ""
        if attempt > 0 and errs:
            fb = classify_translate_failure(errs, stage="phase1", fail_count=attempt)
            retry_note = (
                "\n\n--- 上轮 AB 质检失败，须修正 ---\n"
                + format_retry_feedback(fb, errs)
            )
        prompt = build_translate_ab_merged_prompt(
            entry_id,
            recalled,
            recalled_summary(recalled),
            plan_json,
            mother_file,
        ) + retry_note
        print(
            f"⏳ AB 合并 {entry_id} → {mother_file.name}"
            + (f"（重试 {attempt}/{max_retries}）" if attempt else ""),
            flush=True,
        )
        _llm_turn(
            work_dir,
            entry_id,
            "ab",
            prompt,
            session_id=f"{session_id}-ab-r{attempt}",
            output_path=mother_file,
        )
        if not mother_file.is_file():
            errs = ["AB: LLM 未落盘"]
            continue
        if polish_mother_file(mother_file):
            print("   🔧 已校正 AB 阶段引号形态", flush=True)
        ok, errs = verify_mother_draft(entry_id, recalled, mother_file, plan=plan_data)
        if ok:
            return True, []
        print(f"⚠️ AB 未通过: {errs[0] if errs else '?'}", flush=True)
    return False, [f"AB: {e}" for e in errs]


def _parse_c_parts(data: Dict[str, Any]) -> Tuple[str, str]:
    """从 C 阶段落盘 JSON 提取前置引入/结尾（兼容字段漂移）。"""
    intro = str(data.get("前置引入") or "").strip()
    tail = str(data.get("结尾") or "").strip()
    if intro and tail:
        return intro, tail

    nested = data.get("翻译详情")
    candidates: List[Any] = []
    if isinstance(nested, dict):
        candidates.append(nested)
    elif isinstance(nested, str):
        text = nested.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        if text.startswith("{"):
            try:
                candidates.append(json.loads(text))
            except json.JSONDecodeError:
                pass
    for inner in candidates:
        if not isinstance(inner, dict):
            continue
        intro = intro or str(inner.get("前置引入") or "").strip()
        tail = tail or str(inner.get("结尾") or "").strip()
        if intro and tail:
            break
    return intro, tail


def run_phase_c(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_file: Path,
    baseline_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str]]:
    styled_body = _load_body_field(mother_file, "母本顺译")
    if not styled_body:
        return False, ["缺少 B 阶段母本顺译"]
    plan_json = plan_json_for_phase_a(plan_data)
    c_parts_file = baseline_file.with_suffix(".c-parts.json")
    errs: List[str] = []

    if c_parts_file.is_file():
        try:
            cached = json.loads(c_parts_file.read_text(encoding="utf-8"))
            intro, tail = _parse_c_parts(cached)
            if intro and tail:
                write_baseline_file(
                    baseline_file,
                    entry_id,
                    intro=intro,
                    body=styled_body,
                    tail=tail,
                    plan_data=plan_data,
                    recalled=recalled,
                )
                ok, errs = verify_baseline_draft(
                    entry_id, recalled, baseline_file, plan=plan_data, mother_body=styled_body
                )
                if ok:
                    print(f"⏭️ C 沿用已有 {c_parts_file.name}", flush=True)
                    return True, []
        except json.JSONDecodeError:
            pass

    for attempt in range(_phase_c_max_retries() + 1):
        retry_note = ""
        if attempt > 0 and errs:
            fb = classify_translate_failure(errs, stage="phase_c", fail_count=attempt)
            retry_note = (
                "\n\n--- 上轮 C 质检失败，须修正 ---\n"
                + format_retry_feedback(fb, errs)
            )
        prompt = build_translate_assemble_prompt(
            entry_id,
            recalled,
            recalled_summary(recalled),
            plan_json,
            styled_body,
            c_parts_file,
        ) + retry_note
        print(
            f"⏳ C 写引入+结尾 {entry_id}"
            + (f"（重试 {attempt}/{_phase_c_max_retries()}）" if attempt else ""),
            flush=True,
        )
        _llm_turn(
            work_dir,
            entry_id,
            "assemble",
            prompt,
            session_id=f"{session_id}-c-r{attempt}",
            output_path=c_parts_file,
        )
        if not c_parts_file.is_file():
            errs = ["C: LLM 未落盘"]
            continue
        data = json.loads(c_parts_file.read_text(encoding="utf-8"))
        intro, tail = _parse_c_parts(data)
        if not intro or not tail:
            errs = ["C: 缺少前置引入或结尾"]
            continue
        write_baseline_file(
            baseline_file,
            entry_id,
            intro=intro,
            body=styled_body,
            tail=tail,
            plan_data=plan_data,
            recalled=recalled,
        )
        ok, errs = verify_baseline_draft(
            entry_id, recalled, baseline_file, plan=plan_data, mother_body=styled_body
        )
        if ok:
            return True, []
        print(f"⚠️ C 未通过: {errs[0] if errs else '?'}", flush=True)
    return False, [f"C: {e}" for e in errs]


def run_abcd_baseline(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_file: Path,
    work_dir: Path,
    entry_name: str,
    session_id: str,
    use_llm: bool = True,
    from_phase: str | None = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """A→B→C 产出 baseline_ready。"""
    ok, plan_data, errs = ensure_coverage_ledger(entry_id, recalled, plan_file)
    if not ok:
        return False, errs, {}

    structural_file = structural_draft_path(entry_id, entry_name, work_dir)
    mother_file = mother_draft_path(entry_id, entry_name, work_dir)
    baseline_file = baseline_draft_path(entry_id, entry_name, work_dir)

    split_ab = ab_split_required(recalled, plan_data)
    if split_ab:
        print(f"📐 长文模式：A/B 拆分（M>{os.environ.get('TRANSLATE_AB_SPLIT_M', '15')} 或超字符阈值）", flush=True)
    else:
        print("📐 短篇模式：AB 合并为单次调用", flush=True)

    fp = from_phase or ""
    skip_a = fp in ("phase_b", "phase_c", "phase_d", "phase2")
    skip_b = fp in ("phase_c", "phase_d", "phase2")
    skip_c = fp in ("phase_d", "phase2")

    if not skip_a and not skip_b:
        if not use_llm:
            return False, ["ABCD 需要 LLM"], plan_data
        if split_ab:
            a_ok, a_errs = run_phase_a(
                entry_id, recalled, plan_data=plan_data,
                structural_file=structural_file, work_dir=work_dir, session_id=session_id,
            )
            if not a_ok:
                return False, a_errs, plan_data
            b_ok, b_errs = run_phase_b(
                entry_id, recalled, plan_data=plan_data,
                structural_file=structural_file, mother_file=mother_file,
                work_dir=work_dir, session_id=session_id,
            )
            if not b_ok:
                return False, b_errs, plan_data
        else:
            ab_ok, ab_errs = run_phase_ab_merged(
                entry_id, recalled, plan_data=plan_data,
                mother_file=mother_file, work_dir=work_dir, session_id=session_id,
            )
            if not ab_ok:
                return False, ab_errs, plan_data
    elif skip_a and not skip_b:
        if not use_llm:
            return False, ["B 阶段需要 LLM"], plan_data
        if not structural_file.is_file():
            return False, ["缺少 A 阶段结构顺译，无法跑 B"], plan_data
        b_ok, b_errs = run_phase_b(
            entry_id, recalled, plan_data=plan_data,
            structural_file=structural_file, mother_file=mother_file,
            work_dir=work_dir, session_id=session_id,
        )
        if not b_ok:
            return False, b_errs, plan_data
    elif skip_b and not mother_file.is_file():
        return False, ["缺少 B/AB 母本顺译"], plan_data

    if not skip_c:
        if not use_llm:
            return False, ["ABCD C 阶段需要 LLM"], plan_data
        c_ok, c_errs = run_phase_c(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_file=mother_file,
            baseline_file=baseline_file,
            work_dir=work_dir,
            session_id=session_id,
        )
        if not c_ok:
            return False, c_errs, plan_data
    elif not baseline_file.is_file():
        return False, ["缺少 C 阶段 baseline 成稿"], plan_data

    ok, errs = verify_baseline_draft(
        entry_id,
        recalled,
        baseline_file,
        plan=plan_data,
        mother_body=_load_body_field(mother_file, "母本顺译"),
    )
    if not ok:
        return False, errs, plan_data
    print(f"✅ baseline_ready {entry_id} → {baseline_file.name}", flush=True)
    return True, ["baseline_ready"], plan_data


def baseline_body_for_enrich(baseline_file: Path) -> str:
    _, _, _, detail = load_baseline_parts(baseline_file)
    return detail
