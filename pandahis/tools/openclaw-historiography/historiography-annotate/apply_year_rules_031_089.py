#!/usr/bin/env python3
"""按人物年份规则重处理史记 031–089：保留 LLM 依据，其余走兜底链。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from coordinate_index import build_dynasty_index_from_json
from emperor_resolve import build_emperor_info_index
from lib_config import coerce_year, normalize_entry_category
from person_year_fallback import (
    FALLBACK_DEATH,
    FALLBACK_DYNASTY,
    FALLBACK_EMPEROR,
    FALLBACK_JUNWANG,
    apply_person_year_fallback,
    entry_has_llm_year_basis,
    write_fallback_years_to_entry,
)

ANN = Path(__file__).resolve().parents[3] / "data" / "03索引标注条目"


def sync_junwang(entry: dict, emperor_index: dict) -> Tuple[bool, str]:
    if normalize_entry_category(entry.get("史略分类", "")) != "君王":
        return False, ""
    emp = (entry.get("四级帝王坐标") or entry.get("史略名称") or "").strip()
    info = emperor_index.get(emp)
    if not info:
        return False, "无帝王"
    es, ee = info.get("start_year"), info.get("end_year")
    if es is None or ee is None:
        return False, "帝王无年在位"
    cur_s, cur_e = coerce_year(entry.get("史略开始年")), coerce_year(entry.get("史略结束年"))
    entry["史略开始年"] = int(es)
    entry["史略结束年"] = int(ee)
    af = dict(entry.get("_auto_filled") or {})
    af["_年兜底级别"] = FALLBACK_JUNWANG
    af["_年修正"] = (
        f"君王年与帝王表对齐：{cur_s}～{cur_e} → {es}～{ee}"
        if cur_s != es or cur_e != ee
        else f"君王年与帝王表一致 {es}～{ee}"
    )
    af.pop("_年兜底依据", None)
    af.pop("_年待LLM", None)
    entry["_auto_filled"] = af
    needs = [n for n in (entry.get("_needs_llm") or []) if n not in (
        "史略开始年", "史略结束年",
    )]
    if needs:
        entry["_needs_llm"] = needs
    else:
        entry.pop("_needs_llm", None)
    return True, af["_年修正"]


def reprocess_entry(
    entry: dict,
    emperor_index: dict,
    dynasty_index: dict,
) -> Tuple[str, str]:
    """返回 (action, detail)。"""
    eid = entry.get("史略ID", "?")
    name = entry.get("史略名称", "?")
    cat = normalize_entry_category(entry.get("史略分类", ""))

    if entry_has_llm_year_basis(entry):
        return "keep_llm", (entry.get("_auto_filled") or {}).get("_年LLM依据", "")[:40]

    if cat == "君王":
        ok, msg = sync_junwang(entry, emperor_index)
        return ("junwang", msg) if ok else ("skip", msg)

    if cat not in ("士臣", "庶众", "宗戚"):
        return "skip", "非人物"

    # 清除旧 PERSON_PATCH / 流水线占位年（无 LLM 依据）
    entry.pop("史略开始年", None)
    entry.pop("史略结束年", None)
    af = dict(entry.get("_auto_filled") or {})
    for k in ("_年兜底级别", "_年兜底依据", "_死亡年锚定"):
        af.pop(k, None)
    entry["_auto_filled"] = af

    emp = (entry.get("四级帝王坐标") or "").strip()
    emperor_info = emperor_index.get(emp)

    ys, ye, level, note = apply_person_year_fallback(
        entry,
        emperor_info=emperor_info,
        dynasty_index=dynasty_index,
    )
    if ys is None or ye is None:
        needs = list(entry.get("_needs_llm") or [])
        for f in ("史略开始年", "史略结束年"):
            if f not in needs:
                needs.append(f)
        entry["_needs_llm"] = needs
        af["_年待LLM"] = "须由大模型据史学界主流观点填写生卒"
        entry["_auto_filled"] = af
        return "needs_llm", "兜底失败，待 LLM"

    write_fallback_years_to_entry(entry, ys, ye, level, note)
    return level, f"{ys}～{ye} {note}"


def main() -> int:
    emperor_index = build_emperor_info_index()
    dynasty_index = build_dynasty_index_from_json()
    logs: List[str] = []
    stats = {}

    for vol in range(31, 90):
        for path in sorted(ANN.glob(f"01史记_{vol:03d}_*_skeleton.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            for entry in data.get("entries", []):
                action, detail = reprocess_entry(entry, emperor_index, dynasty_index)
                stats[action] = stats.get(action, 0) + 1
                eid = entry.get("史略ID")
                name = entry.get("史略名称")
                if action == "keep_llm":
                    continue
                if action == "skip":
                    continue
                if action == "junwang":
                    if detail and ("→" in detail or "一致" in detail):
                        logs.append(f"{eid} {name}: {detail}")
                        changed = True
                    continue
                if action == "needs_llm":
                    logs.append(f"{eid} {name}: 待LLM | {detail}")
                    changed = True
                    continue
                logs.append(f"{eid} {name}: {action} | {detail}")
                changed = True
            if changed:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    print("统计:", stats)
    print(f"\n变更 {len(logs)} 条:")
    for ln in logs[:60]:
        print(f"  · {ln}")
    if len(logs) > 60:
        print(f"  ... +{len(logs)-60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
