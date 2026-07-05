#!/usr/bin/env python3
"""修复汉书056 Step1：万石君石奋段首异名，手动划块后 expand skeleton。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANN = ORCH.parent / "historiography-annotate"
ROOT = ORCH.parents[2]
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ANN))

from lib import db  # noqa: E402
from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton  # noqa: E402

WORK = "02汉书"
VOL = "056"
INDEX = ROOT / "data/03索引标注条目/段落索引/02汉书_056.json"
MANIFEST = ROOT / "data/05工作流中间产物/标注/02汉书_056_protagonists.json"
SK = ROOT / "data/03索引标注条目/02汉书_056_万石卫直周张传第十六_skeleton.json"


def main() -> int:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    total = int(index["total"])

    # 段首为「万石君石奋」；卫绾自 P5 中段起；周仁/张欧同段 P8
    draft = {
        "work": WORK,
        "vol": VOL,
        "volume_name": manifest.get("volume_name"),
        "narrative_mode": "hezhuan",
        "total_paragraphs": total,
        "excludes": [
            {"paragraph_from": 1, "paragraph_to": 1, "exclude_reason": "卷首标题"},
            {"paragraph_from": 9, "paragraph_to": 9, "exclude_reason": "赞曰"},
        ],
        "blocks": [
            {"name": "石奋", "category": "文臣", "paragraph_from": 2, "paragraph_to": 4},
            {"name": "卫绾", "category": "文臣", "paragraph_from": 5, "paragraph_to": 6},
            {"name": "直不疑", "category": "文臣", "paragraph_from": 7, "paragraph_to": 7},
            {"name": "周仁", "category": "文臣", "paragraph_from": 8, "paragraph_to": 8},
        ],
        "_mechanical": True,
        "_mechanical_hezhuan": True,
    }

    bp = blocks_path(WORK, VOL)
    bp.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ blocks → {bp.name}")

    sk_path = expand_blocks_to_skeleton(WORK, VOL, index, blocks_file=bp, skeleton_out=SK)
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    para_text = {int(r["id"]): (r.get("text") or "").strip() for r in index["paragraphs"]}

    # P8 周仁/张欧 同段合传：补张欧条目与双归属
    for row in data.get("segment_attribution") or []:
        if int(row.get("paragraph") or 0) == 8:
            row["owners"] = [
                {"name": "周仁", "category": "文臣"},
                {"name": "张欧", "category": "文臣"},
            ]
    entries = data.get("entries") or []
    entries.append(
        {
            "史略ID": "HANSHU_056_05",
            "史略名称": "张欧",
            "史略简介": "张欧",
            "原文字句": para_text.get(8, "")[:80],
            "史略分类": "文臣",
            "主要史料出处": "《汉书·卷56·万石卫直周张传》",
            "paragraphs": [
                {"volume": "万石卫直周张传", "paragraph_from": 8, "paragraph_to": 8}
            ],
        }
    )
    data["entries"] = entries
    prov = data.get("knowledge_provenance") or {}
    prov.setdefault(
        "step1",
        {"source": "llm", "at": "2026-07-03T10:46:30Z", "session_id": "repair-056-step1"},
    )
    data["knowledge_provenance"] = prov
    sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ skeleton → {sk_path.name} ({len(data.get('entries') or [])} 条)")

    db.init_schema()
    db.reset_volume_step(WORK, VOL, "1")
    db.mark_volume_steps_done(WORK, VOL, "1")
    for step in ("2", "3", "4"):
        db.reset_volume_step(WORK, VOL, step)
    print("✓ jobs: s1=done, s2-4=pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
