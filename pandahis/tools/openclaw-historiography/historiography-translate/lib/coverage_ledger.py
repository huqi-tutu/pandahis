"""母本语义覆盖账本：已 conveyed 的 M 单元不重复调 LLM。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.coverage_info import CoverageUnit


def claim_fingerprint(unit: CoverageUnit) -> str:
    row = unit.primary
    info = str(row.get("信息点") or "").strip()
    orig = str(row.get("原文摘句") or row.get("text") or "").strip()
    payload = f"{unit.label}\n{info}\n{orig}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def ledger_path(work_dir: Path, entry_id: str) -> Path:
    return work_dir / "coverage" / f"{entry_id}_coverage_ledger.json"


def load_ledger(work_dir: Path, entry_id: str) -> Dict[str, Dict[str, Any]]:
    path = ledger_path(work_dir, entry_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = data.get("entries")
    return dict(entries) if isinstance(entries, dict) else {}


def save_ledger(work_dir: Path, entry_id: str, entries: Dict[str, Dict[str, Any]]) -> Path:
    path = ledger_path(work_dir, entry_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema": "translate-coverage-ledger/v1",
        "史略ID": entry_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def clear_ledger(work_dir: Path, entry_id: str) -> None:
    path = ledger_path(work_dir, entry_id)
    if path.is_file():
        path.unlink()


def clear_ledger_labels(
    work_dir: Path,
    entry_id: str,
    labels: List[str],
) -> None:
    """清除指定 M 单元的账本记录（本批重试前调用）。"""
    if not labels:
        return
    entries = load_ledger(work_dir, entry_id)
    if not entries:
        return
    for label in labels:
        entries.pop(label, None)
    if entries:
        save_ledger(work_dir, entry_id, entries)
    else:
        clear_ledger(work_dir, entry_id)


def is_conveyed_cached(
    unit: CoverageUnit,
    entries: Dict[str, Dict[str, Any]],
    *,
    fp: Optional[str] = None,
) -> bool:
    fp = fp if fp is not None else claim_fingerprint(unit)
    rec = entries.get(unit.label) or {}
    return (
        str(rec.get("status") or "") == "conveyed"
        and str(rec.get("claim_fp") or "") == fp
    )


def pending_units(
    units: List[CoverageUnit],
    entries: Dict[str, Dict[str, Any]],
) -> tuple[List[CoverageUnit], Dict[str, str], set[str]]:
    """返回 (待 LLM 复核单元, label→fp, 账本已 conveyed 的 label 集合)。"""
    pending: List[CoverageUnit] = []
    fps: Dict[str, str] = {}
    cached_ok: set[str] = set()
    for unit in units:
        fp = claim_fingerprint(unit)
        fps[unit.label] = fp
        if is_conveyed_cached(unit, entries, fp=fp):
            cached_ok.add(unit.label)
        else:
            pending.append(unit)
    return pending, fps, cached_ok


def apply_claim_results(
    entries: Dict[str, Dict[str, Any]],
    *,
    claim_id: str,
    status: str,
    claim_fp: str,
    note: str = "",
) -> None:
    entries[claim_id] = {
        "status": status,
        "claim_fp": claim_fp,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "note": (note or "")[:240],
    }


def conveyed_ratio(
    units: List[CoverageUnit],
    entries: Dict[str, Dict[str, Any]],
    fps: Dict[str, str],
) -> tuple[int, int]:
    ok = 0
    for unit in units:
        rec = entries.get(unit.label) or {}
        fp = fps.get(unit.label) or claim_fingerprint(unit)
        if str(rec.get("status") or "") == "conveyed" and str(rec.get("claim_fp") or "") == fp:
            ok += 1
    return ok, len(units)
