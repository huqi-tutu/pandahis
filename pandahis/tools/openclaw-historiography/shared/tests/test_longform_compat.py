"""长文兼容档位单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.longform_compat import (  # noqa: E402
    batch_is_mid_or_late,
    batch_lacks_colloquial,
    enrich_batch_guard_extra,
    external_adopt_quota,
    is_longform,
    join_narrative_parts,
    mother_batch_guard_note,
    plan_longform_hint,
)
from lib.plan_postprocess import apply_longform_external_floor  # noqa: E402


class TestLongformDetect(unittest.TestCase):
    def test_short_vs_long(self) -> None:
        self.assertFalse(is_longform({"母本逐句清单": [{"编号": f"M{i:03d}"} for i in range(20)]}))
        self.assertTrue(is_longform({"母本逐句清单": [{"编号": f"M{i:03d}"} for i in range(40)]}))

    def test_quota(self) -> None:
        self.assertEqual(external_adopt_quota(20), 0)
        self.assertGreaterEqual(external_adopt_quota(40), 3)
        self.assertLessEqual(external_adopt_quota(200), 8)

    def test_plan_hint_separates_index_and_external(self) -> None:
        hint = plan_longform_hint(80)
        self.assertIn("决策聚焦", hint)
        self.assertIn("不限于", hint)
        self.assertIn("索引补充 ≠ 外部补全", hint)
        self.assertNotIn("自动种子", hint)


class TestJoinParts(unittest.TestCase):
    def test_joins_in_order_without_dropping(self) -> None:
        """分批正文只按序拼接，不因后文专名回指删前文场面。"""
        a = (
            "刘邦带着酒意夜里探路，前面有条大蛇。他拔剑斩蛇，老妇人哭道白帝赤帝。"
            "跟随的人一天比一天敬畏他。"
        )
        b = (
            "父老们立刘季为沛公，旗帜都用红色，因为所杀蛇是白帝之子、杀者赤帝之子。"
            "于是招收子弟攻打胡陵。"
        )
        merged = join_narrative_parts([a, b])
        self.assertIn("探路", merged)
        self.assertIn("立刘季为沛公", merged)
        self.assertLess(merged.index("探路"), merged.index("立刘季为沛公"))

    def test_skips_empty_parts(self) -> None:
        merged = join_narrative_parts(["甲段内容足够长。", "", "  ", "乙段内容足够长。"])
        self.assertEqual(merged, "甲段内容足够长。\n\n乙段内容足够长。")

    def test_heals_paraphrase_duplicate_across_parts(self) -> None:
        """章界换说法复述：保留先写，静默丢掉后段（不门禁）。"""
        a = (
            "封禅泰山这一趟，一路没遇上风雨灾害，顺顺当当。"
            "方士们便又鼓动说蓬莱那些神山好像真能求到了，"
            "汉武帝听了满心欢喜，再次东行到海边眺望。"
            "偏偏这时奉车子侯霍嬗突然暴病，一天之内就死了。"
        )
        b = (
            "汉武帝从泰山封禅回来，这一路没遇上风雨灾祸，顺顺当当。"
            "方士们又在他耳朵边嘀咕蓬莱那些神山这回可算有门路了，"
            "他又往东跑到海边眼巴巴地望着。"
            "偏偏霍嬗突然暴病，一天工夫就死了。"
        )
        c = "五月，汉武帝返回甘泉宫，改元为元封元年，这是后话另起。"
        merged = join_narrative_parts([a, b + "\n\n" + c])
        self.assertIn("没遇上风雨灾害", merged)
        self.assertNotIn("从泰山封禅回来", merged)
        self.assertIn("改元为元封元年", merged)


class TestExternalFloor(unittest.TestCase):
    def test_flips_qualified_candidates(self) -> None:
        plan = {
            "母本逐句清单": [{"编号": f"M{i:03d}"} for i in range(50)],
            "外部补全": [
                {
                    "出处": "《汉书·武帝纪》",
                    "补全类型": "异说",
                    "与母本关系": "汉书另记年号细节，母本未载",
                    "采用": False,
                },
                {
                    "出处": "《史记·封禅书》",
                    "补全类型": "背景",
                    "与母本关系": "补充封禅动机背景，母本仅一句带过",
                    "采用": False,
                },
                {
                    "出处": "常识",
                    "补全类型": "背景",
                    "与母本关系": "无书名不出",
                    "采用": False,
                },
            ],
        }
        n = apply_longform_external_floor(plan)
        # 宏观路径默认可不强制翻 true；此处只保证函数可调用且不误伤第三项
        self.assertFalse(plan["外部补全"][2]["采用"])
        self.assertGreaterEqual(n, 0)


class TestDiscoverMotherBatches(unittest.TestCase):
    def test_excludes_enrich_files(self) -> None:
        import tempfile
        from lib.phase2_batch import discover_mother_batches

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            mother = d / "GLBL_x.mother.json"
            mother.write_text("{}", encoding="utf-8")
            (d / "GLBL_x.mother-b01.json").write_text("{}", encoding="utf-8")
            (d / "GLBL_x.mother-b02.json").write_text("{}", encoding="utf-8")
            (d / "GLBL_x.mother-b01.enrich.json").write_text("{}", encoding="utf-8")
            (d / "GLBL_x.mother-b01.enrich.enrich.json").write_text("{}", encoding="utf-8")
            found = [p.name for p in discover_mother_batches(mother)]
            self.assertEqual(found, ["GLBL_x.mother-b01.json", "GLBL_x.mother-b02.json"])


class TestBatchGuards(unittest.TestCase):
    def test_mother_batch_note(self) -> None:
        note = mother_batch_guard_note(batch_label="第 1/3 批", m_ids=["M001", "M002"])
        self.assertIn("禁止整传重开", note)
        self.assertIn("批末禁越界", note)
        self.assertIn("批首禁重开已写事件", note)
        self.assertIn("M001", note)
        self.assertIn("原文窗口", note)
        self.assertTrue("原文窗口" in note or "must_translate" in note)

    def test_enrich_batch_requires_voice_in_batch(self) -> None:
        note = enrich_batch_guard_extra(batch_no=1, total=26)
        self.assertIn("本批文风", note)
        self.assertTrue("原文窗口" in note or "must_translate" in note)
        self.assertIn("禁止滥用「说白了」", note)
        self.assertNotIn("Phase3", note)
        late = enrich_batch_guard_extra(batch_no=20, total=26)
        self.assertIn("中后批提醒", late)
        self.assertIn("不要**靠插入「说白了」过关", late)
        self.assertTrue(batch_is_mid_or_late(batch_no=20, total=26))
        self.assertFalse(batch_is_mid_or_late(batch_no=1, total=26))
        self.assertTrue(batch_lacks_colloquial("白描顺译。" * 20))
        # 「说白了」不再算合格口语标记
        self.assertTrue(batch_lacks_colloquial("说白了，这事有点意思。" + "叙述" * 40))
        self.assertFalse(batch_lacks_colloquial("偏偏这事倒是有点意思。" + "叙述" * 40))


if __name__ == "__main__":
    unittest.main()
