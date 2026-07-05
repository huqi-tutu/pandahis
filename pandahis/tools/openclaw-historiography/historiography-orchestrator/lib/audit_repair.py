"""Step3 审计 MD 脚本修复：段落覆盖表与 skeleton 对齐（SSOT）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Tuple

from lib.config import paths


def _fmt_owners(seg: dict) -> str:
    if seg.get("exclude_reason"):
        return f"排除（{seg['exclude_reason']}）"
    parts = [f"{o.get('name', '?')}({o.get('category', '?')})" for o in (seg.get("owners") or [])]
    return " + ".join(parts) if parts else "—"


def build_paragraph_table_rows(segment_attribution: list) -> List[str]:
    return [
        f"| P{int(seg['paragraph'])} | {_fmt_owners(seg)} | — |"
        for seg in segment_attribution
    ]


def sync_audit_paragraph_table(
    work: str,
    vol: str,
    *,
    skeleton_path: Path | None = None,
) -> Tuple[bool, str]:
    """
    用 skeleton.segment_attribution 重写本卷「### 段落覆盖清单」。
    返回 (是否改写, 说明)。
    """
    vol = vol.zfill(3)
    sk_path = skeleton_path or _find_skeleton(work, vol)
    if not sk_path:
        return False, "未找到 skeleton"

    data = json.loads(sk_path.read_text(encoding="utf-8"))
    segs = data.get("segment_attribution") or []
    if not segs:
        return False, "skeleton 无 segment_attribution"

    audit_path = paths()["audit"] / f"{work}_标注审计.md"
    if not audit_path.exists():
        return False, f"缺少审计 MD: {audit_path}"

    text = audit_path.read_text(encoding="utf-8")
    vol_hdr = re.compile(
        rf"^##\s*卷{vol}\s*[：:].*$",
        re.MULTILINE,
    )
    m = vol_hdr.search(text)
    if not m:
        return False, f"审计 MD 缺少 ## 卷{vol} 区块"

    block_start = m.start()
    next_vol = re.search(r"^##\s*卷\d{3}\s*[：:]", text[m.end() :], re.MULTILINE)
    block_end = m.end() + next_vol.start() if next_vol else len(text)
    block = text[block_start:block_end]

    rows = build_paragraph_table_rows(segs)
    new_table = "### 段落覆盖清单\n" + "\n".join(rows) + "\n"
    sec_re = re.compile(r"### 段落覆盖清单\n.*?(?=\n### )", re.DOTALL)
    if not sec_re.search(block):
        return False, f"卷{vol} 块内无「### 段落覆盖清单」"

    new_block = sec_re.sub(new_table.rstrip() + "\n\n", block, count=1)
    if new_block == block:
        return False, "段落表已与 skeleton 一致"

    new_text = text[:block_start] + new_block + text[block_end:]
    audit_path.write_text(new_text, encoding="utf-8")
    return True, f"已用 skeleton 补全卷{vol} 段落表（{len(rows)} 行）"


def _find_skeleton(work: str, vol: str) -> Path | None:
    matches = sorted(paths()["annotations"].glob(f"{work}_{vol}_*_skeleton.json"))
    return matches[0] if matches else None
