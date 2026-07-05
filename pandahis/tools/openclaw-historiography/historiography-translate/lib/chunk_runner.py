"""分块翻译编排：plan → draft → merge。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lib.chunk_merge import (
    merge_chunk_bodies,
    merge_chunk_plans,
    write_final_output,
)
from lib.chunking import (
    ChunkSpec,
    chunk_body_path,
    chunk_plan_path,
    chunk_timeout_sec,
    ensure_manifest,
    manifest_path,
    needs_chunked_mode,
    read_previous_chunk_tail,
    slice_recalled_for_chunk,
    update_chunk_status,
)
from lib.fingerprint import recalled_summary
from lib.source_text import build_source_original
from lib.openclaw import (
    build_chunk_source_plan_prompt,
    build_chunk_translate_prompt,
    run_agent_turn,
)
from lib.verify import verify_chunk_body
from lib.work_artifacts import load_plan, plan_path, save_plan, verify_chunk_plan


def should_use_chunked_flow(recalled: Dict[str, Any]) -> bool:
    return needs_chunked_mode(recalled)


def _plan_json_text(path: Path) -> str:
    ok, data, _ = load_plan(path)
    if not ok:
        return "{}"
    return json.dumps(data, ensure_ascii=False, indent=2)


def _sentence_id_end(spec: ChunkSpec) -> int:
    return spec.sentence_id_start + max(spec.mother_sentence_count, 1) - 1


def ensure_chunk_plan(
    entry_id: str,
    recalled: Dict[str, Any],
    spec: ChunkSpec,
    work_dir: Path,
    entry_name: str,
    *,
    session_id: str,
    dry_run: bool = False,
    use_llm: bool = True,
) -> Tuple[bool, List[str]]:
    recalled_chunk = slice_recalled_for_chunk(recalled, spec)
    plan_file = chunk_plan_path(entry_id, entry_name, work_dir, spec.chunk_id)
    sid_end = _sentence_id_end(spec)

    ok, errors = verify_chunk_plan(
        entry_id,
        recalled_chunk,
        plan_file,
        sentence_id_start=spec.sentence_id_start,
        sentence_id_end=sid_end,
    )
    if ok:
        return True, []

    prompt = build_chunk_source_plan_prompt(
        entry_id,
        recalled_chunk,
        recalled_summary(recalled_chunk),
        plan_file,
        sentence_id_start=spec.sentence_id_start,
        sentence_id_end=sid_end,
        chunk_id=spec.chunk_id,
        chunk_total=spec.chunk_total,
    )
    if dry_run:
        print(
            f"   chunk-{spec.chunk_id:02d} plan prompt ≈{len(prompt)} 字符 → {plan_file}"
        )
        return False, errors

    if not use_llm:
        return False, errors

    timeout = chunk_timeout_sec(spec)
    print(
        f"   🧭 分块 {spec.chunk_id}/{spec.chunk_total} plan → {plan_file.name}",
        flush=True,
    )
    run_agent_turn(
        prompt,
        session_id=session_id,
        timeout_sec=timeout,
        artifact_paths={"plan": plan_file},
    )
    ok_load, plan_data, _ = load_plan(plan_file)
    if ok_load:
        save_plan(
            plan_file,
            plan_data,
            recalled_chunk,
            id_start=spec.sentence_id_start,
        )
    return verify_chunk_plan(
        entry_id,
        recalled_chunk,
        plan_file,
        sentence_id_start=spec.sentence_id_start,
        sentence_id_end=sid_end,
    )


def run_chunk_translate(
    entry_id: str,
    recalled: Dict[str, Any],
    spec: ChunkSpec,
    work_dir: Path,
    entry_name: str,
    *,
    session_id: str,
    dry_run: bool = False,
    use_llm: bool = True,
) -> Tuple[bool, List[str]]:
    recalled_chunk = slice_recalled_for_chunk(recalled, spec)
    plan_file = chunk_plan_path(entry_id, entry_name, work_dir, spec.chunk_id)
    body_file = chunk_body_path(entry_id, entry_name, work_dir, spec.chunk_id)

    ok, errors = verify_chunk_body(body_file, recalled_chunk)
    if ok:
        return True, []

    plan_ok, _, plan_errs = load_plan(plan_file)
    if not plan_ok:
        return False, plan_errs

    prev_tail = read_previous_chunk_tail(
        entry_id, entry_name, work_dir, spec.chunk_id
    )
    prompt = build_chunk_translate_prompt(
        entry_id,
        recalled_chunk,
        recalled_summary(recalled_chunk),
        _plan_json_text(plan_file),
        body_file,
        chunk_id=spec.chunk_id,
        chunk_total=spec.chunk_total,
        previous_tail=prev_tail,
    )
    if dry_run:
        print(
            f"   chunk-{spec.chunk_id:02d} draft prompt ≈{len(prompt)} 字符 → {body_file}"
        )
        return False, errors

    if not use_llm:
        return False, errors

    timeout = chunk_timeout_sec(spec)
    print(
        f"   ⏳ 分块 {spec.chunk_id}/{spec.chunk_total} 翻译 → {body_file.name}",
        flush=True,
    )
    run_agent_turn(
        prompt,
        session_id=session_id,
        timeout_sec=timeout,
        artifact_paths={"markdown": body_file},
    )
    return verify_chunk_body(body_file, recalled_chunk)


def run_chunked_pipeline(
    entry_id: str,
    recalled: Dict[str, Any],
    *,
    work_dir: Path,
    out_dir: Path,
    entry_name: str,
    target: Path,
    session_id: str,
    dry_run: bool = False,
    use_llm: bool = True,
) -> Tuple[bool, List[str]]:
    manifest, specs, rebuilt = ensure_manifest(recalled, work_dir, entry_name)
    mpath = manifest_path(entry_id, entry_name, work_dir)
    if rebuilt:
        print(
            f"📦 分块清单 {len(specs)} 块 "
            f"（约 {manifest.get('mother_sentence_count')} 母本句）"
        )
    elif manifest.get("chunked"):
        print(f"📦 续跑分块翻译 {len(specs)} 块")

    errors: List[str] = []
    t0 = time.time()

    for spec in specs:
        chunk_meta = next(
            (c for c in manifest.get("chunks") or [] if c.get("chunk_id") == spec.chunk_id),
            {},
        )
        status = str(chunk_meta.get("status") or "pending")
        if status == "done":
            print(f"   ⏭️ 分块 {spec.chunk_id}/{spec.chunk_total} 已完成")
            continue

        plan_ok, plan_errs = ensure_chunk_plan(
            entry_id,
            recalled,
            spec,
            work_dir,
            entry_name,
            session_id=f"{session_id}-c{spec.chunk_id:02d}-plan",
            dry_run=dry_run,
            use_llm=use_llm,
        )
        if not plan_ok:
            update_chunk_status(manifest, spec.chunk_id, "plan_failed", mpath)
            return False, plan_errs

        update_chunk_status(manifest, spec.chunk_id, "plan_done", mpath)

        if dry_run:
            run_chunk_translate(
                entry_id,
                recalled,
                spec,
                work_dir,
                entry_name,
                session_id=f"{session_id}-c{spec.chunk_id:02d}",
                dry_run=True,
                use_llm=False,
            )
            continue

        draft_ok, draft_errs = run_chunk_translate(
            entry_id,
            recalled,
            spec,
            work_dir,
            entry_name,
            session_id=f"{session_id}-c{spec.chunk_id:02d}",
            use_llm=use_llm,
        )
        if not draft_ok:
            update_chunk_status(manifest, spec.chunk_id, "failed", mpath)
            return False, draft_errs

        update_chunk_status(manifest, spec.chunk_id, "done", mpath)

    if dry_run:
        return False, ["dry-run: 分块未合并"]

    merged_plan, merge_plan_errs = merge_chunk_plans(
        entry_id, recalled, specs, work_dir, entry_name
    )
    if merge_plan_errs:
        return False, merge_plan_errs

    master_plan = plan_path(entry_id, entry_name, work_dir)
    master_plan.write_text(
        json.dumps(merged_plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    detail, merge_body_errs = merge_chunk_bodies(
        entry_id,
        entry_name,
        specs,
        work_dir,
        merged_plan.get("参考著作") or [],
    )
    if merge_body_errs:
        return False, merge_body_errs

    write_final_output(
        entry_id,
        detail,
        target,
        source_original=build_source_original(recalled),
    )
    elapsed = time.time() - t0
    print(f"🔗 分块合并完成 {len(detail)} 字 ({elapsed:.0f}s) → {target}")
    return True, []
