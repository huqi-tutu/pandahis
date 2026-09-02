"""Phase1 完成判定（纯读，不调 LLM）— runner / 队列共用。"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional

from lib.coverage_info import build_coverage_units
from lib.coverage_ledger import (
    claim_fingerprint,
    conveyed_ratio,
    load_ledger,
    pending_units,
)
from lib.coverage_l2 import semantic_coverage_gate_passed
from lib.phase2_batch import discover_mother_batches
from lib.work_artifacts import load_normalized_plan, mother_draft_path, plan_path


def _mother_batch_size() -> int:
    return max(0, int(os.environ.get("TRANSLATE_MOTHER_BATCH", "18")))


def _mother_json_has_body(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    body = (data.get("母本顺译") or data.get("翻译详情") or "").strip()
    return bool(body)


def mother_phase1_complete(
    work_dir: Path,
    entry_id: str,
    entry_name: str,
    *,
    recalled: Optional[Dict[str, Any]] = None,
    plan_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """纯读判定 Phase1 是否完成（不调 LLM、不写账本）。"""
    if not entry_name:
        return False
    pf = plan_path(entry_id, entry_name, work_dir)
    if plan_data is None and not pf.is_file():
        return False

    mother_file = mother_draft_path(entry_id, entry_name, work_dir)
    if not mother_file.is_file():
        matches = sorted(
            p
            for p in work_dir.glob(f"{entry_id}_*.mother.json")
            if ".mother-b" not in p.name
        )
        if matches:
            mother_file = matches[0]
        else:
            return False

    if plan_data is None:
        if recalled is None:
            return False
        try:
            _, plan_data, _ = load_normalized_plan(pf, recalled)
        except Exception:
            return False

    checklist = plan_data.get("母本逐句清单") or []
    if not isinstance(checklist, list) or not checklist:
        return False

    batch_size = _mother_batch_size()
    uses_batches = batch_size > 0 and len(checklist) > batch_size
    if uses_batches:
        if not mother_file.is_file():
            return False
        batches = discover_mother_batches(mother_file)
        expected = math.ceil(len(checklist) / batch_size)
        if len(batches) < expected:
            return False
        if not all(_mother_json_has_body(p) for p in batches):
            return False
    elif not _mother_json_has_body(mother_file):
        return False

    if os.environ.get("TRANSLATE_COVERAGE_INCREMENTAL", "1") == "0":
        return True

    units = build_coverage_units(checklist)
    if not units:
        return True

    entries = load_ledger(work_dir, entry_id)
    _, fps, _ = pending_units(units, entries)
    ok_count, total = conveyed_ratio(units, entries, fps)

    weak_labels: list[str] = []
    for unit in units:
        rec = entries.get(unit.label) or {}
        fp = fps.get(unit.label) or claim_fingerprint(unit)
        status = str(rec.get("status") or "")
        if status == "conveyed" and str(rec.get("claim_fp") or "") == fp:
            continue
        weak_labels.append(unit.label)

    passed, _ = semantic_coverage_gate_passed(
        ok_count,
        total,
        len(weak_labels),
    )
    return passed
