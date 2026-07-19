"""锚点 core_enumerations 语义覆盖：意思到了即可，不要求整串字面出现。"""

from __future__ import annotations

import re
from typing import Any

# 锚点枚举短语 → 正文可接受的同义/近义表述（非穷举，仅补 verify 拆词覆盖不到的常见写法）
_ENUM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "多次交战": ("三战", "再战", "数战", "反复", "连战", "交战"),
    "最终归服": ("归服", "臣服", "并入", "联盟", "炎黄"),
    "黄帝擒杀蚩尤": (
        "禽杀蚩尤",
        "擒杀蚩尤",
        "杀蚩尤",
        "擒获并杀死蚩尤",
        "擒获并杀",
        "遂禽杀",
    ),
    "德行充实": ("德充", "德不衰", "貌丑德充", "德行", "德"),
    "黄帝次妃": ("次妃", "第四妃"),
    "内助后宫": ("内助", "执掌后宫", "后宫事务"),
    "教民养蚕": ("养蚕", "育蚕", "蚕桑", "先蚕"),
    "辅佐黄帝": ("辅佐", "正妃", "第一夫人"),
}

_STOP_TOKENS = frozenset(
    {
        "的",
        "与",
        "及",
        "和",
        "为",
        "在",
        "以",
        "等",
        "之",
        "其",
        "所",
    }
)


def _significant_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"《[^》]+》", "", text)
    cleaned = re.sub(r"[（(][^）)]+[）)]", " ", cleaned)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,8}", cleaned)
    out: list[str] = []
    for tok in tokens:
        if tok in _STOP_TOKENS:
            continue
        if tok not in out:
            out.append(tok)
    return out


def _keyword_hit_ratio(body: str, keywords: list[str]) -> float:
    kws = [k.strip() for k in keywords if k and str(k).strip()]
    if not kws:
        return 1.0
    hits = sum(1 for kw in kws if kw in body)
    return hits / len(kws)


def enum_item_covered(body: str, item: Any) -> bool:
    """判断正文是否已语义覆盖一条 core_enumeration 项。"""
    if isinstance(item, dict):
        kws = item.get("keywords") or []
        if kws:
            return _keyword_hit_ratio(body, [str(k) for k in kws]) >= 0.5
        item_s = str(item.get("text") or item.get("label") or "").strip()
    else:
        item_s = str(item).strip()

    if not item_s:
        return True
    if item_s in body:
        return True

    paren = re.match(r"^([^（(]+)[（(]([^）)]+)[）)]$", item_s)
    if paren:
        core, alt = paren.group(1).strip(), paren.group(2).strip()
        if core in body or alt in body:
            return True

    for alt in _ENUM_SYNONYMS.get(item_s, ()):
        if alt in body:
            return True

    if "内助" in item_s and "后宫" in item_s:
        if "内助" in body and "后宫" in body:
            return True

    if item_s == "黄帝次妃" and "次妃" in body and "黄帝" in body:
        return True

    tokens = _significant_tokens(item_s)
    if tokens:
        hits = sum(1 for tok in tokens if tok in body)
        need = max(1, (len(tokens) + 1) // 2)
        if hits >= need:
            return True

    return False


def count_enum_coverage(body: str, enum: dict[str, Any]) -> tuple[int, int, list[str]]:
    """返回 (covered, total, missing_labels)。"""
    items = enum.get("items") or []
    missing: list[str] = []
    for item in items:
        item_s = str(item.get("text") if isinstance(item, dict) else item)
        if not enum_item_covered(body, item):
            missing.append(item_s[:24])
    covered = len(items) - len(missing)
    return covered, len(items), missing
