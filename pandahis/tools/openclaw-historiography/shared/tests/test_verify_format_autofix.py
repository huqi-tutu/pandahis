"""verify_format_autofix 测试。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.source_citation import curved_quote_after_source_citation_issues  # noqa: E402
from shared.reference_works import reference_volume_mismatch_issues  # noqa: E402
from shared.verify_format_autofix import autofix_detail_format  # noqa: E402


def test_fix_curved_quote():
    raw = '《荀子·议兵》说周武王"封微子于宋"，后世亦传颂。'
    out, fixes = autofix_detail_format(raw + "\n\n参考著作：\n1. 《荀子·议兵》")
    assert "source_curved_quote" in fixes
    assert "「封微子于宋」" in out
    body = out.split("参考著作")[0]
    assert not curved_quote_after_source_citation_issues(body)


def test_fix_volume_mismatch():
    raw = (
        "据《诗经·商颂·长发》记载。\n\n"
        "参考著作：\n"
        "1. 《诗经·商颂》\n"
        "2. 《诗经·商颂·长发》"
    )
    out, fixes = autofix_detail_format(raw)
    assert "refs_volume_mismatch" in fixes
    assert "《诗经·商颂》" not in out.split("参考著作")[1] or "《诗经·商颂·长发》" in out
    assert not reference_volume_mismatch_issues(out)


def test_fix_nested_corner_quote():
    raw = '汤说：「"予有言：人视水见形"」——白话。'
    out, fixes = autofix_detail_format(raw)
    assert "nested_corner_quote" in fixes
    assert '「"予有言' not in out
    assert "「予有言：人视水见形」" in out
