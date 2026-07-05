#!/usr/bin/env python3
"""跳过《汉书》表/志卷（014–040）：全段 exclude，entries 为空。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
_ROOT = SKILL_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from paragraph_utils import classify_paragraph_header, resolve_source_file, split_mode_for_work, split_paragraphs  # noqa: E402

ORCH = _ROOT / "historiography-orchestrator"
if str(ORCH) not in sys.path:
    sys.path.insert(0, str(ORCH))

from lib import gates, blocks_workflow  # noqa: E402
from lib.adapters.openclaw import expected_skeleton_path  # noqa: E402
from lib.protagonist_workflow import protagonists_path  # noqa: E402
from lib.db import connect, utc_now  # noqa: E402

WORK = "02汉书"
VOLS = [f"{n:03d}" for n in range(14, 41)]


def _exclude_reason(vol_name: str, header: str | None) -> str:
    if header in ("卷首标题", "篇内小标题", "纯纪年"):
        return header
    if vol_name.endswith("表"):
        return "志书数据"
    return "志书数据"


def skip_vol(vol: str) -> tuple[bool, str]:
    from lib import blocks_workflow as bw

    vol = vol.zfill(3)
    idx = gates.load_paragraph_index(WORK, vol)
    vn = bw.volume_display_name(WORK, vol, idx)
    total = int(idx["total"])
    vol_type = "表" if vn.endswith("表") else "志书数据"

    bp = blocks_workflow.blocks_path(WORK, vol)
    if bp.exists():
        bp.unlink()
    pp = protagonists_path(WORK, vol)
    if pp.exists():
        pp.unlink()

    sk_path = expected_skeleton_path(WORK, vol, idx)
    if sk_path.exists():
        sk_path.unlink()

    paras = {p["id"]: p.get("text", "") for p in idx.get("paragraphs") or []}
    attr = []
    for p in range(1, total + 1):
        text = paras.get(p, "")
        header = classify_paragraph_header(text)
        attr.append(
            {
                "paragraph": p,
                "owners": [],
                "exclude_reason": _exclude_reason(vn, header),
            }
        )

    sk = {
        "volume": vn,
        "source_file": (idx.get("source_file") or f"{WORK}_{vol}.txt").strip(),
        "total_paragraphs": total,
        "volume_type": vol_type,
        "segment_attribution": attr,
        "entries": [],
    }
    sk_path.parent.mkdir(parents=True, exist_ok=True)
    sk_path.write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    from knowledge_provenance import stamp_provenance  # noqa: E402

    stamp_provenance(sk_path, "1", source="skip_non_narrative", reason=vol_type)
    stamp_provenance(sk_path, "4", source="skip_non_narrative", reason="无叙事条目")

    gates.step2_prepare(sk_path)
    gates.step3_write_audit_block(WORK, vol, sk_path)
    gates.step4_prepare(sk_path)

    ok_fin, fin_msg = gates.step4_finalize(sk_path)
    if not ok_fin:
        return False, f"finalize: {fin_msg[-300:]}"

    for step in ("1", "2", "3", "4"):
        ok, msg = gates.verify_step(WORK, vol, step)
        if not ok:
            return False, f"Step{step}: {msg[-400:]}"
    conn = connect()
    now = utc_now()
    for step in ("1", "2", "3", "4"):
        conn.execute(
            "UPDATE jobs SET status='done', fail_count=0, detail='', finished_at=? "
            "WHERE work_id=? AND vol=? AND step=?",
            (now, WORK, vol, step),
        )
    conn.commit()
    return True, f"{vn} skip OK"


def main() -> None:
    failed = []
    for vol in VOLS:
        if len(sys.argv) > 1 and vol not in [v.zfill(3) for v in sys.argv[1:]]:
            continue
        try:
            ok, msg = skip_vol(vol)
            print("✅" if ok else "❌", vol, msg[:100])
            if not ok:
                failed.append(vol)
        except Exception as e:
            print(f"❌ {vol} 异常: {e}")
            failed.append(vol)
    if failed:
        raise SystemExit(f"失败: {failed}")
    print(f"\n✅ 已 skip {len(VOLS)} 卷")


if __name__ == "__main__":
    main()
