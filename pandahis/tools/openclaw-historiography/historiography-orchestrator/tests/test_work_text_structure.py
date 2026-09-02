"""work_text_structure 提示注入。"""

from __future__ import annotations

import unittest

from lib.work_text_structure import work_text_structure_hint


class TestWorkTextStructure(unittest.TestCase):
    def test_hanshu_has_volume_title_and_zanyue(self) -> None:
        hint = work_text_structure_hint("02汉书")
        self.assertIn("卷首标题", hint)
        self.assertIn("赞曰", hint)
        self.assertIn("太史公曰", hint)
        self.assertIn("硃建", hint)

    def test_shiji_no_volume_title_on_p1(self) -> None:
        hint = work_text_structure_hint("01史记")
        self.assertIn("无独立卷首标题", hint)
        self.assertIn("太史公曰", hint)

    def test_sanguozhi_has_volume_title_and_pingyue(self) -> None:
        hint = work_text_structure_hint("04三国志")
        self.assertIn("卷首标题", hint)
        self.assertIn("评曰", hint)
        self.assertIn("不建条目", hint)

    def test_unknown_work_generic(self) -> None:
        hint = work_text_structure_hint("99未知")
        self.assertIn("通用", hint)


if __name__ == "__main__":
    unittest.main()
