#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量修复 V2 顺译失败项：参考著作格式 / 王莽·刘歆人工通过 / 薄史料转 compose。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = DATA / "05工作流中间产物"
T11 = DATA / "11新标注条目翻译"
TRANSLATE_WORK = WORK / "翻译"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
TRANSLATE = ROOT / "tools" / "openclaw-historiography" / "historiography-translate"

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(TRANSLATE))

from v2_detail_routing import (  # noqa: E402
    TRANSLATION_VERSION_V2,
    has_11,
    is_valid_v2_11_doc,
    load_v2,
    queue_row,
)

THIN_COMPOSE_IDS = frozenset({
    "GLBL_00029", "GLBL_00107", "GLBL_00111", "GLBL_00116",
    "GLBL_00120", "GLBL_00121", "GLBL_00127",
})
FORCE_PASS_IDS = frozenset({"GLBL_01104", "GLBL_00091"})


def fix_reference_in_detail(detail: str) -> str:
    from lib.prose_sanitize import fix_reference_section_format

    return fix_reference_section_format(detail)


def load_recall(entry_id: str) -> dict:
    from lib.recall import recall_entry

    return recall_entry(entry_id, index_path=V2_INDEX)


def finalize_11_file(fp: Path, entry_id: str, recalled: dict) -> bool:
    from lib.config import TRANSLATION_VERSION_V2
    from lib.source_text import attach_source_original

    doc = json.loads(fp.read_text(encoding="utf-8"))
    detail = fix_reference_in_detail(str(doc.get("翻译详情") or ""))
    if not detail.strip():
        return False
    doc["史略ID"] = entry_id
    doc["翻译详情"] = detail
    fp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attach_source_original(fp, recalled, translation_version=TRANSLATION_VERSION_V2)
    return is_valid_v2_11_doc(json.loads(fp.read_text(encoding="utf-8")))


def ref_format_failed_ids() -> list[str]:
    cp = json.loads((WORK / "v2_translate_checkpoint.json").read_text(encoding="utf-8"))
    out = []
    for f in cp.get("failed") or []:
        if f.get("error") != "exit=1":
            continue
        ticket = TRANSLATE_WORK / f"{f['史略ID']}.repair.json"
        if not ticket.is_file():
            continue
        errs = json.loads(ticket.read_text()).get("errors") or []
        if errs and "参考著作须独立成段" in errs[0]:
            out.append(f["史略ID"])
    return out


def fix_ref_format_batch() -> tuple[int, list[str]]:
    ok_ids: list[str] = []
    for eid in ref_format_failed_ids():
        files = [f for f in T11.glob(f"{eid}_*.json") if f.name != "翻译复用清单.json"]
        if not files:
            print(f"  ⚠️ {eid} 无 11 半成品，跳过")
            continue
        try:
            recalled = load_recall(eid)
        except Exception as exc:
            print(f"  ❌ {eid} recall 失败: {exc}")
            continue
        if finalize_11_file(files[0], eid, recalled):
            ok_ids.append(eid)
            print(f"  ✅ {eid} 参考著作格式已修复")
        else:
            print(f"  ❌ {eid} 修复后仍无效")
    return len(ok_ids), ok_ids


def merge_wang_mang() -> bool:
    eid = "GLBL_00091"
    name = "王莽"
    enrich_files = sorted(TRANSLATE_WORK.glob(f"{eid}_{name}.mother-b*.enrich.json"))
    if len(enrich_files) < 50:
        print(f"  ❌ {eid} enrich 批次数不足: {len(enrich_files)}")
        return False
    parts = []
    for fp in enrich_files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        t = str(doc.get("翻译详情") or "").strip()
        if t:
            parts.append(t)
    from lib.phase2_batch import append_reference_section
    from lib.work_artifacts import load_normalized_plan, plan_path

    recalled = load_recall(eid)
    pf = plan_path(eid, name, TRANSLATE_WORK)
    _, plan_data, _ = load_normalized_plan(pf, recalled)
    detail = append_reference_section("\n\n".join(parts), plan_data, recalled)
    detail = fix_reference_in_detail(detail)

    out = T11 / f"{eid}_{name}.json"
    out.write_text(
        json.dumps({"史略ID": eid, "翻译详情": detail}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    from lib.source_text import attach_source_original

    attach_source_original(out, recalled, translation_version=TRANSLATION_VERSION_V2)
    ok = is_valid_v2_11_doc(json.loads(out.read_text(encoding="utf-8")))
    print(f"  {'✅' if ok else '❌'} {eid} 王莽合并 {len(parts)} 批 → {out.name}")
    return ok


def force_pass_liuxin_from_mother() -> bool:
    """刘歆：用户核准直接通过，用 Phase1 母本 + 参考著作落盘（跳过引号质检）。"""
    import re

    eid = "GLBL_01104"
    name = "刘歆"
    mother_fp = TRANSLATE_WORK / f"{eid}_{name}.mother.json"
    if not mother_fp.is_file():
        print(f"  ❌ {eid} 缺少 mother.json")
        return False
    from lib.prose_sanitize import sanitize_mother_detail
    from lib.phase2_batch import append_reference_section
    from lib.work_artifacts import load_normalized_plan, plan_path
    from lib.source_text import attach_source_original
    from lib.config import TRANSLATION_VERSION_V2

    raw = json.loads(mother_fp.read_text(encoding="utf-8")).get("母本顺译") or ""
    body = sanitize_mother_detail(str(raw))
    body = re.sub(r"^M\d{3}\s*\n?", "", body, flags=re.M)
    body = re.sub(r"\nM\d{3}\s*\n", "\n", body)
    body = re.sub(r"MOTHER_DRAFT_DONE[^\n]*\n?", "", body)
    body = body.strip()

    recalled = load_recall(eid)
    pf = plan_path(eid, name, TRANSLATE_WORK)
    _, plan_data, _ = load_normalized_plan(pf, recalled)
    detail = append_reference_section(body, plan_data, recalled)
    detail = fix_reference_in_detail(detail)

    out = T11 / f"{eid}_{name}.json"
    out.write_text(
        json.dumps({"史略ID": eid, "翻译详情": detail}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    attach_source_original(out, recalled, translation_version=TRANSLATION_VERSION_V2)
    ok = is_valid_v2_11_doc(json.loads(out.read_text(encoding="utf-8")))
    print(f"  {'✅' if ok else '❌'} {eid} 刘歆母本直出 → {out.name}")
    return ok


def run_liuxin_phase2() -> bool:
    eid = "GLBL_01104"
    print(f"  ⏳ {eid} 刘歆 Phase2 补全…")
    proc = subprocess.run(
        [
            sys.executable,
            str(TRANSLATE / "translate.py"),
            "run-one",
            "--id",
            eid,
            "--index",
            str(V2_INDEX),
            "--output-dir",
            str(T11),
            "--from-phase",
            "phase2",
        ],
        cwd=str(TRANSLATE),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and not list(T11.glob(f"{eid}_*.json")):
        print(f"  ❌ {eid} Phase2 失败 exit={proc.returncode}")
        print(proc.stdout[-800:] if proc.stdout else proc.stderr[-800:])
        return False
    files = list(T11.glob(f"{eid}_*.json"))
    if not files:
        return False
    recalled = load_recall(eid)
    ok = finalize_11_file(files[0], eid, recalled)
    print(f"  {'✅' if ok else '❌'} {eid} 刘歆 {'已通过' if ok else '仍无效'}")
    return ok


def add_thin_to_compose_queue() -> int:
    compose_path = WORK / "v2_compose_queue.json"
    queue = json.loads(compose_path.read_text(encoding="utf-8"))
    existing = {r["史略ID"] for r in queue}
    index = {e["史略ID"]: e for e in load_v2()}
    added = 0
    for eid in sorted(THIN_COMPOSE_IDS):
        if eid in existing:
            continue
        entry = index.get(eid)
        if not entry:
            continue
        queue.append(queue_row(entry, "compose"))
        added += 1
    if added:
        queue.sort(key=lambda r: (str(r.get("二级朝代坐标") or ""), str(r.get("史略ID") or "")))
        compose_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def update_checkpoints(fixed_ids: list[str], compose_ids: list[str]) -> None:
    cp_path = WORK / "v2_translate_checkpoint.json"
    cp = json.loads(cp_path.read_text(encoding="utf-8"))
    done = set(cp.get("done") or [])
    failed = cp.get("failed") or []
    routed = set(cp.get("routed_to_compose") or [])

    fixed_set = set(fixed_ids)
    compose_set = set(compose_ids)
    new_failed = []
    for f in failed:
        eid = f["史略ID"]
        if eid in fixed_set or eid in compose_set:
            if eid in fixed_set:
                done.add(eid)
            if eid in compose_set:
                routed.add(eid)
            continue
        new_failed.append(f)

    cp["done"] = sorted(done)
    cp["failed"] = new_failed
    cp["routed_to_compose"] = sorted(routed)
    cp["updated_at"] = datetime.now(timezone.utc).isoformat()
    cp_path.write_text(json.dumps(cp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-liuxin-phase2", action="store_true", help="跳过刘歆 Phase2（仅合并王莽等）")
    args = parser.parse_args()

    print("1/4 修复参考著作格式…")
    n_ref, ref_ok = fix_ref_format_batch()
    print(f"   → {n_ref}/{len(ref_format_failed_ids())} 条")

    print("2/4 王莽直接通过（合并 enrich）…")
    wang_ok = merge_wang_mang()

    print("3/4 刘歆直接通过…")
    liu_ok = force_pass_liuxin_from_mother()

    fixed = list(ref_ok)
    if wang_ok:
        fixed.append("GLBL_00091")
    if liu_ok:
        fixed.append("GLBL_01104")

    print("4/4 薄史料 7 条加入 compose 队列…")
    added = add_thin_to_compose_queue()
    print(f"   → 新增 {added} 条（共路由 {len(THIN_COMPOSE_IDS)} 条）")

    update_checkpoints(fixed, sorted(THIN_COMPOSE_IDS))

    valid = sum(1 for e in load_v2() if str(e.get("史略ID", "")) in {
        r["史略ID"] for r in json.loads((WORK / "v2_translate_queue.json").read_text())
    } and has_11(str(e["史略ID"])))
    # recount from translate queue
    tq = json.loads((WORK / "v2_translate_queue.json").read_text())
    valid_t = sum(1 for r in tq if has_11(r["史略ID"]))
    print(f"\n完成：参考著作 {n_ref} | 王莽 {'✅' if wang_ok else '❌'} | 刘歆 {'✅' if liu_ok else '❌'} | compose +{added}")
    print(f"顺译队列有效 v2：{valid_t}/129")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
