"""Atomic candidate output handling for translation runs."""

from __future__ import annotations

import os
from pathlib import Path


def staging_path(target: Path, run_id: str = "") -> Path:
    """Return an isolated candidate path next to the formal output."""
    del run_id
    stage_dir = target.parent / ".staging"
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir / target.name


def promote_candidate(candidate: Path, target: Path) -> None:
    """Atomically promote a verified candidate into the formal output path."""
    if not candidate.is_file():
        raise FileNotFoundError(f"candidate output missing: {candidate}")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(candidate, target)


def discard_candidate(candidate: Path) -> None:
    try:
        candidate.unlink()
    except FileNotFoundError:
        return


def cleanup_staging(directory: Path) -> None:
    stage_dir = directory / ".staging"
    if not stage_dir.is_dir():
        return
    for path in stage_dir.iterdir():
        if path.is_file() and path.suffix == ".json":
            try:
                path.unlink()
            except OSError:
                pass
