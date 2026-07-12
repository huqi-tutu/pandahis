"""通识文言禁释词表（L0）：顺译时直接融入白话，禁止「X就是Y」式注释。"""

from __future__ import annotations

import re
from typing import List

# L0：通识字词，直接顺译，禁止单独引号+解释
L0_GLOSS_WORDS = frozenset(
    {
        "崩",
        "薨",
        "卒",
        "殂",
        "立",
        "崩",
        "咸",
        "弗",
        "莫",
        "不",
        "从",
        "服",
        "诸侯",
        "天子",
        "帝王",
        "百姓",
        "万民",
        "天下",
        "乃",
        "遂",
        "于是",
        "既",
        "已",
        "未",
        "皆",
        "悉",
        "咸",
        "弗能",
        "莫能",
        "莫不",
        "咸来",
        "咸归",
        "咸尊",
        "宾从",
        "从服",
    }
)

# L0 组合短语
L0_GLOSS_PHRASES = (
    "莫不从服",
    "莫能伐",
    "弗能征",
    "咸来宾从",
    "咸归轩辕",
    "咸尊轩辕",
    "三战",
    "然后得其志",
)

# 检测「「崩」就是去世」「「莫不从服」——没有不…」类冗余解释
_FORBIDDEN_GLOSS_PATTERNS = [
    re.compile(r"「崩」[^。]{0,20}(?:去世|逝世|死亡|驾崩)"),
    re.compile(r"「薨」[^。]{0,20}(?:去世|逝世|死亡)"),
    re.compile(r"「卒」[^。]{0,20}(?:去世|逝世|死亡)"),
    re.compile(r"「莫不从服」[^。]{0,40}(?:无不|没有不|都)"),
    re.compile(r"「咸」[^。]{0,12}(?:都|皆|全部)"),
    re.compile(r"「弗」[^。]{0,12}(?:不|没有)"),
    re.compile(r"「诸侯」[^。]{0,20}(?:各|部落|首领)"),
    re.compile(r"「天子」[^。]{0,20}(?:皇帝|君主|天子)"),
    re.compile(
        r"「([\u4e00-\u9fff])」[^。]{0,8}(?:就是|即|指的是|意思是)"
    ),
]


def is_l0_word(word: str) -> bool:
    w = word.strip().strip("「」")
    return w in L0_GLOSS_WORDS or w in L0_GLOSS_PHRASES


def detect_forbidden_gloss(text: str) -> List[str]:
    issues: List[str] = []
    for pat in _FORBIDDEN_GLOSS_PATTERNS:
        for m in pat.finditer(text):
            issues.append(f"通识词冗余解释: {m.group(0)[:40]}")
    return issues


def gloss_rules_prompt_block() -> str:
    return (
        "禁释词（L0）：崩/薨/卒/立/咸/弗/莫不/诸侯/天子/万民/天下等通识文言，"
        "直接融入白话叙述，禁止「「崩」就是去世」式注释；"
        "「莫不从服」等固定短语整体顺译，禁止拆词逐字解释。"
    )
