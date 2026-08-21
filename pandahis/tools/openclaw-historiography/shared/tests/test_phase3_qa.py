"""Phase3–5 质检/修复工具函数。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.phase3_qa import (  # noqa: E402
    build_accepted_issue_text,
    extract_fenced_block,
    extract_repaired_body,
    merge_qa_report,
    program_qa_findings,
)


class TestPhase3ProgramQA(unittest.TestCase):
    def test_detects_garbled_and_timeline(self) -> None:
        mother = "甲" * 500
        detail = (
            "前文。又了也受不了，于是把瑟破开。\n\n"
            "到了征和四年，下轮台诏悔过。\n\n"
            "第二年，天子又往东边巡游，公玊带又来凑热闹。"
        )
        finds = program_qa_findings(mother=mother, detail=detail)
        cats = {f["类别"] for f in finds}
        self.assertIn("标点", cats)
        self.assertIn("时间线", cats)

    def test_merge_p0_fails(self) -> None:
        report = merge_qa_report(
            [{"级别": "P0", "类别": "事实错误", "说明": "次子误", "摘录": ""}],
            {"通过": True, "问题": [], "摘要": "ok"},
        )
        self.assertFalse(report["通过"])

    def test_extract_fenced_block(self) -> None:
        raw = "前言\n<<<QA_JSON\n{\"通过\": false}\nQA_JSON\n后记"
        self.assertIn("通过", extract_fenced_block(raw, "QA_JSON"))

    def test_extract_repaired_body(self) -> None:
        raw = "<<<REPAIRED\n修复后的正文段落。\nREPAIRED\n<<<REPAIR_JSON\n{}\nREPAIR_JSON"
        self.assertEqual(extract_repaired_body(raw), "修复后的正文段落。")

    def test_build_accepted_issue_text_includes_listed_p2(self) -> None:
        text = build_accepted_issue_text(
            qa_md="报告全文",
            qa_json={
                "问题": [
                    {"级别": "P0", "类别": "时间", "说明": "年号错", "摘录": "甲"},
                    {"级别": "P2", "类别": "表达", "说明": "白话误用直角引号", "摘录": "乙"},
                ],
                "优先修改": ["P0-1"],
            },
            accept={"接受全部P0": True},
        )
        self.assertIn("年号错", text)
        self.assertIn("自动采纳", text)
        self.assertIn("白话误用直角引号", text)

    def test_detects_markdown_heading(self) -> None:
        mother = "甲" * 500
        detail = "开场。\n\n## 一、新朝气象\n\n后文。\n\n参考著作：\n- 《史记》"
        finds = program_qa_findings(mother=mother, detail=detail)
        self.assertTrue(any("章节标题" in f.get("说明", "") for f in finds))

    def test_missing_refs_when_supplement_signal(self) -> None:
        mother = "甲" * 500
        detail = "正文提到《汉书》另有记载，却不列书目。"
        finds = program_qa_findings(mother=mother, detail=detail)
        cats = {f["类别"] for f in finds}
        self.assertIn("史源", cats)

    def test_plan_external_hunt_default_off(self) -> None:
        import os

        from lib.external_macro import plan_external_hunt_enabled

        old = os.environ.pop("TRANSLATE_PLAN_EXTERNAL", None)
        old_mode = os.environ.get("TRANSLATE_PHASE2_MODE")
        try:
            os.environ["TRANSLATE_PHASE2_MODE"] = "polish"
            self.assertFalse(plan_external_hunt_enabled())
            os.environ["TRANSLATE_PLAN_EXTERNAL"] = "1"
            self.assertTrue(plan_external_hunt_enabled())
        finally:
            if old is None:
                os.environ.pop("TRANSLATE_PLAN_EXTERNAL", None)
            else:
                os.environ["TRANSLATE_PLAN_EXTERNAL"] = old
            if old_mode is None:
                os.environ.pop("TRANSLATE_PHASE2_MODE", None)
            else:
                os.environ["TRANSLATE_PHASE2_MODE"] = old_mode

    def test_issues_need_repair(self) -> None:
        from lib.phase3_qa import issues_need_repair

        self.assertTrue(
            issues_need_repair({"问题": [{"级别": "P1", "说明": "x"}]})
        )
        self.assertTrue(
            issues_need_repair({"问题": [{"级别": "P2", "说明": "x"}]})
        )
        self.assertTrue(
            issues_need_repair({"问题": [{"级别": "P3", "说明": "x"}]})
        )
        self.assertFalse(issues_need_repair({"问题": []}))

    def test_detects_missing_now_place(self) -> None:
        mother = "甲" * 500
        detail = "章邯为雍王，定都废丘。\n\n参考著作：\n- 《史记》"
        finds = program_qa_findings(mother=mother, detail=detail)
        self.assertTrue(
            any(
                "废丘" in (f.get("说明") or "") or "废丘" in (f.get("摘录") or "")
                for f in finds
            )
        )


if __name__ == "__main__":
    unittest.main()
