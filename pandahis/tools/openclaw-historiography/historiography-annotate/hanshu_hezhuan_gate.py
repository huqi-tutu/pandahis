#!/usr/bin/env python3
"""《汉书》合传卷门禁：卷名拆分白名单 + repair 前校验。"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

SKILL_DIR = Path(__file__).resolve().parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from check_format import (  # noqa: E402
    _HEZHUAN_CORE_OVERRIDES,
    _bogus_hezhuan_chunk_names,
    _core_person_covered,
    _split_hezhuan_core_names,
)


def core_from_source(source_file: str) -> str:
    m = re.match(r"^02汉书_\d{3}_(.+?)传", source_file or "")
    return m.group(1) if m else ""


def expected_protagonist_segments(source_file: str) -> List[str]:
    """卷名「传」前核心 → 人物标识列表（来自白名单或启发式）。"""
    core = core_from_source(source_file)
    if not core:
        return []
    return _split_hezhuan_core_names(core)


def bogus_entry_names(source_file: str) -> Set[str]:
    """禁止作为史略名称的卷名相邻简称伪名。"""
    core = core_from_source(source_file)
    return _bogus_hezhuan_chunk_names(core) if core else set()


def validate_repair_plan(
    source_file: str,
    entry_names: List[str],
) -> Tuple[bool, str]:
    """
    repair 落盘前校验：
    1. 卷名须在白名单或能拆成 ≥2 人
    2. 不得含伪简称条目名
    3. 每位卷名核心人物须有 entry（姓/全名匹配）
    """
    core = core_from_source(source_file)
    if not core:
        return True, "非合传卷名格式，跳过门禁"
    segments = expected_protagonist_segments(source_file)
    if len(segments) < 2:
        return (
            False,
            f"卷「{core}传」未在白名单且无法可靠拆分；"
            f"请先补 check_format._HEZHUAN_CORE_OVERRIDES",
        )
    bogus = bogus_entry_names(source_file)
    bad = [n for n in entry_names if n in bogus]
    if bad:
        return False, f"含卷名伪简称条目: {bad}（禁止如「{core[:2]}」类切块）"
    person_set = set(entry_names)
    missing = [s for s in segments if not _core_person_covered(s, person_set)]
    if missing:
        return (
            False,
            f"卷名核心人物未齐: {missing}；当前 entries={entry_names}；"
            f"白名单={segments}",
        )
    if core not in _HEZHUAN_CORE_OVERRIDES:
        return True, f"启发式拆分通过: {segments}（建议补白名单）"
    return True, f"白名单核对通过: {segments}"
