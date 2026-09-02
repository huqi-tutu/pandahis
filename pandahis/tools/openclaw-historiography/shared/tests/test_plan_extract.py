"""plan JSON 提取：须识别长文决策包（有外部补全、无母本清单）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from llm.artifacts import extract_best_json, extract_plan_json  # noqa: E402


class TestExtractPlanDecision(unittest.TestCase):
    def test_decision_only_with_external(self) -> None:
        text = """
SOURCE_PLAN_DONE
```json
{
  "史略ID": "GLBL_00085",
  "史略名称": "汉高祖",
  "母本著作": "01史记",
  "外部补全": [
    {
      "采用": true,
      "补全类型": "补充细节",
      "出处": "《史记·项羽本纪》",
      "与母本关系": "鸿门宴细节母本本纪略写",
      "母本锚点": "M080 后",
      "主题": "鸿门宴"
    }
  ],
  "索引补充处理": [{"出处": "《汉书·高帝纪》", "处理": "异说"}],
  "写作结构": [{"小节": "本传"}],
  "参考著作": ["《史记·项羽本纪》"],
  "风险提示": []
}
```
"""
        plan = extract_plan_json(text)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan["史略ID"], "GLBL_00085")
        self.assertEqual(len(plan["外部补全"]), 1)
        self.assertNotIn("母本逐句清单", plan)
        best = extract_best_json(text)
        self.assertIsNotNone(best)
        assert isinstance(best, dict)
        self.assertEqual(len(best.get("外部补全") or []), 1)

    def test_prefer_nonempty_external_over_empty_checklist_shell(self) -> None:
        text = """
{"史略ID":"x","母本逐句清单":[{"编号":"M001"}],"外部补全":[]}
```json
{"史略ID":"y","外部补全":[{"采用":true,"出处":"《汉书·高帝纪》","补全类型":"异说","与母本关系":"年号差异相对母本"}],"参考著作":["《汉书》"]}
```
"""
        plan = extract_plan_json(text)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan["史略ID"], "y")
        self.assertGreaterEqual(len(plan["外部补全"]), 1)

    def test_intro_only_json(self) -> None:
        text = (
            '{"史略ID":"GLBL_00330","前置引入":'
            '"战国楚国风雨飘摇。屈原这个名字后来被端午裹得很甜，'
            '可在史书里他首先是个把心掏给楚王的人。'
            '《史记·屈原贾生列传》对屈原生平的描写。"}'
        )
        best = extract_best_json(text)
        self.assertIsNotNone(best)
        assert isinstance(best, dict)
        self.assertIn("前置引入", best)
        self.assertEqual(best["史略ID"], "GLBL_00330")

    def test_ending_only_json(self) -> None:
        text = (
            '```json\n{"史略ID":"GLBL_00330","结尾":'
            '"江水还在流，那份不肯同流合污的心气，'
            '却成了后来无数人嘴里的屈原。"}\n```\n'
            "TRANSLATE_DONE GLBL_00330"
        )
        best = extract_best_json(text)
        self.assertIsNotNone(best)
        assert isinstance(best, dict)
        self.assertIn("结尾", best)


if __name__ == "__main__":
    unittest.main()
