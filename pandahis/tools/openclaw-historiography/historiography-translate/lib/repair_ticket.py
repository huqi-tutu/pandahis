"""翻译质检修复工单：失败时落盘，repair 命令可读并执行。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.qa_repair import RepairPlan, format_repair_feedback  # noqa: E402


def ticket_path(work_dir: Path, entry_id: str) -> Path:
    return work_dir / f"{entry_id}.repair.json"


def save_repair_ticket(
    work_dir: Path,
    *,
    entry_id: str,
    entry_name: str,
    stage: str,
    errors: list[str],
    plan: RepairPlan,
    fail_count: int = 0,
) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "schema": "qa_repair_ticket/v1",
        "pipeline": "translate",
        "entry_id": entry_id,
        "entry_name": entry_name,
        "stage": stage,
        "fail_count": fail_count,
        "errors": errors,
        "plan": plan.to_dict(),
        "feedback": format_repair_feedback(plan, errors),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = ticket_path(work_dir, entry_id)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_repair_ticket(work_dir: Path, entry_id: str) -> dict[str, Any] | None:
    path = ticket_path(work_dir, entry_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_open_issues_ticket(
    work_dir: Path,
    *,
    entry_id: str,
    entry_name: str,
    stage: str,
    issues: list[str],
) -> Path | None:
    """终检通过但存在软问题：写工单供后续 refine/repair，不阻断出队。"""
    if not issues:
        return None
    plan = classify_translate_failure(issues, stage=stage, fail_count=0)
    work_dir.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "schema": "qa_repair_ticket/v1",
        "pipeline": "translate",
        "entry_id": entry_id,
        "entry_name": entry_name,
        "stage": stage,
        "status": "open_issues",
        "severity": "ticket",
        "fail_count": 0,
        "errors": issues,
        "plan": plan.to_dict(),
        "feedback": format_repair_feedback(plan, issues),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = ticket_path(work_dir, entry_id)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
