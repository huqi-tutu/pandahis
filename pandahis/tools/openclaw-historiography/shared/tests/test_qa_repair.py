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


def test_mother_span_drop_not_legend() -> None:
    plan = classify_translate_failure(
        ["整段漏：母本第72–74段在成稿中对不上（锚点：谒者随何）"],
        stage="phase2",
        fail_count=1,
    )
    assert plan.root_cause == "MOTHER_SPAN_DROP"
    assert plan.action == "phase2_splice_missing_spans"


def test_ai_flavor_script_fix() -> None:
    plan = classify_translate_failure(
        ["AI 腔词「可谓」出现 6 次 ≥ 5（单篇最多 4 次）"],
        stage="verify_final",
        fail_count=0,
    )
    assert plan.root_cause == "AI_FLAVOR"
    assert plan.disposition == "script_fix"
    assert plan.refine_scope == "ai_flavor"


def test_ai_flavor_refine_after_script() -> None:
    plan = classify_translate_failure(
        ["AI 腔词全文合计 6 次 ≥ 5"],
        stage="verify_final",
        fail_count=1,
    )
    assert plan.root_cause == "AI_FLAVOR"
    assert plan.disposition == "refine_scope"
