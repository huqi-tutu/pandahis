#!/usr/bin/env python3
"""V2 skeleton 合并 → 史记汉书全局索引（复用 V1 GLBL 编号 + enrichment）。

规则：
- 数据源：data/10新标注条目/*_skeleton.json
- 合并键：史略名称（仅名称）
- 史料标注字段以 V2 为准；V1 匹配仅 史略来源=史料提取
- 厚度门与 V1 merge 一致
- V1 同名（史料提取线）：史略ID 直接复用 V1 编号
- V1 无匹配：新编号从 GLBL_01087 起（不与已占用编号冲突）

用法:
  python3 merge_v2_global_index.py
  python3 merge_v2_global_index.py --dry-run
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

_ANNOTATE_DIR = Path(__file__).resolve().parents[1]
if str(_ANNOTATE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANNOTATE_DIR))

from merge_global_entries import (  # noqa: E402
    _build_glbl_entry,
    _load_sources,
    _rank_sources,
)
from source_thickness import (  # noqa: E402
    apply_thickness_mub_swap,
    build_deferred_record,
    should_defer_glbl,
)

ANNOTATION_FIELDS = frozenset(
    {
        "主要史料出处",
        "五级细坐标",
        "六级段落锚点",
        "原文出处",
        "原文字句",
        "paragraphs",
        "source_entries",
        "合并来源",
        "来源著作",
        "来源条目数",
        "段落域数",
        "母本著作",
        "母本史略ID",
    }
)

V1_ENRICHMENT_FIELDS = frozenset(
    {
        "史略简介",
        "优先级",
        "优先级判定理由",
        "史略开始年",
        "史略结束年",
        "峰值年",
        "峰值原因",
        "峰值类型",
        "峰值置信度",
        "人物标签",
        "人物标签判定理由",
        "人物标签置信度",
        "一级文明坐标",
        "二级朝代坐标",
        "三级政权坐标",
        "四级帝王坐标",
        "文明ID",
        "朝代ID",
        "政权ID",
        "帝王ID",
        "宗戚ID",
        "考订依据",
        "_auto_filled",
        "_needs_llm",
        "_年LLM依据",
        "年LLM依据",
        "主旨",
        "子类",
        "制度类型",
        "作者或提出者",
        "论著标签",
        "影响",
        "边界备注",
        "审核状态",
        "建议年份",
        "建议挂靠帝王",
    }
)

GLBL_START = 1087


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _glbl_num(gid: str) -> int:
    m = re.match(r"GLBL_(\d+)", gid or "")
    return int(m.group(1)) if m else 999999


def _load_v1_extract_by_name(index_path: Path) -> Dict[str, dict]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    buckets: Dict[str, List[dict]] = defaultdict(list)
    for entry in data:
        if entry.get("史略来源") != "史料提取":
            continue
        name = str(entry.get("史略名称") or "").strip()
        if name:
            buckets[name].append(entry)
    out: Dict[str, dict] = {}
    for name, items in buckets.items():
        out[name] = min(items, key=lambda e: _glbl_num(e.get("史略ID", "")))
    return out


def _overlay_v1_enrichment(v2_entry: dict, v1_entry: Optional[dict]) -> dict:
    out = copy.deepcopy(v2_entry)
    if not v1_entry:
        return out
    for field, val in v1_entry.items():
        if field in ("史略ID", "史略名称", "史略分类", "史略来源") or field in ANNOTATION_FIELDS:
            continue
        if field in V1_ENRICHMENT_FIELDS or field not in out:
            if val not in (None, ""):
                out[field] = copy.deepcopy(val)
    out["史略来源"] = "史料提取"
    return out


def merge(*, dry_run: bool = False) -> dict:
    root = _repo_root()
    v2_root = root / "data" / "10新标注条目"
    v1_index = root / "data" / "03索引标注条目" / "史略索引_01至02.json"
    out_path = v2_root / "史略索引_史记汉书.json"
    thin_path = root / "data" / "05工作流中间产物" / "薄标注待补全" / "registry_v2.json"

    sources = _load_sources(v2_root, "01史记_*") + _load_sources(v2_root, "02汉书_*")
    v1_by_name = _load_v1_extract_by_name(v1_index)

    groups: Dict[str, List[dict]] = defaultdict(list)
    for s in sources:
        groups[s["name"]].append(s)

    entries: List[dict] = []
    deferred: List[dict] = []
    glbl_seq = GLBL_START - 1
    used_glbl_ids: set[str] = set()
    multi = 0
    cross = 0
    v1_matched = 0
    v1_id_reused = 0
    new_id_assigned = 0

    for name, group in sorted(groups.items(), key=lambda x: (x[1][0]["cat"], x[0])):
        ranked = apply_thickness_mub_swap(_rank_sources(group))
        defer, total_chars, reason = should_defer_glbl(ranked)
        if defer:
            deferred.append(build_deferred_record(ranked, total_chars=total_chars, reason=reason))
            continue

        v1_ref = v1_by_name.get(name)
        if v1_ref and v1_ref.get("史略ID"):
            glbl_id = str(v1_ref["史略ID"])
            v1_id_reused += 1
        else:
            while True:
                glbl_seq += 1
                glbl_id = f"GLBL_{glbl_seq:05d}"
                if glbl_id not in used_glbl_ids:
                    break
            new_id_assigned += 1

        used_glbl_ids.add(glbl_id)
        base = _build_glbl_entry(glbl_id, group, ranked=ranked)
        ent = _overlay_v1_enrichment(base, v1_ref)
        entries.append(ent)

        if v1_ref:
            v1_matched += 1
        if len(group) > 1:
            multi += 1
        if len({g["work"] for g in group}) > 1:
            cross += 1

    entries.sort(key=lambda e: _glbl_num(e.get("史略ID", "")))

    if not dry_run:
        thin_path.parent.mkdir(parents=True, exist_ok=True)
        thin_path.write_text(
            json.dumps(
                {
                    "schema": "thin_annotation_deferred/v2",
                    "source": "10新标注条目",
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "threshold_han_chars": 100,
                    "entry_count": len(deferred),
                    "entries": deferred,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "output_path": str(out_path),
        "thin_registry_path": str(thin_path),
        "total_entries": len(entries),
        "v1_enrichment_matched": v1_matched,
        "v1_id_reused": v1_id_reused,
        "new_id_assigned": new_id_assigned,
        "thin_deferred": len(deferred),
        "multi_source": multi,
        "cross_work": cross,
        "source_skeleton_entries": len(sources),
        "id_range": (
            f"{entries[0]['史略ID']}..{entries[-1]['史略ID']}" if entries else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = merge(dry_run=args.dry_run)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not args.dry_run:
        print(f"\n✅ 已写入 {stats['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
