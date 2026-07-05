"""合传 skeleton：删除卷名简称伪条目（如张陈、张周、郦陆、卫直）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Tuple

from lib.config import ANNOTATE_DIR, paths

sys.path.insert(0, str(ANNOTATE_DIR))
from check_format import (  # noqa: E402
    _bogus_hezhuan_chunk_names,
    _core_person_covered,
    _split_hezhuan_core_names,
)


def _core_from_data(data: dict) -> str:
    source_file = data.get("source_file") or ""
    m = re.match(r"^02汉书_\d{3}_(.+?)传", source_file)
    return m.group(1) if m else ""


def strip_bogus_hezhuan_entries(
    work: str,
    vol: str,
    *,
    skeleton_path: Path | None = None,
) -> Tuple[bool, str]:
    """
    合传卷：删除史略名称为卷名简称切块（张周/郦陆/卫直等）的伪士臣条目，
    并同步清理 segment_attribution 中的同名 owners。
    仅在删后仍满足合传人物覆盖时改写。
    """
    vol = vol.zfill(3)
    sk_path = skeleton_path or _find_skeleton(work, vol)
    if not sk_path:
        return False, "未找到 skeleton"

    data = json.loads(sk_path.read_text(encoding="utf-8"))
    core = _core_from_data(data)
    bogus = _bogus_hezhuan_chunk_names(core)
    if not bogus:
        return False, "无合传简称规则，跳过"

    entries = data.get("entries") or []
    removed = [e.get("史略名称") for e in entries if e.get("史略名称") in bogus]
    if not removed:
        return False, "无伪简称条目"

    from lib_config import normalize_entry_category  # noqa: E402

    kept = [e for e in entries if e.get("史略名称") not in bogus]
    person_kept = {
        e.get("史略名称", "")
        for e in kept
        if normalize_entry_category(e.get("史略分类", "")) in {"士臣", "君纪"}
    }
    segments = _split_hezhuan_core_names(core, person_kept)
    if segments and not all(_core_person_covered(s, person_kept) for s in segments):
        return False, f"删伪条目后合传人物未齐，勿自动删: {removed}"

    remove_set = set(removed)
    for row in data.get("segment_attribution") or []:
        owners = row.get("owners") or []
        new_owners = [o for o in owners if o.get("name") not in remove_set]
        if len(new_owners) != len(owners):
            row["owners"] = new_owners

    data["entries"] = kept
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, f"已删除伪合传简称条目 {removed}（卷{vol}）"


def _find_skeleton(work: str, vol: str) -> Path | None:
    matches = sorted(paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None
