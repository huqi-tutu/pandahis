"""区分「需走翻译流水线」与「朝代知识补全（免翻译）」条目。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from entry_source import (  # noqa: E402
    SOURCE_EXTRACT,
    SOURCE_SUPPLEMENT,
    is_supplement_entry,
)


def is_translate_required(entry: Dict[str, Any]) -> bool:
    return not is_supplement_entry(entry)


def load_translated_ids(translate_dir: Path) -> Set[str]:
    summary = translate_dir / "史略翻译_汇总.json"
    if summary.is_file():
        data = json.loads(summary.read_text(encoding="utf-8"))
        return {str(e["史略ID"]) for e in data.get("entries") or [] if e.get("史略ID")}
    return {
        p.stem.split("_")[0] + "_" + p.stem.split("_")[1]
        for p in translate_dir.glob("GLBL_*.json")
    }


def load_dynasty_detail_ids(detail_aggregate: Path) -> Set[str]:
    if not detail_aggregate.is_file():
        return set()
    data = json.loads(detail_aggregate.read_text(encoding="utf-8"))
    return {str(e["史略ID"]) for e in data.get("entries") or [] if e.get("史略ID")}


def compute_progress(
    entries: Iterable[Dict[str, Any]],
    *,
    translated_ids: Set[str],
    dynasty_detail_ids: Set[str],
) -> Dict[str, Any]:
    translate_required: List[Dict[str, Any]] = []
    dynasty_supplement: List[Dict[str, Any]] = []
    for e in entries:
        if is_supplement_entry(e):
            dynasty_supplement.append(e)
        else:
            translate_required.append(e)

    tr_done = sum(1 for e in translate_required if e["史略ID"] in translated_ids)
    dk_done = sum(1 for e in dynasty_supplement if e["史略ID"] in dynasty_detail_ids)

    by_dynasty: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "translate_total": 0,
            "translate_done": 0,
            "supplement_total": 0,
            "supplement_done": 0,
        }
    )
    for e in translate_required:
        dyn = str(e.get("二级朝代坐标") or "未知")
        by_dynasty[dyn]["translate_total"] += 1
        if e["史略ID"] in translated_ids:
            by_dynasty[dyn]["translate_done"] += 1
    for e in dynasty_supplement:
        dyn = str(e.get("二级朝代坐标") or "未知")
        by_dynasty[dyn]["supplement_total"] += 1
        if e["史略ID"] in dynasty_detail_ids:
            by_dynasty[dyn]["supplement_done"] += 1

    return {
        "index_total": len(translate_required) + len(dynasty_supplement),
        "translate_required_total": len(translate_required),
        "translate_done": tr_done,
        "dynasty_supplement_total": len(dynasty_supplement),
        "dynasty_detail_done": dk_done,
        "content_ready": tr_done + dk_done,
        "by_dynasty": dict(by_dynasty),
    }


def format_progress_report(progress: Dict[str, Any]) -> str:
    tr_total = progress["translate_required_total"]
    tr_done = progress["translate_done"]
    dk_total = progress["dynasty_supplement_total"]
    dk_done = progress["dynasty_detail_done"]
    pct = (tr_done / tr_total * 100) if tr_total else 0.0

    lines = [
        "📊 史略内容进度（修正口径）",
        f"   索引总条目: {progress['index_total']}",
        f"   需翻译: {tr_done}/{tr_total} ({pct:.1f}%)",
        f"   朝代知识补全（免翻译）: {dk_done}/{dk_total}",
        f"   已有详情正文: {progress['content_ready']}/{tr_total + dk_total}",
        "",
        "   按朝代（需翻译 | 朝代补全）:",
    ]
    for dyn, v in sorted(
        progress["by_dynasty"].items(),
        key=lambda x: -(x[1]["translate_total"] + x[1]["supplement_total"]),
    ):
        if v["translate_total"] or v["supplement_total"]:
            lines.append(
                f"     {dyn}: 翻译 {v['translate_done']}/{v['translate_total']}"
                f" | 补全 {v['supplement_done']}/{v['supplement_total']}"
            )
    return "\n".join(lines)
