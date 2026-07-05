"""朝代名解析与 朝代.json 自动对齐（SSOT：朝代.json）。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from coordinate_index import (
    DYNASTY_JSON,
    EMPEROR_JSON,
    build_dynasty_index_from_json,
    emperor_row_name,
    load_emperor_records,
    make_dynasty_id,
    resolve_civilization_id,
)
from emperor_resolve import infer_civilization_for_dynasty

SKILL_DIR = Path(__file__).resolve().parent
ALIAS_JSON = SKILL_DIR / "reference" / "朝代别名.json"

# 常见 LLM 别称 → 朝代.json 标准名
_BUILTIN_DYNASTY_ALIASES: Dict[str, str] = {
    "殷商": "商",
    "殷": "商",
    "商朝": "商",
    "商代": "商",
    "东周朝": "东周",
}


def _load_alias_map() -> Dict[str, str]:
    mapping = dict(_BUILTIN_DYNASTY_ALIASES)
    if ALIAS_JSON.exists():
        with open(ALIAS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for alias, canonical in (data.get("global") or {}).items():
            a, c = str(alias).strip(), str(canonical).strip()
            if a and c:
                mapping[a] = c
    return mapping


def canonical_dynasty(
    dynasty: str,
    dynasty_index: Optional[Dict[str, dict]] = None,
    alias_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    将标注/帝王表中的朝代名规范为 朝代.json 标准名。
    - 已在表中 → 原样
    - 别名表（殷商→商等）→ 标准名
    - 仍不在表中 → 原样（留给 auto_supplement 补录）
    """
    dynasty = (dynasty or "").strip()
    if not dynasty:
        return dynasty

    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    if dynasty in di:
        return dynasty

    amap = alias_map if alias_map is not None else _load_alias_map()
    if dynasty in amap:
        canonical = amap[dynasty].strip()
        if canonical in di:
            return canonical

    return dynasty


def _norm_key(key: str) -> str:
    return key.lstrip("\ufeff").strip()


def _load_emperor_rows(path: Path) -> List[dict]:
    with open(path, encoding="utf-8-sig") as f:
        raw_rows = json.load(f)
    return [{_norm_key(k): v for k, v in raw.items()} for raw in raw_rows]


def _load_dynasty_rows(path: Path) -> List[dict]:
    with open(path, encoding="utf-8-sig") as f:
        raw_rows = json.load(f)
    return [{_norm_key(k): v for k, v in raw.items()} for raw in raw_rows]


def normalize_emperor_json_dynasties(
    *,
    emperor_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    """将帝王.json 中可规范化的朝代别名改为 朝代.json 标准名。"""
    ep = emperor_path or EMPEROR_JSON
    rows = _load_emperor_rows(ep)
    di = build_dynasty_index_from_json()
    amap = _load_alias_map()
    patched = 0
    logs: List[str] = []

    for row in rows:
        old = (row.get("朝代") or "").strip()
        if not old:
            continue
        new = canonical_dynasty(old, di, amap)
        if new != old:
            row["朝代"] = new
            patched += 1
            emperor = emperor_row_name(row) or "?"
            logs.append(f"帝王表「{emperor}」朝代 {old} → {new}")

    if patched and not dry_run:
        with open(ep, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return patched, logs


def canonicalize_entry_dynasty_coords(
    entry: dict,
    dynasty_index: Optional[Dict[str, dict]] = None,
    alias_map: Optional[Dict[str, str]] = None,
) -> bool:
    """就地规范 skeleton 条目二级朝代坐标。"""
    di = dynasty_index if dynasty_index is not None else build_dynasty_index_from_json()
    amap = alias_map if alias_map is not None else _load_alias_map()
    old = (entry.get("二级朝代坐标") or "").strip()
    if not old:
        return False
    new = canonical_dynasty(old, di, amap)
    if new == old:
        return False
    entry["二级朝代坐标"] = new
    auto = entry.get("_auto_filled")
    if isinstance(auto, dict) and auto.get("二级朝代坐标") == old:
        auto["二级朝代坐标"] = new
    return True


def collect_dynasty_hints_from_skeleton(data: dict) -> Dict[str, dict]:
    hints: Dict[str, dict] = {}
    di = build_dynasty_index_from_json()
    amap = _load_alias_map()

    for entry in data.get("entries", []):
        auto = entry.get("_auto_filled") or {}
        raw = (entry.get("二级朝代坐标") or auto.get("二级朝代坐标") or "").strip()
        dynasty = canonical_dynasty(raw, di, amap)
        if not dynasty:
            continue
        bucket = hints.setdefault(
            dynasty,
            {"civilizations": Counter(), "starts": [], "ends": []},
        )
        civ = (entry.get("一级文明坐标") or auto.get("一级文明坐标") or "").strip()
        if civ:
            bucket["civilizations"][civ] += 1
        for key in ("史略开始年", "史略结束年"):
            val = entry.get(key)
            if isinstance(val, int):
                if key.endswith("开始年"):
                    bucket["starts"].append(val)
                else:
                    bucket["ends"].append(val)

    return hints


def _extend_dynasty_hints_from_emperors(hints: Dict[str, dict]) -> None:
    if not hints:
        return
    targets = set(hints.keys())
    di = build_dynasty_index_from_json()
    amap = _load_alias_map()
    for info in load_emperor_records():
        raw = (info.get("dynasty") or "").strip()
        dynasty = canonical_dynasty(raw, di, amap)
        if dynasty not in targets:
            continue
        bucket = hints[dynasty]
        civ = (info.get("civilization") or "").strip()
        if civ:
            bucket["civilizations"][civ] += 1
        if info.get("start_year") is not None:
            bucket["starts"].append(info["start_year"])
        if info.get("end_year") is not None:
            bucket["ends"].append(info["end_year"])


def _fmt_dynasty_year(value: Optional[int]) -> str:
    if value is None:
        return "-"
    return str(value)


def draft_dynasty_row(dynasty: str, bucket: dict) -> dict:
    civ = (
        bucket["civilizations"].most_common(1)[0][0]
        if bucket["civilizations"]
        else infer_civilization_for_dynasty(dynasty)
    )
    civ_id = resolve_civilization_id(civ)
    start = min(bucket["starts"]) if bucket["starts"] else None
    end = max(bucket["ends"]) if bucket["ends"] else None
    return {
        "朝代": dynasty,
        "朝代ID": make_dynasty_id(civ_id, dynasty),
        "文明": civ,
        "文明ID": civ_id,
        "开始时间": _fmt_dynasty_year(start),
        "结束时间": _fmt_dynasty_year(end),
    }


def auto_supplement_dynasties_from_skeleton(
    data: dict,
    *,
    dynasty_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, List[str]]:
    """skeleton/帝王引用的朝代若不在 朝代.json → 自动补录。"""
    dp = dynasty_path or DYNASTY_JSON
    rows = _load_dynasty_rows(dp)
    existing = {(r.get("朝代") or "").strip() for r in rows}

    hints = collect_dynasty_hints_from_skeleton(data)
    _extend_dynasty_hints_from_emperors(hints)

    added = 0
    logs: List[str] = []
    for dynasty in sorted(hints):
        if dynasty in existing:
            continue
        draft = draft_dynasty_row(dynasty, hints[dynasty])
        rows.append(draft)
        existing.add(dynasty)
        added += 1
        logs.append(
            f"自动补录朝代「{dynasty}」({draft['文明']} "
            f"{draft['开始时间']}～{draft['结束时间']})"
        )

    if added and not dry_run:
        with open(dp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return added, logs


def auto_normalize_dynasty_reference(
    data: dict,
    *,
    emperor_path: Optional[Path] = None,
    dynasty_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """
    Step4 前自动对齐朝代 reference：
    1) 修补帝王.json 朝代别名
    2) 从 skeleton 补录缺失朝代到 朝代.json
    3) 规范 skeleton 二级朝代坐标
    """
    logs: List[str] = []
    emp_n, emp_logs = normalize_emperor_json_dynasties(
        emperor_path=emperor_path, dry_run=dry_run
    )
    logs.extend(emp_logs)

    reg_n, reg_logs = auto_supplement_dynasties_from_skeleton(
        data, dynasty_path=dynasty_path, dry_run=dry_run
    )
    logs.extend(reg_logs)

    di = build_dynasty_index_from_json()
    amap = _load_alias_map()
    sk_n = 0
    for entry in data.get("entries", []):
        if canonicalize_entry_dynasty_coords(entry, di, amap):
            sk_n += 1
            logs.append(f"skeleton [{entry.get('史略ID')}] 朝代坐标已规范")

    return emp_n, reg_n, sk_n, logs
