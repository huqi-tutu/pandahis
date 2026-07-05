"""Step4 封板检测：防止 Step1 expand 覆盖已补全字段的 skeleton。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from lib.config import ANNOTATE_DIR

sys.path.insert(0, str(ANNOTATE_DIR))
from coordinate_index import COORD_FIELDS, COORD_ID_FIELDS, migrate_entry_fields  # noqa: E402

STEP4_REQUIRED = (
    "优先级",
    "优先级判定理由",
    "史略开始年",
    "史略结束年",
    *COORD_FIELDS,
    *COORD_ID_FIELDS,
)


def skeleton_step4_sealed(data: dict) -> bool:
    """entries 已具备 Step4 全部正式字段且无 _needs_llm。"""
    entries = data.get("entries") or []
    if not entries:
        return False
    for entry in entries:
        migrate_entry_fields(entry)
        if entry.get("_needs_llm"):
            return False
        for key in STEP4_REQUIRED:
            val = entry.get(key)
            if val is None or val == "":
                return False
    return True


def load_skeleton_sealed(sk_path: Path) -> bool:
    if not sk_path.is_file():
        return False
    try:
        import json

        data = json.loads(sk_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return skeleton_step4_sealed(data)
