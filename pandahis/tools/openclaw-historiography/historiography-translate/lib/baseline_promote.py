"""母本顺译降级为 baseline 成稿（Phase2 失败时不废整条）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from lib.staging import promote_candidate, staging_path


def baseline_fallback_enabled() -> bool:
    return os.environ.get("TRANSLATE_BASELINE_ON_PHASE2_FAIL", "1") != "0"


def write_baseline_from_file(
    target: Path,
    baseline_file: Path,
    entry_id: str,
    *,
    translation_version: str | None = None,
    phase2_errors: List[str] | None = None,
) -> Path:
    """将 C 阶段 baseline 写入正式路径。"""
    if not baseline_file.is_file():
        raise FileNotFoundError(f"baseline 不存在: {baseline_file}")
    data = json.loads(baseline_file.read_text(encoding="utf-8"))
    detail = str(data.get("翻译详情") or "").strip()
    if not detail:
        raise ValueError("baseline 翻译详情为空")

    candidate = staging_path(target, "baseline")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    doc: Dict[str, Any] = {
        "史略ID": entry_id,
        "翻译详情": detail,
        "翻译版本": translation_version or "baseline_ready",
    }
    if phase2_errors:
        doc["_baseline_meta"] = {
            "reason": "phase_d_failed",
            "errors": phase2_errors[:8],
        }
    candidate.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    promote_candidate(candidate, target)
    return target


def write_baseline_from_mother(
    target: Path,
    entry_id: str,
    mother_body: str,
    *,
    translation_version: str | None = None,
    phase2_errors: List[str] | None = None,
) -> Path:
    """将母本顺译写入候选稿；由 promote 落正式路径。"""
    body = (mother_body or "").strip()
    if not body:
        raise ValueError("母本顺译为空，无法生成 baseline")

    candidate = staging_path(target, "baseline")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    doc: Dict[str, Any] = {
        "史略ID": entry_id,
        "翻译详情": body,
        "翻译版本": translation_version or "baseline_mother",
    }
    if phase2_errors:
        doc["_baseline_meta"] = {
            "reason": "phase2_failed",
            "errors": phase2_errors[:8],
        }
    candidate.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    promote_candidate(candidate, target)
    return target
