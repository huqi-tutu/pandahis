"""qa_repair 分类回归。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.qa_repair import classify_translate_failure  # noqa: E402


def test_thin_source_routes() -> None:
    plan = classify_translate_failure(
        ["史料原文合计仅28汉字（<100），禁止一期翻译"],
        stage="recall",
    )
    assert plan.root_cause == "THIN_SOURCE"
    assert plan.disposition == "route_pipeline"


def test_coverage_retries() -> None:
    plan = classify_translate_failure(
        ["母本覆盖不足：M003 未命中"],
        stage="phase1",
        fail_count=0,
    )
    assert plan.root_cause == "COVERAGE_MISS"
    assert plan.disposition == "retry_llm"
