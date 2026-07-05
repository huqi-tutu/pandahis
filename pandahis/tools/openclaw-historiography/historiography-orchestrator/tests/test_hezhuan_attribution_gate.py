"""合传 segment_attribution 归属规则测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ANNOTATE = Path(__file__).resolve().parents[2] / "historiography-annotate"
sys.path.insert(0, str(ANNOTATE))

from hezhuan_attribution_gate import (  # noqa: E402
    hezhuan_uses_independent_paragraphs,
    paragraph_mentions_person,
    validate_segment_ownership,
)


def _hezhuan_skel(attribution: list, *, mode: str = "hezhuan") -> dict:
    return {
        "volume": "张耳陈馀传",
        "narrative_mode": mode,
        "protagonist_count": 2,
        "protagonists_manifest": [
            {"name": "张耳", "category": "武将"},
            {"name": "陈馀", "category": "武将"},
        ],
        "entries": [
            {"史略名称": "张耳", "史略分类": "武将"},
            {"史略名称": "陈馀", "史略分类": "武将"},
        ],
        "segment_attribution": attribution,
    }


class TestHezhuanAttributionGate(unittest.TestCase):
    def test_non_hezhuan_rejects_multi_owner(self) -> None:
        data = _hezhuan_skel(
            [{"paragraph": 2, "owners": [{"name": "张耳"}, {"name": "陈馀"}]}],
            mode="single",
        )
        errs = validate_segment_ownership(data, {2: "张耳、陈馀俱之陈"})
        self.assertTrue(any("禁止多归属" in e for e in errs))

    def test_co_narrative_allows_multi_when_both_mentioned(self) -> None:
        text = "张耳，大梁人也。陈馀，亦大梁人，好儒术。耳、馀上谒涉。"
        data = _hezhuan_skel(
            [{"paragraph": 2, "owners": [{"name": "张耳"}, {"name": "陈馀"}]}],
        )
        errs = validate_segment_ownership(data, {2: text})
        self.assertEqual(errs, [])

    def test_co_narrative_rejects_missing_subject(self) -> None:
        text = "赵相贯高怒曰：吾王孱王也！张王旦暮自上食。"
        data = _hezhuan_skel(
            [{"paragraph": 8, "owners": [{"name": "张耳"}, {"name": "陈馀"}]}],
        )
        errs = validate_segment_ownership(data, {8: text})
        self.assertTrue(
            any("陈馀" in e for e in errs)
            or any("分段独立合传" in e for e in errs)
        )

    def test_independent_blocks_reject_multi_owner(self) -> None:
        para_text = {
            2: "张耳，大梁人也，少时及魏公子毋忌为客。",
            3: "陈馀，亦大梁人，好儒术。游赵苦陉。",
        }
        data = _hezhuan_skel(
            [
                {"paragraph": 2, "owners": [{"name": "张耳"}]},
                {"paragraph": 3, "owners": [{"name": "张耳"}, {"name": "陈馀"}]},
            ],
        )
        self.assertTrue(
            hezhuan_uses_independent_paragraphs(data, para_text, ["张耳", "陈馀"])
        )
        errs = validate_segment_ownership(data, para_text)
        self.assertTrue(any("分段独立合传" in e for e in errs))

    def test_paragraph_mentions_single_char(self) -> None:
        self.assertTrue(paragraph_mentions_person("张耳", "耳、馀上谒涉"))
        self.assertTrue(paragraph_mentions_person("陈馀", "耳、馀上谒涉"))

    def test_alias_name_mentions_for_same_paragraph_handoff(self) -> None:
        text = (
            "以《鲁诗》教授楚国，龚胜、舍师事焉。萧望之为御史大夫，除广德为属，"
            "数与论议，器之，荐广德经行宜充本朝。为博士，论石渠，迁谏大夫，"
            "代贡禹为长信少府、御史大夫。广德为人温雅有醖藉。"
            "平当字子思，祖父以訾百万，自下邑徙平陵。"
        )
        data = {
            "volume": "隽疏于薛平彭传",
            "narrative_mode": "hezhuan",
            "protagonist_count": 2,
            "protagonists_manifest": [
                {"name": "薛广德", "category": "文臣"},
                {"name": "平当", "category": "文臣"},
            ],
            "entries": [
                {"史略名称": "薛广德", "史略分类": "文臣"},
                {"史略名称": "平当", "史略分类": "文臣"},
            ],
            "segment_attribution": [
                {
                    "paragraph": 15,
                    "owners": [{"name": "薛广德"}, {"name": "平当"}],
                }
            ],
        }
        self.assertTrue(paragraph_mentions_person("薛广德", text))
        self.assertTrue(paragraph_mentions_person("平当", text))
        self.assertEqual(validate_segment_ownership(data, {15: text}), [])

    def test_087_whitelisted_handoff_allows_multi_owner_without_repeated_name(self) -> None:
        text = (
            "少时好侠，斗鸡走马，长乃变节，从嬴公受《春秋》。以明经为议郎，至符节令。"
            "孝昭元凤三年正月，泰山、莱芜山南匈匈有数千人声。"
            "后五年，孝宣帝兴于民间，即位，征孟子为郎。夏侯始昌，鲁人也。"
        )
        data = {
            "volume": "眭两夏侯京翼李传",
            "narrative_mode": "hezhuan",
            "protagonist_count": 2,
            "protagonists_manifest": [
                {"name": "眭弘", "category": "文臣"},
                {"name": "夏侯始昌", "category": "文臣"},
            ],
            "entries": [
                {"史略名称": "眭弘", "史略分类": "文臣"},
                {"史略名称": "夏侯始昌", "史略分类": "文臣"},
            ],
            "segment_attribution": [
                {
                    "paragraph": 3,
                    "owners": [{"name": "眭弘"}, {"name": "夏侯始昌"}],
                }
            ],
        }
        self.assertEqual(validate_segment_ownership(data, {3: text}), [])


if __name__ == "__main__":
    unittest.main()
