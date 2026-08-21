"""声口样例去情节：只留口气，避免章界复述。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.phase2_batch import extract_voice_sample, scrub_voice_sample_for_style  # noqa: E402


class TestVoiceSample(unittest.TestCase):
    def test_scrub_strips_books_and_places(self) -> None:
        raw = (
            "他跑到碣石（今河北昌黎一带），又见《史记·封禅书》所载，"
            "嘴里念着「鸿渐于般」。"
        )
        s = scrub_voice_sample_for_style(raw)
        self.assertNotIn("《", s)
        self.assertNotIn("今河北", s)
        self.assertNotIn("鸿渐于般", s)

    def test_extract_is_short_and_not_full_plot(self) -> None:
        ch3_tail = (
            "典礼结束。\n\n"
            "封禅泰山这一趟，一路没遇上风雨灾害，顺顺当当。"
            "方士们便又鼓动说蓬莱那些神山好像真能求到了，"
            "汉武帝听了满心欢喜，于是再次东行到海边眺望。"
            "偏偏这时，随行的奉车子侯霍嬗突然暴病，一天之内就死了。"
            "汉武帝没了兴致，这才离开海边，沿着海岸北上，"
            "到碣石（今河北昌黎一带），再巡行辽西，一直到了九原（今内蒙古包头一带）。"
            "五月，返回甘泉宫。有司上言，今年改元为元封元年。"
        )
        sample = extract_voice_sample(ch3_tail)
        self.assertLessEqual(len(sample), 160)
        # 不应再是整段回程故事
        self.assertNotIn("霍嬗突然暴病", sample)
        self.assertNotIn("一路没遇上风雨", sample)


if __name__ == "__main__":
    unittest.main()
