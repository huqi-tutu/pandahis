"""plan 分批过滤与 M 锚点、批间衔接测试。"""

from __future__ import annotations

import unittest

from lib.batch_continuity import (
    build_continuity_prompt_block,
    prose_batch_tail,
    split_checklist_at_p_boundaries,
)
from lib.m_anchor import (
    anchor_hits_batch,
    batch_m_numbers,
    normalize_mother_anchor,
    parse_anchor_m_refs,
)
from lib.plan_batch_filter import plan_slice_for_batch, plan_slice_for_batch_prompt


def _item(mid: int, pid: int, text: str = "") -> dict:
    return {
        "编号": f"M{mid:03d}",
        "段落": f"01史记 卷012 孝武本纪 P{pid}",
        "原文摘句": text or f"句{mid}。",
    }


def _mini_checklist() -> list:
    return [_item(i, 1 if i <= 5 else (2 if i <= 9 else 5)) for i in range(1, 19)]


class TestMAnchor(unittest.TestCase):
    def test_parse_m_range(self):
        self.assertEqual(parse_anchor_m_refs("M001–M009"), set(range(1, 10)))

    def test_p_to_m_normalize(self):
        cl = _mini_checklist()
        got = normalize_mother_anchor("P5后", cl)
        self.assertRegex(got, r"M\d{3}后")

    def test_anchor_no_m_no_hit(self):
        batch = batch_m_numbers(_mini_checklist())
        self.assertFalse(anchor_hits_batch("P99后", batch, checklist=_mini_checklist()))

    def test_tail_only_last_batch(self):
        batch = batch_m_numbers(_mini_checklist())
        self.assertFalse(anchor_hits_batch("tail", batch, batch_index=1, batch_total=3))
        self.assertTrue(anchor_hits_batch("tail", batch, batch_index=3, batch_total=3))


class TestPlanSlice(unittest.TestCase):
    def test_batch_slice_m_only(self):
        cl = _mini_checklist()
        plan = {
            "史略ID": "T",
            "史略名称": "测试",
            "母本著作": "01史记",
            "母本逐句清单": cl,
            "外部补全": [
                {"采用": True, "母本锚点": "M009后", "出处": "《汉书》", "候选内容": "a"},
            ],
        }
        batch_items = cl[:18]
        sliced = plan_slice_for_batch(plan, batch_items, batch_index=1, batch_total=2)
        self.assertEqual(sliced["本批范围"], "M001–M018")
        self.assertEqual(len(sliced["母本逐句清单"]), 18)
        self.assertNotIn("外部补全", sliced)

    def test_batch_prompt_slice_slim(self):
        cl = _mini_checklist()
        for i, item in enumerate(cl):
            item["必现词"] = [f"锚{i}"]
            item["引用粒度"] = "parallel_cluster" if i % 5 == 0 else "narrative"
            item["母本提示"] = "叙事句：专名与数字融入白话叙述。"
        plan = {
            "史略ID": "T",
            "史略名称": "测试",
            "母本著作": "01史记",
            "母本逐句清单": cl,
        }
        batch_items = cl[:6]
        slim = plan_slice_for_batch_prompt(plan, batch_items, batch_index=1, batch_total=2)
        self.assertEqual(slim["本批范围"], "M001–M006")
        self.assertIn("引用粒度说明", slim)
        self.assertIn("narrative", slim["引用粒度说明"])
        self.assertIn("parallel_cluster", slim["引用粒度说明"])
        for row in slim["母本逐句清单"]:
            self.assertEqual(set(row.keys()), {"编号", "原文摘句"})
            self.assertNotIn("必现词", row)
            self.assertNotIn("母本提示", row)
        full = plan_slice_for_batch(plan, batch_items)
        self.assertIn("必现词", full["母本逐句清单"][0])


class TestBatchSplit(unittest.TestCase):
    def test_straddle_at_ideal_ends_before_new_p(self):
        # P1: M1-10, P2: M11-25；target=11 → ideal 跨 M10/M11，应在 M10 末切
        cl = [_item(i, 1 if i <= 10 else 2) for i in range(1, 26)]
        batches = split_checklist_at_p_boundaries(cl, target_size=11)
        self.assertEqual(batches[0][-1]["编号"], "M010")
        self.assertEqual(batches[1][0]["编号"], "M011")

    def test_far_boundary_uses_ideal_when_closer(self):
        # P 边界在 M10，target=18 时更接近 ideal=18 而非 M10
        cl = [_item(i, 1 if i <= 10 else 2) for i in range(1, 26)]
        batches = split_checklist_at_p_boundaries(cl, target_size=18)
        self.assertEqual(batches[0][-1]["编号"], "M018")

    def test_single_batch_when_short(self):
        cl = _mini_checklist()
        self.assertEqual(len(split_checklist_at_p_boundaries(cl, target_size=30)), 1)


class TestBatchContinuity(unittest.TestCase):
    def test_prose_tail_respects_char_budget(self):
        long_para = "甲。" * 200
        body = f"{long_para}\n\n{long_para}\n\n末段收束。"
        tail = prose_batch_tail(body, max_chars=120, max_paras=3)
        self.assertLessEqual(len(tail), 120)
        self.assertIn("末段收束", tail)

    def test_batch2_has_mother_and_prose_context(self):
        cl = _mini_checklist()
        block = build_continuity_prompt_block(
            batch_index=2,
            batch_total=2,
            batch_items=cl[9:],
            full_checklist=cl,
            prev_body="上批第一段。\n\n上批第二段。",
        )
        self.assertIn("第 2/2 批", block)
        self.assertIn("母本前情", block)
        self.assertIn("M009", block)
        self.assertIn("上批第二段", block)

    def test_batch1_no_prev_context(self):
        cl = _mini_checklist()
        block = build_continuity_prompt_block(
            batch_index=1,
            batch_total=2,
            batch_items=cl[:9],
            full_checklist=cl,
            prev_body="",
        )
        self.assertIn("开篇顺译", block)
        self.assertNotIn("母本前情", block)
        self.assertNotIn("上批末段", block)


class TestNarratorFraming(unittest.TestCase):
    def test_batch_draft_no_duplicate_priority_blocks(self):
        from lib.rule_bundle import compile_rule_bundle

        bundle = compile_rule_bundle({"blocks": [{"role": "补充"}]}, phase="batch_draft", batch_m_count=10)
        self.assertIn("## 叙述者", bundle)
        self.assertIn("## 本步任务", bundle)
        self.assertIn("## 冲突时优先级", bundle)
        self.assertIn("## 引用与顺译（P2）", bundle)
        self.assertIn("逐句顺译", bundle)
        self.assertIn("何时引", bundle)
        self.assertIn("跨著作补充", bundle)
        self.assertIn("外部补全与多源融入", bundle)
        self.assertIn("母本去重", bundle)
        self.assertNotIn("### 外部补全与多源融入（权威）", bundle)
        self.assertIn("历史研究者", bundle)
        self.assertIn("五类准入", bundle)
        self.assertNotIn("## 跨著作补充（权威）", bundle)
        self.assertNotIn("每批至少", bundle)
        self.assertNotIn("### 异说（P0 硬约束）", bundle)
        self.assertIn("## 校验与术语", bundle)
        self.assertNotIn("## 硬约束（P0）", bundle)
        self.assertNotIn("### 执行优先级", bundle)
        self.assertNotIn("### 精简四步成稿", bundle)
        self.assertEqual(bundle.count("母本覆盖"), 1)
        self.assertNotIn("【本阶段】分批成稿：严格按 plan", bundle)

    def test_normalize_corner_quotes(self):
        from lib.prose_sanitize import normalize_corner_quotes

        self.assertEqual(normalize_corner_quotes("『习用干戈』"), "「习用干戈」")

    def test_sanitize_mother_keeps_bare_classic_titles(self):
        """无 · 的典籍《》不得降格为「」；与引号校正解耦。"""
        from lib.prose_sanitize import sanitize_mother_detail

        raw = (
            "《汉书》载，武帝读『易经』；"
            "又见《易经》与《史记·封禅书》。"
            "误标《「画法」》应还原。"
        )
        out = sanitize_mother_detail(raw)
        self.assertIn("《汉书》", out)
        self.assertIn("《易经》", out)
        self.assertIn("《史记·封禅书》", out)
        self.assertIn("「易经」", out)  # 『』→「」仅改引号形态
        self.assertNotIn("『", out)
        self.assertIn("「画法」", out)
        self.assertNotIn("《「画法」》", out)
        self.assertNotIn("「汉书」", out)
        self.assertNotIn("「易经」与", out)  # 《易经》不得被降成「易经」

    def test_sanitize_enrich_keeps_six_arts_titles(self):
        """六经语境下典籍仍用《》，不再降格。"""
        from lib.prose_sanitize import sanitize_enrich_detail

        raw = "他通六经，尤好《诗》《书》《易》。"
        out = sanitize_enrich_detail(raw)
        self.assertIn("《诗》", out)
        self.assertIn("《书》", out)
        self.assertIn("《易》", out)
        self.assertNotIn("「诗」", out)

    def test_finalize_fixes_white_corner_quotes(self):
        from lib.final_polish import finalize_translation_detail

        recalled = {"母本著作": "01史记", "blocks": [], "史料原文": "习用干戈"}
        detail, changes = finalize_translation_detail(
            "他说『习用干戈』。",
            recalled,
            mother_text="习用干戈",
        )
        self.assertIn("「习用干戈」", detail)
        self.assertNotIn("『", detail)
        self.assertTrue(any("『』" in c for c in changes))

    def test_reference_section_drops_bare_mother_when_volumes_exist(self):
        from lib.final_polish import build_reference_section_from_body

        body = (
            "《史记》原文说「孝武皇帝者，孝景中子也」。"
            "《史记·封禅书》补了一笔。"
        )
        recalled = {
            "母本著作": "01史记",
            "主要史料出处": "《史记·孝武本纪》",
        }
        ref_block = build_reference_section_from_body(body, recalled)
        self.assertIn("孝武本纪", ref_block)
        self.assertIn("封禅书", ref_block)
        self.assertNotIn("2. 《史记》\n", ref_block)
        self.assertNotRegex(ref_block, r"\d+\. 《史记》\s*$")

    def test_reference_section_drops_bare_hanshu_framing(self):
        """正文 framing 的裸《汉书》保留《》，但不入参考著作。"""
        from lib.final_polish import build_reference_section_from_body

        body = "《汉书》载武帝好《易经》。又见《汉书·郊祀志》。"
        recalled = {
            "母本著作": "01史记",
            "主要史料出处": "《史记·孝武本纪》",
        }
        ref_block = build_reference_section_from_body(body, recalled)
        self.assertIn("孝武本纪", ref_block)
        self.assertIn("郊祀志", ref_block)
        self.assertIn("易经", ref_block)  # 单书名可入列
        self.assertNotIn("《汉书》\n", ref_block)
        self.assertNotRegex(ref_block, r"\d+\. 《汉书》\s*$")

    def test_verify_rejects_bare_shiji_in_reference_section(self):
        from lib.verify import _detect_reference_granularity

        detail = (
            "正文。\n\n参考著作：\n"
            "1. 《史记·孝武本纪》\n"
            "2. 《史记》\n"
            "3. 《史记·封禅书》"
        )
        errs = _detect_reference_granularity(detail)
        self.assertTrue(any("《史记》" in e for e in errs))

    def test_plan_no_prose_narrator(self):
        from lib.narrator_framing import narrator_block_for_phase

        self.assertIn("规划编辑", narrator_block_for_phase("plan"))
        self.assertEqual(narrator_block_for_phase("unknown_phase"), "")


if __name__ == "__main__":
    unittest.main()
