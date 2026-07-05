"""Step4 merge-auto / fill_entries 须保留 LLM 写入的 _坐标主轴说明。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
_ROOT = ORCH.parent
sys.path.insert(0, str(_ROOT / "historiography-annotate"))

from coordinate_index import build_emperor_index, build_regime_index  # noqa: E402
from fill_fields import fill_entries, merge_all_entries  # noqa: E402
from lib_config import build_dynasty_index, load_regime_index, person_spindle_rationale  # noqa: E402

SPINDLE_TEXT = (
    "张耳虽早年任魏国外黄令，但其最高官职为汉初赵王，"
    "其历史功业与政治归属最终落定于汉高祖时期。"
)


class TestStep4SpindlePreserve(unittest.TestCase):
    def _sample_entry(self) -> dict:
        return {
            "史略ID": "HANSHU_042_01",
            "史略名称": "张耳",
            "史略分类": "文臣",
            "史略简介": "张耳，大梁人也。",
            "四级帝王坐标": "汉高祖",
            "史略开始年": -264,
            "史略结束年": -202,
            "优先级": "P0",
            "_auto_filled": {
                "_坐标主轴说明": SPINDLE_TEXT,
                "年规则": "旧规则应被脚本覆盖",
            },
        }

    def test_fill_entries_preserves_spindle_rationale(self) -> None:
        entry = self._sample_entry()
        ei = build_emperor_index()
        di = build_dynasty_index()
        ri = load_regime_index()
        data = {"entries": [entry], "volume": "张耳陈馀传"}
        fill_entries(
            [entry],
            ei,
            di,
            ri,
            work_id="02汉书",
            data=data,
            no_junji=True,
        )
        self.assertEqual(person_spindle_rationale(entry), SPINDLE_TEXT)
        self.assertIn("年规则", entry.get("_auto_filled", {}))

    def test_merge_auto_preserves_spindle_rationale(self) -> None:
        entry = self._sample_entry()
        entry2 = {
            "史略ID": "HANSHU_042_02",
            "史略名称": "陈馀",
            "史略分类": "文臣",
            "史略简介": "陈馀，亦大梁人。",
            "四级帝王坐标": "汉高祖",
            "史略开始年": -264,
            "史略结束年": -204,
            "优先级": "P0",
            "_auto_filled": {
                "_坐标主轴说明": "陈馀主要活动于楚汉相争时期，对抗对象为汉高祖。",
            },
        }
        data = {"entries": [entry, entry2], "volume": "张耳陈馀传", "work": "02汉书"}
        ei = build_emperor_index()
        di = build_dynasty_index()
        ri = load_regime_index()
        merge_all_entries(
            data["entries"],
            data=data,
            emperor_index=ei,
            dynasty_index=di,
            regime_index=ri,
            work_id="02汉书",
        )
        self.assertGreaterEqual(len(person_spindle_rationale(entry)), 8)
        self.assertGreaterEqual(len(person_spindle_rationale(entry2)), 8)
        self.assertNotIn("_坐标主轴说明", entry.get("_needs_llm", []))


if __name__ == "__main__":
    unittest.main()
