"""君王命名：以帝王.json「帝王」字段为唯一标准名。"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from emperor_resolve import (
    align_skeleton_emperors,
    build_emperor_info_index,
    collect_unresolved_junji,
    resolve_emperor_label,
    work_id_from_volume,
)


def junji_name_violation(name: str, *, emperor_index: Optional[Dict[str, dict]] = None) -> Optional[str]:
    """
    君王名称违规说明；None 表示合规。
    标准：史略名称须与帝王.json「帝王」字段完全一致。
    """
    n = name.strip()
    if not n:
        return "君王名称为空"
    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()
    if n in eidx:
        return None
    info, method = resolve_emperor_label(n, emperor_index=eidx)
    if info:
        return (
            f"君王名「{n}」应改为帝王表标准名「{info['emperor']}」"
            f"（{method or '可解析'}）"
        )
    return f"君王「{n}」不在帝王.json，且无法通过别名解析"


def rename_junji_in_skeleton(data: dict) -> Tuple[dict, List[str]]:
    """就地解析并对齐君王名称（帝王表标准名）。"""
    return align_skeleton_emperors(data, only_junji=True)


def collect_junji_violations(
    data: dict,
    emperor_index: Optional[Dict[str, dict]] = None,
) -> List[str]:
    eidx = emperor_index if emperor_index is not None else build_emperor_info_index()
    errs: List[str] = []
    work_id = work_id_from_volume(data.get("volume", ""))

    for entry in data.get("entries", []):
        if entry.get("史略分类") != "君王":
            continue
        name = entry.get("史略名称", "").strip()
        if name in eidx:
            coord = (entry.get("四级帝王坐标") or "").strip()
            if coord and coord != name:
                errs.append(
                    f"[{entry.get('史略ID')}] 君王名称「{name}」与四级帝王坐标「{coord}」不一致"
                )
            continue
        msg = junji_name_violation(name, emperor_index=eidx)
        if msg:
            errs.append(f"[{entry.get('史略ID')}] {msg}")

    for row in data.get("segment_attribution", []):
        for owner in row.get("owners", []):
            if owner.get("category") != "君王":
                continue
            name = owner.get("name", "").strip()
            if name in eidx:
                continue
            msg = junji_name_violation(name, emperor_index=eidx)
            if msg:
                errs.append(f"段{row.get('paragraph')} 归属 {msg}")

    unresolved = collect_unresolved_junji(data, emperor_index=eidx)
    for u in unresolved:
        if u not in errs:
            errs.append(u)

    _ = work_id  # 保留扩展点
    return errs
