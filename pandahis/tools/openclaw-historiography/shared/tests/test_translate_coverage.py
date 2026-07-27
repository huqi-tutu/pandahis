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

    def test_qi_m001_short_sentence_paraphrase(self) -> None:
        """启 M001：以天下授益 → 白话转述须命中，勿因泛词过滤误杀。"""
        item = {
            "编号": "M001",
            "原文摘句": "以天下授益。",
            "信息点": "禹将天下传给益。",
            "必现词": [],
        }
        body = "禹在去世前，把天下交给了益。三年丧期一满，益主动让位……"
        score = item_coverage_score(item, body)
        self.assertGreaterEqual(score, 0.32, msg=f"score={score}")

    def test_verify_passes_reasonable_paraphrase(self) -> None:
        import os

        os.environ["TRANSLATE_COVERAGE_MODE"] = "l1"
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


from lib.coverage_l2 import semantic_coverage_gate_passed  # noqa: E402


class TestSemanticCoverageGate(unittest.TestCase):
    def test_pass_at_eighty_percent(self) -> None:
        ok, _ = semantic_coverage_gate_passed(16, 20, 4, min_ratio=0.80, max_fail=3)
        self.assertTrue(ok)

    def test_pass_when_fail_count_within_limit(self) -> None:
        ok, _ = semantic_coverage_gate_passed(17, 20, 3, min_ratio=0.80, max_fail=3)
        self.assertTrue(ok)

    def test_fail_when_both_thresholds_missed(self) -> None:
        ok, note = semantic_coverage_gate_passed(14, 20, 6, min_ratio=0.80, max_fail=3)
        self.assertFalse(ok)
        self.assertIn("未传达 6 条", note)

    def test_empty_total_passes(self) -> None:
        ok, _ = semantic_coverage_gate_passed(0, 0, 0)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
