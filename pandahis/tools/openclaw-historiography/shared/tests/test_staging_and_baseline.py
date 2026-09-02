"""Candidate promotion and baseline regression tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "historiography-translate"))

from lib.baseline_quality import detect_baseline_regression  # noqa: E402
from lib.run_ledger import latest, new_run, preserve_candidate, resume_phase_for, save, update  # noqa: E402
from lib.staging import promote_candidate, staging_path  # noqa: E402


class TestStagingAndBaseline(unittest.TestCase):
    def test_candidate_is_not_formal_until_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            formal = root / "GLBL_00084_汉武帝.json"
            formal.write_text(json.dumps({"翻译详情": "旧稿"}), encoding="utf-8")
            candidate = staging_path(formal, "run")
            candidate.write_text(json.dumps({"翻译详情": "新稿"}), encoding="utf-8")
            self.assertEqual(json.loads(formal.read_text(encoding="utf-8"))["翻译详情"], "旧稿")
            promote_candidate(candidate, formal)
            self.assertEqual(json.loads(formal.read_text(encoding="utf-8"))["翻译详情"], "新稿")

    def test_run_ledger_preserves_failed_candidate_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = new_run(
                root,
                "GLBL_00084",
                formal_target=root / "formal.json",
                source_fingerprint="fp",
            )
            candidate = root / "candidate.json"
            candidate.write_text("{}", encoding="utf-8")
            preserve_candidate(manifest, candidate)
            update(manifest, phase="phase5", status="pending_recovery", next_action="retry_phase5")
            resumed = latest(root, "GLBL_00084")
            self.assertIsNotNone(resumed)
            self.assertEqual(resumed["status"], "pending_recovery")
            self.assertTrue(Path(resumed["candidate"]).is_file())

    def test_runtime_failure_resumes_phase1(self) -> None:
        self.assertEqual(resume_phase_for("runtime"), "phase1")
        self.assertEqual(resume_phase_for("phase5"), "phase5")

    def test_baseline_catches_core_anchor_loss_without_length_gate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            vdir = root / "_versions" / "GLBL_00084_汉武帝"
            vdir.mkdir(parents=True)
            baseline = "卫青 霍去病 巫蛊 轮台 罪己 征和 " + "甲" * 2000
            (vdir / "GLBL_00084_汉武帝.v6.json").write_text(
                json.dumps({"翻译版本": "v6", "翻译详情": baseline}, ensure_ascii=False),
                encoding="utf-8",
            )
            errors = detect_baseline_regression(
                "GLBL_00084",
                "轮台 罪己 征和 " + "乙" * 500,
                out_dir=root,
                entry_name="汉武帝",
                mother="卫青 霍去病 巫蛊 轮台 罪己 征和",
            )
            self.assertTrue(any("核心内容锚点" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
