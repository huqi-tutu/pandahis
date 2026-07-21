#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""君王条目年份与帝王.json 对齐（SSOT）。

君王类：史略开始年=即位年，史略结束年=退位/崩年。
模型补全或同步时须强制覆盖，不得保留 LLM 自行推断的年份。
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_EMPEROR_JSON = (
    Path(__file__).resolve().parents[1] / "data" / "01历史坐标数据" / "帝王.json"
)


def parse_emperor_year(value: Any) -> int | None:
    """解析帝王.json 中的即位/退位年（支持 约-1919、-2698 等）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    if not s or s in ("-", "—", "未知", "不详"):
        return None
    if "至今" in s:
        return None
    s = re.sub(r"^[约\s]+", "", s, flags=re.I).strip()
    if s.lstrip("-").isdigit():
        return int(s)
    m = re.match(r"^(-?\d+)", s)
    return int(m.group(1)) if m else None


def load_emperor_rows(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or DEFAULT_EMPEROR_JSON
    return json.loads(p.read_text(encoding="utf-8"))


def build_emperor_indexes(
    rows: list[dict[str, Any]] | None = None,
    *,
    dynasty_id: str | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """按帝王名称、帝王ID 建索引；可按朝代过滤。"""
    data = rows if rows is not None else load_emperor_rows()
    by_name: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for row in data:
        if dynasty_id and str(row.get("朝代ID", "")).strip() != dynasty_id:
            continue
        eid = str(row.get("帝王ID", "")).strip()
        if eid:
            by_id[eid] = row
        for key in ("帝王名称", "帝王原名"):
            name = str(row.get(key, "")).strip()
            if name:
                by_name[name] = row
    return by_name, by_id


def resolve_emperor_row(
    entry: dict[str, Any],
    by_name: dict[str, dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    eid = str(entry.get("帝王ID") or "").strip()
    if eid and eid in by_id:
        return by_id[eid]
    for key in ("四级帝王坐标", "史略名称"):
        name = str(entry.get(key) or "").strip()
        if name and name in by_name:
            return by_name[name]
    return None


def junji_reign_years(emp_row: dict[str, Any]) -> tuple[int | None, int | None]:
    return (
        parse_emperor_year(emp_row.get("即位时间")),
        parse_emperor_year(emp_row.get("退位时间")),
    )


def align_junji_entry_years(
    entry: dict[str, Any],
    *,
    by_name: dict[str, dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    force: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """对齐单条君王条目；返回 (新条目, 变更说明列表)。"""
    if str(entry.get("史略分类", "")).strip() != "君王":
        return entry, []

    out = deepcopy(entry)
    emp = resolve_emperor_row(out, by_name, by_id)
    if not emp:
        return out, []

    reign_start, reign_end = junji_reign_years(emp)
    changes: list[str] = []
    eid = str(out.get("史略ID", "?"))
    name = str(out.get("史略名称", "?"))

    out["帝王ID"] = str(emp.get("帝王ID", out.get("帝王ID", ""))).strip()
    out["四级帝王坐标"] = str(emp.get("帝王名称", out.get("四级帝王坐标", ""))).strip()

    for label, ssot, field in (
        ("即位年", reign_start, "史略开始年"),
        ("退位年", reign_end, "史略结束年"),
    ):
        if ssot is None:
            continue
        old = out.get(field)
        if not force and old is not None:
            continue
        if old != ssot:
            changes.append(f"{eid} {name} {field}: {old} → {ssot}（帝王表{label}）")
            out[field] = ssot

    peak = out.get("峰值年")
    start = out.get("史略开始年")
    end = out.get("史略结束年")
    if isinstance(start, int) and isinstance(end, int) and isinstance(peak, int):
        lo, hi = min(start, end), max(start, end)
        if peak < lo or peak > hi:
            new_peak = start
            changes.append(f"{eid} {name} 峰值年: {peak} → {new_peak}（落入在位区间）")
            out["峰值年"] = new_peak

    if changes:
        auto = dict(out.get("_auto_filled") or {})
        auto["_君王年份SSOT"] = "帝王.json"
        auto["_君王年份对齐"] = changes
        out["_auto_filled"] = auto

    return out, changes


def align_junji_entries(
    entries: list[dict[str, Any]],
    *,
    dynasty_id: str | None = None,
    emperor_json: Path | None = None,
    force: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = load_emperor_rows(emperor_json)
    by_name, by_id = build_emperor_indexes(rows, dynasty_id=dynasty_id)
    out: list[dict[str, Any]] = []
    all_changes: list[str] = []
    for entry in entries:
        aligned, changes = align_junji_entry_years(
            entry,
            by_name=by_name,
            by_id=by_id,
            force=force,
        )
        out.append(aligned)
        all_changes.extend(changes)
    return out, all_changes


def validate_junji_years(
    entries: list[dict[str, Any]],
    *,
    dynasty_id: str | None = None,
    emperor_json: Path | None = None,
) -> list[str]:
    """校验君王条目是否与帝王表一致（gate 用）。"""
    rows = load_emperor_rows(emperor_json)
    by_name, by_id = build_emperor_indexes(rows, dynasty_id=dynasty_id)
    issues: list[str] = []
    for entry in entries:
        if str(entry.get("史略分类", "")).strip() != "君王":
            continue
        eid = str(entry.get("史略ID", "?"))
        name = str(entry.get("史略名称", "?"))
        emp = resolve_emperor_row(entry, by_name, by_id)
        if not emp:
            continue
        reign_start, reign_end = junji_reign_years(emp)
        start = entry.get("史略开始年")
        end = entry.get("史略结束年")
        if reign_start is not None and start != reign_start:
            issues.append(
                f"[{eid}] {name} 史略开始年 {start} ≠ 帝王表即位年 {reign_start}"
            )
        if reign_end is not None and end != reign_end:
            issues.append(
                f"[{eid}] {name} 史略结束年 {end} ≠ 帝王表退位年 {reign_end}"
            )
    return issues
