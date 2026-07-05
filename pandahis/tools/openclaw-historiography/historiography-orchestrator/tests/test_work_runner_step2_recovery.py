"""Step2 失败恢复：优先 verify-only 修复，避免机械错误空转。"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import work_runner  # noqa: E402


def test_step2_hanshu_header_error_prefers_verify_only_repair():
    err = "verify step2 失败:\n❌ 段2 为篇内小标题，不得设 owners，须 exclude_reason=篇内小标题"
    with patch.object(
        work_runner.gates, "is_step2_emperor_reference_only_error", return_value=False
    ), patch.object(
        work_runner, "_apply_failure_recovery", return_value=("repair_bypass:verify_only", True)
    ), patch.object(work_runner, "_rollback_to_step1") as rollback:
        retry_detail, rolled_back = work_runner._handle_step2_verify_failure(
            "02汉书", "092", 1001, err, 1, 2
        )
    assert retry_detail == "repair_bypass:verify_only"
    assert not rolled_back
    rollback.assert_not_called()


def test_step2_generic_verify_error_still_rolls_back():
    err = "verify step2 失败:\n❌ 段落覆盖不完整"
    with patch.object(
        work_runner.gates, "is_step2_emperor_reference_only_error", return_value=False
    ), patch.object(
        work_runner, "_apply_failure_recovery", return_value=("verify_feedback:test", False)
    ), patch.object(work_runner, "_rollback_to_step1") as rollback:
        retry_detail, rolled_back = work_runner._handle_step2_verify_failure(
            "02汉书", "092", 1002, err, 1, 2
        )
    assert retry_detail is None
    assert rolled_back
    rollback.assert_called_once()


if __name__ == "__main__":
    test_step2_hanshu_header_error_prefers_verify_only_repair()
    test_step2_generic_verify_error_still_rolls_back()
    print("ok")
