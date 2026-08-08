#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顺译队列辅助：与 Skill verify_output 对齐的完成判定与续跑模式。"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRANSLATE_SKILL = ROOT / "tools" / "openclaw-historiography" / "historiography-translate"
HIST_ROOT = ROOT / "tools" / "openclaw-historiography"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
OUT_11 = DATA / "11新标注条目翻译"
TRANSLATE_WORK = DATA / "05工作流中间产物" / "翻译"


@lru_cache(maxsize=1)
def _ensure_translate_imports() -> None:
    for p in (str(HIST_ROOT), str(TRANSLATE_SKILL)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _entry_name_from_index(eid: str) -> str:
    try:
        rows = json.loads(V2_INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    for row in rows:
        if str(row.get("史略ID") or "") == eid:
            return str(row.get("史略名称") or "")
    return ""


def _load_repair_ticket(eid: str) -> dict[str, Any] | None:
    path = TRANSLATE_WORK / f"{eid}.repair.json"
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _glob_mother_file(eid: str) -> Path | None:
    matches = sorted(
        p
        for p in TRANSLATE_WORK.glob(f"{eid}_*.mother.json")
        if ".mother-b" not in p.name
    )
    return matches[0] if matches else None


def mother_verify_passed(eid: str, *, entry_name: str | None = None) -> bool:
    """Phase1 母本已通过 verify_mother_draft（非 batch 全篇）。"""
    _ensure_translate_imports()
    from lib.recall import recall_entry  # noqa: WPS433
    from lib.verify import verify_mother_draft  # noqa: WPS433
    from lib.work_artifacts import load_normalized_plan, mother_draft_path, plan_path  # noqa: WPS433

    name = entry_name or _entry_name_from_index(eid)
    if not name:
        return False
    mother_file = mother_draft_path(eid, name, TRANSLATE_WORK)
    if not mother_file.is_file():
        mother_file = _glob_mother_file(eid)
    if not mother_file or not mother_file.is_file():
        return False
    pf = plan_path(eid, name, TRANSLATE_WORK)
    if not pf.is_file():
        return False
    try:
        recalled = recall_entry(eid, index_path=V2_INDEX)
        _, plan_data, _ = load_normalized_plan(pf, recalled)
        ok, _ = verify_mother_draft(
            eid, recalled, mother_file, plan=plan_data, batch_mode=False
        )
        return ok
    except Exception:
        return False


def is_translate_verify_done(eid: str, *, entry_name: str | None = None) -> bool:
    """与 Skill 终检 verify_output 对齐（队列 done 判定）。"""
    _ensure_translate_imports()
    from lib.recall import recall_entry  # noqa: WPS433
    from lib.verify import verify_output  # noqa: WPS433
    from lib.work_artifacts import load_normalized_plan, plan_path  # noqa: WPS433

    name = entry_name or _entry_name_from_index(eid)
    if not name:
        return False
    pf = plan_path(eid, name, TRANSLATE_WORK)
    plan_data: dict[str, Any] | None = None
    try:
        recalled = recall_entry(eid, index_path=V2_INDEX)
        if pf.is_file():
            _, plan_data, _ = load_normalized_plan(pf, recalled)
        ok, _ = verify_output(eid, recalled, OUT_11, plan=plan_data)
        return ok
    except Exception:
        return False


def pick_retry_mode(eid: str, *, entry_name: str | None = None) -> str:
    """repair | phase2 | full — 全局续跑策略。"""
    if _load_repair_ticket(eid):
        return "repair"
    if mother_verify_passed(eid, entry_name=entry_name):
        return "phase2"
    return "full"
