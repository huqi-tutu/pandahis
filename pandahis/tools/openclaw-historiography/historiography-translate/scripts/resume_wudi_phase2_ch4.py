#!/usr/bin/env python3
"""Resume 汉武帝 Phase2 from chapter 4 (reuse fixed ch01–ch03; quote autofix on)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_TRANSLATE_ROOT = Path(__file__).resolve().parent.parent
_OPENCLAW_ROOT = _TRANSLATE_ROOT.parent
sys.path.insert(0, str(_TRANSLATE_ROOT))
sys.path.insert(0, str(_OPENCLAW_ROOT))

from shared.qa_repair import classify_translate_failure, format_retry_feedback  # noqa: E402
from lib.config import load_dotenv, resolve_output_dir  # noqa: E402
from lib.phase2_batch import (  # noqa: E402
    batch_checklist_items,
    build_chapter_enrich_prompt,
    classic_quote_must_embed_note,
    concatenate_mother_batch_texts,
    discover_mother_batches,
    extract_voice_sample,
    group_batches_into_chapters,
    merge_enrich_batches,
    plan_for_enrich_batch,
)
from lib.prose_sanitize import polish_enrich_file, polish_enrich_file_full  # noqa: E402
from lib.recall import recall_entry  # noqa: E402
from lib.runner import (  # noqa: E402
    _load_mother_text,
    _llm_turn,
    _phase2_max_retries,
    _phase2_temperature,
    _rebuild_output_references,
    _repair_feedback_suffix,
    _try_enrich_landing_patch,
    _verify_enrich_with_autofix,
    attach_source_original,
    touch_heartbeat,
)
from lib.verify import verify_enrich_batch_slice  # noqa: E402

START_FROM = 4  # 1-based chapter index


def main() -> int:
    load_dotenv()
    os.environ.setdefault("HIST_LLM_PROVIDER", "deepseek")
    os.environ.setdefault("TRANSLATE_PHASE2_TEMPERATURE", "0.55")
    os.environ["TRANSLATE_AUTO_SYNC"] = "0"

    hist = Path(os.environ["HISTOGRAPH_ROOT"])
    work = hist / "data/05工作流中间产物/翻译"
    idx = hist / "data/10新标注条目/史略索引_史记汉书.json"
    out_dir = resolve_output_dir(index_path=idx)
    entry_id = "GLBL_00084"
    entry_name = "汉武帝"
    plan = json.loads((work / f"{entry_id}_{entry_name}.plan.json").read_text(encoding="utf-8"))
    recalled = recall_entry(entry_id, index_path=idx)
    mother_file = work / f"{entry_id}_{entry_name}.mother.json"
    target = out_dir / f"{entry_id}_{entry_name}.json"
    session_id = "tr-glbl-00084-p2-resume-ch4"

    batch_files = discover_mother_batches(mother_file)
    chapters = group_batches_into_chapters(batch_files)
    total = len(chapters)
    print(f"resume Phase2 from ch{START_FROM}: {total} chapters", flush=True)

    parts: list[str] = []
    for ci in range(1, START_FROM):
        ch = mother_file.with_name(f"{mother_file.stem}-ch{ci:02d}.enrich.json")
        if not ch.is_file():
            print(f"missing ch{ci:02d}", flush=True)
            return 2
        parts.append(_load_mother_text(ch))
    voice_sample = extract_voice_sample(parts[-1]) if parts else ""

    for ci in range(START_FROM, total + 1):
        chapter_batches = chapters[ci - 1]
        batch_nos = [int(p.stem.rsplit("-b", 1)[-1]) for p in chapter_batches]
        chapter_mother = concatenate_mother_batch_texts(chapter_batches)
        chapter_target = mother_file.with_name(f"{mother_file.stem}-ch{ci:02d}.enrich.json")
        if chapter_target.exists():
            chapter_target.unlink()
        label = f"第 {ci}/{total} 章（b{batch_nos[0]:02d}–b{batch_nos[-1]:02d}）"
        chapter_ok = False
        chapter_errs: list[str] = []
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
                        f"本章母本首段起句供核对：{head}…"
                    )
                if any("经典引用候选" in e or "直角「」" in e for e in chapter_errs):
                    _c_items = []
                    for bn in batch_nos:
                        _c_items.extend(batch_checklist_items(plan, bn))
                    retry_note += classic_quote_must_embed_note(_c_items)
            prompt = (
                build_chapter_enrich_prompt(
                    entry_id,
                    recalled,
                    plan,
                    chapter_mother,
                    chapter_target,
                    chapter_no=ci,
                    total_chapters=total,
                    batch_nos=batch_nos,
                    include_intro=False,
                    voice_sample=voice_sample,
                )
                + retry_note
                + _repair_feedback_suffix()
            )
            print(
                f"⏳ {label} → {chapter_target.name}"
                + (f"（重试 {attempt}/{_phase2_max_retries()}）" if attempt else ""),
                flush=True,
            )
            under_rw = any("誊抄" in e or "重合" in e for e in (chapter_errs or []))
            _llm_turn(
                work,
                entry_id,
                "enrich",
                prompt,
                session_id=f"{session_id}-ch{ci}-r{attempt}",
                timeout_sec=900,
                artifact_paths={"output": chapter_target},
                temperature=_phase2_temperature(
                    attempt=attempt, under_rewrite=under_rw or attempt == 0
                ),
            )
            if not chapter_target.is_file():
                chapter_errs = [f"{label}: 未落盘"]
                continue
            polish_enrich_file(chapter_target)
            from lib.citation_mode import apply_quote_style_fixes_to_file

            q_changes = apply_quote_style_fixes_to_file(chapter_target, plan)
            if q_changes:
                print(f"   🔧 引号风格: {', '.join(q_changes)}", flush=True)
            ch_items = []
            for bn in batch_nos:
                ch_items.extend(batch_checklist_items(plan, bn))
            chapter_plan = plan_for_enrich_batch(plan, ch_items)
            slice_ok, slice_errs = verify_enrich_batch_slice(
                entry_id,
                recalled,
                chapter_target,
                batch_mother_text=chapter_mother,
                batch_label=label,
                plan=chapter_plan,
            )
            if not slice_ok:
                chapter_errs = slice_errs or [f"{label}: 质检未通过"]
                patched_ok, patched_errs = _try_enrich_landing_patch(
                    entry_id,
                    recalled,
                    chapter_target=chapter_target,
                    chapter_plan=chapter_plan,
                    chapter_mother=chapter_mother,
                    label=label,
                    session_id=f"{session_id}-ch{ci}-r{attempt}",
                    work_dir=work,
                    slice_errs=chapter_errs,
                )
                if patched_ok:
                    body = _load_mother_text(chapter_target)
                    parts.append(body)
                    voice_sample = extract_voice_sample(body)
                    chapter_ok = True
                    break
                if patched_errs:
                    chapter_errs = patched_errs
                print(f"⚠️ {label} 未通过: {chapter_errs[0]}", flush=True)
                continue
            body = _load_mother_text(chapter_target)
            parts.append(body)
            voice_sample = extract_voice_sample(body)
            chapter_ok = True
            break
        if not chapter_ok:
            print("FAIL", label, chapter_errs[:3], flush=True)
            return 3

    combined = merge_enrich_batches(entry_id, parts, plan, recalled)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"史略ID": entry_id, "翻译详情": combined}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    polish_enrich_file_full(target)
    _rebuild_output_references(target, recalled, plan)
    attach_source_original(target, recalled)
    # mother.json 可能仅有批文件；终检用全批拼接
    mother_full = concatenate_mother_batch_texts(batch_files) or _load_mother_text(mother_file)
    e_ok, e_errs = _verify_enrich_with_autofix(
        entry_id, recalled, target, plan, mother_text=mother_full
    )
    print(
        "final verify",
        e_ok,
        e_errs[:5] if e_errs else [],
        "chars",
        len(combined),
        flush=True,
    )
    touch_heartbeat(work, entry_id, stage="done_enrich")
    return 0 if e_ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
