"""failure_classifier 回归：Step4 误删 skeleton / 归属打回 Step1。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.failure_classifier import (  # noqa: E402
    classify_failure,
    should_rollback_from_step4,
)


def test_step4_volume_title_is_attribution_not_blocks():
    err = """
check_format final:
  📊 归属表检查 (共 70 段)
  ❌ 段1 为卷首标题（卷一下  高帝纪第一下），不得设 owners，须 exclude_reason=卷首标题
  📄 exclude 内容门
  ✅ exclude 内容 OK
"""
    plan = classify_failure("4", err, work="02汉书", vol="002")
    assert plan.root_cause == "ATTRIBUTION_LAYOUT"
    assert plan.invalidate == ("blocks", "skeleton")
    assert should_rollback_from_step4(plan, "4")


def test_exclude_gate_pass_does_not_invalidate():
    err = """
blocks 无效:
  📄 exclude 内容门
  ✅ exclude 内容 OK
  ❌ 未覆盖段 5
"""
    plan = classify_failure("1", err)
    assert plan.root_cause == "BLOCKS_LAYOUT"
    assert "未覆盖" in err


def test_exclude_gate_fail_is_blocks():
    err = "blocks 无效: P69 非「太史公曰」起笔，禁止 exclude=太史公曰"
    plan = classify_failure("1", err)
    assert plan.root_cause == "BLOCKS_LAYOUT"


def test_step4_field_error_stays_step4():
    err = "verify step4 失败:\nStep4 LLM 后字段仍缺失:\n  - SHIJI_002_04 缺少: 优先级"
    plan = classify_failure("4", err)
    assert plan.root_cause == "STEP4_FIELDS"
    assert plan.invalidate == ()
    assert not should_rollback_from_step4(plan, "4")


def test_exclude_section_pass_with_attribution_error():
    err = """
  📄 exclude 内容门
  ✅ exclude 内容 OK
  ❌ 段1 为卷首标题，不得设 owners
"""
    plan = classify_failure("4", err)
    assert plan.root_cause == "ATTRIBUTION_LAYOUT"
    assert should_rollback_from_step4(plan, "4")


def test_step4_spindle_missing_not_attribution_rollback():
    err = """
verify step4 失败:
check_format final:
  ❌ [HANSHU_042_01] 张耳 跨时期人物：须在 _auto_filled 填写 _坐标主轴说明
     ⛔ 段01 → 排除 (卷首标题)
"""
    plan = classify_failure("4", err, work="02汉书", vol="042")
    assert plan.root_cause == "STEP4_FIELDS"
    assert not should_rollback_from_step4(plan, "4")


if __name__ == "__main__":
    test_step4_volume_title_is_attribution_not_blocks()
    test_exclude_gate_pass_does_not_invalidate()
    test_exclude_gate_fail_is_blocks()
    test_step4_field_error_stays_step4()
    test_exclude_section_pass_with_attribution_error()
    print("ok")
