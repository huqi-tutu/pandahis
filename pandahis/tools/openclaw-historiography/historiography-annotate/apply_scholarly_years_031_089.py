#!/usr/bin/env python3
"""将 031–089 中误用「去世年单点」、但学界有推测生卒的条目改为完整区间并写 _年LLM依据。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from lib_config import coerce_year, normalize_entry_category
from person_year_fallback import entry_has_llm_year_basis
from shiji_scholarly_lifespans import LIFESPANS_BY_EID, lookup_scholarly_lifespan

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"


def apply_scholarly(entry: dict, start: int, end: int, note: str) -> bool:
    cur_s = coerce_year(entry.get("史略开始年"))
    cur_e = coerce_year(entry.get("史略结束年"))
    if cur_s == start and cur_e == end and entry_has_llm_year_basis(entry):
        return False
    entry["史略开始年"] = int(start)
    entry["史略结束年"] = int(end)
    af = dict(entry.get("_auto_filled") or {})
    af["_年LLM依据"] = note
    for k in ("_年兜底级别", "_年兜底依据", "_死亡年锚定", "_年待LLM"):
        af.pop(k, None)
    entry["_auto_filled"] = af
    needs = [f for f in (entry.get("_needs_llm") or []) if f not in (
        "史略开始年", "史略结束年",
    )]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)
    return True


def main() -> int:
    logs: List[str] = []
    stats = {"applied": 0, "skip_llm": 0, "skip_no_data": 0, "skip_junwang": 0}

    for vol in range(31, 90):
        for path in sorted(ANN.glob(f"01史记_{vol:03d}_*_skeleton.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for entry in data.get("entries", []):
                eid = entry.get("史略ID", "?")
                name = entry.get("史略名称", "?")
                cat = normalize_entry_category(entry.get("史略分类", ""))

                if cat == "君王":
                    stats["skip_junwang"] += 1
                    continue
                if cat not in ("士臣", "庶众", "宗戚"):
                    continue
                if entry_has_llm_year_basis(entry):
                    stats["skip_llm"] += 1
                    continue

                span = lookup_scholarly_lifespan(entry)
                if span is None:
                    stats["skip_no_data"] += 1
                    continue

                start, end, note = span
                af = entry.get("_auto_filled") or {}
                was_death_only = af.get("_年兜底级别") == "去世年单点"
                cur_s, cur_e = coerce_year(entry.get("史略开始年")), coerce_year(entry.get("史略结束年"))

                if apply_scholarly(entry, start, end, note):
                    stats["applied"] += 1
                    tag = "去世年单点→学界" if was_death_only else "补全学界"
                    logs.append(
                        f"{eid} {name}: {tag} {cur_s}～{cur_e} → {start}～{end} | {note[:36]}"
                    )
                    changed = True

            if changed:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    print("统计:", stats)
    print(f"\n变更 {len(logs)} 条:")
    for ln in logs:
        print(f"  · {ln}")
    print(f"\n学界表共 {len(LIFESPANS_BY_EID)} 条 eid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
