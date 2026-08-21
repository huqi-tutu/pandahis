"""外部补全逐条落地与定向补洞。"""

from __future__ import annotations

import unittest

from lib.enrich_landing import (
    apply_landing_inserts,
    check_item_landing,
    cross_book_landing_errors,
    format_landing_checklist_note,
    is_landing_only_failure,
    iter_external_landing_items,
    missing_landing_items,
)
from lib.plan_postprocess import plan_for_enrich_phase
from lib.verify import _cross_book_hard_errors, _plan_cross_book_sources


class EnrichLandingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = {
            "外部补全": [
                {
                    "采用": True,
                    "主题": "刘邦出生神话的异说",
                    "出处": "《汉书·高帝纪》",
                    "与母本关系": "增补太公见蛟龙于其上，并明确已而有娠",
                    "母本锚点": "M004 后",
                },
                {
                    "采用": True,
                    "主题": "刘邦与项羽的对比评价",
                    "出处": "《汉书·项籍传》",
                    "与母本关系": "班固赞对比：背关怀楚、放逐义帝 vs 入关约法",
                    "母本锚点": "M096 后",
                },
                {
                    "采用": False,
                    "主题": "不采用项",
                    "出处": "《资治通鉴·汉纪》",
                    "母本锚点": "M010 后",
                },
            ],
            "索引补充处理": [
                {
                    "出处": "《汉书·高帝纪第一上》",
                    "处理": "异说",
                    "锚点": "按事件挂母本对应 M",
                }
            ],
        }

    def test_enrich_phase_still_detects_landing(self) -> None:
        enrich = plan_for_enrich_phase(self.plan)
        items = iter_external_landing_items(enrich)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(x.get("_须落地") for x in enrich["外部补全"]))
        # 旧 OR-any 在 enrich 切片上会 required=[]；现应仍能列出书名
        titles = _plan_cross_book_sources(enrich)
        self.assertIn("汉书·高帝纪", titles)
        self.assertIn("汉书·项籍传", titles)

    def test_per_item_not_or_any(self) -> None:
        # 只有高帝纪 → 项籍传仍应失败
        body = "出生时太公见蛟龙。《汉书·高帝纪》还写已而有娠。"
        errs = cross_book_landing_errors(body, self.plan, label="测")
        self.assertTrue(any("项籍传" in e or "对比评价" in e for e in errs))
        self.assertFalse(any("出生神话" in e for e in errs))

    def test_keyword_required_when_source_present(self) -> None:
        body = "班固在《汉书·项籍传》里写了几句，略过不表。"
        items = iter_external_landing_items(self.plan)
        xiang = [x for x in items if "项籍" in x["出处"]][0]
        ok, reason = check_item_landing(body, xiang)
        self.assertFalse(ok)
        self.assertIn("主题指纹", reason)

    def test_v11_style_false_pass_blocked(self) -> None:
        """旧逻辑：正文有《汉书·高帝纪》即整项 PASS；现应拦项籍传。"""
        body = (
            "事迹见于《史记·高祖本纪》，并行记载亦见于《汉书·高帝纪》。"
            "刘媪梦与神遇，太公见蛟龙，已而有娠。"
        )
        errs = _cross_book_hard_errors(body, self.plan, label="成稿")
        self.assertTrue(errs)
        self.assertTrue(any("项籍" in e or "对比" in e for e in errs))

    def test_checklist_note(self) -> None:
        note = format_landing_checklist_note(plan_for_enrich_phase(self.plan))
        self.assertIn("本章须落地", note)
        self.assertIn("项籍传", note)

    def test_apply_inserts(self) -> None:
        body = "他心胸豁达开朗。平素很有气度。"
        new, n = apply_landing_inserts(
            body,
            [
                {
                    "marker": "心胸豁达开朗",
                    "paragraph": "《汉书·高帝纪》更爱用「豁达大度」四字。",
                }
            ],
        )
        self.assertEqual(n, 1)
        self.assertIn("豁达大度", new)
        self.assertIn("平素很有气度", new)

    def test_skip_insert_inside_corner_quote(self) -> None:
        body = (
            "他叹息一声，说出了一句让在场所有人都心里发毛的话：「嗟乎！"
            "吾诚得如黄帝，吾视去妻子如脱躧耳。」当场拜公孙卿为郎。"
        )
        new, n = apply_landing_inserts(
            body,
            [
                {
                    "marker": "眼睛都直了",  # not in body
                    "paragraph": "旁白。",
                },
                {
                    "marker": "说出了一句让在场所有人都心里发毛的话：",
                    "paragraph": (
                        "说起求仙，那真是《史记·封禅书》里浓墨重彩的一笔。"
                        "信得痴，杀得狠，追得急。"
                    ),
                },
            ],
        )
        self.assertEqual(n, 0)
        self.assertIn("「嗟乎！", new)
        self.assertNotIn("信得痴", new)

    def test_skip_insert_when_paraphrase_already_present(self) -> None:
        body = (
            "说起求仙，那真是《史记·封禅书》里浓墨重彩的一笔。"
            "方士一个接一个登场，信得痴，杀得狠，追得急，一辈子跟神仙较劲。\n\n"
            "他听完公孙卿的故事，眼睛都直了。"
        )
        new, n = apply_landing_inserts(
            body,
            [
                {
                    "marker": "眼睛都直了",
                    "paragraph": (
                        "说起汉武帝求仙与方士，那真是《史记·封禅书》里浓墨重彩的一笔。"
                        "李少君栾大公孙卿一个接一个，信得痴，杀得狠，追得急，"
                        "一辈子都在跟神仙较劲。"
                    ),
                }
            ],
        )
        self.assertEqual(n, 0)
        self.assertEqual(new.count("信得痴"), 1)

    def test_landing_only_failure_detect(self) -> None:
        self.assertTrue(
            is_landing_only_failure(
                ["成稿：外部补全未落地「x」@ M1 — 缺出处"]
            )
        )
        self.assertFalse(
            is_landing_only_failure(
                ["成稿：外部补全未落地「x」", "成稿：几乎誊抄母本"]
            )
        )

    def test_missing_list(self) -> None:
        miss = missing_landing_items("只有白话没有书名。", self.plan)
        self.assertEqual(len(miss), 2)


if __name__ == "__main__":
    unittest.main()
