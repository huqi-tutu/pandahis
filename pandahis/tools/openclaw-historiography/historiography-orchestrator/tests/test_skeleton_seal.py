"""skeleton Step4 封板检测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ORCH))

from lib.skeleton_seal import skeleton_step4_sealed  # noqa: E402


class TestSkeletonSeal(unittest.TestCase):
    def test_not_sealed_without_coords(self):
        data = {
            "entries": [
                {
                    "史略名称": "陈胜",
                    "优先级": "P0",
                    "_auto_filled": {"_坐标主轴说明": "x"},
                }
            ]
        }
        self.assertFalse(skeleton_step4_sealed(data))

    def test_sealed_with_full_step4(self):
        data = {
            "entries": [
                {
                    "优先级": "P0",
                    "优先级判定理由": "x",
                    "史略开始年": -1,
                    "史略结束年": -1,
                    "一级文明坐标": "华夏",
                    "二级朝代坐标": "秦",
                    "三级政权坐标": "秦",
                    "四级帝王坐标": "秦始皇",
                    "文明ID": "HX",
                    "朝代ID": "CD_HX_QIN",
                    "政权ID": "ZQ_HX_QIN_QIN",
                    "帝王ID": "DW_HX_QIN_QIN_QINSHIHUANG",
                    "五级细坐标": "x",
                    "六级段落锚点": "[P1]",
                    "原文出处": "x",
                }
            ]
        }
        self.assertTrue(skeleton_step4_sealed(data))


if __name__ == "__main__":
    unittest.main()
