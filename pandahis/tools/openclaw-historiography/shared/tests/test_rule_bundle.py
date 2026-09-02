"""rule_bundle 理想分工：各 phase 含/不含正确规则、无明显整包重复。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
if str(TRANSLATE) not in sys.path:
    sys.path.insert(0, str(TRANSLATE))

from lib.rule_bundle import compile_rule_bundle  # noqa: E402


def _bundle(phase: str) -> str:
    return compile_rule_bundle(
        {"id": "T", "blocks": [], "母本内容": []}, phase=phase
    )


class TestRuleBundleIdealSplit(unittest.TestCase):
    def test_mother_has_core_not_humor_or_external(self):
        b = _bundle("draft_mother")
        self.assertIn("【主场】规则十", b)
        self.assertIn("【主场】规则四", b)
        self.assertIn("【主场】规则七", b)
        self.assertIn("【主场】规则九", b)
        self.assertIn("说书人当面讲史", b)
        self.assertTrue("逐句" in b or "信息覆盖" in b)
        self.assertIn("原文与白话自然融合", b)
        self.assertIn("成稿硬门槛", b)
        self.assertTrue("七项" in b or "终稿质量维度" in b)
        self.assertTrue("不强制幽默" in b or "风格" in b)
        self.assertTrue("终稿按七维验收" in b or "七项" in b)
        self.assertIn("本阶段主责", b)
        self.assertIn("门禁是兜底", b)
        self.assertIn("文言虚词误读陷阱", b)
        self.assertIn("是为零陵", b)
        self.assertIn("【质量宪法】", b)
        # Phase1 不得灌幽默专章 / 外部补全长文 / 完整风格章 / 附录运维
        self.assertNotIn("### 幽默规范", b)
        self.assertNotIn("### 外部补全与锚点原则", b)
        self.assertNotIn("### 外部补全防幻觉", b)
        self.assertNotIn("## 规则一：风格定位", b)
        self.assertNotIn("附录：编排器与运维", b)
        self.assertNotIn("TRANSLATE_USE_CHUNK", b)
        self.assertEqual(b.count("【主场】规则十"), 1)
        self.assertEqual(b.count("### 禁止事项（硬 / 软）"), 1)

    def test_enrich_step_order_and_humor(self):
        b = _bundle("draft_enrich")
        self.assertIn("【质量宪法】", b)
        self.assertIn("【主场 · 改表达】规则一", b)
        self.assertIn("### 幽默规范", b)
        self.assertIn("### 外部补全与锚点原则", b)
        self.assertIn("### 覆盖与引用（Phase2 短约束）", b)
        self.assertIn("门禁是兜底", b)
        self.assertNotIn("【主场】规则十", b)
        self.assertNotIn("【主场】规则十", b)
        self.assertNotIn("【主场】规则四", b)
        self.assertNotIn("附录：编排器与运维", b)
        idx_const = b.index("【质量宪法】")
        idx_voice = b.index("【主场 · 改表达】规则一")
        self.assertLess(idx_const, idx_voice)

    def test_plan_cross_book_no_style(self):
        b = _bundle("plan")
        self.assertIn("### 外部补全与锚点原则", b)
        self.assertIn("默认 false", b)
        self.assertIn("母本同一卷", b)
        self.assertIn("门禁是兜底", b)
        self.assertNotIn("### 幽默规范", b)
        self.assertNotIn("【主场】规则十", b)
        self.assertNotIn("六类触发条件", b)
        self.assertNotIn("是为零陵", b)
        self.assertIn("【轻量】规则十", b)

    def test_no_layer2_p2_duplication(self):
        """旧实现第二层固定再灌 P2；理想包不得让规则十正文出现两次。"""
        mother = _bundle("draft_mother")
        self.assertLessEqual(mother.count("【主场】规则十"), 1)
        enrich = _bundle("draft_enrich")
        self.assertNotIn("【主场】规则十", enrich)
        plan = _bundle("plan")
        self.assertNotIn("【主场】规则十", plan)

    def test_enrich_smaller_or_comparable_without_r10(self):
        mother = _bundle("draft_mother")
        enrich = _bundle("draft_enrich")
        self.assertNotIn("【主场】规则十", enrich)
        self.assertLess(len(mother), 28000)
        self.assertIn("外部补全", enrich)
        self.assertNotIn("外部补全与锚点原则", mother)

    def test_examples_mark_gloss_loop_as_bad(self):
        """批注体只能作为反例出现。"""
        mother = _bundle("draft_mother")
        self.assertIn("批注体", mother)
        self.assertIn("❌", mother)
        self.assertTrue(
            "「」——同义白话" in mother or "对照作业体" in mother,
            "母本包应含破折号同义回声反例",
        )


if __name__ == "__main__":
    unittest.main()
