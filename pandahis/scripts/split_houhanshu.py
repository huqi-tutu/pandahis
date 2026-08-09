#!/usr/bin/env python3
"""从「二十四史原文/03后汉书.txt」按卷拆分，输出至 03后汉书_拆分后/。

样式对齐现有《汉书》拆分：
- 文件名：03后汉书_NNN_标题.txt
- 卷首行：卷号/志号 + 双空格 + 标题（单行）
- 删除纯空白行，跳过「返回总目录」
- 不改动任何非空正文
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

WORK = "03后汉书"
SOURCE = ROOT / "data/00原文母本/二十四史原文/03后汉书.txt"
SPLIT_DIR = resolve_split_dir(f"{WORK}_拆分后")

# 卷首：卷一上 / 卷四十上 / 卷九十 …
VOL_HEADER_RE = re.compile(
    r"^卷[一二三四五六七八九十百零\d上中下之]+(?:\s+|(?=[^\s]))"
)
# 志首：志第一 / 志第三十 …
ZHI_HEADER_RE = re.compile(
    r"^志第[一二三四五六七八九十百]+(?:\s+|(?=[^\s]))"
)
SKIP_LINE_RE = re.compile(r"^返回总目录\s*$")
TITLE_EXTRACT_RE = re.compile(
    r"^(?:卷[\d一二三四五六七八九十百零上中下之]+|志第[一二三四五六七八九十百]+)"
    r"(?:\s+|(?=[^\s]))(.+)$"
)


def normalize_title_key(title: str) -> str:
    return re.sub(r"\s+", "", title.strip())


def title_from_header(line: str) -> str:
    line = line.strip()
    m = TITLE_EXTRACT_RE.match(line)
    if m:
        return m.group(1).strip()
    return line


def is_vol_header(line: str) -> bool:
    s = line.strip()
    if not s or SKIP_LINE_RE.match(s):
        return False
    # 正文长句中偶含「卷×」字样，用句号 + 长度过滤
    if "。" in s and len(s) > 36:
        return False
    return bool(VOL_HEADER_RE.match(s) or ZHI_HEADER_RE.match(s))


def find_body_start(lines: list[str]) -> int:
    """目录区后，同一卷首第二次出现处即为正文起点。"""
    seen: dict[str, int] = {}
    for i, ln in enumerate(lines):
        if not is_vol_header(ln):
            continue
        key = normalize_title_key(title_from_header(ln))
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


def format_header_line(header: str) -> str:
    """统一为「卷号/志号 + 双空格 + 标题」。"""
    h = re.sub(r"\s+", " ", header.strip())
    m = re.match(
        r"^(卷[\d一二三四五六七八九十百零上中下之]+|志第[一二三四五六七八九十百]+)\s+(.+)$",
        h,
    )
    if not m:
        return h
    return f"{m.group(1)}  {m.group(2)}"


def safe_filename_title(title: str) -> str:
    # 保留全角括号等中文标点；去掉路径非法字符
    t = title.strip()
    for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|'):
        t = t.replace(ch, "＿")
    return t


def main() -> int:
    parser = argparse.ArgumentParser(description="拆分《后汉书》为按卷 txt")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    parser.add_argument(
        "--expect",
        type=int,
        default=130,
        help="期望卷数（纪传分卷 + 志，默认 130）",
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

    blank_check = sum(1 for _, body in sections for ln in body if not ln.strip())
    if blank_check:
        raise SystemExit(f"输出仍含 {blank_check} 行空白正文")

    assignments: list[tuple[str, str, list[str]]] = []
    for i, (header, body) in enumerate(sections, start=1):
        title = title_from_header(header)
        if not title:
            raise SystemExit(f"无法解析标题: {header}")
        vol = f"{i:03d}"
        out_name = f"{WORK}_{vol}_{safe_filename_title(title)}.txt"
        header_line = format_header_line(header)
        assignments.append((out_name, header_line, body))

    if args.dry_run:
        for name, header_line, body in assignments[:8]:
            print(f"  {name}: header={header_line!r} body_lines={len(body)}")
        print("  …")
        for name, header_line, body in assignments[-3:]:
            print(f"  {name}: header={header_line!r} body_lines={len(body)}")
        return 0

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    # 清理同前缀旧文件，避免残留错卷
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
