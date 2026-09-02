#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顺译队列辅助：与 Skill verify_output 对齐的完成判定与续跑模式。"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class TranslateRunSpec:
    """队列调用 translate.py 的参数（纯读决策，不调 LLM）。"""

    mode: str  # full | phase2 | phase3 | phase4 | phase5 | repair | resume
    cli_args: tuple[str, ...]
    reason: str = ""

    def label(self) -> str:
        if self.mode == "resume":
            return "resume:" + (self.cli_args[-1] if self.cli_args else "?")
        return self.mode


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


def load_pending_manifest(eid: str) -> dict[str, Any] | None:
    _ensure_translate_imports()
    from lib.run_ledger import latest  # noqa: WPS433

    manifest = latest(TRANSLATE_WORK, eid)
    if not manifest:
        return None
    if str(manifest.get("status") or "") == "pending_recovery":
        return manifest
    return None


def load_resumable_manifest(eid: str) -> dict[str, Any] | None:
    """running / failed / pending_recovery 均可续跑。"""
    _ensure_translate_imports()
    from lib.run_ledger import latest  # noqa: WPS433

    manifest = latest(TRANSLATE_WORK, eid)
    if not manifest:
        return None
    if str(manifest.get("status") or "") in {
        "pending_recovery",
        "running",
        "failed",
    }:
        return manifest
    return None


def is_api_transient_error(message: str) -> bool:
    _ensure_translate_imports()
    from shared.coverage_semantic import is_retryable_infra_error  # noqa: WPS433

    return is_retryable_infra_error(RuntimeError(message))


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


def _plan_file(eid: str, name: str) -> Path:
    _ensure_translate_imports()
    from lib.work_artifacts import plan_path  # noqa: WPS433

    return plan_path(eid, name, TRANSLATE_WORK)


def _mother_file(eid: str, name: str) -> Path:
    _ensure_translate_imports()
    from lib.work_artifacts import mother_draft_path  # noqa: WPS433

    mf = mother_draft_path(eid, name, TRANSLATE_WORK)
    if mf.is_file():
        return mf
    matches = sorted(
        p
        for p in TRANSLATE_WORK.glob(f"{eid}_*.mother.json")
        if ".mother-b" not in p.name
    )
    return matches[0] if matches else mf


def mother_phase1_complete(eid: str, *, entry_name: str | None = None) -> bool:
    """纯读判定 Phase1 是否完成（不调 LLM、不写账本）。"""
    _ensure_translate_imports()
    from lib.phase1_status import mother_phase1_complete as _phase1_complete  # noqa: WPS433
    from lib.recall import recall_entry  # noqa: WPS433

    name = entry_name or _entry_name_from_index(eid)
    if not name:
        return False
    try:
        recalled = recall_entry(eid, index_path=V2_INDEX)
    except Exception:
        recalled = None
    return _phase1_complete(
        TRANSLATE_WORK,
        eid,
        name,
        recalled=recalled,
    )


def mother_verify_passed(eid: str, *, entry_name: str | None = None) -> bool:
    """Phase1 完成判定（队列用：纯读，不调 LLM）。"""
    return mother_phase1_complete(eid, entry_name=entry_name)


def is_translate_verify_done(eid: str, *, entry_name: str | None = None) -> bool:
    """队列 done 判定：纯读、零 LLM。

    快路径：最新 run manifest 已 promoted 且正式文件在位 → 信任 promote 时终检。
    回退：程序版 verify_output（覆盖检查仅报告、不调 LLM、不影响判定）。
    """
    _ensure_translate_imports()
    from lib.recall import recall_entry  # noqa: WPS433
    from lib.run_ledger import latest as latest_run  # noqa: WPS433
    from lib.verify import verify_output  # noqa: WPS433
    from lib.work_artifacts import load_normalized_plan, plan_path  # noqa: WPS433

    name = entry_name or _entry_name_from_index(eid)
    if not name:
        return False
    try:
        manifest = latest_run(TRANSLATE_WORK, eid)
        if manifest and str(manifest.get("status") or "") in {"promoted", "baseline_ready"}:
            target = Path(str(manifest.get("formal_target") or ""))
            if target.is_file():
                return True
    except Exception:
        pass
    pf = plan_path(eid, name, TRANSLATE_WORK)
    plan_data: dict[str, Any] | None = None
    try:
        recalled = recall_entry(eid, index_path=V2_INDEX)
        if pf.is_file():
            _, plan_data, _ = load_normalized_plan(pf, recalled)
        ok, _ = verify_output(eid, recalled, OUT_11, plan=plan_data, coverage="report")
        return ok
    except Exception:
        return False


def _resume_from_manifest(manifest: dict[str, Any], eid: str, *, entry_name: str | None) -> TranslateRunSpec:
    resume_phase = str(manifest.get("resume_phase") or "phase1")
    if resume_phase != "phase1" and not mother_phase1_complete(eid, entry_name=entry_name):
        return TranslateRunSpec("full", (), "manifest 待恢复但 Phase1 未完成 → 全量续跑（批缓存）")
    if resume_phase == "phase1":
        if mother_phase1_complete(eid, entry_name=entry_name):
            return TranslateRunSpec(
                "resume",
                ("--resume", "latest", "--from-phase", "phase2"),
                "manifest phase1 但账本就绪 → phase2",
            )
        return TranslateRunSpec(
            "resume",
            ("--resume", "latest"),
            "manifest pending_recovery → Phase1（批缓存）",
        )
    return TranslateRunSpec(
        "resume",
        ("--resume", "latest", "--from-phase", resume_phase),
        f"manifest pending_recovery → {resume_phase}",
    )


def _resume_phase_after_phase1(manifest: dict[str, Any]) -> str:
    rp = str(manifest.get("resume_phase") or "phase1")
    if rp == "phase1":
        return "phase2"
    return rp


def build_translate_run(eid: str, *, entry_name: str | None = None) -> TranslateRunSpec:
    """队列 SSOT：manifest 优先，其次 repair，再 phase2/full。"""
    name = entry_name or _entry_name_from_index(eid)
    manifest = load_pending_manifest(eid)
    if manifest:
        return _resume_from_manifest(manifest, eid, entry_name=name)

    phase1_done = mother_phase1_complete(eid, entry_name=name)
    resumable = load_resumable_manifest(eid)
    if resumable and phase1_done:
        next_phase = _resume_phase_after_phase1(resumable)
        return TranslateRunSpec(
            "resume",
            ("--resume", "latest", "--from-phase", next_phase),
            f"manifest {resumable.get('status')} + Phase1 就绪 → {next_phase}",
        )

    ticket = _load_repair_ticket(eid)
    if ticket and phase1_done:
        return TranslateRunSpec("repair", (), f"repair ticket stage={ticket.get('stage')}")
    if ticket and not phase1_done:
        return TranslateRunSpec("full", (), "repair ticket 存在但 Phase1 未完成 → 全量")

    if phase1_done:
        return TranslateRunSpec("phase2", ("--from-phase", "phase2"), "Phase1 账本就绪 → phase2")
    return TranslateRunSpec("full", (), "无缓存 / Phase1 未完成")


def pick_retry_mode(eid: str, *, entry_name: str | None = None) -> str:
    """repair | phase2 | full | resume — 兼容旧调用。"""
    return build_translate_run(eid, entry_name=entry_name).label()
