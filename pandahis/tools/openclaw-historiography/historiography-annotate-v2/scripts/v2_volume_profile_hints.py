#!/usr/bin/env python3
"""v2 卷型黄灯：Step1a 判定的切法风格与 skeleton 是否对得上（只提醒，不拦批量）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from paths_config import histograph_paths  # noqa: E402


def _entry_span(entry: dict) -> int:
    total = 0
    for pr in entry.get("paragraphs") or []:
        if not isinstance(pr, dict):
            continue
        pf = int(pr.get("paragraph_from") or 0)
        pt = int(pr.get("paragraph_to") or pf)
        total += max(0, pt - pf + 1)
    return total


def collect_profile_yellow_hints(manifest: dict, skeleton: dict) -> List[str]:
    """A/B/C 与切法不一致时给黄灯文案（不 FAIL）。"""
    hints: List[str] = []
    mode = (manifest.get("narrative_mode") or "single").strip()
    arc = (manifest.get("volume_arc") or "").strip().upper()
    n_prot = len(manifest.get("protagonists") or [])
    entries = skeleton.get("entries") or []
    n_entries = len(entries)
    total = int(skeleton.get("total_paragraphs") or 0)
    attribution = skeleton.get("segment_attribution") or []
    n_exclude = sum(1 for row in attribution if row.get("exclude_reason"))

    # A = 单人卷（single / fanzuo）
    is_a = mode in ("single", "fanzuo") or arc == "A"
    # B = 多人卷（hezhuan，本纪多人 / 世家多代国君等）
    is_b = mode == "hezhuan" or arc == "B"
    # C = 合传（liezhuan_hezhuan 等）
    is_c = arc == "C" or (manifest.get("volume_subtype") or "") == "liezhuan_hezhuan"

    if is_a:
        if n_prot > 1:
            hints.append(
                "Step1a 判为【单人卷 A】，但定了多于 1 位主轴——请核对是否应为【多人卷 B】或【合传 C】。"
            )
        if n_entries > 1:
            hints.append(
                "Step1a 判为【单人卷 A】，但 skeleton 切出了多条 entry——像【多人卷 B】，请核对。"
            )

    if is_b and not is_c:
        if n_entries == 1 and total > 0:
            span = _entry_span(entries[0]) if entries else 0
            if span >= max(1, int(total * 0.6)):
                name = (entries[0].get("史略名称") or entries[0].get("name") or "").strip()
                hints.append(
                    f"Step1a 判为【多人卷 B】，但 {span}/{total} 段几乎全归「{name}」——"
                    "像【单人卷 A】，请核对（例：误把世家当始祖贯卷）。"
                )
        if n_prot >= 2 and n_entries < n_prot:
            hints.append(
                f"Step1a 定了 {n_prot} 位主轴，但只有 {n_entries} 条 entry——可能漏拆，请核对。"
            )
        if n_prot >= 2 and total >= 40 and n_exclude < max(3, int(total * 0.06)):
            hints.append(
                "Step1a 判为【多人卷 B】，但划出去的段落很少——"
                "中间享国链/小君是否误塞进主轴 block？请扫一眼（不必逐段）。"
            )

    if is_c and n_entries < 2:
        hints.append("Step1a 判为【合传 C】，但 entry 少于 2 条——请核对。")

    return hints


def print_profile_yellow_hints(manifest: dict, skeleton: dict) -> None:
    hints = collect_profile_yellow_hints(manifest, skeleton)
    if not hints:
        print("\n  🟡 卷型黄灯\n  ✅ Step1a 切法风格与 skeleton 大致一致", flush=True)
        return
    print("\n  🟡 卷型黄灯（不拦批量，供抽检）", flush=True)
    for h in hints:
        print(f"  ⚠️  {h}", flush=True)


def _protagonists_path(work: str, vol: str) -> Path:
    return histograph_paths()["annotate_work"] / f"{work}_{vol.zfill(3)}_protagonists.json"


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="v2 卷型黄灯（只提醒）")
    ap.add_argument("--work", required=True)
    ap.add_argument("--vol", required=True)
    ap.add_argument("--skeleton", type=Path)
    args = ap.parse_args()

    work = args.work.strip()
    vol = args.vol.zfill(3)
    pp = _protagonists_path(work, vol)
    if not pp.is_file():
        print(f"❌ 缺少 {pp}", file=sys.stderr)
        return 1
    manifest = json.loads(pp.read_text(encoding="utf-8"))

    if args.skeleton:
        sk_path = args.skeleton
    else:
        matches = list(histograph_paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
        if not matches:
            print("❌ skeleton 未找到", file=sys.stderr)
            return 1
        sk_path = matches[0]
    skeleton = json.loads(sk_path.read_text(encoding="utf-8"))
    print_profile_yellow_hints(manifest, skeleton)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
