"""Plan 母本逐句清单 → 分批（供 streamlined / ABCD 共用）。"""

from __future__ import annotations

from typing import Any, Dict, List

from lib.batch_continuity import default_batch_target, split_checklist_at_p_boundaries


def batched_mother_checklist(plan_data: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    checklist = plan_data.get("母本逐句清单") or []
    if not isinstance(checklist, list):
        return [[]]
    return split_checklist_at_p_boundaries(checklist, default_batch_target())
