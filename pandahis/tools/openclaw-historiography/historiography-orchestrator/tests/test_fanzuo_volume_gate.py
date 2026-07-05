"""蕃祚卷白名单与 054 误分类门禁测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ANN = Path(__file__).resolve().parents[2] / "historiography-annotate"
ORCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANN))
sys.path.insert(0, str(ORCH))

from category_v3 import is_fanzuo_volume  # noqa: E402
from fanzuo_volumes import fanzuo_category_errors  # noqa: E402
from hanshu_hezhuan_gate import validate_repair_plan  # noqa: E402
from identity_gate import validate_protagonists_identity  # noqa: E402
from lib import blocks_workflow, gates  # noqa: E402
from lib.protagonist_workflow import load_protagonists  # noqa: E402


class TestFanzuoVolumeWhitelist(unittest.TestCase):
    def test_hanshu_fanzuo_volumes(self):
        self.assertTrue(is_fanzuo_volume("02汉书", "107", "匈奴传第六十四上"))
        self.assertTrue(is_fanzuo_volume("02汉书", "109", "西南夷两粤朝鲜传第六十五"))
        self.assertTrue(is_fanzuo_volume("02汉书", "110", "西域传第六十六上"))

    def test_hanshu_054_not_fanzuo(self):
        self.assertFalse(
            is_fanzuo_volume("02汉书", "054", "淮南衡山济北王传")
        )

    def test_fanzuo_category_blocked_on_054(self):
        errs = fanzuo_category_errors(
            "02汉书",
            "054",
            "淮南衡山济北王传",
            [("刘安", "蕃祚")],
            prefix="entry ",
        )
        self.assertEqual(len(errs), 1)
        self.assertIn("禁止蕃祚", errs[0])

    def test_protagonist_gate_rejects_fanzuo_on_054(self):
        data = {
            "volume_name": "淮南衡山济北王传",
            "protagonists": [
                {"name": "刘长", "category": "蕃祚", "rationale": "x"},
                {"name": "刘安", "category": "蕃祚", "rationale": "x"},
                {"name": "刘赐", "category": "蕃祚", "rationale": "x"},
                {"name": "刘勃", "category": "蕃祚", "rationale": "x"},
            ],
        }
        ok, msg = validate_protagonists_identity(
            "02汉书", "054", data, volume_name="淮南衡山济北王传"
        )
        self.assertFalse(ok)
        self.assertIn("禁止蕃祚", msg)

    def test_protagonist_gate_accepts_zongqi_on_054(self):
        data = {
            "volume_name": "淮南衡山济北王传",
            "protagonists": [
                {"name": "刘长", "category": "宗戚", "rationale": "x"},
                {"name": "刘安", "category": "宗戚", "rationale": "x"},
                {"name": "刘赐", "category": "宗戚", "rationale": "x"},
                {"name": "刘勃", "category": "宗戚", "rationale": "x"},
            ],
        }
        ok, msg = validate_protagonists_identity(
            "02汉书", "054", data, volume_name="淮南衡山济北王传"
        )
        self.assertTrue(ok, msg)
        self.assertIn("身份 OK", msg)

    def test_hanshu_083_hezhuan_gate_accepts_full_core_names(self):
        ok, msg = validate_repair_plan(
            "02汉书_083_隽疏于薛平彭传第四十一.txt",
            ["隽不疑", "疏广", "疏受", "于定国", "薛广德", "平当", "彭宣"],
        )
        self.assertTrue(ok, msg)
        self.assertIn("白名单核对通过", msg)

    def test_hanshu_083_hezhuan_gate_rejects_pseudo_chunks(self):
        ok, msg = validate_repair_plan(
            "02汉书_083_隽疏于薛平彭传第四十一.txt",
            ["隽疏", "于薛", "平彭"],
        )
        self.assertFalse(ok)
        self.assertIn("卷名核心人物未齐", msg)

    def test_hanshu_084_hezhuan_gate_accepts_full_core_names(self):
        ok, msg = validate_repair_plan(
            "02汉书_084_王贡两龚鲍传第四十二.txt",
            ["王吉", "贡禹", "龚胜", "龚舍", "鲍宣"],
        )
        self.assertTrue(ok, msg)
        self.assertIn("白名单核对通过", msg)

    def test_hanshu_087_hezhuan_gate_accepts_full_core_names(self):
        ok, msg = validate_repair_plan(
            "02汉书_087_眭两夏侯京翼李传第四十五.txt",
            ["眭弘", "夏侯始昌", "夏侯胜", "京房", "翼奉", "李寻"],
        )
        self.assertTrue(ok, msg)
        self.assertIn("白名单核对通过", msg)

    def test_hanshu_088_hezhuan_gate_accepts_full_core_names(self):
        ok, msg = validate_repair_plan(
            "02汉书_088_赵尹韩张两王传第四十六.txt",
            ["赵广汉", "尹翁归", "韩延寿", "张敞", "王尊", "王章"],
        )
        self.assertTrue(ok, msg)
        self.assertIn("白名单核对通过", msg)

    def test_hanshu_094_hezhuan_gate_accepts_full_core_names(self):
        ok, msg = validate_repair_plan(
            "02汉书_094_王商史丹傅喜传第五十二.txt",
            ["王商", "史丹", "傅喜"],
        )
        self.assertTrue(ok, msg)
        self.assertIn("白名单核对通过", msg)

    def test_hanshu_083_mechanical_blocks_accept_shoushou_alias(self):
        work = "02汉书"
        vol = "083"
        idx = gates.load_paragraph_index(work, vol)
        manifest = load_protagonists(work, vol)
        ok, msg = blocks_workflow.try_mechanical_blocks_from_manifest(
            work, vol, idx, manifest=manifest
        )
        self.assertTrue(ok, msg)

    def test_entry_opening_quote_extends_short_lead_paragraph(self):
        quote = blocks_workflow._entry_opening_quote(
            {
                14: "薛广德字长卿，沛郡相人也。",
                15: "以《鲁诗》教授楚国，龚胜、舍师事焉。",
            },
            [(14, 15)],
        )
        self.assertEqual(quote, "薛广德字长卿，沛郡相人也。")


if __name__ == "__main__":
    unittest.main()
