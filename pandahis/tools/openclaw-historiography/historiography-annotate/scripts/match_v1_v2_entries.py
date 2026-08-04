#!/usr/bin/env python3
"""V1↔V2 skeleton 条目匹配 → entry_entity_map + llm_verify_queue。

匹配策略（confidence < 1.0 一律 needs_llm_verify）：
  Tier1 同卷精确同名 → 1.0
  Tier2 别名 canonical 相同 → 0.95
  Tier3 原文字句锚点（≥6字包含）+ 分类同 → 0.85–0.95
  Tier4 段落 IoU ≥ 0.5 + 分类同 → IoU 值
  未匹配 → unresolved

用法:
  python3 match_v1_v2_entries.py
  python3 match_v1_v2_entries.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import sys

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from canonical_resolve import load_alias_table, resolve_canonical, same_person_key  # noqa: E402

GROUP_KEYWORDS = ("儒林", "酷吏", "游侠", "货殖", "佞幸", "循吏")


def _load_match_blocklist() -> Set[Tuple[str, str, str, str]]:
    """(work, vol, v1_name, v2_name) 禁止自动配对；见 史略异名表.json match_blocklist。"""
    out: Set[Tuple[str, str, str, str]] = set()
    for row in load_alias_table().get("match_blocklist") or []:
        w = str(row.get("work") or "").strip()
        v = str(row.get("vol") or "").strip()
        a = str(row.get("v1_name") or "").strip()
        b = str(row.get("v2_name") or "").strip()
        if w and v and a and b:
            out.add((w, v, a, b))
            out.add((w, v, b, a))
    return out


_BLOCKLIST: Set[Tuple[str, str, str, str]] | None = None


def _is_blocked(v1: "EntryRef", v2: "EntryRef") -> bool:
    global _BLOCKLIST
    if _BLOCKLIST is None:
        _BLOCKLIST = _load_match_blocklist()
    key = (v1.work, v1.vol, v1.史略名称, v2.史略名称)
    return key in _BLOCKLIST


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _out_dir() -> Path:
    d = _repo_root() / "data" / "05工作流中间产物" / "canonical命名"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_skeleton_path(fp: Path) -> Tuple[str, str, str]:
    m = re.match(r"(\d{2}[^_]+)_(\d{3})_(.+?)_skeleton\.json", fp.name)
    if not m:
        raise ValueError(f"无法解析: {fp.name}")
    return m.group(1), m.group(2), m.group(3)


def _paragraph_set(entry: dict) -> Set[int]:
    out: Set[int] = set()
    for p in entry.get("paragraphs") or []:
        pf = int(p.get("paragraph_from") or p.get("paragraph") or 0)
        pt = int(p.get("paragraph_to") or pf)
        for i in range(pf, pt + 1):
            if i > 0:
                out.add(i)
    return out


def _paragraph_iou(a: Set[int], b: Set[int]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _text_snippet(entry: dict, n: int = 80) -> str:
    t = str(entry.get("原文字句") or entry.get("史略简介") or "").strip()
    t = re.sub(r"\s+", "", t)
    return t[:n]


def _is_group_volume(title: str) -> bool:
    return any(kw in title for kw in GROUP_KEYWORDS)


@dataclass
class EntryRef:
    work: str
    vol: str
    vol_title: str
    史略ID: str
    史略名称: str
    史略分类: str
    原文字句: str = ""
    paragraphs: Set[int] = field(default_factory=set)


@dataclass
class MatchRecord:
    v1: Optional[dict]
    v2: Optional[dict]
    canonical_name: str
    match_method: str
    confidence: float
    needs_llm_verify: bool
    paragraph_iou: float = 0.0
    notes: str = ""


def _load_entries_from_dir(skeleton_dir: Path) -> Dict[Tuple[str, str], List[EntryRef]]:
    by_vol: Dict[Tuple[str, str], List[EntryRef]] = defaultdict(list)
    for fp in sorted(skeleton_dir.glob("*_skeleton.json")):
        try:
            work, vol, title = _parse_skeleton_path(fp)
        except ValueError:
            continue
        data = json.loads(fp.read_text(encoding="utf-8"))
        vol_title = str(data.get("volume") or title)
        for e in data.get("entries") or []:
            name = str(e.get("史略名称") or "").strip()
            if not name:
                continue
            by_vol[(work, vol)].append(
                EntryRef(
                    work=work,
                    vol=vol,
                    vol_title=vol_title,
                    史略ID=str(e.get("史略ID") or ""),
                    史略名称=name,
                    史略分类=str(e.get("史略分类") or ""),
                    原文字句=_text_snippet(e, 200),
                    paragraphs=_paragraph_set(e),
                )
            )
    return by_vol


def _entry_dict(ref: EntryRef) -> dict:
    return {
        "work": ref.work,
        "vol": ref.vol,
        "vol_title": ref.vol_title,
        "史略ID": ref.史略ID,
        "史略名称": ref.史略名称,
        "史略分类": ref.史略分类,
        "原文字句": ref.原文字句[:120],
    }


def _text_anchor_score(a: str, b: str) -> float:
    ta, tb = re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)
    if len(ta) < 6 or len(tb) < 6:
        return 0.0
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    for length in range(min(len(shorter), 40), 5, -1):
        sub = shorter[:length]
        if sub in longer:
            return 0.85 + 0.1 * (length / 40)
    return 0.0


def _match_pair(v1: EntryRef, v2: EntryRef, *, group_vol: bool) -> Optional[MatchRecord]:
    if group_vol:
        return None  # 群像传禁止自动 IoU 匹配
    if _is_blocked(v1, v2):
        return None

    cn = resolve_canonical(v1.史略名称, category=v1.史略分类).canonical
    cn2 = resolve_canonical(v2.史略名称, category=v2.史略分类).canonical
    proposed = cn if cn else cn2

    # Tier1 exact
    if v1.史略名称 == v2.史略名称:
        iou = _paragraph_iou(v1.paragraphs, v2.paragraphs)
        conf = 1.0
        method = "exact_name"
        if v1.史略分类 != v2.史略分类:
            conf = 0.9
            method = "exact_name_category_mismatch"
        return MatchRecord(
            v1=_entry_dict(v1),
            v2=_entry_dict(v2),
            canonical_name=proposed or v1.史略名称,
            match_method=method,
            confidence=conf,
            needs_llm_verify=conf < 1.0,
            paragraph_iou=iou,
        )

    # Tier2 alias
    if same_person_key(v1.史略名称, v2.史略名称, category_a=v1.史略分类, category_b=v2.史略分类):
        iou = _paragraph_iou(v1.paragraphs, v2.paragraphs)
        return MatchRecord(
            v1=_entry_dict(v1),
            v2=_entry_dict(v2),
            canonical_name=proposed,
            match_method="alias_canonical",
            confidence=0.95,
            needs_llm_verify=True,
            paragraph_iou=iou,
            notes=f"V1={v1.史略名称} V2={v2.史略名称}",
        )

    # Tier3 text anchor
    if v1.史略分类 == v2.史略分类:
        anchor = _text_anchor_score(v1.原文字句, v2.原文字句)
        if anchor >= 0.85:
            iou = _paragraph_iou(v1.paragraphs, v2.paragraphs)
            return MatchRecord(
                v1=_entry_dict(v1),
                v2=_entry_dict(v2),
                canonical_name=proposed or v1.史略名称,
                match_method="text_anchor",
                confidence=anchor,
                needs_llm_verify=True,
                paragraph_iou=iou,
            )

    # Tier4 IoU
    if v1.史略分类 == v2.史略分类:
        iou = _paragraph_iou(v1.paragraphs, v2.paragraphs)
        if iou >= 0.5:
            return MatchRecord(
                v1=_entry_dict(v1),
                v2=_entry_dict(v2),
                canonical_name=proposed or v1.史略名称,
                match_method="paragraph_iou",
                confidence=round(iou, 4),
                needs_llm_verify=True,
                paragraph_iou=iou,
            )

    return None


def _greedy_match(v1_list: List[EntryRef], v2_list: List[EntryRef], *, group_vol: bool) -> Tuple[List[MatchRecord], Set[int], Set[int]]:
    """按 confidence 降序贪心配对。"""
    candidates: List[Tuple[float, int, int, MatchRecord]] = []
    for i, v1 in enumerate(v1_list):
        for j, v2 in enumerate(v2_list):
            rec = _match_pair(v1, v2, group_vol=group_vol)
            if rec:
                candidates.append((rec.confidence, i, j, rec))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    matched_v1: Set[int] = set()
    matched_v2: Set[int] = set()
    records: List[MatchRecord] = []

    for _conf, i, j, rec in candidates:
        if i in matched_v1 or j in matched_v2:
            continue
        matched_v1.add(i)
        matched_v2.add(j)
        records.append(rec)

    return records, matched_v1, matched_v2


def run_match(*, dry_run: bool = False) -> dict:
    v1_dir = _repo_root() / "data" / "03索引标注条目"
    v2_dir = _repo_root() / "data" / "10新标注条目"

    v1_by_vol = _load_entries_from_dir(v1_dir)
    v2_by_vol = _load_entries_from_dir(v2_dir)

    all_vols = sorted(set(v1_by_vol.keys()) | set(v2_by_vol.keys()))
    matches: List[dict] = []
    v1_only: List[dict] = []
    v2_only: List[dict] = []
    llm_queue: List[dict] = []

    stats = defaultdict(int)

    for key in all_vols:
        v1_list = v1_by_vol.get(key, [])
        v2_list = v2_by_vol.get(key, [])
        vol_title = (v1_list[0].vol_title if v1_list else v2_list[0].vol_title) if (v1_list or v2_list) else ""
        group_vol = _is_group_volume(vol_title)

        if not v1_list:
            for v2 in v2_list:
                v2_only.append(_entry_dict(v2))
                stats["v2_only"] += 1
            continue
        if not v2_list:
            for v1 in v1_list:
                v1_only.append(_entry_dict(v1))
                stats["v1_only"] += 1
            continue

        records, matched_v1, matched_v2 = _greedy_match(v1_list, v2_list, group_vol=group_vol)
        for rec in records:
            d = {
                "v1": rec.v1,
                "v2": rec.v2,
                "canonical_name": rec.canonical_name,
                "match_method": rec.match_method,
                "confidence": rec.confidence,
                "needs_llm_verify": rec.needs_llm_verify,
                "paragraph_iou": rec.paragraph_iou,
                "notes": rec.notes,
            }
            matches.append(d)
            stats["matched"] += 1
            if rec.needs_llm_verify:
                stats["needs_llm"] += 1
                llm_queue.append(
                    {
                        "id": f"CVQ_{stats['needs_llm']:05d}",
                        "status": "pending",
                        "match_method": rec.match_method,
                        "confidence": rec.confidence,
                        "candidates": [rec.v1["史略名称"], rec.v2["史略名称"]],
                        "proposed_canonical": rec.canonical_name,
                        "category": rec.v1.get("史略分类") or rec.v2.get("史略分类"),
                        "evidence": {
                            "v1": rec.v1,
                            "v2": rec.v2,
                            "paragraph_iou": rec.paragraph_iou,
                            "notes": rec.notes,
                        },
                        "prompt_hint": (
                            f"判断「{rec.v1['史略名称']}」(V1) 与「{rec.v2['史略名称']}」(V2) "
                            f"是否为同一人；若是，canonical 应为「{rec.canonical_name}」。"
                        ),
                    }
                )
            else:
                stats["auto_pass"] += 1

        for i, v1 in enumerate(v1_list):
            if i not in matched_v1:
                v1_only.append(_entry_dict(v1))
                stats["v1_only"] += 1
        for j, v2 in enumerate(v2_list):
            if j not in matched_v2:
                v2_only.append(_entry_dict(v2))
                stats["v2_only"] += 1

    result = {
        "schema": "entry_entity_map/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": dict(stats),
        "matches": matches,
        "v1_only": v1_only,
        "v2_only": v2_only,
    }

    llm_doc = {
        "schema": "llm_verify_queue/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "confidence < 1.0 须 LLM 同人判定后方可统一名称",
        "count": len(llm_queue),
        "items": llm_queue,
    }

    if not dry_run:
        out = _out_dir()
        (out / "entry_entity_map.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out / "llm_verify_queue.json").write_text(
            json.dumps(llm_doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary_lines = [
            f"# V1↔V2 匹配摘要",
            "",
            f"- 生成时间: {result['generated_at']}",
            f"- 已匹配: {stats['matched']}",
            f"- 自动通过 (confidence=1.0): {stats['auto_pass']}",
            f"- 待 LLM 校验: {stats['needs_llm']}",
            f"- 仅 V1: {stats['v1_only']}",
            f"- 仅 V2: {stats['v2_only']}",
            "",
        ]
        (out / "匹配摘要.md").write_text("\n".join(summary_lines), encoding="utf-8")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="V1↔V2 entry matching")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run_match(dry_run=args.dry_run)
    s = result["stats"]
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print(f"\n→ {_out_dir() / 'entry_entity_map.json'}")


if __name__ == "__main__":
    main()
