#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from emperor_year_align import align_junji_entry_years, build_emperor_indexes, parse_emperor_year


class EmperorYearAlignTest(unittest.TestCase):
    def test_parse_emperor_year(self):
        self.assertEqual(parse_emperor_year("约-1919"), -1919)
        self.assertEqual(parse_emperor_year("-1704"), -1704)

    def test_force_align_overwrites_llm_years(self):
        emperors = [
            {
                "帝王ID": "DW_HX_XIA_XIA_FA",
                "帝王名称": "发",
                "帝王原名": "发",
                "即位时间": "-1704",
                "退位时间": "-1652",
                "朝代ID": "CD_HX_XIA",
            }
        ]
        by_name, by_id = build_emperor_indexes(emperors, dynasty_id="CD_HX_XIA")
        entry = {
            "史略ID": "GLBL_00612",
            "史略名称": "发",
            "史略分类": "君王",
            "四级帝王坐标": "发",
            "帝王ID": "DW_HX_XIA_XIA_FA",
            "史略开始年": -1630,
            "史略结束年": -1610,
            "峰值年": -1620,
        }
        aligned, changes = align_junji_entry_years(
            entry, by_name=by_name, by_id=by_id, force=True
        )
        self.assertEqual(aligned["史略开始年"], -1704)
        self.assertEqual(aligned["史略结束年"], -1652)
        self.assertEqual(aligned["峰值年"], -1704)
        self.assertTrue(changes)


if __name__ == "__main__":
    unittest.main()
