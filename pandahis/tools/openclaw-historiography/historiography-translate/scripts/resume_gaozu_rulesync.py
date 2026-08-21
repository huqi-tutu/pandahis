#!/usr/bin/env python3
"""Resume GLBL_00085 Phase1 from batch 4 (reuse b01–b03), then Phase2 via run-one."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TRANSLATE_ROOT = _HERE.parent
sys.path.insert(0, str(_TRANSLATE_ROOT))

from lib.config import load_dotenv, resolve_output_dir  # noqa: E402
from lib.coverage_info import build_coverage_units  # noqa: E402
from lib.coverage_ledger import clear_ledger_labels  # noqa: E402
from lib.longform_compat import join_narrative_parts  # noqa: E402
from lib.prose_sanitize import sanitize_mother_detail  # noqa: E402
from lib.recall import recall_entry  # noqa: E402
from lib.runner import (  # noqa: E402
    _load_mother_text,
    _run_phase1_mother_single,
    _write_mother_draft,
    touch_heartbeat,
)
from lib.verify import verify_mother_draft  # noqa: E402


def main() -> int:
    load_dotenv()
    os.environ.setdefault("HIST_LLM_PROVIDER", "deepseek")
    os.environ["TRANSLATE_AUTO_SYNC"] = "0"

    hist_root = Path(os.environ["HISTOGRAPH_ROOT"])
    work = hist_root / "data/05工作流中间产物/翻译"
    idx = hist_root / "data/10新标注条目/史略索引_史记汉书.json"
    entry_id = "GLBL_00085"
    plan = json.loads((work / "GLBL_00085_汉高祖.plan.json").read_text(encoding="utf-8"))
    recalled = recall_entry(entry_id, index_path=idx)
    checklist = plan.get("母本逐句清单") or []
    batch_size = max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))
    batches = [checklist[i : i + batch_size] for i in range(0, len(checklist), batch_size)]
    mother_file = work / "GLBL_00085_汉高祖.mother.json"
    session_base = "tr-glbl-00085-resume-rulesync"

    b04 = work / "GLBL_00085_汉高祖.mother-b04.json"
    if b04.exists():
        b04.unlink()
        print("removed broken b04", flush=True)

    labels = [u.label for u in build_coverage_units(checklist[3 * batch_size :])]
    clear_ledger_labels(work, entry_id, labels)
    print(f"cleared ledger labels from batch4 onward: {len(labels)}", flush=True)

    parts: list[str] = []
    for bi, batch_items in enumerate(batches, start=1):
        batch_file = mother_file.with_name(
            f"{mother_file.stem}-b{bi:02d}{mother_file.suffix}"
        )
        sid0 = batch_items[0].get("编号") if batch_items else "?"
        sid1 = batch_items[-1].get("编号") if batch_items else "?"
        label = f"第 {bi}/{len(batches)} 批（{sid0}–{sid1}）"
        if bi < 4 and batch_file.is_file():
            print(f"reuse {label}", flush=True)
            parts.append(_load_mother_text(batch_file))
            continue
        batch_plan = {**plan, "母本逐句清单": batch_items}
        ok, errs = _run_phase1_mother_single(
            entry_id,
            recalled,
            plan_data=batch_plan,
            mother_file=batch_file,
            work_dir=work,
            session_id=f"{session_base}-mother-b{bi}",
            batch_label=label,
        )
        if not ok:
            print("FAIL Phase1", label, errs[:3], flush=True)
            return 2
        parts.append(_load_mother_text(batch_file))

    combined = join_narrative_parts([p for p in parts if p.strip()])
    _write_mother_draft(mother_file, entry_id, sanitize_mother_detail(combined))
    touch_heartbeat(work, entry_id, stage="verify_mother")
    m_ok, m_errs = verify_mother_draft(entry_id, recalled, mother_file, plan=plan)
    print(
        "mother merge verify",
        m_ok,
        m_errs[:3] if m_errs else [],
        "chars",
        len(combined),
        flush=True,
    )
    if not m_ok:
        return 3

    print("=== Phase2 via run-one --from-phase phase2 ===", flush=True)
    out_dir = resolve_output_dir(index_path=idx)
    cmd = [
        sys.executable,
        "-u",
        str(_TRANSLATE_ROOT / "translate.py"),
        "run-one",
        "--id",
        entry_id,
        "--index",
        str(idx),
        "--output-dir",
        str(out_dir),
        "--from-phase",
        "phase2",
    ]
    env = os.environ.copy()
    env["HIST_LLM_PROVIDER"] = "deepseek"
    env["TRANSLATE_AUTO_SYNC"] = "0"
    rc = subprocess.call(cmd, cwd=str(_TRANSLATE_ROOT), env=env)
    print("phase2 exit", rc, flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
