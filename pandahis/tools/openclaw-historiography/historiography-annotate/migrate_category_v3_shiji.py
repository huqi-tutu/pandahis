#!/usr/bin/env python3
"""将《史记》已标注数据迁移至史略分类 v3，并刷新蕃祚卷考订字段。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from category_v3 import migrate_shiji_tree, refresh_detail_coords_tree  # noqa: E402
from collective_volume_subjects import (  # noqa: E402
    collective_provenance_fields,
    collective_year_span,
    is_collective_subject,
)

ROOT = Path(os.environ.get("HISTOGRAPH_ROOT", SKILL_DIR.parents[2]))


def refresh_fanzuo_provenance(sk_path: Path) -> int:
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    n = 0
    for entry in data.get("entries") or []:
        if entry.get("史略分类") != "蕃祚":
            continue
        name = (entry.get("史略名称") or "").strip()
        if not is_collective_subject(name, data.get("volume", "")):
            continue
        prov = collective_provenance_fields(name)
        if not prov:
            continue
        af = dict(entry.get("_auto_filled") or {})
        old_basis = (af.get("_年LLM依据") or "").strip()
        old_rule = (af.get("年规则") or "").strip()
        legacy_script = (
            "叙事跨度" in old_basis
            or "叙事起年" in old_rule
            or old_rule == "叙事起年 → 叙事止年"
        )
        for k, v in prov.items():
            if af.get(k) != v:
                af[k] = v
                n += 1
        entry["_auto_filled"] = af
        span = collective_year_span(name)
        if span is not None:
            start, end, note = span
            for field, val in (("史略开始年", start), ("史略结束年", end)):
                if entry.get(field) != val:
                    entry[field] = val
                    n += 1
            if legacy_script or not old_basis or (af.get("_年LLM依据") or "").strip() != note:
                if af.get("_年LLM依据") != note:
                    af["_年LLM依据"] = note
                    entry["_auto_filled"] = af
                    n += 1
    if n:
        sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return n


def main() -> None:
    stats = migrate_shiji_tree(ROOT)
    prov_n = 0
    sk_dir = ROOT / "data" / "03索引标注条目"
    for fp in sorted(sk_dir.glob("01史记_*_skeleton.json")):
        prov_n += refresh_fanzuo_provenance(fp)
    detail_n = refresh_detail_coords_tree(ROOT)
    print("migrate:", json.dumps(stats, ensure_ascii=False))
    print("fanzuo_provenance_updates:", prov_n)
    print("detail_coords_refreshed:", detail_n)


if __name__ == "__main__":
    main()
