#!/usr/bin/env python3
"""从「二十四史原文/04三国志.txt」按卷拆分，输出至 04三国志_拆分后/。

样式对齐现有《后汉书》拆分：
- 文件名：04三国志_NNN_篇名.txt（如 武帝纪第一）
- 卷首行：卷号 + 书部（魏书/蜀书/吴书） + 双空格 + 篇名（单行）
- 删除纯空白行，跳过「返回总目录」
- 不改动任何非空正文
- 文末「上三国志注表」无独立卷号，归入卷六十五
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tools/openclaw-historiography"
sys.path.insert(0, str(SKILLS))

from paths_config import resolve_split_dir  # noqa: E402

WORK = "04三国志"
SOURCE = ROOT / "data/00原文母本/二十四史原文/04三国志.txt"
SPLIT_DIR = resolve_split_dir(f"{WORK}_拆分后")

# 卷首：卷一 魏书一 / 卷三十一 蜀书一 / 卷四十六 吴书一 …
VOL_HEADER_RE = re.compile(
    r"^卷[一二三四五六七八九十百零\d]+"
    r"(?:\s+(?:魏|蜀|吴)书[一二三四五六七八九十百零\d]+)?$"
)
SKIP_LINE_RE = re.compile(r"^返回总目录\s*$")
TITLE_LINE_RE = re.compile(
    r".+第[一二三四五六七八九十百零\d]+(?:[上中下])?$"
)


def normalize_title_key(title: str) -> str:
    return re.sub(r"\s+", "", title.strip())


def is_vol_header(line: str) -> bool:
    s = line.strip()
    if not s or SKIP_LINE_RE.match(s):
        return False
    if "。" in s and len(s) > 36:
        return False
    return bool(VOL_HEADER_RE.match(s))


def is_chapter_title(line: str) -> bool:
    s = line.strip()
    if not s or "。" in s:
        return False
    if len(s) > 40:
        return False
    if is_vol_header(s):
        return False
    return bool(TITLE_LINE_RE.match(s))


def find_body_start(lines: list[str]) -> int:
    """目录区后，同一卷首第二次出现处即为正文起点。"""
    seen: dict[str, int] = {}
    for i, ln in enumerate(lines):
        if not is_vol_header(ln):
            continue
        key = normalize_title_key(ln)
        if key in seen:
            return i
        seen[key] = i
    raise RuntimeError("未找到正文起始（目录区后第二次出现的卷首）")


def split_body_sections(lines: list[str], start: int) -> list[tuple[str, str, list[str]]]:
    """返回 (卷首原行, 篇名, 正文行)。"""
    indices = [i for i in range(start, len(lines)) if is_vol_header(lines[i])]
    sections: list[tuple[str, str, list[str]]] = []
    for idx, pos in enumerate(indices):
        end = indices[idx + 1] if idx + 1 < len(indices) else len(lines)
        header = lines[pos].strip()
        body_raw: list[str] = []
        for ln in lines[pos + 1 : end]:
            if not ln.strip():
                continue
            if SKIP_LINE_RE.match(ln.strip()):
                continue
            if is_vol_header(ln):
                continue
            body_raw.append(ln.rstrip("\n"))

        if not body_raw:
            raise RuntimeError(f"卷无正文: {header}")

        title = body_raw[0].strip()
        if not is_chapter_title(title):
            raise RuntimeError(f"卷首后首行非篇名: {header!r} → {title!r}")
        body = body_raw[1:]
        sections.append((header, title, body))
    return sections


def format_header_line(vol_header: str, title: str) -> str:
    """统一为「卷号 书部  +  篇名」。"""
    h = re.sub(r"\s+", " ", vol_header.strip())
    return f"{h}  {title.strip()}"


def safe_filename_title(title: str) -> str:
    t = title.strip()
    for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|"):
        t = t.replace(ch, "＿")
    return t


def main() -> int:
    parser = argparse.ArgumentParser(description="拆分《三国志》为按卷 txt")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    parser.add_argument(
        "--expect",
        type=int,
        default=65,
        help="期望卷数（魏30 + 蜀15 + 吴20，默认 65）",
    )
    args = parser.parse_args()

    if not SOURCE.is_file():
        raise SystemExit(f"源文件不存在: {SOURCE}")

    raw = SOURCE.read_text(encoding="utf-8")
    lines = raw.splitlines()
    body_start = find_body_start(lines)
    sections = split_body_sections(lines, body_start)

    print(f"源文件: {SOURCE}")
    print(f"正文起始: 第 {body_start + 1} 行")
    print(f"切分卷数: {len(sections)}")

    if len(sections) != args.expect:
        raise SystemExit(
            f"卷数不符：得到 {len(sections)}，期望 {args.expect}。"
            "请检查卷首识别规则。"
        )

    blank_check = sum(1 for _, _, body in sections for ln in body if not ln.strip())
    if blank_check:
        raise SystemExit(f"输出仍含 {blank_check} 行空白正文")

    assignments: list[tuple[str, str, list[str]]] = []
    for i, (vol_header, title, body) in enumerate(sections, start=1):
        vol = f"{i:03d}"
        out_name = f"{WORK}_{vol}_{safe_filename_title(title)}.txt"
        header_line = format_header_line(vol_header, title)
        assignments.append((out_name, header_line, body))

    if args.dry_run:
        for name, header_line, body in assignments[:8]:
            print(f"  {name}: header={header_line!r} body_lines={len(body)}")
        print("  …")
        for name, header_line, body in assignments[-3:]:
            print(f"  {name}: header={header_line!r} body_lines={len(body)}")
        return 0

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    for old in SPLIT_DIR.glob(f"{WORK}_*.txt"):
        old.unlink()

    written = 0
    for out_name, header_line, body in assignments:
        parts = [header_line, *body]
        text = "\n".join(parts) + "\n"
        (SPLIT_DIR / out_name).write_text(text, encoding="utf-8")
        written += 1

    print(f"✅ 已写入 {written} 个文件 → {SPLIT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
