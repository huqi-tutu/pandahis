#!/usr/bin/env python3
"""repair 脚本边界：仅机械修复，禁止替代 LLM 知识性决策。"""

from __future__ import annotations

import os
import sys
from typing import NoReturn

from knowledge_provenance import FORBIDDEN_REPAIR_KNOWLEDGE_FIELDS

NARRATIVE_REPAIR_SCRIPTS = frozenset(
    {
        "repair_hanshu_vol001.py",
        "repair_hanshu_vol041.py",
        "repair_hanshu_vol042.py",
        "repair_hanshu_liezhuan_batch.py",
        "repair_hanshu_diji_batch.py",
    }
)


def guard_narrative_knowledge_repair(script_file: str) -> None:
    """
    叙事卷 repair 已废止。知识性字段（块界、分类、坐标、年份）须走 Step1/Step4 LLM。
    表/志 skip 请用 repair_skip_narrative_volume / repair_hanshu_skip_zhizhi（仅机械 exclude）。
    """
    name = os.path.basename(script_file)
    if name not in NARRATIVE_REPAIR_SCRIPTS:
        return
    if os.environ.get("ALLOW_LEGACY_NARRATIVE_REPAIR") == "1":
        print(f"⚠️ ALLOW_LEGACY_NARRATIVE_REPAIR=1：跳过废止检查（{name}，仅供调试）", file=sys.stderr)
        return
    print(
        f"⛔ {name} 已废止：不得用脚本替代 Step1/Step4 大模型知识性决策。\n"
        "   请使用: python3 hist.py run-work --work 02汉书 --one-volume\n"
        "   表/志机械 skip: repair_hanshu_skip_zhizhi.py 或编排器 _preflight_skip",
        file=sys.stderr,
    )
    raise SystemExit(2)


def assert_repair_does_not_finalize_llm(entry: dict) -> None:
    """repair 脚本不得删除 _needs_llm 或假装 Step4 已完成。"""
    if "_needs_llm" not in entry:
        return
    raise RuntimeError(
        "repair 禁止 pop/_needs_llm；知识性字段须交 Step4 LLM 补全"
    )


def refuse_knowledge_field_write(field: str) -> NoReturn:
    raise RuntimeError(
        f"repair 禁止写入知识性字段「{field}」；"
        f"允许字段限于：原文字句摘录、坐标 ID 同步、exclude_reason 等机械项。"
        f"（禁止集: {', '.join(sorted(FORBIDDEN_REPAIR_KNOWLEDGE_FIELDS))}）"
    )
