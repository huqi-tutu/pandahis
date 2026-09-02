"""Baseline 成篇：程序拼接 B 正文 + C 头尾。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from lib.phase2_batch import append_reference_section


def assemble_baseline_detail(
    *,
    intro: str,
    body: str,
    tail: str,
    plan_data: Dict[str, Any],
    recalled: Dict[str, Any],
) -> str:
    intro = (intro or "").strip()
    body = (body or "").strip()
    tail = (tail or "").strip()
    if intro and body.startswith(intro):
        body = body[len(intro) :].lstrip()
    parts = [p for p in (intro, body, tail) if p]
    core = "\n\n".join(parts)
    return append_reference_section(core, plan_data, recalled)


def write_baseline_file(
    path: Path,
    entry_id: str,
    *,
    intro: str,
    body: str,
    tail: str,
    plan_data: Dict[str, Any],
    recalled: Dict[str, Any],
    translation_version: str = "baseline_ready",
) -> str:
    detail = assemble_baseline_detail(
        intro=intro,
        body=body,
        tail=tail,
        plan_data=plan_data,
        recalled=recalled,
    )
    doc = {
        "史略ID": entry_id,
        "前置引入": intro.strip(),
        "正文": body.strip(),
        "结尾": tail.strip(),
        "翻译详情": detail,
        "翻译版本": translation_version,
        "_pipeline_meta": {"stage": "baseline_ready", "mode": "abcd"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return detail


def load_baseline_parts(path: Path) -> Tuple[str, str, str, str]:
    """intro, body, tail, full detail"""
    if not path.is_file():
        return "", "", "", ""
    data = json.loads(path.read_text(encoding="utf-8"))
    intro = str(data.get("前置引入") or "").strip()
    body = str(data.get("正文") or data.get("母本顺译") or "").strip()
    tail = str(data.get("结尾") or "").strip()
    detail = str(data.get("翻译详情") or "").strip()
    if not detail and body:
        detail = "\n\n".join(p for p in (intro, body, tail) if p)
    return intro, body, tail, detail
