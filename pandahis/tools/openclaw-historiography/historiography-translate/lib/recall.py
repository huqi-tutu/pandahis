"""桥接 historiography-annotate 全局召回。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from lib.config import ANNOTATE_DIR, default_index_path

if str(ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(ANNOTATE_DIR))

from recall_paragraphs import (  # noqa: E402
    RecallError,
    find_global_entry,
    load_global_index,
    recall_global_index_entry,
)
from transition_spans import (  # noqa: E402
    apply_recall_subject_filter,
    inject_exit_supplements,
)


def recall_entry(
    entry_id: str,
    *,
    index_path: Path | None = None,
) -> Dict[str, Any]:
    idx_path = index_path or default_index_path()
    index = load_global_index(idx_path)
    entry = find_global_entry(index, entry_id)
    recalled = recall_global_index_entry(entry)
    recalled = apply_recall_subject_filter(recalled)
    all_entries: List[Dict[str, Any]] = list(index.get("entries") or [])
    recalled = inject_exit_supplements(recalled, index_entries=all_entries)
    return recalled


__all__ = ["RecallError", "recall_entry", "load_global_index", "find_global_entry"]
