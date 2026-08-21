"""嵌套产出 JSON 应被 sanitize 剥壳，避免正文乱入史略ID。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.prose_sanitize import (  # noqa: E402
    sanitize_enrich_detail,
    sanitize_enrich_detail_full,
)


class TestUnwrapNestedJson(unittest.TestCase):
    def test_whole_blob(self) -> None:
        raw = '{\n  "史略ID": "GLBL_00085",\n  "翻译详情": "项羽已经救完了赵国。"\n}'
        self.assertEqual(sanitize_enrich_detail(raw), "项羽已经救完了赵国。")

    def test_embedded_blob(self) -> None:
        raw = (
            "这是第二条罪。」\n\n"
            '{\n  "史略ID": "GLBL_00085",\n  "翻译详情": "项羽已经救完了赵国，这是第三条罪状。"\n}\n\n'
            "后面还有正文。"
        )
        out = sanitize_enrich_detail(raw)
        self.assertNotIn("史略ID", out)
        self.assertIn("项羽已经救完了赵国", out)
        self.assertIn("后面还有正文", out)
        self.assertIn("这是第二条罪", out)

    def test_strips_markdown_headings(self) -> None:
        raw = "前文。\n\n## 一、新朝气象：儒学与窦太后的较量\n\n后文继续。"
        out = sanitize_enrich_detail_full(raw)
        self.assertNotIn("## ", out)
        self.assertNotIn("一、新朝气象", out)
        self.assertIn("前文。", out)
        self.assertIn("后文继续。", out)


if __name__ == "__main__":
    unittest.main()
