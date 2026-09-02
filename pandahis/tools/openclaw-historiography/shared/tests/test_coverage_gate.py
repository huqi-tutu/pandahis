"""覆盖门禁短路 / 终检 L1 路径的单元测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))
sys.path.insert(0, str(ROOT))

from lib.coverage import verify_final_coverage  # noqa: E402
from lib.coverage_info import build_coverage_units  # noqa: E402
from lib.coverage_l2 import verify_mother_semantic_coverage  # noqa: E402
from lib.coverage_ledger import (  # noqa: E402
    apply_claim_results,
    claim_fingerprint,
    save_ledger,
)


def _checklist(n: int) -> list:
    return [
        {
            "编号": f"M{i:03d}",
            "段落": f"01史记 卷001 P{i}",
            "原文摘句": f"原文句子{i}号，内容各异。",
            "信息点": f"信息点{i}",
        }
        for i in range(1, n + 1)
    ]


class TestGateShortCircuit(unittest.TestCase):
    def test_passing_ledger_skips_llm(self) -> None:
        """账本已达门禁时，不再发起 LLM 复核。"""
        plan = {"母本逐句清单": _checklist(10)}
        units = build_coverage_units(plan["母本逐句清单"])
        entries: dict = {}
        for unit in units[:9]:
            apply_claim_results(
                entries,
                claim_id=unit.label,
                status="conveyed",
                claim_fp=claim_fingerprint(unit),
            )
        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            save_ledger(work_dir, "GLBL_T001", entries)
            with mock.patch(
                "lib.coverage_l2._translate_llm_call",
                side_effect=AssertionError("LLM 不应被调用"),
            ):
                ok, msgs = verify_mother_semantic_coverage(
                    "任意译文",
                    plan,
                    entry_id="GLBL_T001",
                    work_dir=work_dir,
                )
        self.assertTrue(ok)
        self.assertTrue(any("搁置" in m for m in msgs))

    def test_frozen_units_count_toward_budget(self) -> None:
        """冻结单元计入门禁 weak 预算且不触发 LLM。"""
        plan = {"母本逐句清单": _checklist(10)}
        units = build_coverage_units(plan["母本逐句清单"])
        entries: dict = {}
        for unit in units[:8]:
            apply_claim_results(
                entries,
                claim_id=unit.label,
                status="conveyed",
                claim_fp=claim_fingerprint(unit),
            )
        for unit in units[8:]:
            fp = claim_fingerprint(unit)
            apply_claim_results(entries, claim_id=unit.label, status="unclear", claim_fp=fp)
            apply_claim_results(entries, claim_id=unit.label, status="unclear", claim_fp=fp)
        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td)
            save_ledger(work_dir, "GLBL_T002", entries)
            with mock.patch(
                "lib.coverage_l2._translate_llm_call",
                side_effect=AssertionError("LLM 不应被调用"),
            ):
                ok, _ = verify_mother_semantic_coverage(
                    "任意译文",
                    plan,
                    entry_id="GLBL_T002",
                    work_dir=work_dir,
                )
        # 8/10 = 80% 达 min_ratio；2 weak ≤ max_fail 3 → 放行
        self.assertTrue(ok)


class TestFinalCoverageL1(unittest.TestCase):
    def test_report_mode_never_calls_llm(self) -> None:
        """allow_llm=False 时纯程序判定。"""
        plan = {"母本逐句清单": _checklist(60)}
        detail = "完全无关的成稿。" * 50
        ok, msgs = verify_final_coverage(
            detail,
            plan,
            min_ratio=0.9,
            entry_id="",  # 无 entry_id 时本就不触发 L2
            work_dir=None,
            allow_llm=False,
        )
        self.assertFalse(ok)
        self.assertTrue(any("覆盖不足" in m for m in msgs))

    def test_good_detail_passes_l1(self) -> None:
        plan = {"母本逐句清单": _checklist(3)}
        detail = "。".join(
            f"信息点{i}与原文句子{i}号内容各异的展开" for i in range(1, 4)
        )
        ok, _ = verify_final_coverage(
            detail,
            plan,
            min_ratio=0.5,
            entry_id="",
            work_dir=None,
            allow_llm=False,
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
