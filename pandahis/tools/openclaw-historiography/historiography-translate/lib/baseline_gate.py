"""baseline 母本降级稿识别与发布门禁。"""

from __future__ import annotations

from typing import Any, Dict


def is_baseline_output(data: Dict[str, Any]) -> bool:
    ver = str(data.get("翻译版本") or "").strip().lower()
    if ver.startswith("baseline") or "baseline_mother" in ver:
        return True
    meta = data.get("_baseline_meta")
    return isinstance(meta, dict) and bool(meta)


def baseline_sync_allowed() -> bool:
    import os

    return os.environ.get("TRANSLATE_SYNC_BASELINE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def baseline_sync_blocked(data: Dict[str, Any]) -> bool:
    """baseline_ready / vN 可同步（带版本标注）；其余 baseline 降级稿默认拦截。"""
    if baseline_sync_allowed():
        return False
    ver = str(data.get("翻译版本") or "").strip().lower()
    if ver.startswith("v") or ver == "baseline_ready":
        return False
    return is_baseline_output(data)
