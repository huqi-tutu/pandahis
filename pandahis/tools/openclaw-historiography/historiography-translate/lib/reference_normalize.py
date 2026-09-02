"""参考著作节规范化（全库）。"""

from __future__ import annotations

import re
from typing import List

_INDEX_FILE_REF = re.compile(r"^《?\d{2}[^》·]+》?$")
_GARBAGE_PREFIX = re.compile(r"^《0?\d+")


def normalize_reference_title(title: str) -> str:
    """《01史记》→《史记》；去掉索引文件名形态。"""
    t = str(title or "").strip()
    if not t:
        return t
    bare = t.strip("《》")
    if _GARBAGE_PREFIX.match(t) or _GARBAGE_PREFIX.match(f"《{bare}》"):
        bare = re.sub(r"^\d{2}", "", bare)
    if bare and not bare.startswith("《"):
        return f"《{bare}》"
    return t if t.startswith("《") else f"《{bare}》"


def normalize_reference_list(refs: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in refs:
        t = normalize_reference_title(str(raw).strip())
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def normalize_reference_section(detail: str) -> str:
    """规范化文末参考著作列表条目。"""
    if "参考著作" not in detail:
        return detail
    head, _, tail = detail.partition("参考著作")
    lines = tail.split("\n")
    if not lines:
        return detail
    prefix = lines[0].lstrip(":：").strip()
    body_lines = lines[1:] if prefix == "" else lines
    refs: List[str] = []
    for line in body_lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\d+\.\s*(.+)$", line)
        refs.append(m.group(1).strip() if m else line)
    if not refs and prefix:
        refs = [prefix]
    normed = normalize_reference_list(refs)
    if not normed:
        return detail
    ref_block = "参考著作：\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(normed, start=1))
    return head.rstrip() + "\n\n" + ref_block
