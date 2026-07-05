#!/usr/bin/env python3
"""Step1a LLM 主轴元数据：卷型/人数写入 skeleton，供硬检引用（非脚本书名推断）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib_config import paths


def _protagonists_path(work: str, vol: str) -> Path:
    vol = vol.zfill(3)
    return paths()["annotate_work"] / f"{work}_{vol}_protagonists.json"


def parse_work_vol_from_skeleton(skeleton_path: Path) -> Tuple[Optional[str], Optional[str]]:
    m = re.match(r"^(\d{2}[^_]+)_(\d{3})_", skeleton_path.name)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def load_protagonists_manifest(
    work: str,
    vol: str,
) -> Optional[dict]:
    fp = _protagonists_path(work, vol)
    if not fp.is_file():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def protagonist_count_from_manifest(manifest: Optional[dict]) -> Optional[int]:
    if not manifest:
        return None
    items = manifest.get("protagonists")
    if not isinstance(items, list):
        return None
    return len(items)


def merge_protagonist_metadata(
    data: dict,
    work: str,
    vol: str,
    *,
    manifest: Optional[dict] = None,
) -> dict:
    """将 Step1a LLM 卷型/主轴人数写入 skeleton（不覆盖已有 llm 字段）。"""
    manifest = manifest if manifest is not None else load_protagonists_manifest(work, vol)
    if not manifest:
        return data

    out = dict(data)
    guess = (manifest.get("volume_type_guess") or "").strip()
    if guess and not (out.get("volume_subtype") or "").strip():
        out["volume_subtype"] = guess
        out["volume_subtype_source"] = "llm_step1a"

    n = protagonist_count_from_manifest(manifest)
    if n is not None:
        out["protagonist_count"] = n
        out["protagonist_count_source"] = "llm_step1a"

    rationales = []
    for item in manifest.get("protagonists") or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        rat = (item.get("rationale") or "").strip()
        rationales.append({"name": name, "category": item.get("category"), "rationale": rat})
    if rationales and not out.get("protagonists_manifest"):
        out["protagonists_manifest"] = rationales

    return out


def expected_protagonist_count(
    data: dict,
    skeleton_path: Path,
) -> Tuple[Optional[int], str]:
    """
    返回 (主轴人数, 来源说明)。
    优先 skeleton 内 LLM 写入字段，其次 protagonists.json。
    """
    if isinstance(data.get("protagonist_count"), int):
        src = data.get("protagonist_count_source") or "skeleton"
        return int(data["protagonist_count"]), str(src)

    work, vol = parse_work_vol_from_skeleton(skeleton_path)
    if not work or not vol:
        return None, "unknown"
    manifest = load_protagonists_manifest(work, vol)
    n = protagonist_count_from_manifest(manifest)
    if n is not None:
        return n, "llm_step1a_file"
    return None, "missing"
