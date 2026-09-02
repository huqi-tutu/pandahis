#!/usr/bin/env python3
"""从 _versions 优稿反推成稿/母本字数比，辅助校准 TRANSLATE_LENGTH_RATIO（软警告）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.config import paths, load_dotenv  # noqa: E402


def _plain(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _mother_plain(data: Dict[str, Any]) -> str:
    src = data.get("史料原文")
    if isinstance(src, str):
        return _plain(src)
    if isinstance(src, dict):
        return _plain(str(src.get("text") or ""))
    return ""


def _detail_plain(data: Dict[str, Any]) -> str:
    detail = str(data.get("翻译详情") or "")
    body = detail.split("参考著作", 1)[0]
    return _plain(body)


def scan_versions(versions_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not versions_root.is_dir():
        return rows
    for folder in sorted(versions_root.iterdir()):
        if not folder.is_dir():
            continue
        for fp in sorted(folder.glob("*.v*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            mother = _mother_plain(data)
            detail = _detail_plain(data)
            m_len = len(mother)
            d_len = len(detail)
            if not m_len or not d_len:
                continue
            ratio = d_len / m_len
            rows.append(
                {
                    "file": str(fp),
                    "entry": data.get("史略ID"),
                    "version": data.get("翻译版本"),
                    "mother_chars": m_len,
                    "detail_chars": d_len,
                    "ratio": round(ratio, 3),
                }
            )
    return rows


def _version_roots() -> List[Path]:
    p = paths()
    roots = [
        Path(p["translate_output"]) / "_versions",
        Path(p["translate_output_v2"]) / "_versions",
    ]
    seen: set[str] = set()
    out: List[Path] = []
    for r in roots:
        key = str(r.resolve())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def main() -> int:
    load_dotenv()
    rows: List[Dict[str, Any]] = []
    for root in _version_roots():
        rows.extend(scan_versions(root))
    if not rows:
        print("未找到可统计版本（已扫描 translate_output 与 translate_output_v2 下 _versions/）")
        return 1

    ratios = sorted(r["ratio"] for r in rows)
    n = len(ratios)
    median = ratios[n // 2]
    p75 = ratios[int(n * 0.75)]
    p90 = ratios[int(n * 0.90)] if n >= 10 else ratios[-1]
    avg = sum(ratios) / n

    print(f"样本数: {n}")
    print(f"成稿/母本 比 — 中位 {median:.2f}  均值 {avg:.2f}  P75 {p75:.2f}  P90 {p90:.2f}")
    print(f"建议 TRANSLATE_LENGTH_RATIO（软警告）: {max(1.2, round(p75, 2))}")
    print()
    for r in rows:
        print(
            f"  {r['entry']} {r['version']}: "
            f"{r['detail_chars']}/{r['mother_chars']} = {r['ratio']:.2f}  ({r['file']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
