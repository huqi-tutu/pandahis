"""外部补全宏观选题 / 挂锚工具测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.external_macro import (  # noqa: E402
    fallback_anchors,
    merge_anchors_into_external,
    normalize_macro_external,
)


class TestExternalMacro(unittest.TestCase):
    def test_normalize_defaults(self) -> None:
        items = normalize_macro_external(
            [{"主题": "a", "出处": "《汉纪》", "补全类型": "异说"}]
        )
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].get("采用") is True)
        self.assertEqual(items[0].get("母本锚点"), "")

    def test_merge_anchors_by_theme(self) -> None:
        base = [
            {"采用": True, "主题": "鸿沟另说", "出处": "《汉纪》", "母本锚点": ""},
            {"采用": True, "主题": "班固赞", "出处": "《汉书》", "母本锚点": ""},
        ]
        anchored = [
            {
                "采用": True,
                "主题": "班固赞",
                "出处": "《汉书》",
                "母本锚点": "M400 后",
            },
            {
                "采用": True,
                "主题": "鸿沟另说",
                "出处": "《汉纪》",
                "母本锚点": "M200 后",
            },
        ]
        out = merge_anchors_into_external(base, anchored)
        self.assertEqual(out[0]["母本锚点"], "M200 后")
        self.assertEqual(out[1]["母本锚点"], "M400 后")

    def test_fallback_anchors(self) -> None:
        checklist = [{"编号": f"M{i:03d}", "信息点": f"p{i}"} for i in range(1, 10)]
        external = [
            {"采用": True, "主题": "a", "出处": "《A》"},
            {"采用": False, "主题": "b", "出处": "《B》"},
            {"采用": True, "主题": "c", "出处": "《C》"},
        ]
        out = fallback_anchors(external, checklist)
        self.assertTrue(str(out[0].get("母本锚点") or "").startswith("M"))
        self.assertFalse(str(out[1].get("母本锚点") or "").startswith("M"))
        self.assertTrue(str(out[2].get("母本锚点") or "").startswith("M"))


if __name__ == "__main__":
    unittest.main()
