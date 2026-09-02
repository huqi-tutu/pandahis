"""Persistent run ledger and resumable candidate storage."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_RESUME_PHASE_MAP: Dict[str, str] = {
    "phase1": "phase1",
    "stage1": "phase1",
    "mother": "phase1",
    "runtime": "phase1",
    "recall": "phase1",
    "plan": "phase1",
    "phase2": "phase2",
    "stage2": "phase2",
    "phase3": "phase3",
    "stage3": "phase3",
    "phase4": "phase4",
    "phase5": "phase5",
    "verify": "phase5",
    "verify_final": "phase5",
    "promote": "phase5",
}


def runs_root(work_dir: Path) -> Path:
    root = work_dir / ".runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_run(
    work_dir: Path,
    entry_id: str,
    *,
    formal_target: Path,
    source_fingerprint: str,
) -> Dict[str, Any]:
    run_id = f"{entry_id}-{int(time.time() * 1000)}"
    directory = runs_root(work_dir) / entry_id / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "entry_id": entry_id,
        "run_id": run_id,
        "directory": str(directory),
        "formal_target": str(formal_target),
        "source_fingerprint": source_fingerprint,
        "status": "running",
        "current_phase": "recall",
        "formal_promoted": False,
        "attempts": {},
        "next_action": "run_phase1",
    }


def save(manifest: Dict[str, Any]) -> None:
    directory = Path(str(manifest["directory"]))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load(directory: Path) -> Dict[str, Any]:
    return json.loads((directory / "manifest.json").read_text(encoding="utf-8"))


def latest(work_dir: Path, entry_id: str) -> Optional[Dict[str, Any]]:
    base = runs_root(work_dir) / entry_id
    if not base.is_dir():
        return None
    candidates = [
        p
        for p in base.iterdir()
        if p.is_dir() and (p / "manifest.json").is_file()
    ]
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return load(newest)


def resume_phase_for(phase: str) -> str:
    mapped = _RESUME_PHASE_MAP.get(phase, "phase1")
    try:
        from lib.pipeline_three_node import three_node_pipeline_enabled

        if three_node_pipeline_enabled() and mapped in frozenset({"phase5", "phase4"}):
            return "phase3"
    except ImportError:
        pass
    return mapped


def update(
    manifest: Dict[str, Any],
    *,
    phase: str,
    status: str,
    next_action: str,
    error: str = "",
) -> None:
    manifest["current_phase"] = phase
    manifest["status"] = status
    manifest["next_action"] = next_action
    if error:
        manifest["last_error"] = error[:2000]
    manifest["resume_phase"] = resume_phase_for(phase)
    manifest.setdefault("attempts", {})
    manifest["attempts"][phase] = int(manifest["attempts"].get(phase, 0)) + 1
    save(manifest)


def candidate_path(manifest: Dict[str, Any]) -> Path:
    return Path(str(manifest["directory"])) / "candidate.json"


def preserve_candidate(manifest: Dict[str, Any], candidate: Path) -> None:
    if not candidate.is_file():
        return
    dest = candidate_path(manifest)
    dest.write_bytes(candidate.read_bytes())
    manifest["candidate"] = str(dest)
    save(manifest)
