#!/usr/bin/env python3
"""修复 reference/帝王.json：P0 拼音撞 ID 加序号、P1 同人去重、P2 多次在位合并、P3 同名消歧。"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from coordinate_index import EMPEROR_JSON, parse_year_value, validate_emperor_records

SKILL_DIR = Path(__file__).resolve().parent
SYNC_TARGETS = [
    SKILL_DIR / "reference" / "帝王.json",
    Path.home() / "Desktop" / "padanhis" / "pandahis" / "pandahis" / "data" / "帝王.json",
]
ALIAS_JSON = SKILL_DIR / "reference" / "帝王别名.json"
REPORT_DIR = SKILL_DIR / "reference" / "audit"

# P3：帝王名称消歧（ID 已分时，索引仍按名称建键，须改显示名）
P3_RENAME: Dict[str, str] = {
    "蜀后主|三国·蜀|刘禅": "蜀后主",
    "蜀后主|十国·前蜀|王衍": "前蜀后主",
    "蜀后主|十国·后蜀|孟昶": "后蜀后主",
    "汉少帝|东汉|刘懿": "少帝刘懿",
    "汉少帝|东汉|刘辩": "少帝刘辩",
}


def _row_key(row: dict) -> str:
    return "|".join([
        row.get("帝王名称", ""),
        row.get("政权", ""),
        (row.get("帝王原名") or "").replace("（第一次在位）", "").strip(),
    ])


def _sort_year(row: dict) -> int:
    y = parse_year_value(row.get("即位时间"))
    return y if y is not None else 9_999_999


def _rating(row: dict) -> int:
    try:
        return int(row.get("重要性评级") or 0)
    except (TypeError, ValueError):
        return 0


def _merge_tags(rows: List[dict]) -> str:
    parts: List[str] = []
    seen: set[str] = set()
    for r in rows:
        raw = (r.get("标签") or "").strip()
        if not raw:
            continue
        for piece in raw.replace("，", ",").split(","):
            p = piece.strip()
            if p and p not in seen:
                seen.add(p)
                parts.append(p)
    return ",".join(parts)


def merge_emperor_rows(rows: List[dict]) -> dict:
    """同人多条合并为一条：取最优字段 + 在位年取包络。"""
    rows = sorted(rows, key=lambda r: (_sort_year(r), -_rating(r)))
    base = max(rows, key=lambda r: (_rating(r), len(r.get("标签") or ""), -_sort_year(r)))
    merged = dict(base)

    starts = [parse_year_value(r.get("即位时间")) for r in rows]
    ends = [parse_year_value(r.get("退位时间")) for r in rows]
    valid_starts = [s for s in starts if s is not None]
    valid_ends = [e for e in ends if e is not None]
    if valid_starts:
        merged["即位时间"] = str(min(valid_starts))
    if valid_ends:
        merged["退位时间"] = str(max(valid_ends))
    if valid_starts and valid_ends:
        span = max(valid_ends) - min(valid_starts)
        if span >= 0:
            merged["在位时长"] = str(span if span > 0 else "0.2")

    given = merged.get("帝王原名") or ""
    if "（第一次在位）" in given:
        merged["帝王原名"] = given.replace("（第一次在位）", "").strip()

    tags = _merge_tags(rows)
    if tags:
        merged["标签"] = tags
    merged["重要性评级"] = str(max(_rating(r) for r in rows))
    return merged


def _normalize_orig_name(name: str) -> str:
    return (
        name.replace("（第一次在位）", "")
        .strip()
        .replace("彊", "强")
    )


def _orig_same_person(origs: set[str]) -> bool:
    """原名差异是否仍指同一人（如 田因齐/因齐、田辟强/辟彊）。"""
    cleaned = sorted({_normalize_orig_name(o) for o in origs if o.strip()})
    if len(cleaned) <= 1:
        return True
    for i, a in enumerate(cleaned):
        for b in cleaned[i + 1 :]:
            if a == b or a in b or b in a:
                continue
            if len(a) >= 2 and len(b) >= 2 and a[-2:] == b[-2:]:
                continue
            if len(a) > 2 and a[1:] == b:
                continue
            if len(b) > 2 and b[1:] == a:
                continue
            return False
    return True


def apply_p0_suffixes(records: List[dict]) -> List[str]:
    """拼音 ID 相同的多人：按即位时间加 1、2… 后缀。"""
    logs: List[str] = []
    by_id: Dict[str, List[Tuple[int, dict]]] = defaultdict(list)
    for i, row in enumerate(records):
        by_id[row["帝王ID"]].append((i, row))

    for eid, items in by_id.items():
        if len(items) <= 1:
            continue
        names = {(r.get("帝王名称") or "") for _, r in items}
        origs = {(r.get("帝王原名") or "").replace("（第一次在位）", "").strip() for _, r in items}
        # 同人多次在位 / 同人多条录入 → P1 合并，不拆 ID
        if len(names) == 1 and _orig_same_person(origs):
            continue
        ordered = sorted(items, key=lambda x: _sort_year(x[1]))
        for n, (idx, row) in enumerate(ordered, start=1):
            new_id = f"{eid}{n}"
            if row["帝王ID"] != new_id:
                old = row["帝王ID"]
                row["帝王ID"] = new_id
                logs.append(
                    f"P0 {row.get('帝王名称')}({row.get('帝王原名')}) "
                    f"{old} → {new_id} 即位={row.get('即位时间')}"
                )
    return logs


def apply_p3_renames(records: List[dict]) -> List[str]:
    logs: List[str] = []
    for row in records:
        key = _row_key(row)
        new_name = P3_RENAME.get(key)
        if new_name and row.get("帝王名称") != new_name:
            old = row["帝王名称"]
            row["帝王名称"] = new_name
            logs.append(f"P3 {old} → {new_name} [{row.get('政权')}]")
    return logs


def _person_key(row: dict) -> Tuple[str, str, str]:
    given = (row.get("帝王原名") or "").replace("（第一次在位）", "").strip()
    return (
        (row.get("帝王名称") or "").strip(),
        (row.get("政权") or "").strip(),
        given,
    )


def _prefer_id(ids: List[str]) -> str:
    """同人多条时优先无 _2/_3 后缀的 ID。"""
    clean = [i for i in ids if not re.search(r"_\d+$", i)]
    pool = clean or ids
    return sorted(pool, key=len)[0]


def dedupe_by_person(records: List[dict]) -> Tuple[List[dict], List[str]]:
    """同人同政权重复录入（帝王ID 不同）→ 合并。"""
    logs: List[str] = []
    groups: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)
    for row in records:
        groups[_person_key(row)].append(row)

    out: List[dict] = []
    for key, rows in groups.items():
        if len(rows) == 1:
            out.append(rows[0])
            continue
        ids = [r["帝王ID"] for r in rows]
        if len(set(ids)) == 1:
            merged = merge_emperor_rows(rows)
            logs.append(f"P1 合并 {key[0]}@{key[1]} ×{len(rows)}")
            out.append(merged)
            continue
        merged = merge_emperor_rows(rows)
        merged["帝王ID"] = _prefer_id(ids)
        logs.append(
            f"P1 同人合并 {key[0]}@{key[1]} IDs={ids} → {merged['帝王ID']}"
        )
        out.append(merged)
    return out, logs


def dedupe_by_id(records: List[dict]) -> Tuple[List[dict], List[str]]:
    """P1/P2：同一帝王ID 多条 → 合并一条。"""
    logs: List[str] = []
    groups: Dict[str, List[dict]] = defaultdict(list)
    order: List[str] = []
    for row in records:
        eid = row["帝王ID"]
        if eid not in groups:
            order.append(eid)
        groups[eid].append(row)

    out: List[dict] = []
    for eid in order:
        rows = groups[eid]
        if len(rows) == 1:
            out.append(rows[0])
            continue
        merged = merge_emperor_rows(rows)
        logs.append(
            f"P1/P2 合并 {eid} ×{len(rows)} → {merged.get('帝王名称')} "
            f"{merged.get('即位时间')}～{merged.get('退位时间')}"
        )
        out.append(merged)
    return out, logs


def update_aliases() -> List[str]:
    logs: List[str] = []
    if not ALIAS_JSON.is_file():
        return logs
    data = json.loads(ALIAS_JSON.read_text(encoding="utf-8"))
    g = data.setdefault("global", {})
    alias_add = {
        "蜀后主": "蜀后主",
        "后主": "蜀后主",
        "刘禅": "蜀后主",
        "王衍": "前蜀后主",
        "孟昶": "后蜀后主",
        "汉少帝": "少帝刘辩",
        "少帝": "少帝刘辩",
        "刘辩": "少帝刘辩",
        "刘懿": "少帝刘懿",
        "仲康": "仲康",
        "中康": "中康",
    }
    for alias, canonical in alias_add.items():
        if g.get(alias) != canonical:
            g[alias] = canonical
            logs.append(f"别名 {alias} → {canonical}")
    ALIAS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return logs


def repair(records: List[dict]) -> Tuple[List[dict], List[str]]:
    logs: List[str] = []
    logs.extend(apply_p0_suffixes(records))
    logs.extend(apply_p3_renames(records))
    records, dedupe_logs = dedupe_by_id(records)
    logs.extend(dedupe_logs)
    records, person_logs = dedupe_by_person(records)
    logs.extend(person_logs)
    return records, logs


def write_records(records: List[dict]) -> None:
    payload = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    for path in SYNC_TARGETS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def main() -> int:
    src = EMPEROR_JSON
    records = json.loads(src.read_text(encoding="utf-8"))
    before = len(records)

    backup = src.with_name(f"_backup_帝王_{datetime.now():%Y%m%d_%H%M%S}.json")
    shutil.copy2(src, backup)

    repaired, logs = repair(records)
    errs = validate_emperor_records(repaired)
    if errs:
        print("⛔ 修复后校验失败，未写入：")
        for e in errs[:20]:
            print(f"  - {e}")
        shutil.copy2(backup, src)
        return 1

    write_records(repaired)
    alias_logs = update_aliases()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / "帝王ID去重修复报告.md"
    lines = [
        "# 帝王.json ID 去重修复报告",
        "",
        f"- 备份：`{backup.name}`",
        f"- 修复前：**{before}** 条",
        f"- 修复后：**{len(repaired)}** 条",
        f"- 删除重复：**{before - len(repaired)}** 条",
        "",
        "## 操作日志",
        "",
    ]
    for line in logs + alias_logs:
        lines.append(f"- {line}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"✅ 帝王.json 修复完成：{before} → {len(repaired)} 条")
    print(f"   备份: {backup}")
    print(f"   报告: {report}")
    for path in SYNC_TARGETS:
        print(f"   已写入: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
