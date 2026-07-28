#!/usr/bin/env python3
"""补全春秋 P0 应补/边界可补见证条目。"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

import cw_lib as cw  # noqa: E402

# (entry_id, extra_prompt)
TASKS: list[tuple[str, str]] = [
    (
        "GLBL_00068",
        "必须输出≥1条见证。优先：楚纪南城遗址（湖北荆州，楚都核心，庄王问鼎时期政治中心）。"
        "可再补1条低优先级传说陵寝（如上蔡楚庄王冢，须标P2/P3）。禁止空结果。",
    ),
    (
        "GLBL_00125",
        "必须输出≥1条见证。优先：秦雍城遗址（陕西凤翔，秦穆公扩雍、霸西戎之秦都）。"
        "禁止空结果。",
    ),
    (
        "GLBL_00065",
        "必须输出≥1条见证。优先：曲村—天马遗址/晋侯墓群（山西曲沃，晋国宗庙考古核心，"
        "与献公灭曲沃、奠定晋国格局相关）。禁止空结果。",
    ),
    (
        "GLBL_00063",
        "必须输出≥1条见证。优先：侯马晋国遗址/新田绛都遗存（山西侯马，晋景公迁新田）。"
        "禁止空结果。",
    ),
    (
        "GLBL_00133",
        "必须输出≥1条见证。优先：晋阳城遗址（山西太原，赵氏根基，赵襄子灭智伯、三分晋关键地望）。"
        "禁止空结果。",
    ),
    (
        "GLBL_00712",
        "输出1条P2见证即可：晋国都城绛/侯马遗址，文物介绍须点明与晋灵公、赵盾弑君时代关联。"
        "禁止空结果。",
    ),
    (
        "GLBL_00708",
        "输出1条P2见证：侯马/绛都晋国遗址，介绍须点明晋厉公时期卿族专权背景。禁止空结果。",
    ),
    (
        "GLBL_00711",
        "输出1条P2见证：晋国遗址或韩原一带地望，介绍须点明晋惠公流亡、韩原之战背景。禁止空结果。",
    ),
    (
        "GLBL_00714",
        "输出1条P2见证：侯马/绛都晋国遗址，介绍须点明晋顷公时六卿格局。禁止空结果。",
    ),
    (
        "GLBL_00007",
        "输出1条P2见证：卫故城遗址（河南濮阳/卫地），介绍须点明卫灵公与孔子周游经卫。禁止空结果。",
    ),
    (
        "GLBL_00772",
        "输出1条P2见证：临淄齐都遗址，介绍须点明齐襄公时期齐纪关系、齐灭纪等背景。禁止空结果。",
    ),
    (
        "GLBL_00769",
        "输出1条P2见证：临淄齐都遗址，介绍须点明齐灵公末期、晏婴辅政背景。禁止空结果。",
    ),
    (
        "GLBL_00763",
        "输出1条P2见证：临淄齐都遗址，介绍须点明齐庄公、崔庆之乱背景。禁止空结果。",
    ),
    (
        "GLBL_00064",
        "输出1条P2见证：曲村—天马遗址，介绍须点明晋武公据曲沃、小宗代大宗背景。禁止空结果。",
    ),
    (
        "GLBL_00734",
        "输出1条P2见证：郑韩故城遗址（河南新郑），介绍须点明郑文公时期郑国都城。禁止空结果。",
    ),
]


def main() -> int:
    cw.validate_histograph_root()
    cw.ensure_deepseek_v4_pro()
    paths = cw.histograph_paths()
    mid = paths["witness"].parent / "05工作流中间产物" / "评述见证补全"
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = mid / f"春秋_witness_gaps_{stamp}.json"

    results: list[dict] = []
    for i, (eid, hint) in enumerate(TASKS, 1):
        entry = cw.find_entry(entry_id=eid)
        name = str(entry.get("史略名称", ""))
        print(f"[{i}/{len(TASKS)}] witness {eid} {name} …", flush=True)
        try:
            r = cw.compose_one("witness", entry_id=eid, revise=True, extra_prompt=hint)
            print(
                f"  ✅ status={r.get('status')} entries={r.get('entry_count')}",
                flush=True,
            )
            results.append({"id": eid, "name": name, "status": "ok", **r})
        except Exception as ex:
            print(f"  ❌ {ex}", flush=True)
            traceback.print_exc()
            results.append({"id": eid, "name": name, "status": "error", "error": str(ex)})

    err = [x for x in results if x["status"] == "error"]
    summary_path.write_text(
        json.dumps({"stamp": stamp, "results": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nDONE ok={len(results)-len(err)} err={len(err)} → {summary_path}", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
