"""本篇对照表今地：只验收表内已知地名的首次标注，不是二十四史全库。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional

_TABLE_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.M,
)
_SPLIT_NAMES = re.compile(r"[\/／、,，]+")
_OPTIONAL_MARK = re.compile(r"可不标|古今同名")
# 复合专名：鸿门宴、广武涧 等，首次命中不要求在「宴/涧」前插今地
_TITLE_SUFFIX = re.compile(r"^(君|侯|王|津|公|将|相|宴|涧|道)")


def gazetteer_markdown_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "historiography-compose"
        / "references"
        / "古地名今地对照.md"
    )


def parse_gazetteer_markdown(text: str) -> List[dict]:
    """解析对照表。单字地名、标明可不标的不进扫描清单。"""
    rows: List[dict] = []
    seen: set[str] = set()
    for m in _TABLE_ROW.finditer(text or ""):
        raw_names = m.group(1).strip()
        loc = m.group(2).strip()
        if raw_names in {"古地名", "--------"} or loc.startswith("-"):
            continue
        optional = bool(_OPTIONAL_MARK.search(loc))
        if optional:
            continue
        for name in _SPLIT_NAMES.split(raw_names):
            name = name.strip()
            if len(name) < 2 or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "now": loc})
    rows.sort(key=lambda r: len(r["name"]), reverse=True)
    return rows


@lru_cache(maxsize=1)
def load_gazetteer() -> List[dict]:
    path = gazetteer_markdown_path()
    if not path.is_file():
        return []
    return parse_gazetteer_markdown(path.read_text(encoding="utf-8"))


def _inside_now_paren(body: str, idx: int) -> bool:
    """命中落在已有（今…）夹注内部，不算地名首次出现。"""
    start = max(0, idx - 48)
    chunk = body[start:idx]
    pos = -1
    for token in ("（今", "(今"):
        p = chunk.rfind(token)
        if p > pos:
            pos = p
    if pos < 0:
        return False
    abs_open = start + pos
    closer_cn = body.find("）", abs_open)
    closer_en = body.find(")", abs_open)
    closers = [c for c in (closer_cn, closer_en) if c >= 0]
    if not closers:
        return True
    return min(closers) > idx


def missing_first_now_places(
    detail: str,
    *,
    gazetteer: Optional[Iterable[dict]] = None,
    window: int = 32,
) -> List[str]:
    """成稿里对照表地名首次出现却未紧跟（今…）的名单（最长名优先，避免短名误伤）。"""
    rows = list(gazetteer) if gazetteer is not None else load_gazetteer()
    body = str(detail or "")
    missing: List[str] = []
    occupied: List[tuple[int, int]] = []
    for row in rows:
        name = str(row.get("name") or "")
        if len(name) < 2:
            continue
        start = 0
        while True:
            idx = body.find(name, start)
            if idx < 0:
                break
            if any(a <= idx < b for a, b in occupied):
                start = idx + len(name)
                continue
            if _inside_now_paren(body, idx):
                start = idx + len(name)
                continue
            rest = body[idx + len(name) :]
            if _TITLE_SUFFIX.match(rest):
                start = idx + len(name)
                continue
            occupied.append((idx, idx + len(name)))
            after = rest[:window]
            if after.startswith("（今") or after.startswith("(今"):
                break
            # 允许短复合地名后标注：丰邑中阳里人（今…）
            if re.match(r"^[\u4e00-\u9fff·・]{0,16}[（(]今", after):
                break
            missing.append(name)
            break
    return missing
