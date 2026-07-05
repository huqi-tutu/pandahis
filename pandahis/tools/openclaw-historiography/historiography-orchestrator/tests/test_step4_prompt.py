"""Step4 DeepSeek prompt 落盘契约。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ORCH = Path(__file__).resolve().parents[1]
ROOT = ORCH.parent
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ROOT))

from lib.adapters.openclaw import build_step_prompt, expected_skeleton_path  # noqa: E402
from lib import gates  # noqa: E402


class TestStep4Prompt(unittest.TestCase):
    def test_deepseek_step4_requires_json_block_and_embeds_skeleton(self):
        work, vol = "02汉书", "042"
        idx = gates.load_paragraph_index(work, vol)
        sk = expected_skeleton_path(work, vol, idx)
        self.assertTrue(sk.is_file(), f"missing fixture skeleton: {sk}")

        with patch.dict(os.environ, {"HIST_LLM_PROVIDER": "deepseek"}, clear=False):
            prompt = build_step_prompt(work, vol, "4", idx)

        self.assertIn("```json 代码块", prompt)
        self.assertIn("禁止未输出 JSON 就回复 STEP4_DONE", prompt)
        self.assertIn("HANSHU_042_01", prompt)
        self.assertIn('"segment_attribution"', prompt)


if __name__ == "__main__":
    unittest.main()
