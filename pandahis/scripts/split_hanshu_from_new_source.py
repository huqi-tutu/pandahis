#!/usr/bin/env python3
"""从「二十四史新/02汉书.txt」重做拆分，输出至 02汉书_拆分后/。

- 按正文区卷首行切分（跳过目录区重复卷目）
- 删除纯空白行，不改动任何非空正文
- 跳过「返回总目录」
- 卷号与既有文件名对齐（按卷名模糊匹配）；新增「卷十九下」为 120 卷
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tools/openclaw-historiography"
ORCH = SKILLS / "historiography-orchestrator"
sys.path.insert(0, str(SKILLS))
sys.path.insert(0, str(ORCH))

from paths_config import resolve_split_dir  # noqa: E402

WORK = "02汉书"
SOURCE = ROOT / "data/00原文母本/二十四史新/02汉书.txt"
SPLIT_DIR = resolve_split_dir(f"{WORK}_拆分后")

VOL_HEADER_RE = re.compile(
    r"^卷[一二三四五六七八九十百零\d上中下之]+(?:\s+|(?=[^\s]))"
)
SKIP_LINE_RE = re.compile(r"^返回总目录\s*$")
FILENAME_RE = re.compile(rf"^{re.escape(WORK)}_(\d{{3}})_(.+)\.txt$")

CHAR_NORMALIZE = str.maketrans(
    {
        "馀": "余",
        "兒": "儿",
        "繇": "徭",
        "説": "说",
    }
)


def normalize_title_key(title: str) -> str:
    t = re.sub(r"\s+", "", title.strip())
    t = re.sub(r"[\uE000-\uF8FF\ufeff]", "", t)
    return t.translate(CHAR_NORMALIZE)


def title_from_vol_header(line: str) -> str:
    line = line.strip()
    m = re.match(r"^卷[\d一二三四五六七八九十百零上中下之]+(?:\s+|(?=[^\s]))(.+)$", line)
    if m:
        return m.group(1).strip()
    return line


def is_vol_header(line: str) -> bool:
    s = line.strip()
    if not s or SKIP_LINE_RE.match(s):
        return False
    if "。" in s and len(s) > 36:
        return False
    return bool(VOL_HEADER_RE.match(s))


def is_likely_title_line(line: str) -> bool:
    s = line.strip()
    if not s or "。" in s:
        return False
    if len(s) > 40:
        return False
    if s.startswith("卷"):
        return True
    if re.search(r"第[一二三四五六七八九十百零\d]+", s):
        return True
    return False


def read_old_header_lines(text: str) -> list[str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    header = [lines[0]]
    for ln in lines[1:]:
        if is_likely_title_line(ln):
            header.append(ln)
        else:
            break
    return header


def find_body_start(lines: list[str]) -> int:
    seen: dict[str, int] = {}
    for i, ln in enumerate(lines):
        if not is_vol_header(ln):
            continue
        key = normalize_title_key(title_from_vol_header(ln))
        if key in seen:
            return i
        seen[key] = i
    raise RuntimeError("未找到正文起始（目录区后第二次出现的卷首）")


def split_body_sections(lines: list[str], start: int) -> list[tuple[str, list[str]]]:
    indices = [i for i in range(start, len(lines)) if is_vol_header(lines[i])]
    sections: list[tuple[str, list[str]]] = []
    for idx, pos in enumerate(indices):
        end = indices[idx + 1] if idx + 1 < len(indices) else len(lines)
        header = lines[pos].strip()
        body: list[str] = []
        for ln in lines[pos + 1 : end]:
            if not ln.strip():
                continue
            if SKIP_LINE_RE.match(ln.strip()):
                continue
            if is_vol_header(ln):
                continue
            body.append(ln.rstrip("\n"))
        sections.append((header, body))
    return sections


def load_existing_volume_map() -> dict[str, tuple[str, Path, list[str]]]:
    """norm_title -> (vol, path, header_lines)"""
    mapping: dict[str, tuple[str, Path, list[str]]] = {}
    for fp in SPLIT_DIR.glob(f"{WORK}_*.txt"):
        if "backup" in fp.parts:
            continue
        m = FILENAME_RE.match(fp.name)
        if not m:
            continue
        vol, title_suffix = m.group(1), m.group(2)
        text = fp.read_text(encoding="utf-8")
        header = read_old_header_lines(text)
        key = normalize_title_key(title_suffix)
        mapping[key] = (vol, fp, header)
    return mapping


def header_lines_from_vol_header(header: str) -> list[str]:
    h = header.strip()
    m = re.match(r"^(卷[\d一二三四五六七八九十百零上中下之]+)\s+(.+)$", h)
    if m and re.search(r"[上下]$", m.group(1)):
        return [m.group(1), m.group(2)]
    return [h]


def format_new_volume_filename(vol: str, title: str) -> str:
    return f"{WORK}_{vol}_{title}.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description="从二十四史新母本重做汉书拆分")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    parser.add_argument("--no-backup", action="store_true", help="不写备份目录")
    args = parser.parse_args()

    if not SOURCE.is_file():
        raise SystemExit(f"源文件不存在: {SOURCE}")

    raw = SOURCE.read_text(encoding="utf-8")
    lines = raw.splitlines()
    body_start = find_body_start(lines)
    sections = split_body_sections(lines, body_start)
    existing = load_existing_volume_map()

    print(f"源文件: {SOURCE}")
    print(f"正文起始: 第 {body_start + 1} 行")
    print(f"切分卷数: {len(sections)}")
    print(f"既有卷映射: {len(existing)} 个文件")

    assignments: list[tuple[str, Path, list[str], list[str], str]] = []
    used_vols: set[str] = set()
    unmatched: list[str] = []

    for header, body in sections:
        title = title_from_vol_header(header)
        key = normalize_title_key(title)
        if key in existing:
            vol, old_fp, header_lines = existing[key]
            out_name = old_fp.name
        else:
            vol = "120"
            if vol in used_vols:
                raise RuntimeError(f"卷号 120 已被占用，无法写入新卷: {header}")
            out_name = format_new_volume_filename(vol, title)
            header_lines = header_lines_from_vol_header(header)
            unmatched.append(header)

        out_path = SPLIT_DIR / out_name
        used_vols.add(vol)
        assignments.append((vol, out_path, header_lines, body, header))

    if len(assignments) != len(sections):
        raise RuntimeError("卷分配数量异常")

    mapped = len(sections) - len(unmatched)
    print(f"匹配既有卷号: {mapped}，新增: {len(unmatched)}")
    for h in unmatched:
        print(f"  + 新卷: {h}")

    blank_check = sum(1 for _, _, _, body, _ in assignments for ln in body if not ln.strip())
    if blank_check:
        raise RuntimeError(f"输出仍含 {blank_check} 行空白正文")

    if args.dry_run:
        for vol, path, header_lines, body, src_header in assignments[:5]:
            print(f"  {vol} {path.name}: header={len(header_lines)} body={len(body)}")
        print("  …")
        return 0

    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = SPLIT_DIR / f"backup_before_new_resplit_{stamp}"
        backup.mkdir(parents=True, exist_ok=True)
        for fp in SPLIT_DIR.glob(f"{WORK}_*.txt"):
            if fp.is_file():
                shutil.copy2(fp, backup / fp.name)
        print(f"已备份至 {backup}")

    written = 0
    for vol, out_path, header_lines, body, _ in assignments:
        parts = header_lines + body
        text = "\n".join(parts)
        if raw.endswith("\n") or parts:
            text += "\n"
        out_path.write_text(text, encoding="utf-8")
        written += 1

    print(f"✅ 已写入 {written} 个文件 → {SPLIT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
