"""citation_mode：提示文案、经典引用候选、索引补充纠偏。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.citation_mode import (  # noqa: E402
    apply_quote_style_fixes,
    citation_mode_hint,
    classic_quote_soft_quota,
    count_classic_corner_quotes,
    detect_curly_source_quotes,
    enrich_checklist_citation_modes,
    fix_corner_vernacular_to_curly,
    fix_curly_source_to_corner,
    mark_classic_quote_candidates,
    score_classic_quote_candidate,
)
from lib.plan_postprocess import inject_index_supplements_plan  # noqa: E402


class TestCitationHints(unittest.TestCase):
    def test_no_legacy_gloss_instruction(self) -> None:
        for mode in ("narrative", "parallel_cluster", "genealogy", "appraisal"):
            h = citation_mode_hint(mode)
            self.assertNotIn("先整段或整簇引用原文，再作一段白话解释", h)
            self.assertNotIn("「」用于完整摘句、对话或并列句群", h)
            self.assertIn("白话", h)

    def test_enrich_replaces_legacy_hint(self) -> None:
        cl = [
            {
                "编号": "M001",
                "原文摘句": "仁而爱人，喜施，意豁如也。常有大度。",
                "母本提示": "并列句群：先整段或整簇引用原文，再作一段白话解释。",
            }
        ]
        enrich_checklist_citation_modes(cl)
        tip = cl[0]["母本提示"]
        self.assertNotIn("先整段或整簇引用原文，再作一段白话解释", tip)
        self.assertTrue("直角「」" in tip or "引用" in tip)


class TestClassicCandidates(unittest.TestCase):
    def test_quota_scales(self) -> None:
        self.assertGreaterEqual(classic_quote_soft_quota(29), 2)
        self.assertLessEqual(classic_quote_soft_quota(29), 8)
        q = classic_quote_soft_quota(467)
        self.assertGreaterEqual(q, 8)
        self.assertLessEqual(q, 15)

    def test_appraisal_scores_high(self) -> None:
        s = score_classic_quote_candidate(
            "生而神灵，弱而能言，幼而徇齐，长而敦敏，成而聪明。",
            "appraisal",
        )
        self.assertGreaterEqual(s, 5)

    def test_mark_respects_quota(self) -> None:
        cl = []
        for i in range(50):
            cl.append(
                {
                    "编号": f"M{i+1:03d}",
                    "原文摘句": f"仁而爱人，喜施，意豁如也，常有大度{i}。",
                    "引用粒度": "parallel_cluster",
                }
            )
        n = mark_classic_quote_candidates(cl)
        self.assertGreater(n, 0)
        self.assertLessEqual(n, classic_quote_soft_quota(50))
        self.assertTrue(any(x.get("经典引用候选") for x in cl))

    def test_count_corner_quotes(self) -> None:
        t = "他说：“白话。”又引「生而神灵，弱而能言」和「短」。"
        self.assertEqual(count_classic_corner_quotes(t, min_len=6), 1)


class TestQuoteStyleFixes(unittest.TestCase):
    def _plan(self) -> dict:
        return {
            "母本逐句清单": [
                {
                    "编号": "M001",
                    "原文摘句": "鸿渐于般。元封元年天子始建汉家之封。天道将军。",
                    "经典引用候选": True,
                },
                {
                    "编号": "M002",
                    "原文摘句": "仁而爱人，喜施，意豁如也。",
                    "经典引用候选": False,
                },
            ]
        }

    def test_a_curly_source_to_corner(self) -> None:
        plan = self._plan()
        text = "方士说：“鸿渐于般”，又题“天道将军”，年号“元封元年”。"
        fixed, n = fix_curly_source_to_corner(text, plan)
        self.assertGreaterEqual(n, 2)
        self.assertIn("「鸿渐于般」", fixed)
        self.assertIn("「天道将军」", fixed)
        self.assertIn("「元封元年」", fixed)
        self.assertEqual(detect_curly_source_quotes(fixed, plan), [])

    def test_b_corner_vernacular_to_curly(self) -> None:
        plan = self._plan()
        text = "他笑道：「这事就这么定了吧，你们可以回去了。」"
        fixed, n = fix_corner_vernacular_to_curly(text, plan)
        self.assertEqual(n, 1)
        self.assertIn("“这事就这么定了吧，你们可以回去了。”", fixed)
        self.assertNotIn("「这事就这么定了吧", fixed)

    def test_b_protects_classic_source(self) -> None:
        plan = self._plan()
        text = "史载「仁而爱人，喜施，意豁如也」。"
        fixed, n = fix_corner_vernacular_to_curly(text, plan)
        self.assertEqual(n, 0)
        self.assertIn("「仁而爱人，喜施，意豁如也」", fixed)

    def test_apply_both(self) -> None:
        plan = self._plan()
        text = (
            "他道：“鸿渐于般”。旁人却说：「这事你们可以回去了吧。」"
        )
        fixed, changes = apply_quote_style_fixes(text, plan)
        self.assertTrue(any("弯引原文" in c for c in changes))
        self.assertTrue(any("直角白话" in c for c in changes))
        self.assertIn("「鸿渐于般」", fixed)
        self.assertIn("“这事你们可以回去了吧。”", fixed)

    def test_vernacular_with_wenyan_honorific_uses_curly(self) -> None:
        """半白话对白（我听说/如今）即使含「足下」，只要不是母本原文子串，用弯引。"""
        source = "臣闻足下约，先入咸阳者王之。今足下留守宛。"
        text = "陈恢说：「我听说足下有约，先入咸阳者为王。如今足下却留守宛城。」"
        fixed, n = fix_corner_vernacular_to_curly(
            text, {"母本逐句清单": []}, source_original=source
        )
        self.assertEqual(n, 1)
        self.assertIn("“我听说足下有约，先入咸阳者为王。如今足下却留守宛城。”", fixed)

    def test_source_original_blob_converts_curly_source(self) -> None:
        source = "嗟乎，大丈夫当如此也！"
        text = "他脱口叹道：“嗟乎，大丈夫当如此也！”"
        fixed, n = fix_curly_source_to_corner(
            text, {"母本逐句清单": []}, source_original=source
        )
        self.assertGreaterEqual(n, 1)
        self.assertIn("「嗟乎，大丈夫当如此也！」", fixed)


class TestIndexSupplementUpgrade(unittest.TestCase):
    def test_no_index_seed_for_empty_external(self) -> None:
        """空外部补全不得用索引书目自动种子（跨书选题归 LLM）。"""
        from lib.plan_postprocess import finalize_plan

        plan = {
            "母本逐句清单": [{"编号": f"M{i:03d}", "原文摘句": f"句{i}。"} for i in range(50)],
            "外部补全": [],
            "索引补充处理": [
                {
                    "出处": "《汉书·高帝纪第一上》",
                    "处理": "异说",
                    "理由": "平行正史筛差异",
                }
            ],
        }
        out = finalize_plan(plan, recalled=None)
        self.assertEqual(out.get("外部补全") or [], [])
        self.assertNotIn("外部补全种子", (out.get("_长文兼容") or {}))

    def test_merge_keeps_skeleton_checklist(self) -> None:
        from lib.plan_postprocess import merge_llm_plan_decisions

        skeleton = {
            "母本逐句清单": [{"编号": "M001", "原文摘句": "甲。"}],
            "外部补全": [],
            "索引补充处理": [{"出处": "《汉书·高帝纪》", "处理": "异说"}],
        }
        llm = {
            "母本逐句清单": [{"编号": "M999", "原文摘句": "应被忽略。"}],
            "外部补全": [
                {
                    "采用": True,
                    "出处": "《史记·项羽本纪》",
                    "补全类型": "补充细节",
                    "与母本关系": "鸿门宴细节母本本纪略写、列传较详",
                }
            ],
            "参考著作": ["《史记·项羽本纪》"],
        }
        merged = merge_llm_plan_decisions(skeleton, llm)
        self.assertEqual(merged["母本逐句清单"][0]["编号"], "M001")
        self.assertEqual(merged["外部补全"][0]["出处"], "《史记·项羽本纪》")
        self.assertEqual(merged["索引补充处理"][0]["处理"], "异说")

    def test_parallel_hanshu_not_deduped(self) -> None:
        mother = "高祖沛丰邑人" * 80
        hanshu = "高祖沛丰邑人" * 70 + "异文年号细节若干"
        recalled = {
            "母本著作": "01史记",
            "blocks": [
                {
                    "role": "母本",
                    "work": "01史记",
                    "vol": "008",
                    "volume": "高祖本纪",
                    "paragraphs": [{"id": 1, "text": mother}],
                },
                {
                    "role": "补充",
                    "work": "02汉书",
                    "vol": "001",
                    "volume": "高帝纪第一上",
                    "paragraphs": [{"id": 2, "text": hanshu}],
                },
            ],
        }
        plan = {
            "母本著作": "01史记",
            "索引补充处理": [
                {
                    "出处": "《汉书·高帝纪第一上》",
                    "处理": "去重不用",
                    "理由": "与母本主体一致",
                }
            ],
        }
        inject_index_supplements_plan(plan, recalled)
        entries = plan["索引补充处理"]
        self.assertTrue(entries)
        self.assertEqual(entries[0]["处理"], "异说")
        self.assertIn("差异", entries[0]["理由"])


    def test_demote_same_mother_volume(self) -> None:
        """正在翻译的同一卷不得采用为外部补全。"""
        from lib.plan_postprocess import finalize_external, is_same_mother_volume

        recalled = {
            "母本著作": "01史记",
            "blocks": [
                {
                    "role": "母本",
                    "work": "01史记",
                    "source_file": "01史记_008_高祖本纪第八.txt",
                    "paragraphs": [{"id": 1, "text": "高祖沛丰邑中阳里人。"}],
                }
            ],
        }
        self.assertTrue(
            is_same_mother_volume("《史记·高祖本纪》", recalled=recalled, plan={})
        )
        self.assertFalse(
            is_same_mother_volume("《史记·项羽本纪》", recalled=recalled, plan={})
        )
        plan = {
            "外部补全": [
                {
                    "采用": True,
                    "出处": "《史记·高祖本纪》",
                    "补全类型": "补充细节",
                    "与母本关系": "本卷另段细节，实为重复母本卷",
                },
                {
                    "采用": True,
                    "出处": "《史记·项羽本纪》",
                    "补全类型": "补充细节",
                    "与母本关系": "鸿门宴场面细节母本略写",
                },
            ]
        }
        finalize_external(plan, recalled)
        self.assertFalse(plan["外部补全"][0]["采用"])
        self.assertTrue(plan["外部补全"][1]["采用"])
        self.assertIn("同一卷", plan["外部补全"][0].get("理由") or "")


if __name__ == "__main__":
    unittest.main()
