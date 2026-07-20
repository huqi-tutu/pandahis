#!/usr/bin/env python3
"""五帝评述/见证强制重跑（覆盖旧文件；评述带在途顾颉刚配额）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

import cw_lib as cw  # noqa: E402

GU_RE = re.compile(r"顾颉刚|古史辨")
DYNASTY = "五帝"
GU_MAX_RATIO = 0.45  # 在途阈值略严于最终 50%，留余量


def _doc_has_gu(doc: dict) -> bool:
    return bool(GU_RE.search(json.dumps(doc.get("entries") or [], ensure_ascii=False)))


def _commentary_extra(gu_used: int, done: int, total: int) -> str:
    """已完成 done 条评述中有 gu_used 条含顾；下一条是否禁止。"""
    # 若本条再用顾，占比 = (gu_used+1)/(done+1)
    next_ratio = (gu_used + 1) / (done + 1)
    hard_cap = int(total * GU_MAX_RATIO)
    lines = [
        "- 禁止「原文/白话」翻译体；禁止姓氏溯源/纯记事充评述。",
        "- 教材级框架不得放第 1 条；同文件顾颉刚至多 1 条。",
    ]
    if gu_used >= hard_cap or next_ratio > GU_MAX_RATIO:
        lines.append(
            f"- **禁止**引用顾颉刚或《古史辨》（本朝配额：已用 {gu_used}/{done}，"
            f"上限约 {hard_cap}/{total}）。改用其他评述人与著作。"
        )
    elif gu_used / max(done, 1) >= 0.30:
        lines.append(
            f"- 本朝已较多使用顾颉刚（{gu_used}/{done}），本条**优先不用**顾颉刚/《古史辨》。"
        )
    return "\n".join(lines)


def _witness_extra() -> str:
    return "\n".join(
        [
            "- 「传为」陵墓、现代纪念碑属 E 层：不得标 P0；仅有 E 则输出 []。",
            "- 国家专祀连续陵园（如桥山黄帝陵）可高排；村里传墓不可冒充。",
            "- 早期存在性物证（铸铭名号等）优先于传说陵。",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="五帝评述/见证强制重跑")
    parser.add_argument("--mode", choices=["both", "commentary", "witness"], default="both")
    parser.add_argument("--max", type=int, default=0, help="最多处理几条史略（0=全部）")
    args = parser.parse_args()

    cw.validate_histograph_root()
    paths = cw.histograph_paths()
    mid = paths["commentary"].parent / "05工作流中间产物" / "评述见证补全"
    mid.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary_path = mid / f"五帝_force_rerun_{stamp}.json"

    entries = cw.list_entries_by_dynasty(DYNASTY)
    if args.max > 0:
        entries = entries[: args.max]
    total = len(entries)
    modes: list[str] = (
        ["commentary", "witness"]
        if args.mode == "both"
        else [args.mode]
    )
    print(
        f"强制重跑 dyn={DYNASTY} n={total} modes={modes} gu_cap≈{GU_MAX_RATIO:.0%}",
        flush=True,
    )

    results: list[dict] = []
    gu_used = 0
    commentary_done = 0

    # 先评述后见证，便于配额
    ordered_modes = [m for m in ("commentary", "witness") if m in modes]

    for mode in ordered_modes:
        label = "评述" if mode == "commentary" else "见证"
        for i, e in enumerate(entries, 1):
            eid = str(e.get("史略ID") or "").strip()
            name = str(e.get("史略名称") or "").strip()
            if mode == "commentary":
                extra = _commentary_extra(gu_used, commentary_done, total)
            else:
                extra = _witness_extra()
            print(f"[{mode} {i}/{total}] → {label} {eid} {name} …", flush=True)
            try:
                r = cw.compose_one(
                    mode,  # type: ignore[arg-type]
                    entry_id=eid,
                    revise=True,
                    extra_prompt=extra,
                )
                out = Path(r["path"])
                doc = json.loads(out.read_text(encoding="utf-8"))
                if mode == "commentary":
                    commentary_done += 1
                    if _doc_has_gu(doc):
                        gu_used += 1
                        print(
                            f"    （含顾颉刚；配额 {gu_used}/{commentary_done}）",
                            flush=True,
                        )
                print(
                    f"    ✅ {label} {eid} status={r.get('status')} entries={r.get('entry_count')}",
                    flush=True,
                )
                results.append(
                    {
                        "id": eid,
                        "name": name,
                        "mode": mode,
                        "status": "ok",
                        "doc_status": r.get("status"),
                        "entry_count": r.get("entry_count"),
                        "gu_quota": f"{gu_used}/{commentary_done}" if mode == "commentary" else None,
                    }
                )
            except Exception as ex:
                print(f"    ❌ {label} {eid}: {ex}", flush=True)
                traceback.print_exc()
                results.append(
                    {
                        "id": eid,
                        "name": name,
                        "mode": mode,
                        "status": "error",
                        "error": str(ex),
                    }
                )

    err = [x for x in results if x["status"] == "error"]
    ok = [x for x in results if x["status"] == "ok"]
    print(f"\n=== DONE ok={len(ok)} err={len(err)} gu_final={gu_used}/{commentary_done} ===", flush=True)
    summary_path.write_text(
        json.dumps(
            {
                "stamp": stamp,
                "dynasty": DYNASTY,
                "gu_used": gu_used,
                "commentary_done": commentary_done,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"summary → {summary_path}", flush=True)

    # 朝代配额终检
    from verify_cw import verify_dynasty_commentary  # noqa: WPS433

    dyn_issues = verify_dynasty_commentary(DYNASTY, commentary_dir=paths["commentary"])
    for it in dyn_issues:
        print(f"DYNASTY {it['level']}: {it['msg']}", flush=True)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
