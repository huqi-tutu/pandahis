"""翻译线母本覆盖验收（信息点概率制）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "historiography-translate"
sys.path.insert(0, str(ROOT))

from lib.coverage import item_coverage_score, verify_mother_coverage  # noqa: E402
from lib.coverage_info import (  # noqa: E402
    build_coverage_units,
    info_point_is_classical,
    sanitize_info_point,
)


class TestCoverageInfo(unittest.TestCase):
    def test_classical_info_detected(self) -> None:
        orig = "令益予众庶稻，可种卑湿。"
        self.assertTrue(info_point_is_classical(orig, orig))
        self.assertEqual(sanitize_info_point(orig, orig), "")

    def test_baihua_info_kept(self) -> None:
        info = "禹令益把稻种分给百姓，可在低湿处种植。"
        orig = "令益予众庶稻，可种卑湿。"
        self.assertFalse(info_point_is_classical(info, orig))
        self.assertEqual(sanitize_info_point(info, orig), info)


class TestCoverageScore(unittest.TestCase):
    def test_paraphrase_scores_higher_than_literal_keyword_miss(self) -> None:
        item = {
            "编号": "M023",
            "原文摘句": "令益予众庶稻，可种卑湿。",
            "信息点": "",
            "必现词": [],
        }
        body = "他让益把稻种分给百姓，方便大家在那些低湿的田地里种上庄稼。"
        score = item_coverage_score(item, body)
        self.assertGreater(score, 0.32)

    def test_baihua_info_point_matches_translation(self) -> None:
        item = {
            "原文摘句": "令益予众庶稻，可种卑湿。",
            "信息点": "禹令益把稻种分给百姓，可在低湿处种植。",
            "必现词": [],
        }
        body = "他让益把稻种分给百姓，方便大家在那些低湿的田地里种上庄稼。"
        self.assertGreater(item_coverage_score(item, body), 0.18)


class TestCoverageVerify(unittest.TestCase):
    def test_parallel_cluster_grouping(self) -> None:
        checklist = [
            {
                "编号": "M029",
                "段落": "P1",
                "引用粒度": "parallel_cluster",
                "原文摘句": "其土白壤。",
                "信息点": "",
            },
            {
                "编号": "M030",
                "段落": "P1",
                "引用粒度": "parallel_cluster",
                "原文摘句": "赋上上错，田中中。",
                "信息点": "",
            },
        ]
        units = build_coverage_units(checklist)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].kind, "group")

    def test_verify_passes_reasonable_paraphrase(self) -> None:
        plan = {
            "母本逐句清单": [
                {
                    "编号": "M001",
                    "原文摘句": "夏禹，名曰文命。",
                    "信息点": "夏禹名叫文命。",
                    "必现词": ["夏禹", "文命"],
                },
                {
                    "编号": "M023",
                    "原文摘句": "令益予众庶稻，可种卑湿。",
                    "信息点": "禹令益把稻种分给百姓，可在低湿处种植。",
                    "必现词": [],
                },
            ]
        }
        detail = (
            "这是一段引入，交代阅读框架。\n\n"
            "司马迁先记：夏禹，名曰文命。\n\n"
            "治水时，他让益把稻种分给百姓，方便大家在那些低湿的田地里种上庄稼。"
        )
        ok, errs = verify_mother_coverage(detail, plan, min_ratio=0.5)
        self.assertTrue(ok, msg="; ".join(errs))


if __name__ == "__main__":
    unittest.main()
