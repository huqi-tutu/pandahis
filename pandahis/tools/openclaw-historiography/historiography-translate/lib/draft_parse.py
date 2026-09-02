"""从 LLM 落盘 JSON 提取正文字段（兼容 翻译详情 内嵌 markdown JSON）。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List


def _unwrap_markdown_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _nested_candidates(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    nested = data.get("翻译详情")
    if isinstance(nested, dict):
        out.append(nested)
    elif isinstance(nested, str):
        text = _unwrap_markdown_json(nested)
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    out.append(parsed)
            except json.JSONDecodeError:
                pass
    return out


def extract_draft_body(data: Dict[str, Any], *field_names: str) -> str:
    """按优先级从顶层或嵌套 JSON 提取第一个非空字段。"""
    names = field_names or ("翻译详情",)
    for inner in _nested_candidates(data):
        for k in names:
            if k == "翻译详情":
                continue
            v = str(inner.get(k) or "").strip()
            if v:
                return v
    for k in names:
        v = str(data.get(k) or "").strip()
        if not v:
            continue
        if k != "翻译详情" and not v.startswith("```"):
            return v
        if k == "翻译详情":
            unwrapped = _unwrap_markdown_json(v)
            if unwrapped.startswith("{"):
                try:
                    parsed = json.loads(unwrapped)
                    if isinstance(parsed, dict):
                        for fk in names:
                            if fk == "翻译详情":
                                continue
                            fv = str(parsed.get(fk) or "").strip()
                            if fv:
                                return fv
                except json.JSONDecodeError:
                    pass
            if not v.startswith("```"):
                return v
    return ""
