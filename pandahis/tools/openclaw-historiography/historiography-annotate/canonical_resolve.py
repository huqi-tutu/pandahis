#!/usr/bin/env python3
"""统一史略名称解析：帝王别名 + 宗戚别名 + 史略异名表 + merge 硬编码。

用于 merge_global_entries、identity_gate、V1↔V2 匹配、skeleton 标准名对齐。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from emperor_resolve import build_alias_to_canonical

SKILL_DIR = Path(__file__).resolve().parent
ALIAS_TABLE_JSON = SKILL_DIR / "reference" / "史略异名表.json"
ZONGQI_ALIAS_JSON = SKILL_DIR / "reference" / "宗戚别名.json"

# merge 遗留硬编码（逐步迁入史略异名表）
MERGE_HARDCODED: Dict[str, str] = {
    "项籍": "项羽",
    "陈涉": "陈胜",
    "蜀卓氏": "卓氏",
    "滕公（夏侯婴）": "汝阴侯夏侯婴",
}


@dataclass(frozen=True)
class ResolvedName:
    raw: str
    canonical: str
    source: str  # exact | alias_table | emperor | zongqi | zongqi_json | hardcoded | unchanged


def _repo_root() -> Path:
    return SKILL_DIR.parents[2]


def _zongqi_display_from_row(title: str, given: str) -> str:
    t, g = (title or "").strip(), (given or "").strip()
    if not t:
        return g
    if g and g not in t:
        return f"{t}{g}"
    return t


@lru_cache(maxsize=1)
def load_alias_table() -> dict:
    if not ALIAS_TABLE_JSON.is_file():
        return {"global": {}, "功臣标准名": {}}
    return json.loads(ALIAS_TABLE_JSON.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def build_unified_alias_map() -> Dict[str, str]:
    """标注名/异名 → 最终 canonical（merge key + 目标 display）。"""
    out: Dict[str, str] = {}

    # 1) 史略异名表 global（最高优先）
    cfg = load_alias_table()
    for alias, canonical in (cfg.get("global") or {}).items():
        a, c = str(alias).strip(), str(canonical).strip()
        if a and c:
            out[a] = c

    # 2) 功臣标准名：本名 → 侯号+本名
    for given, full in (cfg.get("功臣标准名") or {}).items():
        g, f = str(given).strip(), str(full).strip()
        if g and f:
            out.setdefault(g, f)
            out.setdefault(f, f)

    # 2b) 宗戚标准名：本名 → 王号+本名
    for given, full in (cfg.get("宗戚标准名") or {}).items():
        g, f = str(given).strip(), str(full).strip()
        if g and f:
            out.setdefault(g, f)
            out.setdefault(f, f)

    # 3) 宗戚别名.json
    if ZONGQI_ALIAS_JSON.is_file():
        zq = json.loads(ZONGQI_ALIAS_JSON.read_text(encoding="utf-8"))
        for alias, canonical in (zq.get("global") or {}).items():
            a, c = str(alias).strip(), str(canonical).strip()
            if a and c:
                out.setdefault(a, c)

    # 4) 宗戚.json：王号+本名
    zj_path = _repo_root() / "data" / "01历史坐标数据" / "宗戚.json"
    if zj_path.is_file():
        for row in json.loads(zj_path.read_text(encoding="utf-8")):
            title = str(row.get("宗戚名称") or "").strip()
            given = str(row.get("宗戚原名") or "").strip()
            display = _zongqi_display_from_row(title, given)
            if display:
                out.setdefault(display, display)
            if given and display:
                out.setdefault(given, display)
            if title and display:
                out.setdefault(title, display)

    # 5) 帝王别名
    for alias, canonical in build_alias_to_canonical().items():
        out.setdefault(alias, canonical)

    # 6) merge 硬编码
    for alias, canonical in MERGE_HARDCODED.items():
        out.setdefault(alias, canonical)

    return out


def resolve_canonical(name: str, *, category: str = "") -> ResolvedName:
    """将任意标注名解析为 canonical。"""
    raw = (name or "").strip()
    if not raw:
        return ResolvedName(raw="", canonical="", source="unchanged")

    alias_map = build_unified_alias_map()
    if raw in alias_map:
        c = alias_map[raw]
        src = "alias_table" if c != raw else "exact"
        return ResolvedName(raw=raw, canonical=c, source=src)

    return ResolvedName(raw=raw, canonical=raw, source="unchanged")


def resolve_display_name(name: str, *, category: str = "") -> str:
    """返回最终应写入 skeleton 的史略名称（若表中有标准名则替换）。"""
    return resolve_canonical(name, category=category).canonical


def same_person_key(name_a: str, name_b: str, *, category_a: str = "", category_b: str = "") -> bool:
    """两标注名是否指向同一 canonical 实体（不含 LLM 语义校验）。"""
    ca = resolve_canonical(name_a, category=category_a).canonical
    cb = resolve_canonical(name_b, category=category_b).canonical
    return bool(ca) and ca == cb


def is_approved_display(name: str) -> bool:
    """名称是否已在 SSOT 表中确认为最终 display（可直接写入 skeleton）。"""
    r = resolve_canonical(name)
    cfg = load_alias_table()
    approved = set((cfg.get("功臣标准名") or {}).values())
    approved.update(v for v in (cfg.get("global") or {}).values() if "王" in v or "侯" in v)
    return r.canonical in approved


def clear_cache() -> None:
    load_alias_table.cache_clear()
    build_unified_alias_map.cache_clear()
