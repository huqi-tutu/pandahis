"""全局索引筛选（朝代等）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from lib.config import default_index_path
from lib.recall import load_global_index


def entry_ids_for_dynasty(
    dynasty: str,
    *,
    index_path: Path | None = None,
) -> Set[str]:
    """按二级朝代坐标或三级政权坐标筛选史略 ID。"""
    idx_path = index_path or default_index_path()
    index = load_global_index(idx_path)
    entries = index.get("entries") or []
    out: Set[str] = set()
    for e in entries:
        eid = e.get("史略ID")
        if not eid:
            continue
        if e.get("二级朝代坐标") == dynasty or e.get("三级政权坐标") == dynasty:
            out.add(str(eid))
    return out


def filter_pending_jobs(
    jobs: List[Dict[str, Any]],
    *,
    dynasty: Optional[str] = None,
    from_id: Optional[str] = None,
    index_path: Path | None = None,
) -> List[Dict[str, Any]]:
    out = list(jobs)
    if dynasty:
        allowed = entry_ids_for_dynasty(dynasty, index_path=index_path)
        out = [j for j in out if j.get("entry_id") in allowed]
    if from_id:
        out = [j for j in out if str(j.get("entry_id") or "") >= from_id]
    out.sort(key=lambda j: str(j.get("entry_id") or ""))
    return out
