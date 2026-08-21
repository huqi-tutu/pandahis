"""历史翻译质量宪法：按阶段切片注入 prompt。

SSOT：historiography-compose/references/历史翻译质量宪法.md
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict

_CONSTITUTION = (
    Path(__file__).resolve().parents[2]
    / "historiography-compose"
    / "references"
    / "历史翻译质量宪法.md"
)

_SECTION_ALIASES = {
    "eight": ("## 一、历史翻译八大守恒", "## 二、"),
    "phase2_add": ("## 二、Phase2 新增内容三条", "## 三、"),
    "backtrace": ("## 三、Evidence Backtrace", "## 四、"),
    "slice_p1": ("## 四、阶段切片 · Phase1", "## 五、"),
    "slice_p2": ("## 五、阶段切片 · Phase2", "## 六、"),
    "slice_p3": ("## 六、阶段切片 · Phase3", None),
}


@lru_cache(maxsize=1)
def _raw() -> str:
    if not _CONSTITUTION.is_file():
        return ""
    return _CONSTITUTION.read_text(encoding="utf-8")


def _extract(start_prefix: str, end_prefix: str | None) -> str:
    text = _raw()
    if not text:
        return ""
    start = text.find(start_prefix)
    if start < 0:
        return ""
    if end_prefix:
        end = text.find(end_prefix, start + len(start_prefix))
        body = text[start:end] if end > start else text[start:]
    else:
        body = text[start:]
    return body.strip()


def _section(key: str) -> str:
    start, end = _SECTION_ALIASES[key]
    return _extract(start, end)


def constitution_snip(*, phase: str) -> str:
    """phase: draft_mother | draft_enrich | polish | phase3 | draft | plan(skip empty)."""
    if phase in {"plan"}:
        return ""
    eight = _section("eight")
    # 八大守恒正文过长时取标题+每条首行，避免挤爆；完整文件仍在 SSOT
    eight_short = _eight_bullets(eight)
    if phase == "draft_mother":
        return _join(
            "【质量宪法 · Phase1】`历史翻译质量宪法.md`",
            eight_short,
            _section("slice_p1"),
        )
    if phase in {"draft_enrich", "polish", "draft"}:
        return _join(
            "【质量宪法 · Phase2】`历史翻译质量宪法.md`",
            eight_short,
            _section("phase2_add"),
            _section("slice_p2"),
        )
    if phase == "phase3":
        return _join(
            "【质量宪法 · Phase3】`历史翻译质量宪法.md`",
            eight_short,
            _section("backtrace"),
            _section("slice_p3"),
        )
    return eight_short


def _eight_bullets(eight_section: str) -> str:
    """压缩为八条一行要点，保留可扫读性。"""
    if not eight_section:
        return (
            "八大守恒：①事件 ②顺序 ③主体(谁-做-对谁-结果) ④因果 "
            "⑤时间(绝对/相对/距离) ⑥范围 ⑦认知(角色+证据强度) ⑧来源"
        )
    lines = ["**八大守恒（硬）**："]
    for m in re.finditer(
        r"### ([①②③④⑤⑥⑦⑧][^\n]+)\n([^\n#]+)",
        eight_section,
    ):
        title = m.group(1).strip()
        body = re.sub(r"\s+", " ", m.group(2).strip())
        if len(body) > 72:
            body = body[:70] + "…"
        lines.append(f"- **{title}**：{body}")
    if len(lines) == 1:
        lines.append(
            "- ①事件 ②顺序 ③主体四元组 ④因果 ⑤时间 ⑥范围 ⑦认知 ⑧来源"
        )
    return "\n".join(lines)


def _join(*parts: str) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def constitution_path() -> Path:
    return _CONSTITUTION
