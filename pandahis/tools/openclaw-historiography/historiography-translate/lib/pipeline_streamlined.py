"""精简四步流水线：Ledger(M) → 分批成稿 → 引入/结尾 → 终检。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.baseline_assemble import assemble_baseline_detail
from lib.batch_continuity import build_continuity_prompt_block
from lib.batch_split import batched_mother_checklist
from lib.coverage_plan import ensure_coverage_ledger
from lib.draft_parse import extract_draft_body
from lib.openclaw import (
    build_batch_draft_prompt,
    build_ending_prompt,
    build_intro_prompt,
    run_agent_turn,
)
from lib.plan_batch_filter import batch_plan_json_for_prompt
from lib.prose_sanitize import polish_mother_file
from lib.stall_watch import touch_heartbeat
from lib.verify import verify_assemble_parts, verify_mother_draft

from lib.work_artifacts import mother_draft_path
from shared.qa_repair import classify_translate_failure, format_retry_feedback


def streamlined_pipeline_enabled() -> bool:
    mode = os.environ.get("TRANSLATE_PIPELINE", "streamlined").strip().lower()
    if mode in ("abcd", "legacy"):
        return False
    if os.environ.get("TRANSLATE_ABCD_PIPELINE", "0") == "1" and mode == "abcd":
        return False
    return os.environ.get("TRANSLATE_TWO_PHASE", "1") != "0"


def _batch_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_BATCH_MAX_RETRIES", "2")))


def _assemble_max_retries() -> int:
    return max(0, int(os.environ.get("TRANSLATE_ASSEMBLE_MAX_RETRIES", "2")))


def _llm_turn(
    work_dir: Path,
    entry_id: str,
    stage: str,
    prompt: str,
    *,
    session_id: str,
    output_path: Path,
) -> None:
    touch_heartbeat(work_dir, entry_id, stage=f"llm_{stage}")
    run_agent_turn(
        prompt,
        session_id=session_id,
        timeout_sec=int(os.environ.get("TRANSLATE_LLM_TIMEOUT", "900")),
        artifact_paths={"output": output_path},
    )
    touch_heartbeat(work_dir, entry_id, stage=f"done_{stage}")


def ensure_expansive_plan(
    entry_id: str,
    recalled: Dict[str, Any],
    plan_file: Path,
    *,
    work_dir: Path,
    session_id: str,
    use_llm: bool = True,
    force: bool = False,
) -> Tuple[bool, Dict[str, Any], List[str]]:
    """程序 coverage ledger（M 清单）；补全他书在分批成稿阶段由提示词驱动，不再 LLM plan。"""
    del work_dir, session_id, use_llm, force  # 保留签名兼容旧调用
    ok, ledger, errs = ensure_coverage_ledger(entry_id, recalled, plan_file)
    if ok:
        print(f"📋 coverage ledger（M 清单）→ {plan_file.name}", flush=True)
    return ok, ledger, errs


def _parse_field(data: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = str(data.get(k) or "").strip()
        if v:
            return v
    nested_raw = data.get("翻译详情")
    inners: List[Dict[str, Any]] = []
    if isinstance(nested_raw, dict):
        inners.append(nested_raw)
    elif isinstance(nested_raw, str):
        text = nested_raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        if text.startswith("{"):
            try:
                inners.append(json.loads(text))
            except json.JSONDecodeError:
                pass
    for inner in inners:
        for k in keys:
            v = str(inner.get(k) or "").strip()
            if v:
                return v
    return ""


def _parse_assemble_parts(data: Dict[str, Any]) -> Tuple[str, str]:
    intro = _parse_field(data, "前置引入")
    tail = _parse_field(data, "结尾", "总结")
    return intro, tail


def _llm_write_part(
    *,
    entry_id: str,
    work_dir: Path,
    session_id: str,
    stage: str,
    label: str,
    output_path: Path,
    prompt: str,
    field_keys: Tuple[str, ...],
    verify_fn,
) -> Tuple[bool, List[str], str]:
    """单字段 LLM 落盘（引入或结尾）。"""
    max_retries = _assemble_max_retries()
    errs: List[str] = []
    text = ""
    for attempt in range(max_retries + 1):
        retry_note = ""
        if attempt > 0 and errs:
            fb = classify_translate_failure(errs, stage="assemble", fail_count=attempt)
            retry_note = (
                "\n\n--- 上轮质检失败，须修正 ---\n"
                + format_retry_feedback(fb, errs)
            )
        print(
            f"⏳ {label} {entry_id}"
            + (f"（重试 {attempt}/{max_retries}）" if attempt else ""),
            flush=True,
        )
        if output_path.is_file():
            output_path.unlink()
        _llm_turn(
            work_dir,
            entry_id,
            stage,
            prompt + retry_note,
            session_id=f"{session_id}-{stage}-r{attempt}",
            output_path=output_path,
        )
        if not output_path.is_file():
            errs = [f"{label}: LLM 未落盘"]
            continue
        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errs = [f"{label}: JSON 解析失败: {exc}"]
            continue
        text = _parse_field(data, *field_keys)
        ok, errs = verify_fn(text)
        if ok:
            return True, [], text
        print(f"⚠️ {label}未通过: {errs[0] if errs else '?'}", flush=True)
    return False, [f"{label}: {e}" for e in errs], ""


def run_final_assemble(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    body: str,
    plan_data: Dict[str, Any],
    assemble_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str], str, str, str]:
    """两次短 LLM：引入 → 结尾；程序拼接正文。不用 plan 前置素材、不灌规则包。"""
    from lib.verify import verify_assemble_parts, verify_ending_only, verify_intro_only

    intro_path = assemble_file.with_name(
        assemble_file.name.replace(".assemble.json", ".intro.json")
        if assemble_file.name.endswith(".assemble.json")
        else f"{assemble_file.stem}.intro.json"
    )
    ending_path = assemble_file.with_name(
        assemble_file.name.replace(".assemble.json", ".ending.json")
        if assemble_file.name.endswith(".assemble.json")
        else f"{assemble_file.stem}.ending.json"
    )

    ok_i, errs_i, intro = _llm_write_part(
        entry_id=entry_id,
        work_dir=work_dir,
        session_id=session_id,
        stage="intro",
        label="前置引入",
        output_path=intro_path,
        prompt=build_intro_prompt(entry_id, recalled, intro_path),
        field_keys=("前置引入",),
        verify_fn=verify_intro_only,
    )
    if not ok_i:
        return False, errs_i, "", "", ""

    ok_e, errs_e, tail = _llm_write_part(
        entry_id=entry_id,
        work_dir=work_dir,
        session_id=session_id,
        stage="ending",
        label="篇末结尾",
        output_path=ending_path,
        prompt=build_ending_prompt(entry_id, recalled, body, ending_path),
        field_keys=("结尾", "总结"),
        verify_fn=verify_ending_only,
    )
    if not ok_e:
        return False, errs_e, intro, "", ""

    ok, errs = verify_assemble_parts(intro, tail)
    if not ok:
        return False, [f"装配: {e}" for e in errs], intro, tail, ""

    # 合并中间产物，便于审计
    assemble_file.parent.mkdir(parents=True, exist_ok=True)
    assemble_file.write_text(
        json.dumps(
            {"史略ID": entry_id, "前置引入": intro, "结尾": tail},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    detail = assemble_baseline_detail(
        intro=intro,
        body=body,
        tail=tail,
        plan_data=plan_data,
        recalled=recalled,
    )
    return True, [], intro, tail, detail


def run_batch_drafts(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_data: Dict[str, Any],
    mother_file: Path,
    work_dir: Path,
    session_id: str,
) -> Tuple[bool, List[str], str]:
    batches = batched_mother_checklist(plan_data)
    full_checklist = plan_data.get("母本逐句清单") or []
    parts: List[str] = []
    max_retries = _batch_max_retries()

    if len(batches) > 1:
        print(f"📦 分批成稿 {entry_id}：{len(batches)} 批", flush=True)

    for bi, batch_items in enumerate(batches, start=1):
        batch_path = mother_file.with_name(f"{mother_file.stem}-b{bi:02d}{mother_file.suffix}")
        sid0 = batch_items[0].get("编号") if batch_items else "?"
        sid1 = batch_items[-1].get("编号") if batch_items else "?"
        label = f"成稿 第 {bi}/{len(batches)} 批（{sid0}–{sid1}）"
        batch_plan_json = batch_plan_json_for_prompt(
            plan_data,
            batch_items,
            batch_index=bi,
            batch_total=len(batches),
        )
        prev_body = parts[-1] if bi > 1 and parts else ""
        continuity = build_continuity_prompt_block(
            batch_index=bi,
            batch_total=len(batches),
            batch_items=batch_items,
            full_checklist=full_checklist if isinstance(full_checklist, list) else [],
            prev_body=prev_body,
        )

        errs: List[str] = []
        for attempt in range(max_retries + 1):
            retry_note = ""
            if attempt > 0 and errs:
                fb = classify_translate_failure(errs, stage="phase1", fail_count=attempt)
                retry_note = (
                    "\n\n--- 上轮质检失败，须修正 ---\n"
                    + format_retry_feedback(fb, errs)
                )
            prompt = build_batch_draft_prompt(
                entry_id,
                recalled,
                batch_items,
                batch_plan_json,
                batch_path,
                continuity_block=continuity,
            )
            prompt += retry_note
            print(label + (f"（重试 {attempt}/{max_retries}）" if attempt else ""), flush=True)
            _llm_turn(
                work_dir,
                entry_id,
                f"batch-{bi}",
                prompt,
                session_id=f"{session_id}-b{bi}-r{attempt}",
                output_path=batch_path,
            )
            if not batch_path.is_file():
                errs = [f"{label}: LLM 未落盘"]
                continue
            if polish_mother_file(batch_path):
                print("   🔧 已校正批内引号形态", flush=True)
            verify_plan = {"母本逐句清单": batch_items}
            ok, errs = verify_mother_draft(
                entry_id,
                recalled,
                batch_path,
                plan=verify_plan,
                batch_mode=True,
                batch_label=label,
            )
            if ok:
                body = extract_draft_body(
                    json.loads(batch_path.read_text(encoding="utf-8")),
                    "母本顺译",
                    "翻译详情",
                )
                parts.append(body.strip())
                break
            print(f"⚠️ {label} 未通过: {errs[0] if errs else '?'}", flush=True)
        else:
            return False, [f"{label}: {e}" for e in errs], ""

    combined = "\n\n".join(p for p in parts if p)
    mother_file.parent.mkdir(parents=True, exist_ok=True)
    mother_file.write_text(
        json.dumps(
            {"史略ID": entry_id, "母本顺译": combined},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return True, [], combined


def run_streamlined_pipeline(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    plan_file: Path,
    target: Path,
    work_dir: Path,
    entry_name: str,
    session_id: str,
    use_llm: bool = True,
    from_phase: str | None = None,
) -> Tuple[bool, List[str]]:
    """四步：ledger → 分批成稿 → 引入/结尾 → 落盘 target。"""
    if not use_llm:
        return False, ["精简流水线需要 LLM"]

    fp = (from_phase or "").strip().lower()
    mother_file = mother_draft_path(entry_id, entry_name, work_dir)
    # mother.json → assemble.json（勿用 with_suffix，否则变成 mother.assemble.json）
    assemble_file = mother_file.with_name(
        mother_file.name.replace(".mother.json", ".assemble.json")
        if mother_file.name.endswith(".mother.json")
        else f"{mother_file.stem}.assemble.json"
    )

    plan_ok, plan_data, plan_errs = ensure_expansive_plan(
        entry_id,
        recalled,
        plan_file,
        work_dir=work_dir,
        session_id=session_id,
        use_llm=fp not in ("batch", "draft", "assemble"),
        force=fp == "plan",
    )
    if not plan_ok:
        return False, plan_errs

    body = extract_draft_body(
        json.loads(mother_file.read_text(encoding="utf-8")),
        "母本顺译",
        "翻译详情",
    ) if mother_file.is_file() else ""

    if fp not in ("assemble",) and not body:
        ok, errs, body = run_batch_drafts(
            entry_id,
            recalled,
            plan_data=plan_data,
            mother_file=mother_file,
            work_dir=work_dir,
            session_id=session_id,
        )
        if not ok:
            return False, errs
    elif not body:
        return False, ["缺少分批成稿正文，无法装配"]

    ok, errs, _intro, _tail, detail = run_final_assemble(
        entry_id,
        recalled,
        body=body,
        plan_data=plan_data,
        assemble_file=assemble_file,
        work_dir=work_dir,
        session_id=session_id,
    )
    if not ok:
        return False, errs

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "史略ID": entry_id,
                "翻译详情": detail,
                "_pipeline_meta": {"mode": "streamlined", "status": "pending_review"},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"✅ {entry_id} 精简流水线成稿 {len(detail)} 字 → {target.name}", flush=True)
    return True, []
