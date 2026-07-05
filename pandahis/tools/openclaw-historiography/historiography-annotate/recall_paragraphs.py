#!/usr/bin/env python3
"""按段落索引召回原文（标注 / 校验 / 翻译共用 SSOT）。

禁止翻译阶段自行 split 原文 txt；段号以 段落索引/*.json 为准。

用法:
  # 单卷连续区间
  python3 recall_paragraphs.py --work 01A尚书 --vol 001 --from 1 --to 8

  # skeleton 某条目（自动 min→max 连续召回，见 annotate SKILL）
  python3 recall_paragraphs.py --skeleton path/to/skeleton.json --entry-id SHANGSHU_001_02

  # JSON 输出（供 compose 流水线）
  python3 recall_paragraphs.py --work 01A尚书 --vol 001 --from 3 --to 3 --json

  # 全局史略索引条目（按 paragraphs[] 逐块召回，禁止 min→max 合并）
  # 每块 role：work == 条目.母本著作 → 母本，否则 → 补充
  python3 recall_paragraphs.py --global-index 史略索引_01至02.json --entry-id GLBL_00019 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib_config import paths


class RecallError(Exception):
    pass


def index_path(work: str, vol: str) -> Path:
    vol = str(vol).zfill(3)
    return paths()["paragraph_index"] / f"{work}_{vol}.json"


def load_paragraph_index(work: str, vol: str) -> dict:
    fp = index_path(work, vol)
    if not fp.is_file():
        raise RecallError(
            f"缺少段落索引: {fp}\n"
            f"请先运行: hist.py bootstrap --work {work}"
        )
    return json.loads(fp.read_text(encoding="utf-8"))


def paragraph_text(index: dict, para_id: int) -> str:
    total = int(index.get("total", 0))
    if para_id < 1 or para_id > total:
        raise RecallError(
            f"段号 {para_id} 越界（索引共 {total} 段，mode={index.get('paragraph_mode')})"
        )
    for p in index["paragraphs"]:
        if int(p["id"]) == para_id:
            return str(p["text"])
    raise RecallError(f"索引中未找到段 {para_id}")


def recall_range(index: dict, para_from: int, para_to: int) -> List[Tuple[int, str]]:
    """返回 [(段号, 文本), ...] 闭区间。"""
    if para_from > para_to:
        raise RecallError(f"paragraph_from {para_from} > paragraph_to {para_to}")
    return [(i, paragraph_text(index, i)) for i in range(para_from, para_to + 1)]


def recall_entry_ranges(
    entry: dict,
    *,
    work: str,
    vol: str,
    index: Optional[dict] = None,
) -> List[Tuple[int, str]]:
    """
    按 annotate SKILL：取条目 paragraphs 各卷的 min(from)→max(to) 连续区间。
    当前一卷 skeleton 默认同一卷；多区间先合并为一条连续带。
    """
    prs = entry.get("paragraphs") or []
    if not prs:
        raise RecallError(f"条目 {entry.get('史略ID', '?')} 无 paragraphs")

    idx = index or load_paragraph_index(work, vol)
    lo = min(int(p["paragraph_from"]) for p in prs)
    hi = max(int(p["paragraph_to"]) for p in prs)
    return recall_range(idx, lo, hi)


def recall_paragraph_block(block: dict) -> dict:
    """召回全局索引中单条 paragraph 域（一个 work/vol/from/to 闭区间）。"""
    work = block["work"]
    vol = str(block["vol"]).zfill(3)
    pf = int(block["paragraph_from"])
    pt = int(block["paragraph_to"])
    idx = load_paragraph_index(work, vol)
    chunks = recall_range(idx, pf, pt)
    return {
        "work": work,
        "vol": vol,
        "volume": block.get("volume", ""),
        "source_file": block.get("source_file", ""),
        "source_path": block.get("source_path", ""),
        "source_entry_id": block.get("source_entry_id", ""),
        "paragraph_from": pf,
        "paragraph_to": pt,
        "paragraph_mode": idx.get("paragraph_mode"),
        "paragraph_count": len(chunks),
        "paragraphs": [{"id": i, "text": t} for i, t in chunks],
        "text": join_recalled(chunks),
    }


def _block_role(entry: dict, block: dict) -> str:
    mother = entry.get("母本著作") or ""
    if block.get("work") == mother:
        return "母本"
    return "补充"


def load_global_index(index_path: Path) -> dict:
    fp = Path(index_path)
    if not fp.is_file():
        raise RecallError(f"全局索引不存在: {fp}")
    return json.loads(fp.read_text(encoding="utf-8"))


def find_global_entry(index: dict, entry_id: str) -> dict:
    for e in index.get("entries") or []:
        if e.get("史略ID") == entry_id:
            return e
    raise RecallError(f"全局索引中无条目 {entry_id}")


def recall_global_index_entry(
    entry: dict,
    *,
    sort_mother_first: bool = True,
) -> dict:
    """
    按 paragraphs[] 逐块召回；不跨块 min→max 合并。
    返回 blocks[]，每块含 role（母本/补充）与段落文本。
    """
    raw_blocks = entry.get("paragraphs") or []
    if not raw_blocks:
        raise RecallError(f"条目 {entry.get('史略ID', '?')} 无 paragraphs")

    blocks: List[dict] = []
    for i, b in enumerate(raw_blocks):
        rb = recall_paragraph_block(b)
        rb["role"] = _block_role(entry, b)
        rb["block_index"] = i
        blocks.append(rb)

    if sort_mother_first:
        blocks.sort(key=lambda x: (0 if x["role"] == "母本" else 1, x["block_index"]))

    return {
        "史略ID": entry.get("史略ID"),
        "史略名称": entry.get("史略名称"),
        "史略分类": entry.get("史略分类"),
        "母本著作": entry.get("母本著作"),
        "来源著作": entry.get("来源著作") or [],
        "来源条目数": int(entry.get("来源条目数") or len(raw_blocks)),
        "段落域数": int(entry.get("段落域数") or len(raw_blocks)),
        "block_count": len(blocks),
        "paragraph_count": sum(int(b["paragraph_count"]) for b in blocks),
        "blocks": blocks,
    }


def recall_from_global_index_file(index_path: Path, entry_id: str) -> dict:
    index = load_global_index(index_path)
    entry = find_global_entry(index, entry_id)
    return recall_global_index_entry(entry)


def join_recalled(chunks: List[Tuple[int, str]], *, separator: str = "\n") -> str:
    return separator.join(t for _, t in chunks)


def recall_for_skeleton_entry(
    skeleton_path: Path,
    *,
    entry_id: Optional[str] = None,
    entry_index: Optional[int] = None,
    work: Optional[str] = None,
    vol: Optional[str] = None,
) -> dict:
    data = json.loads(skeleton_path.read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    if entry_id:
        entry = next((e for e in entries if e.get("史略ID") == entry_id), None)
        if not entry:
            raise RecallError(f"skeleton 中无条目 {entry_id}")
    elif entry_index is not None:
        if entry_index < 0 or entry_index >= len(entries):
            raise RecallError(f"entry_index 越界: {entry_index}")
        entry = entries[entry_index]
    else:
        raise RecallError("需要 --entry-id 或 --entry-index")

    stem = skeleton_path.stem.replace("_skeleton", "")
    import re

    m = re.match(r"^(\d{1,2}[A-Za-z\u4e00-\u9fff]+)_(\d{3})_", stem)
    if not m:
        raise RecallError(f"无法从文件名解析著作/卷号: {skeleton_path.name}")
    work = work or m.group(1)
    vol = vol or m.group(2)

    index = load_paragraph_index(work, vol)
    chunks = recall_entry_ranges(entry, work=work, vol=vol, index=index)
    lo, hi = chunks[0][0], chunks[-1][0]

    return {
        "work": work,
        "vol": vol,
        "entry_id": entry.get("史略ID"),
        "entry_name": entry.get("史略名称"),
        "paragraph_from": lo,
        "paragraph_to": hi,
        "paragraph_mode": index.get("paragraph_mode"),
        "paragraph_count": len(chunks),
        "text": join_recalled(chunks),
        "paragraphs": [{"id": i, "text": t} for i, t in chunks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="段落索引召回原文（SSOT）")
    parser.add_argument("--work", help="著作，如 01A尚书")
    parser.add_argument("--vol", help="卷号，如 001")
    parser.add_argument("--from", dest="para_from", type=int, help="起始段号（含）")
    parser.add_argument("--to", dest="para_to", type=int, help="结束段号（含）")
    parser.add_argument("--skeleton", type=Path, help="卷 skeleton.json")
    parser.add_argument("--entry-id", help="史略ID")
    parser.add_argument("--entry-index", type=int, help="entries 下标，0 起")
    parser.add_argument("--global-index", type=Path, help="全局史略索引 JSON 路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--preview", type=int, default=0, help="仅预览前 N 段（与区间联用）")
    args = parser.parse_args()

    try:
        if args.global_index and args.entry_id:
            result = recall_from_global_index_file(args.global_index, args.entry_id)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(
                    f"📎 {result['史略ID']} {result['史略名称']} "
                    f"({result['block_count']} 域 / {result['paragraph_count']} 段)\n"
                )
                for b in result["blocks"]:
                    print(
                        f"  [{b['role']}] {b['work']} 卷{b['vol']} "
                        f"{b.get('volume','')} P{b['paragraph_from']}-P{b['paragraph_to']} "
                        f"({b['paragraph_count']} 段)"
                    )
                    if args.preview > 0:
                        for p in b["paragraphs"][: args.preview]:
                            t = p["text"]
                            snip = t[:72] + ("…" if len(t) > 72 else "")
                            print(f"    [P{p['id']:02d}] {snip}")
            return 0

        if args.skeleton:
            result = recall_for_skeleton_entry(
                args.skeleton,
                entry_id=args.entry_id,
                entry_index=args.entry_index,
                work=args.work,
                vol=args.vol,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                meta = result
                print(
                    f"📎 {meta['work']} 卷{meta['vol']} "
                    f"{meta['entry_name']} ({meta['entry_id']})\n"
                    f"   段 {meta['paragraph_from']}–{meta['paragraph_to']} "
                    f"(mode={meta['paragraph_mode']}, {meta['paragraph_count']} 段)\n"
                )
                if args.preview > 0:
                    for p in result["paragraphs"][: args.preview]:
                        t = p["text"]
                        snip = t[:72] + ("…" if len(t) > 72 else "")
                        print(f"  [P{p['id']:02d}] {snip}")
                    if result["paragraph_count"] > args.preview:
                        print(f"  … 共 {result['paragraph_count']} 段")
                else:
                    print(result["text"])
            return 0

        if not (args.work and args.vol and args.para_from is not None and args.para_to is not None):
            parser.error("需要 --work --vol --from --to，或 --skeleton + --entry-id")

        index = load_paragraph_index(args.work, args.vol)
        chunks = recall_range(index, args.para_from, args.para_to)
        payload = {
            "work": args.work,
            "vol": str(args.vol).zfill(3),
            "paragraph_from": args.para_from,
            "paragraph_to": args.para_to,
            "paragraph_mode": index.get("paragraph_mode"),
            "paragraph_count": len(chunks),
            "text": join_recalled(chunks),
            "paragraphs": [{"id": i, "text": t} for i, t in chunks],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"📎 {args.work} 卷{payload['vol']} "
                f"P{args.para_from}–P{args.para_to} "
                f"(mode={payload['paragraph_mode']}, {payload['paragraph_count']} 段)\n"
            )
            if args.preview > 0:
                for p in payload["paragraphs"][: args.preview]:
                    t = p["text"]
                    snip = t[:72] + ("…" if len(t) > 72 else "")
                    print(f"  [P{p['id']:02d}] {snip}")
            else:
                print(payload["text"])
        return 0
    except RecallError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
