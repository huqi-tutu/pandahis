"""汉书 Step4 人物年份占位检测与清空。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "historiography-annotate"
sys.path.insert(0, str(ROOT))

from hanshu_step4_hardening import (  # noqa: E402
    clear_entries_without_year_basis,
    detect_person_year_placeholder,
    entry_year_needs_llm_basis,
    person_year_needs_llm,
)
from lib_config import validate_year_quality  # noqa: E402


class TestHanshuYearPlaceholder(unittest.TestCase):
    def test_detect_gaozu_reign_copy(self) -> None:
        entry = {
            "史略名称": "周昌",
            "史略分类": "文臣",
            "四级帝王坐标": "汉高祖",
            "二级朝代坐标": "西汉",
            "史略开始年": -202,
            "史略结束年": -195,
            "_auto_filled": {},
        }
        msg = detect_person_year_placeholder(entry)
        self.assertIsNotNone(msg)
        self.assertIn("在位", msg or "")

    def test_detect_lazy_hanwang_span(self) -> None:
        entry = {
            "史略名称": "赵尧",
            "史略分类": "文臣",
            "四级帝王坐标": "汉高祖",
            "二级朝代坐标": "西汉",
            "史略开始年": -206,
            "史略结束年": -195,
            "_auto_filled": {},
        }
        msg = detect_person_year_placeholder(entry)
        self.assertIsNotNone(msg)

    def test_llm_basis_not_placeholder(self) -> None:
        entry = {
            "史略名称": "张苍",
            "史略分类": "文臣",
            "四级帝王坐标": "汉文帝",
            "史略开始年": -256,
            "史略结束年": -152,
            "_auto_filled": {"_年LLM依据": "学界约前256–前152"},
        }
        self.assertIsNone(detect_person_year_placeholder(entry))
        self.assertFalse(person_year_needs_llm(entry))

    def test_clear_forces_needs_llm(self) -> None:
        entry = {
            "史略ID": "HANSHU_052_02",
            "史略名称": "周昌",
            "史略分类": "文臣",
            "四级帝王坐标": "汉高祖",
            "二级朝代坐标": "西汉",
            "史略开始年": -206,
            "史略结束年": -195,
            "优先级": "P1",
            "_auto_filled": {},
        }
        n, _ = clear_entries_without_year_basis([entry], force_all_without_basis=True)
        self.assertEqual(n, 1)
        self.assertNotIn("史略开始年", entry)
        self.assertIn("史略开始年", entry.get("_needs_llm") or [])

    def test_junwang_without_basis_cleared(self) -> None:
        entry = {
            "史略ID": "HANSHU_001_01",
            "史略名称": "汉高祖",
            "史略分类": "君王",
            "史略开始年": -202,
            "史略结束年": -195,
            "_auto_filled": {"年规则": "即位年 → 退位/崩年"},
        }
        self.assertTrue(entry_year_needs_llm_basis(entry))
        n, _ = clear_entries_without_year_basis([entry], force_all_without_basis=True)
        self.assertEqual(n, 1)
        self.assertNotIn("史略开始年", entry)

        entries = [
            {
                "史略ID": "X",
                "史略名称": "周昌",
                "史略分类": "文臣",
                "史略开始年": -206,
                "史略结束年": -195,
                "四级帝王坐标": "汉高祖",
                "二级朝代坐标": "西汉",
                "_auto_filled": {},
            }
        ]
        issues = validate_year_quality(entries)
        self.assertTrue(any("_年LLM依据" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
