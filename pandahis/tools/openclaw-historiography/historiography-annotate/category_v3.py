#!/usr/bin/env python3
"""史略分类 v3：文臣 / 武将 / 宦官 / 蕃祚 等枚举与迁移辅助。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

from collective_volume_subjects import COLLECTIVE_YEAR_RULE, COLLECTIVE_YEAR_RULE_NOTE
from fanzuo_volumes import is_fanzuo_volume as _is_fanzuo_volume

# ── 合法枚举 ──────────────────────────────────────────────
VALID_CATS = frozenset({
    "君王",
    "宗戚",
    "宦官",
    "文臣",
    "武将",
    "蕃祚",
    "庶众",
})

# 需四级帝王坐标与人物生卒年规则（非君王）
SPINDLE_CATEGORIES = frozenset({
    "文臣",
    "武将",
    "宦官",
    "庶众",
    "宗戚",
    "蕃祚",
})

OFFICIAL_CATEGORIES = frozenset({"文臣", "武将", "宦官"})

# 分类唯一性链（高者优先）
CATEGORY_PRIORITY = (
    "君王",
    "宗戚",
    "宦官",
    "文臣",
    "武将",
    "蕃祚",
    "庶众",
)

# 读盘兼容：旧 skeleton 七类 + 士臣
LEGACY_READ_CATS = frozenset({
    "君纪", "事略", "典制", "民录", "论著", "著作", "思想", "士臣",
})

LEGACY_CATEGORY_MAP = {
    "君纪": "君王",
    "宫眷": "宗戚",
    "著作": "论著",
    "思想": "论著",
    # 士臣 不在此映射：须经 resolve_category_v3 拆为文臣/武将/宦官
}

# ── 《史记》武将名录（史名以武事最著）──────────────────────
SHIJI_WUJIANG_NAMES: Set[str] = {
    "白起", "王翦", "吴起", "司马穰苴", "廉颇", "乐毅", "蒙恬", "田单", "伍子胥",
    "卫青", "霍去病", "李广", "韩信", "樊哙", "周勃", "灌婴", "彭越", "黥布", "魏豹",
    "季布", "栾布", "郦商", "靳歙", "傅宽", "灌夫", "杨仆", "韩王信",
    "田荣", "田横", "田儋", "刘濞", "张耳", "陈馀",
}

# ── 《史记》宦官（卷主轴为内官/近幸；不含受宫刑士人）──────
SHIJI_EUNUCH_NAMES: Set[str] = {
    "李延年",
}

# ── 本为士臣但应归庶众（刺客、优人、隐逸等）──────────────
SHIJI_SHUZHONG_NAMES: Set[str] = {
    "专诸", "曹沫", "聂政", "荆轲", "豫让",
    "优孟", "优旃", "淳于髡",
    "伯夷",
}

# ── 强制文臣（著述/儒学主轴）────────────────────────────
SHIJI_WENCHEN_FORCE: Set[str] = {
    "孔子", "司马迁",
}

# ── 蕃祚：政权/部族集体名 ────────────────────────────────
FANZUO_SUBJECT_NAMES: Set[str] = {
    "匈奴", "南越", "东越", "朝鲜", "西南夷", "大宛",
}

FANZUO_YEAR_RULE = COLLECTIVE_YEAR_RULE
FANZUO_YEAR_RULE_NOTE = COLLECTIVE_YEAR_RULE_NOTE


def normalize_entry_category(cat: str) -> str:
    """读盘归一；士臣保留原样供迁移脚本识别。"""
    c = (cat or "").strip()
    return LEGACY_CATEGORY_MAP.get(c, c)


def is_fanzuo_volume(work: str, vol: str, volume_name: str = "") -> bool:
    return _is_fanzuo_volume(work, vol, volume_name)


def resolve_category_v3(
    name: str,
    current: str,
    *,
    volume_name: str = "",
    work: str = "",
    vol: str = "",
) -> str:
    """将旧分类解析为 v3 唯一分类。"""
    name = (name or "").strip()
    cur = normalize_entry_category((current or "").strip())

    if cur in {"君王", "宗戚"}:
        return cur

    if cur == "蕃祚":
        return "蕃祚"

    if cur == "宦官":
        return "宦官"

    if cur in {"文臣", "武将"}:
        return cur

    # 庶众 → 蕃祚（域外/边陲政权集体）
    if cur == "庶众":
        if name in FANZUO_SUBJECT_NAMES:
            return "蕃祚"
        if is_fanzuo_volume(work, vol, volume_name) and is_collective_volume_name(name, volume_name):
            return "蕃祚"
        return "庶众"

    # 士臣 → 文臣 / 武将 / 宦官 / 庶众
    if cur == "士臣" or cur == "":
        if name in SHIJI_EUNUCH_NAMES:
            return "宦官"
        if name in SHIJI_SHUZHONG_NAMES:
            return "庶众"
        if name in SHIJI_WENCHEN_FORCE:
            return "文臣"
        if name in SHIJI_WUJIANG_NAMES:
            return "武将"
        if name in FANZUO_SUBJECT_NAMES:
            return "蕃祚"
        return "文臣"

    return cur if cur in VALID_CATS else "文臣"


def is_collective_volume_name(name: str, volume_name: str) -> bool:
    vn = (volume_name or "").replace("列传", "").strip()
    nm = (name or "").strip()
    if not nm or not vn:
        return False
    return nm in vn or vn.startswith(nm) or nm in FANZUO_SUBJECT_NAMES


def migrate_skeleton_data(data: dict, *, work: str = "", vol: str = "") -> int:
    """就地迁移 skeleton / blocks / protagonists 中的分类字段。返回变更数。"""
    changed = 0
    vol_name = (data.get("volume") or "").strip()

    for entry in data.get("entries") or []:
        old = (entry.get("史略分类") or "").strip()
        new = resolve_category_v3(
            entry.get("史略名称", ""),
            old,
            volume_name=vol_name,
            work=work,
            vol=vol,
        )
        if new != old:
            entry["史略分类"] = new
            changed += 1
            af = entry.get("_auto_filled")
            if isinstance(af, dict) and old == "庶众" and new == "蕃祚":
                af["年规则"] = FANZUO_YEAR_RULE
                af["年规则备注"] = FANZUO_YEAR_RULE_NOTE

    for seg in data.get("segment_attribution") or []:
        for owner in seg.get("owners") or []:
            old = (owner.get("category") or "").strip()
            new = resolve_category_v3(
                owner.get("name", ""),
                old,
                volume_name=vol_name,
                work=work,
                vol=vol,
            )
            if new != old:
                owner["category"] = new
                changed += 1

    for block in data.get("blocks") or []:
        old = (block.get("category") or "").strip()
        new = resolve_category_v3(
            block.get("name", ""),
            old,
            volume_name=vol_name,
            work=work,
            vol=vol,
        )
        if new != old:
            block["category"] = new
            changed += 1

    for p in data.get("protagonists") or []:
        old = (p.get("category") or "").strip()
        new = resolve_category_v3(
            p.get("name", ""),
            old,
            volume_name=vol_name,
            work=work,
            vol=vol,
        )
        if new != old:
            p["category"] = new
            changed += 1

    return changed


def migrate_json_file(path: Path, *, work: str = "01史记", vol: str = "") -> int:
    if not path.exists():
        return 0
    m = re.search(r"_(\d{3})_", path.name)
    vol_id = vol or (m.group(1) if m else "")
    data = json.loads(path.read_text(encoding="utf-8"))
    n = migrate_skeleton_data(data, work=work, vol=vol_id)
    if n:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def refresh_detail_coords_tree(data_root: Path, *, work: str = "01史记") -> int:
    """按当前史略分类重算五级细坐标 / 六级段落锚点 / 原文出处。"""
    import re
    from detail_coords import fill_all_detail_coords

    sk_dir = data_root / "data" / "03索引标注条目"
    updated = 0
    for fp in sorted(sk_dir.glob(f"{work}_*_skeleton.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        m = re.search(r"_(\d{3})_", fp.name)
        vol = m.group(1) if m else "000"
        n = fill_all_detail_coords(data, work_id=work, json_path=str(fp))
        if n:
            fp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated += n
    return updated


def migrate_shiji_tree(data_root: Path) -> Dict[str, int]:
    """迁移《史记》 skeleton、blocks、protagonists。"""
    stats = {"skeleton": 0, "blocks": 0, "protagonists": 0, "files": 0}
    mid = data_root / "data" / "05工作流中间产物" / "标注"
    sk_dir = data_root / "data" / "03索引标注条目"

    for fp in sorted(sk_dir.glob("01史记_*_skeleton.json")):
        n = migrate_json_file(fp, work="01史记")
        if n:
            stats["skeleton"] += n
            stats["files"] += 1
    for fp in sorted(mid.glob("01史记_*_blocks.json")):
        n = migrate_json_file(fp, work="01史记")
        if n:
            stats["blocks"] += n
            stats["files"] += 1
    for fp in sorted(mid.glob("01史记_*_protagonists.json")):
        n = migrate_json_file(fp, work="01史记")
        if n:
            stats["protagonists"] += n
            stats["files"] += 1
    return stats


if __name__ == "__main__":
    import os
    root = Path(os.environ.get("HISTOGRAPH_ROOT", "."))
    st = migrate_shiji_tree(root)
    print(json.dumps(st, ensure_ascii=False, indent=2))
