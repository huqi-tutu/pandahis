"""外部补全 vs 全书母本信息点判重（脚本粗筛）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.external_dedupe import (  # noqa: E402
    apply_external_mother_dedupe,
    overlap_ratio,
    score_external_against_mother,
    script_demote_duplicates,
)
from lib.plan_postprocess import finalize_plan  # noqa: E402


class TestExternalDedupe(unittest.TestCase):
    def test_overlap_detects_shared_event(self) -> None:
        self.assertGreater(
            overlap_ratio("鸿门宴樊哙闯帐细节", "鸿门宴上樊哙带剑闯帐护卫沛公"),
            0.4,
        )

    def test_script_demotes_pre_anchor_duplicate_of_later_mother(self) -> None:
        plan = {
            "母本逐句清单": [
                {"编号": "M010", "原文摘句": "沛公旦日从百余骑来见项王。", "信息点": "沛公次日带随从见项王"},
                {
                    "编号": "M180",
                    "原文摘句": "樊哙带剑拥盾入军门，嗔目视项王，头发上指。",
                    "信息点": "樊哙闯帐护卫沛公怒视项王",
                },
            ],
            "外部补全": [
                {
                    "采用": True,
                    "补全类型": "补充细节",
                    "主题": "樊哙带剑闯帐怒视项王护卫沛公",
                    "出处": "《史记·项羽本纪》",
                    "母本锚点": "M010 后",
                    "与母本关系": "补充宴会场面",  # 无未载/差异话术 → 脚本应降级
                },
                {
                    "采用": True,
                    "补全类型": "异说",
                    "主题": "年号起迄与本纪不同",
                    "出处": "《汉书·高帝纪》",
                    "母本锚点": "M010 后",
                    "与母本关系": "母本未载汉纪年号细节；汉书另记，属异说增量",
                },
            ],
        }
        stats = script_demote_duplicates(plan)
        self.assertFalse(plan["外部补全"][0]["采用"])
        self.assertGreaterEqual(stats["demoted"], 1)
        # 第二条有明确差异话术且主题与母本不重合 → 仍可采用或仅可疑
        self.assertTrue(
            plan["外部补全"][1]["采用"] is True
            or plan["外部补全"][1].get("_判重") == "suspicious"
        )

    def test_finalize_runs_script_dedupe(self) -> None:
        plan = {
            "史略ID": "T",
            "外部补全": [
                {
                    "采用": True,
                    "补全类型": "补充细节",
                    "主题": "高祖送徒骊山丰西泽中拔剑击斩大蛇",
                    "出处": "《汉书·高帝纪》",
                    "母本锚点": "M001 后",
                    "与母本关系": "补充斩蛇经过",
                }
            ],
            "母本逐句清单": [
                {
                    "编号": "M050",
                    "原文摘句": "高祖以亭长为县送徒骊山，到丰西泽中，有大蛇当径，高祖拔剑击斩蛇。",
                    "信息点": "高祖送徒遇蛇拔剑斩蛇",
                }
            ],
            "写作结构": [{"小节": "本传"}],
            "参考著作": ["《史记》"],
        }
        out = finalize_plan(plan, recalled=None, external_dedupe_llm=False)
        adopted = [x for x in out["外部补全"] if x.get("采用") is True]
        self.assertEqual(len(adopted), 0)
        self.assertGreaterEqual((out.get("_外部补全判重") or {}).get("script_demoted", 0), 1)

    def test_score_finds_later_m(self) -> None:
        rows = [
            {"编号": "M001", "文本": "起于沛丰", "信息点": "起于沛丰", "原文摘句": ""},
            {"编号": "M200", "文本": "白登之围匈奴围刘邦七日", "信息点": "白登被围七日", "原文摘句": ""},
        ]
        item = {
            "主题": "白登匈奴围刘邦七日不得出",
            "与母本关系": "补充被围经过",
        }
        score, mid = score_external_against_mother(item, rows)
        self.assertGreater(score, 0.45)
        self.assertEqual(mid, "M200")


if __name__ == "__main__":
    unittest.main()
