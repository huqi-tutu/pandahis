#!/usr/bin/env python3
"""peak_year LLM 输入与守门逻辑单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ANNOTATE = Path(__file__).resolve().parents[1]
if str(ANNOTATE) not in sys.path:
    sys.path.insert(0, str(ANNOTATE))

from peak_year import (  # noqa: E402
    PEAK_CONF,
    PEAK_REASON,
    apply_post_llm_checks,
    build_llm_input,
    build_llm_prompt,
    is_high_risk_entry,
    is_joint_biography,
    write_peak,
)


class PeakYearLlmTests(unittest.TestCase):
    def test_joint_biography_detects_hezhuan(self) -> None:
        entry = {
            "史略名称": "丙吉",
            "主要史料出处": "《汉书·卷86·魏相丙吉传》",
        }
        self.assertTrue(is_joint_biography(entry))

    def test_joint_biography_single_subject(self) -> None:
        entry = {
            "史略名称": "东方朔",
            "主要史料出处": "《汉书·卷77·东方朔传》",
        }
        self.assertFalse(is_joint_biography(entry))

    def test_build_llm_input_has_subject_anchor(self) -> None:
        entry = {
            "史略ID": "GLBL_00253",
            "史略名称": "丙吉",
            "史略分类": "文臣",
            "史略简介": "护养皇曾孙，宣帝朝丞相",
            "史略开始年": -130,
            "史略结束年": -55,
            "主要史料出处": "《汉书·卷86·魏相丙吉传》",
            "六级段落锚点": "[P9-P15]",
            "二级朝代坐标": "西汉",
            "三级政权坐标": "西汉",
            "四级帝王坐标": "汉宣帝",
            "五级细坐标": "汉书·卷086·文臣·01",
            "原文字句": "丙吉字少卿，鲁国人也。",
            "考订依据": {
                "坐标主轴": "丙吉官位高峰在汉宣帝朝",
                "年": "约前130至前55",
            },
            "paragraphs": [
                {
                    "work": "02汉书",
                    "volume": "魏相丙吉传",
                    "paragraph_from": 9,
                    "paragraph_to": 15,
                    "role": "母本",
                }
            ],
        }
        payload = build_llm_input(entry)
        self.assertEqual(payload["判定对象"], "丙吉")
        self.assertIn("坐标主轴", payload)
        self.assertIn("母本段落", payload)
        self.assertNotIn("优先级", payload)
        self.assertTrue(is_high_risk_entry(entry))

    def test_prompt_contains_subject_lock(self) -> None:
        entry = {
            "史略ID": "X1",
            "史略名称": "丙吉",
            "史略分类": "文臣",
            "史略开始年": -130,
            "史略结束年": -55,
            "主要史料出处": "《汉书·卷86·魏相丙吉传》",
            "原文字句": "丙吉字少卿",
        }
        prompt = build_llm_prompt("文臣", [entry])
        self.assertIn("主体锁定", prompt)
        self.assertIn("判定对象", prompt)

    def test_post_llm_flags_missing_name_in_reason(self) -> None:
        entry = {
            "史略ID": "X1",
            "史略名称": "丙吉",
            "史略分类": "文臣",
            "史略开始年": -130,
            "史略结束年": -55,
        }
        write_peak(
            entry,
            -74,
            "魏相主持朝政达到高峰",
            "career_peak",
            0.8,
            "llm",
        )
        notes = apply_post_llm_checks(entry)
        self.assertTrue(notes)
        self.assertLessEqual(entry[PEAK_CONF], 0.35)
        self.assertIn("未点名判定对象", entry["_auto_filled"]["_峰值待审"])

    def test_post_llm_passes_when_reason_names_subject(self) -> None:
        entry = {
            "史略ID": "X1",
            "史略名称": "丙吉",
            "史略分类": "文臣",
            "史略开始年": -130,
            "史略结束年": -55,
        }
        write_peak(
            entry,
            -74,
            "丙吉任丞相、知人善任达于巅峰",
            "career_peak",
            0.85,
            "llm",
        )
        notes = apply_post_llm_checks(entry)
        self.assertEqual(notes, [])
        self.assertEqual(entry[PEAK_REASON], "丙吉任丞相、知人善任达于巅峰")


if __name__ == "__main__":
    unittest.main()
