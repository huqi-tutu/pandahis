#!/usr/bin/env python3
"""细拆汉书 044/048 原文行界，重建段落索引，供重标。"""

from __future__ import annotations

import json
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

from paths_config import resolve_split_dir  # noqa: E402
from lib.config import paths  # noqa: E402
from lib.paragraph_index import build_index_for_file, write_index  # noqa: E402
from paragraph_utils import split_mode_for_work  # noqa: E402

WORK = "02汉书"
SPLIT_DIR = resolve_split_dir("02汉书_拆分后")
BACKUP_DIR = SPLIT_DIR / "backup_before_fix"


def _backup(src: Path) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dst = BACKUP_DIR / src.name
    if not dst.exists():
        shutil.copy2(src, dst)


def _split_before(text: str, markers: list[str]) -> str:
    """在首次出现的 marker 前插入换行（已是行首则跳过）。"""
    out = text
    for marker in markers:
        pat = re.compile(rf"(?<!\n)({re.escape(marker)})")
        out = pat.sub(r"\n\1", out, count=1)
    return out


def repair_vol044() -> int:
    vol = "044"
    src = SPLIT_DIR / "02汉书_044_韩彭英卢吴传第四.txt"
    _backup(src)
    lines = src.read_text(encoding="utf-8").splitlines()
    body = "\n".join(lines[1:])
    body = _split_before(body, ["吴芮，秦时番阳令也，"])
    new_text = lines[0] + "\n" + body + "\n"
    src.write_text(new_text, encoding="utf-8")
    mode = split_mode_for_work(WORK, new_text)
    idx = build_index_for_file(WORK, vol, src, mode)
    write_index(WORK, vol, idx)
    print(f"  044: {src.name} → {idx['total']} 段")
    return idx["total"]


def _reflow(text: str, target: int = 480) -> list[str]:
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


def repair_vol048() -> int:
    vol = "048"
    src = SPLIT_DIR / "02汉书_048_高五王传第八.txt"
    backup = BACKUP_DIR / src.name
    if not backup.is_file():
        raise SystemExit(f"缺少备份: {backup}")
    _backup(src)
    raw = backup.read_text(encoding="utf-8").splitlines()
    header = raw[0]
    line2 = raw[1]

    body = line2
    for old, new in [
        ("淮南厉王长自有传。", "淮南厉王长自有传。\n"),
        ("子襄嗣。赵隐王如意，", "子襄嗣。\n赵隐王如意，"),
        ("。无子，绝。赵幽王友，", "。无子，绝。\n赵幽王友，"),
        ("皆封其子为列侯。赵共王恢。", "皆封其子为列侯。\n赵共王恢。"),
        ("废其嗣。燕灵王建。", "废其嗣。\n燕灵王建。"),
        ("绝后。齐悼惠王子，", "绝后。\n齐悼惠王子，"),
    ]:
        if old not in body:
            raise SystemExit(f"048 拆段锚点缺失: {old[:24]}")
        body = body.replace(old, new, 1)

    praise = ""
    if "赞曰：" in body:
        body, praise = body.split("赞曰：", 1)
        praise = "赞曰：" + praise.strip()

    gene_start = body.find("齐悼惠王子，")
    if gene_start < 0:
        raise SystemExit("048 未找到齐悼惠王子世系段")
    main = body[:gene_start].strip()
    genealogy = body[gene_start:].strip()
    gene_lines = _reflow(genealogy, 480)

    chunks = [header, main, *gene_lines]
    if praise:
        chunks.append(praise)
    new_text = "\n".join(chunks) + "\n"
    src.write_text(new_text, encoding="utf-8")
    mode = split_mode_for_work(WORK, new_text)
    idx = build_index_for_file(WORK, vol, src, mode)
    write_index(WORK, vol, idx)
    print(f"  048: {src.name} → {idx['total']} 段")
    return idx["total"]


def main() -> int:
    n44 = repair_vol044()
    n48 = repair_vol048()
    print(f"✅ 段落索引已更新（044={n44} 段，048={n48} 段）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
