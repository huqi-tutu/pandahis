#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2 详情路径分流：顺译 skill → compose-detail；西汉暂不处理。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V2_INDEX = DATA / "10新标注条目" / "史略索引_史记汉书.json"
T11 = DATA / "11新标注条目翻译"
T04 = DATA / "04史料翻译"
T06 = DATA / "06朝代知识补全" / "详情"

TRANSLATION_VERSION_V2 = "v2"

EXCLUDE_DYNASTIES = frozenset({"西汉"})
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 9}


def load_v2() -> list[dict[str, Any]]:
    return json.loads(V2_INDEX.read_text(encoding="utf-8"))


def _load_11_doc(fp: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def is_valid_v2_11_doc(doc: dict[str, Any]) -> bool:
    """V2 顺译成稿：版本标记 + 正文 + 史料原文。"""
    if str(doc.get("翻译版本") or "") != TRANSLATION_VERSION_V2:
        return False
    if not str(doc.get("翻译详情") or "").strip():
        return False
    if not str(doc.get("史料原文") or "").strip():
        return False
    return True


def has_11_legacy(eid: str) -> bool:
    """11 目录内旧迁移/补丁产出（无 v2 版本字段但有正文）。"""
    for fp in T11.glob(f"{eid}_*.json"):
        if fp.name in {"翻译复用清单.json"}:
            continue
        doc = _load_11_doc(fp)
        if doc and str(doc.get("翻译详情") or "").strip() and not doc.get("翻译版本"):
            return True
    return False


def has_11(eid: str) -> bool:
    """V2 顺译 skill 有效成稿（strict）。"""
    for fp in T11.glob(f"{eid}_*.json"):
        if fp.name in {"翻译复用清单.json"}:
            continue
        doc = _load_11_doc(fp)
        if doc and is_valid_v2_11_doc(doc):
            return True
    return False


def has_06(eid: str) -> bool:
    return any(T06.glob(f"{eid}_*.json"))


def has_detail(eid: str) -> bool:
    return has_11(eid) or has_11_legacy(eid) or has_06(eid)


def has_04_detail(eid: str) -> bool:
    for fp in T04.glob(f"{eid}_*.json"):
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
            if (doc.get("翻译详情") or "").strip():
                return True
        except (json.JSONDecodeError, OSError):
            continue
    return False


def has_mother(entry: dict[str, Any]) -> bool:
    if (entry.get("原文字句") or "").strip():
        return True
    return any(p.get("role") == "母本" for p in (entry.get("paragraphs") or []))


def translate_eligible(entry: dict[str, Any]) -> bool:
    src = str(entry.get("史略来源") or "史料提取")
    return src == "史料提取" and has_mother(entry)


def route_entry(entry: dict[str, Any]) -> str | None:
    """返回路径：translate | compose | skip_done | skip_xihan | None

    V1 04 顺译不复用，仅作留档；满足顺译条件的条目一律走 translate skill 写入 11。
    """
    dynasty = str(entry.get("二级朝代坐标") or "")
    if dynasty in EXCLUDE_DYNASTIES:
        return "skip_xihan"
    eid = str(entry.get("史略ID") or "").strip()
    if not eid:
        return None
    if has_detail(eid):
        return "skip_done"
    if translate_eligible(entry):
        return "translate"
    return "compose"


def queue_row(entry: dict[str, Any], path: str) -> dict[str, Any]:
    eid = str(entry["史略ID"])
    has04 = has_04_detail(eid)
    return {
        "史略ID": entry["史略ID"],
        "史略名称": entry.get("史略名称"),
        "二级朝代坐标": entry.get("二级朝代坐标"),
        "史略分类": entry.get("史略分类"),
        "优先级": entry.get("优先级") or "",
        "史略来源": entry.get("史略来源") or "",
        "路径": path,
        "有母本": has_mother(entry),
        "V1有04留档": has04,
        "备注": "V1 04 不复用，须重译至 11" if has04 and path == "translate" else "",
    }


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            PRIORITY_ORDER.get(str(r.get("优先级") or ""), 9),
            str(r.get("二级朝代坐标") or ""),
            str(r.get("史略ID") or ""),
        ),
    )


def build_queues() -> dict[str, Any]:
    translate: list[dict] = []
    compose: list[dict] = []
    skipped: dict[str, int] = {}
    v1_04_retranslate = 0

    for entry in load_v2():
        path = route_entry(entry)
        if path is None:
            continue
        if path.startswith("skip"):
            skipped[path] = skipped.get(path, 0) + 1
            continue
        row = queue_row(entry, path)
        if path == "translate":
            if row.get("V1有04留档"):
                v1_04_retranslate += 1
            translate.append(row)
        else:
            compose.append(row)

    return {
        "policy": {
            "exclude_dynasties": sorted(EXCLUDE_DYNASTIES),
            "order": ["translate", "compose"],
            "v1_04_policy": "04史料翻译仅留档，禁止 promote 至 11；须 translate skill 重译",
            "note": "西汉之前无详情：先顺译至 11，不满足顺译条件才 compose",
        },
        "translate": sort_rows(translate),
        "compose": sort_rows(compose),
        "skipped": skipped,
        "counts": {
            "translate": len(translate),
            "translate_with_v1_04留档": v1_04_retranslate,
            "compose": len(compose),
        },
    }
