#!/usr/bin/env python3
"""修复汉书053 Step1：机械划块 + 合传段首异名（硃建/娄敬）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANNOTATE = ORCH.parent / "historiography-annotate"
ROOT = ORCH.parents[2]
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ANNOTATE))

from lib.blocks_workflow import blocks_path, expand_blocks_to_skeleton  # noqa: E402
from lib.volume_manifest import build_mechanical_hezhuan_blocks  # noqa: E402

WORK = "02汉书"
VOL = "053"
INDEX = ROOT / "data/03索引标注条目/段落索引/02汉书_053.json"
MANIFEST = ROOT / "data/05工作流中间产物/标注/02汉书_053_protagonists.json"
SK = ROOT / "data/03索引标注条目/02汉书_053_郦陆朱刘叔孙传第十三_skeleton.json"


def main() -> int:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    para_text = {int(r["id"]): (r.get("text") or "").strip() for r in index["paragraphs"]}

    draft = build_mechanical_hezhuan_blocks(
        manifest,
        total_paragraphs=int(index["total"]),
        para_text=para_text,
    )
    # 朱建传记跨 P8–P9（P9 末段才接力娄敬）；刘敬自 P10 起
    for blk in draft["blocks"]:
        if blk["name"] == "朱建":
            blk["paragraph_to"] = 9
        elif blk["name"] == "刘敬":
            blk["paragraph_from"] = 10
            blk["paragraph_to"] = 12
        elif blk["name"] == "叔孙通":
            blk["paragraph_from"] = 13

    prov = {}
    if SK.is_file():
        old = json.loads(SK.read_text(encoding="utf-8"))
        prov = old.get("knowledge_provenance") or {}

    bp = blocks_path(WORK, VOL)
    bp.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ blocks → {bp}")

    sk_path = expand_blocks_to_skeleton(WORK, VOL, index, blocks_file=bp, skeleton_out=SK)
    data = json.loads(sk_path.read_text(encoding="utf-8"))
    if prov:
        data["knowledge_provenance"] = prov
        sk_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"✓ skeleton → {sk_path.name} ({len(data.get('entries') or [])} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
