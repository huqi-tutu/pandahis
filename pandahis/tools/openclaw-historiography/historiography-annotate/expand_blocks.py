#!/usr/bin/env python3
"""块优先工作流：将叙事块草稿展开为 segment_attribution。

每段须被 exclude 或恰好一个 block 覆盖；块与 exclude 不可重叠。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from lib_config import VALID_CATS, VALID_EXCLUDE_REASONS


def _parse_ranges(items: List[dict], key_from: str, key_to: str) -> List[Tuple[int, int, dict]]:
    out: List[Tuple[int, int, dict]] = []
    for item in items:
        pf = int(item[key_from])
        pt = int(item[key_to])
        if pf > pt:
            raise ValueError(f"paragraph_from {pf} > paragraph_to {pt}: {item}")
        out.append((pf, pt, item))
    return out


def expand_blocks(draft: dict) -> Tuple[List[dict], List[str]]:
    """返回 (segment_attribution, errors)。"""
    errors: List[str] = []
    total = int(draft.get("total_paragraphs") or 0)
    if total <= 0:
        return [], ["total_paragraphs 须为正整数"]

    excludes = _parse_ranges(draft.get("excludes") or [], "paragraph_from", "paragraph_to")
    blocks = _parse_ranges(draft.get("blocks") or [], "paragraph_from", "paragraph_to")

    exclude_map: Dict[int, str] = {}
    for pf, pt, item in excludes:
        reason = (item.get("exclude_reason") or "").strip()
        if reason not in VALID_EXCLUDE_REASONS:
            errors.append(f"非法 exclude_reason: {reason!r} (P{pf}-P{pt})")
        for p in range(pf, pt + 1):
            if p in exclude_map:
                errors.append(f"P{p} 重复 exclude")
            exclude_map[p] = reason

    owner_map: Dict[int, Tuple[str, str]] = {}
    for pf, pt, item in blocks:
        name = (item.get("name") or "").strip()
        cat = (item.get("category") or "").strip()
        if not name:
            errors.append(f"P{pf}-P{pt}: block 缺少 name")
        if cat not in VALID_CATS:
            errors.append(f"P{pf}-P{pt}: 非法 category {cat!r}")
        for p in range(pf, pt + 1):
            if p in exclude_map:
                errors.append(f"P{p} 同时出现在 exclude 与 block [{name}]")
                continue
            if p in owner_map:
                prev = owner_map[p]
                errors.append(f"P{p} 重复归属: [{prev[0]}] 与 [{name}]")
            owner_map[p] = (name, cat)

    attribution: List[dict] = []
    for p in range(1, total + 1):
        if p in exclude_map:
            attribution.append({"paragraph": p, "owners": [], "exclude_reason": exclude_map[p]})
        elif p in owner_map:
            name, cat = owner_map[p]
            attribution.append({"paragraph": p, "owners": [{"name": name, "category": cat}]})
        else:
            errors.append(f"P{p} 未覆盖（无 block 也无 exclude）")
            attribution.append({"paragraph": p, "owners": []})

    return attribution, errors


def merge_entry_paragraphs(draft: dict, attribution: List[dict]) -> List[dict]:
    """从 blocks 归纳 entries 用的 paragraphs 块（不含 volume，由调用方补）。"""
    by_key: Dict[Tuple[str, str], List[Tuple[int, int]]] = {}
    for item in draft.get("blocks") or []:
        key = (item["name"].strip(), item["category"].strip())
        by_key.setdefault(key, []).append((int(item["paragraph_from"]), int(item["paragraph_to"])))

    entries: List[dict] = []
    for (name, cat), ranges in sorted(by_key.items()):
        ranges.sort()
        merged: List[Tuple[int, int]] = []
        for pf, pt in ranges:
            if merged and pf <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], pt))
            else:
                merged.append((pf, pt))
        entries.append({
            "史略名称": name,
            "史略分类": cat,
            "paragraphs": [{"paragraph_from": pf, "paragraph_to": pt} for pf, pt in merged],
        })
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description="叙事块草稿 → segment_attribution")
    ap.add_argument("draft", type=Path, help="块草稿 JSON")
    ap.add_argument("-o", "--output", type=Path, help="写出 segment_attribution JSON 数组")
    ap.add_argument("--merge-entries", action="store_true", help="同时输出归纳后的 paragraphs 草稿")
    ap.add_argument("--pretty", action="store_true", default=True)
    args = ap.parse_args()

    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    attribution, errors = expand_blocks(draft)

    if errors:
        print("❌ 展开失败:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    result: Dict[str, Any] = {"segment_attribution": attribution}
    if args.merge_entries:
        result["entry_paragraphs_draft"] = merge_entry_paragraphs(draft, attribution)

    out_text = json.dumps(
        result if args.merge_entries else attribution,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
    )

    if args.output:
        args.output.write_text(out_text + "\n", encoding="utf-8")
        print(f"✅ 已写入 {args.output}（{len(attribution)} 段）")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
