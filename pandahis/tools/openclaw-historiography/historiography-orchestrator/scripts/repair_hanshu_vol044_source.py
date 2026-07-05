#!/usr/bin/env python3
"""补全汉书 044 韩彭英卢吴传：从权威原文插入韩信正文，重建段落索引。"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

ORCH = Path(__file__).resolve().parents[1]
ANNOTATE = ORCH.parent / "historiography-annotate"
SKILLS = ORCH.parent
sys.path.insert(0, str(SKILLS))
sys.path.insert(0, str(ORCH))
sys.path.insert(0, str(ANNOTATE))

from paths_config import histograph_paths, resolve_split_dir  # noqa: E402
from lib.config import paths  # noqa: E402
from lib.paragraph_index import build_index_for_file, write_index  # noqa: E402
from paragraph_utils import split_mode_for_work  # noqa: E402

WORK = "02汉书"
VOL = "044"
SOURCE_NAME = "02汉书_044_韩彭英卢吴传第四.txt"
def _resolve_auth_source() -> Path:
    override = os.environ.get("HIST_AUTH_SOURCE")
    if override:
        return Path(override)
    return (
        histograph_paths()["auth_sources"]
        / "02汉书 [流芳阁 lfglib.cn]-d4fa.txt"
    )


AUTH_SOURCE = _resolve_auth_source()
SPLIT_DIR = resolve_split_dir("02汉书_拆分后")
SRC = SPLIT_DIR / SOURCE_NAME
BACKUP = SPLIT_DIR / "backup_before_fix" / SOURCE_NAME


def _reflow(text: str, target: int = 480) -> list[str]:
    """按句号切分为与现有拆分密度相近的段落行。"""
    sents = re.split(r"(。)", text)
    parts: list[str] = []
    buf = ""
    for piece in sents:
        if not piece:
            continue
        buf += piece
        if piece == "。" and len(buf) >= target:
            parts.append(buf)
            buf = ""
    if buf.strip():
        parts.append(buf)
    return parts


def _extract_hanxin_block(full_text: str) -> str:
    start = full_text.rfind("卷三十四韩彭英卢吴传第四")
    if start < 0:
        raise RuntimeError("权威原文中未找到卷三十四韩彭英卢吴传第四")
    chunk = full_text[start:]
    end = chunk.find("彭越字仲")
    if end < 0:
        raise RuntimeError("权威原文中未找到彭越字仲分界")
    return chunk[len("卷三十四韩彭英卢吴传第四") : end].strip()


def main() -> int:
    if not AUTH_SOURCE.is_file():
        raise SystemExit(f"缺少权威原文: {AUTH_SOURCE}")
    if not SRC.is_file():
        raise SystemExit(f"缺少拆分原文: {SRC}")

    full = AUTH_SOURCE.read_text(encoding="utf-8")
    hanxin = _extract_hanxin_block(full)
    if len(hanxin) < 1000:
        raise SystemExit(f"韩信正文过短（{len(hanxin)} 字），中止")

    cur = SRC.read_text(encoding="utf-8")
    cur_lines = cur.splitlines()
    cur_body = "\n".join(cur_lines[1:]).strip()

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if not BACKUP.exists():
        shutil.copy2(SRC, BACKUP)
        print(f"  备份: {BACKUP}")

    hanxin_lines = _reflow(hanxin)
    new_text = "卷三十四韩彭英卢吴传第四\n" + "\n".join(hanxin_lines) + "\n" + cur_body + "\n"
    SRC.write_text(new_text, encoding="utf-8")

    mode = split_mode_for_work(WORK, new_text)
    idx = build_index_for_file(WORK, VOL, SRC, mode)
    fp = write_index(WORK, VOL, idx)
    print(f"  写入原文: {SRC.name}（+{len(hanxin_lines)} 段韩信正文）")
    print(f"  段落索引: {fp.name} → {idx['total']} 段 (mode={mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
